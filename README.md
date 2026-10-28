# Ibovespa histórico (1968 → hoje)

Página interativa com o fechamento diário do Ibovespa desde 02/01/1968, nominal ou corrigido pela inflação, com a reação do índice a cada escolha presidencial (diretas, indiretas e posses de vices). Funciona aberta direto do disco, sem servidor e sem internet, e também publicada no GitHub Pages, atualizada todo dia útil por um GitHub Actions.

## Como usar a página

Abra o `index.html` no navegador (dois cliques) ou acesse o endereço do GitHub Pages.

| Controle | O que faz |
|---|---|
| **1A · 5A · 10A · Pós-Real · Tudo** | Período mostrado. Zoom manual (roda do mouse, arrastar no gráfico ou na barra de baixo) desmarca os botões. |
| **Log · Linear** | Escala do eixo vertical. Log é melhor para comparar variações percentuais ao longo de décadas. |
| **Nominal · Real · IPCA · Real · IGP-DI** | Correção pela inflação. No modo real, os valores ficam em pontos da **última data visível** (se o zoom mostra 1985–1995, tudo aparece em pontos do fim desse intervalo). "Real · IPCA" usa IGP-DI antes de 1980, quando o IPCA ainda não existia. |
| **Eleições** | Liga e desliga as linhas verticais: escolhas diretas (tracejado laranja), indiretas (pontilhado) e posses de vices (cinza com o nome). |
| **Datas** | Escolhe o intervalo exato. |

- **Crosshair:** ao passar o mouse aparecem data, fechamento (e o nominal, no modo real), variação no dia, variação desde o início do período visível, distância até o topo anterior, quem governava e, entre a eleição e a posse, quem foi eleito.
- **Quadros abaixo do gráfico:** estatísticas do período visível (variação, média ao ano, máxima, mínima, maior queda a partir de um topo, melhor e pior dia).
- **Tabela de escolhas presidenciais:** variação do índice no primeiro pregão e no 5º pregão após cada votação ou posse, contra o último fechamento antes dela. Clique numa linha para ver os 45 dias antes e depois no gráfico. "aguardando" = ainda não houve pregão depois do evento.

O padrão ao abrir é escala **Linear** e correção **Real · IPCA**.

## Arquivos

| Arquivo | Conteúdo | Quem altera |
|---|---|---|
| `index.html` | Estrutura e estilo da página | você, raramente |
| `app.js` | Toda a lógica da página (comentada) | você, raramente |
| `dados_historicos.js` | Fechamentos consolidados desde 02/01/1968 (até a data do campo `completoAte`) e inflação mensal | o script, automaticamente na virada de ano |
| `eventos.js` | Escolhas presidenciais, posses de vices e governos | você, à mão, quando houver eleição |
| `ibov_recente.js` | Fechamentos depois de `completoAte` e inflação dos últimos 3 anos | o script, automaticamente |
| `atualizar_ibov.py` | Baixa os dados, grava `ibov_recente.js` e faz a virada de ano em `dados_historicos.js` | — |
| `requirements.txt` | Dependências do script | Dependabot |
| `vendor/echarts.min.js` | Apache ECharts 5.4.3 (biblioteca do gráfico, licença Apache 2.0) | — |
| `.github/workflows/atualizar.yml` | Execução diária no GitHub Actions | — |
| `.github/dependabot.yml` | Propostas mensais de atualização de actions e dependências | — |

A página carrega `ibov_recente.js` se ele existir. Os dados dele substituem os embutidos a partir da primeira data que ele traz. Se o arquivo faltar ou estiver malformado, a página usa só os dados embutidos e registra o erro no console do navegador (F12).

## Atualizar os dados

### No seu computador

```powershell
py -m pip install -r requirements.txt
py atualizar_ibov.py
```

Saídas possíveis:

- `OK: histórico até 26/10/2026; recente com 2 pregões até 28/10/2026 (B3); IPCA até 09/2026.`: arquivos atualizados.
- `Virada de ano: ...`: o script moveu dados para o histórico (ver "Virada de ano").
- `Sem dados novos (último pregão ...)`: nada mudou desde a última execução; nenhum arquivo é tocado.
- `ERRO: ... Nenhum arquivo foi alterado.` (código de saída 1): os dados baixados não passaram na validação (datas repetidas ou fora de ordem, valor ≤ 0, variação diária acima de 25%, salto entre o histórico e os dados novos, ou série terminando antes da versão já publicada). Os arquivos anteriores continuam valendo.

Para ver o que o script faria sem gravar nada, use `py atualizar_ibov.py --simular`.

O script tenta a B3 primeiro. Se a B3 falhar num ano, só aquele ano vem do Yahoo Finance; o `yfinance` é instalado na hora, na versão fixada no script, só se for preciso. A fonte usada aparece na saída e no rodapé da página.

### Automático no GitHub

O workflow `.github/workflows/atualizar.yml` roda de segunda a sexta às 19:30 de Brasília (depois do fechamento) e faz commit de `ibov_recente.js` e `dados_historicos.js` apenas quando os dados mudam. Commits que alteram o histórico levam "(histórico consolidado)" na mensagem.

1. Crie o repositório com todos os arquivos desta pasta (inclusive `.github/`).
2. Em **Settings → Actions → General → Workflow permissions**, deixe **Read and write permissions** (o workflow precisa fazer commit).
3. Na aba **Actions**, abra "Atualizar Ibovespa" e clique em **Run workflow** para testar. No log, o passo `python atualizar_ibov.py` mostra a fonte usada.
4. Opcional: em **Settings → Pages**, escolha **Deploy from a branch → main / (root)**. A página fica em `https://<usuário>.github.io/<repositório>/`.

Observações:

- **Commits do robô:** o robô faz commits; dê `git pull` antes de editar algo localmente.
- **Falhas:** se a validação falhar, o job fica vermelho e o GitHub envia e-mail. Os dados publicados não mudam.
- **Agendamento parado:** o GitHub desativa agendamentos de repositórios públicos sem atividade por 60 dias. Como há commits quase todo dia útil, isso não deve ocorrer; se ocorrer, reative na aba Actions.
- **Execuções simultâneas:** nunca há duas execuções ao mesmo tempo (`concurrency`), e o push faz `pull --rebase` antes, então um push seu no meio da execução não derruba o job.

## Virada de ano (automática)

O script cuida disso sozinho; não há nada para editar.

- `dados_historicos.js` tem o campo `completoAte`, a data até onde os fechamentos estão consolidados.
- `ibov_recente.js` traz só os pregões **depois** dessa data. Por isso a página nunca tem buraco entre os dois arquivos.
- A cada execução, o script baixa da B3 os anos a partir do dia seguinte a `completoAte`. No ano corrente isso é só o próprio ano. Em janeiro, entra também o ano que terminou.
- **Virada de ano:** na primeira execução de um ano novo, os pregões do ano encerrado saem do `ibov_recente.js` e entram no `dados_historicos.js`, e `completoAte` passa a ser 31/12. Por segurança, o ano só é consolidado se o último pregão dele for de 20/12 em diante; caso contrário, a consolidação fica para a próxima execução.
- **Inflação:** um mês entra no histórico quando IPCA e IGP-DI daquele mês já foram publicados e o mês está dentro do período consolidado. O IPCA de dezembro sai por volta de 10 de janeiro, então dezembro entra alguns dias depois dos pregões. Até lá, a página usa a inflação do `ibov_recente.js`, que sempre traz os últimos 3 anos.
- **Ordem de gravação:** o histórico é gravado antes do arquivo recente. Se a execução for interrompida entre os dois, a página continua sem buraco.

Para conferir antes de acontecer, rode `py atualizar_ibov.py --simular` em janeiro: a saída mostra as linhas `Virada de ano: ...` sem gravar nada.

## Eventos políticos (`eventos.js`)

Para uma nova eleição, acrescente uma linha em `escolhas`. Ela pode ser cadastrada antes da data; a tabela mostra "aguardando" até haver pregões depois dela.

```js
{ data: "01/10/2030", nome: "Fulano", tipo: "direta", posse: "01/01/2031" },
```

Quando o eleito tomar posse, acrescente-o em `governos`:

```js
{ desde: "01/01/2031", nome: "Fulano" },
```

Tipos: `direta`, `indireta` e `vice` (vice que assumiu; use `obs` para o contexto, por exemplo "efetivado em ..."). Um nome no formato `"Titular → Vice"` indica que o vice assumiu durante aquele mandato.

## Fontes e metodologia

- **Ibovespa:** B3 (planilha IBOVDIA para 1968–1997; "Evolução Diária" de Estatísticas históricas a partir de 1998). Valores na escala atual de pontos, com as divisões do índice já aplicadas pela B3. Por isso os anos 60 aparecem com valores como 1×10⁻¹⁰. Nos primeiros anos a B3 publica poucos algarismos significativos.
- **Inflação:** IPCA (IBGE, série SGS 433, a partir de 1980) e IGP-DI (FGV, série SGS 190), mensais, via API do Banco Central.
- **Correção diária:** a inflação de cada mês é distribuída geometricamente pelos dias do mês, para não haver degraus no dia 1º. Depois do último mês divulgado, o índice de preços fica constante. O IGP-DI costuma sair alguns dias antes do IPCA, então por alguns dias do mês os dois modos reais terminam em meses diferentes; a nota acima do gráfico informa até quando cada um vai.
- **Reação a eventos:** base = último pregão antes da data. "Dia seguinte" = primeiro pregão depois da data; "Semana" = 5º pregão depois. Quando a votação ou posse caiu num dia de pregão (marcado com *), a variação inclui o pregão do próprio dia.

## Licenças

Dados da B3, do IBGE, da FGV e do Banco Central, sujeitos aos termos de cada fonte. Apache ECharts © The Apache Software Foundation, licença Apache 2.0.
