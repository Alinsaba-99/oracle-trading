# Project Review — 2026-07-20 (seconda review, post-M31)

> Review sistematica read-only. Metodo: 3 stream paralleli (core/execution/policy/market,
> analytics/genetics/research, deployable-surfaces/UI) + quality gate eseguiti localmente
> + probe deterministici. Findings verificati con esecuzione reale dove indicato.

## 1. Executive assessment

**Livello: research-grade con regressione di baseline. NON production-ready, NON deployabile.**

Lo stato dichiarato in PROJECT.md ("research-grade con paper test; live non autorizzato") è onesto,
ma tre fatti peggiorano il quadro rispetto alla baseline del 18 luglio:

1. **Baseline regredita**: 26 test falliti (vs 0 dichiarati), 143 errori ruff (vs "Pass"),
   13 errori mypy (vs 0 con override). Nessun run CI remoto recente che abbia intercettato la regressione.
2. **Lo stack Docker non parte**: `infra/docker/db/schema.sql` non esiste → postgres init fallisce
   → tutti i servizi `depends_on: service_healthy` restano fermi.
3. **La dashboard è rotta in produzione**: con auth attiva (default compose) ogni chiamata API
   dal browser riceve 401; lo stream SSE non ha alcun producer; le route SPA danno 404
   quando servite dall'API.

I buchi critici di dominio sono tutti nel path che dovrebbe diventare live (OMS, fill accounting,
risk bypass, feed dati, timing backtest). La direzione architetturale (mode guard, risk gate
obbligatorio nel costruttore, operatori GA causali) è buona e va preservata.

## 2. Quality gate eseguiti

| Gate | Risultato 20 luglio | Baseline 18 luglio |
|---|---|---|
| pytest (`-m "not slow"`) | **26 failed**, 1857 passed, 1 skipped | 1605 passed, 2 skipped |
| ruff check | **143 errori** (28 F401, 26 UP017, 17 I001, 15 ARG001, ...) | Pass |
| ruff format | non rieseguito (no write in review) | 397 file |
| mypy strict | **13 errori in 5 file** | 0 (con override) |
| uv lock --check | non rieseguito | Pass |

Fallimenti pytest principali:
- `tests/api/test_endpoints.py` — 401 invece di 200 (env-dependent: con ORACLE_API_KEY
  settata i test non-auth falliscono; fixture non isola la config).
- `tests/genetics/test_operators.py` (6) — **test stale**: asseriscono la vecchia semantica
  full-array; gli operatori sono stati correttamente convertiti a causali/expanding in b98af40
  (prefix-invariance verificata con probe; `test_operators_causal.py` 36 verdi). Codice giusto,
  test da aggiornare.
- `tests/execution/test_paper_broker.py` (3) — **test stale**: assumono ordine aperto dopo
  submit; PaperBroker fila immediatamente (market simulation).
- `tests/unit/test_market_sources.py::test_parse_kline_valid` — KeyError `is_final`: parser
  Binance e test disallineati.
- `tests/unit/test_challenge_simulator.py::test_min_trading_days_blocks_premature_pass` — da investigare.

Errori mypy principali:
- `agents/committee/fund_manager.py:84` — kwarg `trigger` inesistente su `PortfolioPlan`
  (possibile bug runtime vero nel committee agent).
- `market/realtime.py:95-150` — API ib_insync usata male (`IB` in typed context,
  `MarketDataType` inesistente).
- `core/observability.py:114-128`, `market/sentiment.py`, `market/data_sources.py:145`.

## 3. Findings — BLOCKER

### B1. avg_fill_price non è media pesata — e il test codifica il bug come atteso
`execution/order_manager/manager.py:200` e `core/oms.py:194`: `order.avg_fill_price = fill.price`
(ultimo fill). Test `tests/execution/test_order_manager.py:456` asserisce il valore sbagliato
(30@150 + 70@151 → atteso 151.00 invece di 150.70).
**Impatto**: P&L sbagliato su ogni ordine con fill parziali; risk governor e ledger divergenti dal broker.
**Fix**: `avg = (old_avg*old_qty + price*qty) / new_filled`; correggere entrambi i siti e il test.

### B2. Kill switch e script operativi bypassano risk/OMS
`core/kill.py:64-72` — flatten invia dict raw diretto al broker (no OMS, no idempotenza, no ledger;
con MT5 il parsing duck-typed di un dict fallisce → flatten che fallisce silenziosamente nel momento
del bisogno). `scripts/run_paper_session.py:115` — submit diretto senza OrderManager né risk.
`showcase.py:574` — `OrderManager(paper)` con 1 arg (firma attuale ne richiede 2 → codice rotto).
**Fix**: fast-path emergenza che conserva idempotenza + ledger + reconcile immediato post-flatten.

### B3. MT5 cancel_order perde lo stato prima della conferma
`execution/brokers/metatrader.py:380` — `self._open.pop(broker_order_id)` PRIMA di `order_send`.
Se il REMOVE fallisce, l'ordine resta vivo sul server ma sparisce localmente → zombie order,
kill_all non lo vede più.
**Fix**: pop solo dopo retcode OK; su failure re-inserire e segnalare FATAL.

### B4. Trade short misclassificati come long nel trade log (VERIFICATO eseguendo vectorbt)
`analytics/backtest/engines/vectorized.py:336` — `direction_val in (0, 1) → long`, ma vectorbt
usa `direction=1` per SHORT. Ogni short diventa long nel `Trade` di dominio: analisi per-direzione,
report e dashboard invertiti.
**Fix**: `long if direction_val == 0 else short`.

### B5. Fitness cache GA con chiavi incomplete → il GA evolve contro numeri di un'altra config
`genetics/fitness/evaluator.py:105-116,224-235` + `cache.py:24-33`: la chiave non include
`split_method`, niente di `BacktestConfig` (slippage, commissioni, capitale), né `train_size`
(pybroker); fingerprint dati = shape + prime 10 righe di close (collisioni su dati ristampati).
**Fix**: chiave = split_method + backtest_config.model_dump() + hash completo/campionato dati.

### B6. GA senza holdout intoccato né multiple-testing correction; cap MaxDD su media fold
`genetics/engine.py:132-308` (tutto il data al fitness), `evaluator.py:281` (cap `maxdd>0.50`
sul MEAN per-fold DD: un fold al 90% DD con quattro al 5% dà media 22% e passa),
nessun DSR/Bonferroni/White reality-check in `analytics/qualification/`. La doc dichiara
"Impedire accesso GA al final holdout" ma il codice non lo implementa.
**Fix**: holdout sigillato prima di `GeneticEngine.run`; cap su OOS concatenato; DSR/SPA in qualification.

### B7. docker-compose non parte: db/schema.sql mancante
`infra/docker/docker-compose.yml:14` monta `./db/schema.sql` — il file non esiste → postgres
init fallisce → api/scheduler (depends_on healthy) non partono mai. **VERIFICATO**.

### B8. Dashboard 401 in produzione + healthcheck Docker fallisce con auth (VERIFICATO live)
`apps/api/main.py:94-105` richiede X-API-Key su `/api/`; il browser non la manda
(`apps/dashboard/src/lib/api.ts`) → ogni pagina UI è un error banner. Bonus: healthcheck
compose/Dockerfile fa `curl /api/health` senza key → container `unhealthy` permanente.
**Fix**: esentare `/api/health` e `/metrics`; per la UI: session cookie o esenzione same-origin
(`sec-fetch-site: same-origin`) o token iniettato in index.html.

## 4. Findings — HIGH

### H1. OrderManager: stato in-memory, idempotenza volatile, race su submit
`manager.py:34-37` — restart = perdita idempotenza (doppio ordine dopo crash tra submit e response).
`submit` senza lock: due coroutine stesso request_id → check-then-act race → doppio ordine.
`core/oms.py` (InMemoryOMS, più corretto) NON è usato da OrderManager: due OMS paralleli con
bug diversi. CLI trade non persistente: `submit` in un processo, `list` in un altro → vuoto;
`kill` inutile cross-process.

### H2. SSE /api/v1/stream/positions senza producer (VERIFICATO: zero chiamanti di broadcast)
`apps/api/ws.py:31` — mai chiamato. La dashboard paga polling + SSE morto; `ConnectionBadge`
inutilizzato, header con pallino "Connected" hardcoded sempre verde (`layout.tsx:111-114`).

### H3. Feed Polygon: nessun reconnect, nessun gap-detection, fallback REST = dati di IERI
`market/realtime.py:399-407` — su errore recv lo stream muore silenziosamente (Binance invece ha
backoff+reconnect). Fallback REST usa `/prev` (barra del giorno precedente spacciata per live,
dedup per price-change le rende quasi tutte identiche). Nessuna validazione timestamp.
API key in chiaro nell'URL (`:464`, `data_sources.py:227`) → leak nei log httpx; `pd.to_datetime`
naive senza UTC (`:238`) → join/shift silenziosi con feed tz-aware.

### H4. Broker CCXT/IBKR: errori di trasporto trasformati in falsi successi
`ccxt_broker.py:60-89` — cancel→False, status→"unknown", positions→`[]` su QUALSIASI eccezione
(incluse auth error / exchange down): durante un outage il book sembra flat al risk governor.
`ibkr.py:30-34,63` — connect/placeOrder bloccanti nell'event loop; `stream_orders` stub vuoto
→ fill mai consegnati, OrderManager resta su submitted, IBKR non espone get_fills → mai riconciliato.
**Fix**: eccezioni tipizzate (BrokerUnavailableError), mai `[]`/`unknown` su errori di trasporto.

### H5. Timing esecuzione divergente tra i 3 engine + look-ahead nel fallback Nautilus
Vectorized: shift 1 barra (corretto). PyBroker (`pybroker_integration.py:85-102`): esegue il
segnale della barra CORRENTE senza shift, sizing fisso 100 shares. Nautilus: coerente nel path
principale ma `nautilus.py:316-328` usa `sig[i+1]` per tradare a `closes[i]` → look-ahead di 1
barra nell'equity ricostruita; sizing 95% free cash. Tre engine, tre semantiche → i parity check
M31 non sono comparabili.

### H6. Annualizzazione hardcoded a 252 ovunque
`metrics.py:25,55,90,109,160,179`; `walk_forward.py:167-174` (ricalcola fold con 252 mischiando
metriche freq-aware e non); `bias.py:37-44,241`. Su dati intraday Sharpe gonfiato di √(barre/giorno).
Se `pd.infer_freq` fallisce, vectorbt riceve `freq=None` → Sharpe per-barra silenzioso.

### H7. WalkForwardEngine ignora train_idx/purge; CPCV costruisce equity su dati non contigui
`walk_forward.py:107-117` — scarta gli indici dello splitter: purge mai applicato; in CPCV il
"prefisso" include test block futuri (leakage per qualsiasi fitting sul prefisso, es. HMM);
`test_data` splice di blocchi non contigui passato a vectorbt come serie continua → salti finti
nell'equity ai confini dei blocchi.

### H8. Regime HMM fittato full-sample → label di regime con look-ahead
`regime/detector.py:90-93,114-135` + `detectors/hmm.py:87,110-129` — Viterbi smoothed full-sample:
la state alla barra t usa le barre successive. Se le label alimentano feature backtestate sullo
stesso periodo è leakage puro. **Fix**: forward-filtering o walk-forward refit con embargo.

### H9. Resume GA da checkpoint rompe riproducibilità RNG; RNG globale tra isole concorrenti
`islands.py:446-458` (checkpoint non salva `rng.getstate()`), `islands.py:253` (`_random.seed`
globale), `operators/__init__.py:73` e `selection.py` (DEAP usa random globale) mentre le isole
girano in `asyncio.to_thread` → stesso seed, risultati diversi tra run e tra resume.

### H10. Reconciliation engine fragile e mai enforced
`core/reconciliation.py:139,222-224` — accesso a privati duck-typed con fallback silenzioso (check
saltato = report "clean"); confronto posizioni solo lato broker; `_blocked` informativo: NESSUN
componente consulta `is_blocked()` prima di submit (zero chiamanti); zero test unit.
Anche: SPA routing rotto via API (`GET /trades` → 404, verificato); dati API assenti nel container
(path hardcoded `checkpoints/`, `experiments/`, `results/`, `data/` non copiati né montati; config
`checkpoint_dir`/`data_dir` esiste ma i service la ignorano); endpoint live stub 503 che la UI
poll-a ogni 30s (`/trades/positions`, `/performance/today`).

## 5. Findings — MEDIUM/LOW (selezione)

- M1. SQLite: nessun WAL, nessun busy_timeout, connessioni leakate su eccezione
  (`trade_service.py:18,127`), nessuna transazione multi-statement; Postgres citato ma mai usato.
- M2. Sortino con downside deviation sui soli rendimenti negativi → sovrastima sistematica;
  `inf` con zero perdite → fold perfetti diventano fitness -1 nel GA (`metrics.py:70-90`,
  `evaluator.py:246-252`).
- M3. Sharpe CI con n = #trade invece di #periodi (`bias.py:80-84,162`); MC evaluation con
  finestre sovrapposte stride=5<window=130 → mc_pass_rate troppo ottimista (`evaluation.py:102`).
- M4. `_EMPTY_FITNESS=(-1,-1,-1,1.0)` può dominare genomi legittimi peggiori (`evaluator.py:53`);
  `random_seed=42` hardcoded nell'ExperimentContext → provenance falsa (`evaluator.py:124`).
- M5. PyBroker: segnale pre-computato una volta su full data prima del walkforward → leakage
  per segnali stateful (`pybroker_integration.py:52-53`).
- M6. Config API: nessun `.env` loading, `debug=True` default (fail-closed production guard mai
  attivo), `/metrics` hardcoded a 0 (Prometheus scrapa dati finti), scheduler compose è
  `sleep 3600 || true` che maschera errori, CORS hardcoded localhost:5173.
- M7. Intelligence inbox write-only (POST senza GET, nessun consumer, nessuna pagina UI).
- M8. `policy/engine/` e `policy/definitions/` vuoti — la "policy engine" pubblicizzata non esiste;
  esiste solo `policy/prop_firm/`.
- M9. Test API env-dependent: con ORACLE_API_KEY settata nell'ambiente i test non-auth falliscono
  (401) — fixture non isola la config.
- M10. mypy `fund_manager.py:84` kwarg `trigger` inesistente su PortfolioPlan — verificare a runtime.

## 6. UI GAP — dashboard attuale (esiste già: React 18 + Vite + TS, 3 pagine)

La dashboard NON va creata da zero: esiste in `apps/dashboard/` con pagine Dashboard / Trades / GA
e 15 test verdi. Va fatta evolvere e collegata a dati veri.

**Rotto oggi:**
- Auth: 401 su tutte le API in produzione (B8) — bloccante.
- SSE morto (H2) — la UI è polling-only; indicatore connessione finto (sempre verde).
- SPA 404 via API (H10); dati assenti nel container (H10); endpoint 503 poll-ati (H10).

**Pagine mancanti per una UI operativa production-grade:**
1. Positions page (hook e tipi esistono già, manca la route).
2. Risk monitoring — drawdown vs limiti, daily loss, esposizione, stato prop-firm rules.
3. Kill switch UI — cancel-all / flatten con conferma (richiede H1: persistenza ordini).
4. Order blotter + order entry manuale (oggi UI 100% read-only).
5. Intelligence inbox viewer (ElizaOS scrive, nessuno legge).
6. Settings/status — mode corrente (research/paper), auth, versione, health servizi.
7. Alerts — notifiche su breach di rischio.
8. Onboarding — empty state che guida ("come popolare: oracle backtest run ...").

## 7. Punti di forza da preservare

- Mode guard con isolamento credenziali (`core/domain/guard.py`) — ben fatto.
- Risk gate obbligatorio nel costruttore di OrderManager e PortfolioBridge (rifiuta None).
- PropFirmRiskGovernor deterministico e fail-closed (rifiuta se manca market spec o stop).
- Operatori GA causali/expanding corretti (prefix-invariance testata, 36 test verdi).
- Shift anti-look-ahead corretto nel vectorized engine (`vectorized.py:185`).
- InMemoryOMS ha idempotenza client_order_id, dedup fill, blocco transizioni all'indietro
  (va promosso a OMS unico durevole).
- Prop-firm profiles versionati con fonti hashate; RESEARCH_ONLY bloccato su path live.

## 8. Piano di remediation priorizzato

**Settimana 1 — ripristino baseline (bloccante per tutto il resto):**
1. Aggiornare test stale (operators, paper_broker) e fixare market_sources/challenge_simulator.
2. `ruff check --fix` + risolvere i restanti; fix mypy (fund_manager, realtime, observability).
3. Test API: isolare la config auth nelle fixture (monkeypatch settings).
4. Fix B1 (weighted avg fill price, entrambi i siti + test) — 30 minuti, altissimo valore.
5. Fix B4 (direction mapping vectorbt) — 5 minuti, corregge tutti i trade log.
6. CI: far passare il gate remoto e renderlo bloccante su PR.

**Settimana 2 — deployabilità:**
7. Creare `infra/docker/db/schema.sql` (B7); esentare `/api/health` e `/metrics` da auth (B8).
8. Auth UI: esenzione same-origin o session cookie (B8); SPA fallback 404→index.html.
9. Unificare serving dashboard (una sola: o nginx o API static mount).
10. Volumi compose per checkpoints/results/data + service che usano `settings.*_dir`.

**Settimana 3 — OMS durevole (sblocca CLI, kill switch UI, reconciliation):**
11. Unificare OrderManager su OMS durevole (SQLite WAL ora, Postgres dopo): ordini, seen_fills,
    seen_requests persistiti; asyncio.Lock su request_id (H1).
12. CLI trade legge/scrive lo store durevole → list/status/kill cross-process funzionanti.
13. Fix MT5 cancel (B3); broker exceptions tipizzate (H4).
14. Reconciliation: protocolli espliciti, confronto bidirezionale, `is_blocked()` consultato
    nel path di submit, test unit (H10).

**Settimana 4 — truth del research (prerequisito a fidarsi dei numeri):**
15. Fix cache key fitness GA (B5); holdout sigillato + cap MaxDD su OOS concatenato (B6).
16. RNG per-isola serializzato in checkpoint (H9).
17. Annualizzazione dalla frequenza reale (H6); Sortino corretto + clamp inf (M2).
18. Walk-forward: rispettare train_idx/purge; CPCV per blocchi contigui (H7); HMM causale (H8).
19. Allineare timing/sizing dei 3 engine o dichiarare un solo engine di qualification (H5).

**Settimana 5 — real-time + UI operativa:**
20. Feed Polygon: reconnect+backoff, gap detection, fallback su last-trade, timestamp UTC,
    key in header (H3).
21. SSE producer: OrderManager/risk pubblicano su sse_manager; heartbeat; ConnectionBadge reale.
22. UI: Positions, Risk, Kill switch, Order blotter, Settings (vedi §6).
23. `/metrics` reale (prometheus-client); scheduler reale o rimosso; `.env` loading.

**Scope non verificato:** broker reali (IBKR/CCXT/MT5 solo lettura codice), infrastruttura
k8s/terraform, integrazione ElizaOS oltre al publisher, CI remota (nessun run ispezionato).
