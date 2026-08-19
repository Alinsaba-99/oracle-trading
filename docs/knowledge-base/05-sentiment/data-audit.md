# 05 Sentiment — Data Audit (free $0 verified 2026-08-17)

> Regola hard: $0/mo per dati. Vedi ADR-020.

## Fonti sentiment free verificate

| Fonte | Coverage | Format | API Key | Limit | Note |
|---|---|---|---|---|---|
| **CNN Fear & Greed Index** | 2011-2026 daily | HTML scraped | nessuna | rate-limit soft | https://money.cnn.com/data/fear-and-greed/. Free via scraper (chrome-devtools-mcp o curl_cffi) |
| **CBOE Put/Call Ratio historical** | 2007-2026 daily | CSV direct | nessuna | nessuna | https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/indexpcarchive.csv. **Top source** |
| **AAII Sentiment Survey** | 1987-2026 weekly | HTML + CSV (membership) | nessuna (basic free) | free weekly summary | https://www.aaii.com/sentimentsurvey. Historical CSV requires free basic membership |
| **VIX (via FRED)** | 1990-2026 daily | JSON via FRED | `FRED_API_KEY` free | 120 req/min | Series VIXCLS. **USATO in Oracle Lane D** |
| **VIX (via yfinance ^VIX)** | 1990-2026 daily | pandas DataFrame | nessuna | rate-limit | Fallback per FRED. `yf.Ticker("^VIX")` |
| **StockTwits API** | real-time | JSON | nessuna (anon) | 200 req/hour | https://api.stocktwits.com/api/2/messages/symbol/{symbol}.json. Real-time only, no historical archive free |
| **Reddit API (PRAW)** | real-time + 1000 latest per subreddit | JSON | nessuna (anon) | 60 req/min | Subreddits: r/wallstreetbets, r/investing, r/stocks, r/stockmarket |
| **ApeWisdom API** | real-time + 24h | JSON | nessuna | soft limit | https://apewisdom.io/api. Reddit trending tickers |
| **Google Trends** | 2004-2026 weekly | CSV via pytrends | Google account free | rate-limit | `pip install pytrends`. Retail attention proxy |
| **Baker-Wurgler sentiment index (Wurgler website)** | 1960-2025 monthly | Excel | nessuna | NYU Stern website | https://sites.google.com/a/nyu.edu/jeffreywurgler/data |
| **Shiller CAPE (public data)** | 1871-2026 monthly | CSV | nessuna | http://www.econ.yale.edu/~shiller/data.htm | Monthly CAPE + interest rates |

## Capabilities Oracle esistenti

- ✅ `analytics/macro/fred.py:FREDClient` — VIXCLS series
- ✅ `_load_vix` in `lane_d_vrp_backtest.py` — VIX via FRED + yfinance fallback
- ✅ AI Analyst Swarm `SentimentAnalyst` (RSS + transformers NLP) — ma inaffidabile per backtesting (vedi `2026-08-16-ai-analyst-swarm-renaissance-pattern` memory)

## Gap dichiarati

1. **CNN Fear&Greed scraper** NON implementato. TODO BL-KB-38.
2. **CBOE P/C ratio adapter** NON implementato. CSV direct download. TODO BL-KB-39.
3. **AAII survey scraper** NON implementato. Free weekly. TODO BL-KB-40.
4. **Baker-Wurgler composite index** NON implementato. Free CSV monthly from Wurgler website. TODO BL-KB-41.
5. **StockTwits adapter** NON implementato. Free real-time. TODO BL-KB-42.
6. **Reddit PRAW adapter** NON implementato. TODO BL-KB-43.
7. **Google Trends adapter** NON implementato. Retail attention proxy. TODO BL-KB-44.

## Cap da NON usare (paywalled)

| Fonte | Perché esclusa | Alternativa free |
|---|---|---|
| Bloomberg sentiment | $24k/yr | StockTwits + Reddit + AAII |
| Investors Intelligence (historical) | $50/mo | AAII free + StockTwits |
| Twitter API Basic | $100/mo | StockTwits + Reddit + Nitter (defunct) |
| NewsAPI | $449/mo per business | RSS feeds + Tavily (with API) |
| Dataminr | enterprise | Reddit PRAW + StockTwits |
| GDELT Project | free but heavy | 3 billion news events since 1979, free but requires infrastructure |
| Bloomberg Twitter HD | enterprise | StockTwits + Reddit |
| RavenPack | $5k+/yr | Reddit + news RSS |

## Reference data free

- **Baker-Wurgler sentiment data**: https://sites.google.com/a/nyu.edu/jeffreywurgler/data — NYU Stern public
- **Shiller CAPE data**: http://www.econ.yale.edu/~shiller/data.htm — monthly since 1871
- **CBOE data archive**: https://cdn.cboe.com/ — free CSV archives
- **AAII sentiment survey**: https://www.aaii.com/sentimentsurvey — weekly since 1987
