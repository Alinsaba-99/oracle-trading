# 09 Cyclical — Literature Review

> Fonti: Tavily API (advanced) 2026-08-17. URL verified.

## 1. Elliott Wave Theory

### Elliott 1938 — original

**Book**: Elliott, R. (1938). *The Wave Principle*.

- **5-3 wave pattern**: 5 impulse waves + 3 corrective waves per cycle.
- **Fibonacci ratios**: wave 2 = 0.618 × wave 1, wave 3 = 1.618 × wave 1, etc.
- **Fractal**: same pattern at all timeframes (1m to monthly).

### Frost-Prechter 1978 — Elliott Wave Principle

**Book**: Frost, A., Prechter, R. (1978). *Elliott Wave Principle: Key to Market Behavior*.

- **Wave personality**: wave 3 strongest, wave 2 + wave 4 alternate in complexity.
- **Rule of alternation**: corrections alternate (sharp vs sideways).
- **Channel technique**: trendlines parallel channels project wave 5 target.
- **Subjectivity**: same chart can be interpreted differently by 2 Elliotticians.

### Empirical evidence

- **Limited predictive power**: academic studies show inconsistent OOS results.
- **Hindsight bias**: easy to fit waves after the fact, hard in real-time.
- **Self-organization**: practitioners constantly revise wave counts.

## 2. Gann Theory

### Gann 1923 — Truth of the Stock Tape

**Book**: Gann, W. (1923). *Truth of the Stock Tape*.

- **3 pillars**:
  1. Price: support/resistance levels
  2. Time: time determines reversals ("when time is up, price will follow")
  3. Proportion: geometric angles (1x1, 2x1, 3x1) + circle (360°) + square + triangle
- **Gann Fan**: 9 angles from major high/low, 1x1 = 45° (most important).
- **Square of Nine**: spiral of numbers 1, 2, 3, ..., 9, 16, 25, ... = key support/resistance.
- **Time cycles**: 90-day, 180-day, 360-day cycles (seasonal + geometric).

### Empirical evidence

- **Mysticism + mathematics**: some geometric angles work, some don't. No rigorous OOS test.
- **Self-fulfilling**: enough traders watch Gann angles → support/resistance becomes real.
- **Square of Nine**: hit/miss on actual reversals.

## 3. Hurst exponent

### Hurst 1951 — original

**Paper**: Hurst, H. (1951). *Long-Term Storage Capacity of Reservoirs*. Transactions of the American Society of Civil Engineers.

- **R/S analysis** (Rescaled Range): range of cumulative deviations / standard deviation.
- **Hurst exponent H** = log(R/S) / log(n) regression slope.
- **H = 0.5** = random walk (Brownian motion)
- **H > 0.5** = persistent (trending, long memory)
- **H < 0.5** = anti-persistent (mean reverting)

### Mandelbrot 1968 — fractal application

**Paper**: Mandelbrot, B. (1968). *Robustness of the Rescaled Range R/S in the Measurement of Noncyclic Long Run Statistical Dependence*.

- **Fractional Brownian motion**: H parameter generalizes Brownian motion.
- **Long memory**: H > 0.5 → autocorrelation decays hyperbolically (vs exponentially in AR models).
- **Financial time series**: most equity indices H ~0.55-0.65 (persistent trending).

### S&P 500 Hurst dynamics 2022 study

- **Hurst exponent dynamics of S&P 500 returns**: H < 0.5 in EMH assumption, but actual values often exceed 0.5.
- **Misconception**: Mandelbrot's "H > 0.5 = long memory" actually measures persistence/fractal trending, NOT strict long memory.
- **Multifractal processes**: financial returns exhibit multifractal scaling, large deviations + multiplicative cascades.

### Empirical edge

- **Trending vs mean-reverting classification**: H > 0.6 → trend-following strategies work. H < 0.4 → mean-reversion works.
- **Regime detection**: H shifts during crises (2020 COVID → H drops to 0.3 = anti-persistent panic).
- **Edge**: documented in academic literature, replicable OOS.

## 4. Kondratieff wave

### Kondratieff 1926 — long wave theory

**Paper**: Kondratieff, N. (1926). *Long Waves in Economic Life*.

- **50-60 year cycles**: 4 phases (recovery, prosperity, recession, depression).
- **Empirical observations**: 1780-1840 (Industrial Revolution), 1840-1890 (Railway), 1890-1940 (Electricity + Steel), 1940-1990 (Automobile + Aviation), 1990-2040 (Information Tech).
- **Driver**: technological innovation clusters (Schumpeter 1934).

### Schumpeter 1939 — Business Cycles

**Book**: Schumpeter, J. (1939). *Business Cycles: A Theoretical, Historical, and Statistical Analysis of the Capitalist Process*.

- **4-tier cycle hierarchy**:
  1. **Kondratieff** (50-60y): innovation waves
  2. **Kuznets** (15-25y): infrastructure investment
  3. **Juglar** (7-11y): fixed capital investment
  4. **Kitchin** (3-4y): inventory cycle
- **Innovation as driver**: entrepreneur clusters → creative destruction.

### Empirical evidence

- **Hecht-Jason 2014**: long waves ~50y confirmed in economic + financial data.
- **Process innovation downswing** vs **product innovation upswing**.
- **Limitation**: 200 years of data = only 4 cycles observed. Hard to test statistically.

## 5. Cap summary

**Edge rigorous + maintained**:
- Hurst exponent — long memory + trending classification, replicable OOS.

**Edge subjective + non-rigorous**:
- Elliott Wave — hindsight bias, subjective counts.
- Gann Theory — mysticism + self-fulfilling geometric levels.

**Edge too long-horizon / untestable**:
- Kondratieff 50-60y — only 4 cycles observed since 1780.
- Schumpeter 4-tier — descriptive, hard to test.

**Implication for Oracle**: Hurst exponent + cycle detection via FFT is buildable. Elliott + Gann + Kondratieff sono **educational / speculative**, NON signal generating per Oracle.
