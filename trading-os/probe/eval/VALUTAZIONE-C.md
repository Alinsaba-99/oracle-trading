# VALUTAZIONE C — Basic Components + Visualization + MQ + Databases

> Lotto 3 di 6. Stesse regole: nessuna esclusione, scheda per voce.

## C.1 — Fundamental libraries (16 voci)

### 1. cvxpy (cvxpy/cvxpy)
- **Metadati**: 6.307★ · push 2026-08-22 · Apache-2.0 · Py/C++
- **Copre**: R11 (convex optimization modeling language).
- **Stato**: già transitivo in Oracle (via pyportfolioopt); KEEP documentato.
- **Per adottare**: keep; promuoverlo a dipendenza diretta se R11 lo usa
  esplicitamente.

### 2. jax (jax-ml/jax)
- **Metadati**: 36.196★ · push 2026-08-22 · Apache-2.0 · Py
- **Copre**: R10 (vmap/jit/GPU per ricerca numerica).
- **Limiti**: GPU non nel setup; sovrapposto a torch.
- **Per adottare**: no ora; nota per eventuale ricerca GPU.

### 3. numpy (numpy/numpy)
- **Metadati**: 32.579★ · push 2026-08-21 · licenza NOASSERTION (BSD-style) · C
- **Copre**: R5/R6/R10 foundation.
- **Stato**: installato. Keep.

### 4. trade-frame (rburkholder/trade-frame)
- **Metadati**: 674★ · push 2026-08-14 · licenza NOASSERTION · C++
- **Copre**: R7/R13 (IBKR + IQFeed, options).
- **Limiti**: C++; licenza da leggere; dati IQFeed (DTN) = paid.
- **Per adottare**: no (dati paid + C++).

### 5. scipy (scipy/scipy)
- **Metadati**: 14.944★ · push 2026-08-21 · BSD-3-Clause · Py/C
- **Stato**: installato (extra analytics). Keep.

### 6. statsmodels (statsmodels/statsmodels)
- **Metadati**: 11.583★ · push 2026-08-21 · BSD-3-Clause · Py
- **Stato**: installato. Keep. R9 (test statistici) ne beneficia.

### 7. PyMC (pymc-devs/pymc)
- **Metadati**: 9.718★ · push 2026-08-17 · licenza NOASSERTION (Apache-2.0 in
  realtà — verificare) · Py
- **Copre**: R10 (modelli bayesiani: regime, shrinkage).
- **Per adottare**: candidato per regime bayesiano futuro; verificare licenza
  effettiva (repo dice Apache-2.0 nel LICENSE).

### 8. DEAP (DEAP/deap)
- **Metadati**: 6.434★ · push 2026-04-17 · LGPL-3.0 · Py
- **Stato**: già installato (motore GA del nostro genetics/). Keep.
- **Nota licenza**: LGPL già accettato in casa.

### 9. pandas (pandas-dev/pandas)
- **Metadati**: 49.541★ · push 2026-08-21 · BSD-3-Clause · Py/Cython
- **Stato**: installato. Keep.

### 10. polars (pola-rs/polars)
- **Metadati**: 39.436★ · push 2026-08-22 · MIT · Rust/Py
- **Stato**: installato; colonna portante. Keep.

### 11. FireDucks
- **Metadati**: sito/progetto (fireducks-dev), repo non risolto dallo slug.
- **Copre**: pandas-API accelerata da compilatore.
- **Per adottare**: curiosità; polars copre la performance.

### 12. Hugging Face (huggingface org)
- **Metadati**: org (lo slug "huggingface/" non è un repo → API_ERROR, unico
  errore residuo del probe). I repo principali (transformers, datasets)
  sono attivi.
- **Stato**: transformers installato. Keep.

### 13. LangChain (langchain-ai/langchain)
- **Metadati**: 144.745★ · push 2026-08-22 · MIT · Py
- **Stato**: in extra agents. Keep se il greenfield usa orchestrazione LLM.

### 14. scikit-learn (scikit-learn/scikit-learn)
- **Metadati**: 67.006★ · push 2026-08-21 · BSD-3-Clause · Py/Cython
- **Stato**: installato (extra analytics). Keep. R10 baseline.

### 15. PyTorch (pytorch/pytorch)
- **Metadati**: 102.530★ · push 2026-08-22 · licenza NOASSERTION (BSD-style)
- **Stato**: installato. Keep.

### 16. Keras / TensorFlow
- **Metadati**: keras 64.245★ Apache-2.0; tensorflow 197.213★ Apache-2.0.
- **Verdetto registrato**: ridondanti con torch nel nostro stack.

### 17. rustworkx / networkx
- **Metadati**: rustworkx 1.744★ Apache-2.0 push 2026-08; networkx 17.210★
  push 2026-08-21.
- **Copre**: grafi (correlazioni, cluster asset).
- **Per adottare**: networkx è leggero e utile per R11 (clustering HRP già
  in pyportfolioopt); hold.

## C.2 — Computation (13 voci)

### Ray (ray-project/ray)
- **Metadati**: 43.577★ · push 2026-08-22 · Apache-2.0 · Py/C++
- **Copre**: R6/R10 parallelismo distribuito.
- **Limiti**: single-machine basta; overhead operativo.
- **Per adottare**: hold; joblib/multiprocessing coprono.

### csp (Point72/csp)
- **Metadati**: 432★ · push 2026-08-19 · Apache-2.0 · Py/C++
- **Copre**: R16 (stream processing reattivo, produzione Point72).
- **Per adottare**: candidato serio per la pista real-time/streaming;
  Apache-2.0; verificarne l'ergonomia.

### Dask (dask/dask)
- **Metadati**: 13.894★ · push 2026-08-17 · BSD-3-Clause
- **Verdetto registrato**: polars copre; hold.

### Spark (apache/spark)
- **Metadati**: 43.852★ · Apache-2.0 · Scala
- **Verdetto registrato**: JVM, fuori scala/progetto.

### Hamilton (apache/hamilton, ex dagworks)
- **Metadati**: 2.574★ · push 2026-08-19 · Apache-2.0 · Py
- **Copre**: R1/R4 (dataflow DAG per feature pipeline).
- **Forza**: Apache-2.0, attivo, pensato per dataframes+ML.
- **Per adottare**: candidato per la pipeline fattori (alternativa a
  orchestrazione ad-hoc).

### Incremental (janestreet/incremental)
- **Metadati**: 1.497★ · push 2026-07-10 · MIT · OCaml
- **Verdetto registrato**: OCaml; valore concettuale (self-adjusting
  computation) per R16, non adozione.

### Joblib (joblib/joblib)
- **Metadati**: 4.386★ · push 2026-08-19 · BSD-3-Clause
- **Stato**: transitivo (sklearn). Keep come parallelismo semplice.

### Tributary (1kbgz/tributary)
- **Metadati**: 466★ · push 2026-06-23 · Apache-2.0 · Py
- **Nota**: il catalogo linka timkpaine/tributary (redirect → 1kbgz).
- **Copre**: R16 (streaming dataflow).
- **Per adottare**: alternativa a csp da confrontare.

### GraphKit (yahoo/graphkit)
- **Metadati**: 92★ · push 2023-03 · Apache-2.0 · il catalogo lo marca
  "No activity".
- **Verdetto registrato**: morto.

### Man MDF (man-group/mdf)
- **Metadati**: 183★ · push 2016-12 · MIT · catalogo "No activity".
- **Verdetto registrato**: morto (2016).

### Anchors C++ (oluwatimilehin/anchors)
- **Metadati**: 23★ · push 2022-10 · licenza NONE · catalogo "No activity".
- **Verdetto registrato**: morto + licenza assente.

### Anchors Rust (lord/anchors)
- **Metadati**: 137★ · **archived** · push 2026-01 · licenza NONE.
- **Verdetto registrato**: archived.

### Loman (janushendersonassetallocation/loman)
- **Metadati**: 119★ · push 2026-08-18 · BSD-3-Clause · catalogo "No activity"
  (ma push recente?).
- **Verdetto registrato**: attività minima; DAG research calc — hold.

## C.3 — Performance boosters (10 voci)

### cython (cython/cython)
- **Metadati**: 10.830★ · push 2026-08-22 · Apache-2.0
- **Stato**: toolchain già usata (talib wrapper). Keep come dev tool.

### numba (numba/numba)
- **Metadati**: 11.125★ · push 2026-08-21 · BSD-2-Clause
- **Stato**: transitivo via vectorbt. Keep.

### pybind11 (pybind/pybind11)
- **Metadati**: 17.999★ · push 2026-08-19 · licenza NOASSERTION (BSD)
- **Verdetto registrato**: solo se si scrive C++; hold.

### pyo3 (PyO3/pyo3)
- **Metadati**: 16.058★ · push 2026-08-21 · Apache-2.0/MIT
- **Verdetto registrato**: solo se pista Rust; hold.

### CuPy (cupy/cupy)
- **Metadati**: 12.265★ · push 2026-08-20 · MIT
- **Verdetto registrato**: GPU assente; no.

### CuDF (NVIDIA/cudf)
- **Metadati**: 9.733★ · push 2026-08-22 · Apache-2.0
- **Verdetto registrato**: GPU; no.

### codon (exaloop/codon)
- **Metadati**: 16.830★ · push 2026-08-22 · Apache-2.0
- **Verdetto registrato**: compilatore Python LLVM; sperimentale; hold.

### Bottleneck (pydata/bottleneck)
- **Metadati**: 1.181★ · push 2026-08-09 · BSD-2-Clause
- **Verdetto registrato**: pandas accel; polars non ne ha bisogno.

### NumExpr (pydata/numexpr)
- **Metadati**: 2.534★ · push 2026-08-17 · MIT
- **Verdetto registrato**: idem.

### pandarallel (nalepae/pandarallel)
- **Metadati**: 3.800★ · push 2024-07 · BSD-3-Clause
- **Verdetto registrato**: fermo; polars copre.

## C.4 — Profilers (3 voci)

### py-spy (benfred/py-spy)
- **Metadati**: 15.445★ · push 2026-08-14 · MIT · Rust
- **Copre**: R19 (sampling profiler, zero instrumentation).
- **Per adottare**: dev-tool candidato P3.

### pyinstrument (joerick/pyinstrument)
- **Metadati**: 8.005★ · push 2026-08-04 · BSD-3-Clause
- **Copre**: R19.
- **Per adottare**: dev-tool candidato P3.

### Memray (bloomberg/memray)
- **Metadati**: 15.198★ · push 2026-08-21 · Apache-2.0
- **Copre**: R19 (memory profiler).
- **Per adottare**: dev-tool candidato P3.

## C.5 — Alternative numpy/pandas (6 voci)

### ndarray (rust-ndarray)
- **Metadati**: 4.312★ · push 2026-07-18 · Apache-2.0/MIT · Rust
### faer (sarah-quinones/faer-rs)
- **Metadati**: 2.564★ · push 2026-06-24 · MIT · Rust
### DataFrame C++ (hosseinmoein/DataFrame)
- **Metadati**: 2.977★ · push 2026-08-21 · BSD-3-Clause · C++
### Vaex (vaexio/vaex)
- **Metadati**: 8.508★ · push 2026-04-01 · MIT · Py/C++
### Modin (modin-project/modin)
- **Metadati**: 10.389★ · push 2026-02-10 · Apache-2.0
### Koalas (databricks/koalas)
- **Metadati**: 3.371★ · push 2024-03 · Apache-2.0 · assorbito in PySpark.
- **Verdetto di sezione**: nessuno necessario — stack polars+numpy già
  definito; registrati come dato (Vaex out-of-core è l'unico concetto
  utile se il lake supera la RAM).

## C.6 — Visualization (11 voci)

### 1. matplotlib
- **Metadati**: 23.106★ · push 2026-08-22 · licenza PSF/BSD-like · Py
- **Stato**: installato. Keep.

### 2. seaborn (mwaskom/seaborn)
- **Metadati**: 14.007★ · push 2026-07-06 · BSD-3-Clause
- **Per adottare**: keep/hold per report statici.

### 3. Dash (plotly/dash)
- **Metadati**: 24.379★ · push 2026-08-21 · MIT
- **Copre**: R18 (data apps Python, no JS).
- **Per adottare**: candidato se la UI greenfield è Python-only; si
  confronta con la dashboard React già esistente in Oracle.

### 4. Perspective (perspective-dev/perspective, FINOS)
- **Metadati**: 11.127★ · push 2026-08-10 · Apache-2.0 · C++/Rust/Py
- **Copre**: R18 (grid interattiva streaming-friendly per dataset grandi).
- **Forza**: pensato esattamente per grandi dataset finanziari streaming.
- **Per adottare**: candidato per la pagina dati/factory della UI.

### 5. Streamlit (streamlit/streamlit)
- **Metadati**: 45.583★ · push 2026-08-22 · Apache-2.0
- **Stato**: extra dashboard in Oracle.
- **Per adottare**: rapido prototyping UI; produzione = altro.

### 6. gradio (gradio-app/gradio)
- **Metadati**: 43.401★ · push 2026-08-22 · Apache-2.0
- **Per adottare**: solo per demo modelli; hold.

### 7. pylatex (JelteF/PyLaTeX)
- **Metadati**: 2.354★ · push 2024-07 · MIT
- **Verdetto registrato**: report PDF; nicchia.

### 8. D-Tale (man-group/dtale)
- **Metadati**: 5.215★ · push 2026-07-24 · LGPL-2.1 · JS/Py
- **Copre**: R18/R4 (esplorazione dataframe).
- **Limiti**: LGPL; tool di esplorazione, non produzione.
- **Per adottare**: dev-tool per esplorazione lake.

### 9. mplfinance (matplotlib/mplfinance)
- **Metadati**: 4.427★ · push 2024-08 · licenza NOASSERTION · Py
- **Copre**: R18 (candlestick).
- **Limiti**: fermo 2024 ma completo.
- **Per adottare**: candlestick nei report; verificare licenza.

### 10. KLinePic
- **Metadati**: sito + repo esempi **GONE_404** (klinepic-agent-api-examples).
- **Verdetto registrato**: repo esempi sparito; SaaS.

### 11. btplotting (happydasch/btplotting)
- **Metadati**: 385★ · push 2025-05 · GPL-3.0 · Py/bokeh
- **Verdetto registrato**: plotting per backtrader; GPL; nicchia.

## C.7 — Message Queues (3 voci)

### Kafka (apache/kafka)
- **Metadati**: 33.582★ · push 2026-08-21 · Apache-2.0 · Java
### RedPanda (redpanda-data/redpanda)
- **Metadati**: 12.466★ · push 2026-08-22 · licenza NONE (BSL-like!) · C++
- **Nota licenza**: RedPanda è Business Source License, non OSS pieno —
  il probe riporta NONE; da confermare prima di qualsiasi uso.
### BlazingMQ (bloomberg/blazingmq)
- **Metadati**: 3.206★ · push 2026-08-21 · Apache-2.0 · C++
- **Verdetto di sezione**: R16 già coperto da NATS (scelta ADR-001 di
  Oracle); MQ pesanti = over-engineering per un progetto single-machine.
  Registrati tutti come dati.

## C.8 — Databases (9 voci)

### 1. ArcticDB (man-group/ArcticDB)
- **Metadati**: 2.486★ · push 2026-08-21 · licenza NOASSERTION (Apache-2.0
  con eccezioni — da leggere) · C++/Py
- **Copre**: R4 (DataFrame DB serverless per timeseries).
- **Forza**: progettato per dati finanziari (Man Group); versioning nativo.
- **Per adottare**: candidato per lo storage fattori/risultati; licenza
  da leggere con attenzione.

### 2. DuckDB (duckdb/duckdb)
- **Metadati**: 40.523★ · push 2026-08-20 · MIT · C++/Py
- **Stato**: installato (extra analytics). Keep. R4 analytics SQL sul lake.

### 3. lance (lance-format/lance)
- **Metadati**: 6.961★ · push 2026-08-22 · Apache-2.0 · Rust
- **Copre**: R4 (columnar ML-native, random access veloce, versioning).
- **Per adottare**: hold; interessante se il lake diventa feature-store.

### 4. Arctic (man-group/arctic)
- **Metadati**: 3.085★ · push 2024-04 · LGPL-2.1 · Py
- **Verdetto registrato**: predecessore di ArcticDB; manutenzione minima.

### 5. PyStore (ranaroussi/pystore)
- **Metadati**: 612★ · push 2026-04 · Apache-2.0 · Py
- **Verdetto registrato**: parquet-store semplice; ridondante col lake.

### 6. Marketstore (alpacahq/marketstore)
- **Metadati**: **GONE_404** — repo cancellato/spostato (probe 2026-08-22).
- **Verdetto registrato**: il catalogo linka un repo morto.

### 7. Tectonicdb (0b01/tectonicdb)
- **Metadati**: 752★ · push 2024-01 · licenza NOASSERTION · Rust
- **Copre**: R4/R8 (DB compresso per tick/order book + streaming protocol).
- **Limiti**: fermo 2024; licenza da leggere.
- **Per adottare**: candidato solo con pista L2.

### 8. Redis (redis/redis)
- **Metadati**: 76.068★ · push 2026-08-20 · licenza NOASSERTION (ora
  dual-license RSALv2/SSPL — NON più BSD!) · C
- **Nota importante**: il catalogo lo presenta come classico, ma Redis dal
  2024 ha licenza non-OSS (RSAL/SSPL) — fatto registrato.
- **Per adottare**: no; Postgres + NATS coprono.

### 9. kdb (KxSystems)
- **Metadati**: repo companion (q language).
- **Verdetto registrato**: kdb+ è commerciale; i repo OSS sono solo
  utilità; non adottabile come DB.

## Riepilogo lotto C

| Sezione | Candidati | Dati registrati |
|---|---|---|
| Fundamental libs | PyMC, Hamilton | stack già coperto al 90% |
| Computation | csp, Tributary (streaming R16) | Ray/Dask/Spark ridondanti |
| Performance | numba (già), cython (già) | GPU esclusa |
| Profilers | py-spy, pyinstrument, Memray (dev) | — |
| Alternatives | nessuna (polars basta) | Vaex concept |
| Visualization | Perspective, Dash, mplfinance, D-Tale | — |
| MQ | nessuna (NATS resta) | RedPanda BSL! |
| Databases | ArcticDB, lance, Tectonicdb (condizionale) | marketstore 404; Redis non-OSS |

**Prossimo lotto**: D = Data Source (17+6+14+8 voci) — il più critico per
"avere tutto quello che serve".
