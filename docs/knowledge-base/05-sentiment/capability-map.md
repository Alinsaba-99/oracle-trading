# 05 Sentiment — Capability Map per Oracle

> Cosa costruire in Oracle (edge > 0.5 + free data + stack esistente).

## ✅ Già in Oracle

| Capability | File | Note |
|---|---|---|
| VIX loader (FRED + yfinance fallback) | `analytics/macro/fred.py:FREDClient` + `lane_d_vrp_backtest.py:_load_vix` | VIXCLS series, 1990+ |
| VRP backtester (Lane D) | `analytics/strategy/lane_d_vrp_backtest.py` | Sharpe -0.08 storico, edge assente nella implementazione attuale. Da fixare con regime filter (BL-OPC-9) |
| AI Analyst Swarm SentimentAnalyst | `analytics/ai_analysts/sentiment.py` | RSS + transformers NLP. Inaffidabile per backtesting (vedi `2026-08-16-ai-analyst-swarm-renaissance-pattern`) |

## 🔨 P1 — Implementare prossimo (edge forte + free data)

### BL-KB-38: CNN Fear&Greed Index adapter
- **Perché**: free $0, contrarian signal at extremes, maintained 2011+.
- **Cosa**: `analytics/sentiment/cnn_fg.py:CNNFearGreedAdapter` con:
  - Scrape https://money.cnn.com/data/fear-and-greed/ via curl_cffi o chrome-devtools-mcp
  - Parse HTML → extract current value + 7 sub-indicators
  - Historical scraper per backtest (daily 2011-2026)
- **Output**: dict { date, fg_value, sub_indicators }.
- **Tempo**: ~2-3 giorni.

### BL-KB-39: CBOE put/call ratio adapter
- **Perché**: free CSV direct download, weekly/monthly backtest data 2007+.
- **Cosa**: `analytics/sentiment/cboe_pc.py:CBOEPutCallAdapter` con:
  - Download https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/indexpcarchive.csv
  - Parse CSV → Polars DataFrame with columns: date, call_vol, put_vol, total_vol, pc_ratio
  - Cache su `data/sentiment/cboe/`
- **Output**: daily P/C ratio + 5d/20d MA.
- **Tempo**: ~1-2 giorni.

### BL-KB-40: AAII sentiment survey scraper
- **Perché**: free weekly since 1987, contrarian signal 6m horizon.
- **Cosa**: `analytics/sentiment/aaii.py:AAIIAdapter` con:
  - Scrape https://www.aaii.com/sentimentsurvey (HTML)
  - Free basic membership per historical CSV
  - Output: weekly bull/bear/neutral %
- **Tempo**: ~2-3 giorni.

### BL-KB-41: Baker-Wurgler composite sentiment index
- **Perché**: seminal sentiment factor, free monthly data 1960+.
- **Cosa**: `analytics/sentiment/baker_wurgler.py:BakerWurglerAdapter` con:
  - Download from https://sites.google.com/a/nyu.edu/jeffreywurgler/data
  - 6 proxies: closed-end fund discount, NYSE turnover, IPO volume, IPO first-day returns, equity share, dividend premium
  - PCA composite replicating BW methodology
- **Output**: monthly sentiment index.
- **Tempo**: ~2-3 giorni.

### BL-KB-42: StockTwits adapter
- **Perché**: free real-time bullish/bearish cashtag messages.
- **Cosa**: `analytics/sentiment/stocktwits.py:StockTwitsAdapter` con:
  - GET https://api.stocktwits.com/api/2/messages/symbol/{symbol}.json (no auth)
  - Rate limit 200 req/hour anonymous
  - Output: list of recent messages with user sentiment tags
- **Limit**: no historical archive free. Going forward only.
- **Tempo**: ~1-2 giorni.

### BL-KB-43: Reddit PRAW adapter
- **Perché**: free 60 req/min, top submissions da r/wallstreetbets + r/investing.
- **Cosa**: `analytics/sentiment/reddit_adapter.py:RedditAdapter` con:
  - `pip install praw`
  - Subreddits: r/wallstreetbets, r/investing, r/stocks, r/stockmarket, r/CryptoCurrency
  - Extract tickers from submissions + comments via cashtag regex
  - Sentiment via transformers NLP (HuggingFace free)
- **Output**: list of (timestamp, ticker, sentiment_score, mention_count).
- **Tempo**: ~2-3 giorni.

### BL-KB-44: Google Trends adapter
- **Perché**: retail attention proxy, free 2004+.
- **Cosa**: `analytics/sentiment/trends.py:GoogleTrendsAdapter` con:
  - `pip install pytrends`
  - Track ticker search interest over time
  - Output: weekly search interest + 4w MA
- **Tempo**: ~1-2 giorni.

## 🔨 P2 — Implementare per signal combos

### BL-KB-45: Composite sentiment signal
- **Perché**: combinare 7 sentiment signals → stronger composite.
- **Cosa**: `analytics/strategy/catalog/sentiment.py:CompositeSentimentSignal` con:
  - Inputs: CNN F&G (BL-KB-38) + CBOE P/C (BL-KB-39) + AAII (BL-KB-40) + BW (BL-KB-41) + VIX + VRP (already in Lane D) + StockTwits (BL-KB-42) + Reddit (BL-KB-43) + Google Trends (BL-KB-44)
  - Normalize each to [0, 1] (extreme fear → 0, extreme greed → 1)
  - Equal-weighted or PCA-weighted composite
- **Output**: composite sentiment score [0, 1] per asset.
- **Tempo**: ~3-5 giorni (depends on BL-KB-38..44).

### BL-KB-46: Sentiment regime classifier
- **Perché**: regime overlay per Lane B sizing.
- **Cosa**: `analytics/strategy/catalog/sentiment.py:SentimentRegimeClassifier` con:
  - 3 regimes: extreme fear (composite < 0.2), neutral (0.2-0.8), extreme greed (> 0.8)
  - Size Lane B: 1.5x in extreme fear, 0.5x in extreme greed, 1.0x neutral
- **Tempo**: ~2-3 giorni.

## 🔨 P3 — VRP followup

### BL-KB-47: Lane D VRP with regime filter
- **Perché**: Lane D backtest storico Sharpe -0.08 = edge assente (vedi `lane-d-vrp-backtest-real-2026-08-17`). Da fixare.
- **Cosa**: estendere `lane_d_vrp_backtest.py:VRPBacktestConfig` con:
  - `regime_filter_vix_min: float = 30` (no trade when VIX < 30)
  - `term_structure_inverted_check: bool = True`
  - `tail_cap_premium_multiple: float = 3.0` (stop loss assoluto su collateral)
- **Target**: Sharpe > 0.5 con regime filter.
- **Tempo**: ~3-5 giorni.

## 🔄 P4 — Deferrire

- **Investors Intelligence** paywalled — skip.
- **Twitter API** paywalled — skip, StockTwits è proxy.
- **NewsAPI** paywalled — vedi dominio 07 news automated.

## ❌ Hard-blocked (paywalled)

- Investors Intelligence historical — $50/mo
- Twitter API Basic — $100/mo
- Bloomberg sentiment — $24k/yr
- RavenPack — $5k+/yr
- Dataminr — enterprise

## Sequenza implementazione raccomandata

```
BL-KB-38 CNN F&G adapter        (~2-3g) ← scraper
BL-KB-39 CBOE P/C adapter       (~1-2g) ← CSV direct download
BL-KB-40 AAII survey scraper    (~2-3g) ← free basic membership
BL-KB-41 Baker-Wurgler index    (~2-3g) ← PCA composite
BL-KB-42 StockTwits adapter    (~1-2g) ← real-time only
BL-KB-43 Reddit PRAW adapter   (~2-3g) ← + transformers NLP
BL-KB-44 Google Trends adapter (~1-2g) ← retail attention
BL-KB-45 Composite sentiment   (~3-5g) ← ensemble
BL-KB-46 Sentiment regime      (~2-3g) ← Lane B overlay
BL-KB-47 Lane D VRP fix        (~3-5g) ← regime filter
```

Totale: **~19-31 giorni** per completare P1+P2 sentiment.

## Prossimo step

Dopo P1+P2:
1. Composite sentiment signal su 2010-2025 backtest → Sharpe target > 0.5
2. Sentiment regime classifier overlay su Lane B Composite → test alpha +5%/yr
3. Lane D VRP con regime filter → Sharpe > 0.5 (vs -0.08 attuale)
4. DSR/PBO/CPCV validation (dominio 03)
