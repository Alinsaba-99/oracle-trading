# 12 Behavioral — Literature Review

> Fonti: Tavily API (advanced) 2026-08-17. URL verified.

## 1. Long-term reversal

### De Bondt-Thaler 1985

**Paper**: De Bondt, W., Thaler, R. (1985). *Does the Stock Market Overreact?* Journal of Finance.

- **Methodology**: rank stocks by 3y past returns. Long losers (bottom decile), short winners (top decile). Hold 3-5y.
- **Result**: losers outperform winners by ~5-8%/yr over 3-5y.
- **Asymmetric**: stronger reversal for losers than winners.
- **January concentration**: ~50% of reversal in January (tax-loss selling + reinvestment).
- **Cause**: investor overreaction to recent performance.
- **Edge maintained**: replicated multiple times.

### De Bondt-Thaler 1987

- Reversal persists even after controlling for size + beta + CAPM.
- Behavioral explanation robust.

## 2. Prospect theory + loss aversion

### Kahneman-Tversky 1979

**Paper**: Kahneman, D., Tversky, A. (1979). *Prospect Theory: An Analysis of Decision under Risk*. Econometrica.

- **Value function**: S-shaped, steeper for losses than gains.
- **Loss aversion**: losses hurt ~2.25x more than equivalent gains feel good.
- **Reference dependence**: utility measured relative to reference point (purchase price), not absolute wealth.
- **Risk-seeking in losses**: gamblers double-down to recover.
- **Risk-averse in gains**: lock in profits early.
- **Implications for trading**:
  - Disposition effect: sell winners too early, hold losers too long.
  - House money effect: risk-taking after gains.
  - Break-even effect: risk-seeking to recover losses.

### Thaler 1980 + 1985

- Mental accounting: separate buckets for separate investments (vs portfolio view).
- Endowment effect: ownership overvalues assets.

## 3. Irrational exuberance + CAPE

### Shiller 2000

**Book**: Shiller, R. (2000). *Irrational Exuberance*. Princeton University Press.

- **CAPE ratio**: S&P 500 price / 10y average inflation-adjusted earnings.
- **Predictive**: forward 10y stock returns correlate -0.4 to -0.5 with initial CAPE.
- **2000 dotcom prediction**: CAPE > 40 = bubble. Subsequent -50% crash 2000-2002.
- **2007 housing bubble**: Shiller warned again. Subsequent GFC.
- **2026 status**: CAPE > 30 = elevated but not bubble territory.

### Shiller CAPE critics

- **Siegel**: accounting changes (buybacks + dividends) inflate EPS, CAPE understated.
- **Modified CAPE** (interest-rate adjusted, ECY): better signal.

## 4. Black Swan + Antifragile

### Taleb 2007 — The Black Swan

- **Definition**: rare, extreme impact, retrospectively predictable events.
- **Fat-tailed distributions**: Gaussian models underestimate tail risk.
- **Implication**: financial models using normal distribution underprice tail risk.

### Taleb 2012 — Antifragile

- **Antifragile**: systems that benefit from volatility (vs fragile that breaks).
- **Barbell strategy**: 90% safe assets (cash + Treasuries) + 10% convex bets (long-dated options + venture).
- **Avoid fragile middle**: leverage, short-vol, hidden tail exposures.
- **Convexity**: cap downside, unlimited upside.
- **Tail risk hedging**: SPY OTM puts as insurance.

## 5. Extrapolative expectations

### Greenwood-Shleifer 2014

**Paper**: Greenwood, R., Shleifer, A. (2014). *Expectations of Returns and Asset Prices*.

- **Survey data**: investor expectations of future returns extrapolate recent past returns.
- **Mechanism**: high recent returns → high expectations → more inflows → higher prices → bubble.
- **6 surveys tested** (Gallup, AAII, II, VIX-implied, CFO, Shiller): all show extrapolative behavior.
- **Implications**: expectation spikes → low future returns.

### Barberis 2018

**Paper**: Barberis, N. (2018). *Psychology-based Models of Asset Prices and the Case for an Empirical Distinction Between Bubbles and Style Investing*.

- Extrapolation + bubbles formal model.
- Combines Greenwood-Shleifer with behavioral theory.
- Bubbles: high prices driven by extrapolative expectations.

## 6. Disposition effect

### Frazzini 2006

**Paper**: Frazzini, A. (2006). *The Disposition Effect and Underreaction to News*.

- **Investors sell winners too early, hold losers too long** (Kahneman-Tversky implication).
- **Underreaction**: unrealized losses → information not impounded in price → drift.
- **PEAD**: post-earnings announcement drift amplification via disposition.
- **Strategy**: long high-CP + positive surprise + high unrealized losses (held by disposition investors).

## 7. Cap summary

**Edge maintained**:
- De Bondt-Thaler reversal (3-5y).
- Shiller CAPE bubble detection.
- Frazzini disposition effect + PEAD amplification.
- Taleb barbell tail-risk hedging.

**Edge behavioral framework** (non signal diretto):
- Kahneman-Tversky prospect theory (position sizing).
- Greenwood-Shleifer extrapolative expectations (bubble warning).

**Edge too long-horizon**:
- Shiller CAPE (10y predict).
- De Bondt-Thaler (3-5y horizon).
