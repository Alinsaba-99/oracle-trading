# 09 Cyclical — Capability Map per Oracle

> Cosa costruire in Oracle (rigorous Hurst + FFT only; Elliott/Gann/Kondratieff sono educational).

## ✅ Già in Oracle

| Capability | File | Note |
|---|---|---|
| Dukascopy lake | `data/lake/normalized/symbol=EURUSD/...` | 21 symbols 1m+5m+1h+1d |
| statsmodels | (installed) | HP filter (dominio 02) |

## 🔨 P1 — Implementare prossimo (rigorous edge + free data)

### BL-KB-69: Hurst exponent calculator
- **Perché**: Hurst 1951 + Mandelbrot 1968. Edge rigoroso per trending vs mean-reverting classification.
- **Cosa**: `analytics/strategy/catalog/cyclical.py:HurstCalculator` con:
  - R/S analysis (rescaled range method)
  - Rolling window: 252d (annual), 756d (3y), 1260d (5y)
  - Output: H value per asset + regime label (trending if H > 0.6, mean-revert if H < 0.4, random if H ~0.5)
  - Crisis detection: H drop below 0.4 in last 30d
- **Tempo**: ~2-3 giorni.
- **Costo**: $0 (hurster Python lib free).

### BL-KB-70: FFT cycle detector
- **Perché**: spectral analysis per cycle strength + dominant periods.
- **Cosa**: `analytics/strategy/catalog/cyclical.py:FFTSignal` con:
  - FFT (Fast Fourier Transform) via scipy.fft
  - Power spectrum: dominant cycle periods
  - Output: top-3 dominant cycle periods + strength
- **Tempo**: ~2-3 giorni.

### BL-KB-71: Schumpeter 4-tier cycle classifier (long-horizon macro overlay)
- **Perché**: Schumpeter 1939 framework. Long-horizon macro context.
- **Cosa**: `analytics/strategy/catalog/cyclical.py:SchumpeterCycleClassifier` con:
  - Kondratieff (50-60y): innovation waves, FRED GDP + tech investment
  - Kuznets (15-25y): infrastructure, FRED fixed investment
  - Juglar (7-11y): fixed capital, FRED business investment
  - Kitchin (3-4y): inventory, FRED inventories
  - Output: 4 cycle phase labels (recovery/prosperity/recession/depression)
- **Tempo**: ~3-5 giorni.
- **Caveat**: descriptive framework, not signal generation. Use as macro context only.

## 🔄 P3 — Educational only (NON signal generation)

### BL-KB-72: Elliott Wave visualizer (educational)
- **Perché**: educational reference, NON signal generation.
- **Cosa**: visual tool per wave count visualization. NOT a strategy.
- **Status**: deferred indefinitely.

### BL-KB-73: Gann angle calculator (educational)
- **Perché**: geometric levels support/resistance. Self-fulfilling.
- **Cosa**: Gann Fan angles + Square of Nine visualization. NOT a strategy.
- **Status**: deferred indefinitely.

## ❌ Hard-blocked (paywalled)

- Bloomberg cycle analysis — $24k/yr
- Refinitiv cycle tools — $1.8k/mo
- WaveBasis (Elliott proprietary) — $30/mo

## Sequenza implementazione raccomandata

```
BL-KB-69 Hurst exponent          (~2-3g) ← rigorous edge
BL-KB-70 FFT cycle detector     (~2-3g) ← spectral analysis
BL-KB-71 Schumpeter classifier  (~3-5g) ← macro context (educational)
```

Totale: **~7-11 giorni** per cyclical rigoroso.

## Prossimo step

Dopo P1:
1. Backtest Hurst regime classifier → allocate trend-following vs mean-reversion strategies by H value
2. FFT cycle detector → identify dominant cycle periods per asset
3. Combina con Lane B + macro overlay per ensemble

**Target**: Hurst-based regime classifier per dynamically switch between trend-following + mean-reversion. +1-2%/yr post-cost su 5y. Sharpe 0.2-0.4 (overlay).
