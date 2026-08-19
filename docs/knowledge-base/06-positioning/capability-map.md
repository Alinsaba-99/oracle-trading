# 06 Positioning — Capability Map per Oracle

> Cosa costruire in Oracle (edge forte + free CFTC data + stack ready).

## ✅ Già in Oracle

| Capability | File | Note |
|---|---|---|
| Dukascopy forex lake (legacy) | `data/lake/normalized/symbol=EURUSD/...` | 21 symbols cached |

## 🔨 P1 — Implementare prossimo (edge forte + free data)

### BL-KB-48: CFTC COT adapter
- **Perché**: CFTC free 1986+, edge documentato Asness + Bhansali.
- **Cosa**: `analytics/positioning/cot_adapter.py:COTAdapter` con:
  - `pip install cot_reports`
  - Fetch legacy + disaggregated + TFF reports
  - Cache su `data/positioning/cot/{report_type}_{symbol}_{date}.csv`
  - Parse Polars DataFrame: commercial/non-commercial/nonreportable + net positions
- **Output**: weekly snapshot per symbol.
- **Tempo**: ~2-3 giorni.
- **Costo**: $0.

### BL-KB-49: Smart Money Indicator (SMI) calculator
- **Perché**: Bhansali 2014 robusto a multiple testing, +4-6%/yr.
- **Cosa**: `analytics/strategy/catalog/positioning.py:SmartMoneyIndicator` con:
  - SMI = (non-commercial net - commercial net) / open_interest
  - Normalize to z-score (5y lookback)
  - Output: SMI score [-3, +3] per asset
- **Tempo**: ~1-2 giorni.

### BL-KB-50: Hedging pressure signal (De Roon 2000)
- **Perché**: R² 5-10% on 1-3m, complementare a SMI.
- **Cosa**: `analytics/strategy/catalog/positioning.py:HedgingPressureSignal` con:
  - HP = commercial net position / open_interest
  - Extreme HP > 0.5 = commercial long extreme (bullish contrarian)
  - Extreme HP < -0.5 = commercial short extreme (bearish contrarian)
- **Tempo**: ~1 giorno.

### BL-KB-51: Open interest signal (Hong-Yogo 2012)
- **Perché**: complements hedging pressure, R² 2-3%.
- **Cosa**: `analytics/strategy/catalog/positioning.py:OpenInterestSignal` con:
  - OI growth = (OI_t - OI_t-4w) / OI_t-4w
  - High OI growth → bullish, low/negative → bearish
- **Tempo**: ~1 giorno.

### BL-KB-52: Lane G COT positioning strategy
- **Perché**: nuova lane per Oracle. Long-or-flat timing su commodity futures.
- **Cosa**: `analytics/strategy/lane_g_cot.py:COTPositioningStrategy` con:
  - Universe: top commodity futures (ES, NQ, CL, GC, SI, HG, ZB, ZN, DX)
  - Signals: SMI (BL-KB-49) + Hedging Pressure (BL-KB-50) + OI (BL-KB-51)
  - Long-or-flat per Bhansali 2014 methodology
  - Rebalance weekly (post-Friday COT release)
  - Risk: 2% equity per asset, max 5 concurrent
- **Target**: Sharpe > 0.7 su 1990-2025 backtest.
- **Tempo**: ~3-5 giorni (depends on BL-KB-48..51).

## 🔨 P2 — Implementare per validazione G5

### BL-KB-53: Commodity basis + curve signal
- **Perché**: Fama-French 1987 + Bessembinder-Chan 1992. Futures basis predicts returns.
- **Cosa**: `analytics/strategy/catalog/positioning.py:BasisSignal` con:
  - basis = futures price - spot price (contango vs backwardation)
  - Backwardation → high future returns (positive roll yield)
  - Contango → low future returns (negative roll yield)
- **Data**: CME futures prices (IBKR delayed) + spot (yfinance).
- **Tempo**: ~2-3 giorni.

### BL-KB-54: T-Bill rate commodity predictability
- **Perché**: Bessembinder-Chan 1992 strongest in-sample predictor.
- **Cosa**: integrate in macro overlay (vedi dominio 02).
- **Tempo**: ~1 giorno.

## 🔄 P3 — Deferrire

- **Broker-dealer risk aversion (Etula 2013)** — hard to proxy free. Skip MVP.
- **OVX variance risk premium oil** — quando CBOE OVX free data available.
- **Real-time positioning post-COT** — paywalled Refinitiv/Bloomberg.

## ❌ Hard-blocked (paywalled)

- Refinitiv real-time COT — $1.8k/mo
- Bloomberg positioning — $24k/yr
- CME Live COT — paid
- TradingVolume.com — $50/mo
- QuikStrike COT — paid

## Sequenza implementazione raccomandata

```
BL-KB-48 CFTC COT adapter         (~2-3g) ← cot_reports lib
BL-KB-49 SMI calculator           (~1-2g) ← Bhansali 2014
BL-KB-50 Hedging pressure signal  (~1g)   ← De Roon 2000
BL-KB-51 Open interest signal     (~1g)   ← Hong-Yogo 2012
BL-KB-52 Lane G positioning       (~3-5g) ← orchestrator
BL-KB-53 Commodity basis signal   (~2-3g) ← Fama-French 1987
BL-KB-54 T-Bill commodity overlay (~1g)   ← Bessembinder-Chan
```

Totale: **~11-16 giorni** per completare P1+P2 positioning.

## Prossimo step

Dopo P1+P2:
1. Backtest Lane G su 1986-2025 commodity futures con COT data
2. DSR/PBO/CPCV validation (dominio 03)
3. **Target**: Sharpe > 0.7 on Lane G. Combinare con Lane B (fundamental, Sharpe 0.93) per ensemble.
