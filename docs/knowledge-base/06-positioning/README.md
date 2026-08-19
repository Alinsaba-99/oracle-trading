# Dominio 06 — Positioning / COT

> Knowledge base Oracle — studio approfondito 2026-08-17 via Tavily API.

## Sintesi esecutiva

L'analisi del posizionamento tramite **COT (Commitments of Traders)** report è **edge documentato** con dati free $0 (CFTC pubblicazione settimanale):

1. **CFTC COT report** — pubblicato ogni venerdì, dati posizione al martedì precedente. 3 categorie: commercial (hedgers), non-commercial (large speculators), nonreportable (small speculators).
2. **Smart Money Indicator (SMI)** — Bhansali 2014 + Alpha Architect. Relative sentiment = non-commercial net position vs commercial. Edge ~+4-6%/yr, robusto a multiple testing.
3. **Asness 2013** — smart money indicators (commercial positioning) predict asset returns in commodity futures.
4. **Bhansali 2014** — SMI non è trend following, è relative sentiment. Long-or-flat timing strategies.
5. **Till 2014** — managed money futures positioning comme smart/dumb money proxy in commodities.
6. **De Roon et al 2000** — hedging pressure (commercial net) forecasts commodity futures returns.
7. **Hong-Yogo 2012** — open interest contains information about commodity returns.
8. **Etula 2013** — broker-dealer risk aversion contains commodity returns info.

**Edge forte maintained**:
- Commercial (hedger) positioning extremes → reversal signal (commercial long = bottom near, commercial short = top near).
- Non-commercial (speculator) extremes → continuation signal (managed money long = trend up).
- SMI long-or-flat strategies beat trend-following (Bhansali 2014).

**Cap to build Oracle**:
1. CFTC COT adapter (`cot_reports` Python lib free, 1986+)
2. Smart Money Indicator calculator
3. Hedging pressure signal (De Roon 2000)
4. Open interest signal (Hong-Yogo 2012)
5. Lane G COT positioning strategy

**Free data sources**:
- CFTC public: https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed
- `cot_reports` Python lib (NDelventhal): https://github.com/NDelventhal/cot_reports — 1986+ legacy + disaggregated + TFF

Vedi [literature.md](literature.md), [data-audit.md](data-audit.md), [edge.md](edge.md), [capability-map.md](capability-map.md).
