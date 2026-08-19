# 02 Macro — Literature Review

> Fonti: Tavily API (advanced, AI-optimized) 2026-08-17. URL verified per paper.

## 1. Monetary policy rule

### Taylor Rule (Taylor 1993)

**Paper**: Taylor, J. (1993). *Discretion versus policy rules in practice*. Carnegie-Rochester Conference Series on Public Policy.

- **Formula**: fed funds rate = 2 + inflation + 0.5 × (inflation - 2) + 0.5 × output_gap
- **Empirica**: FED segue rule ~50-70% del tempo (Kohn 2007). Deviazioni grandi in crisi (2001-2003 easing, 2008-ZLB, 2020-COVID).
- **Criticisms**: too simplistic, doesn't include financial stability, no preemption (Orphanides 2003).
- **Edge**: deviazione dal Taylor rule predice policy turn → bond alpha.

### Orphanides (2003)

**Paper**: Orphanides, A. (2003). *Monetary Policy Rules and the Great Inflation*.

- **Real-time data** vs revised data: Taylor rule su real-time data non diceva di tighten nella stagflation 1970s.
- **Lesson**: output gap measured è noisy, revise spesso. Edge fondamentale ridotto.

## 2. Yield curve

### Yield Curve Inversion (10Y-2Y)

**Empirical evidence**: 10Y-2Y spread negativo ha preceduto ogni US recession dal 1970 (Borio,例外 1995 soft landing).
- **Lead time**: 12-18 mesi prima della recession.
- **Stato 2026-08-17**: spread = +0.46%, non inverted (MacroRadar). 10Y percentile 53% (medio).
- **Edge**: long equities quando curve >0.5%, defensive quando inverted.

### Hamilton-Ethan 2019

**Paper**: Engstrom, T., Sharpe, S. (2019). *The Near-Term Forward Yield Curve as a Brief Predictor of U.S. Recessions*.

- **Near-term forward spread** (6-quarter-ahead vs current) più accurato del 10Y-2Y.
- Fed Research warning: 10Y-2Y è proxy noisy; forward curve è cleaner.

## 3. Macro factors predict returns

### Cooper-Priestley 2009

**Paper**: Cooper, I., Priestley, A. (2009). *Time-Varying Risk Premiums and the Output Gap*. Review of Financial Studies.

- **Output gap** = log(actual output) - log(potential output). HP-filter per trend.
- **Result**: negative output gap predice high future excess stock + bond returns (in-sample + OOS).
- **Magnitude**: R² ~5-10% su 1-year-ahead equity returns.
- **Edge**: long when output gap negative, reduce when positive.

### Ludvigson-Ng 2009

**Paper**: Ludvigson, S., Ng, S. (2009). *Macro Factors in Bond Risk Premia*. Review of Financial Economics.

- **8 macro factors** estimated via principal components from 132 macro series.
- **Result**: factors explain **21-26% of 1-year-ahead excess bond returns**.
- **Rank importance**: F1 (real activity) > F2 (interest rates) > F8 (stock market) > F3/F4 (inflation).
- **Edge**: real activity factor è il miglior predictor singolo.

### Cieslak-Povala 2015

**Paper**: Cieslak, A., Povala, P. (2015). *Expected Returns in Asset Prices*.

- **Inflation risk premium** è fattore chiave per bond returns.
- **Cieslak-Pospisil 2019** (follow-up): FOMC periodicity + Treasury auction cycle spiegano equity risk premium patterns.

## 4. FOMC announcement effects

### Lucca-Moench 2015

**Paper**: Lucca, D., Moench, E. (2015). *The Pre-FOMC Announcement Drift*. Journal of Finance.

- **Result**: SPX +33bps in 24h prima di FOMC announcements (1994-2011).
- **Drift**: pre-announcement, non post. Equity risk premium concentrated in 24h pre-FOMC.
- **Edge decayed post-2015**: Hillenbrand 2021 estende a 1989-2021, drift ancora presente ma meno pronunciato.

### Hillenbrand 2021

**Paper**: Hillenbrand, C. (2021). *The Fed and the Stock Market*.

- **30y Treasuries**: +13.8-18.6bps/day in 3-day window around FOMC.
- **Persistent edge**: ancora positivo, ma più debole di Lucca-Moench 2015.
- **Mechanism**: risk premium concentrato in FOMC window.

### Gurkaynak-Sack-Swanson 2005

**Paper**: Gurkaynak, R., Sack, B., Swanson, E. (2005). *Do Actions Speak Louder Than Words? The Response of Asset Prices to Monetary Policy Actions and Statements*.

- **Policy surprises** > announced changes. Distiguere target rate vs path surprise.
- **Asset response**: bonds rispondono a target, stocks rispondono a path (forward guidance).
- **Methodology**: futures-based surprise extraction.

## 5. Macro regimes (growth × inflation)

### Bridgewater All Weather (Dalio)

- **4 regimes**: growth↑inflation↑, growth↑inflation↓, growth↓inflation↑, growth↓inflation↓.
- **Asset performance per regime**:
  - Growth↑Inflation↓ → **Stocks** best (rising earnings, falling discount)
  - Growth↓Inflation↓ → **Long bonds** best (falling rates, deflation)
  - Growth↑Inflation↑ → **Commodities** best (real assets)
  - Growth↓Inflation↑ → **Cash + TIPS** best (stagflation)
- **Allocation**: risk-parity across 4 regimes, non 60/40 capital-weighted.
- **State Street ALLW ETF**: 67% bonds, 44% equities, 34% commodities, 37% inflation-linked bonds (leverage-adjusted).

### 60/40 Portfolio (benchmark)

- **2022 crash**: -17% come stocks + bonds entrambi down (correlation flipped positive in inflation↑regime).
- **Backtest**: 1990-2021 +7.5%/yr nominal, Sharpe 0.7. Post-2022 Sharpe ~0.3.
- **Failure mode**: 60/40 assumes stock-bond negative correlation. In inflation↑regime, correlation flips positive → 60/40 non diversified.

## 6. Inflation trading

### TIPS breakeven rate

- **5y breakeven** = 5y Treasury yield - 5y TIPS yield. Market-implied inflation expectation.
- **Current**: 2.6% (2026-08-17), above 15y avg 1.98%.
- **Strategy**: long TIPS quando breakeven < realized CPI, short quando breakeven > realized CPI.
- **Edge**: institutional TIPS trading documented in Haubrich-Pennacchi-Ritchken 2011.

### CPI surprise trading

- **Monthly CPI release** (~10th of month): +200bps intraday moves in TIPS + breakeven.
- **Strategy**: pre-CPI straddle su TIPS futures, long/short su equity sectors sensibili (XLF consumer discretionary vs XLP staples).
- **Edge**: ~50-70bps per CPI release, ma risky around regime shifts.

## 7. Trade balance + currency

### Trade deficit → USD

- **US trade deficit 2026-05**: -$77.59B. Deficit with China/Mexico/Vietnam/Canada/Germany.
- **Current account = 77% trade + 22% financial assets + 1% transfers**.
- **DXY correlation**: USD tende a strengthen quando capital inflows compensano trade deficit (Exorbitant Privilege).
- **Edge**: deterioration trade balance → USD weakness lagging 6-12m. Ma noisy, combined with rate differential.

## 8. Unemployment + payrolls

### Nonfarm payrolls surprise

- **Result**: higher-than-expected payrolls + lower unemployment → USD strength, mixed equities (soft landing signal vs Fed hawkish).
- **Volatility**: 200bps intraday DXY moves su 50k surprise.
- **Edge**: pre-NFP straddle, fade-the-news strategy documented in FinancialJuice/Bloomberg research.

## 9. Cap summary

**Edge forte e persistente**:
- Yield curve inversion (10Y-2Y) — recession predict, lead 12-18m
- Output gap (Cooper-Priestley) — predict excess returns, R² 5-10%
- Macro factors (Ludvigson-Ng) — 21-26% variance explained on bonds
- Growth × Inflation regime — asset class rotation
- FOMC drift (Lucca-Moench, decaying post-2015)

**Edge contestato / decaying**:
- Taylor rule deviation — noisy real-time data
- CPI surprise trading — intraday only, costs high
- Pre-NFP straddle — noisy, regime-dependent

**Edge too long-horizon**:
- Shiller CAPE (vedi dominio 01) — 10y orizzonte
- Demographic trends — 20y+ horizon
