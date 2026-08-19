# 08 Intermarket — Data Audit (free $0 verified 2026-08-17)

> Regola hard: $0/mo per dati. Vedi ADR-020.

## Fonti cross-asset free verificate

| Fonte | Coverage | Format | API Key | Note |
|---|---|---|---|---|
| **yfinance ETF cross-asset** | 1993-2026 daily | pandas DataFrame | nessuna | SPY, AGG, IEF, TLT, DBC, UUP, GLD, USO, XME, XLB, XLV, XLP, XLF, XLE, XLI, XLY, XLK, XLU. Free |
| **yfinance commodity futures** | 2000+ daily | pandas DataFrame | nessuna | ^GSPC (S&P), ^VIX (vol), ^DJI, ^IXIC, ^RUT, ^TNX (10y), ^IRX (T-bill) |
| **yfinance forex majors** | 2003+ daily | pandas DataFrame | nessuna | EURUSD=X, USDJPY=X, GBPUSD=X, AUDUSD=X, USDCAD=X, USDCHF=X, NZDUSD=X |
| **Dukascopy lake (legacy)** | 2003+ 1m+5m+1h+1d | parquet cached | nessuna | 21 symbols cached in Oracle (vedi `r5-hard-mode-search`) |
| **FRED spreads** | 1962+ daily | JSON via FRED | `FRED_API_KEY` free | BAA_AAA, BAMLH0A0HYM2, T10YIE, DGS10, DGS2, T10Y2Y |
| **Stooq historical** | 1990+ daily | CSV | nessuna | Free fallback per yfinance rate-limit |
| **Cryptocompare** | 2010+ crypto daily | JSON | nessuna | Crypto cross-asset correlations |

## ETF cross-asset covered (yfinance free)

### Asset class ETFs
- **SPY** — S&P 500 stocks
- **QQQ** — Nasdaq 100
- **IWM** — Russell 2000 small cap
- **AGG** — US bonds aggregate
- **IEF** — 7-10y Treasury
- **TLT** — 20+ year Treasury
- **LQD** — investment grade corporate bonds
- **HYG** — high yield bonds
- **DBC** — commodities basket
- **UUP** — US Dollar Index
- **GLD** — gold
- **USO** — oil
- **XME** — metals + mining

### Sector SPDRs (Stovall rotation)
- **XLY** — Consumer Discretionary (early expansion)
- **XLK** — Technology (early expansion)
- **XLI** — Industrials (early expansion)
- **XLE** — Energy (peak)
- **XLB** — Materials (peak)
- **XLU** — Utilities (contraction defensive)
- **XLV** — Healthcare (contraction defensive)
- **XLP** — Consumer Staples (contraction defensive)
- **XLF** — Financials (recovery)
- **XLC** — Communication Services
- **XLRE** — Real Estate
- **XLB** — Materials (duplicato, OK)

### Crypto
- **BTC-USD** — Bitcoin
- **ETH-USD** — Ethereum
- **BNB-USD**, **SOL-USD**, **ADA-USD**, **XRP-USD**, **DOGE-USD**

## Capabilities Oracle esistenti

- ✅ `analytics/strategy/catalog/` ha molti signal classici (Piotroski, Greenblatt, Lakonishok)
- ✅ Lane B backtester (fundamental equity)
- ✅ Dukascopy forex lake 21 symbols cached

## Gap dichiarati

1. **Cross-asset correlation matrix** NON implementato. yfinance + ETFs free. TODO BL-KB-61.
2. **Sector rotation signal** (Stovall 4-stage) NON implementato. TODO BL-KB-62.
3. **Credit spread signal** (Baa-Aaa + HY spread) NON implementato. FRED free. TODO BL-KB-63.
4. **Flight-to-quality detector** (stock-bond correlation breakdown) NON implementato. TODO BL-KB-64.
5. **Commodity-currency pair signal** (DXY + oil/gold/copper) NON implementato. TODO BL-KB-65.
6. **Bitcoin safe haven classifier** NON implementato. yfinance free. TODO BL-KB-66.

## Cap da NON usare (paywalled)

| Fonte | Perché esclusa | Alternativa free |
|---|---|---|
| Bloomberg cross-asset | $24k/yr | yfinance + ETFs + Dukascopy |
| Refinitiv cross-asset | $1.8k/mo | yfinance + FRED |
| ICE Data Services | $5k+/yr | yfinance + Dukascopy |
| FactSet cross-asset | enterprise | yfinance + FRED |
| MSCI correlation matrices | enterprise | rolling yfinance correlation |

## Reference implementations free

- **StockCharts Murphy PerfChart**: https://chartschool.stockcharts.com/table-of-contents/market-analysis/intermarket-analysis — free live comparison S&P500 + CRB + USD + 30y Bond
- **FRED BAA_AAA**: https://fred.stlouisfed.org/series/BAA_AAA — Moody's spread
- **ETFreplay**: https://etfreplay.com — free sector rotation tool
