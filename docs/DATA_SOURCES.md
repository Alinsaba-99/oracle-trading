# Oracle Data Sources — Coverage Matrix

> Aggiornato: 2026-07-19

## Coverage Completa

```
ASSET CLASS    Timeframes              Fonti
───────────────────────────────────────────────────────
Futures (ES)   tick  ❌                 Polygon.io (con key)
              1m-5m  🟡 Polygon.io     Polygon.io (con key)  
              15m    🟡 Polygon.io     Polygon.io (con key)
              1h     ✅ yfinance       yfinance
              1d     ✅ yfinance/OBB   yfinance, OpenBB

Crypto (BTC)   tick  🟡 CCXT           CCXT orderbook
              1m    ✅ CCXT            CCXT spot/futures
              5m    ✅ CCXT            CCXT spot/futures
              15m   ✅ CCXT            CCXT spot/futures
              1h    ✅ CCXT            CCXT spot/futures
              1d    ✅ CCXT/yfinance   CCXT, yfinance
              fund. ✅ CCXT            Perpetual funding rate

Equities(SPY)  tick  ❌                 IBKR (con TWS)
              1m    🟡 Polygon.io      Polygon.io (con key)
              1d    ✅ yfinance/OBB    yfinance, OpenBB
              fund. ✅ OpenBB           Financial statements

FX majors      1d    ✅ yfinance/OBB    yfinance, OpenBB
FX minors      1d    🟡 OpenBB         OpenBB

Macro (GDP)    qrt   ✅ FRED           Federal Reserve API
Macro (CPI)    mon   ✅ FRED           Federal Reserve API
Macro (NFP)    mon   ✅ FRED           Federal Reserve API
Macro (rates)  mon   ✅ FRED           FEDFUNDS, DGS10, DGS2

News/Sentiment N/A   ✅ AlphaAI        Relevance-scored news

Options        chain 🟡 OpenBB         OpenBB
               greeks✅ Helium MCP     Free, no signup
```

## Fonti per Gap

| Gap | Fonte | API Key | Costo | Integrazione |
|:---:|-------|:-------:|:-----:|:------------:|
| Intraday futures 1m/5m/15m | **Polygon.io** | ✅ `ORACLE_DATA_POLYGON_KEY` | Free (5 req/min) | `polygon_futures_minute()` |
| Crypto perpetuals + funding | **CCXT** | ❌ | Free | `ccxt_futures_ohlcv()` |
| Macro (GDP, CPI, NFP, rates) | **FRED** | 🟡 Demo/public | Free | `fred_series()` |
| News/sentiment scoring | **AlphaAI** | ✅ `ORACLE_DATA_ALPHAI_KEY` | Free (20 req/min) | `SentimentFetcher.alphai_news()` |
| Options Greeks (free) | **Helium MCP** | ❌ | Free (50 queries) | Da integrare |
| Real-time tick futures | **IBKR** (ib_insync) | TWS/Gateway | Già in dip. | Da attivare |

## Quick Reference

```bash
# Macro data (no key needed)
uv run --frozen python -c "from market.data_sources import DataFetcher; f=DataFetcher(); f.fred_series('GDP')"

# Crypto perpetual futures (no key)
uv run --frozen python -c "from market.data_sources import DataFetcher; f=DataFetcher(); f.ccxt_futures_ohlcv('binance','BTC/USDT:USDT','1h')"

# Intraday futures (Polygon key needed)
uv run --frozen python -c "from market.data_sources import DataFetcher; f=DataFetcher(); f.polygon_futures_minute('ES','2026-07-01','2026-07-19')"

# Multi-timeframe refresh
uv run --frozen python scripts/refresh_data.py --multi-timeframe ES
```

## Setup Chiavi API

```bash
# Polygon.io (free tier: 5 API calls/min)
export ORACLE_DATA_POLYGON_KEY="your_key_here"

# AlphaAI (free tier: 20 req/min, 100/day)
export ORACLE_DATA_ALPHAI_KEY="your_key_here"

# FRED (free, no key needed for basic CSV access)
# Optional: get key at https://fred.stlouisfed.org/docs/api/api_key.html
export ORACLE_DATA_FRED_KEY="your_key_here"
```
