# 12 Behavioral — Capability Map per Oracle

> Cosa costruire in Oracle (edge forte + free data + stack ready).

## ✅ Già in Oracle

| Capability | File | Note |
|---|---|---|
| Lane B backtester | `analytics/strategy/lane_b_backtester.py` | Fundamental equity (disposition-prone universe) |
| FRED VIX loader | `analytics/macro/fred.py:FREDClient` | Risk aversion proxy |
| LLM via vsllm/OmniRoute | `analytics/ai_analysts/lateral.py` + `synthesizer.py` | Sentiment + behavioral detection |

## 🔨 P1 — Implementare prossimo (edge forte + free data)

### BL-KB-86: Shiller CAPE adapter + bubble detector
- **Perché**: Shiller 2000 bubble prediction, 10y return correlation -0.5.
- **Cosa**: `analytics/behavioral/cape_adapter.py:CAPEAdapter` con:
  - Download http://www.econ.yale.edu/~shiller/data/ie_data.xls (monthly)
  - CAPE calculation: S&P 500 price / 10y avg inflation-adjusted earnings
  - Bubble detector: CAPE > 35 = elevated, > 45 = bubble, < 15 = undervalued
  - Output: CAPE value + historical percentile
- **Tempo**: ~1-2 giorni.
- **Costo**: $0.

### BL-KB-87: De Bondt-Thaler reversal signal
- **Perché**: +5-8%/yr over 3-5y, robust replicated.
- **Cosa**: `analytics/strategy/catalog/behavioral.py:DeBondtThalerSignal` con:
  - Rank stocks by 3y past returns
  - Long bottom decile (losers), short top decile (winners)
  - Hold 3-5y, rebalance annually
  - Edge concentrated in January (tax-loss selling effect)
- **Tempo**: ~2-3 giorni.

### BL-KB-88: Taleb barbell tail-risk overlay
- **Perché**: convexity + insurance, Black Swan protection.
- **Cosa**: `analytics/strategy/lane_k_tail_risk.py:TalebBarbellStrategy` con:
  - 90% safe: Treasury bills (BIL ETF) or cash
  - 10% convex bets: SPY OTM puts 3-6m out, 20-30% OTM
  - Roll puts monthly
  - Cost budget: 1-2%/yr insurance premium
- **Target**: limit drawdown to -20% max in any year (vs SPY -50% in 2008).
- **Tempo**: ~3-5 giorni.

### BL-KB-89: Loss aversion position sizing
- **Perché**: Kahneman-Tversky 1979. Methodology for sizing.
- **Cosa**: `analytics/strategy/catalog/behavioral.py:LossAversionSizer` con:
  - Position size scaled by unrealized P&L relative to reference
  - Reduce size after -X% (avoid doubling-down to recover)
  - Increase size after +X% (house money effect aware, not doubling)
  - Disposition-aware exit (sell winners if momentum breaks, hold losers if thesis intact)
- **Tempo**: ~2-3 giorni.

### BL-KB-90: Bubble detector (Greenwood-Shleifer)
- **Perché**: extrapolative expectations → bubble warning.
- **Cosa**: `analytics/strategy/catalog/behavioral.py:BubbleDetector` con:
  - Inputs: CAPE (BL-KB-86) + sentiment (dominio 05 composite) + extrapolative survey data (AAII + II + Baker-Wurgler)
  - Output: bubble probability [0, 1]
  - Bubble = high CAPE + high sentiment + extrapolative expectations
- **Tempo**: ~3-5 giorni.

## 🔨 P2 — Implementare per ensemble

### BL-KB-91: Lane K behavioral composite strategy
- **Perché**: nuova lane per behavioral ensemble.
- **Cosa**: `analytics/strategy/lane_k_behavioral.py:BehavioralCompositeStrategy` con:
  - Universe: SPY + 11 SPDR sectors + De Bondt-Thaler losers decile
  - Signals: De Bondt-Thaler (BL-KB-87) + Bubble detector (BL-KB-90) + Taleb barbell (BL-KB-88)
  - Risk: Taleb barbell overlay (90% safe + 10% convex)
  - Loss aversion sizing (BL-KB-89) on all positions
- **Target**: Sharpe > 0.6 su 1990-2025, max DD < 25%.
- **Tempo**: ~5-7 giorni.

## 🔄 P3 — Deferrire

- **Disposition effect detection per ticker** — requires 13-F + options flow data. Defer.
- **Real-time sentiment Twitter** — paywalled, skip.
- **NFT/Crypto behavioral** — defer to dominio 11 on-chain.

## ❌ Hard-blocked (paywalled)

- Bloomberg behavioral analytics — $24k/yr
- Refinitiv sentiment + flows — $1.8k/mo
- Investor's Intelligence historical — $50/mo
- Dataminr social sentiment — enterprise

## Sequenza implementazione raccomandata

```
BL-KB-86 Shiller CAPE adapter    (~1-2g)
BL-KB-87 De Bondt-Thaler         (~2-3g)
BL-KB-88 Taleb barbell tail-risk (~3-5g)
BL-KB-89 Loss aversion sizing    (~2-3g)
BL-KB-90 Bubble detector         (~3-5g)
BL-KB-91 Lane K behavioral       (~5-7g)
```

Totale: **~16-25 giorni** per behavioral P1+P2.

## Prossimo step

Dopo P1+P2:
1. Backtest Lane K behavioral su 1990-2025
2. DSR/PBO/CPCV validation (dominio 03)
3. **Target**: Sharpe > 0.6 on Lane K. Combina con Lane B + sentiment overlay + Lane F (crypto order flow) per ensemble multi-domain.
