# Dominio 09 — Cyclical / Elliott / Gann / Hurst

> Knowledge base Oracle — studio approfondito 2026-08-17 via Tavily API.
> **Edge contestato / metodologicamente discusso**.

## Sintesi esecutiva

Il dominio ciclico è il più **contestato in letteratura** — edge documentato è debole o difficile da validare empiricamente:

1. **Elliott Wave Theory** (Elliott 1938, Frost-Prechter 1978): principle of 5-3 wave patterns + Fibonacci ratios. **Subjektivo**, no definitive empirical evidence di predictive power consistente. Hindsight bias problem.
2. **Gann Theory** (Gann 1923): geometric angles (1x1, 2x1, 3x1), Square of Nine, time cycles. "When time is up, price will follow". Misto di mysticism + mathematics, non testabile rigorosamente.
3. **Hurst exponent** (Hurst 1951, Mandelbrot 1968): long memory in time series. H > 0.5 = persistent (trending), H < 0.5 = anti-persistent (mean reverting), H = 0.5 = random walk. **Mathematica rigorosa + edge documentato**.
4. **Kondratieff wave** (Kondratieff 1926): 50-60 year economic cycle. Schumpeter support con innovation waves. **Empirical evidence debatable** (few cycles observed since 1780).
5. **Schumpeter business cycle** (1939): innovation clusters drive long waves. Kondratieff ~50-60y, Kuznets ~15-25y, Juglar ~7-11y, Kitchin ~3-4y.

**Edge summary**:
- ✅ **Hurst exponent** = edge rigoroso, mantenuto OOS
- ⚠️ Elliott + Gann = subjective, non testabile scientificamente
- ⚠️ Kondratieff = too few observations per cycle, hard to test

**Cap to build Oracle**:
1. Hurst exponent calculator (R/S analysis)
2. Cycle detector (FFT + spectral analysis)
3. Schumpeter 4-tier cycle classifier (long-horizon macro overlay)

Vedi [literature.md](literature.md), [data-audit.md](data-audit.md), [edge.md](edge.md), [capability-map.md](capability-map.md).
