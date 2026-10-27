"""
Atualiza ibov_recente.js, lido pela página ibovespa_offline.html (na mesma pasta).

- Ibovespa: fechamentos diários dos anos ANO_INICIAL até o atual, direto da B3
  (mesmos dados do download "Evolução Diária"). Se a B3 falhar, usa o Yahoo (^BVSP).
- Inflação: IPCA (SGS 433) e IGP-DI (SGS 190) mensais dos últimos 3 anos, do Banco Central.

Uso:  py atualizar_ibov.py
Requer: pip install requests   (e, só para o plano B, pip install yfinance)
"""
import base64, csv, io, json, sys, time
from datetime import date, datetime
from pathlib import Path

import requests

ANO_INICIAL = 2026          # a página já traz embutido tudo até 26/10/2026
SAIDA = Path(__file__).with_name("ibov_recente.js")
HDR = {"User-Agent": "Mozilla/5.0"}


def get(url, **kw):
    for t in range(4):
        try:
            r = requests.get(url, headers=HDR, timeout=60, **kw)
            if r.ok:
                return r
            print(f"  HTTP {r.status_code}, tentando de novo...")
        except requests.RequestException as e:
            print(f"  {e.__class__.__name__}, tentando de novo...")
        time.sleep(3 * (t + 1))
    raise RuntimeError(f"falhou: {url}")


# ---------- Ibovespa pela B3 ----------
def b3_ano(ano):
    """Mesmo CSV do botão 'Download' de Estatísticas históricas > Evolução diária."""
    param = base64.b64encode(json.dumps(
        {"index": "IBOV", "language": "pt-br", "year": str(ano)}).encode()).decode()
    url = ("https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/"
           f"IndexCall/GetDownloadPortfolioDay/{param}")
    txt = get(url).text.strip().strip('"')
    if not txt.startswith(("IBOV", "Dia", "﻿")):
        txt = base64.b64decode(txt).decode("latin-1")   # a B3 devolve o CSV em base64
    out = []
    for linha in txt.splitlines():
        p = linha.split(";")
        if not p or not p[0].strip().isdigit():
            continue
        dia = int(p[0])
        for mes, val in enumerate(p[1:13], 1):
            val = val.strip()
            if val:
                try:
                    d = date(ano, mes, dia)
                except ValueError:
                    continue
                out.append((d, float(val.replace(".", "").replace(",", "."))))
    if not out:
        raise RuntimeError(f"CSV da B3 de {ano} veio vazio")
    return out


def yahoo(ano_ini):
    import yfinance as yf
    df = yf.download("^BVSP", start=f"{ano_ini}-01-01", progress=False, auto_adjust=False)
    s = df["Close"].squeeze().dropna()
    return [(ts.date(), round(float(v), 2)) for ts, v in s.items()]


def ibovespa():
    hoje = date.today()
    try:
        dados = []
        for ano in range(ANO_INICIAL, hoje.year + 1):
            print(f"B3 {ano}...")
            dados += b3_ano(ano)
        return sorted(dados), "B3"
    except Exception as e:
        print(f"B3 indisponível ({e}); usando Yahoo Finance.")
        return sorted(yahoo(ANO_INICIAL)), "Yahoo Finance"


# ---------- Inflação pelo Banco Central ----------
def sgs(cod, ini):
    url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}/dados"
           f"?formato=json&dataInicial={ini:%d/%m/%Y}")
    r = get(url)
    if not r.text.lstrip().startswith("["):
        raise RuntimeError(f"SGS {cod} não devolveu JSON")
    return {d["data"][3:]: float(d["valor"]) for d in r.json()}


def inflacao():
    ini = date(date.today().year - 2, 1, 1)
    ipca, igp = sgs(433, ini), sgs(190, ini)
    meses = sorted(set(ipca) | set(igp), key=lambda m: (m[3:], m[:2]))
    return [[m, ipca.get(m), igp.get(m)] for m in meses]


def main():
    serie, fonte = ibovespa()
    try:
        infl = inflacao()
    except Exception as e:
        print(f"Inflação não atualizada ({e}).")
        infl = []
    js = {
        "gerado": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "fonte": fonte,
        "d": [[d.strftime("%d/%m/%Y"), v] for d, v in serie],
        "infl": infl,
    }
    SAIDA.write_text("window.IBOV_RECENTE=" + json.dumps(js, ensure_ascii=False) + ";\n",
                     encoding="utf-8")
    print(f"OK: {len(serie)} pregões até {serie[-1][0]:%d/%m/%Y} ({fonte}); "
          f"inflação até {infl[-1][0] if infl else '-'} -> {SAIDA.name}")


if __name__ == "__main__":
    sys.exit(main())
