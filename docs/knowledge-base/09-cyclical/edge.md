# 09 Cyclical — Edge Plausibility

> Valutazione critica per ogni cyclical signal.

## Edge summary

| Signal | Source | Edge | Free $0 | Rigore | Decay |
|---|---|---|---|---|---|
| Hurst exponent (R/S) | Hurst 1951, Mandelbrot 1968 | +1-2%/yr trending classification | ✅ | ✅ rigorous | basso |
| Hurst regime shift | academic | crisis detection (H < 0.4) | ✅ | ✅ rigorous | basso |
| FFT cycle detection | spectral analysis | marginal | ✅ | ✅ rigorous | medio |
| Elliott Wave | Elliott 1938, Frost-Prechter 1978 | subjective, non-replicable | ✅ | ❌ subjective | n/a |
| Gann angles | Gann 1923 | self-fulfilling | ✅ | ❌ subjective | n/a |
| Kondratieff wave | Kondratieff 1926 | long-horizon (50-60y) | ✅ | ⚠️ few observations | n/a |
| Schumpeter 4-tier cycle | Schumpeter 1939 | descriptive | ✅ | ⚠️ descriptive | n/a |

## Verdetto edge

**Edge rigoroso + maintained**:
- **Hurst exponent** (H > 0.5 trending, H < 0.5 mean-reverting): classificazione rigorosa, replicabile OOS, edge documentato in literature.
- **Hurst regime shift** (crisis detection): H drops during crises (anti-persistent panic), early warning signal.

**Edge subjective + non-replicable**:
- Elliott Wave: hindsight bias, multiple interpretations same chart, no OOS validation.
- Gann Theory: self-fulfilling geometric levels, no rigorous empirical support.

**Edge too long-horizon**:
- Kondratieff 50-60y: only 4 cycles observed since 1780, statistically weak.
- Schumpeter 4-tier: descriptive framework, not tradable signal.

## Regime dipendenza

- **Hurst regime detection**: H shifts precede crises (useful for crisis timing).
- **Cycle FFT**: cycle strength varies by market + asset class, not universal.
- **Elliott/Gann**: no regime dependence (subjective).

## Cost-realism check

- **Trading costs**: cyclical signals low-frequency, 20-50 trades/yr → marginal costs.
- **Tax**: same as equity (~26% IT capital gains).
- **Net edge realistico**: +0.5-1%/yr post-cost su 5y con Hurst alone. Sharpe 0.2-0.4.

## Validazione G5 (ADR-017)

Per promozione cyclical strategy:
- DSR ≥ 0.95
- PBO < 0.5 (Elliott/Gann non testabili, automatic reject)
- CPCV OOS Sharpe > 0.5
- 250+ paper sessions con pass-rate ≥ 90%

Hurst exponent è l'unico cyclical signal rigoroso. Elliott + Gann sono **educational**, non implementabili come signal generation.
