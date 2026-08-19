# 04 Order flow — Edge Plausibility

> Valutazione critica. Edge è forte ma dati L2 sono hard-blocked per US equities + futures.

## Edge summary

| Signal | Source | Edge | Free $0 | Note |
|---|---|---|---|---|
| Auction Market Theory (POC + Value Area) | Steidlmayer + Dalton | robust | ✅ (Volume Profile approximate via L1) | Reliable per daily timeframes |
| Footprint + delta | AlgoStorm ref | R² 30-40% short-term | ✅ solo crypto | Strong per crypto futures |
| Order Flow Imbalance (OFI) | Cont-Brown 2008 | R² 30-40% 10-min horizon | ✅ solo crypto | Edge decays 30-60 min |
| Stacked imbalances | practitioners | directional | ✅ solo crypto | 3-4x ratio + min 50-200 contracts |
| Absorption | practitioners | reversal signal | ✅ solo crypto | High delta opposite to price |
| Cumulative Delta divergence | practitioners | exhaustion signal | ✅ solo crypto | Price new high, delta doesn't |
| VWAP deviation | textbook | mean reversion | ✅ all assets | L1 sufficient |
| OBV (On Balance Volume) | textbook | trend confirm | ✅ all assets | L1 sufficient |
| Volume Profile (rough) | L1 1m intraday | support/resistance | ✅ all assets | Less granular than L2 |

## Verdetto edge

**Edge forte ma asset-class-segregated**:

1. **Crypto (BTCUSDT/ETHUSDT perp)**: free L2 Binance → full footprint + delta + imbalance. Edge R² 30-40% su 10-min horizon. Decay 30-60 min. Intraday trading edge.
2. **US equities**: Volume Profile rough da yfinance 1m. Daily timeframe. Edge marginal per L1 only.
3. **US futures**: hard-blocked L2. Lane A (SPY 1h) userà price + volume + VWAP + OBV come proxy.

## Regime dipendenza

Order flow edge è:
- **High-frequency**: edge concentrated in 0-10 min horizon. Decay rapid 30-60 min.
- **Liquidity-dependent**: high-volume instruments (BTCUSDT, SPY) → edge più forte. Low-volume (small caps) → noisy.
- **Event-driven**: edge amplificato su news announcements (FOMC, CPI, earnings).

## Cost-realism check

- **Crypto L2 free $0**: nessun costo dati. Captura via WebSocket going forward + Binance Vision historical.
- **US L2 $75-100/mo**: paywalled. Hard-blocked per $0 rule.
- **Trading costs crypto**: 0.04% taker Binance (vs 0.02% maker). Per 100 trades/mo su $100k → $400 cost. Drag 0.4%/mo.
- **Net edge crypto**: +2-5%/mo realistico su order flow alpha. Sharpe 0.8-1.5 su intraday.
- **Net edge US L1**: marginal, +0-2%/yr su daily timeframe.

## Validazione G5 (ADR-017)

Per promozione crypto L2 strategy:
- DSR ≥ 0.95 (con molti backtests su tick L2)
- PBO < 0.5 (overfitting risk alto su tick-level)
- CPCV OOS Sharpe > 0.5
- 250+ paper sessions con pass-rate ≥ 90%
- Tick-level data → high-frequency overfitting risk → threshold più alto

## Conclusioni Oracle

- **Lane F crypto order flow** (nuova): free L2 → footprint + delta + imbalance su BTCUSDT/ETHUSDT perp. **MVP fattibile $0**.
- **Lane A SPY 1h (esistente)**: hard-blocked L2. Userà L1 + VWAP + OBV proxy.
- **Lane B fundamental equity (esistente)**: non necessita order flow (timeframe multi-month).
- **Lane D VRP (esistente)**: synthetic Black-Scholes, non necessita L2.
