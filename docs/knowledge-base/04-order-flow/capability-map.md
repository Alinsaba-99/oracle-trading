# 04 Order flow — Capability Map per Oracle

> Cosa costruire in Oracle (crypto-focused) + gap dichiarati US.

## ✅ Già in Oracle

| Capability | File | Note |
|---|---|---|
| BinanceVisionHistorical adapter | `market/ingestion/sources.py:BinanceVisionHistorical` | Bulk CSV L1 + volume. **NO L2 capture** |
| BinanceREST adapter | `market/ingestion/sources.py:BinanceREST` | Real-time REST public L1 + klines |
| PaperBroker | `execution/brokers/paper.py:PaperBroker` | Paper trading con bracket orders |

## 🔨 P1 — Crypto L2 lane (free $0, edge forte)

### BL-KB-28: Binance WebSocket L2 depth adapter
- **Perché**: Binance public WS offre L2 depth 100ms free. Per footprint + OFI su crypto.
- **Cosa**: `market/ingestion/binance_ws.py:BinanceWSDepth` con:
  - `subscribe_depth(symbol)` → WS stream depth updates
  - Reconstruct full order book from increments (manage local snapshot)
  - Output: tuple (bids_list, asks_list) sorted
- **Data**: `wss://fstream.binance.com/public/stream` (perp), `wss://stream.binance.com:9443` (spot). Free no auth.
- **Tempo**: ~3-5 giorni.
- **Costo**: $0.

### BL-KB-29: Binance Vision L2 historical adapter
- **Perché**: storico L2 tick per backtest. Binance Vision bulk free.
- **Cosa**: estendere `market/ingestion/sources.py:BinanceVisionHistorical` con `fetch_l2_depthsnapshots(symbol, start, end)`:
  - URL: `https://data.binance.vision/data/streams/depthsnapshots/daily/{symbol}/{date}.zip`
  - Parse CSV gzipped → OHLCV-equivalent per L2 (timestamp, bids, asks)
- **Output**: list[L2Snapshot] timestamped.
- **Tempo**: ~2-3 giorni.

### BL-KB-30: Footprint chart calculator
- **Perché**: visualizzazione bid/ask per price per candle. Delta + cumulative delta + imbalances.
- **Cosa**: `analytics/strategy/catalog/orderflow.py:FootprintChart` con:
  - Input: list[L2Snapshot] + list[Trade] in candle window
  - Output: per candle: dict { price: {bid_vol, ask_vol, delta} }
  - Lee-Ready trade classification (aggressive vs passive)
- **Tempo**: ~3-5 giorni.

### BL-KB-31: Order Flow Imbalance (OFI) signal
- **Perché**: Cont-Brown 2008 R² 30-40% su 10-min horizon. Edge forte intra-day.
- **Cosa**: `analytics/strategy/catalog/orderflow.py:OFISignal` con:
  - OFI = sum(weighted bid/ask updates)
  - Per timestamp t: OFI(t) = bid_vol_added - bid_vol_removed + ask_vol_removed - ask_vol_added
  - Threshold: high OFI → long signal; low OFI → short
- **Tempo**: ~3-5 giorni.

### BL-KB-32: Volume Profile calculator (L1 compatible)
- **Perché**: Steidlmayer CBPVA. Utilizzabile anche con L1 (rough).
- **Cosa**: `analytics/strategy/catalog/orderflow.py:VolumeProfile` con:
  - Input: list[OHLCVBar] (L1 sufficient se 1m timeframe)
  - Output: dict { price: volume } + POC + Value Area (70%)
  - Support/resistance levels = High/Low Value Area
- **Tempo**: ~2-3 giorni.

### BL-KB-33: Cumulative Delta + Absorption signal
- **Perché**: cumulative delta divergence = exhaustion signal. Absorption = reversal.
- **Cosa**: `analytics/strategy/catalog/orderflow.py:CumulativeDelta` con:
  - Per trade: delta = aggressive_buy_vol - aggressive_sell_vol
  - Cumulative session delta running total
  - Absorption: price up + delta negative OR price down + delta positive
  - Divergence: price new high + cumulative delta non new high
- **Tempo**: ~2-3 giorni.

## 🔨 P2 — Crypto Lane F orchestrator

### BL-KB-34: Lane F crypto order flow strategy
- **Perché**: nuova lane per crypto. Combina OFI + Volume Profile + Footprint.
- **Cosa**: `analytics/strategy/lane_f_orderflow.py:CryptoOrderFlowStrategy` con:
  - Signals: OFI (BL-KB-31) + Volume Profile POC (BL-KB-32) + Cumulative Delta (BL-KB-33)
  - Universe: BTCUSDT perp + ETHUSDT perp + top 10 altcoin perp
  - Timeframe: 1m + 5m (intraday)
  - Risk: 0.5% equity per trade, max 5 concurrent
- **Tempo**: ~5-7 giorni (depends on BL-KB-30..33).

### BL-KB-35: Crypto PaperBroker integration
- **Perché**: PaperBroker attuale è equity-centric. Per crypto serve:
  - Symbol normalization (BTCUSDT perp vs spot)
  - Funding rate tracking (perp)
  - 24/7 sessioni (no daily rollover)
- **Cosa**: estendere `execution/brokers/paper.py:PaperBroker` con `crypto_mode: bool = True`.
- **Tempo**: ~2-3 giorni.

## 🔨 P3 — US L1 proxy signals

### BL-KB-36: VWAP deviation signal (US equities L1)
- **Perché**: proxy di fair value quando L2 non disponibile. Mean reversion signal.
- **Cosa**: `analytics/strategy/catalog/orderflow.py:VWAPSignal` con:
  - VWAP = sum(price × volume) / sum(volume) per session
  - Deviation bands: ±1 std dev
  - Signal: long quando price < VWAP - 1σ, short quando price > VWAP + 1σ
- **Tempo**: ~1 giorno.

### BL-KB-37: OBV (On Balance Volume) trend signal
- **Perché**: proxy of aggression senza L2.
- **Cosa**: `analytics/strategy/catalog/orderflow.py:OBVSignal` con:
  - OBV += volume se close > prev_close, OBV -= volume se close < prev_close
  - Trend confirm: price up + OBV up = healthy uptrend
  - Divergence: price new high + OBV non new high = bearish
- **Tempo**: ~1 giorno.

## 🔄 P4 — Deferrire

- **Lane A SPY 1h order flow enhancement** — quando US L2 sbloccato (Paper Plus sub).
- **Footprint su CME ES/NQ** — paywalled.

## ❌ Hard-blocked (paywalled)

- **Nasdaq TotalView L2** — $48/mo IBKR
- **NYSE OpenBook L2** — $25/mo IBKR
- **CME Globex L2** — $10-30/mo
- **Tardis.dev L2 historical** — $350/mo+
- **Databento** — OUT definitivo (carta IT)
- **dxFeed L2** — $50/mo
- **IQFeed L2** — $130/mo
- **Polygon L2** — $199/mo

## Sequenza implementazione raccomandata

```
BL-KB-28 Binance WS L2 adapter      (~3-5g) ← real-time capture
BL-KB-29 Binance Vision L2 hist     (~2-3g) ← historical for backtest
BL-KB-32 Volume Profile             (~2-3g) ← simple, usable L1
BL-KB-30 Footprint chart            (~3-5g) ← L2 required
BL-KB-31 OFI signal                 (~3-5g) ← Cont-Brown 2008
BL-KB-33 Cumulative Delta           (~2-3g) ← absorption + divergence
BL-KB-34 Lane F orchestrator        (~5-7g) ← crypto strategy
BL-KB-35 Crypto PaperBroker         (~2-3g) ← 24/7 + funding
BL-KB-36 VWAP signal                (~1g)   ← L1 proxy
BL-KB-37 OBV signal                 (~1g)   ← L1 proxy
```

Totale: **~22-33 giorni** per completare crypto L2 lane + L1 proxy signals.

## Prossimo step

Dopo P1+P2:
1. Backtest Lane F su BTCUSDT perp 2020-2025 con L2 Binance Vision historical
2. Applica DSR/PBO/CPCV (dominio 03 methodology)
3. Se passa → promozione paper trading crypto live (24/7 Binance paper)
4. **Target**: Sharpe > 1.5 su crypto intraday. Edge reale free $0.
