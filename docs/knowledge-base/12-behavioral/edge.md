# 12 Behavioral — Edge Plausibility

> Valutazione critica per ogni behavioral signal.

## Edge summary

| Signal | Source | Edge | Free $0 | Orizzonte | Decay |
|---|---|---|---|---|---|
| De Bondt-Thaler reversal | De Bondt-Thaler 1985 | +5-8%/yr 3-5y | ✅ | 3-5y | basso (robust replicated) |
| Shiller CAPE bubble | Shiller 2000 | -0.5 corr 10y returns | ✅ | 10y | basso (predictive) |
| Loss aversion position sizing | Kahneman-Tversky 1979 | behavioral framework | ✅ | n/a (methodology) | n/a |
| Taleb barbell tail-risk | Taleb 2007/2012 | convexity + insurance | ✅ | event-driven | basso |
| Frazzini disposition + PEAD | Frazzini 2006 | +2-4% drift amplification | ✅ | 1-3m | medio |
| Extrapolative expectations | Greenwood-Shleifer 2014 | bubble warning | ✅ | 3-12m | medio |
| Disposition effect detection | practitioners | +1-2%/3m | ✅ | 1-3m | medio |

## Verdetto edge

**Edge maintained**:
- **De Bondt-Thaler reversal** (3-5y) — robusto, replicated multiple times. Asymmetric + January concentration.
- **Shiller CAPE** (10y predict) — bubble detection. Forward 10y returns -0.4 to -0.5 correlation.
- **Taleb barbell** — tail risk hedging via convexity (SPY OTM puts).
- **Frazzini disposition + PEAD** — drift amplification via disposition behavior.

**Edge behavioral framework** (non signal diretto):
- **Kahneman-Tversky prospect theory** — methodology for position sizing + risk management.
- **Greenwood-Shleifer extrapolation** — bubble warning signal (high recent returns → low future).

## Regime dipendenza

- De Bondt-Thaler: stronger after extended bull (overreaction larger).
- Shiller CAPE: 10y horizon, regime-cycle dependent.
- Taleb barbell: event-driven (tail risk emerges in crises).
- Disposition effect: stronger in retail-heavy stocks.

## Cost-realism check

- **Trading costs**: behavioral low-frequency (quarterly/annual), 20-50 trades/yr → marginal.
- **Tail risk hedging cost**: SPY OTM puts ~1-2%/yr premium. Drag on bull markets, lifesaver in crashes.
- **Tax**: same as equity.
- **Net edge realistico**: +1-3%/yr post-cost su 5y. Sharpe 0.3-0.6.

## Validazione G5 (ADR-017)

Per promozione behavioral strategy:
- DSR ≥ 0.95
- PBO < 0.5
- CPCV OOS Sharpe > 0.5
- 250+ paper sessions con pass-rate ≥ 90%

Behavioral edge è less noisy di L2/news ma slower (3m-5y horizon). Combina con Lane B + sentiment overlay.
