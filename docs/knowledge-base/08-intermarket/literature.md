# 08 Intermarket — Literature Review

> Fonti: Tavily API (advanced) 2026-08-17. URL verified.

## 1. Murphy intermarket framework

### Murphy 1991 — Trading with Intermarket Analysis

**Book**: Murphy, J. (1991). *Trading with Intermarket Analysis*. Wiley.

- **4 asset-class**: stocks, bonds, commodities, currencies.
- **3 key relationships**:
  1. Stocks ↔ Bonds: typically negative (flight to quality)
  2. Bonds ↔ Commodities: inverse (rates up → commodities down)
  3. Commodities ↔ USD: inverse (strong dollar → commodities cheaper)
- **Business cycle stages**:
  - Early expansion: stocks up, bonds down (rate expectations)
  - Late expansion: commodities up (inflationary)
  - Contraction: bonds up (flight to quality), stocks down
  - Recovery: stocks bounce, commodities bottom

### Murphy's PerfChart

- StockCharts.com: compare performance of S&P 500, CRB Index, USD Index, 30y Treasury Bond.
- Identify business cycle stage by which asset class is leading.

## 2. Stock-bond correlation regime

### Baur-Lucey 2010 — Flight to Quality

**Paper**: Baur, D., Lucey, B. (2010). *Is Gold a Hedge or a Safe Haven? An Analysis of Stocks, Bonds and Gold*. Financial Review.

- **Gold safe haven**: negative correlation to stocks + bonds during crises.
- **Flight to quality**: stocks crash → bonds boom (US Treasuries). 4.6% US stock crashes coincide con US bond booms.
- **Asymmetric**: correlation negative only in crises, positive in normal regime.

### Connolly-Stivers-Sun 2005

**Paper**: Connolly, R., Stivers, C., Sun, L. (2005). *Stock Market Uncertainty and the Relation between Stock and Bond Returns*. Journal of Financial Economics.

- **Time-varying correlation**: regime-dependent. High stock vol → flight to quality → negative correlation.
- **Volatility surprise**: equity vol shocks increase stock-bond correlation magnitude (more negative).

### 2022 stock-bond correlation flip

- **2020-2021**: stock-bond correlation negative (normal regime). Bonds hedge equities.
- **2022-2023**: correlation flipped positive. Both stocks AND bonds fell. 60/40 portfolio -17%.
- **Cause**: inflation↑ regime + Fed hiking cycle. Both stocks + bonds re-priced lower.
- **2024-2026 re-normalization**: correlation back to negative as inflation cooled.

## 3. Commodity-currency

### DXY + commodities inverse

- **Strong DXY** → commodities cheaper globally (priced in USD).
- **Weak DXY** → commodities expensive.
- **Magnitudes**: DXY +1% → oil -2-3%, gold -1-2%, copper -2-3%.

### Commodity currencies

- **CAD**: oil-correlated (Canada exports oil).
- **AUD**: iron-ore + coal-correlated.
- **BRL**: iron-ore + soybeans.
- **ZAR**: gold + platinum.
- **NOK**: oil.
- **RUB**: oil + gas (sanctions dependent).

## 4. Bitcoin as safe haven

### Fibo-crypto 2026 research

- **BTC correlation with Nasdaq/tech**: increased since 2020. Range 0.3-0.6.
- **BTC correlation with gold**: low, oscillating -0.1 to +0.3. NOT a safe haven.
- **Volatility BTC**: ~50-60% annualized. vs Gold 15-20%.
- **Verdict**: BTC is **risk asset**, not safe haven. NOT a gold substitute.

### Implications for portfolio

- **5-15% BTC allocation**: high return potential, high vol.
- **Inflation hedge debate**: no income stream (vs TIPS coupons). Capital appreciation only.
- **Liquidity**: high for BTC, low for small caps altcoins.

## 5. Sector rotation

### Sam Stovall — S&P Guide to Sector Rotation

- **4 stages business cycle** (since 1948 data):
  1. **Early Expansion**: cyclical sectors outperform — Consumer Discretionary (XLY), Technology (XLK), Industrials (XLI).
  2. **Peak**: energy + materials benefit from commodity inflation — Energy (XLE), Materials (XLB).
  3. **Contraction**: defensive sectors hold up — Utilities (XLU), Healthcare (XLV), Consumer Staples (XLP).
  4. **Recovery/Trough**: financials lead as rates fall — Financials (XLF).
- **Lead time**: 6-9 months. Markets forward-looking, sectors rotate before economic data confirms.
- **Practical**: SPDR sector ETFs (XLY, XLK, XLI, XLE, XLB, XLU, XLV, XLP, XLF) — all free via yfinance.

## 6. Credit spread predictors

### Asness 2013 — Baa-Aaa spread

- **Baa-Aaa spread** = Baa yield - Aaa yield. Quality spread within investment grade.
- **Predict equity**: high spread → tight financial conditions → low future equity returns.
- **Mechanism**: credit spread = recession indicator.

### Collin-Dufresne-Goldstein-Martin 2001

- **Credit spread determinants**: macro factors + market volatility.
- **Predictability**: bond returns predictable from credit spread + term spread.

### FRED series

- **BAA_AAA** — Moody's Baa-Aaa spread
- **BAMLH0A0HYM2** — BofA US High Yield Index option-adjusted spread
- **T10YIE** — 10y breakeven inflation
- **DGS10** — 10y Treasury yield
- **WILL5000INDFC** — Wilshire 5000 total market index

## 7. Cap summary

**Edge forte maintained**:
- Murphy 3 correlations — regime-dependent but persistent.
- Baur-Lucey flight-to-quality — asymmetric in crises.
- Stovall sector rotation — 6-9m lead, free ETFs.
- Baa-Aaa credit spread — recession predict.

**Edge decayed**:
- 2022 stock-bond positive correlation broke Murphy model. Re-normalized 2024-2026.

**Edge hard-blocked**:
- Real-time cross-asset futures — paywalled Refinitiv/Bloomberg. ETFs via yfinance are free.
