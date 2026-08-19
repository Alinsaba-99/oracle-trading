# Oracle Knowledge Base — 13 domini di analisi

> Living document. Obiettivo: mappare per ogni dominio la letteratura, le fonti dati free, l'edge plausibile, la capability map (cosa costruire in Oracle).
> Sessioni di studio 2026-08-17+. Ogni dominio = 1 subdirectory + 1 report markdown + memorie collegate.

## Indice domini

| # | Dominio | Status | Priority (edge × free-data) |
|---|---|---|---|
| 01 | [Fundamental](01-fundamental/) | ⏳ In corso | ⭐⭐⭐ (Piotroski/Greenblatt/Lakonishok/Fama-French) |
| 02 | [Macro](02-macro/) | ⏳ Pianificato | ⭐⭐⭐ (FRED/BIS/ECB free, tassi/inflazione/PIL) |
| 03 | [Quant / DSR / PBO](03-quant/) | ⏳ Pianificato | ⭐⭐⭐ (purgedcv MIT free, Bailey López de Prado) |
| 04 | [Order flow / L2 / footprint](04-order-flow/) | ⏳ Pianificato | ⭐ (paywalled ovunque — gap dichiarato) |
| 05 | [Sentiment / Fear&Greed / VIX / put-call](05-sentiment/) | ⏳ Pianificato | ⭐⭐ (CNN/CBOE delayed free) |
| 06 | [Positioning / COT](06-positioning/) | ⏳ Pianificato | ⭐⭐⭐ (CFTC free, Asness/Bhansali paper) |
| 07 | [News automated / Reddit / Twitter](07-news/) | ⏳ Pianificato | ⭐⭐ (Reddit free, Twitter API paywalled) |
| 08 | [Intermarket / 4 asset-class correlations](08-intermarket/) | ⏳ Pianificato | ⭐⭐ (yfinance free, Murphy textbook) |
| 09 | [Cyclical / Elliott / Gann / Hurst](09-cyclical/) | ⏳ Pianificato | ⭐ (matematica pura, edge contestato) |
| 10 | [Seasonal / pattern ricorrenti](10-seasonal/) | ⏳ Pianificato | ⭐⭐ (yfinance free, Sell in May ecc.) |
| 11 | [On-chain / crypto](11-onchain/) | ⏳ Pianificato | ⭐⭐⭐ (Etherscan/Btcscan raw free, Glassnode paywalled) |
| 12 | [Behavioral / bubble / panic](12-behavioral/) | ⏳ Pianificato | ⭐⭐ (Shiller CAPE free, Kahneman/Taleb) |
| 13 | [Meta-synthesis / Renaissance pattern](13-meta-synthesis/) | ⏳ Pianificato | ⭐⭐⭐ (combo 12 domini → 1 decisione) |

## Metodologia di studio (per dominio)

1. **Literature review** → Tavily (AI-optimized, legge contenuti) + Exa (neural search per paper SSRN/ArXiv) + SearXNG (aggregatore multi-engine senza quota). Output: sezione "Letteratura" con citazioni.
2. **Free data audit** → per ogni fonte citata nei paper: è free $0? SecEDGAR/SimFin/FRED/CFTC/CBOE delayed/CNN Fear&Greed/Reddit API/Etherscan raw. Escludere Polygon/Tiingo/Databento/Bloomberg/Refinitiv (vedi `no-paid-financial-data` memory).
3. **Edge plausibility** → consenso accademico. Dove c'è disaccordo. Effetto size documentato. In-sample vs OOS. Decay. Regime dipendenza.
4. **Capability map** → cosa costruire prima in Oracle (edge > 0.5 + free data + stack esistente), cosa deferrire, cosa è hard-blocked (es. L2 order flow paywalled). Link a backlog items BL-KB-NNN.

## Output per dominio

- `docs/knowledge-base/NN-dominio/README.md` — indice del dominio + sintesi
- `docs/knowledge-base/NN-dominio/literature.md` — paper + blog + libri con citazioni
- `docs/knowledge-base/NN-dominio/data-audit.md` — fonti verificate free vs paywalled
- `docs/knowledge-base/NN-dominio/edge.md` — edge plausibility + regime + decay
- `docs/knowledge-base/NN-dominio/capability-map.md` — implementazione Oracle
- Memoria yith_archive persistente per citazioni veloci nelle sessioni future

## Search MCP server disponibili 2026-08-17

Vedi [memory `search-mcp-servers-2026-08-17`](../../../.claude/projects/-home-alin--repos-oracle-trading/memory/search-mcp-servers-2026-08-17.md):
- **Tavily** (1000/mese) — AI-optimized, legge contenuti non solo snippet
- **Brave Search** (2000/mese) — web search generica
- **Exa** (1000/mese) — neural search per paper accademici
- **SearXNG** (illimitato, docker `oracle-searxng` porta 8888) — aggregatore multi-engine
- **DuckDuckGo** (illimitato) — fallback zero-key

Costo totale: **$0/mo**. Quota combinata ~3-5k query/mese.
