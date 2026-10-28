/* Eventos políticos marcados no gráfico e na tabela. Pode editar à mão.
 *
 * escolhas: eleições (diretas) e escolhas indiretas, mais as posses de vices que assumiram.
 *   data  : dia da votação (ou do início do exercício, no caso de vice)
 *   tipo  : "direta" | "indireta" | "vice"
 *   posse : dia em que o escolhido assumiu (o tooltip mostra "eleito, a empossar" até essa data)
 *   obs   : texto curto exibido na tabela (opcional)
 * governos: quem governava a partir de cada data (usado na linha "Governo" do tooltip).
 *
 * Para uma eleição futura, basta acrescentar a linha; a tabela mostra "aguardando" até haver pregões.
 */
window.IBOV_EVENTOS = {
  escolhas: [
    { data: "25/10/1969", nome: "Médici",            tipo: "indireta", posse: "30/10/1969" },
    { data: "15/01/1974", nome: "Geisel",            tipo: "indireta", posse: "15/03/1974" },
    { data: "15/10/1978", nome: "Figueiredo",        tipo: "indireta", posse: "15/03/1979" },
    { data: "15/01/1985", nome: "Tancredo → Sarney", tipo: "indireta", posse: "15/03/1985" },
    { data: "15/03/1985", nome: "Sarney",            tipo: "vice",     obs: "assume no lugar de Tancredo · efetivado em 21/04/1985" },
    { data: "17/12/1989", nome: "Collor → Itamar",   tipo: "direta",   posse: "15/03/1990" },
    { data: "02/10/1992", nome: "Itamar",            tipo: "vice",     obs: "assume com o afastamento de Collor · efetivado em 29/12/1992" },
    { data: "03/10/1994", nome: "FHC",               tipo: "direta",   posse: "01/01/1995" },
    { data: "04/10/1998", nome: "FHC",               tipo: "direta",   posse: "01/01/1999" },
    { data: "27/10/2002", nome: "Lula",              tipo: "direta",   posse: "01/01/2003" },
    { data: "29/10/2006", nome: "Lula",              tipo: "direta",   posse: "01/01/2007" },
    { data: "31/10/2010", nome: "Dilma",             tipo: "direta",   posse: "01/01/2011" },
    { data: "26/10/2014", nome: "Dilma → Temer",     tipo: "direta",   posse: "01/01/2015" },
    { data: "12/05/2016", nome: "Temer",             tipo: "vice",     obs: "assume com o afastamento de Dilma · efetivado em 31/08/2016" },
    { data: "28/10/2018", nome: "Bolsonaro",         tipo: "direta",   posse: "01/01/2019" },
    { data: "30/10/2022", nome: "Lula",              tipo: "direta",   posse: "01/01/2023" },
    { data: "25/10/2026", nome: "Lula",              tipo: "direta",   posse: "01/01/2027" }
  ],
  governos: [
    { desde: "15/03/1967", nome: "Costa e Silva" },
    { desde: "31/08/1969", nome: "Junta Militar" },
    { desde: "30/10/1969", nome: "Médici" },
    { desde: "15/03/1974", nome: "Geisel" },
    { desde: "15/03/1979", nome: "Figueiredo" },
    { desde: "15/03/1985", nome: "Sarney" },
    { desde: "15/03/1990", nome: "Collor" },
    { desde: "02/10/1992", nome: "Itamar" },
    { desde: "01/01/1995", nome: "FHC" },
    { desde: "01/01/2003", nome: "Lula" },
    { desde: "01/01/2011", nome: "Dilma" },
    { desde: "12/05/2016", nome: "Temer" },
    { desde: "01/01/2019", nome: "Bolsonaro" },
    { desde: "01/01/2023", nome: "Lula" }
    { desde: "01/01/2027", nome: "Lula" }
  ]
};
