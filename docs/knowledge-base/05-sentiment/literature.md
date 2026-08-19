# 05 Sentiment — Literature Review

> Fonti: Tavily API (advanced) 2026-08-17. URL verified per paper.

## 1. Academic sentiment theory

### Brown-Cliff 2005

**Paper**: Brown, S., Cliff, M. (2005). *Sentiment and Asset Pricing*.

- **Sentiment indicators**: II survey, closed-end fund discount, NYSE odd-lot ratio, net mutual fund flows, ARMS index, IPO volume + returns.
- **Result**: sentiment predicts DJIA stock returns at 1-, 2-, 3-year horizons.
- **Coefficient sign**: negative (high sentiment → low future returns).
- **Magnitude**: more negative for larger + growth firms (counter-intuitive — easier to arbitrage small stocks?).
- **Methodology**: vector autoregression (VAR) on sentiment + returns.

### Baker-Wurgler 2006

**Paper**: Baker, M., Wurgler, J. (2006). *Investor Sentiment and the Cross-Section of Stock Returns*. Journal of Finance, 61(4), 1645-1680.

- **6 sentiment proxies**:
  1. Closed-end fund discount
  2. NYSE turnover
  3. Number of IPOs
  4. First-day IPO returns
  5. Equity share in new issues
  6. Dividend premium
- **Composite sentiment index**: PCA from 6 proxies.
- **Result**: sentiment affects hard-to-arbitrage stocks most (small, volatile, growth, unprofitable, non-dividend-paying).
- **Sentiment-driven**: high sentiment → overvaluation → low future returns; low sentiment → undervaluation → high future returns.

### Baker-Wurgler 2007

**Paper**: Baker, M., Wurgler, J. (2007). *Investor Sentiment in the Stock Market*. Journal of Economic Perspectives, 21, 129-151.

- **Survey of literature**.
- **Sentiment proxies**: survey-based (AAII, II), market-implied (VIX, put-call, closed-end fund discount), behavioral (IPO volume, retail trading).
- **Comovement**: sentiment proxies correlate, common factor.

### Bollerslev-Tauchen-Zhou 2009

**Paper**: Bollerslev, T., Tauchen, G., Zhou, H. (2009). *Expected Stock Returns and Variance Risk Premia*. Review of Financial Studies.

- **VRP (variance risk premium)** = VIX² - expected realized variance.
- **Predictability**: VRP predicts S&P500 quarterly returns with R² ~10-17%.
- **Edge**: VRP positivo → high future returns (compensation for short-vol risk).
- **Mechanism**: variance risk premium reflects aggregate risk aversion → drives equity premium.

### Bekaert-Hoerova-Lo Duca 2013

**Paper**: Bekaert, G., Hoerova, M., Lo Duca, M. (2013). *Risk, Uncertainty, and Monetary Policy*.

- **VIX decomposition**: VIX² = uncertainty (physical expected variance) + variance risk premium.
- **Result**: VRP = "risk aversion" component. Uncertainty reacts to macro news, VRP reacts to monetary policy.
- **Implication**: VIX è fear index per VRP, non per physical uncertainty alone.

## 2. Market sentiment indicators (free data)

### CNN Fear & Greed Index

- **7 indicators** (equal-weighted):
  1. Stock Price Momentum (S&P 500 vs 125-day MA)
  2. Stock Price Strength (52-week highs/lows)
  3. Stock Price Breadth (Mc Clellan Volume Summation)
  4. Put/Call Options Ratio
  5. Market Volatility (VIX)
  6. Safe Haven Demand (stocks vs bonds 20-day)
  7. Junk Bond Demand (spread vs Treasuries)
- **Scale**: 0-100. Extreme Fear <25, Greed >75.
- **Stats 10y** (2016-2026): avg 49.09, std 19.78, max 82, min 3, days <10 = 16, days >90 = 0.
- **2026-08-13**: value 66 (greed).
- **Edge**: contrarian signal at extremes. Extreme greed → bearish next 1-3m.

### CBOE Put/Call Ratio

- **Free historical archive**: https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/indexpcarchive.csv (CSV, 2007+).
- **Data fields**: date, call volume, put volume, total volume, P/C ratio.
- **2026-08-17**: P/C = 0.79.
- **Edge**: P/C > 1.0 = bearish (puts > calls), P/C < 0.7 = bullish. Extreme readings contrarian.

### AAII Sentiment Survey

- **Since 1987** weekly.
- **Free**: aaii.com/sentimentsurvey (public results every Thursday).
- **2026-08-12**: bull 34.7% (avg 37.5%), neutral 27.4%, bearish 37.9%.
- **Edge**: extreme bull (>50%) → contrarian bearish; extreme bear (>50%) → contrarian bullish. Lead ~6m.
- **Historical data free download**: AAII membership free basic for historical CSV.

### Investors Intelligence (II)

- **Since 1963** weekly.
- **Paywalled** (~$50/mo per historical access).
- **Edge**: bull-bear spread correlates with SP500 lagged (responsive, non-predictive at standard horizons).
- **Free**: weekly summary in Barron's magazine.

## 3. VIX as fear index

### Whaley 2000

**Paper**: Whaley, R. (2000). *The Investor Fear Gauge*. Journal of Portfolio Management.

- **VIX origin**: introduced 1993 by CBOE, redesigned 2003.
- **VIX = risk-neutral expected variance** of S&P500 over next 30 days. Computed from option prices.
- **"Fear index"**: reflects market's expectation of future volatility.
- **Edge**: VIX > 30 = high fear = potential reversal bullish; VIX < 12 = complacency = caution.

### Bekaert-Hoerova 2005

- **VIX² = uncertainty + variance risk premium**.
- **VRP = VIX² - realized variance** → predicts returns.
- **VRP high → investors compensated for short-vol risk → high future returns**.

## 4. Social media sentiment (free)

### StockTwits API

- **Free, no API key** for basic endpoints.
- **Real-time messages**: bullish/bearish cashtag ($AAPL, $TSLA).
- **Endpoints**:
  - `/messages/symbol/{symbol}.json` — recent messages
  - `/symbols/trending/{asset}.json` — trending tickers
  - `/suggest/{q}.json` — search
- **Rate limit**: 200 req/hour anonymous, 4000 req/hour authenticated.
- **Limitation**: NO historical archive free. Real-time only.

### Reddit API

- **Free** (praw library in Python).
- **Subreddits**: r/wallstreetbets, r/investing, r/stocks, r/stockmarket.
- **Top submissions**: contains tickers + sentiment words (bullish/bearish/long/short).
- **Historical**: Pushshift archive (limited 2023+, but Reddit API gives 1000 latest per subreddit).

### ApeWisdom

- **Free no API key**. https://apewisdom.io/api.
- **Tracks Reddit mentions** by ticker. Real-time + 24h stats.
- **Trending tickers**: most mentioned in r/wallstreetbets.

### Twitter API (paywalled)

- **Free tier**: $100/mo Basic, 10k tweets/mese read.
- **Alternatives**: Nitter (defunct 2024), web scraper (rate-limited), StockTwits as proxy.

## 5. Cap summary

**Edge reale e free**:
- Brown-Cliff sentiment (1-3y predictability) — free via AAII + closed-end fund discount
- Baker-Wurgler composite — replicable with PCA + free proxies
- CNN Fear&Greed — free scraper (chrome-devtools-mcp)
- CBOE P/C ratio — free CSV historical archive
- AAII survey — free weekly + basic membership for historical
- VIX VRP — already in Lane D backtest
- StockTwits — free real-time

**Edge debole o paywalled**:
- Investors Intelligence — paywalled
- Twitter API — paywalled ($100/mo)
- Bloomberg sentiment — paywalled

**Edge too long-horizon**:
- Brown-Cliff 1-3y orizzonti — slow signal
- Baker-Wurgler sentiment regime — multi-year cycles
