# VALUTAZIONE D — Data Source (il lotto critico per R2/R3)

> Lotto 4 di 6. La domanda qui è concreta: il catalogo fornisce dati per
> ogni asset class e ogni tipo di segnale, a $0? Ogni voce: cosa dà,
> quanto costa davvero, limiti, autenticazione, PIT.

## D.1 — Stocks & General (17 voci + 9 extra del catalogo)

### 1. FilingFirehose (jaablon/filingfirehose-python)
- **Metadati**: 1★ · push 2026-05-10 · MIT
- **Dà**: SEC EDGAR JSON API con 8-K classificate per body-text (cattura
  item sepolti: 7.3% dei filing 8.01 flaggati), 13D/G con 21+ activist
  filer taggati, rilevazione ATM S-3/424B5. REST + MCP + SDK + GH Action.
- **Costo**: free tier 72h di ritardo; archivio completo da $29/mese (FUORI).
- **Limiti**: il free tier a 72h è inutilizzabile per segnali (il valore
  di un 8-K è nei minuti).
- **Verdetto**: il tier free è un teaser; per R3 SEC serve edgartools
  (diretto EDGAR, zero ritardo). Registrato.

### 2. AltData Atlas (altdataatlas.com)
- **Dà**: directory di alternative data provider.
- **Verdetto**: meta-fonte; utile come indice in Stage-2.

### 3. polymarket-canary-tape (HuggingFace)
- **Dà**: tape microstruttura prediction markets: 271M trade CEX + 61M
  eventi order-book Polymarket (apr-lug 2026), finestra overlap per
  latency studies. **CC-BY-4.0, gratis**.
- **Costo**: $0.
- **Verdetto**: dataset unico nel suo genere; fuori tesi attuale ma
  gratuito e scaricabile; registrato come opzione.

### 4. OpenBB Terminal (OpenBB-finance/OpenBB)
- **Metadati**: 72.132★ · push 2026-07-30 · licenza NOASSERTION · Py
- **Dà**: aggregatore research: equity, crypto, FX, macro, opzioni, news,
  insider, ETF — decine di fonti free integrate.
- **Costo**: $0 la piattaforma ( alcune fonti richiedono key proprie).
- **Limiti**: licenza da leggere (NOASSERTION); è una piattaforma completa,
  non una libreria dati — integrarla = adottare un mondo.
- **Verdetto**: candidato come **mappa delle fonti** (quali esistono, come
  si chiamano le API) più che come dipendenza.

### 5. FinanceDatabase (JerBouma/FinanceDatabase)
- **Metadati**: 8.369★ · push 2026-08-16 · MIT
- **Dà**: database di 300.000+ simboli (equity, ETF, fondi, indici, FX,
  crypto, money markets) con metadati.
- **Costo**: $0, no key.
- **Verdetto**: candidato P1 per R2 (universe/simboli). MIT, attivo.

### 6. FinanceToolkit (JerBouma/FinanceToolkit)
- **Metadati**: 5.248★ · push 2026-08-18 · MIT
- **Dà**: 200+ metriche (80+ ratios, 30+ TA, 20+ risk, 50+ macro) da FMP,
  Yahoo, OECD, GMBD.
- **Costo**: dipende da Financial Modeling Prep → free tier limitato
  (250 req/giorno storicamente), oltre è $29+/mese.
- **Verdetto**: la parte Yahoo/OECD è $0; la parte FMP è freemium.
  Adozione condizionata alla verifica del free tier reale.

### 7. AkShare (akfamily/akshare)
- **Metadati**: 22.163★ · push 2026-08-21 · MIT
- **Dà**: dati finanziari cinesi (A-share, bond, futures CN).
- **Verdetto**: fuori mercato (CN). Registrato.

### 8. GetAstockFactors (hugo2046)
- **Metadati**: 98★ · push 2021-10 · licenza NONE
- **Verdetto**: CN, licenza assente, fermo. No.

### 9. findatapy (cuemacro/findatapy)
- **Metadati**: 2.107★ · push 2026-07-02 · Apache-2.0
- **Dà**: API unificata per scaricare da Quandl, Bloomberg, Yahoo, ecc.
- **Costo**: dipende dalle fonti (Bloomberg/Quandl = paid).
- **Verdetto**: abstraction layer; utile solo per le fonti free che già
  usiamo (Yahoo). Hold.

### 10. FXMacroData (fxmacrodata/fxmacrodata)
- **Metadati**: 9★ · push 2026-07-15 · MIT
- **Dà**: macro FX real-time (banche centrali, tassi, inflazione, GDP 18
  valute) + MCP + OAuth.
- **Costo**: free tier da verificare.
- **Verdetto**: piccolo, recente; probe necessario prima dell'uso.

### 11. yfinance (ranaroussi/yfinance)
- **Metadati**: 25.045★ · push 2026-08-20 · Apache-2.0
- **Stato**: già installato e in ADR-020. Keep. R2 daily.

### 12. pandas-datareader (pydata/pandas-datareader)
- **Metadati**: 3.236★ · push 2026-07-21 · licenza NOASSERTION
- **Dà**: FRED, World Bank, OECD, Stooq…
- **Verdetto**: FRED già nostro via PIT vintage; Stooq è il valore
  aggiunto. Hold.

### 13. Wallstreet (mcdallas/wallstreet)
- **Metadati**: 1.689★ · push 2024-07 · MIT
- **Dà**: opzioni real-time + stock.
- **Limiti**: fermo 2024; scraping Yahoo opzioni fragile.
- **Verdetto**: pista opzioni eventualmente; hold.

### 14. TuShare (wadatu/tushare)
- **Metadati**: 15.357★ · push 2024-03 · BSD-3-Clause
- **Verdetto**: CN. No.

### 15. Investpy (alvarobartt/investpy)
- **Metadati**: 1.851★ · push 2026-04 · MIT
- **Dà**: scraping Investing.com.
- **Limiti**: storicamente rotto più volte (Investing.com blocca);
  fragile per costruzione.
- **Verdetto**: rischio alto di rottura; no.

### 16. awesome-data (akfamily/awesome-data)
- **Metadati**: 658★ · push 2025-03 · MIT
- **Verdetto**: altra lista di fonti — materiale Stage-2.

### 17. FundamentalAnalysis (JerBouma/FundamentalAnalysis)
- **Dà**: 20y profili, statements, ratios 20.000+ company.
- **Costo**: dipende da FMP (freemium come Toolkit).
- **Verdetto**: stesso discorso FinanceToolkit.

### 18-21. FinancialData.net / StockAInsights / Insider Alerts / goMacro.ai
- **Dà**: SaaS vari (stock data API, AI filings extraction, Form 4
  alerts, calendario macro AI).
- **Verdetto**: tutti commerciali; fuori $0 salvo free tier esplicito
  dichiarato. Registrati come dati.

### 22. Chart Library MCP (grahammccain/chart-library-mcp)
- **Metadati**: 20★ · push 2026-06-10 · MIT
- **Dà**: ricerca similarità pattern storici: 24M+ embedding (pgvector),
  15K+ simboli, 10 anni minute-bar, forward returns inclusi.
- **Costo**: dichiarato free/MCP; da verificare hosting.
- **Verdetto**: idea potente (pattern → forward returns precalcolati);
  20★ = non validato; probe.

### 23. Helium MCP ⚠️
- **Metadati**: **GONE_404** — repo `connerlambden/helium-mcp` sparito
  (probe 2026-08-22). Il catalogo lo elenca DUE volte (17.1 e 17.2).
- **Verdetto**: il catalogo linka un progetto morto; il sito potrebbe
  esistere ancora ma il repo no. Registrato.

### 24. The Stall (thebrierfox/the-stall)
- **Metadati**: 7★ · push 2026-08-16 · MIT
- **Dà**: 191 capability dati mercati, pay-per-call via x402 (USDC su Base).
- **Verdetto**: pagamento crypto per chiamata = contro spirito $0
  prevedibile. No.

### 25. AlphaAI (alphai.io)
- **Dà**: news relevance-scored (GDELT + SEC EDGAR): score 1-10, categoria,
  impact per ticker; Form 4 come eventi strutturati. Free: 20 req/min,
  100/giorno, no card. MCP incluso.
- **Costo**: $0 nel free tier.
- **Verdetto**: candidato probe per R3 news/sentiment; il limite
  100/giorno condiziona l'uso (solo produzione, non backtest storico).

### 26. BDE Score (hbhqq9/bde-score)
- **Metadati**: 3★ · push 2026-08-01 · licenza NOASSERTION
- **Verdetto**: minuscolo; no.

## D.2 — Alternative (6 voci)

### 1. Adanos Market Sentiment API
- **Dà**: sentiment cross-platform (Reddit, X, Polymarket) per equity.
- **Costo**: tier da verificare.
- **Verdetto**: probe; claim da verificare.

### 2. 13F Insight
- **Dà**: tracking 13F istituzionali, 5.000+ manager, alerts.
- **Costo**: free tier dichiarato; resto SaaS.
- **Verdetto**: la stessa informazione è gratis via EDGAR/edgartools;
  valore aggiunto = UX. No per noi.

### 3. SEC EDGAR Filing API (SEC-API-io/sec-api-python)
- **Metadati**: 315★ · push 2026-04 · MIT (il client) — ma il SERVIZIO è
  a pagamento (free trial limitato).
- **Verdetto**: il client è MIT ma il backend è commerciale → no;
  EDGAR diretto è gratis.

### 4. edgartools (dgunning/edgartools) ⭐
- **Metadati**: 2.600★ · push 2026-08-22 · MIT
- **Dà**: SEC EDGAR completo: fundamentals, 13F, insider (Form 4), 8-K,
  corporate events. Direttamente da EDGAR = $0, no key, PIT per
  costruzione (filing date). MCP incluso.
- **Verdetto**: **il candidato principale per R3 equity fundamental/
  institutional**. MIT, attivo (push oggi).

### 5. AlphaSMO (alphasmo/alphasmo-tools)
- **Metadati**: 2★ · push 2026-08-12 · MIT
- **Dà**: 13F + Form 4 + segnale "smart money convergence" (dove sia
  istituzioni che insider comprano). Free anonymous tier, no signup.
- **Verdetto**: neonato ma l'idea (convergence insider+institutional) è
  un'ipotesi EF pronta; probe.

### 6. CongressionalStockBrain
- **Dà**: STOCK Act disclosures → segnali (800+ lawmakers, 50K+ trade).
- **Costo**: free tier dichiarato.
- **Verdetto**: ipotesi "seguire il congresso" nota in letteratura;
  dati free se confermati → probe Stage-2.

## D.3 — Crypto (16 voci)

### 1. cryptofeed (bmoscon/cryptofeed) ⭐
- **Metadati**: 2.882★ · push 2026-08-10 · licenza **NOASSERTION** ⚠️
- **Dà**: feed handler WS normalizzato per 20+ exchange: trades, book,
  funding, liquidations, ticker, open interest.
- **Verdetto**: candidato principale per R16 crypto going-forward;
  **la licenza va letta prima di ogni adozione** (il probe non la
  classifica).

### 2. orderflow (focus1691 → ora tiagosiebler/orderflow)
- **Metadati**: il repo si è spostato: `tiagosiebler/orderflow` 80★ ·
  push 2025-03 · MIT · TS/NestJS/TimescaleDB.
- **Dà**: footprint candles real-time da WS trade data multi-exchange.
- **Verdetto**: redirect registrato; MIT; rilevante per pista footprint.

### 3. Agent Gateway
- **Dà**: prezzi real-time 500+ token via Hyperliquid, no key.
- **Verdetto**: minuscolo; no.

### 4. tessera-api (tesseralytics/python-client)
- **Metadati**: 2★ · push 2026-07-13 · **GPL-3.0** ⚠️
- **Dà**: OHLCV arricchito order-flow, funding, positioning da trade
  Hyperliquid grezzi; lettura in Polars/DuckDB.
- **Verdetto**: GPL sul client; il DATO è il valore; probe sul servizio.

### 5. CoinPaprika
- **Dà**: prezzi, volumi, market cap, OHLCV, exchange data 12.000+ coin.
  **No key, 20.000 chiamate/mese free**.
- **Verdetto**: candidato per metadati/universe crypto (R2).

### 6. DexPaprika
- **Dà**: DEX/DeFi: pool, token, OHLCV, trade history, 36 chain, 230+
  DEX. **No key, 200.000 req/mese free**.
- **Verdetto**: candidato per on-chain/DeFi (R3).

### 7. PreReason (PreReason/mcp)
- **Metadati**: 5★ · push 2026-08-19 · MIT
- **Dà**: briefing pre-analizzati BTC+macro (17 contesti: Fed balance
  sheet, M2, yields, hashrate, correlation SPY/QQQ/VXX/UUP) con trend,
  confidence, percentile, regime.
- **Verdetto**: minuscolo; idea di contesto macro pre-digerito; probe.

### 8. sharpe.ai
- **Dà**: funding rates, opzioni, arbitraggio, narrative, listing, news
  crypto. Endpoints pubblici senza key obbligatoria.
- **Verdetto**: probe; condizioni free da verificare.

### 9. Coinugget
- **Dà**: dashboard segnali RSI/price action.
- **Verdetto**: consumer; no.

### 10. Microverse Systems ⭐
- **Dà**: **L2 order book real-time da 21 exchange, WebSocket gratis,
  historical replay, sub-ms latency** (anche in crypto_focus.md).
- **Costo**: dichiarato free; limiti da verificare.
- **Verdetto**: l'UNICA fonte L2 multi-exchange free del catalogo.
  Se i limiti reggono, sblocca l'intera pista microstruttura (R3/R8)
  che altrimenti è paywalled. **Probe prioritario.**

### 11. Market Posture Daily
- **Dà**: trend/regime/relative-strength giornaliero ~90 crypto +
  equity/ETF, cointegration pair screener. Free terminal + JSON.
- **Verdetto**: probe; dati regime già nostri ma il confronto è utile.

### 12. BitBank
- **Dà**: forecasting ML crypto.
- **Verdetto**: 🟠 claim predittivi non verificabili; no.

### 13. AgentServices (vbkotecha/agentservices-api)
- **Metadati**: 1★ · push 2026-08-21 · Apache-2.0
- **Dà**: 54 servizi/97 endpoint/37 MCP tools, pagamento x402 USDC.
- **Verdetto**: pay-per-call crypto; no.

### 14. WealthVille
- **Dà**: scoring pool DeFi LP (68.800 Solana pool + 575 EVM), verdetto
  ENTER/HOLD/EXIT, **track record 30-giorni pubblico miss-inclusive**.
- **Costo**: no key.
- **Verdetto**: l'onestà del track record pubblico è notevole; fuori
  tesi (LP scoring) ma registrato come metodo.

### 15. Shingou ⭐ (metodo)
- **Dà**: sentiment orario + eventi typed per 30 coppie crypto; ogni
  bucket hash-committed in log pubblico append-only (PIT verificabile,
  mai riscritto); **pubblica backtest negativi** (hit rate ≈ coin flip,
  IC residuo ≈ 0). Free 1.000 req/giorno.
- **Verdetto**: come fonte dati è una delle tante; come **metodo** è il
  gold standard dell'onestà (log verificabile + risultati negativi
  pubblici). Da imitare. Repo log: shingou-io/shingou-signal-log,
  push OGGI.

### 16. 0xArchive
- **Dà**: Hyperliquid + Lighter order-level depth, funding, OI, replay,
  qualità dati. REST/WS/MCP.
- **Verdetto**: probe; condizioni free da verificare.

## D.4 — Prediction Markets (8 voci)

| Voce | Metadati | Dà | Verdetto |
|---|---|---|---|
| Parsec (parsecular/parsec-mcp) | 0★ · NONE | dati+execution PM multi-exchange | neonato, no licenza |
| ProfitPlay (jarvismaximum-hue) | 7★ · MIT | arena AI previsioni BTC/ETH/SOL | curiosità |
| pykalshi (ArshKA/kalshi-client) | 120★ · MIT | client Kalshi completo (WS, pandas) | il più serio del gruppo |
| TurbineFi | web | build/backtest PM strategies | SaaS |
| TBD Predict (ego-protocol) | 1★ · MIT | PM Solana opinioni | no |
| PolyMind | web | alerts Polymarket multi-AI | 🟠 claims |
| marketlens (marketlenstrade) | 25★ · MIT | **L2 tick Polymarket da 2026-03** + backtester queue/latency; free tier poi $39/mese | l'unico dato L2 PM storico; freemium |
| Live Tennis API | 190★ · MIT | feed tennis per PM (1968-2022 archivio) | nicchia sportiva |

**Verdetto sezione**: canale non prioritario; pykalshi è l'unico client
serio se mai si aprisse; marketlens ha un free tier reale.

## D.5 — Matrice dati: cosa copre cosa

| Esigenza dati | Copertura catalogo $0 | Gap |
|---|---|---|
| OHLCV equity daily | yfinance, Stooq (via pdr), FinanceDatabase | ✅ |
| OHLCV equity intraday | **NESSUNA fonte free nel catalogo** | 🔴 gap vero |
| Fundamental/SEC | edgartools, EDGAR diretto | ✅ |
| News/sentiment | AlphaAI (100/day), Shingou (crypto) | ⚠️ limitato per backtest storico |
| Macro PIT | FXMacroData (probe), FRED (nostro) | ✅ via FRED |
| Crypto OHLCV | Binance Vision (nostro), CoinPaprika | ✅ |
| Crypto funding/liq | Binance Vision (nostro), sharpe.ai | ✅ |
| L2 order book | **Microverse (free, probe)** | 🟡 condizionato al probe |
| DEX/DeFi | DexPaprika | ✅ |
| Futures intraday storico | **NESSUNA fonte free nel catalogo** | 🔴 gap vero |
| Opzioni (dati) | **NESSUNA** (solo pricing libs) | 🔴 gap vero |
| Insider/13F | edgartools, AlphaSMO | ✅ |

**I 3 gap veri del catalogo** (equity intraday, futures intraday storico,
opzioni) coincidono con ciò che normalmente è a pagamento — nessun
catalogo OSS può colmarli; vanno dichiarati come limiti strutturali del
greenfield.

**Prossimo lotto**: E = Broker APIs + Quant Shops + Resources + Relevant
Projects + crypto_focus residuo.
