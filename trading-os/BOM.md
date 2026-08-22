# BOM — Catalogo completo `awesome-systematic-trading` per il greenfield

> Bill of Materials per il **nuovo progetto greenfield** in
> `trading-os/`, costruita dal catalogo completo di
> [wangzhe3224/awesome-systematic-trading](https://github.com/wangzhe3224/awesome-systematic-trading)
> (README `main`, fetch 2026-08-21 via GitHub API, 559 righe) **+ sezione
> `crypto_focus.md`** (35 righe). **Nessuna voce del catalogo è stata
> tralasciata**: ogni entry è elencata e classificata; le decisioni di
> adozione sono rimandate a una sessione congiunta (questo file è il
> materiale per quella decisione).
>
> Copertura dichiarata: **16 sezioni del README + crypto_focus = 100%
> delle voci**. Non sono state fatte verifiche repo-per-repo: ogni riga
> riporta lo stato di confidenza (vedi legenda).
>
> Legenda stato:
> - ✅ **GIÀ-NOSTRO** — già dipendenza/clonato/posseduto nel nostro parco
> - 🟢 **ADOPT-CANDIDATE** — candidato adozione (licenza e py3.12 da verificare)
> - 🔵 **REFERENCE** — letteratura/pattern, zero codice
> - 🟠 **PROBE** — claim o free-tier da verificare prima di qualsiasi uso
> - ⚪ **HOLD** — potenziale futuro, nessuna azione
> - 🔴 **DEAD/DUPLICATE** — progetto morto o funzione già coperta
> - ❌ **OUT** — fuori perimetro linguistico/mercato/costo
>
> Legenda confidenza: **R** = letto il README del catalogo; **V** =
> verificato su codice nostro; **S** = studio già fatto (vedi note).
>
> Regola permanente: web/README = untrusted. Ogni claim di rendimento
> ("74% win rate", "2,610%") è marcato 🟠 e non entra mai in una
> qualificazione senza audit indipendente.

---

## 1. 🔥 AI Powered Systematic Trading Systems (18 voci)

| # | Item | Lang | Stato | Conf | Note |
|---|---|---|---|---|---|
| 1 | DepthSight | Py/TS | 🔵 | R | piattaforma drag-drop + AI copilot + billing integrato → prodotto, non componente |
| 2 | TradeSight | Py | 🟠 | R | claim "self-evolving strategies via overnight cron" non verificato |
| 3 | AI Hedge Fund (virattt) | Py | 🔵 | S | riferimento architettura multi-agente; pattern già nostro (5 analysts + Skeptic) |
| 4 | FinRL (AI4Finance) | Py | 🔵 | S | DRL framework: letteratura, non dipendenza (prematuro senza fattori con IC) |
| 5 | FinGPT (AI4Finance) | Py | 🔵 | S | LLM finanza: pattern dataset; noi abbiamo LLM locale via OmniRoute |
| 6 | QLib (Microsoft) | Py/Cython | 🔵 | S | già clonato sul disco; riferimento factor-workflow (alpha158, IC/ICIR pipeline) |
| 7 | Qbot | Py | ⚪ | R | piattaforma quant AI cinese; fuori priorità |
| 8 | VARRD | Py | 🟠 | S | platform chiusa con MCP; solo benchmark metodologico (event studies + test statistici) |
| 9 | InvicTrade | — | 🟠 | R | claim "74% historical win rate" non auditato |
| 10 | BullBear | TS | ⚪ | R | arena AI con $100K virtuali; pattern battle già coperto (vedi §18) |
| 11 | FinClaw (NeuZhou) | Py | 🔵 | S | GA evolution 484 fattori: riferimento pipeline, studio 2026-08-19 archiviato |
| 12 | OpenFinClaw | TS | ⚪ | R | NL strategy generation su OpenClaw (68K★); claim non verificati |
| 13 | StockKit | TS | ⚪ | R | report daily via email; prodotto |
| 14 | stock-analysis (AdvancingTitans) | Py | 🔵 | R | evidence-pack Markdown/JSON per agenti: buon formato da imitare |
| 15 | oracle3 | Py | 🔵 | R | Kalshi/Polymarket pricing (Wang transform, λ̂=0.183, 291K contratti): metodo interessante, mercato fuori tesi |
| 16 | Eterna | MCP | 🟠 | R | "autonomous perp AI in 60s": claim da verificare, endpoint esterno |
| 17 | Inalpha | Py/TS | 🔵 | S | rank-IC + factor timing + machine approval: il suo core è il nostro Stage 4 |
| 18 | TraderHarness | Py | 🔵 | R | PIT masking + entity anonymization per backtest LLM: idea per test non-lookahead |

**Sintesi sezione**: 0 dipendenze, 4 riferimenti metodologici forti
(QLib, Inalpha, FinClaw, TraderHarness), 5 claim da trattare come
non-verificati. I sistemi AI completi sono **competitor/prodotti**, non
materiale da installare.

## 2. Backtest + live — General purpose, event-driven (26 voci)

| # | Item | Lang | Stato | Conf | Note |
|---|---|---|---|---|---|
| 1 | the0 | Py/TS/Rust | ⚪ | R | execution engine container-isolato |
| 2 | aat | Py/C++ | ⚪ | R | async event-driven, live multi-exchange |
| 3 | barter-rs | Rust | ❌ | R | fuori perimetro linguistico |
| 4 | bt | Py | 🔴 | R | coperto da vectorbt |
| 5 | Better Quant | C++ | ❌ | R | |
| 6 | Botvana | Rust | ❌ | R | |
| 7 | backtrader | Py | 🔵 | R | classico event-driven; riferimento API |
| 8 | backtesting.py | Py | 🔵 | S | già usato dal corpus MoonDev (Harvard-RBI); prototipi rapidi |
| 9 | FlashFunk | Rust | ❌ | R | |
| 10 | QuantFabric | C++ | ❌ | R | mercati CN |
| 11 | gobacktest | Go | ❌ | R | |
| 12 | Hikyuu | C++/Py | ❌ | R | CN |
| 13 | Investing Algorithm Framework | Py | ⚪ | R | |
| 14 | lumibot | Py | ⚪ | R | "a bit slow" dichiarato dal catalogo |
| 15 | **nautilus_trader** | Py/Cython/Rust | ✅ | V | già installato + clonato; adapter Hyperliquid incluso; live-trading ready |
| 16 | PyBroker | Py | ✅ | V | presente come extra (pybroker-integration) |
| 17 | QuantConnect Lean | C# | ⚪ | R | riferimento architettura cloud backtest |
| 18 | QUANTAXIS | Py/Rust | ❌ | R | CN |
| 19 | Rqalpha | Py | ❌ | R | CN |
| 20 | quanttrader | Py | 🔴 | R | "similar to backtesting.py" |
| 21 | qf-lib | Py | ⚪ | R | event-driven modulare |
| 22 | sdoosa-algo-trade-python | Py | 🔴 | R | didattico per newbie |
| 23 | vnpy | Py | ❌ | R | CN |
| 24 | WonderTrader | C++ | ❌ | R | CN |
| 25 | zvt | Py | ❌ | R | CN |
| 26 | zipline | Py | 🔴 | R | Quantopian morto 2020 |
| 27 | PandoraTrader | C++ | ❌ | R | CTP CN |
| 28 | **hftbacktest** | Py/numba | 🟢 | R | HFT backtest con queue position + latency + full tick — unico nel catalogo per L2 |
| 29 | flashalpha-fill-simulator | Py | ⚪ | R | fill simulator opzioni, zero deps |
| 30 | Cipher (cipher-bt) | Py | ⚪ | R | position-adjustment focused |
| 31 | Gunbot Quant | Py | ⚪ | R | screener+backtest con UI |
| 32 | PythonTradingFramework | Py | ⚪ | R | K8s, 150+ indicatori |
| 33 | Tradingview Screener API | TS | ⚪ | R | 13K campi dati TradingView + MCP |

## 3. Backtest + live — Vector-based (8 voci)

| # | Item | Lang | Stato | Conf | Note |
|---|---|---|---|---|---|
| 1 | QTradeX | Py | ⚪ | R | |
| 2 | FinHack | Py | ❌ | R | CN |
| 3 | **pysystemtrade** (Rob Carver) | Py | 🔵 | S | già in memoria reuse; libro "Systematic Trading"; regime + position sizing |
| 4 | finmarketpy | Py | ⚪ | R | ex-pythalesians |
| 5 | **vectorbt** | Py/numba | ✅ | V | già installato |
| 6 | fund-strategy | TS | ❌ | R | CN |
| 7 | fastquant | Py | 🔴 | R | wrapper, ridondante |
| 8 | Manifold-BT | Py/Rust | 🟠 | R | claim "hundreds of thousands combos in seconds" da verificare |

## 4. Backtest + live — Crypto focus (README, 16 voci)

| # | Item | Lang | Stato | Conf | Note |
|---|---|---|---|---|---|
| 1 | basana | Py | ⚪ | R | async crypto |
| 2 | c-binance-future-quant | Py | ⚪ | R | |
| 3 | triangular-arbitrage2 | TS | 🔴 | R | arb triangolare = competizione saturata |
| 4 | bTrader | Rust | ❌ | R | |
| 5 | **crypto-crawler-rs** | Rust | ⚪ | R | orderbook/trade crawler; Rust ma unica fonte L2 multi-exchange del catalogo |
| 6 | cryptotrader-core | Rust | ❌ | R | |
| 7 | openlimits | Rust | ❌ | R | |
| 8 | **Freqtrade** | Py | ✅ | V | già clonato; riferimento API Binance + strategy pattern |
| 9 | Hummingbot | Py/Cython | 🟢 | R | market-making client; live-ready. **PROBE 2026-08-22**: slug catalogo STALE (`CoinAlpha/`, 214★) → progetto vivo è `hummingbot/hummingbot` 19.538★ push 2026-08-22 Apache-2.0 |
| 10 | Jesse | Py | 🔵 | R | crypto research framework pulito |
| 11 | OctoBot | Py/Cython | ⚪ | R | TA+arb+social con web UI |
| 12 | DeepAlpha | Py | 🟠 | R | claim "70.9% walk-forward accuracy" non verificato |
| 13 | Kelp | Go | ❌ | R | Stellar DEX |
| 14 | exc | Rust | ❌ | R | |
| 15 | MyCryptoBot | Py/JS | ⚪ | R | |
| 16 | godzilla.dev | C++/Py | ⚪ | R | funding-rate arb + MM low-latency; repo community |

## 5. Backtest + live — ML/RL focused (3 voci)

| # | Item | Lang | Stato | Conf | Note |
|---|---|---|---|---|---|
| 1 | ml-quant-trading | Py/PyTorch | 🔵 | R | 213 mask-aware factors + bias correction: materiale mining |
| 2 | TradingGym | Py | ⚪ | R | gym env per RL/rule-based |
| 3 | DQL trading bot | Py | 🔴 | R | didattico |

## 6. Alpha Collections — General (11 voci)

| # | Item | Lang | Stato | Conf | Note |
|---|---|---|---|---|---|
| 1 | **je-suis-tm/quant-trading** | Py | 🔵 | R | 15+ strategie complete (VIX calc, CTA, pair trading, London Breakout, Monte Carlo…) |
| 2 | analyzingalpha | Py | 🔵 | R | companion del libro "Analyzing Alpha" |
| 3 | Finance (shashankvemuri) | Py | 🔵 | R | 150+ programmi quant |
| 4 | ThetaGang | Py | ⚪ | R | IBKR "the wheel" options; rilevante se pista opzioni |
| 5 | PyTrendFollow | Py | 🔵 | R | trend following futures sistematico |
| 6 | czsc | Py | ❌ | R | 缠论 CN |
| 7 | **volest** | Py | 🟢 | R | volatility estimators (Sinclair): Yang-Zhang/GK ecc. |
| 8 | quant-trading (duplicato nel catalogo) | Py | 🔴 | R | stessa entry ripetuta nel catalogo originale |
| 9 | strategies CN (fmzquant) | Py | ❌ | R | |
| 10 | trader (BigBrotherTrade) | Py | ❌ | R | CN |
| 11 | QuantsPlaybook (hugo2046) | Py | 🔵 | R | riproduzione research broker cinesi |

## 7. Alpha — Expression-based (6 voci)

| # | Item | Lang | Stato | Conf | Note |
|---|---|---|---|---|---|
| 1 | torchquantum | Cython/C/Py | ⚪ | R | operatori WorldQuant-style |
| 2 | OpenAlpha | C++ | ⚪ | R | WebSim-compatible |
| 3 | stock (xcycharles) | Py | ❌ | R | A-share factor mining |
| 4 | AlphaGen | Py | 🔵 | R | generazione alpha formulaica via RL |
| 5 | Genetic-Alpha | Py | 🔵 | R | GP per fattori multi-factor |
| 6 | alpha_examples | Py | 🔵 | R | expression alpha in **Polars** — pattern vicino al nostro |

## 8. Alpha — Stock picking (3 voci)

| # | Item | Lang | Stato | Conf | Note |
|---|---|---|---|---|---|
| 1 | InvesTool | Go | ❌ | R | CN |
| 2 | Sequoia | Py | ❌ | R | A-share |
| 3 | valueinvest (wangzhe3224) | Py | 🔵 | R | Graham/DCF/EPV/DDM + sentiment news |

## 9. Alpha — Orderbook / Arbitrage (5 voci)

| # | Item | Lang | Stato | Conf | Note |
|---|---|---|---|---|---|
| 1 | **Microprice** (Stoikov) | — | 🔵 | R | fair price da order book; base microstruttura |
| 2 | Blackbird | C++ | 🔴 | R | il catalogo lo marca "old, not maintained" |
| 3 | bitcoin-arbitrage | Py | 🔴 | R | idem |
| 4 | R2 Bitcoin Arbitrager | TS | 🔴 | R | idem |
| 5 | polymm | Py | ⚪ | R | MM Polymarket sports; devig odds |

## 10. Basic Components — Fundamental (16 voci)

| # | Item | Lang | Stato | Conf | Note |
|---|---|---|---|---|---|
| 1 | cvxpy | Py/C++ | ✅ | V | transitiva pyportfolioopt; KEEP documentato |
| 2 | jax | Py | ⚪ | R | GPU; non nel setup |
| 3 | numpy | Py/C | ✅ | V | |
| 4 | trade-frame | C++ | ❌ | R | |
| 5 | scipy | Py/C | ✅ | V | |
| 6 | statsmodels | Py | ✅ | V | |
| 7 | PyMC | Py | ⚪ | R | probabilistico; possibile per regime bayesiano futuro |
| 8 | DEAP | Py | ✅ | V | GA engine del nostro genetics/ |
| 9 | pandas | Py/Cython | ✅ | V | |
| 10 | polars | Rust/Py | ✅ | V | |
| 11 | FireDucks | Py | ⚪ | R | pandas-API compilata |
| 12 | Hugging Face | — | ✅ | V | via transformers |
| 13 | LangChain | Py | ✅ | V | in extra agents |
| 14 | scikit-learn | Py/Cython | ✅ | V | |
| 15 | PyTorch | Py | ✅ | V | |
| 16 | Keras | Py | 🔴 | R | ridondante con torch |
| 17 | TensorFlow | Py/C++ | 🔴 | R | ridondante con torch |
| 18 | rustworkx | Rust/Py | ⚪ | R | |
| 19 | networkx | Py | ⚪ | R | |

## 11. Computation (13 voci)

| # | Item | Stato | Note |
|---|---|---|---|
| Ray | ⚪ | distributed; single-machine basta |
| csp (Point72) | 🔵 | reactive stream C++: riferimento per real-time futuro |
| Dask | ⚪ | polars copre |
| Spark | ❌ | JVM |
| Hamilton | 🔵 | DAG dataflow: pattern pipeline interessante |
| Incremental (JaneStreet) | 🔵 | Ocaml; concetto incremental computation |
| Joblib | ⚪ | |
| Tributary | ⚪ | |
| GraphKit | 🔴 | marked "No activity" |
| Man MDF | 🔴 | "No activity" |
| Anchors C++ | 🔴 | "No activity" |
| Anchors Rust | 🔴 | "No activity" |
| Loman | 🔴 | "No activity" |

## 12. Performance boosters & profilers (12 voci)

| # | Item | Stato | Note |
|---|---|---|---|
| cython | ⚪ | |
| numba | ✅ | via vectorbt |
| pybind11 | ⚪ | |
| pyo3 | ⚪ | |
| CuPy | ⚪ | GPU |
| CuDF | ⚪ | GPU |
| codon | ⚪ | |
| Bottleneck | ⚪ | |
| NumExpr | ⚪ | |
| pandarallel | ⚪ | |
| py-spy | 🟢 | dev profiler |
| pyinstrument | 🟢 | dev profiler |
| Memray | 🟢 | dev memory profiler |

## 13. Alternative libraries (6 voci)

ndarray, faer, DataFrame C++, Vaex, Modin, Koalas → tutti ⚪/🔴: stack già scelto (polars).

## 14. Analytic tools

### 14.1 Metrics (5)
| Item | Stato | Note |
|---|---|---|
| **alphalens** (fork wangzhe3224) | 🟢 | factor analysis IC/quantile/turnover. **PROBE 2026-08-22**: fork linkato fermo 2023 (4★); mantenuto = `stefan-jansen/alphalens` 631★ push 2025-12 Apache-2.0 |
| **ffn** | 🟢 | financial functions |
| **honest-signals** | 🔵 | pattern vs pattern-free baseline + cluster-robust CI: metodo anti-beta |
| Jacobian | ⚪ | matematica componibile per agenti, MCP |
| **quantstats** | 🟢 | portfolio analytics tearsheet |

### 14.2 Indicators (10)
TA-Lib ✅ (installato, wrapper py) · ta-rust ❌ · finta 🔴 (archived 2022) ·
pandas-ta 🔴 **repo originale cancellato da GitHub (404, probe 2026-08-22)** —
successore comunitario `xgboosted/pandas-ta-classic` 420★ ·
kand ⚪ · chart-patterns 🟠 **repo sparito (404)** · ChartScout 🟠 (SaaS) ·
Wickra 🟠 (514 indicatori streaming, claim O(1) da verificare) · QuantWave 🔵
(Polars-native, bit-exact batch/streaming) · Go port ❌.

### 14.3 Pricing (4)
QuantLib/PyQL ⚪ (opzioni future) · QuantLib.jl ❌ · FinancePy ⚪ ·
tf-quant-finance ⚪ · vollib ⚪.

### 14.4 Risk (4)
| Item | Stato | Note |
|---|---|---|
| **pyfolio** | 🟢 | già in memoria reuse |
| curistat | 🟠 | futures vol forecasting + MCP; SaaS-like |
| System R | 🟠 | risk API con Kelly/MC; claim da verificare |
| QuantDojo | ⚪ | calcolatori web free |

### 14.5 Optimization (7)
cvxportfolio ⚪ · skfolio 🔵 (sklearn-style) · **Riskfolio-Lib** 🟢
(HRP/HERC/CVaR, C++ accel) · deepdow ⚪ · **PyPortfolioOpt** ✅
(installato) · empyrial ⚪ · spectre ⚪ (GPU).

### 14.6 TimeSeries (4)
tsfresh 🟢 (feature extraction) · Prophet 🔴 · pmdarima 🔴 ·
hurst-calculator 🔴 (già implementato da noi).

## 15. Visualization (11)

matplotlib ✅ · seaborn ✅ · Dash ⚪ · **Perspective** 🟢 (FINOS, streaming
grid — forte per dashboard dati grandi) · Streamlit ✅ (extra) · gradio ⚪ ·
pylatex ⚪ · **D-Tale** 🟢 (Man Group) · mplfinance 🟢 (candlestick) ·
KLinePic 🟠 · btplotting ⚪.

## 16. Message Queues / Databases (12)

Kafka ❌ · RedPanda ❌ · BlazingMQ ❌ (NATS già scelto, ADR-001) ·
**ArcticDB** 🔵 (Man Group, DataFrame DB) · **DuckDB** ✅ · lance 🔵
(columnar ML-native) · Arctic 🔴 · PyStore 🔴 · Marketstore ⚪ ·
**tectonicdb** 🔵 (order book ticks compressi — rilevante per L2) ·
Redis ⚪ · kdb ❌ (commerciale).

## 17. Data Source

### 17.1 Stocks & General (17 voci)
| Item | Stato | Note |
|---|---|---|
| **FilingFirehose** | 🟢 | SEC EDGAR JSON, 8-K classified, free tier 72h |
| AltData Atlas | 🔵 | directory di provider alt-data |
| polymarket-canary-tape | 🔵 | 271M trade + 61M OB events free CC-BY (HF dataset) |
| **OpenBB Terminal** | 🔵 | aggregatore fonti free |
| **FinanceDatabase** (JerBouma) | 🟢 | 300K+ simboli, no key |
| **FinanceToolkit** (JerBouma) | 🟠 | 200+ metriche; dipende da FMP — verificare path free |
| AkShare | ❌ | CN |
| 多因子模型数据 | ❌ | CN |
| findatapy | ⚪ | |
| FXMacroData | 🟠 | FX macro API con MCP; free tier da verificare |
| **yfinance** | ✅ | installato |
| pandas-datareader | ⚪ | |
| Wallstreet | ⚪ | |
| TuShare | ❌ | CN |
| Investpy | 🔴 | investing.com scraping fragile |
| awesome-data | 🔵 | altra lista di fonti |
| FundamentalAnalysis (JerBouma) | 🟢 | 20y statements 20K+ company |
| FinancialData.net | 🟠 | API commerciale |
| StockAInsights | 🟠 | AI extraction da filings; SaaS |
| Insider Alerts | 🟠 | SaaS |
| goMacro.ai | 🟠 | SaaS |
| Chart Library MCP | 🟠 | 24M embedding pattern; claims da verificare |
| Helium MCP | 🟠 | free 50 query/IP no signup |
| The Stall | 🟠 | pay-per-call x402 USDC |
| **AlphaAI** | 🟢 | news relevance-scored free 20req/min 100/day no card |
| BDE Score | ⚪ | |

### 17.2 Alternative (6)
Adanos 🟠 · 13F Insight 🟠 · sec-api-python 🔴 (commerciale) ·
**edgartools** 🟢 (SEC EDGAR free + MCP) · **AlphaSMO** 🟢 (13F+Form4
free anonymous) · CongressionalStockBrain 🟠 (STOCK Act disclosures, free tier).

### 17.3 Crypto (14)
| Item | Stato | Note |
|---|---|---|
| **cryptofeed** | 🟢 | WS feed handler 20+ exchange |
| **orderflow** (focus1691) | 🔵 | footprint candles da WS |
| Agent Gateway | ⚪ | prezzi Hyperliquid no key |
| tessera-api | 🟠 | order-flow Hyperliquid → Polars/DuckDB |
| **CoinPaprika** | 🟢 | 20K calls/mese no key |
| **DexPaprika** | 🟢 | 200K req/mese no key, 36 chains |
| PreReason | 🟠 | briefings BTC+macro |
| sharpe.ai | 🟢 | funding/options/narratives endpoints pubblici no key |
| Coinugget | ⚪ | |
| **Microverse Systems** | 🟢 | **L2 realtime 21 exchange free + historical replay** |
| Market Posture Daily | 🔵 | regime/RS 90 crypto free JSON |
| BitBank | 🟠 | forecasting ML |
| AgentServices | 🟠 | x402 |
| WealthVille | 🟠 | DeFi LP scoring; pubblica track record (buon segno) |
| **Shingou** | 🔵 | sentiment con log append-only verificabile + backtest **negativi** pubblicati — metodo onestà |
| 0xArchive | 🟠 | Hyperliquid/Lighter order-level |

### 17.4 Prediction Markets (8)
Parsec ⚪ · ProfitPlay ⚪ · pykalshi ⚪ · TurbineFi ⚪ · TBD Predict ⚪ ·
PolyMind 🟠 · marketlens 🟠 (L2 Polymarket da marzo 2026, free tier) ·
Live Tennis API ⚪. *Canale non prioritario; lasciato a catalogo.*

## 18. Broker APIs (9)

**ib_insync** ✅ · PENDAX ⚪ · **ccxt** ✅ · Coinnect ❌ (Rust) ·
async_rithmic ⚪ (Rithmic = paid data) · pmxt ⚪ · PolyClawster ⚪ ·
NanoStack ⚪ · "More is coming".

## 19. Quant Shops (5)

JaneStreet 🔵 (blog/podcast/OSS) · Man AHL 🔵 (blog/OSS) · DE Shaw 🔵 (OSS) ·
Two Sigma 🔵 (engineering blog) · HRT 🔵 (engineering blog).
*Tutti materiale Stage-2/letteratura, zero codice.*

## 20. Resources (14)

Research: RavenPack insights 🟠 · Alexandria Technology 🟠.
Books: Low Latency C++ ⚪ · Quantitative Portfolio Management 🔵 ·
Algorithmic Trading with Python 🔵 · Python for Algo Trading 🔵 ·
**Systematic Trading (Carver)** 🔵 · **ML for Algo Trading (Jansen)** 🔵 ·
**Advances in Financial ML (exercises repo)** 🔵 · ML for Asset Managers 🔵.
Blogs: QuantBox 🔵 · 大富翁量化 ❌ (CN) · Proof Engineering 🔵 · KeepRule 🔵.
Tutorials: Crypto trading tutorial 🔵 · **Solo Crypto Quant Starter Kit** 🔵
($0/mo playbook — affine ai nostri vincoli). Courses: Hudson & Thames 🔵.

## 21. Relevant Projects + crypto_focus.md (35 voci aggiuntive)

### 21.1 Relevant Projects (8)
systematic-trading-knowledge-collection 🔵 (stesso autore) · awesome-quant CN 🔵 ·
awesome-deep-trading 🔵 · awesome-crypto-trading-bots 🔵 ·
CongressionalStockBrain (duplicato §17.2) · PolyMind (duplicato) ·
EventTrader 🟠 · ToolsNova ⚪.

### 21.2 crypto_focus.md (voci non già coperte sopra)
perp-arbitrageur 🔴 (FTX morto) · FTX funding arb scanner 🔴 ·
HydroProtocol liquidation_bot 🔵 (Go; DDEX) · T-1000 ⚪ · Tai (Elixir) ❌ ·
Blankly ⚪ · Peregrine ⚪ (arb 131 exchange) · K (C++ MM) ⚪ ·
polymarket-whales 🟠 · gocryptotrader ⚪ (Go) · BBGO ⚪ (Go) ·
Solana SDK Tools ⚪ · **Signalview** 🟠 (segnali Hyperliquid con backtest
pubblico score −100..+100: formato da studiare) · **TrendRider** 🔵
(Freqtrade strategy con exit ladder pubblica + live dry-run: claim
"+69% profit/-77% DD" da verificare) · **INDICIA DESK** 🟠 (opzioni whale
classification, track record aperto) · **perpsignal** 🟢 (backtester perp
pure-research, Apache-2.0, `pip install perpsignal`) · **FillBench** 🔵
(benchmark latenza exchange, dati aperti) · **FundingRadar** 🟢 (funding
cross-exchange keyless, stdlib) · RektCalc ⚪.

---

## 22. Matrice di copertura del catalogo (onestà)

| Capability | Copertura catalogo | Gap |
|---|---|---|
| Backtest vectorized | ✅✅ (vectorbt, vbt-pro, Manifold) | — |
| Backtest event-driven | ✅✅ (nautilus, backtrader…) | — |
| Backtest HFT/L2 | ✅ (hftbacktest, unico) | queue model da validare |
| Execution | ✅ (nautilus, hummingbot, freqtrade) | — |
| Dati equity | ✅✅ (edgartools, FMP-based, OpenBB) | survivorship-free universe assente |
| Dati crypto | ✅✅ (Vision/cryptofeed/Microverse/Paprika) | — |
| Dati futures intraday storici | ⚠️ debole | **nessuna fonte free nel catalogo** |
| Dati opzioni | ⚠️ (solo pricing libs) | niente dati OPRA free |
| Dati macro PIT | ⚠️ (FXMacroData commerciale) | FRED vintage = nostra soluzione |
| Order flow L2 | ✅ (Microverse, tectonicdb) | ToS da verificare |
| Metriche/analisi | ✅✅ (quantstats/alphalens/ffn/pyfolio) | — |
| Ottimizzazione portafoglio | ✅✅ (pyportfolioopt/Riskfolio/skfolio) | — |
| Validation overfitting | ⚠️ (honest-signals, purgedcv citata altrove) | DSR/PBO/CPCV = nostra specialità |
| Prop-firm governance/risk | ❌ **vuoto totale** | solo Oracle lo fa |
| UI/dashboard | ⚠️ (generic viz) | nessun trading terminal completo OSS |
| Regime detection | ⚠️ frammentata | — |
| ML/RL | ✅ (qlib/finrl/pybroker) | — |

## 23. Stato delle decisioni

Il catalogo è completo; **nessuna decisione di adozione è ancora presa**.
Le colonne Stato/Conf sono la base fattuale per decidere assieme. I
candidati più frequenti tra i 🟢 (per visibilità, non per decisione):
hftbacktest, Hummingbot, Riskfolio-Lib, alphalens, quantstats+ffn,
pyfolio, volest, cryptofeed, Microverse, edgartools, AlphaSMO,
FinanceDatabase, tsfresh, Perspective, D-Tale, mplfinance,
perpsignal, FundingRadar, py-spy/pyinstrument/Memray.

## 24. Gap dichiarati di questa BOM

1. **Nessuna verifica repo-per-repo**: stato basato sul catalogo + nostri
   studi pregressi (S). Ogni 🟢 richiederà probe (licenza SPDX, py3.12,
   free-tier reale) prima dell'adozione.
2. La descrizione di alcuni item nel catalogo originale contiene refusi
   (es. DuckDB descritto come ArcticDB); qui riportati come da fonte.
3. `crypto_focus.md` ha voci duplicate col README (Freqtrade, Hummingbot,
   Jesse, OctoBot, Kelp, bTrader, Microverse, DeepAlpha): conteggiate una
   volta sola nelle tabelle principali.
4. Le dimensioni/claim quantitativi dei singoli repo (star, activity) non
   sono stati rifetchati: il catalogo usa badge last-commit/stars che
   scadono; trattarli come indicativi.
