# VALUTAZIONE B — Alpha Collections + Analytic Tools

> Lotto 2 di 6. Stesse regole del lotto A: nessuna esclusione, ogni voce
> riceve la scheda; metadati dal probe GitHub 2026-08-22; requisiti R1-R20.

## B.1 — General Alpha (11 voci)

### 1. je-suis-tm/quant-trading
- **Metadati**: 10.604★ · push 2026-06-20 · Apache-2.0 · Py
- **Copre**: R5 (15+ strategie pronte: VIX calc, CTA, Monte Carlo, options
  straddle, London Breakout, pair trading, Heikin-Ashi, Dual Thrust…)
- **Forza**: Apache-2.0, attivo, codice leggibile, ampio spettro.
- **Limiti**: strategie "da blog" senza validazione rigorosa → ogni
  strategia è un'ipotesi da preregistrare, non un edge.
- **Costo**: $0.
- **Per adottare**: materiale mining Stage-2 (ogni strategia → entry
  registry con origine=letteratura).

### 2. analyzingalpha (leosmigel)
- **Metadati**: 525★ · push 2023-08 · licenza NONE · Py
- **Limiti**: fermo 2023, licenza assente.
- **Verdetto registrato**: riferimento per il libro omonimo; codice non
  adottabile per licenza.

### 3. Finance (shashankvemuri/Finance)
- **Metadati**: 4.180★ · push 2026-03-26 · MIT · Py
- **Copre**: R5 (150+ programmi quant).
- **Forza**: MIT, aggiornato 2026.
- **Limiti**: raccolta di snippet, non framework; qualità eterogenea.
- **Per adottare**: materiale mining.

### 4. ThetaGang (brndnmtthws/thetagang)
- **Metadati**: 2.709★ · push 2026-08-22 · **AGPL-3.0** · Py
- **Copre**: R13 (IBKR), R7 (opzioni "the wheel").
- **Forza**: push OGGI; strategia venduta-premi documentatissima; IBKR.
- **Limiti**: AGPL; opzioni = pista non aperta; serve dati opzioni.
- **Costo**: $0 (serve IBKR account per uso reale).
- **Per adottare**: solo se si apre la pista opzioni; AGPL da valutare.

### 5. PyTrendFollow (chrism2671)
- **Metadati**: 467★ · push 2018-04 · MIT · Py
- **Limiti**: fermo dal 2018.
- **Verdetto registrato**: riferimento storico trend-following futures
  (Carver-school); il codice non si adotta, il metodo sì.

### 6. czsc (waditu/czsc)
- **Metadati**: 5.884★ · push 2026-08-16 · licenza NOASSERTION · ora Rust
- **Limiti**: 缠论 (Chan theory) = dominio CN.
- **Verdetto registrato**: fuori mercato.

### 7. volest (jasonstrimpel/volatility-trading)
- **Metadati**: 1.944★ · push 2024-10 · GPL-3.0 · Py
- **Copre**: R5/R11 (volatility estimators di Euan Sinclair: Yang-Zhang,
  Garman-Klass, Rogers-Satchell, Parkinson…).
- **Forza**: unico nel catalogo per stimatori vol completi; utile per
  sizing vol-target e fattori vol.
- **Limiti**: GPL-3.0; fermo 2024 (ma libreria matura, non serve manutenzione
  frequente).
- **Costo**: $0.
- **Per adottare**: candidato per il layer vol; in alternativa riscrivere
  i 5 stimatori (sono formule note) per evitare GPL.

### 8. quant-trading (duplicato del catalogo)
- **Verdetto registrato**: stessa entry di #1 ripetuta nell'originale;
  già valutato.

### 9. strategies CN (fmzquant/strategies)
- **Metadati**: 5.381★ · push 2025-04 · licenza NONE
- **Verdetto registrato**: raccolta CN, licenza assente → non adottabile;
  valore: inventario di idee.

### 10. trader (timercrack, ex BigBrotherTrade)
- **Metadati**: 8.418★ · push 2026-02 · Apache-2.0 · C
- **Nota**: il catalogo dice "实盘股票趋势策略" (strategia trend live CN).
- **Verdetto registrato**: CN; Apache-2.0; fermo da 6 mesi.

### 11. QuantsPlaybook (hugo2046)
- **Metadati**: 5.864★ · push 2026-05 · licenza NONE · Jupyter
- **Copre**: R5 (riproduzione research broker cinesi).
- **Limiti**: licenza assente → non adottabile come codice; CN.
- **Verdetto registrato**: materiale di lettura, non di adozione.

## B.2 — Expression-based alpha (6 voci)

### 1. torchquantum (nymath/torchqtm)
- **Metadati**: 55★ · push 2023-07 · MIT · Cython/C/Py
- **Copre**: R5 (operatori WorldQuant-style).
- **Limiti**: fermo 2023, minuscolo.
- **Verdetto registrato**: riferimento per expression-alpha engine.

### 2. OpenAlpha (caoruicn)
- **Metadati**: **GONE_404** — repo cancellato/spostato (probe 2026-08-22).
- **Verdetto registrato**: il catalogo linka un repo morto; idea
  (WebSim-compatible simulator) sopravvive come concetto.

### 3. stock (xcycharles)
- **Metadati**: 100★ · push 2021-08 · licenza NONE · Jupyter
- **Verdetto registrato**: A-share factor mining; licenza assente.

### 4. AlphaGen (ICT-FinD-Lab/alphagen)
- **Metadati**: 1.201★ · push 2026-06-04 · licenza NONE · Py
- **Copre**: R5/R10 (generazione alpha formulaica via RL).
- **Limiti**: licenza assente = bloccante per adozione codice.
- **Verdetto registrato**: l'IDEA (RL che genera espressioni alpha) è
  rilevante per un futuro G13-style loop; il codice non si adotta.

### 5. Genetic-Alpha (Morgansy)
- **Metadati**: 76★ · push 2020-12 · licenza NONE · Py
- **Verdetto registrato**: fermo 2020, licenza assente; il nostro
  genetics/ fa già GP su alpha.

### 6. alpha_examples (wukan1986)
- **Metadati**: 96★ · push 2026-02 · MIT · Py
- **Copre**: R5 (expression alpha in **Polars**).
- **Forza**: MIT, recente, Polars = vicino al nostro stack.
- **Per adottare**: pattern da leggere per expression-alpha su Polars.

## B.3 — Stock picking (3 voci)

### 1. InvesTool (axiaoxin-com/investool)
- **Metadati**: 2.253★ · push 2025-06 · Apache-2.0 · Go
- **Limiti**: CN, Go.
- **Verdetto registrato**: fuori mercato.

### 2. Sequoia-X (sngyai/Sequoia-X)
- **Metadati**: 5.422★ · push 2026-07 · licenza NONE · Py
- **Verdetto registrato**: A-share, licenza assente → non adottabile.

### 3. valueinvest (wangzhe3224/valueinvest)
- **Metadati**: 56★ · push 2026-08-20 · licenza NONE · Py
- **Copre**: R3/R5 (Graham, DCF, EPV, DDM + news sentiment).
- **Limiti**: licenza NONE; autore = curatore del catalogo.
- **Per adottare**: no (licenza); l'approccio multi-metodo valuation è
  un pattern noto.

## B.4 — Orderbook / Arbitrage (5 voci)

### 1. Microprice (sstoikov/microprice)
- **Metadati**: 473★ · push 2021-01 · licenza NONE · Jupyter
- **Copre**: R5/R8 (fair-price estimator da order book, Stoikov).
- **Forza**: paper di riferimento della microstruttura; implementazione
  minimale leggibile.
- **Limiti**: licenza assente; notebook; fermo (ma completo così).
- **Per adottare**: si re-implementa la formula (è un estimatore chiuso)
  piuttosto che importare codice senza licenza.

### 2-4. Blackbird / bitcoin-arbitrage / R2
- **Metadati**: blackbird **GONE_404**; bitcoin-arbitrage 2.584★ push
  2024-10 MIT; R2 816★ push 2023-04 MIT.
- **Nota**: il catalogo stesso li marca "old and not maintained".
- **Verdetto registrato**: riferimenti storici per arb cross-exchange;
  il mercato arb è saturato da anni; zero urgenza.

### 5. polymm (kachence)
- **Metadati**: 79★ · push 2026-08-16 · MIT · Py
- **Copre**: R7 (MM su prediction market, devig odds).
- **Verdetto registrato**: fuori tesi (prediction markets); tecnica
  devig interessante.

## B.5 — Analytic: Metrics (5 voci)

### 1. alphalens ⭐
- **Correzione probe**: il fork linkato dal catalogo (wangzhe3224/alphalens)
  ha 4★ ed è fermo al 2023. Il mantenuto è **stefan-jansen/alphalens**
  (631★, push 2025-12, Apache-2.0). L'originale quantopian (4.422★) è
  fermo 2024.
- **Copre**: R5/R9/R12 (IC analysis, quantile returns, turnover,
  sector-neutral analysis).
- **Forza**: standard de facto per factor analysis; Apache-2.0.
- **Per adottare**: candidato P0 per il factor lab.

### 2. ffn (pmorissette/ffn)
- **Metadati**: 2.634★ · push 2026-08-13 · MIT · Py
- **Copre**: R12 (calcoli finanziari: performance, drawdown, stats).
- **Forza**: MIT, attivo, stesso autore di bt → coppia naturale.
- **Per adottare**: candidato P0 analytics layer.

### 3. honest-signals (MarvinRey7879)
- **Metadati**: 1★ · push 2026-07-18 · MIT · Jupyter
- **Copre**: R9 (metodo: score pattern vs pattern-free baseline, lift con
  cluster-robust CI invece di hit-rate vs 50%).
- **Limiti**: 1★ = neonato, nessuno l'ha validato.
- **Per adottare**: NON come dipendenza; come **metodo** da replicare
  (è esattamente l'anti-beta discipline generalizzata).

### 4. Jacobian (morluto/jacobian)
- **Metadati**: 55★ · push 2026-08-22 · MIT · Py (MCP, CLI)
- **Copre**: supporto ricerca agent-driven (algebra esatta, congetture).
- **Limiti**: minuscolo, general-purpose math.
- **Per adottare**: curiosità; MCP-native è l'unico spunto.

### 5. quantstats (ranaroussi/quantstats)
- **Metadati**: 7.568★ · push 2026-07-20 · Apache-2.0 · Py
- **Copre**: R12 (tearsheet completi: 100+ metriche, benchmark compare).
- **Forza**: Apache-2.0, attivo, standard per reporting.
- **Per adottare**: candidato P0 reporting layer.

## B.6 — Analytic: Indicators (10 voci)

### 1. TA-Lib (TA-Lib/ta-lib-python)
- **Metadati**: 12.198★ · push 2026-07-29 · BSD-2-Clause · C/Cython
- **Copre**: R5 (200+ indicatori, 60+ candlestick patterns).
- **Stato**: già installato in Oracle; C-lib nativa.
- **Nota riproducibilità**: le implementazioni possono variare tra build
  (lezione MoonDev: indicatori hand-rolled per bit-exactness).
- **Per adottare**: keep; ma ogni fattore critico va re-implementato in
  Polars per determinismo.

### 2. ta-rust (greyblake)
- **Metadati**: 873★ · push 2024-07 · MIT · Rust
- **Verdetto registrato**: riferimento Rust; non serve senza pista Rust.

### 3. finta (peerchemist/finta)
- **Metadati**: 2.264★ · **archived** 2022 · LGPL-3.0 · Py
- **Verdetto registrato**: archived → morta.

### 4. pandas-ta (twopirllc) ⚠️
- **Metadati**: **GONE_404** — il repo originale (che aveva ~11K★) è
  stato cancellato da GitHub (probe 2026-08-22). Il catalogo linka un
  repo inesistente.
- **Successori**: `xgboosted/pandas-ta-classic` (420★), fork sparsi.
- **Coprirebbe**: R5 (130+ indicatori, 60+ patterns).
- **Per adottare**: se serve una indicator lib pandas-based, si valuta
  il successore comunitario verificando licenza; altrimenti TA-Lib +
  Polars coprono.

### 5. kand (kand-ta/kand)
- **Metadati**: 551★ · push 2026-01 · Apache-2.0 · Rust+Py
- **Copre**: R5 (TA veloce Rust con binding Py).
- **Per adottare**: candidato se si vogliono indicatori veloci senza
  C-lib; Apache-2.0.

### 6. chart-patterns (focus1691)
- **Metadati**: **GONE_404** — repo sparito (probe 2026-08-22).
- **Verdetto registrato**: il catalogo linka un repo morto.

### 7. ChartScout
- **Metadati**: sito commerciale (chartscout.io), nessun repo.
- **Verdetto registrato**: SaaS; fuori vincolo $0 se paid.

### 8. Wickra (wickra-lib/wickra)
- **Metadati**: 46★ · push 2026-08-21 · Apache-2.0 · multi-lang
- **Claim**: "514 indicatori O(1)-per-tick, bit-exact batch/streaming"
  🟠 da verificare.
- **Per adottare**: osservare; neonato.

### 9. QuantWave (lavs9/quantwave)
- **Metadati**: 12★ · push 2026-08-18 · MIT · Py/Rust/Polars
- **Copre**: R5/R7 (TA + backtest Polars-native, bit-identical
  batch/streaming, "agent skill").
- **Limiti**: 12★ = neonato.
- **Per adottare**: da monitorare — Polars-native bit-exact è
  architetturalmente interessante per noi.

### 10. go-talib (markcheno)
- **Metadati**: 938★ · push 2026-06 · MIT · Go
- **Verdetto registrato**: Go, fuori perimetro.

## B.7 — Analytic: Pricing (4 voci)

### 1. QuantLib + PyQL (enthought/pyql)
- **Metadati**: PyQL 1.335★ · push 2026-07 · licenza NOASSERTION · Cython
- **Copre**: pricing derivati completo (fixed income, equity, FX, credit).
- **Limiti**: licenza da verificare (QuantLib è BSD-like); pesante.
- **Per adottare**: solo se pista opzioni/derivati.

### 2. QuantLib.jl
- **Metadati**: 144★ · push 2020-02 · licenza NOASSERTION · Julia
- **Verdetto registrato**: Julia fuori perimetro, fermo 2020.

### 3. FinancePy (domokane/FinancePy)
- **Metadati**: 3.110★ · push 2026-08-21 · GPL-3.0 · Py
- **Copre**: pricing derivati (fixed income, equity, FX, credit).
- **Limiti**: GPL-3.0.
- **Per adottare**: candidato se pista derivati; GPL da valutare.

### 4. tf-quant-finance (google)
- **Metadati**: 5.475★ · push 2026-08-06 · Apache-2.0 · Py/TF
- **Copre**: pricing GPU-accelerato.
- **Limiti**: dipende da TensorFlow (non nel nostro stack); GPU.
- **Per adottare**: no per stack; riferimento.

### 5. vollib
- **Metadati**: 1.015★ · push 2023-06 · MIT · Py
- **Copre**: IV/greeks Black76/BS/BSM (lets_be_rational).
- **Verdetto registrato**: utile solo pista opzioni; fermo ma completo.

## B.8 — Analytic: Risk (4 voci)

### 1. pyfolio (quantopian/pyfolio)
- **Metadati**: 6.403★ · push 2023-12 · Apache-2.0 · Py
- **Copre**: R12 (portfolio/risk analytics, tearsheet, Bayesian).
- **Stato**: Quantopian morta; repo in manutenzione minima ma stabile.
- **Forza**: Apache-2.0; complementare a quantstats.
- **Per adottare**: candidato; pyfolio-reloaded (fork attivo, non nel
  catalogo) esiste se serve manutenzione.

### 2. curistat (moxiespirit/MyClone)
- **Metadati**: **GONE_404** — repo sparito (probe 2026-08-22).
- **Verdetto registrato**: il catalogo linka un repo morto (era
  futures vol forecasting + regime CRC + MCP).

### 3. System R (agents.systemr.ai)
- **Metadati**: SaaS, nessun repo.
- **Coprirebbe**: R15 (pre-trade gate, Kelly, MC, regime).
- **Verdetto registrato**: API commerciale; fuori $0 salvo free tier
  dichiarato; claim da verificare.

### 4. QuantDojo Tools Hub
- **Metadati**: sito web (calcolatori), nessun repo.
- **Verdetto registrato**: tool web gratuiti; nessun valore di adozione.

## B.9 — Analytic: Optimization (7 voci)

### 1. cvxportfolio (cvxgrp/cvxportfolio)
- **Metadati**: 1.249★ · push 2026-04-27 · GPL-3.0 · Py
- **Copre**: R11 (portfolio optimization + backtest integrati, Stanford).
- **Limiti**: GPL-3.0.
- **Per adottare**: candidato per R11; GPL da valutare.

### 2. skfolio (skfolio/skfolio)
- **Metadati**: 2.213★ · push 2026-08-14 · BSD-3-Clause · Py
- **Copre**: R11 (30+ modelli ottimizzazione, sklearn-API, cross-validation).
- **Forza**: BSD (licenza ottima), attivo, API moderna.
- **Per adottare**: candidato forte per R11.

### 3. Riskfolio-Lib (dcajasn)
- **Metadati**: 4.453★ · push 2026-08-18 · BSD-3-Clause · C++/Py
- **Copre**: R11 (HRP, HERC, CVaR, EVA, frontier, strategic/tactical).
- **Forza**: BSD, attivo, accelerato C++, il più completo OSS.
- **Per adottare**: candidato forte per R11.

### 4. Deepdow (jankrepl/deepdow)
- **Metadati**: 1.181★ · push 2024-01 · Apache-2.0 · Py
- **Copre**: R10/R11 (allocazione pesi via deep learning in un forward pass).
- **Limiti**: fermo 2024.
- **Per adottare**: riferimento per DL-portfolio.

### 5. PyPortfolioOpt (PyPortfolio/PyPortfolioOpt)
- **Metadati**: 5.972★ · push 2026-07-07 · MIT · Py
- **Copre**: R11 (frontier, Black-Litterman, HRP, CLA).
- **Stato**: già installato in Oracle.
- **Per adottare**: keep; Riskfolio-Lib lo estende.

### 6. empyrial (santoshlite/EigenLedger, ex Empyrial)
- **Metadati**: 1.074★ · push 2025-09 · Apache-2.0 · Py
- **Nota**: il catalogo linka ssantoshp/Empyrial; il repo risolto è
  santoshlite/EigenLedger — possibile rename, da confermare.
- **Copre**: R12/R11 (quant investment library retail/institutional).
- **Per adottare**: valutare dopo verifica rename+licenza.

### 7. spectre (Heerozh/spectre)
- **Metadati**: 821★ · push 2025-04 · GPL-3.0 · Py
- **Copre**: R6 (GPU-parallel backtest).
- **Limiti**: GPL; GPU; fermo.
- **Verdetto registrato**: no GPU nel setup.

## B.10 — Analytic: TimeSeries (4 voci)

### 1. tsfresh (blue-yonder/tsfresh)
- **Metadati**: 9.293★ · push 2026-07-06 · MIT · Py
- **Copre**: R5/R10 (estrazione automatica centinaia di feature da serie).
- **Forza**: MIT, attivo, rilevante per feature engineering fattori.
- **Per adottare**: candidato per lo Stage-3 feature extraction.

### 2. Prophet (facebook/prophet)
- **Metadati**: 20.365★ · push 2026-08-15 · MIT · Py
- **Copre**: forecasting stagionale.
- **Limiti**: forecasting direzionale non è come si cerca edge; utile
  per destagionalizzazione.
- **Per adottare**: solo come tool di decomposizione, non segnale.

### 3. pmdarima (alkaline-ml)
- **Metadati**: 1.733★ · push 2025-11 · MIT · Py
- **Verdetto registrato**: ARIMA automation; scarso valore per edge.

### 4. hurst-calculator (Osamwonyi18)
- **Metadati**: 2★ · push 2026-04 · MIT · Py
- **Verdetto registrato**: Hurst già implementato da noi (BL-012);
  ridondante.

## Riepilogo lotto B

| Sezione | Voci | Candidati forti | Morti/licenza-assente |
|---|---|---|---|
| General Alpha | 11 | je-suis-tm (mining), volest (vol) | analyzingalpha, QuantsPlaybook, strategies CN (licenza) |
| Expression alpha | 6 | alpha_examples (Polars), AlphaGen (idea) | OpenAlpha (404), Genetic-Alpha, stock |
| Stock picking | 3 | — | InvesTool (CN), Sequoia (licenza), valueinvest (licenza) |
| Orderbook/Arb | 5 | Microprice (formula) | blackbird (404), chart-patterns (404) |
| Metrics | 5 | alphalens (jansen fork), ffn, quantstats | honest-signals (metodo, non dep) |
| Indicators | 10 | TA-Lib (keep), kand, QuantWave (watch) | finta (archived), pandas-ta (404!), chart-patterns (404) |
| Pricing | 5 | — (solo se pista derivati) | QuantLib.jl |
| Risk | 4 | pyfolio | curistat (404) |
| Optimization | 7 | Riskfolio-Lib, skfolio, PyPortfolioOpt | spectre (GPL+GPU) |
| TimeSeries | 4 | tsfresh | hurst-calculator (ridondante) |

**Prossimo lotto**: C = Basic Components (fundamental libs, computation,
performance, alternatives) + Databases + MQ + Visualization.
