/* Página do Ibovespa histórico.
 *
 * Entradas (carregadas antes deste arquivo, ver index.html):
 *   window.IBOV_HISTORICO  dados_historicos.js — fechamentos e inflação embutidos
 *   window.IBOV_EVENTOS    eventos.js          — escolhas presidenciais, posses e governos
 *   window.IBOV_RECENTE    ibov_recente.js     — opcional; gerado por atualizar_ibov.py
 *   window.echarts         vendor/echarts.min.js
 */
'use strict';
(() => {
  const DIA_MS = 864e5;
  const $ = id => document.getElementById(id);

  // ------------------------------------------------------------ utilidades

  /** "dd/mm/aaaa" -> milissegundos UTC */
  const dataParaMs = s => { const [d, m, a] = s.split('/').map(Number); return Date.UTC(a, m - 1, d); };
  const doisDig = n => String(n).padStart(2, '0');
  const fmtData = ms => { const d = new Date(ms); return `${doisDig(d.getUTCDate())}/${doisDig(d.getUTCMonth() + 1)}/${d.getUTCFullYear()}`; };
  const isoData = ms => new Date(ms).toISOString().slice(0, 10);
  const DIAS_SEMANA = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'];
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const SOBRESCRITO = { '-': '⁻', 0: '⁰', 1: '¹', 2: '²', 3: '³', 4: '⁴', 5: '⁵', 6: '⁶', 7: '⁷', 8: '⁸', 9: '⁹' };
  function notacaoCientifica(v) {
    const exp = Math.floor(Math.log10(v));
    const mant = v / 10 ** exp;
    return mant.toLocaleString('pt-BR', { maximumFractionDigits: 2 }) + '×10' + [...String(exp)].map(c => SOBRESCRITO[c]).join('');
  }
  /** Pontos do índice: 2 casas acima de 100; notação científica nos valores minúsculos dos anos 60. */
  function fmtPontos(v) {
    if (v > 0 && v < 0.001) return notacaoCientifica(v);
    if (v >= 100) return v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return v.toLocaleString('pt-BR', { maximumSignificantDigits: 4 });
  }
  /** Fração -> "+12,34%", abreviando valores enormes ("+176,6 bi%"). */
  function fmtPct(x) {
    const p = x * 100, sinal = p >= 0 ? '+' : '';
    if (Math.abs(p) >= 1e6) return sinal + p.toLocaleString('pt-BR', { notation: 'compact', maximumFractionDigits: 1 }) + '%';
    if (Math.abs(p) >= 1e4) return sinal + p.toLocaleString('pt-BR', { maximumFractionDigits: 0 }) + '%';
    return sinal + p.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '%';
  }
  const classeSinal = x => (x >= 0 ? 'pos' : 'neg');
  const corToken = nome => getComputedStyle(document.documentElement).getPropertyValue(nome).trim();

  // ------------------------------------------------------------ série do Ibovespa

  const HIST = window.IBOV_HISTORICO;
  const EVENTOS = window.IBOV_EVENTOS || { escolhas: [], governos: [] };

  /** Reconstrói datas e fechamentos a partir dos deslocamentos em dias. */
  function lerHistorico() {
    const datas = [], fechamentos = [];
    let t = dataParaMs(HIST.inicio);
    HIST.dias.forEach((desloc, i) => { t += desloc * DIA_MS; datas.push(t); fechamentos.push(HIST.fechamentos[i]); });
    return { datas, fechamentos };
  }

  // Inflação: arrays de variação % mensal indexados a partir de MES_INICIAL (null = não divulgado).
  const [MES0, ANO0] = HIST.inflacao.inicio.split('/').map(Number);
  const indiceMes = (ano, mes) => (ano - ANO0) * 12 + (mes - MES0);          // mes 1..12
  const textoMes = k => { const m = MES0 - 1 + k; return `${doisDig((m % 12) + 1)}/${ANO0 + Math.floor(m / 12)}`; };

  function definirTaxa(arr, k, valor) {
    while (arr.length <= k) arr.push(null);
    if (valor != null && Number.isFinite(Number(valor))) arr[k] = Number(valor);
  }

  /**
   * Junta ibov_recente.js aos dados embutidos. Trabalha em cópias e só aplica no fim:
   * se o arquivo estiver malformado, a página segue com os dados embutidos.
   */
  function mesclarRecente(serie, inflacao) {
    const rec = window.IBOV_RECENTE;
    if (!rec) return { serie, inflacao, recente: null };
    try {
      const pontos = (rec.d || [])
        .map(([s, v]) => [dataParaMs(s), Number(v)])
        .filter(([t, v]) => Number.isFinite(t) && Number.isFinite(v) && v > 0)
        .sort((a, b) => a[0] - b[0]);

      const datas = serie.datas.slice(), fechamentos = serie.fechamentos.slice();
      if (pontos.length) {
        while (datas.length && datas[datas.length - 1] >= pontos[0][0]) { datas.pop(); fechamentos.pop(); }
        for (const [t, v] of pontos) { datas.push(t); fechamentos.push(v); }
      }
      const ipca = inflacao.ipca.slice(), igpdi = inflacao.igpdi.slice();
      for (const [mesAno, vIpca, vIgp] of rec.infl || []) {
        const [m, a] = mesAno.split('/').map(Number);
        const k = indiceMes(a, m);
        if (k < 0 || !Number.isFinite(k)) continue;
        definirTaxa(ipca, k, vIpca);
        definirTaxa(igpdi, k, vIgp);
      }
      return { serie: { datas, fechamentos }, inflacao: { ipca, igpdi }, recente: pontos.length ? rec : null };
    } catch (e) {
      console.error('ibov_recente.js inválido; usando só os dados embutidos.', e);
      return { serie, inflacao, recente: null };
    }
  }

  const mescla = mesclarRecente(lerHistorico(),
    { ipca: HIST.inflacao.ipcaEncadeado.slice(), igpdi: HIST.inflacao.igpdi.slice() });
  const DATAS = mescla.serie.datas;
  const NOMINAL = mescla.serie.fechamentos;
  const N = DATAS.length;
  const RECENTE = mescla.recente;

  /** Primeiro pregão com data > t */
  function indiceDepois(t) {
    let lo = 0, hi = N;
    while (lo < hi) { const m = (lo + hi) >> 1; if (DATAS[m] <= t) lo = m + 1; else hi = m; }
    return lo;
  }
  const indiceAteInclusive = t => indiceDepois(t) - 1;
  const indiceAntes = t => indiceDepois(t - 1) - 1;                          // último pregão com data < t

  // ------------------------------------------------------------ índice de preços

  /**
   * Nível de preços no início de cada mês (nivel[k] = acumulado até o fim do mês k-1).
   * Meses sem taxa no meio da série contam como 0% (avisado no console);
   * depois do último mês divulgado, o nível fica constante.
   */
  function montarIndicePrecos(taxas, nome) {
    let ultimo = taxas.length - 1;
    while (ultimo >= 0 && taxas[ultimo] == null) ultimo--;
    const nivel = [1];
    for (let k = 0; k <= ultimo; k++) {
      if (taxas[k] == null) console.warn(`${nome}: sem taxa em ${textoMes(k)}; usando 0%.`);
      nivel.push(nivel[k] * (1 + (taxas[k] ?? 0) / 100));
    }
    return { taxas, nivel, ultimo };
  }
  /** Nível de preços num dia, com a inflação do mês distribuída geometricamente pelos dias. */
  function precoNoDia(ind, t) {
    const d = new Date(t), ano = d.getUTCFullYear(), mes = d.getUTCMonth() + 1;
    const k = indiceMes(ano, mes);
    if (k < 0) return ind.nivel[0];
    if (k > ind.ultimo) return ind.nivel[ind.ultimo + 1];
    const diasNoMes = new Date(Date.UTC(ano, mes, 0)).getUTCDate();
    const fracao = (d.getUTCDate() - 1) / diasNoMes;
    return ind.nivel[k] * (1 + ind.taxas[k] / 100) ** fracao;
  }
  const INDICES = {
    ipca: montarIndicePrecos(mescla.inflacao.ipca, 'IPCA'),
    igpdi: montarIndicePrecos(mescla.inflacao.igpdi, 'IGP-DI'),
  };
  const PRECO_POR_PREGAO = {
    ipca: DATAS.map(t => precoNoDia(INDICES.ipca, t)),
    igpdi: DATAS.map(t => precoNoDia(INDICES.igpdi, t)),
  };

  // ------------------------------------------------------------ estado

  const estado = {
    modo: 'ipca',            // 'nom' | 'ipca' | 'igpdi'
    escala: 'value',         // 'value' (linear) | 'log'
    mostrarEventos: true,
    ancora: N - 1,           // pregão cujo poder de compra é a referência do modo real
    faixa: [0, N - 1],       // pregões visíveis no gráfico (índices)
  };
  let exibida = NOMINAL.slice();   // série mostrada (nominal ou real)
  let picos = [];                  // máximo acumulado de `exibida` até cada pregão

  function recalcularSerie() {
    if (estado.modo === 'nom') {
      exibida = NOMINAL.slice();
    } else {
      const precos = PRECO_POR_PREGAO[estado.modo];
      const ref = precos[estado.ancora];
      exibida = NOMINAL.map((v, i) => v * ref / precos[i]);
    }
    picos = new Array(N);
    let max = -Infinity;
    for (let i = 0; i < N; i++) { if (exibida[i] > max) max = exibida[i]; picos[i] = max; }
  }

  // ------------------------------------------------------------ eventos políticos

  const governos = EVENTOS.governos.map(g => ({ nome: g.nome, desde: dataParaMs(g.desde) }))
    .sort((a, b) => a.desde - b.desde);
  const escolhas = EVENTOS.escolhas.map(e => ({
    ...e,
    t: dataParaMs(e.data),
    tPosse: e.posse ? dataParaMs(e.posse) : null,
    ano: e.data.slice(-4),
    nomePrincipal: e.nome.split(' → ')[0],
  })).sort((a, b) => a.t - b.t);

  /** Variações em torno do evento, na série exibida. null = ainda sem pregões. */
  function reacao(ev) {
    const base = indiceAntes(ev.t), apos = indiceDepois(ev.t);
    const ok = j => base >= 0 && j < N;
    return {
      base,
      noDia: base < apos - 1,                                   // houve pregão no próprio dia
      dia: ok(apos) ? exibida[apos] / exibida[base] - 1 : null,
      semana: ok(apos + 4) ? exibida[apos + 4] / exibida[base] - 1 : null,
    };
  }

  function renderTabelaEventos() {
    const linhas = escolhas.map(ev => ({ ev, r: reacao(ev) }));
    const maxAbs = Math.max(1e-9, ...linhas.map(({ r }) => Math.abs(r.dia ?? 0)));
    $('eventos').innerHTML = linhas.map(({ ev, r }, k) => {
      const ast = r.noDia ? '*' : '';
      let detalhe = '';
      if (ev.tipo === 'indireta') detalhe = ` <span class="det">indireta${ast}</span>`;
      if (ev.tipo === 'vice') detalhe = ` <span class="det">posse do vice${ast}${ev.obs ? ' · ' + esc(ev.obs) : ''}</span>`;
      const ano = ev.tipo === 'vice' ? esc(ev.data) : esc(ev.ano);
      const marca = ev.tipo === 'vice' ? '<span class="vice">▸</span> ' : '';
      const vespera = r.base >= 0 ? `${fmtPontos(exibida[r.base])} <span class="mut">${fmtData(DATAS[r.base]).slice(0, 5)}</span>` : '—';
      const celDia = r.dia == null ? '<td class="mut">aguardando</td>'
        : `<td class="${classeSinal(r.dia)}">${fmtPct(r.dia)}<span class="barra" style="width:${Math.round(Math.abs(r.dia) / maxAbs * 60)}px"></span></td>`;
      const celSemana = r.semana != null ? `<td class="${classeSinal(r.semana)}">${fmtPct(r.semana)}</td>`
        : `<td class="mut">${r.dia == null ? 'aguardando' : 'em andamento'}</td>`;
      return `<tr tabindex="0" data-k="${k}"><td>${ano}</td><td>${marca}${esc(ev.nome)}${detalhe}</td><td>${vespera}</td>${celDia}${celSemana}</tr>`;
    }).join('');
  }

  // ------------------------------------------------------------ tooltip (crosshair)

  function htmlTooltip(valorEixoX) {
    const i = Math.min(N - 1, Math.max(0, indiceAteInclusive(valorEixoX)));
    const t = DATAS[i], ini = estado.faixa[0];
    const up = corToken('--up'), down = corToken('--down');
    const pct = x => `<span style="color:${x >= 0 ? up : down}">${fmtPct(x)}</span>`;
    const linha = (k, v) => `<tr><td>${k}</td><td>${v}</td></tr>`;

    let h = `<div style="margin-bottom:4px"><b>${DIAS_SEMANA[new Date(t).getUTCDay()]} ${fmtData(t)}</b></div><table class="tip">`;
    h += linha(estado.modo === 'nom' ? 'Fechamento' : 'Fechamento real', `<b>${fmtPontos(exibida[i])}</b>`);
    if (estado.modo !== 'nom') h += linha('Nominal', fmtPontos(NOMINAL[i]));
    if (i > 0) h += linha('No dia', pct(exibida[i] / exibida[i - 1] - 1));
    if (i > ini) h += linha('Desde ' + fmtData(DATAS[ini]), pct(exibida[i] / exibida[ini] - 1));
    const queda = exibida[i] / picos[i] - 1;
    h += linha('Do topo anterior', queda < -5e-5 ? pct(queda) : `<span style="color:${up}">no topo</span>`);

    const gov = governos.filter(g => g.desde <= t).pop();
    if (gov) h += linha('Governo', `${esc(gov.nome)} (desde ${fmtData(gov.desde)})`);
    const eleito = escolhas.find(e => e.tPosse && e.t <= t && t < e.tPosse);
    if (eleito) h += linha('Eleito', `${esc(eleito.nomePrincipal)} (posse ${fmtData(eleito.tPosse)})`);
    return h + '</table>';
  }

  // ------------------------------------------------------------ gráfico

  const grafico = echarts.init($('grafico'), null, { renderer: 'canvas' });
  const pontosGrafico = () => DATAS.map((t, i) => [t, exibida[i]]);

  function linhasEventos() {
    const elec = corToken('--elec'), mut = corToken('--muted');
    return escolhas.map(ev => ({
      name: ev.tipo === 'vice' ? ev.nomePrincipal : ev.ano,
      xAxis: ev.t,
      lineStyle: ev.tipo === 'vice' ? { type: [2, 4], color: mut }
        : ev.tipo === 'indireta' ? { type: 'dotted', color: elec, opacity: 0.7 } : { color: elec },
      label: { color: ev.tipo === 'vice' ? mut : elec },
    }));
  }

  function opcoesGrafico() {
    const fg = corToken('--fg'), mut = corToken('--muted'), linha = corToken('--line'),
      acc = corToken('--accent'), painel = corToken('--panel'), suave = corToken('--accent-soft');
    const fonteMono = corToken('--mono');
    return {
      animation: false,
      grid: { left: 12, right: 12, top: 18, bottom: 74 },
      tooltip: {
        trigger: 'axis', confine: true, transitionDuration: 0,
        backgroundColor: painel, borderColor: linha, padding: [8, 10],
        textStyle: { color: fg, fontFamily: fonteMono, fontSize: 12 },
        // snap:false -> a leitura segue a data sob o cursor (estável com décadas na tela)
        axisPointer: {
          type: 'cross', snap: false, animation: false,
          lineStyle: { color: mut, type: 'dashed', width: 1 },
          crossStyle: { color: mut, type: 'dashed', width: 1 },
          label: { backgroundColor: mut, color: painel, fontFamily: fonteMono, fontSize: 11 },
        },
        formatter: ps => htmlTooltip(ps[0].axisValue),
      },
      xAxis: {
        type: 'time', splitLine: { show: false },
        axisLine: { lineStyle: { color: linha } }, axisLabel: { color: mut },
        axisPointer: { label: { formatter: p => fmtData(p.value) } },
      },
      yAxis: {
        type: estado.escala, scale: true,
        // No modo log o ECharts arredonda o eixo para potências de 10 e achata a linha; usa a faixa real dos dados.
        ...(estado.escala === 'log' ? { min: v => v.min * 0.97, max: v => v.max * 1.03 } : {}),
        axisLabel: { show: false }, axisPointer: { label: { show: false } },
        splitLine: { lineStyle: { color: linha } },
      },
      dataZoom: [
        { type: 'inside', throttle: 30 },
        {
          type: 'slider', height: 28, bottom: 18, borderColor: linha, textStyle: { color: mut },
          fillerColor: suave, handleStyle: { color: acc },
          dataBackground: { lineStyle: { color: mut }, areaStyle: { color: linha } },
          labelFormatter: v => fmtData(v),
        },
      ],
      series: [{
        type: 'line', data: pontosGrafico(), showSymbol: false, sampling: 'lttb',
        lineStyle: { width: 1.4, color: acc },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: suave }, { offset: 1, color: 'rgba(0,0,0,0)' }] } },
        markLine: estado.mostrarEventos ? {
          symbol: 'none', silent: true,
          lineStyle: { type: 'dashed', width: 1 },
          label: { formatter: p => p.name, fontSize: 10, position: 'insideEndTop' },
          data: linhasEventos(),
        } : { data: [] },
      }],
    };
  }

  /** Lê do gráfico o intervalo visível (uma vez por evento de zoom, não a cada movimento do mouse). */
  function lerFaixaDoGrafico() {
    const z = grafico.getOption().dataZoom[0];
    const a = z.startValue ?? DATAS[0], b = z.endValue ?? DATAS[N - 1];
    estado.faixa = [Math.max(0, indiceDepois(a - 1)), Math.min(N - 1, indiceAteInclusive(b))];
  }

  let zoomProgramatico = false;    // zoom vindo de botão/tabela/redesenho, não do usuário
  function aplicarZoom(inicio, fim) {
    zoomProgramatico = true;                                  // o evento 'datazoom' é síncrono
    grafico.dispatchAction({ type: 'dataZoom', startValue: inicio, endValue: fim });
    zoomProgramatico = false;
  }

  /** Redesenha tudo (troca de escala, tema ou eventos), preservando o zoom atual. */
  function redesenhar() {
    const [i, j] = estado.faixa;
    grafico.setOption(opcoesGrafico(), true);
    aplicarZoom(DATAS[i], DATAS[j]);
  }

  // ------------------------------------------------------------ estatísticas do período

  /** Reduz a fonte de quem não cabe na largura, num passo só (sem loop de layout). */
  function ajustarTextosStats() {
    for (const el of document.querySelectorAll('#stats .v, #stats .s')) {
      el.style.fontSize = '';
      if (el.scrollWidth <= el.clientWidth + 0.5) continue;
      const atual = parseFloat(getComputedStyle(el).fontSize);
      el.style.fontSize = Math.max(8, Math.floor(atual * el.clientWidth / el.scrollWidth * 20) / 20 - 0.1) + 'px';
    }
  }

  function renderStats() {
    const [i, j] = estado.faixa;
    if (j <= i) return;
    const Y = exibida;
    let iMax = i, iMin = i, pico = Y[i], iPico = i, quedaMax = 0, qIni = i, qFim = i;
    let melhor = 0, iMelhor = i, pior = 0, iPior = i;
    for (let k = i; k <= j; k++) {
      if (Y[k] > Y[iMax]) iMax = k;
      if (Y[k] < Y[iMin]) iMin = k;
      if (Y[k] > pico) { pico = Y[k]; iPico = k; }
      const queda = Y[k] / pico - 1;
      if (queda < quedaMax) { quedaMax = queda; qIni = iPico; qFim = k; }
      if (k > i) {
        const v = Y[k] / Y[k - 1] - 1;
        if (v > melhor) { melhor = v; iMelhor = k; }
        if (v < pior) { pior = v; iPior = k; }
      }
    }
    const total = Y[j] / Y[i] - 1;
    const anos = (DATAS[j] - DATAS[i]) / (365.25 * DIA_MS);
    const aoAno = anos > 0.5 ? (Y[j] / Y[i]) ** (1 / anos) - 1 : null;
    const real = estado.modo !== 'nom';
    const quadro = (k, v, s, c = '') => `<div class="stat"><span class="k">${k}</span><span class="v ${c}">${v}</span><span class="s">${s}</span></div>`;
    $('stats').innerHTML =
      quadro('Período', `${(j - i + 1).toLocaleString('pt-BR')} pregões`, `${fmtData(DATAS[i])} → ${fmtData(DATAS[j])}`) +
      quadro(real ? 'Variação real' : 'Variação', fmtPct(total), `${fmtPontos(Y[i])} → ${fmtPontos(Y[j])}`, classeSinal(total)) +
      quadro('Ao ano', aoAno == null ? '—' : fmtPct(aoAno), real ? 'média composta acima da inflação' : 'média composta nominal', aoAno == null ? '' : classeSinal(aoAno)) +
      quadro('Máxima', fmtPontos(Y[iMax]), fmtData(DATAS[iMax])) +
      quadro('Mínima', fmtPontos(Y[iMin]), fmtData(DATAS[iMin])) +
      quadro('Maior queda do topo', fmtPct(quedaMax), `${fmtData(DATAS[qIni])} → ${fmtData(DATAS[qFim])}`, 'neg') +
      quadro('Melhor dia', fmtPct(melhor), fmtData(DATAS[iMelhor]), 'pos') +
      quadro('Pior dia', fmtPct(pior), fmtData(DATAS[iPior]), 'neg');
    ajustarTextosStats();
    $('dataDe').value = isoData(DATAS[i]);
    $('dataAte').value = isoData(DATAS[j]);
  }

  function renderNotaModo() {
    const nota = $('notaModo');
    if (estado.modo === 'nom') { nota.hidden = true; return; }
    const ind = INDICES[estado.modo];
    const nome = estado.modo === 'ipca' ? 'IPCA (IGP-DI antes de 1980)' : 'IGP-DI';
    nota.hidden = false;
    nota.textContent = `Valores em pontos de ${fmtData(DATAS[estado.ancora])} (fim do período visível), corrigidos pelo ${nome}. ` +
      `${estado.modo === 'ipca' ? 'IPCA' : 'IGP-DI'} disponível até ${textoMes(ind.ultimo)}; depois disso o índice de preços fica constante.`;
  }

  /** Troca a âncora do modo real para o fim do período visível e atualiza tudo que depende da série. */
  function atualizarSerieExibida() {
    estado.ancora = estado.faixa[1];
    recalcularSerie();
    grafico.setOption({ series: [{ data: pontosGrafico() }] });
    renderTabelaEventos();
    renderStats();
    renderNotaModo();
  }

  // ------------------------------------------------------------ controles

  function pressionar(grupo, botao) {
    for (const b of grupo.querySelectorAll('button')) b.setAttribute('aria-pressed', b === botao ? 'true' : 'false');
  }

  let quadroAgendado = false, timerAncora = null;
  grafico.on('datazoom', () => {
    if (!zoomProgramatico) pressionar($('periodos'), null);   // zoom manual: nenhum botão de período vale mais
    if (quadroAgendado) return;
    quadroAgendado = true;
    requestAnimationFrame(() => {                              // no máximo uma atualização por quadro
      quadroAgendado = false;
      lerFaixaDoGrafico();
      renderStats();
      if (estado.modo !== 'nom') {
        clearTimeout(timerAncora);
        timerAncora = setTimeout(() => { if (estado.faixa[1] !== estado.ancora) atualizarSerieExibida(); }, 180);
      }
    });
  });

  $('periodos').addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    pressionar($('periodos'), b);
    const fim = DATAS[N - 1];
    let inicio = DATAS[0];
    if (b.dataset.desde) inicio = Date.parse(b.dataset.desde);
    else if (+b.dataset.anos > 0) { const d = new Date(fim); d.setUTCFullYear(d.getUTCFullYear() - +b.dataset.anos); inicio = d.getTime(); }
    aplicarZoom(inicio, fim);
  });

  $('escala').addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    pressionar($('escala'), b);
    estado.escala = b.dataset.escala;
    redesenhar();
  });

  $('correcao').addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    pressionar($('correcao'), b);
    estado.modo = b.dataset.modo;
    atualizarSerieExibida();
  });

  $('mostrarEventos').addEventListener('change', e => { estado.mostrarEventos = e.target.checked; redesenhar(); });

  for (const id of ['dataDe', 'dataAte']) {
    $(id).addEventListener('change', () => {
      const a = Date.parse($('dataDe').value), b = Date.parse($('dataAte').value);
      if (Number.isFinite(a) && Number.isFinite(b) && a < b) { pressionar($('periodos'), null); aplicarZoom(a, b); }
    });
  }

  function focarEvento(tr) {
    const ev = escolhas[+tr.dataset.k];
    pressionar($('periodos'), null);
    aplicarZoom(ev.t - 45 * DIA_MS, Math.min(DATAS[N - 1], ev.t + 45 * DIA_MS));
    const reduzir = matchMedia('(prefers-reduced-motion: reduce)').matches;
    $('grafico').scrollIntoView({ behavior: reduzir ? 'auto' : 'smooth', block: 'center' });
  }
  $('eventos').addEventListener('click', e => { const tr = e.target.closest('tr'); if (tr) focarEvento(tr); });
  $('eventos').addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.matches('tr')) focarEvento(e.target); });

  addEventListener('resize', () => { grafico.resize(); ajustarTextosStats(); });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', redesenhar);
  new MutationObserver(redesenhar).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  // ------------------------------------------------------------ início

  const anoInicial = new Date(DATAS[0]).getUTCFullYear(), anoFinal = new Date(DATAS[N - 1]).getUTCFullYear();
  $('anos').textContent = `${anoInicial}–${anoFinal}`;
  document.title = `Ibovespa ${anoInicial}–${anoFinal}`;

  const varUltimo = NOMINAL[N - 1] / NOMINAL[N - 2] - 1;
  $('ultimo').innerHTML = `Último fechamento ${fmtData(DATAS[N - 1])}: <b>${fmtPontos(NOMINAL[N - 1])}</b> ` +
    `<span class="${classeSinal(varUltimo)}">${fmtPct(varUltimo)}</span>`;
  if (RECENTE) $('infoRecente').textContent = `Dados recentes de ibov_recente.js (${RECENTE.fonte || 'B3'}, gerado em ${RECENTE.gerado || '?'}). `;

  recalcularSerie();
  grafico.setOption(opcoesGrafico(), true);
  renderTabelaEventos();
  renderStats();
  renderNotaModo();
  if (document.fonts) document.fonts.ready.then(ajustarTextosStats);

  // Exposto só para depuração no console do navegador.
  window.IBOV_DEBUG = { estado, DATAS, NOMINAL, exibida: () => exibida, grafico };
})();
