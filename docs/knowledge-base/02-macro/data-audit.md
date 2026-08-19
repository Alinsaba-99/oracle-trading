# 02 Macro — Data Audit (free $0 verified 2026-08-17)

> Regola hard: $0/mo per dati. Vedi ADR-020.

## Fonti macro free verificate

| Fonte | Coverage | Format | API Key | Limit | Note |
|---|---|---|---|---|---|
| **FRED (St. Louis Fed)** | 765,000+ series US + international | JSON, XML, TXT | `FRED_API_KEY` free email | 120 req/min | Top source. CPIAUCSL, GDP, UNRATE, DGS10, T10Y2Y, FEDFUNDS, PAYEMS, VIXCLS. **USATO in Oracle per VIX** |
| **ECB SDMX 2.1 REST** | euro-area rates, M3, HICP, balance sheet | JSON SDMX | nessuna | 30 req/min | `https://data-api.ecb.europa.eu/service/`. Spot rate EUR/EURIBOR, MFI balance sheet |
| **BIS Data Portal** | international banking, FX swaps, debt securities | JSON | nessuna | 30 req/min | `https://data.bis.org`. Cross-border claims, locational banking statistics |
| **BLS (US Bureau Labor Stats)** | US employment, CPI, PPI | JSON | `BLS_API_KEY` free email | 25 req/day public, 500/day with key | Employment situation, CPI detailed, JOLTS |
| **BEA (US Bureau Econ Analysis)** | US GDP, trade balance, personal income | JSON | `BEA_API_KEY` free email | 100 req/day | GDP releases, trade balance, PCE |
| **OECD Stats** | international macro, leading indicators | JSON | nessuna | rate-limited | Composite leading indicators, business confidence |
| **IMF DataMapper** | global macro by country | JSON | nessuna | soft limit | World Economic Outlook database |
| **World Bank API** | country-level macro | JSON | nessuna | 5000 req/hour | GDP, population, trade per country |

## FRED series rilevanti per Oracle

### Equity / bond signals
- `DGS10` — 10y Treasury yield
- `DGS2` — 2y Treasury yield
- `T10Y2Y` — 10y-2y spread (yield curve)
- `FEDFUNDS` — federal funds rate
- `T5YIE` — 5y breakeven inflation
- `VIXCLS` — VIX daily close (già usato in Lane D VRP)
- `BAMLC0A4CBBB` — Baa corporate yield spread

### Macro indicators
- `CPIAUCSL` — CPI all urban consumers, seasonally adjusted
- `PCEPI` — PCE price index (Fed preferred inflation)
- `GDP` — quarterly real GDP
- `INDPRO` — industrial production (output gap)
- `UNRATE` — unemployment rate
- `PAYEMS` — nonfarm payrolls
- `JTSJOL` — job openings (JOLTS)
- `UMCSENT` — University of Michigan consumer sentiment

### Trade + currency
- `BOPGST` — trade balance
- `DTWEXBGS` — trade-weighted USD index (broad)

## Capabilities Oracle esistenti

- ✅ `analytics/macro/fred.py:FREDClient` — async client, `fetch_series("VIXCLS")`
- ✅ `_load_vix` in `lane_d_vrp_backtest.py` usa FRED con yfinance fallback

## Gap dichiarati

1. **FRED adapter non esteso a series complete** — solo VIXCLS usato. Servono 8+ series chiave. TODO BL-KB-09.
2. **ECB adapter** — non implementato. Euro-area macro mancante. TODO BL-KB-10.
3. **BIS adapter** — non implementato. International banking statistics. TODO BL-KB-11.
4. **BLS + BEA adapters** — non implementati. Employment + GDP releases. TODO BL-KB-17.
5. **Macro factor extraction (PCA)** — Ludvigson-Ng 2009 usano 132 series + PCA. Per replicare serve bulk download + scikit-learn PCA. TODO BL-KB-18.

## Capacità Oracle da NON usare

| Fonte | Perché esclusa | Alternativa free |
|---|---|---|
| Bloomberg Terminal | $24k/yr | FRED + BIS + ECB |
| Refinitiv Eikon | $1.8k/mo | FRED + OECD |
| Haver Analytics | $5k+/yr | FRED + BEA |
| Macrobond | $5k+/yr | FRED + BIS |
| IHS Markit | enterprise | OECD + IMF |
| Trading Economics API | $50/mo | FRED + World Bank |
| Investing.com economic calendar | scraper-able | BLS release calendar (free) |

## Real-time economic calendar free

- **BLS release schedule** — https://www.bls.gov/schedule/2026/ (free)
- **BEA release schedule** — https://www.bea.gov/news/schedule (free)
- **FRED Economic Calendar** — https://fred.stlouisfed.org/calendar (free)
- **FOMC meeting calendar** — https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm (free)

Per event-driven trading (pre-FOMC drift, NFP straddle), basta FRED + BLS/BEA calendars, no need paywalled Bloomberg Economic Calendar.
