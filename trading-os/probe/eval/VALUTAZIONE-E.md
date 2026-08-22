# VALUTAZIONE E — Broker APIs + Quant Shops + Resources + crypto_focus residuo

> Lotto 5 di 6 (penultimo). Copre Broker APIs, Quant Shops, Resources
> (research/books/blogs/tutorials/courses), Relevant Projects e le voci di
> crypto_focus.md non ancora valutate nei lotti precedenti.

## E.1 — Broker APIs (9 voci)

### 1. ib_insync (erdewit/ib_insync) ⚠️
- **Metadati**: 3.284★ · push 2024-03-14 · **ARCHIVED** · BSD-2-Clause
- **Dà**: Python sync/async framework per Interactive Brokers API.
- **Stato**: il repo originale è **archiviato** (l'autore ha smesso).
- **Fork vivo**: **`ib-api-reloaded/ib_async`** (1.716★ · push 2026-08-19 ·
  BSD-2-Clause) — è il successore de facto mantenuto dalla community.
- **Verdetto**: il catalogo linka il repo ARCHIVIATO. Nel greenfield si usa
  `ib_async` (ib-api-reloaded). Fatto critico registrato.

### 2. PENDAX (CompendiumFi/PENDAX-SDK)
- **Metadati**: 49★ · push 2024-05 · licenza NONE · JS
- **Dà**: JS SDK per FTX (morto), OKX, Bybit…
- **Verdetto**: licenza assente, fermo, FTX riferimento morto. No.

### 3. ccxt (ccxt/ccxt) ⭐
- **Metadati**: 43.691★ · push 2026-08-22 · MIT
- **Dà**: API unificata per 100+ exchange crypto (REST + WS).
- **Stato**: già installato in Oracle.
- **Verdetto**: keep; è lo standard de facto per connettività crypto.

### 4. Coinnect (hugues31/coinnect)
- **Metadati**: 158★ · push 2021-11 · MIT · Rust
- **Verdetto**: Rust, fermo 2021; ccxt copre. No.

### 5. async_rithmic (rundef/async_rithmic)
- **Metadati**: 114★ · push 2026-08-21 · MIT
- **Dà**: Python async per Rithmic Protocol Buffer API (futures).
- **Costo**: Rithmic = dati a pagamento (data feed fee).
- **Verdetto**: il codice è MIT ma il servizio Rithmic è paid → fuori $0.
  Registrato come opzione futures solo se si paga Rithmic.

### 6. pmxt (pmxt-dev/pmxt)
- **Metadati**: 2.092★ · push 2026-07-18 · MIT · JS/Py
- **Dà**: "il ccxt dei prediction markets" — API trading PM multi-exchange.
- **Verdetto**: rilevante solo se si apre pista PM. MIT, attivo. Hold.

### 7. PolyClawster (al1enjesus/polyclawster)
- **Metadati**: 21★ · push 2026-03-16 · licenza NONE · JS
- **Verdetto**: licenza assente, minuscolo, PM. No.

### 8. NanoStack (api.nano-labs.io)
- **Dà**: execution fabric cross-chain 86 chain, no key.
- **Verdetto**: infrastruttura DeFi execution; fuori tesi spot. Registrato.

### 9. polymarket-whales (al1enjesus/polymarket-whales)
- **Metadati**: 59★ · push 2026-03-20 · MIT
- **Dà**: tracker whale Polymarket, alerts terminal+Telegram.
- **Verdetto**: PM; MIT; piccolo. Hold se pista PM.

## E.2 — Quant Shops (5 voci)

Tutte materiale di lettura/riferimento, zero adozione codice.

| Shop | Cosa offre | Perché interessa |
|---|---|---|
| **JaneStreet** | blog, podcast, OSS (OCaml) | microstruttura, market-making, prob |
| **Man AHL** | blog, podcast, OSS (ArcticDB, D-Tale già visti) | systematic, trend, research process |
| **DE Shaw** | OSS (Python/TS/Rust/Nix) | computational finance |
| **Two Sigma** | engineering blog | data engineering, ML scale |
| **HRT** | engineering blog | low-latency, C++ |

- **Verdetto sezione**: R1/R5/R8 materiale di studio. Da indicizzare come
  fonti Stage-2. Nessun costo.

## E.3 — Resources

### Research (2)
- **RavenPack Insight**: research su news analytics. Provider commerciale;
  gli insight sono gratuiti. Registrato come fonte lettura.
- **Alexandria Technology Insight**: idem.

### Books (8)
| Libro/repo | Metadati | Nota |
|---|---|---|
| Building Low Latency Apps C++ | PacktPublishing, 700★ MIT | solo se pista low-latency |
| Quantitative Portfolio Management | Amazon link | libro, no repo |
| Algorithmic Trading with Python (Conlan) | 3.441★ · fermo 2021 | materiale base |
| Python for Algo Trading (Hilpisch) py4at | 849★ · fermo 2023 | Hilpisch = autorevole |
| Systematic Trading (Carver) = pysystemtrade | già in B | ✅ |
| ML for Algo Trading (Jansen) | 20.571★ · push oggi · MIT | **P0 materiale studio** |
| Advances in Financial ML (exercises) | 1.953★ · fermo 2022 · MIT | López de Prado, già nostro riferimento |
| ML for Asset Managers (emoen) | 660★ · MIT | López de Prado |

### Blogs (4)
- QuantBox (systematic trading toolbox) — lettura.
- 大富翁量化 (zillionare) — CN.
- Proof Engineering — Medium, engineering trading platform.
- KeepRule — knowledge base 500+ regole investing.

### Tutorials (2)
- Crypto trading tutorial (tudorelu) — fermo 2020.
- **Solo Crypto Quant Starter Kit (cryptomotifs/cipher-starter)**: playbook
  150 pagine per signal engine + bot Solana a **$0/mese**. Allineato al
  nostro vincolo $0. Registrato come riferimento metodologico.

### Courses (1)
- **Hudson & Thames** — "scientific method in investment management";
  implementazioni di López de Prado (mlfinlab-like). Riferimento P0 per
  la metodologia di qualificazione.

## E.4 — Relevant Projects + crypto_focus residuo

### Relevant Projects (dal README)
| Voce | Metadati | Verdetto |
|---|---|---|
| systematic-trading-knowledge-collection | 56★ · fermo 2023 | stesso autore; lettura |
| awesome-quant CN (thuquant) | 5.568★ · MIT | CN; indice |
| awesome-deep-trading (cbailes) | 2.030★ · fermo 2023 | indice ML trading |
| awesome-crypto-trading-bots (botcrypto-io) | 2.490★ · CC0-1.0 · push 2026-08 | **indice aggiornato** crypto bot — materiale Stage-2 |
| CongressionalStockBrain | già in D.2 | probe |
| PolyMind | già in D.4 | 🟠 |
| EventTrader (cymetica) | SaaS | CLOB con 10 AI agents live; 🟠 claims |
| ToolsNova | web | calcolatori FX/gold; no |

### crypto_focus.md — voci non ancora valutate
| Voce | Metadati | Dà | Verdetto |
|---|---|---|---|
| perp-arbitrageur (perpetual-protocol) | **GONE_404** | arb perp/FTX | repo morto (FTX) |
| FTX funding arb scanner (staccDOTsol) | 17★ · fermo 2021 | scanner arb | FTX morto; storico |
| Liquidation Bot (HydroProtocol) | 40★ · fermo 2023 · Apache-2.0 · Go | DDEX liq bot | riferimento storico |
| T-1000 (Draichi) | 176★ · push 2026-08-19 · licenza NONE | DL + Ray | licenza assente |
| Tai (fremantle-industries) | 498★ · fermo 2024 · MIT · Elixir | market data + execution toolkit | Elixir fuori perimetro |
| bTrader (gabriel-milan) | 332★ · ARCHIVED · GPL-3.0 · Rust | triangle arb | già in A.3 |
| crypto-crawler-rs | 266★ · fermo 2023 · Apache-2.0 | già in A.3 | |
| cryptotrader-core | 25★ · fermo 2019 | già in A.3 | |
| openlimits | 322★ · fermo 2022 | già in A.3 | |
| Freqtrade / Hummingbot / Jesse / OctoBot / Kelp | già in A.3 | | |
| Blankly (blankly-finance) | 2.464★ · fermo 2024 · LGPL-3.0 | build/backtest/deploy multi-asset | LGPL; fermo |
| Peregrine (wardbradt) | 1.247★ · ARCHIVED · MIT | arb 131 exchange | archived |
| K (ctubio/Krypto-trading-bot) | 3.707★ · fermo 2024 · licenza NOASSERTION · C++ | MM HFT | C++; fermo |
| gocryptotrader (thrasher-corp) | 3.455★ · push 2026-08-21 · MIT · Go | Go trading bot multi-exchange | Go fuori perimetro; attivo |
| BBGO (c9s) | 1.658★ · push 2026-08-21 · AGPL-3.0 · Go | Go bot | AGPL+Go |
| golang-crypto-trading-bot (saniales) | 1.163★ · GPL-3.0 · Go | Go bot | GPL+Go |
| DeepAlpha | già in A.3 | | |
| Solana SDK Tools (DebuggingMax) | **GONE_404** | Solana DEX toolkit | repo morto |
| Microverse Systems | già in D.3 ⭐ | | |
| Signalview (mokshyaprotocol/signalview) | 3★ · MIT · Apache-2.0 | signal engine + backtester perp; strategy come espressione/JSON; Sharpe/DD/win-rate con fee/funding/leva | **interessante**: research library pura, Apache-2.0, `pip install perpsignal` |
| TrendRider (darkvolg) | 18★ · MIT · Py | Freqtrade strategy Bybit con exit ladder | 🟠 claim +69%/-77% da verificare |
| INDICIA DESK | SaaS | BTC/ETH options analytics, whale structures | 🟠 |
| perpsignal (= Signalview engine) | vedi sopra | | |
| FillBench | 0★ · NOASSERTION | benchmark latenza REST exchange (p50/p95/p99), dati aperti | **utile** per R14 slippage/latency calibration |
| FundingRadar (economic-agent) | 0★ · NONE · stdlib | ranking funding rate cross-exchange keyless | idea per fattore funding; licenza assente |
| RektCalc | web | 300+ calcolatori risk crypto | tool web; no |

## E.5 — Correzioni al catalogo emerse in questo lotto

1. **ib_insync → ARCHIVIATO**: usare `ib-api-reloaded/ib_async`.
2. **perp-arbitrageur, Solana SDK Tools**: GONE_404 (repo morti).
3. **marketstore, blackbird, helium-mcp** (dal lotto D/C): GONE_404.
4. **Signalview/perpsignal**: il catalogo li elenca due volte sotto nomi
   diversi; è lo stesso progetto.
5. **RedPanda**: licenza BSL, non OSS pieno (dal lotto C).
6. **Redis**: non più BSD, ora RSALv2/SSPL (dal lotto C).

**Prossimo (ultimo lotto)**: F = sintesi di copertura R1-R20, matrice dei
gap, e lista finale "cosa ci serve davvero" con le decisioni da prendere.
