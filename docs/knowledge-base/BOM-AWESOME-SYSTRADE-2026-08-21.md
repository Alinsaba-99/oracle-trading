# BOM — awesome-systematic-trading → Oracle

> Bill of Materials seria: cosa ci serve davvero da
> [wangzhe3224/awesome-systematic-trading](https://github.com/wangzhe3224/awesome-systematic-trading)
> (4.989 ★, ultimo commit 2026-08-21, 559 righe README + sezione crypto).
> Fetch del README verificato 2026-08-21 via GitHub API. Sostituisce e
> amplia `AWESOME-SYSTRADE-AUDIT-2026-08-17.md`.
>
> Vincoli: **$0/mese** (ADR-020), Python 3.12, licenza compatibile MIT/
> Apache/BSD, allineamento con la **Edge Research Factory** (BL-700..709,
> spec `docs/plans/2026-08-21-edge-research-factory-design.md`).
>
> Legenda stato: ✅ già in casa (installato o clonato) · 🟡 candidato
> (da acquisire) · ❌ escluso (con motivo).

## 0. Cosa abbiamo già (ground truth da pyproject.toml + cloni)

Installato: numpy, pandas, polars, duckdb, pyarrow, statsmodels,
scipy (extra analytics), scikit-learn, lightgbm, torch, transformers,
vectorbt, nautilus-trader (anche clonato), ta-lib, ccxt, ib-insync,
asyncpg, deap, pyportfolioopt, purgedcv, deflated-sharpe, hmmlearn,
ruptures, arch, simfin, yfinance, httpx, streamlit, plotly, structlog,
fastapi, langgraph.
Cloni di riferimento (nessun lavoro nostro dentro): freqtrade, qlib,
TradingAgents.

**Implicazione BOM**: lo strato backtest/execution/ottimizzazione base è
già coperto. I buchi veri sono 4: **analisi fattori** (alphalens/quantstats/
ffn), **dati SEC/alternative** (edgartools), **feed crypto real-time**
(cryptofeed), **research ML** (FinRL/QLib pattern). Tutto il resto è
ridondanza o rumore.

---

## 1. 🔥 AI Powered Systems (18 item nella lista)

| Item | Stato | Verdetto |
|---|---|---|
| **QLib (Microsoft)** | ✅ clonato | 🟡 **Stage 2 factory**: riferimento per IC screen / factor workflow; non installiamo il pacchetto (dipendenze pesanti), ne prendiamo il pattern `alpha158` + IC/ICIR pipeline come input di BL-706 |
| **FinRL** (AI4Finance) | — | 🟡 solo come letteratura Stage 2 (BL-KB-114): RL trading è research-grade, non deploy; citare i paper, non installare |
| **FinGPT** (AI4Finance) | — | 🟡 Stage 2 (BL-KB-113): sentiment LLM; noi abbiamo già ai_analysts via OmniRoute locale; prendere il dataset-pattern, non il framework |
| **AI Hedge Fund** (virattt) | — | 🟡 pattern-only: il nostro `agents/` (5 analysts + Skeptic + Risk) è già più avanti; utile come riferimento di architettura multi-agente |
| **VARRD** | — | ⚠️ **già mappato**: ROADMAP G14 cita VARRD; è closed-platform con MCP — usarlo solo come **benchmark metodologico** (event studies + statistical tests), mai come dipendenza |
| **Inalpha** | — | ⚠️ già studiato (plan-integration mai eseguito, archiviato 2026-08-19): il suo "rank IC + machine approval" è esattamente il nostro Stage 4; riferimento, non integrazione |
| **FinClaw / OpenFinClaw** | — | ⚠️ già studiato (GA evolution 484 fattori): riferimento per BL-431 pipeline pattern; non integrare |
| **DepthSight, TradeSight, BullBear, StockKit, oracle3, Eterna, InvicTrade, DeepAlpha, Qbot, stock-analysis, TraderHarness** | ❌ | esclusi: piattaforme prodotto (billing integrato / claim marketing "74% win rate", "70.9% accuracy" **non verificati** → `claim_non_verificato`), fuori canale, o A-share/CN-only. TraderHarness ha un'idea buona (PIT masking + entity anonymization per test LLM) → nota per BL-619 |

**Regola**: nessun "AI trading system" della lista entra come dipendenza.
Sono competitor o prodotti, non componenti. Da loro prendiamo solo pattern
documentati nel registry (Stage 2, `origine=letteratura`).

## 2. Backtest + live trading (40+ item)

| Item | Stato | Verdetto |
|---|---|---|
| **nautilus_trader** | ✅ installato + clonato | keep, "candidato non certificato" (decisione 2026-08-19 invariata): certification = mesi, non ora |
| **vectorbt** | ✅ installato | keep: sweep veloce di varianti nella factory |
| **PyBroker** | ⚠️ extra interno | presente come extra privato; keep |
| **pysystemtrade** (Rob Carver) | — | 🟡 **Stage 2 letteratura**: il suo regime/position-sizing framework è coerente col nostro dual-channel; già in memoria "reuse quantstats/pyfolio/pysystemtrade" |
| **hftbacktest** (nkaz001) | — | 🟡 **candidato P2**: modeling queue position + latency su tick/L2 — serve solo se i fattori order-flow crypto (VPIN, OFI) passano l'IC screen; licenza Apache-2.0, Python. Non installare prima di BL-708 |
| **backtrader / backtesting.py / zipline / bt / lumibot / fastquant / cipher-bt / QTradeX / Manifold-BT / FinHack / finmarketpy** | ❌ | ridondanti con vectorbt+nautilus; zipline è morto |
| **QuantConnect Lean, barter-rs, aat, BetterQuant, vnpy, Hikyuu, QUANTAXIS, WonderTrader, zvt, rqalpha, gobacktest, the0, Botvana, FlashFunk, PandoraTrader, QuantFabric** | ❌ | stack diverso (C#/Rust/Go/C++) o mercato CN; fuori perimetro |
| **basana, Jesse, OctoBot, Hummingbot, Freqtrade, Kelp, godzilla** | ❌/🟡 | crypto bot completi = duplicherebbero Oracle; **Freqtrade resta riferimento API Binance** (già clonato). godzilla funding-rate-arb = nota Stage 2 per ipotesi EF |
| **ML/RL focused**: TradingGym, ml-quant-trading, DQL bot | ❌ | RL non è la pista; ml-quant-trading (213 mask-aware factors) = nota Stage 2 |

## 3. Alpha Collections

| Item | Stato | Verdetto |
|---|---|---|
| **je-suis-tm/quant-trading** | — | 🟡 Stage 2: 15+ strategie con codice (VIX calc, CTA, pair trading, London Breakout) = materiale mining per BL-704; nessuna adozione diretta |
| **PyTrendFollow** | — | 🟡 Stage 2: trend following futures sistematico — riferimento per ipotesi CTA; il canale futures daily per noi è MORTO (S0.2), quindi solo letteratura |
| **volest** (Sinclair volatility estimators) | — | 🟡 **candidato P2**: vol estimators (Yang-Zhang, Garman-Klass…) utili al dual-channel σ-scaled (BL-709); piccolo, MIT |
| **ThetaGang** (IBKR options wheel) | — | 🟡 Stage 2: opzioni = BL-407/G11, non ora; nota per quando avremo dati opzioni |
| **AlphaGen / Genetic-Alpha / OpenAlpha / torchquantum / alpha_examples** | ❌/🟡 | il nostro `genetics/` copre già GP alpha; alpha_examples (Polars expression alpha) = nota tecnica per BL-706 |
| **czsc / Sequoia / InvesTool / strategies CN** | ❌ | A-share only |
| **Microprice** (Stoikov) | — | 🟡 Stage 2: microprice = ipotesi order-flow EF con meccanismo economico solido; testabile su L2 crypto free (Microverse) |
| **Arbitrage crypto bots** (Blackbird ecc.) | ❌ | la lista stessa li marca "old, not maintained"; funding-rate arb resta come **ipotesi** nel registry, non come codice |

## 4. Basic Components

| Item | Stato | Verdetto |
|---|---|---|
| numpy/scipy/statsmodels/polars/pandas/duckdb/pyarrow/scikit-learn/torch/lightgbm/DEAP/cvxpy | ✅ | tutti già installati (cvxpy via pyportfolioopt, KEEP documentato live-readiness #2) |
| jax / CuPy / CuDF / codon | ❌ | GPU non nel setup; YAGNI |
| Ray / Dask / Spark / csp / Hamilton | ❌ | single-machine basta per il lake (11 GB); polars copre |
| cython/numba/pybind11/pyo3/Bottleneck/NumExpr/pandarallel | ❌ | vectorbt porta già numba; nessun hot spot che lo giustifichi (BL-618 è structlog, non performance) |
| py-spy / pyinstrument / Memray | — | 🟡 dev-tools opzionali P3 per BL-618 se serve profiling; non bloccanti |
| ndarray/faer/DataFrame C++/Vaex/Modin/Koalas | ❌ | alternative a stack già scelto |

## 5. Analytic tools — **la sezione con più buchi reali**

| Item | Stato | Verdetto |
|---|---|---|
| **alphalens (fork wangzhe3224)** | — | 🟡 **P1 BL-710**: analisi fattori (IC, quantile return, turnover). Originale Quantopian morto, fork mantenuto. Serve a BL-706 come secondo parere sull'IC |
| **quantstats** | — | 🟡 **P1 BL-711**: reportistica portfolio (drawdown/Sharpe/tearsheet). Già in memoria reuse. Integrazione leggera sopra `analytics/metrics/canonical.py` (mai in sostituzione: ADR-021) |
| **ffn** | — | 🟡 P2 con quantstats (stesso autore, dipendenza naturale) |
| **honest-signals** | — | 🟡 **Stage 2 riferimento metodologico**: pattern scoring vs pattern-free baseline con cluster-robust CI — è esattamente la disciplina anti-beta di BL-093 generalizzata; citare nel registry |
| **pyfolio** | — | 🟡 P2 (già in memoria reuse); non installato oggi |
| **tsfresh** | — | 🟡 P2 BL-712: feature extraction automatica time-series → alimenta Stage 3 matrice; pesante ma Apache-2.0 |
| **pandas-ta / finta** | — | ❌ abbiamo ta-lib + indicators interni |
| **wickra / kand / QuantWave / chart-patterns / ChartScout** | — | ❌ TA streaming: non siamo in real-time; QuantWave (Polars-native bit-exact) = nota per il futuro |
| **QuantLib / FinancePy / vollib / tf-quant-finance** | ❌ | pricing derivati: opzioni non in pista (G11 futuro) |
| **Riskfolio-Lib** | — | 🟡 **P2 BL-713**: ottimizzazione con HRP/HERC/rischio CVaR, C++ accelerato — complementa pyportfolioopt per BL-709 dual-channel sizing |
| **skfolio / cvxportfolio / empyrial / deepdow / spectre** | ❌ | ridondanti con pyportfolioopt+Riskfolio |
| **Prophet / pmdarima** | ❌ | forecasting direzionale naive: non è come troviamo edge |
| **hurst-calculator** | ❌ | Hurst già implementato (BL-012) |

## 6. Visualization / UI (rilevante per il track UI/UX)

| Item | Stato | Verdetto |
|---|---|---|
| **mplfinance** | — | 🟡 P3: candlestick nei report factory (PNG nei report MD) |
| **Perspective (FINOS)** | — | 🟡 **nota per dashboard**: grid/streaming grandi dataset — il nostro `apps/dashboard` è React+LightweightCharts; Perspective è candidata per la pagina registry/factory (tabelle grandi interattive) quando faremo il track UI |
| **D-Tale (Man Group)** | — | 🟡 P3 esplorazione dati lake during Stage 3 |
| Dash/Streamlit/gradio | ⚠️ streamlit già extra | dashboard vera = apps/dashboard, non Streamlit |
| KLinePic / btplotting / pylance | ❌ | fuori contesto |

## 7. Databases / MQ

| Item | Stato | Verdetto |
|---|---|---|
| DuckDB | ✅ | keep (analytics) |
| **ArcticDB (Man Group)** | — | ❌ il lake è parquet+polars+coverage.json: migrare ora = churn senza valore |
| lance / tectonicdb / marketstore / pystore / arctic | ❌ | ridondanti col lake; tectonicdb (order book compresso) = nota se L2 crypto diventa pista |
| Kafka/RedPanda/BlazingMQ | ❌ | NATS già scelto (ADR-001); MQ pesanti = over-engineering |

## 8. Data Source — **sezione chiave per la factory, filtro $0 duro**

### 8.1 Stocks/general
| Item | Stato | Verdetto |
|---|---|---|
| **edgartools** | — | 🟡 **P1 BL-714**: SEC EDGAR fundamentals + 13F + insider + 8-K, free, MCP incluso. Sblocca dominio 01/06 con dati reali (SimFin resta per i 185 ticker); licenza MIT |
| **FilingFirehose** | — | 🟡 P2: free tier 72h (8-K classified, 13D/G activist tags) — complementar a edgartools; solo tier free (paid $29/mo = fuori) |
| **FinanceToolkit + FinanceDatabase + FundamentalAnalysis** (JerBouma) | — | 🟡 P2 BL-715: 300K+ simboli + 200 metriche; dipende da Financial Modeling Prep — verificare che il path free basti, altrimenti solo FinanceDatabase (universo simboli, no API key) |
| **OpenBB Terminal** | — | 🟡 Stage 2 riferimento: aggregatore fonti free; usare come mappa, non come dipendenza |
| **yfinance / pandas-datareader** | ✅ | keep (già ADR-020) |
| **AkShare/TuShare/GetAstockFactors** | ❌ | CN |
| StockAInsights/FinancialData.net/InsiderAlerts/goMacro/Chart Library MCP/Helium MCP/The Stall | ❌ | SaaS con paid tier o pay-per-call (x402): contro ADR-020; Helium free 50 query = troppo poco; The Stall paga in USDC = no |
| **AlphaAI** | — | 🟡 P3: news relevance-scored free 20 req/min / 100 day no card — per dominio 07 se il budget chiamate basta |
| **FXMacroData** | — | ❌ OAuth/API commerciale; FRED PIT già nostro |

### 8.2 Alternative
| Item | Stato | Verdetto |
|---|---|---|
| **SEC EDGAR** (diretto) | ✅ | già in KB-01; edgartools lo potenzia |
| **AlphaSMO** | — | 🟡 P3: 13F + Form 4 + smart-money-convergence **free anonymous tier no signup** — ipotesi EF pronta (insider+institutional convergence) |
| Adanos / 13F Insight / CongressionalStockBrain | ❌/🟡 | SaaS: CongressionalStockBrain (STOCK Act disclosures, free tier, no login) = nota Stage 2 per ipotesi "congressional trading follow" — letteratura prima |
| **Shingou** | — | 🟡 Stage 2 **esempio di onestà**: pubblica backtest negativi (hit rate ≈ coin flip, IC residuo ≈ 0) e log append-only verificabile — metodo da imitare nei nostri report, non fonte dati |

### 8.3 Crypto — **dove la factory ha il vantaggio dati**
| Item | Stato | Verdetto |
|---|---|---|
| **cryptofeed** (bmoscon) | — | 🟡 **P1 BL-716**: websocket feed handler 20+ exchange, asyncio, maturo. Sblocca raccolta going-forward funding/L2/trades che il lake non ha (Binance Vision = storico). Licenza Apache-2.0 |
| **Microverse Systems** | — | 🟡 **P2 BL-717**: L2 order book real-time **21 exchange free websocket + historical replay** — è lo sblocco dell'hard-block order-flow (KB-04) su crypto; verificare ToS + limiti |
| **CoinPaprika / DexPaprika** | — | 🟡 P2: 20K calls/mese no key / 200K calls/mese no key — metadati + on-chain DEX per dominio 11 |
| **sharpe.ai** | — | 🟡 P3: funding rates + options + arbitrage endpoints pubblici no key — per ipotesi funding (EF) |
| **tessera-api / 0xArchive** | — | 🟡 P2: order-flow Hyperliquid (Polars/DuckDB native) — Hyperliquid è dove MoonDev punta; dati free da verificare |
| **polymarket-canary-tape** (HuggingFace) | — | 🟡 Stage 2: 271M trade + 61M order-book events **free CC-BY-4.0** — dataset unico per microstruttura prediction markets; fuori canale attuale ma costo zero |
| **orderflow footprint** (focus1691) | — | 🟡 P3: footprint candles da WS — riferimento per BL-KB-30 |
| PreReason/BitBank/AgentServices/WealthVille/Coinugget/Market Posture/Agent Gateway | ❌/🟡 | Market Posture Daily (free terminal+JSON, regime/RS 90 crypto) = nota Stage 2; il resto claim non verificabili o nicchia |
| **Binance Vision** (non in lista, nostro) | ✅ | già adapter + ADR-020: fundingRate/liquidationSnapshot storici |

### 8.4 Prediction markets
| Item | Stato | Verdetto |
|---|---|---|
| pykalshi / pmxt / Parsec / TurbineFi / marketlens | ❌ | canale non nostro; marketlens ha free tier ma il valore (L2 storico Polymarket) è fuori tesi. Nota: se mai entrassimo, il polymarket-canary-tape è il dato free |

## 9. Broker APIs

| Item | Stato | Verdetto |
|---|---|---|
| ib_insync / ccxt | ✅ | keep |
| **async_rithmic** | — | ❌ Rithmic = account data a pagamento |
| PENDAX/Coinnect/NanoStack/pmxt/PolyClawster | ❌ | fuori canale |

## 10. Quant shops / Resources (Stage 2 puro, zero install)

- **Jane Street blog/podcast/OSS, Man AHL blog/OSS (ArcticDB, D-Tale già visti), DE Shaw OSS, Two Sigma engineering, HRT Beat** → 🟡 tutti nel piano di amplificazione BL-704 come fonti primarie di ipotesi (pattern microstruttura, execution, risk).
- **Hudson & Thames** (mLFAM implementations) → 🟡 riferimento implementativo per BL-KB-99/109 (già sapevamo; mlfinlab closed-source ma H&T ha materiale open).
- Libri con repo: *Advances in Financial ML* exercises (BlackArbsCEO), *ML for Trading* (jansen), *ML for Asset Managers* (emoen) → Stage 2.
- **systematic-trading-knowledge-collection** (stesso autore) → Stage 2 mining.

---

## 11. Sintesi: la lista della spesa

### P1 — da acquisire ora (sbloccano la factory, tutti $0)
| # | Item | Uso | BL proposto |
|---|---|---|---|
| 1 | **alphalens (fork)** | analisi fattori in BL-706 | BL-710 |
| 2 | **quantstats (+ffn)** | tearsheet report factory | BL-711 |
| 3 | **edgartools** | SEC 13F/insider/8-K free | BL-714 |
| 4 | **cryptofeed** | feed crypto going-forward | BL-716 |
| 5 | **purgedcv/haircut** | già: BL-707 (nessun download) | — |

### P2 — quando il primo sprint lo giustifica
Riskfolio-Lib (BL-713), Microverse L2 (BL-717), tsfresh (BL-712),
FinanceDatabase/Toolkit (BL-715, con verifica FMP free), FilingFirehose
72h, CoinPaprika/DexPaprika, tessera/0xArchive, volest, hftbacktest
(solo se order-flow passa IC), pyfolio.

### P3 — note Stage 2 (zero codice)
Microprice, honest-signals metodo, Shingou metodo-onestà, Market
Posture Daily, AlphaSMO, AlphaAI, CongressionalStockBrain, polymarket-
canary-tape, ThetaGang, je-suis-tm, PyTrendFollow, quant shops blogs.

### ❌ Esclusi per principio
- Qualsiasi cosa con paid tier necessario o pay-per-call (x402/USDC)
- Claim di win-rate/ROI non auditati (InvicTrade, DeepAlpha, Eterna…) →
  marcati `claim_non_verificato`, mai input di qualificazione
- Framework CN/A-share only, stack C#/Rust/Go/C++, bot completi che
  duplicherebbero Oracle, prediction markets (fuori tesi)

## 12. Gap dichiarati di questa BOM

1. Licenze: verificate a livello di famiglia (MIT/Apache/BSD) ma non
   repo-per-repo con SPDX scan — da fare prima di ogni `uv add` (task
   dentro i BL-71x).
2. I free-tier (Microverse, AlphaAI, Sharpe, FilingFirehose) vanno
   verificati all'atto dell'uso: le pagine possono cambiare.
3. crypto_focus.md del repo è uno stub (35 righe): l'inventario crypto
   reale è nel README principale + le nostre fonti ADR-020.
4. Nessuna prova di compatibilità Python 3.12 eseguita in questa BOM —
   ogni BL-71x include smoke install + test.
