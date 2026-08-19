# Dominio 05 — Sentiment / Fear&Greed / VIX

> Knowledge base Oracle — studio approfondito 2026-08-17 via Tavily API.

## Sintesi esecutiva

L'analisi del sentiment ha **edge documentato** ma distribuito su livelli eterogenei:

1. **Brown-Cliff 2005**: sentiment predice future stock returns a 1-3y orizzonti. Sentiment indicatori (II survey, closed-end fund discount, ARMS index, IPO volume) hanno coefficienti negativi (high sentiment → low future returns).
2. **Baker-Wurgler 2006**: sentiment index da 6 proxies (closed-end fund discount, NYSE turnover, IPO volume, IPO first-day returns, equity share in new issues, dividend premium). **Edge forte su small, volatile, growth stocks** (hard to arbitrage).
3. **CNN Fear&Greed Index** (2011-): 7 indicatori equal-weighted, scale 0-100. **2026-08-13 = 66 (greed)**. Stats 10y: avg 49, std 20, days below 10 = 16, days above 90 = 0.
4. **CBOE put/call ratio** free historical archive CSV (2007+). **2026-08-17 = 0.79**. High P/C = bearish sentiment, low P/C = bullish.
5. **AAII Sentiment Survey** weekly since 1987, individual investors bull/bear/neutral. **2026-08-12 = 34.7% bull** (avg 37.5%). Contrarian signal.
6. **Investors Intelligence** weekly advisor sentiment. Bull-bear spread correlates with SP500 (lagging, not predictive).
7. **VIX as fear index** (Whaley 2000): VIX = risk-neutral expected variance S&P500. Reflects both physical expected volatility + variance risk premium.
8. **Bollerslev-Tauchen-Zhou 2009**: variance risk premium (VRP = VIX² - realized variance) predice stock returns. Seminal predictability paper.
9. **StockTwits API free**: bullish/bearish cashtag messages, no API key, real-time. Reddit + ApeWisdom anche free.

**Cap to build Oracle**:
1. CNN Fear&Greed index scraper (chrome-devtools-mcp o curl_cffi)
2. CBOE put/call ratio historical adapter (CSV direct download)
3. AAII sentiment survey scraper (weekly)
4. VIX VRP calculator (Lane D già ha VRP backtester)
5. StockTwits + Reddit sentiment adapter (free)

**Hard gaps**:
- Investor's Intelligence paywalled (~$50/mo)
- Twitter API paywalled ($100/mo+)
- Bloomberg sentiment paywalled

Vedi [literature.md](literature.md), [data-audit.md](data-audit.md), [edge.md](edge.md), [capability-map.md](capability-map.md).
