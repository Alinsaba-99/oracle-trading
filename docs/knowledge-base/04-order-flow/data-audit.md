# 04 Order flow — Data Audit (free $0 verified 2026-08-17)

> Regola hard: $0/mo per dati. Vedi ADR-020.
> **Dominio parzialmente hard-blocked per US equities + futures L2**.

## Fonti L2 free verificate

| Fonte | Coverage | Format | API Key | Limit | Note |
|---|---|---|---|---|---|
| **Binance public WebSocket futures** | BTCUSDT/ETHUSDT/etc perp + spot | WebSocket JSON | nessuna | 5 incoming msg/s × connection, 1024 streams/connection | `wss://fstream.binance.com/public/stream` per futures, `wss://stream.binance.com:9443` per spot. **L2 depth 100ms updates** |
| **Binance Vision historical** | tick L2 + trades 2017+ | CSV gzipped | nessuna | bulk download S3 | `https://data.binance.vision/data-streams/depthsnapshots`. **Bulk free no auth** |
| **Deribit public WebSocket** | BTC/ETH perp + options | WebSocket JSON | nessuna | 20 req/s | `wss://www.deribit.com/ws/api/v2`. Full L2 + increments |
| **BitMEX public WebSocket** | XBTUSD perp + ETHUSD futures | WebSocket JSON | nessuna | 30 req/s | `wss://www.bitmex.com/realtime`. L2 depth + trades |
| **OKX public WebSocket** | crypto futures + spot | WebSocket JSON | nessuna | 20 req/s | `wss://ws.okx.com:8443/ws/v5/public`. L2 depth + trades |
| **Lake API free tier** | crypto L2 historical | Python lib | nessuna | free tier limited | `pip install lakeapi`. Crypto-Lake free subset |

## Fonti L1 free verificate (per Volume Profile approximate)

| Fonte | Coverage | Format | API Key | Note |
|---|---|---|---|---|
| **yfinance** | US equities daily, 1993+ | pandas DataFrame | nessuna | Volume per day, no intra-bar distribution |
| **yfinance intraday** | US equities 1m, last 30d | pandas DataFrame | nessuna | 1m bars allow rough intra-bar volume profile |
| **Dukascopy (legacy bulk)** | 21 forex/crypto/commodities, 2003+ | CSV cached | nessuna | Lake Oracle già popolato |
| **Binance Vision bulk** | crypto spot + perp, 1m+5m+1h+1d | CSV gzipped | nessuna | Free bulk, no auth. OHLCV + volume |

## Capabilities Oracle esistenti

- ✅ `market/ingestion/sources.py:BinanceVisionHistorical` — bulk CSV loader per Binance Vision
- ✅ `market/ingestion/sources.py:BinanceREST` — real-time REST public
- ✅ Lake Oracle 21 symbols + 169M rows cached (vedi `r5-hard-mode-search`)

## Gap dichiarati (hard-blocked per US)

### US equities L2
- **Nasdaq TotalView**: $48/mo via IBKR
- **NYSE OpenBook**: $25/mo via IBKR
- **NYSE ArcaBook**: $11/mo via IBKR
- **OPRA options L1**: $1.50/mo via IBKR (utente ha già)
- **OTC Markets L2**: $20/mo via IBKR
- **Total US L2** ≈ $75-100/mo per data feed completo

### US futures L2
- **CME Globex L2**: ~$10-30/mo (depth + trades). IBKR Paper Gateway NON include L2, solo L1.
- **CME Data Package**: ibkr.com/pricing/market-data-pricing

### Crypto L2 historical (paywalled per tick storico > 1y)
- **Tardis.dev**: $350/mo+ per derivatives historical tick L2
- **Databento**: OUT definitivo (carta italiana rifiutata)
- **Crypto-Lake free**: subset tick L2 free via `lakeapi`

## Alternativi free per US L1 + Volume Profile

- **Volume per price level** (rough Volume Profile) — usando yfinance daily + intraday 1m.
- **OBV (On Balance Volume)** — proxy of aggression, no L2 needed. Implementato in TA-Lib.
- **VWAP deviation** — proxy of fair value, no L2. Implementato.
- **Money Flow Index (MFI)** — volume-weighted RSI, no L2.

## Cap da NON usare (paywalled)

| Fonte | Perché esclusa | Alternativa free |
|---|---|---|
| Nasdaq TotalView | $48/mo IBKR | crypto L2 free + Volume Profile L1 US |
| NYSE OpenBook | $25/mo IBKR | same |
| CME Globex L2 | $10-30/mo | crypto perp L2 free |
| Tardis.dev | $350/mo | Binance Vision bulk + capture going forward |
| Databento | carta IT rifiutata | Binance Vision + lakeapi |
| dxFeed L2 | $50/mo | Binance WS |
| IQFeed L2 | $130/mo | same |
| Polygon L2 | $199/mo | same |

## Strategia Oracle per dominio 04

1. **Crypto lane**: Binance Vision L2 historical + WS real-time → footprint + delta + imbalance per BTCUSDT/ETHUSDT perp. **Free $0, illimitato**.
2. **US equities**: Volume Profile approximate con yfinance 1m intraday (last 30d). Rough ma usable per daily timeframes.
3. **US futures**: hard-blocked per L2. Lane A (SPY 1h) userà price + volume + OBV + VWAP come proxy.
4. **Trade classification Lee-Ready**: per L1 trades data, classify aggressive vs passive. AlgoStorm reference.
