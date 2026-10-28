"""
Mantém os dados da página (index.html) atualizados.

Arquivos
  - dados_historicos.js  fechamentos e inflação consolidados (embutidos na página).
                         O campo "completoAte" diz até que dia os fechamentos estão nele.
  - ibov_recente.js      fechamentos depois de "completoAte" e inflação dos últimos 3 anos.

Fontes
  - Ibovespa: B3 (os mesmos dados do download "Evolução Diária" em Estatísticas
    históricas). Se a B3 falhar num ano, só aquele ano vem do Yahoo Finance (^BVSP).
  - Inflação: IPCA (SGS 433) e IGP-DI (SGS 190), mensais, da API do Banco Central.

O que cada execução faz
  1. Lê "completoAte" do histórico e baixa os fechamentos do ano seguinte a essa data
     em diante (normalmente só o ano corrente; em janeiro, também o ano que terminou).
  2. Valida a série (datas, valores, saltos, continuidade com o histórico).
  3. Virada de ano automática: os anos já encerrados saem do arquivo recente e entram
     no histórico, assim como os meses de inflação já publicados (IPCA e IGP-DI) até o
     fim do período consolidado.
  4. Grava só o que mudou, de forma atômica. Sem mudanças, não grava nada.
  Se a validação falhar, sai com código 1 e não toca em nenhum arquivo.

Uso:    py atualizar_ibov.py            atualiza
        py atualizar_ibov.py --simular  mostra o que faria, sem gravar
Requer: pip install -r requirements.txt
        (o yfinance só é instalado automaticamente se a B3 falhar)
"""
from __future__ import annotations

import argparse
import base64
import importlib
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

PASTA = Path(__file__).resolve().parent
ARQ_RECENTE = PASTA / "ibov_recente.js"
ARQ_HISTORICO = PASTA / "dados_historicos.js"
PREFIXO_RECENTE = "window.IBOV_RECENTE = "
PREFIXO_HISTORICO = "window.IBOV_HISTORICO = "

HDR = {"User-Agent": "Mozilla/5.0"}
YFINANCE_VERSAO = "1.7.0"

# Brasil sem horário de verão desde 2019; evita depender do pacote tzdata no Windows.
FUSO_BRASILIA = timezone(timedelta(hours=-3), "BRT")

# O circuit breaker da B3 encerra o pregão em ±20%; acima disso é dado errado.
VARIACAO_DIARIA_MAX = 0.25

Ponto = tuple[date, float]


class ErroDados(Exception):
    """Dados baixados ou arquivos locais não passaram na validação."""


def ddmmaaaa(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def ler_data(s: str) -> date:
    return datetime.strptime(s, "%d/%m/%Y").date()


# ---------------------------------------------------------------- HTTP

def get(url: str, tentativas: int = 4) -> requests.Response:
    """GET com novas tentativas; lança RuntimeError com o último motivo."""
    motivo = ""
    for t in range(tentativas):
        try:
            r = requests.get(url, headers=HDR, timeout=60)
            if r.ok:
                return r
            motivo = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            motivo = e.__class__.__name__
        print(f"  {motivo}, tentando de novo...")
        time.sleep(3 * (t + 1))
    raise RuntimeError(f"{motivo} em {url}")


# ---------------------------------------------------------------- Ibovespa

def b3_ano(ano: int) -> list[Ponto]:
    """Fechamentos de um ano pela B3. Lista vazia se o ano ainda não tem pregões."""
    param = base64.b64encode(json.dumps(
        {"index": "IBOV", "language": "pt-br", "year": str(ano)}).encode()).decode()
    url = ("https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/"
           f"IndexCall/GetDownloadPortfolioDay/{param}")
    txt = get(url).text.strip().strip('"')
    if not txt.startswith(("IBOV", "Dia", "﻿")):
        txt = base64.b64decode(txt).decode("latin-1")   # a B3 devolve o CSV em base64

    # Layout: uma linha por dia do mês ("1".."31"), uma coluna por mês; linhas
    # de mínimo/máximo no fim não começam com número e são ignoradas.
    pontos = []
    for linha in txt.splitlines():
        campos = linha.split(";")
        if not campos[0].strip().isdigit():
            continue
        dia = int(campos[0])
        for mes, valor in enumerate(campos[1:13], 1):
            valor = valor.strip()
            if not valor:
                continue
            try:
                d = date(ano, mes, dia)
            except ValueError:          # 31/04 etc.
                continue
            pontos.append((d, float(valor.replace(".", "").replace(",", "."))))
    return pontos


def importar_yfinance():
    """Importa o yfinance, instalando a versão fixada se faltar (fallback raro)."""
    try:
        return importlib.import_module("yfinance")
    except ImportError:
        print(f"  instalando yfinance=={YFINANCE_VERSAO}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
                               f"yfinance=={YFINANCE_VERSAO}"])
        return importlib.import_module("yfinance")


def yahoo_ano(ano: int) -> list[Ponto]:
    yf = importar_yfinance()
    df = yf.download("^BVSP", start=f"{ano}-01-01", end=f"{ano + 1}-01-01",
                     progress=False, auto_adjust=False)
    if df is None or df.empty:
        return []
    serie = df["Close"].squeeze("columns").dropna()
    return [(ts.date(), round(float(v), 2)) for ts, v in serie.items()]


def ibovespa(ano_inicial: int, hoje: date) -> tuple[list[Ponto], str]:
    """Série de ano_inicial até hoje. Fallback para o Yahoo é feito ano a ano."""
    dados: list[Ponto] = []
    anos_yahoo = []
    for ano in range(ano_inicial, hoje.year + 1):
        print(f"B3 {ano}...")
        try:
            pontos = b3_ano(ano)
        except Exception as e:                       # noqa: BLE001 - qualquer falha da B3
            print(f"  B3 falhou ({e}); tentando Yahoo Finance para {ano}.")
            pontos = yahoo_ano(ano)
            if pontos:
                anos_yahoo.append(ano)
        if not pontos:
            if ano == hoje.year:
                print(f"  {ano} ainda sem pregões; seguindo.")
                continue
            raise ErroDados(f"nenhum dado para {ano} (B3 e Yahoo)")
        dados += pontos
    fonte = "B3" if not anos_yahoo else \
        "B3 + Yahoo Finance (" + ", ".join(map(str, anos_yahoo)) + ")"
    return sorted(dados), fonte


def validar_serie(serie: list[Ponto]) -> None:
    datas = [d for d, _ in serie]
    if len(set(datas)) != len(datas):
        raise ErroDados("datas duplicadas")
    if datas != sorted(datas):
        raise ErroDados("datas fora de ordem")
    if any(v <= 0 for _, v in serie):
        raise ErroDados("fechamento menor ou igual a zero")
    for (_, v0), (d1, v1) in zip(serie, serie[1:]):
        if abs(v1 / v0 - 1) > VARIACAO_DIARIA_MAX:
            raise ErroDados(f"variação suspeita em {ddmmaaaa(d1)}: {v0} -> {v1}")


# ---------------------------------------------------------------- Inflação

def sgs(codigo: int, inicio: date) -> dict[str, float]:
    url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
           f"?formato=json&dataInicial={ddmmaaaa(inicio)}")
    r = get(url)
    if not r.text.lstrip().startswith("["):
        raise RuntimeError(f"SGS {codigo} não devolveu JSON")
    return {d["data"][3:]: float(d["valor"]) for d in r.json()}


def inflacao(hoje: date) -> list[list]:
    """[["mm/aaaa", ipca|None, igpdi|None], ...]. None = ainda não divulgado."""
    inicio = date(hoje.year - 2, 1, 1)
    ipca, igp = sgs(433, inicio), sgs(190, inicio)
    meses = sorted(set(ipca) | set(igp), key=lambda m: (m[3:], m[:2]))
    return [[m, ipca.get(m), igp.get(m)] for m in meses]


# ---------------------------------------------------------------- Histórico

class Historico:
    """dados_historicos.js: fechamentos codificados como deslocamentos em dias."""

    def __init__(self, bruto: dict):
        self.bruto = bruto
        inicio = ler_data(bruto["inicio"])
        self.datas: list[date] = []
        d = inicio
        for desloc in bruto["dias"]:
            d = d + timedelta(days=desloc)
            self.datas.append(d)
        self.fechamentos: list[float] = list(bruto["fechamentos"])
        if len(self.datas) != len(self.fechamentos):
            raise ErroDados("dados_historicos.js: 'dias' e 'fechamentos' com tamanhos diferentes")
        self.completo_ate = ler_data(bruto.get("completoAte") or ddmmaaaa(self.datas[-1]))
        infl = bruto["inflacao"]
        self.infl_inicio = infl["inicio"]                       # "mm/aaaa"
        self.ipca: list[float] = list(infl["ipcaEncadeado"])
        self.igpdi: list[float] = list(infl["igpdi"])

    @classmethod
    def ler(cls) -> "Historico":
        txt = ARQ_HISTORICO.read_text(encoding="utf-8")
        ini = txt.index(PREFIXO_HISTORICO) + len(PREFIXO_HISTORICO)
        return cls(json.loads(txt[ini: txt.rindex("}") + 1]))

    def mes_do_indice(self, k: int) -> tuple[int, int]:
        m0, a0 = map(int, self.infl_inicio.split("/"))
        m = m0 - 1 + k
        return a0 + m // 12, m % 12 + 1

    def ultimo_mes_inflacao(self) -> str:
        a, m = self.mes_do_indice(len(self.ipca) - 1)
        return f"{m:02d}/{a}"

    def para_js(self) -> str:
        inicio = ler_data(self.bruto["inicio"])
        dias, anterior = [], inicio
        for d in self.datas:
            dias.append((d - anterior).days)
            anterior = d
        dados = {
            "inicio": self.bruto["inicio"],
            "completoAte": ddmmaaaa(self.completo_ate),
            "dias": dias,
            "fechamentos": self.fechamentos,
            "inflacao": {"inicio": self.infl_inicio, "ipcaEncadeado": self.ipca, "igpdi": self.igpdi},
        }
        cabecalho = (
            "/* Dados históricos embutidos. Gerado por atualizar_ibov.py; não editar à mão.\n"
            " * completoAte : fechamentos consolidados até esta data; o ibov_recente.js cobre o que vem depois\n"
            " * dias        : deslocamento em dias corridos do pregão anterior (o 1º é contado a partir de \"inicio\")\n"
            " * fechamentos : fechamento do Ibovespa em pontos, na escala atual (B3)\n"
            " * inflacao    : variação % mensal a partir de \"inicio\"; ipcaEncadeado = IPCA desde 1980, IGP-DI antes\n"
            " * Fontes: B3 (IBOVDIA.XLS 1968–1997, \"Evolução Diária\" a partir de 1998); BCB SGS 433 e 190.\n"
            f" * Último pregão embutido: {ddmmaaaa(self.datas[-1])}. Inflação até {self.ultimo_mes_inflacao()}.\n"
            " */\n")
        return cabecalho + PREFIXO_HISTORICO + json.dumps(dados, separators=(",", ":"),
                                                          ensure_ascii=False) + ";\n"


def consolidar(hist: Historico, serie: list[Ponto], infl: list[list], hoje: date) -> list[str]:
    """
    Virada de ano: move para o histórico os anos encerrados (anteriores ao ano de `hoje`)
    e os meses de inflação já publicados até o fim do período consolidado.
    Altera `hist` no lugar; devolve a lista do que foi feito (vazia = nada).
    """
    feito = []
    fim_ano_passado = date(hoje.year - 1, 12, 31)
    novos = [(d, v) for d, v in serie if hist.completo_ate < d <= fim_ano_passado]
    if novos and hist.completo_ate < fim_ano_passado:
        ultimo = novos[-1][0]
        if ultimo.month != 12 or ultimo.day < 20:
            raise ErroDados(f"ano {ultimo.year} parece incompleto (último pregão {ddmmaaaa(ultimo)}); "
                            "consolidação adiada")
        hist.datas += [d for d, _ in novos]
        hist.fechamentos += [v for _, v in novos]
        hist.completo_ate = fim_ano_passado
        feito.append(f"{len(novos)} pregões até {ddmmaaaa(ultimo)} incorporados ao histórico")

    # Inflação: acrescenta meses contínuos com IPCA e IGP-DI publicados, até o mês de completoAte.
    por_mes = {m: (ipca, igp) for m, ipca, igp in infl}
    limite = (hist.completo_ate.year, hist.completo_ate.month)
    meses_add = []
    while True:
        a, m = hist.mes_do_indice(len(hist.ipca))
        ipca, igp = por_mes.get(f"{m:02d}/{a}", (None, None))
        if (a, m) > limite or ipca is None or igp is None:
            break
        hist.ipca.append(ipca)
        hist.igpdi.append(igp)
        meses_add.append(f"{m:02d}/{a}")
    if meses_add:
        feito.append(f"inflação de {meses_add[0]} a {meses_add[-1]} incorporada ao histórico")
    return feito


# ---------------------------------------------------------------- Arquivo recente

def ler_recente() -> dict | None:
    if not ARQ_RECENTE.exists():
        return None
    txt = ARQ_RECENTE.read_text(encoding="utf-8").strip()
    try:
        return json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
    except ValueError:
        print("Aviso: ibov_recente.js atual não pôde ser lido; será substituído.")
        return None


def recente_para_js(dados: dict) -> str:
    """Um registro por linha, para os diffs do Git mostrarem só os dias novos."""
    def lista(itens):
        if not itens:
            return "[]"
        return "[\n" + ",\n".join("  " + json.dumps(x, ensure_ascii=False) for x in itens) + "\n]"
    return (PREFIXO_RECENTE + "{\n"
            f'"gerado": {json.dumps(dados["gerado"])},\n'
            f'"fonte": {json.dumps(dados["fonte"], ensure_ascii=False)},\n'
            f'"d": {lista(dados["d"])},\n'
            f'"infl": {lista(dados["infl"])}\n'
            "};\n")


def gravar_atomico(caminho: Path, texto: str) -> None:
    tmp = caminho.with_name(caminho.name + ".tmp")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, caminho)


# ---------------------------------------------------------------- Main

def main(argv: list[str] | None = None) -> int:
    args = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    args.add_argument("--simular", action="store_true", help="mostra o que faria, sem gravar")
    args.add_argument("--hoje", help=argparse.SUPPRESS)        # só para testes: dd/mm/aaaa
    opcoes = args.parse_args(argv)

    hoje = ler_data(opcoes.hoje) if opcoes.hoje else datetime.now(FUSO_BRASILIA).date()
    try:
        hist = Historico.ler()
    except (OSError, ValueError, KeyError, ErroDados) as e:
        print(f"ERRO: não foi possível ler dados_historicos.js ({e}).")
        return 1
    anterior = ler_recente()
    ultima_publicada = max([hist.completo_ate] + ([ler_data(anterior["d"][-1][0])]
                                                  if anterior and anterior.get("d") else []))

    # O arquivo recente começa em 1º de janeiro do ano seguinte a "completoAte"
    # (ou do próprio ano, se o histórico terminar no meio dele).
    ano_inicial = (hist.completo_ate + timedelta(days=1)).year
    try:
        serie, fonte = ibovespa(ano_inicial, hoje)
        validar_serie(serie)
        if serie and serie[-1][0] < ultima_publicada:
            raise ErroDados(f"série termina em {ddmmaaaa(serie[-1][0])}, antes da versão "
                            f"publicada ({ddmmaaaa(ultima_publicada)})")
        depois = [(d, v) for d, v in serie if d > hist.completo_ate]
        if depois and abs(depois[0][1] / hist.fechamentos[-1] - 1) > VARIACAO_DIARIA_MAX:
            raise ErroDados(f"salto entre o histórico ({hist.fechamentos[-1]}) e "
                            f"{ddmmaaaa(depois[0][0])} ({depois[0][1]})")
    except (ErroDados, RuntimeError) as e:
        print(f"ERRO: {e}. Nenhum arquivo foi alterado.")
        return 1

    try:
        infl = inflacao(hoje)
    except Exception as e:                           # noqa: BLE001
        print(f"Aviso: inflação não atualizada ({e}); mantendo a anterior.")
        infl = (anterior or {}).get("infl", [])

    hist_antes = hist.para_js()
    try:
        feito = consolidar(hist, serie, infl, hoje)
    except ErroDados as e:
        print(f"Aviso: {e}.")
        feito = []
    mudou_historico = hist.para_js() != hist_antes

    d = [[ddmmaaaa(p), v] for p, v in serie if p > hist.completo_ate]
    mudou_recente = not (anterior and anterior.get("d") == d and anterior.get("infl") == infl
                         and anterior.get("fonte") == fonte)

    for linha in feito:
        print(f"Virada de ano: {linha}.")
    if not mudou_recente and not mudou_historico:
        ultimo = d[-1][0] if d else ddmmaaaa(hist.datas[-1])
        print(f"Sem dados novos (último pregão {ultimo}).")
        return 0
    if opcoes.simular:
        print(f"[simulação] gravaria: {'dados_historicos.js ' if mudou_historico else ''}"
              f"{'ibov_recente.js' if mudou_recente else ''}")
        return 0

    # Histórico primeiro: se o recente falhar depois, a página continua sem buraco
    # (o histórico novo já cobre os dias que o recente antigo trazia).
    if mudou_historico:
        gravar_atomico(ARQ_HISTORICO, hist.para_js())
    if mudou_recente:
        gravar_atomico(ARQ_RECENTE, recente_para_js({
            "gerado": datetime.now(FUSO_BRASILIA).strftime("%d/%m/%Y %H:%M"),
            "fonte": fonte, "d": d, "infl": infl,
        }))
    ipca_ate = next((m for m, ipca, _ in reversed(infl) if ipca is not None), "-")
    print(f"OK: histórico até {ddmmaaaa(hist.completo_ate)}; recente com {len(d)} pregões"
          f"{' até ' + d[-1][0] if d else ''} ({fonte}); IPCA até {ipca_ate}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
