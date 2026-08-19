# Dominio 02 — Macro Analysis

> Knowledge base Oracle — studio approfondito 2026-08-17 via Tavily API.
> Obiettivo: mappare letteratura macro, fonti dati free (FRED/ECB/BIS), edge plausibile, capability map.

## Sintesi esecutiva

L'analisi macro ha **edge documentato** ma distribuito su tre livelli:

1. **Taylor rule / monetary policy rule** (Taylor 1993): prescrive federal funds rate da inflation gap + output gap. Empiricamente联储 seguono rule ~50-70% del tempo. Edge = deviazione dal rule predice policy turn.
2. **Yield curve inversion** (10Y-2Y spread): predice ogni US recession dal 1970 con lead 12-18 mesi. Edge robusto ma lontano-lungo orizzonte. **Stato 2026-08-17: spread +0.46%, non inverted, no recession signal**.
3. **Macro factors predict asset returns**:
   - **Cooper-Priestley 2009**: output gap predice excess stock + bond returns (in-sample + OOS). Negative output gap → high future excess returns.
   - **Ludvigson-Ng 2009**: estimated macro factors explain 21-26% of 1-year-ahead excess bond returns. Real activity factor più importante.
   - **Lucca-Moench 2015**: SPX +33bps in 24h prima di FOMC announcements (1994-2011). **Edge decayed post-2015** (Hillenbrand 2021 lo conferma con dataset più lungo).
4. **Growth × Inflation 4-regime framework** (Bridgewater All Weather): ogni asset class performa meglio in un regime specifico (stocks in growth↑inflation↓, bonds in growth↓inflation↓, commodities in growth↑inflation↑, cash in growth↓inflation↑).
5. **FOMC drift + Treasury auction cycle** (Cieslak-Pospisil 2019): pattern di risk premium legati al calendario FOMC + Treasury auctions. Hillenbrand 2021 estende a 30y Treasuries (+13.8-18.6bps/day 3-day window around FOMC).

## Capacità Oracle esistente

- ✅ `analytics/macro/fred.py:FREDClient` — async FRED API client, fetch_series("VIXCLS")
- ✅ VIX loader integrato in `analytics/strategy/lane_d_vrp_backtest.py:_load_vix`
- ✅ SimFin fundamentals + yfinance prices per backtest

## Gap da colmare

1. **FRED series adapter esteso** — oltre VIXCLS, servono CPIAUCSL, GDP, UNRATE, DGS10, T10Y2Y, FEDFUNDS, PAYEMS. TODO BL-KB-09
2. **ECB SDMX RESTful API adapter** — euro-area rates, M3, inflation. Free $0. TODO BL-KB-10
3. **BIS data portal adapter** — international banking statistics, cross-border flows. Free $0. TODO BL-KB-11
4. **Output gap signal** (Cooper-Priestley 2009) — calcolare come deviazione di industrial production da trend (HP filter). Non implementato. TODO BL-KB-12
5. **Yield curve inversion signal** (10Y-2Y) — indicator regime per asset allocation. Non implementato. TODO BL-KB-13
6. **FOMC drift signal** (Lucca-Moench 2015) — long SPY 24h prima FOMC, flat altri giorni. TODO BL-KB-14
7. **Growth × Inflation regime classifier** — 4 regimes, size allocation. TODO BL-KB-15
8. **CPI surprise trading** — TIPS breakeven rate trading. TODO BL-KB-16

Vedi [literature.md](literature.md), [data-audit.md](data-audit.md), [edge.md](edge.md), [capability-map.md](capability-map.md).
