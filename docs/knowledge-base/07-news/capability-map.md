# 07 News automated — Capability Map per Oracle

> Cosa costruire in Oracle (edge > 0.5 + free data + stack esistente).

## ✅ Già in Oracle

| Capability | File | Note |
|---|---|---|
| RSS scraper + transformers NLP | `analytics/ai_analysts/sentiment.py:SentimentAnalyst` | Inaffidabile per backtesting (0 articles per ticker su 50-ticker run — vedi `ai-swarm-historical-50tickers-2026-08-17`) |
| LLM via vsllm/OmniRoute | `analytics/ai_analysts/lateral.py` + `synthesizer.py` | Free, vsllm/claude-haiku-4-5-20251001. Reliable per Synthesizer, Lateral 503 in run 50-ticker |

## 🔨 P1 — Implementare prossimo (edge forte + free data)

### BL-KB-55: RSS aggregator adapter
- **Perché**: free 20+ financial RSS feeds, Tetlock 2007 methodology.
- **Cosa**: estendere `analytics/ai_analysts/sentiment.py:SentimentAnalyst` con:
  - Feed list: Reuters, CNBC, Bloomberg limited, Seeking Alpha, Motley Fool, MarketBeat, Benzinga, Fortune, FT Alphaville
  - Parse XML → extract title + body + timestamp
  - Ticker extraction via cashtag regex ($AAPL, $TSLA) + NER
  - Cache su `data/news/rss/{date}_{source}_{id}.json`
- **Tempo**: ~2-3 giorni.
- **Costo**: $0.

### BL-KB-56: SEC EDGAR 8-K event detector
- **Perché**: free $0, real-time earnings/M&A event detection.
- **Cosa**: `analytics/news/sec_edgar_events.py:SECEventDetector` con:
  - Subscribe to EDGAR RSS feed (https://www.sec.gov/rss/filings.xml)
  - FTS API per keyword search: "earnings release", "merger agreement", "restatement", "going concern"
  - Parse 8-K body → extract event type + date + ticker
- **Output**: list of (timestamp, ticker, event_type, severity_score).
- **Tempo**: ~2-3 giorni.

### BL-KB-57: FinBERT sentiment classifier
- **Perché**: pre-trained financial NLP, 98% accuracy on Financial PhraseBank. Meglio di transformers generico.
- **Cosa**: `pip install transformers`, modello `prosuslab/finbert`
  - `analytics/news/finbert_classifier.py:FinBERTClassifier` con `classify(text) -> {positive, negative, neutral}`
  - Replace generic transformers in SentimentAnalyst
- **Tempo**: ~1-2 giorni.

### BL-KB-42: StockTwits adapter (già in dominio 05)
- **Perché**: free real-time bullish/bearish cashtag.
- **Cosa**: vedere `docs/knowledge-base/05-sentiment/capability-map.md` BL-KB-42.

### BL-KB-43: Reddit PRAW adapter (già in dominio 05)
- **Perché**: free 60 req/min, r/wallstreetbets + r/investing.
- **Cosa**: vedere `docs/knowledge-base/05-sentiment/capability-map.md` BL-KB-43.

### BL-KB-58: GDELT adapter (optional)
- **Perché**: free 3 billion global news events 1979+, but heavy infrastructure.
- **Cosa**: `analytics/news/gdelt_adapter.py:GDELTAdapter` con:
  - Download CSV daily updates (http://data.gdeltproject.org/gdeltv2/masterfilelist.txt)
  - Filter by topic (theme = "ECON_...", "MILITARY_...")
  - Output: list of (timestamp, country, theme, actor)
- **Tempo**: ~3-5 giorni. Opzionale (heavy).

## 🔨 P2 — Implementare per signal combos

### BL-KB-59: Composite news sentiment signal
- **Perché**: combinare RSS + EDGAR 8-K + Reddit + StockTwits + Google Trends → stronger composite.
- **Cosa**: `analytics/strategy/catalog/news_sentiment.py:CompositeNewsSentimentSignal` con:
  - Inputs: RSS (BL-KB-55) + EDGAR 8-K (BL-KB-56) + Reddit (BL-KB-43) + StockTwits (BL-KB-42) + Google Trends (BL-KB-44 dominio 05)
  - FinBERT classifier (BL-KB-57)
  - Normalize to z-score (5y lookback)
  - Output: composite sentiment [-3, +3]
- **Tempo**: ~3-5 giorni.

### BL-KB-60: News event anomaly signal
- **Perché**: PEAD + earnings surprise + M&A → +2-5% on 1-5d horizon.
- **Cosa**: `analytics/strategy/catalog/news_sentiment.py:NewsEventSignal` con:
  - Detect 8-K events: earnings release, M&A, restatement
  - PEAD: long high-surprise + high-F-Score tickers (vedi dominio 01 BL-KB-04)
  - M&A: long target companies post-announcement
  - Restatement: short firms with "going concern" 8-K
- **Tempo**: ~3-5 giorni.

## 🔄 P3 — Deferrire

- **LLM via vsllm/OmniRoute per sentiment** — già usato in AI Analyst Swarm. Per news sentiment real-time FinBERT è sufficiente.
- **GDELT heavy integration** — quando budget compute è disponibile.

## ❌ Hard-blocked (paywalled)

- NewsAPI business — $449/mo
- Dataminr — enterprise
- Twitter API Basic — $100/mo
- Bloomberg terminal news — $24k/yr
- Refinitiv news — $1.8k/mo
- RavenPack — $5k+/yr

## Sequenza implementazione raccomandata

```
BL-KB-55 RSS aggregator         (~2-3g) ← 20+ feeds
BL-KB-56 SEC EDGAR 8-K events   (~2-3g) ← FTS API
BL-KB-57 FinBERT classifier    (~1-2g) ← pre-trained
BL-KB-43 Reddit PRAW           (~2-3g) ← dominio 05
BL-KB-42 StockTwits            (~1-2g) ← dominio 05
BL-KB-44 Google Trends         (~1-2g) ← dominio 05
BL-KB-58 GDELT adapter          (~3-5g) ← optional
BL-KB-59 Composite news signal (~3-5g) ← ensemble
BL-KB-60 News event anomaly    (~3-5g) ← PEAD + M&A
```

Totale: **~16-28 giorni** per completare P1+P2 news automated.

## Prossimo step

Dopo P1+P2:
1. Backtest composite news signal su 2010-2025 → target Sharpe > 0.5
2. Event anomaly signal → +2-5% post 8-K + PEAD
3. DSR/PBO/CPCV validation (dominio 03)
4. Combina con Lane B (fundamental) per ensemble
