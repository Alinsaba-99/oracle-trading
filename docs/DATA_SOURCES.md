# Oracle Data Sources

> Aggiornato: 2026-07-19

## Fonti Attive

| Fonte | Tipo | Cosa | API Key | Limiti |
|-------|------|------|---------|--------|
| **yfinance** | OHLCV daily/intraday | Futures (ES, NQ, GC, CL...), equities, crypto, FX | ❌ | Rate limit ~2 req/s |
| **CCXT** | OHLCV orderbook | Crypto spot & futures (Binance, Bybit, OKX, Kraken...) | ❌ (public) | Rate limit per exchange |
| **OpenBB** | OHLCV + fondamentali | Equities, ETFs, futures, macro, FX | ❌ (base) | Gratuito per dati base |

## Fonti in Valutazione

| Fonte | Cosa | Perché |
|-------|------|--------|
| FinanceDatabase | 300K+ simboli | Mappatura ticker→strumento |
| FXMacroData | Banche centrali, tassi | Analisi macro FX |
| Helium MCP | Opzioni pricing, Greeks | Strategie options |
| Chart Library | Pattern similarity | ML pattern recognition |

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
