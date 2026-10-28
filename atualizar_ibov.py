"""
Atualiza ibov_recente.js, o arquivo de dados recentes lido pela página (index.html).

Fontes
  - Ibovespa: fechamentos diários de ANO_INICIAL até o ano atual, direto da B3
    (os mesmos dados do download "Evolução Diária" em Estatísticas históricas).
    Se a B3 falhar num ano, só aquele ano vem do Yahoo Finance (^BVSP).
  - Inflação: IPCA (SGS 433) e IGP-DI (SGS 190), mensais, dos últimos 3 anos,
    da API do Banco Central.

Comportamento
  - Valida a série antes de gravar; se algo parecer errado, sai com código 1
    e não toca no arquivo existente.
  - Se os dados forem iguais aos do arquivo atual, não grava nada
    (assim o GitHub Actions não faz commit em feriados).
  - Grava de forma atômica (arquivo temporário + rename).

Uso:   py atualizar_ibov.py
Requer: pip install -r requirements.txt
        (o yfinance só é instalado automaticamente se a B3 falhar)
"""
from __future__ import annotations

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

# A página traz embutidos (dados_historicos.js) todos os fechamentos até 26/10/2026.
# Este arquivo precisa começar no máximo no dia seguinte; começar em 1º de janeiro
# do ano do corte é o mais simples. Mude junto com dados_historicos.js (ver README).
ANO_INICIAL = 2026

SAIDA = Path(__file__).with_name("ibov_recente.js")
PREFIXO_JS = "window.IBOV_RECENTE = "
HDR = {"User-Agent": "Mozilla/5.0"}
YFINANCE_VERSAO = "1.7.0"

# Brasil sem horário de verão desde 2019; evita depender do pacote tzdata no Windows.
FUSO_BRASILIA = timezone(timedelta(hours=-3), "BRT")

# O circuit breaker da B3 encerra o pregão em ±20%; acima disso é dado errado.
VARIACAO_DIARIA_MAX = 0.25

Ponto = tuple[date, float]


class ErroDados(Exception):
    """Dados baixados não passaram na validação."""


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


def ibovespa(hoje: date) -> tuple[list[Ponto], str]:
    """Série de ANO_INICIAL até hoje. Fallback para o Yahoo é feito ano a ano."""
    dados: list[Ponto] = []
    anos_yahoo = []
    for ano in range(ANO_INICIAL, hoje.year + 1):
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


def validar(serie: list[Ponto], ultima_anterior: date | None) -> None:
    if not serie:
        raise ErroDados("série vazia")
    datas = [d for d, _ in serie]
    if len(set(datas)) != len(datas):
        raise ErroDados("datas duplicadas")
    if any(v <= 0 for _, v in serie):
        raise ErroDados("fechamento menor ou igual a zero")
    for (_, v0), (d1, v1) in zip(serie, serie[1:]):
        if abs(v1 / v0 - 1) > VARIACAO_DIARIA_MAX:
            raise ErroDados(f"variação suspeita em {d1:%d/%m/%Y}: {v0} -> {v1}")
    if ultima_anterior and datas[-1] < ultima_anterior:
        raise ErroDados(f"série termina em {datas[-1]:%d/%m/%Y}, antes da versão "
                        f"publicada ({ultima_anterior:%d/%m/%Y})")


# ---------------------------------------------------------------- Inflação

def sgs(codigo: int, inicio: date) -> dict[str, float]:
    url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
           f"?formato=json&dataInicial={inicio:%d/%m/%Y}")
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


# ---------------------------------------------------------------- Arquivo

def ler_anterior() -> dict | None:
    if not SAIDA.exists():
        return None
    txt = SAIDA.read_text(encoding="utf-8").strip()
    try:
        return json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
    except ValueError:
        print("Aviso: ibov_recente.js atual não pôde ser lido; será substituído.")
        return None


def montar_js(dados: dict) -> str:
    """Um registro por linha, para os diffs do Git mostrarem só os dias novos."""
    def lista(itens):
        return "[\n" + ",\n".join("  " + json.dumps(x, ensure_ascii=False) for x in itens) + "\n]"
    return (PREFIXO_JS + "{\n"
            f'"gerado": {json.dumps(dados["gerado"])},\n'
            f'"fonte": {json.dumps(dados["fonte"], ensure_ascii=False)},\n'
            f'"d": {lista(dados["d"])},\n'
            f'"infl": {lista(dados["infl"])}\n'
            "};\n")


def gravar_atomico(texto: str) -> None:
    tmp = SAIDA.with_suffix(".js.tmp")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, SAIDA)


# ---------------------------------------------------------------- Main

def main() -> int:
    hoje = datetime.now(FUSO_BRASILIA).date()
    anterior = ler_anterior()
    ultima_anterior = None
    if anterior and anterior.get("d"):
        ultima_anterior = datetime.strptime(anterior["d"][-1][0], "%d/%m/%Y").date()

    try:
        serie, fonte = ibovespa(hoje)
        validar(serie, ultima_anterior)
    except (ErroDados, RuntimeError) as e:
        print(f"ERRO: {e}. ibov_recente.js não foi alterado.")
        return 1

    try:
        infl = inflacao(hoje)
    except Exception as e:                           # noqa: BLE001
        print(f"Aviso: inflação não atualizada ({e}); mantendo a anterior.")
        infl = (anterior or {}).get("infl", [])

    d = [[p.strftime("%d/%m/%Y"), v] for p, v in serie]
    if anterior and anterior.get("d") == d and anterior.get("infl") == infl \
            and anterior.get("fonte") == fonte:
        print(f"Sem dados novos (último pregão {d[-1][0]}).")
        return 0

    gravar_atomico(montar_js({
        "gerado": datetime.now(FUSO_BRASILIA).strftime("%d/%m/%Y %H:%M"),
        "fonte": fonte, "d": d, "infl": infl,
    }))
    ipca_ate = next((m for m, ipca, _ in reversed(infl) if ipca is not None), "-")
    print(f"OK: {len(d)} pregões até {d[-1][0]} ({fonte}); IPCA até {ipca_ate} "
          f"-> {SAIDA.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
