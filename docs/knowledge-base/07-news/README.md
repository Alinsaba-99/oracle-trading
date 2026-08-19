# Dominio 07 — News automated / Reddit

> Knowledge base Oracle — studio approfondito 2026-08-17 via Tavily API.

## Sintesi esecutiva

L'analisi news automatizzata ha **edge documentato** su orizzonti brevi (giorni/settimane), con dati parzialmente free:

1. **Tetlock 2007** — Wall Street Journal "Abreast of the Market" column. Media pessimism predicts downward pressure on market prices, seguito da reversion. Edge ~+1-2% weekly.
2. **Garcia 2013** — extends Tetlock con Dow Jones Newswires. Negative sentiment ha contemporaneous effect su returns. Edge più forte in recessions.
3. **Heston-La-Poncin 2015** — news future returns predictions. Volatility models + news combined.
4. **Antweiler-Frank 2004** — 1.5M internet message board messages. Significativamente predict market volatility (non returns diretti).
5. **Da et al 2015** — Google search volume for "recession", "unemployment", "bankruptcy" predicts short-term return reversals + temporary volatility spike.
6. **Chen et al 2013** — Seeking Alpha articles sentiment predicts stock returns.
7. **Jegadeesh-Wu 2012** — IPO prospectus 10-K textual analysis predicts future returns.

**Free data sources**:
- SEC EDGAR Full-Text Search API (free, no key, 10 req/sec)
- RSS feeds (Fortune, CNBC, Reuters, Bloomberg limited free, Seeking Alpha, Motley Fool, Benzinga, MarketBeat)
- Reddit API (PRAW, 60 req/min, no key anon)
- StockTwits API (200 req/hour anon)
- ApeWisdom API (Reddit trending tickers, free)
- Tradestie API (top-50 WSB tickers bullish/bearish, free no key)
- Google Trends (pytrends, free 2004+)

**Paywalled**:
- Twitter API Basic ($100/mo) — alternative StockTwits + Reddit
- NewsAPI ($449/mo business) — alternative RSS
- Dataminr (enterprise) — alternative Reddit + RSS
- RavenPack ($5k+/yr) — alternative RSS + transformers NLP

**Cap to build Oracle**:
1. RSS aggregator adapter (top 20 financial feeds)
2. SEC EDGAR 8-K event detector (earnings, M&A, restatements)
3. Reddit PRAW adapter (r/wallstreetbets + r/investing + r/stocks)
4. StockTwits adapter (real-time cashtag messages)
5. LLM sentiment classifier (FinBERT free open-source, vs paid LLM)
6. Composite news sentiment signal

Vedi [literature.md](literature.md), [data-audit.md](data-audit.md), [edge.md](edge.md), [capability-map.md](capability-map.md).
