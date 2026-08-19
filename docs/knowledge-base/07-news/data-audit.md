# 07 News automated — Data Audit (free $0 verified 2026-08-17)

> Regola hard: $0/mo per dati. Vedi ADR-020.

## Fonti news free verificate

| Fonte | Coverage | Format | API Key | Limit | Note |
|---|---|---|---|---|---|
| **SEC EDGAR Full-Text Search API** | 2001+ all SEC filings | JSON | nessuna | 10 req/sec | `https://efts.sec.gov/LATEST/search-index?q=...`. Search 8-K/10-K/10-Q by keyword |
| **SEC EDGAR Company Filings API** | 1993+ | JSON | nessuna | 10 req/sec | `https://data.sec.gov/submissions/CIK{cik}.json` |
| **Reddit API (PRAW)** | real-time + 1000 latest per sub | JSON | nessuna (anon) | 60 req/min | `pip install praw`. Subreddits: r/wallstreetbets, r/investing, r/stocks, r/stockmarket, r/CryptoCurrency |
| **StockTwits API** | real-time | JSON | nessuna (anon) | 200 req/hour | `https://api.stocktwits.com/api/2/messages/symbol/{symbol}.json`. No historical archive free |
| **Tradestie API** | WSB top-50 daily | JSON | nessuna | soft limit | `https://tradestie.com/api/v1/apps/reddit`. Bull/bear tags |
| **ApeWisdom API** | Reddit trending 24h | JSON | nessuna | soft limit | `https://apewisdom.io/api`. Reddit-wide ticker mentions |
| **Google Trends (pytrends)** | 2004+ weekly | pandas DataFrame | Google account free | rate-limited | `pip install pytrends`. Search volume for any keyword |
| **RSS feeds (20+ financial news)** | real-time | XML | nessuna | rate-limited | Reuters, CNBC, Bloomberg limited, Seeking Alpha, Motley Fool, MarketBeat, Benzinga, Fortune, FT Alphaville |
| **GDELT Project** | 1979+ global news events | CSV bulk | nessuna | 3 billion events, large | https://www.gdeltproject.org. Heavy infrastructure needed |
| **FinBERT (HuggingFace)** | pre-trained NLP | Python lib | nessuna | GPU recommended | `prosuslab/finbert`. Financial sentiment 98% accuracy |
| **vsllm via OmniRoute (LLM)** | vsllm/claude-haiku-4-5-20251001 | Python lib | PROXY_MANAGED | free tier | Already used in Oracle AI Analyst Swarm |

## RSS feeds top 20

1. Reuters: https://www.reuters.com/arc/outboundfeeds/v3/financial-rss/
2. CNBC: https://www.cnbc.com/id/100003114/device/rss/rss.html
3. Bloomberg (limited): https://www.bloomberg.com/feed
4. Seeking Alpha: https://seekingalpha.com/market_currents.xml
5. Motley Fool: https://www.fool.com/feeds/index.aspx
6. MarketBeat: https://www.marketbeat.com/rss/
7. Benzinga: https://www.benzinga.com/feed
8. Fortune: https://fortune.com/feed
9. Nasdaq: https://www.nasdaq.com/rss
10. FT Alphaville: https://www.ft.com/alphaville?format=rss
11. The Big Picture: https://ritholtz.com/feed/
12. Abnormal Returns: https://abnormalreturns.com/feed/
13. Pragmatic Capitalism: https://www.pragcap.com/feed/
14. Philosophical Economics: https://www.philosophicaleconomics.com/feed/
15. Klement on Investing: https://klementoninvesting.substack.com/feed
16. JPMorgan Insights: https://www.jpmorgan.com/insights/rss
17. Of Dollars and Data: https://ofdollarsanddata.com/feed/
18. Nikkei Asia: https://asia.nikkei.com/rss
19. South China Morning Post Business: https://www.scmp.com/business/feed
20. Business Standard: https://www.business-standard.com/rss/latest.rss

## Capabilities Oracle esistenti

- ✅ `analytics/ai_analysts/sentiment.py:SentimentAnalyst` — RSS scraper + transformers NLP
- ✅ `analytics/ai_analysts/lateral.py` + `synthesizer.py` — LLM via vsllm/OmniRoute

## Gap dichiarati

1. **RSS adapter incomplete** — SentimentAnalyst inesistente su tickers minori (vedi AI swarm 50-ticker run 2026-08-17, 0 articles per ticker). TODO BL-KB-55.
2. **SEC EDGAR 8-K event detector** NON implementato. TODO BL-KB-56.
3. **Reddit PRAW adapter** NON implementato (vedi BL-KB-43 dominio 05). TODO BL-KB-43.
4. **StockTwits adapter** NON implementato (vedi BL-KB-42 dominio 05). TODO BL-KB-42.
5. **FinBERT integration** NON implementato. SentimentAnalyst usa transformers generico. TODO BL-KB-57.
6. **GDELT adapter** NON implementato. Heavy but free. TODO BL-KB-58.

## Cap da NON usare (paywalled)

| Fonte | Perché esclusa | Alternativa free |
|---|---|---|
| NewsAPI business | $449/mo | RSS feeds + SEC EDGAR |
| Dataminr | enterprise | Reddit PRAW + RSS |
| Twitter API Basic | $100/mo | StockTwits + Reddit |
| Bloomberg terminal news | $24k/yr | RSS + CNBC + Reuters |
| Refinitiv news | $1.8k/mo | RSS + SEC EDGAR + GDELT |
| RavenPack | $5k+/yr | RSS + FinBERT |
| Thomson Reuters news | enterprise | RSS + GDELT |
| AlphaSense | enterprise | RSS + SEC EDGAR + LLM via vsllm |

## Reference implementations free

- **FinBERT**: https://huggingface.co/prosuslab/finbert — pre-trained financial sentiment
- **SEC EDGAR docs**: https://www.sec.gov/developer — REST API documentation
- **PRAW**: https://praw.readthedocs.io — Reddit Python wrapper
- **StockTwits API**: https://stocktwits.com/developers/docs — API reference
- **Tradestie API**: https://tradestie.com/api/v1 — WSB top-50 free
- **GDELT Project**: https://www.gdeltproject.org — global news events 1979+
