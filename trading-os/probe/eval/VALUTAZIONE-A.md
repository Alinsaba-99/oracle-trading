# VALUTAZIONE A — Backtest & Execution Frameworks

> Lotto 1 di 6: tutte le voci delle sezioni *Backtest + live* (event-driven,
> vector-based, crypto-focus, ML/RL) del catalogo awesome-systematic-trading.
> Nessuna esclusione: ogni voce riceve la sua scheda. Metadati da
> `metadata.tsv` (probe GitHub 2026-08-22, stelle/push/licenza).
> Requisiti R1-R20 in `trading-os/probe/REQUIREMENTS.md`.

## Trovati del probe che cambiano il catalogo

1. **Hummingbot**: il catalogo linka `CoinAlpha/hummingbot` (214★, fermo
   2025) — slug STALE. Il progetto si è spostato in **`hummingbot/hummingbot`**
   (19.538★, push 2026-08-22, Apache-2.0, attivissimo).
2. **ib_insync**: `erdewit/ib_insync` è **archived** (2024). Il fork vivo è
   **`ib-api-reloaded/ib_async`** (1.716★, push 2026-08-19, BSD-2-Clause).
3. **alphalens** (sezione analitica, anticipato): il fork linkato dal
   catalogo (wangzhe3224, 4★, fermo 2023) non è quello giusto; il mantenuto
   è **`stefan-jansen/alphalens`** (631★, push 2025-12, Apache-2.0).
4. **pandas-ta**: repo originale **cancellato da GitHub** (404). Successore
   comunitario: `xgboosted/pandas-ta-classic` (420★).
5. **cryptofeed**: licenza NOASSERTION — da leggere il LICENSE a mano.

---

## A.1 — Event-driven frameworks (26 voci)

### 1. the0 (alexanderwanyoike/the0)
- **Metadati**: 389★ · push 2026-08-13 · Apache-2.0 · TS/Rust/C++/Py multi
- **Copre**: R7 (execution engine), R16, R17
- **Cosa fa**: execution engine self-hosted; ogni bot gira in container
  isolato; "no framework imposed — your bot is just normal code".
- **Forza**: isolamento per bot = bel modello operativo; attivo.
- **Limiti**: giovane (389★), niente backtest, solo execution.
- **Costo**: $0 (self-hosted, docker).
- **Per adottare**: serve un backtester a fianco; valutare solo se si
  sceglie un'architettura "bot-in-container".

### 2. aat (AsyncAlgoTrading/aat)
- **Metadati**: 829★ · push 2026-07-27 · Apache-2.0 · C++/Py
- **Copre**: R7, R13 (live multi-exchange), R16
- **Cosa fa**: event-driven async, accelerazione C++ opzionale, live
  cross-exchange.
- **Forza**: licenza pulita, attivo, disegno modulare.
- **Limiti**: community piccola; sovrapposto a nautilus.
- **Costo**: $0.
- **Per adottare**: confrontare con nautilus su uno stesso caso d'uso
  prima di sceglierlo.

### 3. barter-rs (barter-rs/barter-rs)
- **Metadati**: 2.237★ · push 2026-08-20 · MIT · Rust
- **Copre**: R7, R13, R16
- **Cosa fa**: framework Rust event-driven live+backtest con motore
  "near-identical" tra i due.
- **Forza**: MIT, attivo, parità backtest/live nativa (cosa rara).
- **Limiti**: Rust = altro linguaggio nel progetto.
- **Costo**: $0.
- **Per adottare**: solo se si apre una pista Rust; altrimenti pattern
  da copiare (parità engine backtest/live).

### 4. bt (pmorissette/bt)
- **Metadati**: 2.964★ · push 2026-08-07 · MIT · Py
- **Copre**: R6 (albero di strategie), R12
- **Cosa fa**: backtest flessibile basato su Strategy Tree (Algo).
- **Forza**: MIT, ancora mantenuto, stesso autore di ffn → sinergia.
- **Limiti**: sovrapposto a vectorbt per lo sweep; non event-driven.
- **Costo**: $0.
- **Per adottare**: valutare come layer di composizione strategie sopra
  i segnali; non come motore unico.

### 5. BetterQuant (byrnexu/betterquant)
- **Metadati**: 230★ · push 2024-06 · licenza NONE · C++
- **Copre**: R7, R13 (mercati CN)
- **Limiti**: licenza assente (bloccante per adozione), fermo dal 2024,
  mercato cinese.
- **Costo**: $0 ma inutilizzabile legalmente senza licenza.
- **Verdetto registrato**: non adottabile; tenere a catalogo come dato.

### 6. Botvana (featherenvy/botvana)
- **Metadati**: 249★ · push 2022-05 · AGPL-3.0 · Rust
- **Limiti**: fermo da 4 anni, AGPL (copyleft forte), Rust.
- **Costo**: $0.
- **Verdetto registrato**: morto; zero urgenza.

### 7. backtrader (mementum/backtrader)
- **Metadati**: 22.917★ · push 2024-08 · GPL-3.0 · Py
- **Copre**: R7, R13 (alcuni broker)
- **Forza**: enorme base di utenti, documentazione immensa, pattern
  API diventati standard de facto.
- **Limiti**: manutenzione minima dal 2024; GPL-3.0 (se distribuito);
  lento rispetto a vectorbt.
- **Costo**: $0.
- **Per adottare**: utile come riferimento API; adozione reale solo per
  confronto. La sua eredità vive in backtesting.py.

### 8. backtesting.py (kernc/backtesting.py)
- **Metadati**: 8.874★ · push 2026-08-05 · AGPL-3.0 · Py
- **Copre**: R6/R7 ibrido, R18 (plot interattivo)
- **Forza**: già usato nel corpus MoonDev (Harvard-RBI); ottimizzatore
  integrato; attivo.
- **Limiti**: AGPL-3.0 → se il greenfield diventa prodotto distribuito,
  copyleft; single-asset oriented.
- **Costo**: $0.
- **Per adottare**: ottimo prototipatore; la licenza va decisa come
  politica di progetto (uso interno vs distribuzione).

### 9. FlashFunk (HFQR/FlashFunk)
- **Metadati**: 142★ · push 2025-03 · licenza NONE · Rust
- **Limiti**: licenza assente, fermo, nicchia.
- **Verdetto registrato**: non adottabile (licenza).

### 10. QuantFabric (QuantFabric/QuantFabric)
- **Metadati**: 258★ · push 2026-08-07 · licenza NOASSERTION · C++
- **Limiti**: mercati CN (CFFEX/ZCE/DCE/SHFE/SSE/SZSE), C++, licenza da leggere.
- **Coprirebbe**: R7/R13 per CN — fuori tesi.
- **Verdetto registrato**: fuori mercato.

### 11. gobacktest (gobacktest/gobacktest)
- **Metadati**: 241★ · **archived** · push 2023-10 · MIT · Go
- **Verdetto registrato**: morto (archived), Go fuori perimetro.

### 12. Hikyuu (fasiondog/hikyuu)
- **Metadati**: 3.458★ · push 2026-08-21 · Apache-2.0 · C++/Py
- **Limiti**: ecosistema CN (docs cinesi, dati CN).
- **Forza**: attivo, Apache-2.0, C++/Python ibrido.
- **Verdetto registrato**: fuori mercato (CN), ma esempio di framework
  C++ core + Py API.

### 13. Investing Algorithm Framework (coding-kitties)
- **Metadati**: 1.710★ · push 2026-08-20 · Apache-2.0 · Py
- **Copre**: R7, R13, R17 (deploy)
- **Forza**: attivo, Apache-2.0, orientato al deploy di bot.
- **Limiti**: medio-small community; backtest basilare.
- **Per adottare**: valutare per la fase "bot deploy" se non coperta da altri.

### 14. lumibot (Lumiwealth/lumibot)
- **Metadati**: 1.952★ · push 2026-08-21 · GPL-3.0 · Py
- **Copre**: R7, R13 (Alpaca/IBKR/crypto)
- **Limiti**: catalogo stesso dice "a bit slow"; GPL.
- **Costo**: $0.
- **Per adottare**: solo se serve il suo parco broker; altrimenti ridondante.

### 15. nautilus_trader (nautechsystems)
- **Metadati**: 27.149★ · push 2026-08-22 · LGPL-3.0 · Rust/Py
- **Copre**: R7, R8 (parziale, tick), R13, R16, R17
- **Forza**: il più completo event-driven open-source: Rust core,
  adapter multi-exchange (incluso Hyperliquid), parità backtest/live,
  attivamente sviluppato (push oggi).
- **Limiti**: LGPL-3.0 (dynamic linking ok); curva di apprendimento alta;
  certification cost stimata in mesi (già registrato da Oracle).
- **Costo**: $0.
- **Per adottare**: candidato forte come motore unico event-driven;
  va fatta una proof-of-concept su un caso crypto + uno equity.

### 16. PyBroker (edtechre/pybroker)
- **Metadati**: 3.511★ · push 2026-08-21 · licenza NOASSERTION · Py
- **Copre**: R7 + R10 (ML-native)
- **Forza**: backtest con ML integrato, bootstrap/Walkforward built-in.
- **Limiti**: licenza da verificare (NOASSERTION); Oracle ce l'ha già
  come extra interno.
- **Costo**: $0.
- **Per adottare**: già parzialmente in casa; verificare licenza.

### 17. QuantConnect Lean (QuantConnect/Lean)
- **Metadati**: 21.296★ · push 2026-08-21 · Apache-2.0 · C#
- **Copre**: R7, R13, R16 — in C#/.NET
- **Forza**: industria-standard, dati multi-asset modellati benissimo
  (corporate actions, splits, opzioni), Apache-2.0.
- **Limiti**: C# = altro stack; cloud features legate alla piattaforma
  QuantConnect (ma il motore è standalone).
- **Costo**: $0 self-hosted (il cloud è paid).
- **Per adottare**: se si vuole il massimo realismo dati equity; costo
  di stack alto.

### 18. QUANTAXIS (yutiansut/QUANTAXIS)
- **Metadati**: 11.027★ · push 2026-02 · MIT · Py/Rust
- **Limiti**: ecosistema CN; push rallentato.
- **Verdetto registrato**: fuori mercato.

### 19. Rqalpha (ricequant/rqalpha)
- **Metadati**: 6.710★ · push 2026-08-21 · licenza NOASSERTION · Py
- **Limiti**: CN (A-share), licenza da leggere.
- **Verdetto registrato**: fuori mercato.

### 20. quanttrader (letianzj/quanttrader)
- **Metadati**: 765★ · push 2024-06 · Apache-2.0 · Py
- **Limiti**: fermo dal 2024; duplicato di backtesting.py per ammissione
  del catalogo.
- **Verdetto registrato**: riferimento morto.

### 21. qf-lib (quarkfin/qf-lib)
- **Metadati**: 954★ · push 2026-08-05 · Apache-2.0 · Py
- **Copre**: R7, R12, R13
- **Forza**: modulare, attivo, Apache-2.0, tool analisi qualità inclusi.
- **Per adottare**: candidato per la cassetta attrezzi analisi/rischio
  se non coperta da quantstats/pyfolio.

### 22. sdoosa-algo-trade-python
- **Metadati**: 650★ · push 2023-09 · licenza NONE · Py
- **Verdetto registrato**: didattico per newbie; nessun valore ingegneristico.

### 23. vnpy (vnpy/vnpy)
- **Metadati**: 44.671★ · push 2026-08-10 · MIT · Py
- **Copre**: R7, R13, R16, R18 (GUI)
- **Forza**: enorme, MIT, attivo, piattaforma completa con GUI.
- **Limiti**: focus CN (CTP futures, A-share); docs prevalentemente cinesi.
- **Verdetto registrato**: fuori mercato principale, ma i suoi adapter
  gateway (20+ exchange/broker) sono materiale di studio.

### 24. WonderTrader (wondertrader/wondertrader)
- **Metadati**: 6.284★ · push 2025-09 · MIT · C++/Py
- **Limiti**: CN.
- **Verdetto registrato**: fuori mercato.

### 25. zvt (zvtvz/zvt)
- **Metadati**: 4.281★ · push 2026-07 · MIT · Py
- **Limiti**: CN (A-share data-centric).
- **Verdetto registrato**: fuori mercato; il suo data-abstraction layer
  è un pattern leggibile.

### 26. zipline (quantopian/zipline)
- **Metadati**: 20.056★ · push 2024-02 · Apache-2.0 · Py
- **Stato**: Quantopian morta 2020; repo in manutenzione minima.
- **Coprirebbe**: R7 equity.
- **Nota**: fork comunitari (zipline-reloaded) esistono ma non sono nel
  catalogo; il catalogo linka l'originale.
- **Verdetto registrato**: morto; valore storico (ha definito il concetto
  di pipeline API).

### 27. PandoraTrader (pegasusTrader/PandoraTrader)
- **Metadati**: 1.459★ · push 2025-10 · licenza NONE · C++
- **Verdetto registrato**: CTP/CN, licenza assente → non adottabile.

### 28. hftbacktest (nkaz001/hftbacktest) ⭐
- **Metadati**: 4.379★ · push 2025-12 · MIT · Rust/Py (numba)
- **Copre**: R8 (UNICO nel catalogo), R14
- **Forza**: modeling realistico di queue position, latency, full L2
  tick; MIT; citato nella letteratura HFT.
- **Limiti**: ultimo push 8 mesi fa (da monitorare); richiede dati L2
  veri (Microverse/tectonicdb) per esprimersi.
- **Costo**: $0.
- **Per adottare**: è il candidato naturale quando si apre la pista
  microstruttura; prima va verificata la disponibilità di L2 storico.

### 29. flashalpha-fill-simulator (FlashAlpha-lab)
- **Metadati**: 3★ · push 2026-08-20 · MIT · Py
- **Copre**: R14 (fill opzioni)
- **Forza**: zero dipendenze, engine-agnostic, recente.
- **Limiti**: 3★ = neonato, non validato da nessuno.
- **Per adottare**: solo se pista opzioni; prima leggere il codice.

### 30. Cipher (nanvel/cipher-bt)
- **Metadati**: 19★ · push 2025-08 · MIT · Py
- **Copre**: R7 (position adjustment)
- **Limiti**: minuscolo.
- **Verdetto registrato**: riferimento di nicchia.

### 31. Gunbot Quant (GuntharDeNiro/gunbot-quant)
- **Metadati**: 54★ · push 2025-08 · MIT · JS
- **Copre**: R6 + R18 (UI screener)
- **Limiti**: piccolo, JS.
- **Verdetto registrato**: nota marginale.

### 32. PythonTradingFramework (JustinGuese)
- **Metadati**: 35★ · push 2026-08-18 · MIT · Py
- **Copre**: R7, R17 (K8s, cron)
- **Limiti**: 35★, usa Yahoo come dati.
- **Per adottare**: nessuno; il pattern K8s+CronJob è l'unico spunto.

### 33. Tradingview Screener API (jmargieh/tradingview-screener)
- **Metadati**: 14★ · push 2026-04 · MIT · TS
- **Copre**: R2 (13K campi TV), R3 parziale
- **Limiti**: dipende da TradingView non ufficiale (stabilità a rischio);
  TS; legale da verificare.
- **Per adottare**: solo se serve lo screening TV; rischio ToS dichiarato.

---

## A.2 — Vector-based frameworks (8 voci)

### 1. QTradeX (squidKid-deluxe/QTradeX-Algo-Trading-SDK)
- **Metadati**: 84★ · push 2026-07-30 · licenza NOASSERTION · Py
- **Limiti**: licenza da leggere; piccolo.
- **Verdetto registrato**: in attesa di licenza.

### 2. FinHack (FinHackCN/finhack)
- **Metadati**: 1.131★ · push 2026-08-19 · licenza NOASSERTION · Py
- **Coprirebbe**: R1-R7 full pipeline (factor mining, ML, live)
- **Limiti**: CN; licenza da leggere.
- **Verdetto registrato**: fuori mercato; il disegno end-to-end è
  interessante da leggere.

### 3. pysystemtrade (robcarver17, pst-group/pysystemtrade)
- **Metadati**: 3.471★ · push 2026-07-18 · GPL-3.0 · Py
- **Copre**: R5, R7, R11, R12, R13 (IBKR)
- **Forza**: implementazione completa del libro "Systematic Trading" di
  Rob Carver: position sizing, forecasting, portfolio, costi.
  Trasparenza unica (l'autore pubblica i suoi trade reali).
- **Limiti**: GPL-3.0; codebase datata nello stile; orientato futures.
- **Costo**: $0.
- **Per adottare**: materiale di studio P0 per sizing/forecast
  combination; adozione codice solo per GPL-compatibilità.

### 4. finmarketpy (cuemacro/finmarketpy)
- **Metadati**: 3.805★ · push 2026-04 · Apache-2.0 · Py
- **Copre**: R12 (analisi mercati), R6
- **Forza**: Apache-2.0, attivo, analisi backtest+market.
- **Per adottare**: candidata come libreria di analisi; verificare API.

### 5. vectorbt (polakowo/vectorbt)
- **Metadati**: 8.755★ · push 2026-08-02 · licenza NOASSERTION · Py/numba
- **Copre**: R6 (migliaia di strategie in secondi), R12
- **Nota**: vectorbt PRO (commerciale) esiste ma la versione OSS basta.
  Licenza "NOASSERTION" = custom, da leggere prima di ogni adozione.
- **Costo**: $0 (OSS).
- **Per adottare**: già adottato da Oracle; nel greenfield è il default
  per sweep; licenza da riverificare.

### 6. fund-strategy (SunshowerC/fund-strategy)
- **Metadati**: 935★ · push 2023-01 · licenza NONE · TS
- **Verdetto registrato**: CN, fermo, licenza assente → non adottabile.

### 7. fastquant (enzoampil/fastquant)
- **Metadati**: 1.754★ · push 2023-09 · MIT · Py
- **Limiti**: fermo dal 2023; wrapper 3-linee sopra backtrader.
- **Verdetto registrato**: morto; valore zero.

### 8. Manifold-BT (manifoldbt/manifoldbt)
- **Metadati**: 28★ · push 2026-08-22 · licenza NOASSERTION · Py/Rust
- **Copre**: R6, R9 (walk-forward + Monte Carlo built-in), R14
- **Forza**: Rust-powered, fill realistici, centinaia di migliaia di
  combinazioni in secondi, push OGGI.
- **Limiti**: 28★ = neonato; licenza da leggere; claim prestazionali da
  verificare (🟠).
- **Per adottare**: da tenere d'occhio; prova su un benchmark nostro
  prima di qualsiasi uso.

---

## A.3 — Crypto-focus frameworks (16 voci)

### 1. basana (gbeced/basana)
- **Metadati**: 857★ · push 2026-08-09 · licenza NOASSERTION · Py
- **Copre**: R7/R13 crypto
- **Forza**: async event-driven, attivo, stessa scuola di PyAlgoTrade.
- **Per adottare**: licenza da leggere; candidato leggero.

### 2. c-binance-future-quant (Melelery)
- **Metadati**: 857★ · push 2025-04 · licenza NONE · Py
- **Verdetto registrato**: licenza assente → non adottabile; riferimento
  architettura Binance futures.

### 3. triangular-arbitrage2 (zlq4863947)
- **Metadati**: 249★ · push 2021-10 · licenza NONE · TS
- **Verdetto registrato**: fermo, licenza assente, arbitraggio triangolare
  saturato → non adottabile.

### 4. bTrader (gabriel-milan/btrader)
- **Metadati**: 332★ · **archived** · push 2021-05 · GPL-3.0 · Rust
- **Verdetto registrato**: archived 2021 → morto.

### 5. crypto-crawler-rs (crypto-crawler/crypto-crawler-rs)
- **Metadati**: 266★ · push 2023-03 · Apache-2.0 · Rust
- **Copre**: R3/R16 (orderbook+trade crawl multi-exchange)
- **Limiti**: fermo da 3 anni (ma il codice può essere comunque utile).
- **Per adottare**: se si apre pista L2 e non si usa Microverse/cryptofeed.

### 6. cryptotrader-core (monomadic)
- **Metadati**: 25★ · push 2019-06 · licenza NONE · Rust
- **Verdetto registrato**: morto 2019, licenza assente.

### 7. openlimits (nash-io/openlimits)
- **Metadati**: 322★ · push 2022-07 · BSD-2-Clause · Rust
- **Limiti**: Nash è fallita; repo fermo 2022.
- **Verdetto registrato**: morto; ccxt copre lo stesso spazio in Python.

### 8. Freqtrade (freqtrade/freqtrade)
- **Metadati**: 53.502★ · push 2026-08-21 · GPL-3.0 · Py
- **Copre**: R3 (dati exchange), R5, R6, R7, R10 (ML optimize), R13,
  R17 (Telegram), R18 (web UI FreqUI)
- **Forza**: il più completo crypto bot OSS: backtest, hyperopt,
  dry-run, pairlists, protezione, web UI, Telegram, edge positioning.
- **Limiti**: GPL-3.0; crypto-only; opinionato.
- **Costo**: $0.
- **Per adottare**: candidato come "palestra" crypto rapida; la
  convivenza con nautilus va definita (freqtrade = ricerca crypto,
  nautilus = execution seria?).

### 9. Hummingbot (hummingbot/hummingbot) ⭐
- **Metadati**: 19.538★ · push 2026-08-22 · Apache-2.0 · Py/Cython
- **Copre**: R7 (market making), R13, R16, R17
- **Forza**: Apache-2.0 (licenza migliore tra i crypto bot),
  market-making + arbitraggio, gateway CEX/DEX, fondazione con
  governance, attivissimo.
- **Limiti**: specializzato MM/arb, non generalista; pesante.
- **Costo**: $0.
- **Per adottare**: unico candidato serio se si apre la pista
  market-making; Apache-2.0 lo rende integrabile senza vincoli.

### 10. Jesse (jesse-ai/jesse)
- **Metadati**: 8.353★ · push 2026-08-19 · MIT · Py
- **Copre**: R5, R6, R7, R10, R13, R18
- **Forza**: MIT, API pulita, research-first, multi-timeframe,
  optimization; attivo.
- **Limiti**: alcune feature avanzate sono nel cloud paid (verify!).
- **Costo**: $0 OSS; cloud opzionale.
- **Per adottare**: candidato forte per ricerca crypto; verificare
  cosa è OSS vs paid.

### 11. OctoBot (Drakkar-Software/OctoBot)
- **Metadati**: 6.448★ · push 2026-08-21 · GPL-3.0 · Py/Cython
- **Copre**: R5, R7, R13, R18 (web UI)
- **Limiti**: GPL; tentacles model = estensioni; alcuni servizi cloud paid.
- **Per adottare**: valutare solo se la sua UI/community interessa.

### 12. DeepAlpha (stefanoviana/deepalpha)
- **Metadati**: 41★ · push 2026-05 · MIT · Py
- **Claim**: "70.9% walk-forward accuracy" 🟠 NON VERIFICATO.
- **Verdetto registrato**: claim non auditato; 41★; leggere codice prima
  di qualsiasi considerazione.

### 13. Kelp (stellar/kelp)
- **Metadati**: 1.127★ · **archived** · push 2023-11 · licenza NOASSERTION · Go
- **Verdetto registrato**: archived → morto.

### 14. exc (Nouzan/exc)
- **Metadati**: 43★ · push 2024-08 · MIT · Rust
- **Verdetto registrato**: astrazione exchange Rust; nicchia.

### 15. MyCryptoBot (diogomatoschaves)
- **Metadati**: 141★ · push 2026-06 · licenza NONE · Py/JS
- **Verdetto registrato**: licenza assente → non adottabile.

### 16. godzilla.dev (godzilla-foundation/godzilla-community)
- **Metadati**: 371★ · push 2026-08-11 · Apache-2.0 · C++/Py
- **Copre**: R7 (funding arb + MM low-latency), R13
- **Forza**: Apache-2.0, attivo, nicchia funding-rate arb.
- **Per adottare**: se pista funding arb; community version limitata
  vs paid (verificare).

---

## A.4 — ML/RL focused (3 voci)

### 1. ml-quant-trading (initial-d/ml-quant-trading)
- **Metadati**: 77★ · push 2026-08-22 · MIT · Py/PyTorch
- **Copre**: R5 (213 fattori mask-aware), R10, R12 (bias correction)
- **Forza**: push oggi; factor library ampia; bias correction esplicita.
- **Limiti**: 77★ = poco validato dalla community.
- **Per adottare**: materiale mining per la lista fattori.

### 2. TradingGym (Yvictor/TradingGym)
- **Metadati**: 1.910★ · push 2024-02 · MIT · Py
- **Copre**: R10 (gym env)
- **Limiti**: fermo 2024.
- **Verdetto registrato**: riferimento per RL-env; gymnasium moderno lo
  sostituisce.

### 3. DQL trading bot (pskrunner14/trading-bot)
- **Metadati**: 1.174★ · push 2023-12 · MIT · Py
- **Verdetto registrato**: didattico; nessun valore.

---

## Riepilogo lotto A

| Categoria | Voci | Migliori candidati (per valutazione, non decisione) |
|---|---|---|
| Event-driven | 33 | nautilus_trader, hftbacktest, backtesting.py (AGPL), aat, Investing Algorithm Framework |
| Vector | 8 | vectorbt (già nostro), pysystemtrade (studio), Manifold-BT (osservato) |
| Crypto | 16 | Hummingbot (Apache-2.0), Freqtrade, Jesse (MIT), godzilla |
| ML/RL | 3 | ml-quant-trading (mining fattori) |
| Morti/archived | 9 | zipline, gobacktest, bTrader, Kelp, fastquant, openlimits, cryptotrader-core, quanttrader, triangular-arbitrage2 |
| Licenza assente/bloccante | 8 | BetterQuant, FlashFunk, fund-strategy, c-binance, MyCryptoBot, PandoraTrader, sdoosa, czsc-CN |

**Prossimo lotto**: B = Alpha Collections + Basic Components (26 voci).
