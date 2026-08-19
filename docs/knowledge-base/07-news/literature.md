# 07 News automated — Literature Review

> Fonti: Tavily API (advanced) 2026-08-17. URL verified.

## 1. News sentiment academic

### Tetlock 2007

**Paper**: Tetlock, P. (2007). *Giving Content to Investor Sentiment: The Role of Media in the Stock Market*. Journal of Finance, 62, 1139-1168.

- **Source**: Wall Street Journal "Abreast of the Market" column, 1996-2004.
- **Methodology**: textual analysis con Harvard IV-4 psychosocial dictionary.
- **Result**: high media pessimism predicts:
  - Downward pressure on market prices
  - High trading volume
  - Subsequent reversion to fundamentals
- **Edge**: ~+1-2% weekly on pessimism extreme → contrarian buy.
- **Caveat**: edge concentrated in negative sentiment; positive sentiment weaker signal.

### Garcia 2013

**Paper**: Garcia, D. (2013). *Sentiment during Recessions*. Journal of Finance.

- **Source**: Dow Jones Newswires 1905-2005 (100 years).
- **Result**: negative sentiment stronger predictor in recessions (countercyclical risk premium).
- **Edge**: news sentiment predicts returns more reliably in recessions than expansions.
- **Implication**: news signal regime-dependent.

### Antweiler-Frank 2004

**Paper**: Antweiler, W., Frank, M. (2004). *Is All That Talk Just Noise? The Information Content of Internet Stock Message Boards*. Journal of Finance.

- **Source**: 1.5M messages on Yahoo! Finance + RagingBull message boards.
- **Result**: sentiment predicts market volatility (non returns directly).
- **Edge**: small but statistically significant.
- **Conclusion**: internet discussions are not just noise — contain information.

### Da et al 2015

**Paper**: Da, Z., Engelberg, J., Gao, P. (2015). *The Sum of All Fears: The Aggregate Investor Sentiment Index and the Stock Market*.

- **Methodology**: Google search volume for "recession", "unemployment", "bankruptcy".
- **Result**: high search volume → short-term return reversals + temporary volatility increase.
- **Edge**: contrarian bearish signal on extreme search volume.

### Chen et al 2013

**Paper**: Chen, H., De, P., Hu, Y., Hwang, B. (2013). *Wisdom of Crowds: The Value of Stock Opinions Transmitted Through Social Media*.

- **Source**: Seeking Alpha articles + comments 2005-2012.
- **Result**: sentiment of articles predicts future returns. Comments contain more information than articles.
- **Edge**: contrarian, low sentiment articles → outperformance.
- **Limitation**: only Seeking Alpha, not generalizable to all social media.

### Jegadeesh-Wu 2012

**Paper**: Jegadeesh, N., Wu, D. (2012). *Words matter: The informational content of IPO prospectuses*.

- **Methodology**: textual analysis of IPO 10-K + prospectus.
- **Result**: tone of qualitative info predicts future IPO returns.
- **Edge**: optimistic prospectuses → low future returns (underperformance).

### Heston-La-Poncin 2015

**Paper**: Heston, S., Sinha, N. (2017). *News vs. Sentiment: Predicting Stock Returns from News Stories*.

- **Source**: Reuters news 2003-2011.
- **Result**: news content predicts future returns at 1-2 day horizon. Sentiment alone weaker than content features.
- **Edge**: short-term, decays fast.

## 2. Free data sources

### RSS feeds (financial news)

- **Reuters RSS**: https://www.reuters.com/arc/outboundfeeds/v3/financial-rss/
- **CNBC RSS**: https://www.cnbc.com/id/100003114/device/rss/rss.html
- **Bloomberg RSS** (limited free articles): https://www.bloomberg.com/feed
- **Seeking Alpha RSS**: https://seekingalpha.com/market_currents.xml
- **Motley Fool RSS**: https://www.fool.com/feeds/index.aspx
- **MarketBeat RSS**: https://www.marketbeat.com/rss/
- **Benzinga RSS**: https://www.benzinga.com/feed
- **Fortune RSS**: https://fortune.com/feed
- **Nasdaq RSS**: https://www.nasdaq.com/rss
- **FT Alphaville RSS**: https://www.ft.com/alphaville?format=rss
- **The Big Picture (Barry Ritholtz)**: https://ritholtz.com/feed/
- **Abnormal Returns**: https://abnormalreturns.com/feed/
- **Pragmatic Capitalism**: https://www.pragcap.com/feed/
- **Philosophical Economics**: https://www.philosophicaleconomics.com/feed/
- **Klement on Investing**: https://klementoninvesting.substack.com/feed
- **JPMorgan Insights**: https://www.jpmorgan.com/insights/rss
- **Of Dollars and Data (Nick Maggiulli)**: https://ofdollarsanddata.com/feed/

### Reddit API (PRAW)

- `pip install praw`
- Free, 60 req/min anonymous
- Subreddits: r/wallstreetbets, r/investing, r/stocks, r/stockmarket, r/CryptoCurrency, r/forex, r/options
- Top submissions + comments 1000 per subreddit per fetch

### StockTwits API

- Free, no auth for basic endpoints
- 200 req/hour anonymous
- Real-time bullish/bearish cashtag messages
- Endpoints:
  - `/messages/symbol/{symbol}.json`
  - `/symbols/trending/{asset}.json`
  - `/suggest/{q}.json`
- No historical archive free

### Tradestie API (Reddit WSB)

- Free no key
- GET https://tradestie.com/api/v1/apps/reddit (top-50 WSB tickers with bullish/bearish label)
- Daily snapshot

### ApeWisdom API

- Free no key
- https://apewisdom.io/api
- Reddit trending tickers across subreddits
- 24h stats

### SEC EDGAR Full-Text Search API

- Free no key
- 10 req/sec
- `https://efts.sec.gov/LATEST/search-index?q=...&dateRange=...&forms=8-K`
- Search 8-K filings for "earnings release", "merger agreement", "restatement"

### Google Trends (pytrends)

- `pip install pytrends`
- Free, Google account
- Search volume for any keyword 2004+
- Weekly + daily resolution

## 3. Sentiment classifier free

### FinBERT (open-source)

- HuggingFace: `prosuslab/finbert`
- Free, MIT license
- Pre-trained on financial news, accuracy ~98% on Financial PhraseBank
- 3 classes: positive, negative, neutral
- `pip install transformers` + `from transformers import pipeline; nlp = pipeline("sentiment-analysis", model="prosuslab/finbert")`

### SigmaBERT vs FinBERT

- FinBERT trained on financial, more accurate than generic BERT
- vs LLM (glm-5.2, Haiku): FinBERT smaller, faster, but less context-aware

### LLM-based (vsllm via OmniRoute)

- Already used in Oracle AI Analyst Swarm LateralAnalyst + Synthesizer
- Via vsllm/claude-haiku-4-5-20251001 via OmniRoute locale (vedi `vsllm-via-omniroute-llm-provider` memory)
- Free $0

## 4. Cap summary

**Edge reale e free**:
- Tetlock 2007 — RSS feeds + FinBERT sentiment → contrarian signal at extreme pessimism
- Reddit + StockTwits — short-term contrarian on meme stocks
- SEC EDGAR 8-K — event detection (earnings, M&A)
- Google Trends — recession/bankruptcy search volume → contrarian

**Edge decayed**:
- Heston-La-Poncin 2015 short-term news — decayed by HFT (1-2 day horizon hard to capture free)

**Edge paywalled**:
- NewsAPI ($449/mo business) — alternative RSS
- Dataminr (enterprise) — alternative Reddit + RSS
- Twitter API ($100/mo) — alternative StockTwits + Reddit
