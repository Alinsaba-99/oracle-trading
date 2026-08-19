# Live Readiness Gap Analysis — Execution vs Capitale Reale

> **STATUS**: assessment formale, 2026-08-10. Fix applicati lo stesso giorno:
> gap #1 (FRED vintage) e #3 (pessimistic-fill) RISOLTI; gap #2 (cvxpy)
> KEEP documentato. Vedi §2.2-2.4 per i dettagli.
> **Oggetto**: verificare le 5 "falle" ipotizzate per il passaggio research/paper →
> live/funded, contro lo stato reale del repo.
> **Metodo**: ogni claim è tracciato a file:line o report versionato. Nessuna
> conclusione basata su memoria.
> **Fonti**: ROADMAP.md · ORACLE_AUTOPILOT_STATUS.md · BACKLOG.md ·
> docs/plan-production-grade.md (commit `3bdef58`) · docs/reports/s0-1-bl023-autopsy.md ·
> docs/reports/s0-2-economic-model.md · docs/reports/multiasset/walkforward.md ·
> docs/reports/m31-rerun-final/m31.md · docs/ARCHITECTURE.md · docs/ADR/ADR-010 ·
> execution/* · core/* · policy/* · genetics/* · analytics/macro/fred.py ·
> analytics/backtest/engines/{nautilus,vectorized}.py · analytics/strategy/risk_sized.py

## 0. Verdetto esecutivo

**Le 5 falle proposte sono in gran parte già progettate (e in parte già
implementate) in questo repo: disaccoppiamento decision/execution, risk kernel
deterministico, OMS durevole con reconcile, kill switch separato. Anche lo
"stack istituzionale" esterno (nautilus, vectorbt, polars, ccxt, cvxpy) è già
installato — per la maggior parte già cablato (§2). La falla che l'analisi
ipotetica non vede è diversa: il sistema non ha ancora un edge verificato
(G5/G6 REJECTED), e il modello economico S0.2 quantifica l'obiettivo
"€3K/mese" come 5-16× sopra il soffitto di alpha misurato. Un bug reale è
stato comunque trovato: **lookahead bias FRED** (dati rivisti usati come
puntuali, §2.2).**

**Implicazione**: dedicare lo sprint all'hardening execution oggi non sblocca
nulla — il gate live (G7) è bloccato su G5/G6, non sull'architettura. La
sequenza corretta (già scritta nel piano production-grade S0→S6) è: chiudere
l'edge, poi il paper trade-producing, poi il live. L'hardening è lavoro
parallelo a bassa priorità, non prerequisito.

## 1. Le 5 falle ipotizzate → stato reale

### Falla 1 — Latenza / agenti nel critical path

**Ipotesi**: se analyst/committee/oracle (LLM o euristiche pesanti) sono nel
critical path tick→ordine, il sistema è morto per slippage.

**Stato reale**: la separazione è già il *design attuale*, non un gap.

| Evidenza | Dove |
|---|---|
| `OrderManager` dichiarato "deterministic, no LLM involvement" | `execution/order_manager/manager.py:1` |
| `TradeIntentBridge` ritorna `None` per REPLAY/SHADOW (mai ordine eseguibile) | `execution/order_manager/intent_bridge.py:18-20` |
| LLM/analyst/GA producono solo evidence o TradeIntent, mai ordini | ADR-010 §Decision (`docs/ADR/ADR-010-deterministic-execution-safety-boundary.md:23`) |
| hot path mode→risk→OMS→broker sincrona e in-process | `docs/ARCHITECTURE.md:99-103` |

**Gap residuo**: nessuno architetturale. La sincronia in-process (ARCHITECTURE
§3.2) è una scelta deliberata per il primo deployment: errori e transazioni
espliciti. La separazione in servizi è *ammessa solo dopo benchmark*, non
prescritta.

### Falla 2 — Overfitting GA / DEAP

**Ipotesi**: la fitness GA curve-fitta, i backtest ignorano impatto e slippage.

**Stato reale**: parzialmente addressed, e soprattutto il processo ha GIÀ
catturato il rischio descritto.

| Evidenza | Dove |
|---|---|
| Fitness supporta modalità `"cpcv"` (combinatorial purged) | `genetics/fitness/evaluator.py:43` |
| Penalità CAGR sotto soglia (x0.01) e profit factor soft | `genetics/fitness/evaluator.py:289-293` |
| Composizione fitness con penalità DD e turnover | `genetics/evolution.py:118-126` |
| N onesto = regimi × top-3 finestre × qty1 = 18 curve uniche | ADR-016 (grep `docs/ADR/ADR-016*.md:46`) |
| Dataset pinnato con sha256 in header dei report | `docs/reports/m31-rerun-final/m31.md:7` |
| Sweep 8 candidati → 8/8 REJECTED | BACKLOG.md BL-023 Fase 5c |
| Walk-forward multi-asset → 0/9 asset×segnale battono buy&hold | `docs/reports/multiasset/walkforward.md` |

**Gap reale**: manca un Deflated Sharpe Ratio esplicito e le penalità sono
moltiplicative/soft. Ma il rischio *è già materializzato e catturato*: il 0/9 e
l'8/8 sono la prova che il gate non lascia passare il curve-fitting. Il gap
CPCV/DSR è un raffinamento del processo, non la ragione per non fidarsi.

### Falla 3 — OMS / riconciliazione dello stato

**Ipotesi**: broker si disconnettono, fill parziali, orphan order; il bot deve
sapere cosa c'è a mercato dopo un crash.

**Stato reale**: lo scheletro è già implementato e in parte verificato.

| Evidenza | Dove |
|---|---|
| `OrderManager.reconcile()` interroga il broker e corregge divergenze | `execution/order_manager/manager.py:103-118` |
| Idempotenza su `request_id` (no duplicati su retry/timeout) | `execution/order_manager/manager.py:46-49` |
| `ReconciliationWorker` periodico broker↔OMS↔ledger; fatal mismatch blocca nuove entrate | `core/reconciliation_worker.py:1-8,95-123` |
| `PostgresOMS` idempotente via `client_order_id` per account | `core/oms_postgres.py:28-33` |
| `RecoveryService` + `ReconciliationWorker`; restart senza perdita/dup | STATUS.md §3 G3 ✅ PASSED |
| PaperBroker snapshot/restore per restart recovery | `execution/brokers/paper.py:272-311` |
| G3 ledger/OMS = ✅ PASSED (PostgreSQL path attivo) | `docs/ORACLE_AUTOPILOT_STATUS.md:35` |

**Gap residuo**: `PostgresOMS` è attivo solo con `--storage=postgres`; il path
in-memory resta il default (STATUS.md §3 G3). Reconcile continuo con *diff* e
blocco su disallineamento persistente non è dimostrato end-to-end con un broker
reale (mai testato contro IBKR live, ovviamente). Ma l'infrastruttura c'è.

### Falla 4 — Monolite in produzione (GIL/GC)

**Ipotesi**: GA o download FRED nello stesso processo dell'execution rischiano
freeze in alta volatilità.

**Stato reale**: rischio reale ma *posticipato di proposito*, e gestito da ADR.

| Evidenza | Dove |
|---|---|
| hot path in-process è scelta deliberata per il primo deployment | `docs/ARCHITECTURE.md:99-103` |
| Separazione in servizi "ammessa solo dopo benchmark, ownership distinta o isolamento di failure dimostrato" | `docs/ARCHITECTURE.md:106-107` |
| Il piano production-grade prevede stabilità/security in S5 | `docs/plan-production-grade.md` §S5 |

**Gap**: nessuno bloccante oggi. È il primo punto in cui l'essay ha ragione *in
futuro*: prima del funded serve la separazione, ma è lavoro S5/S6, non
prerequisito G7.

### Falla 5 — Risk management hard-coded vs agenti

**Ipotesi**: il policy engine troppo smart e i kill-switch assenti.

**Stato reale**: è il punto più solido del repo. Hard limits deterministici,
kill switch separato e già esistente.

| Evidenza | Dove |
|---|---|
| `PropFirmRiskGovernor` "pure, deterministic decision component" | `policy/prop_firm/governor.py:1-16` |
| Pre-trade gate, daily loss, overall loss, sizing, rollover, challenge_outcome | `policy/prop_firm/governor.py:407-423` |
| Session guards: circuit breaker, stale feed, risk alert bus, extreme-market conference | `execution/session_guards.py:1-26` |
| `RiskAlertBus`: HARD breach ferma entrate; `can_submit()`/`acknowledge()` bloccano finché umano conferma | `execution/session_guards.py` |
| Kill switch separato dal decision plane, verifica stato broker-side, flatten totale | ADR-010 §Decision:30 · `core/kill.py:1-27,44-96` |
| `TradeIntentBridge` blocca REPLAY/SHADOW all'origine | `execution/order_manager/intent_bridge.py:18-20` |

**Gap residuo (veri, ma piccoli)**: niente token bucket / rate limiting degli
ordini (grep `token_bucket|rate_limit|orders_per` in execution/core/policy = 0
hit); nessun fat-finger check hardcoded ($/size massimo assoluto); il kill
switch non è agganciato a un monitor esterno che lo invochi a livello OS
(esiste `core/kill.py`, non il watchdog che lo chiama da fuori processo).
Sono 3 componenti "stupidi" da aggiungere in S5, non un motivo per fermare la
ricerca.

## 2. Audit dello stack esterno (awesome-systematic-trading)

### 2.1 Il claim "ti mancano gli strumenti" è falso per la maggior parte

L'analisi esterna consiglia un "Megazord": nautilus_trader, vectorbt, polars,
cvxpy, QuestDB, NATS, Databento, Dukascopy. Verifica contro il repo reale
(directory `site-packages` + importazioni nel codice):

| Strumento consigliato | Nel repo | Uso reale |
|---|---|---|
| nautilus_trader 1.230.0 | ✅ installato | ✅ **usato**: `analytics/backtest/engines/nautilus.py` (`NautilusEngine`, SimulatedExchange con slippage/commission, FuturesContract) |
| vectorbt 1.1.0 | ✅ installato | ✅ **usato**: `analytics/backtest/engines/vectorized.py` (`VectorizedEngine`) |
| polars 1.43.1 | ✅ installato | ✅ **usato ovunque**: indicatori, macro, cache, feature store |
| numba 0.66 | ✅ installato | ⚪ indiretto (interno a vectorbt); nessun import diretto |
| ccxt 4.5.64 | ✅ installato | ✅ **usato**: `execution/brokers/ccxt_broker.py` |
| ib_insync 0.9.86 | ✅ installato | ✅ **usato**: `execution/brokers/ibkr.py` |
| cvxpy 1.9.2 | ✅ installato | ❌ **dipendenza morta**: non importato da nessun file del progetto |
| Dukascopy | ✅ | adapter reale: `market/ingestion/sources.py:786` (`jetta.dukascopy.com/v1`) |
| Databento | ✅ | tra i source: `market/ingestion/orchestrator.py:84` |
| QuestDB | ADR-002 | ⚪ **SUPERSEDED da ADR-009** (storage strategy) |
| NATS | ADR-001 | ⚪ decisione documentata, runtime non autorevole |
| Prometheus/Grafana, Dagster, MLflow, ArcticDB, cryptofeed, hftbacktest | ❌ non presenti | — |

**Conclusione 2.1**: l'infrastruttura consigliata è già installata e per la
maggior parte già cablata. Il deficit reale è di *catalogazione* (cvxpy morto
che nessuno sapeva morto), non di acquisizione. Verificato 2026-08-10.

### 2.2 Gap verificato #1 — Lookahead bias FRED (CONFERMATO, non tracciato)

`analytics/macro/fred.py:150` fa `GET /series/observations` con
`file_type=json` e `observation_start` (`fred.py:137,143`): è l'endpoint della
serie **corrente e rivista**. Nessun handling `vintage` / `ALFRED` /
`revision_date` in `analytics/macro/` (grep = 0 hit; `state.py:32` definisce uno
snapshot macro ma senza provenance temporale). I dati macro dati all'Analyst
sono quelli *corretti oggi*, non quelli *pubblicati all'epoca* → edge fantasma
nei walk-forward.

- **Severità**: alta (invalida qualunque verdetto macro-conditional).
- **Fix**: o ALFRED vintage, o marcare i dati come `PIT=False` ed escluderli dai
  walk-forward finché non c'è il vintage.
- **Stima**: ~1 giorno di lavoro.
- **Stato (2026-08-10, RISOLTO)**: `fred.py` `fetch_series`/`fetch_multiple`
  ora accettano `vintage=` che mappa a `vintage_dates` (endpoint ALFRED
  point-in-time). Senza `vintage=` la richiesta NON è PIT (documentato nella
  docstring: solo live/as-of-now). Test: `test_vintage_sends_vintage_dates` +
  `test_no_vintage_omits_vintage_dates`. Chiunque usi dati macro in un
  walk-forward DEVE passare `vintage=` al bar-date per non guardare avanti.

### 2.3 Gap verificato #2 — cvxpy è una dipendenza morta

`cvxpy 1.9.2` è in `site-packages` ma `grep "import cvxpy|from cvxpy"` su tutto
il codice del progetto (esclusi venv/build/.omx) = **0 hit**. `analytics/strategy/risk_sized.py`
fa sizing con `atr_percent_sizes` (`risk_sized.py:41`), non con cvxpy.

- **Fix**: o cablare cvxpy (sizing Markowitz/Kelly nel decision layer), o
  rimuoverlo dal lockfile. Dipendenza morta = debito senza benefici.
- **Stato (2026-08-10, KEEP — NON è rimovibile)**: cvxpy è *transitiva
  obbligatoria* di `pyportfolioopt` (dichiarata direttamente in
  `pyproject.toml:37`, non importata dal progetto). Rimuoverla dal lockfile
  significa rompere pyportfolioopt, che il piano profittevole usa per sizing
  della lane A (Markowitz/Kelly, `docs/plan-profitable-system.md:148-149,
  180`). Decisione: **KEEP**, verrà cablata in S1.2 del piano profittevole
  per il sizing lane A. Il lockfile non è morto: è in attesa del suo unico
  consumatore pianificato.

### 2.4 Gap verificato #3 — Paper broker fill-on-touch senza queue position

`execution/brokers/paper.py:395-421` ha slippage (`paper_slippage_bps=50` =
0.5%, `config.py:28`) e fill parziale (`paper_partial_fill_prob`,
`paper.py:416-421`). Ma `paper_spread_bps=0` (`config.py:27`) e **non c'è
simulazione di queue position** (il mercato tocca il tuo prezzo e rimbalza
senza fillarti). Rischio: DEAP impara a sfruttare il fill-on-touch.

- **Severità**: media. Attenuato dal fatto che i costi hardcoded già macinano
  molta edge falsa (0/9 walk-forward è la prova che il gate filtra).
- **Fix (20% del valore di hftbacktest, 2% del lavoro)**: pessimistic-fill —
  esecuzione limite solo se il mercato sfonda di X tick. Niente parser PCAP, niente
  server 24/7.
- **Stato (2026-08-10, RISOLTO)**: `BrokerConfig` ora espone
  `paper_limit_penetration_ticks` (default 0 = fill-on-touch legacy) +
  `paper_tick_size` (default 0.01). `_is_marketable` in `paper.py` richiede
  che il mercato sfondi il trigger di N tick prima di riempire limit/stop.
  Per attivarlo basta settare `paper_limit_penetration_ticks>0`; il default
  preserva il comportamento esistente. Test: `TestPessimisticFill` (touch ≠
  fill, penetration = fill, stop incluso, zero-tick = legacy).

### 2.5 Cosa NON fare (trappole dell'analisi esterna)

- **Piano "zero-budget L2/L3" (PCAP IEX, Oracle Cloud, Hawkes)**: mesi di lavoro
  per alimentare hftbacktest, ma il collo di bottiglia non è la microstruttura —
  è che G5/G6 sono REJECTED e l'alpha ≈ 0 netto. Raccogliere L2 non crea edge.
- **Dati sintetici GAN (TimeGAN/Quant GAN)**: contraddizione interna all'analisi —
  se DEAP memorizza 12 mesi veri, memorizzerà ancora più facilmente 1000 mesi
  sintetici (struttura artificiale per definizione). È un generatore di overfitting,
  non una soluzione.

## 3. Gap matrix execution vs live

| Componente | Stato | Mancante per live | Blocker G7? |
|---|---|---|---|
| Decision/execution boundary | ✅ progettato (ADR-010) | — | no |
| OMS durable | 🟡 Postgres attivo solo `--storage=postgres` | default persistente | no (G3 ✅) |
| Reconcile | 🟡 worker esiste, mai provato vs broker reale | diff continuo + block on mismatch testato end-to-end | no |
| Ledger | ✅ PostgresLedger attivo (G3 ✅) | — | no |
| Hard risk kernel | ✅ PASSED (G4) | rate limiting, fat-finger | no |
| Kill switch | ✅ `core/kill.py` esiste | watchdog esterno | no |
| Paper broker | ✅ snapshot/restore | slippage aggressivo (vedi sotto) | no |
| Slippage/fee simulation | 🟡 costi hardcoded (commission 10bps / slippage 5bps nel motore backtest; paper broker spread=0) | configurabilità + aggressività | sì (per validità G6) |
| Edge (research) | ❌ G5 REJECTED | edge verificato o chiusura onesta | **SÌ — blocca tutto** |
| Paper trade-producing | ❌ G6 REJECTED (0 trade) | run con trade e P&L reali | **SÌ** |
| Monolith → servizi | ⚪ deferred S5/S6 | separazione processo | no (post-G7) |

## 4. Il vero blocker: l'edge, quantificato

| Evidenza | Valore | Fonte |
|---|---|---|
| M31 re-run canonico | Sharpe **-2.51** (onesto -0.251/-0.31) | `docs/reports/m31-rerun-final/m31.md` · BACKLOG G5 |
| Candidati segnale | **8/8 REJECTED** | BACKLOG BL-023 Fase 5c |
| Walk-forward multi-asset | **0/9 battono buy&hold** | `docs/reports/multiasset/walkforward.md` |
| Alpha residuo misurato | **+2.3%..+6.1% lordo/anno → ~0 netto costi** | `docs/reports/s0-2-economic-model.md` §0 |
| Obiettivo €3K/mese | richiede alpha **≥30-120%/anno = 5-16× il soffitto** | `docs/reports/s0-2/eval_economics.json` |
| Base rate funded account | la maggioranza fallisce | S0.4 del piano production-grade |

Citazione dal repo: *"Il 'capitale mancante' non è denaro: è l'edge."*
(`docs/reports/s0-2-economic-model.md` §0).

## 5. ADR proposto (draft — NON accettato)

**Titolo**: Live readiness gated su edge + paper trade-producing, non su
architettura.

- **Contesto**: l'infrastruttura execution/OMS/risk copre già le 5 falle
  classiche del passaggio paper→live. L'hardening residuo (rate limit, fat
  finger, watchdog kill, slippage configurabile) è bounded e non blocca nulla.
- **Decisione**:
  1. Nessun capitale reale, nessun funded, nessun ordine live prima che G5
     (edge verificato) e G6 (paper trade-producing, run BL-024 qualificante)
     siano PASSED.
  2. Lo sprint immediato è ricerca/edge (S1), non hardening execution.
  3. L'hardening execution (rate limit, fat-finger, watchdog, slippage
     aggressivo nel paper broker, persistenza OMS di default) è lavoro S5,
     pianificato in parallelo a bassa priorità.
  4. I 3 gap verificati in §2 sono debito da saldare PRIMA della prossima
     ricerca macro-conditional: (a) FRED senza vintage = dati rivisti spacciati
     per puntuali → ALFRED o marcatura `PIT=False` ed esclusione dai
     walk-forward; (b) cvxpy morto → cablarlo o rimuoverlo dal lockfile;
     (c) paper broker fill-on-touch → pessimistic-fill (esecuzione solo se il
     mercato sfonda di X tick).
- **Conseguenze positive**: zero rischio di mettere capitale su edge ≈ 0; il
  repo non brucia altro tempo su infra inutile.
- **Conseguenze negative**: il "live" resta lontano; eventuale frustrazione sul
  ritmo.
- **Enforcement**: G7 resta ⚪ NOT_STARTED; PAPER/SHADOW/EVALUATION/FUNDED
  restano DISABLED (STATUS.md §1). Nessun commit che tocca i mode guard senza
  questo ADR accettato.

## 6. Piano: cosa serve davvero per G7

Dalla roadmap e dal piano production-grade, in ordine:

1. **S1 — Chiudere G5** con verdetto definitivo: o un edge che sopravvive al
   walk-forward anti-beta (S_test > Sharpe buy&hold, non solo Sharpe alto), o
   chiusura onesta della lane daily. Il 0/9 è già il segnale che lo spazio è
   affollato (S0.4).
2. **S2 — Chiudere G6** (BL-024): run paper indipendente che produca trade e
   P&L reali (oggi 0 trade, 0 P&L, Sharpe 0). Slippage/fee simulati in modo
   aggressivo e configurabile, non hardcoded.
3. **S3 — G7 readiness**: S3.3 vertical slice esecuzione prop-firm (strumento,
   order types, session rules, restart/recupero) — SENZA pretendere che validi
   l'alpha.
4. **S5 — Hardening** (rate limit, fat-finger, watchdog kill, persistenza OMS
   default, separazione servizi) prima del funded.

## 7. Cosa NON fare

- Non mettere capitale reale ora: l'edge misurato è ≈ 0 netto (S0.2), e i gate
  live sono bloccati su G5/G6, non sull'architettura.
- Non riscrivere il disaccoppiamento decision/execution: è già il design.
- Non aggiungere servizi (Redis/NATS split) senza benchmark: ADR-010/ARCHITECTURE
  §3.2 lo vieta espressamente fino a prova di bisogno.
- Non trattare l'hardening come prerequisito G7: è post-edge.

## 8. Verifica (revisore a contesto fresco)

Fact-check indipendente eseguito 2026-08-10 da un subagent a contesto fresco
(regola alinos: "mai il generatore che certifica se stesso"): **17/18 claim
VERIFIED**; una correzione fatti (costi: commission 10bps / slippage 5bps, non
"10bps spread") e una sovra-dichiarazione (kill switch: "separato dal decision
plane", non "processo separato") — entrambe corrette in questo documento. Tutti
i componenti citati (CPCV split, session guards, kill switch, reconciliation
engine, PostgresOMS idempotenza) risultano **implementati, non stub**.

## 9. Limiti di questo assessment

- La persistenza Postgres OMS è verificata su path `--storage=postgres`; il
  comportamento di default (in-memory) non è equivalente in produzione.
- Nessun broker live è mai stato toccato (giustamente): riconciliazione e
  kill-switch vs un broker reale sono verifiche S3, non ancora fatte.
- Il modello economico S0.2 è MC sintetico con parametri da riconfermare
  (S0.5): i numeri "5-16×" sono ordini di grandezza, non precisione.
- I threshold DD (4.0 vs 5.0 vs 3.0) vivono in 3 posti (vedi piano S6.10,
  CRITICAL): una sola source of truth da config è pre-requisito per qualunque
  verdetto G6/G7 riproducibile.

## Fonti

- `docs/ORACLE_AUTOPILOT_STATUS.md` — matrice gate autoritativa (2026-08-01)
- `docs/reports/s0-1-bl023-autopsy.md` — decomposizione fallimento BL-023
- `docs/reports/s0-2-economic-model.md` + `docs/reports/s0-2/eval_economics.json` — modello economico
- `docs/reports/multiasset/walkforward.md` — anti-beta walk-forward
- `docs/reports/m31-rerun-final/m31.md` — re-run canonico REJECTED
- `docs/ADR/ADR-010-deterministic-execution-safety-boundary.md` — confine sicurezza
- `docs/plan-production-grade.md` (commit `3bdef58`) — piano S0-S6
- `execution/order_manager/manager.py` · `intent_bridge.py`
- `execution/session_guards.py` · `execution/brokers/paper.py` · `ibkr.py`
- `core/reconciliation_worker.py` · `core/oms_postgres.py` · `core/kill.py`
- `policy/prop_firm/governor.py`
- `genetics/fitness/evaluator.py` · `genetics/evolution.py`
