# Oracle Data Sources

> Aggiornato: 2026-07-19

## Fonti Attive

| Fonte | Tipo | Cosa | API Key | Limiti |
|-------|------|------|---------|--------|
| **yfinance** | OHLCV daily/intraday | Futures (ES, NQ, GC, CL...), equities, crypto, FX | ❌ | Rate limit ~2 req/s |
| **CCXT** | OHLCV orderbook | Crypto spot & futures (Binance, Bybit, OKX, Kraken...) | ❌ (public) | Rate limit per exchange |
| **OpenBB** | OHLCV + fondamentali | Equities, ETFs, futures, macro, FX | ❌ (base) | Gratuito per dati base |

## Fonti per Gap Identificati

| Gap | Fonte | Cosa | Integrazione |
|:---:|-------|------|:------------:|
| Intraday futures 1m-15m | **IBKR** (ib_insync) | Tick/1m/5m ES, NQ, GC, CL | ✅ Già in dip. |
| Intraday futures 1m-15m | **Polygon.io** | REST API stocks/options/futures | ❌ API key |
| Crypto perpetuals | **CCXT futures** | Binance/BYBIT perpetual OHLCV + funding | ✅ Già in dip. |
| Options chain | **OpenBB** | Options chain, Greeks | ✅ Installato |
| Options pricing | **Helium MCP** | Fair value, prob_ITM, Greeks free | 🆕 Da integrare |
| Macro real-time | **FRED** (OpenBB) | GDP, CPI, NFP, tassi | ✅ Installato |
| Macro central banks | **FXMacroData** | Policy rates, inflation, 18 currency | 🆕 Da integrare |
| News/Sentiment | **AlphaAI** | Relevance-scored news, free tier | 🆕 `market/sentiment.py` |

## Multi-Timeframe / Multi-Asset Coverage

| Timeframe | Futures | Crypto | Equities | FX | Macro |
|:---------:|:-------:|:------:|:--------:|:--:|:----:|
| tick | IBKR | CCXT | IBKR | IBKR | ❌ |
| 1m | IBKR | CCXT | IBKR/Polygon | IBKR | ❌ |
| 5m | IBKR | CCXT | IBKR/Polygon | IBKR | ❌ |
| 15m | yfinance | CCXT | yfinance/IBKR | yfinance | ❌ |
| 1h | yfinance | CCXT | yfinance | yfinance | ❌ |
| 4h | yfinance | CCXT | yfinance | yfinance | ❌ |
| 1d | yfinance/OpenBB | CCXT | yfinance/OpenBB | yfinance | FRED/OpenBB |
| 1wk | yfinance | ❌ | yfinance | yfinance | FRED/OpenBB |

## Script Multi-Timeframe

```bash
# Fetch multi-timeframe data per un asset
uv run --frozen python scripts/refresh_data.py --multi-timeframe ES
# Scarica: ES_1d.parquet, ES_1h.parquet, ES_15m.parquet
```

## Fonti in Valutazione

| Fonte | Cosa | Perché |
|-------|------|--------|
| FinanceDatabase | 300K+ simboli | Mappatura ticker→strumento |
| Chart Library | Pattern similarity | ML pattern recognition |
| The Stall MCP | 191 capabilities | Dati on-chain, prediction markets |

## Script di Refresh

```bash
# Aggiornare tutti i dati futures
uv run --frozen python -c "
from market.data_sources import DataFetcher
f = DataFetcher()
for sym in ['ES', 'NQ', 'GC', 'CL']:
    f.yfinance_futures(sym, period='1y')
"

# Crypto via CCXT
uv run --frozen python -c "
from market.data_sources import DataFetcher
f = DataFetcher()
f.ccxt_ohlcv('binance', 'BTC/USDT', '1h', 1000)
"
```

## Come Aggiungere una Nuova Fonte

1. Aggiungere metodo in `market/data_sources.py`
2. Aggiungere dipendenza in `pyproject.toml`
3. `uv sync --frozen`
4. Test: `pytest tests/unit/test_data_sources.py`
