# 01 Fundamental — Data Audit (free $0 verified 2026-08-17)

> Regola hard: $0/mo per dati finanziari. Vedi ADR-020.
> Esclusioni: Polygon/Tiingo/Databento/Bloomberg/Refinitiv/CSI/Norgate/ORATS/EODHD/Twelve/Tardis/Kibot/FirstRate paid/IVolatility.

## Fonti fundamentals free verificate

| Fonte | Coverage | Format | API Key | Limit | Note |
|---|---|---|---|---|---|
| **SEC EDGAR** | US-listed securities, 1993+ | 10-K/10-Q raw, XBRL structured | nessuna | 10 req/sec | Source-of-truth. Richiede XBRL parsing. Bulk download via `https://www.sec.gov/Archives/edgar/full-index/` |
| **SEC EDGAR FTS API** | full-text search 2001+ | JSON | nessuna | 10 req/sec | `https://efts.sec.gov/LATEST/search-index?q=...&dateRange=...` |
| **SimFin bulk (cached)** | 185 tickers US top, 2015-2025 | CSV (income/balance/cashflow/prices/companies) | `SIMFIN_API_KEY` (free email) | 5 req/sec | Cached in `data/simfin/`. PIT filtered by `publish_date`. **USATO in Lane B Oracle** |
| **SimFin API** | same | JSON | same | 50 req/day free tier | Bulk download preferred |
| **yfinance fundamentals** | global, 1980+ | JSON via `tk.quarterly_income_stmt` | nessuna | rate-limit ~2000/h | Inaffidabile per backtesting (date non sempre PIT), OK per screening |

## Source of truth oracle per fundamentals

- `analytics/fundamental/simfin_loader.py` — SimFinLoader con `income_statements()`, `balance_sheets()`, `cash_flows()`, `daily_prices()`, `companies()`. Cache su `data/simfin/`.
- API key `SIMFIN_API_KEY` in `.env` (free email signup 2026-08-15).

## Gap dichiarati

1. **SEC EDGAR adapter** NON implementato. SimFin bulk ha 185 tickers US top + 5y. EDGAR dà 6.000+ tickers US + 30y storia.
   - TODO BL-KB-01: implementare `analytics/fundamental/edgar_loader.py` con XBRL parser.
   - Bulk URL: `https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{q}/master.idx`
   - XBRL viewer: `https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik}&type=10-K&date={date}&action=get`
2. **International fundamentals** — SimFin US-only. Per EU/JP tickers: mancano free. Gap dichiarato in ADR-020.
3. **Earnings call transcripts** — non in scope free. Seeking Alpha paywalled, Motley Fool paywalled. Gap dichiarato.

## Capacità esistenti Oracle che usano fundamentals

- ✅ `analytics/strategy/catalog/value.py`:
  - `PiotroskiFScore` (9 criteri originali 2000)
  - `GreenblattMagicFormula` (ROC + earnings yield ranking)
  - `LakonishokValueMomentum` (B/M + past 12m return, 3-5y orizzonte)
- ✅ `analytics/strategy/lane_b_backtester.py`:
  - `CompositeLaneBScore` (40% Piotroski + 40% Greenblatt + 20% Lakonishok, threshold 0.65, return_band (-0.20, +0.50))
  - Backtest 2020-2025 Sharpe 0.93 → **prossimo gate G5 ADR-017 (DSR/PBO/CPCV)**

## Fonti da NON usare

| Fonte | Perché esclusa | Alternativa free |
|---|---|---|
| Bloomberg Terminal | $24k/yr | SEC EDGAR + SimFin |
| Refinitiv Eikon | $1.8k/mo | yfinance fundamentals + SimFin |
| S&P Capital IQ | $5k+/yr | SimFin + SEC EDGAR |
| FactSet | enterprise | SEC EDGAR + yfinance |
| Morningstar Direct | $17k+/yr | SimFin |
| Zacks Fundamentals | $300/mo | SEC EDGAR |
| Stock Analysis Premium | $50/mo | SimFin bulk + yfinance |
| Alpha Vantage fundamentals | 25 req/day free, $50/mo paid | SimFin + SEC EDGAR |
| Financial Modeling Prep | 250 req/day free | SimFin (185 tickers + 5y) + EDGAR (6.000 tickers + 30y) |

Vedi `no-paid-financial-data` memory per hard rule.
