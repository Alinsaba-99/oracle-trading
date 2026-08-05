# PLAN — Oracle: production-grade, profittevole, efficiente

> **STATUS: APPROVED** via /autoplan 2026-08-05 (Final Approval Gate, default A — 0 user challenges, 0 taste decisions).
> Draft in input alla pipeline /autoplan. Data: 2026-08-05. Branch: main (HEAD cb745ed).
> Stato di partenza: G0-G4 PASSED, G5 REJECTED (BL-023: M31 REJECTED, 8/8 candidati
> REJECTED, multi-asset walk-forward 0/9 — nessun segnale batte il buy&hold),
> G6 REJECTED (nessun run trade-producing), G6-I PARTIAL, G7-G9 NOT_STARTED.

## Premesse

- **P1** — Obiettivo dichiarato: €3K/mese da trading tramite prop firm (MyFundedFutures).
  Serve un edge validato: niente capitale reale finché G5+G6 non sono PASSED.
- **P2** — La metodologia di validazione è già la lezione appresa da BL-023: benchmark-relative
  (S_test > BH_S), multi-asset, walk-forward out-of-sample, N onesto, luck test. Non si torna indietro.
- **P3** — "Production-grade" = capability gate G0-G9 con evidenza riproducibile (ADR-012),
  non fasi temporali. Ogni gate ha una matrice gate/stato autoritativa (STATUS.md).
- **P4** — L'infrastruttura (lake, OMS, ledger, risk, CI) è già solida: il collo di bottiglia
  è la ricerca di edge, non l'ingegneria.

## Scope proposto

### S0 — Diagnosi e governance (PREREQUISITI, lezione Codex)
- S0.1 — **Diagnosi BL-023**: decomporre il fallimento PRIMA di ampliare la ricerca
  (dati vs implementazione vs costi vs benchmark vs orizzonte vs regime). Più dati
  non risolvono un fallimento non diagnosticato.
- S0.2 — **Modello economico prop-firm**: costi eval, reset, regole payout, trailing
  DD, consistency, slippage/commissioni/tasse, probabilità di sopravvivenza → "€3K/mese"
  diventa una tesi quantificata, non un outcome.
- S0.3 — **Governance ricerca**: trial ledger immutabile (ipotesi pre-registrata,
  dataset versionato, holdout finale intatto, multiplicity correction), feature lineage.
  Il luck test dopo 1000 tentativi senza ledger non significa nulla.
- S0.4 — **Tabella EV delle alternative** (una pagina, anche rough): per ogni lane,
  EV atteso per mese di sforzo — (a) productize lake/stack backtest, (b) evaluation
  services per altri (processo risk/OMS disciplinato), (c) consulting, (d) ricerca
  alpha (lane corrente). L'EV della lane ricerca DEVE giustificarsi contro il base
  rate dei funded account (maggioranza fallisce) — il 0/9 è già il segnale che lo
  spazio cercato è affollato.
- S0.5 — **Channel constraints front-loaded** (da S3 → S1): analisi ToS MyFundedFutures
  (daily loss, trailing DD, no-automation BL-071, payout split) = un weekend di lettura,
  non un gate. Le soglie di ricerca derivano DALLE regole del canale; exit criterion se
  le regole cambiano materialmente (il settore ha avuto ondate regolatorie 2024-25);
  valutare un secondo canale.

### S1 — Chiudere G5 (research truth) con verdetto definitivo
- S1.1 — Nuova derivazione segnali SOLO dopo S0: regime filter + exit management
  sull'alpha residuo, fattori alternativi, timeframe intraday (5m/15m/30m).
  **Condizione (lezione M32a)**: il regime filter è la lead idea SOLO dopo un
  post-mortem del classificatore — nel paper run M32a 29/30 sessioni erano
  classificate "choppy" (classificatore biasato, mean-reversion attivo 72% del
  tempo). La ricerca fattori FinClaw 484 SOLO con pre-registrazione delle family +
  FDR/Bonferroni su family + holdout finale intatto; preferire spazi meno affollati
  (microstruttura, dati idiosincratici, nuovi strumenti) ai fattori pubblici che
  ogni corso di quant insegna.
- S1.2 — Walk-forward multi-asset come gate standard per ogni candidato (runner Fase 2
  → pipeline). Sfumato: asset-specific ammesso con motivazione documentata.
- S1.3 — Estendere il lake SOLO dopo S0.1 (commodity futures con metodologia di
  roll esplicita; equities 1m BL-052; ETF settoriali; crypto extra).
- S1.4 — Soglie ADR-016 riviste: Sharpe ≥ 0.5 CON cost model (slippage+commissioni),
  CI e serial-correlation; DD ≤ 4% con definizione esplicita (peak-to-trough giornaliero);
  "0 breach" ridefinito (n sim, modello esposizione); luck p ≤ 0.1; S_test > BH_S
  interpretato con l'opportunity cost del payoff prop-firm, non solo vs buy&hold.
  **Sensitivity: l'edge DEVE sopravvivere a costi avversi pre-dichiarati** (worst-case
  slippage/commissioni) — un edge che passa solo con assunzioni ottimistiche è fragile.
  **Net-of-cost come metrica di gate**: il gross Sharpe non è la metrica del gate;
  per futures intraday il benchmark buy&hold va a sua volta cost-adjusted e
  roll-adjusted (i futures non si "tengono" come un ETF).
  **Sizing bridge pre-registrato**: walkforward.py:7 dichiara "signal-level (scale-free,
  no broker economics)" — senza posizione/contratti il costo per contratto NON è
  applicabile ai returns. Pre-registrare la convenzione di sizing (1 contratto per
  unità di segnale, o vol-target con target esplicito) come CAMPO DEL LEDGER PRIMA del
  cost model, così i verdetti sono riproducibili.
  **Sharpe unificato**: walkforward.sharpe (walkforward.py:98-106) restituisce 0.0 su
  varianza zero; statistics._sharpe (statistics.py:87-92) restituisce inf su serie
  costante positiva → bootstrap_luck_p_value (statistics.py:60-84) → p≈0.002
  "significativo" su una serie degenere (il path che la guardia zero-trade mira a
  bloccare, ma a livello RICERCA oggi PASSA). Unificare in statistics.py, eliminare
  walkforward.sharpe, regression test sul contratto zero-variance (il test esistente
  test_multiasset_walkforward.py:52-56 codifica 0.0 — l'altra implementazione dà inf).
  **"0 breach ridefinito (n sim, modello esposizione)" = cambiamento METODOLOGICO, non
  tweak di soglia** (M6): il breach counting è oggi per-window deterministico nel gate
  M31; il passaggio a simulazione/esposizione può capovolgere i verdetti; "DD ≤ 4%
  peak-to-trough giornaliero" è indefinito per segnali intraday (il DD intraday si
  misura sul path intraday, non sulle chiusure daily). Serve un ADR dedicato + definizione
  registrata nel ledger PRIMA di giudicare qualsiasi candidato.
- S1.5 — Trial ledger: ogni esperimento registrato immutabile (data, ipotesi, dataset,
  parametri, verdetto) + holdout finale intatto. **Pre-registrazione obbligatoria**:
  ipotesi, metrica primaria, stopping rule, universo candidati PRIMA del run
  (anti-HARKing); correzione per molteplicità su family definite.
  **Hash-chaining**: JSONL "immutabile" è trivialmente editabile — se il ledger alimenta
  il luck test con multiplicity, aggiungere prev-hash per record (o sqlite); concurrency:
  i run paralleli S4 competono sul register read-check-write (due processi → id duplicati);
  **holdout enforcement meccanico**: "holdout finale intatto" non può essere una speranza —
  access-log del holdout + regola pre-registrata (chi lo tocca prima del verdetto = trial
  invalido).
  **Contract (DX 5.3)**: storage (append-only JSONL con hash chain vs tabella Postgres),
  quale superficie CLI lo ospita, workflow di pre-registrazione (ipotesi → dataset pin →
  parametri PRIMA del run), e COME i runner enforceano "holdout finale intatto" (il
  runner conosce i bound del holdout e rifiuta?). Sottosezione "Trial ledger contract"
  con schema, comandi, hook di enforcement nel gate runner.
- S1.6 — **Kill/pivot decision memo**: budget di ricerca (tempo, trial, denaro) e
  albero a 4 rami — continuare / narrow a un mercato / pivot a tooling / abbandonare.
  Include confronto EV narrow-vs-wide. **Meta-kill rule scritta PRIMA del run**:
  budget bounded (max N family, max 3 mesi); se la ricerca bounded fallisce, la lane
  ricerca è chiusa PERMANENTEMENTE e si persegue la lane alternativa (tabella S0.4).
  **Calendario esplicito**: quando ci si aspetta reddito, o un "no" definitivo
  (es. 12-18 mesi, per lo più "no" → dirlo ora).
- S1.7 — **Vettorizzare il loop O(n²)** in walkforward.py:122-127 (np.append per barra):
  ok a 6.5K barre, esplode a 250K+ su intraday. Split train/test con maschere
  vettorizzate PRIMA di promettere speedup paralleli.

### S2 — Chiudere G6 (paper trade-producing)
- S2.1 — BL-024 rivisto: 250-session (non 100), P&L > 0 con expectancy minima
  esplicita, Sharpe non-zero CON soglia, pass rate ≥ 0.90 (definito: ordini/esecuzioni/
  risk-check), DD a percentili (P95, max worst-case — non mean), reconcile 100%,
  **guardia zero-trade qualitativa**: run con 0 trade = FAIL non-zero; inoltre minimo
  trade eseguiti + sessioni attive + coverage esposizione (un singolo trade accidentale
  non è evidenza); motivo del fail machine-readable (no signals / rejected / risk-block /
  infra) con exit code distinto. **Guardia per-window**: min trade per finestra +
  floor totale (249 finestre vuote + 1 che trade NON passa); `_verify_pin_hash`
  (run_g6_wp2_paper_sessions.py:99-107) da warning → FATAL (dataset pinnato corrotto =
  run invalido, exit non-zero); NESSUN flag `--no-guard` di fuga; soglia sopravvissuta
  `mean_sharpe ≥ -0.5` è NEGATIVA (un run con edge negativo passa) → deve essere > 0.
  **Vincolo statistico**: sul dataset default (250 barre)
  le finestre 95-bar NON sono 250 sessioni indipendenti — usare il lake ES completo
  (6.5K barre) o finestre Monte Carlo con semina deterministico; specificare
  numeratore/denominatore del pass rate e riconciliarlo dal ledger, non dai contatori.
  **Non-overlapping come default**: `step=max(1,(N-window)//n)` su 250 barre → overlap
  ~94%, solo 2 finestre non sovrapposte esistono; assert `n ≤ floor(N/window)` con
  errore altrimenti (il docstring "non-overlapping when possible" è impossibile su
  questo dataset).
  **Timeline dichiarata**: 100 sessioni ≈ 4.7 mesi di calendario (mai dichiarato prima);
  trade-frequency viability check PRIMA di impegnare il run (se la family spara solo
  nel regime "volatile" ~3% delle sessioni, un run di 100 sessioni produce ~3 trade —
  statisticamente inutile); entrambi i regimi rappresentati.
- S2.2 — Solo dopo un candidato G5 PASSED: nessun paper run su segnali già falsificati.
  **Refactor script-as-module**: run_g6_wp2_100_sessions.py:51 importa
  `scripts.run_g6_wp2_paper_sessions` via sys.path hack (linea 49) — la riscrittura S2.1
  deve promuovere `_run_session` a modulo library.
  **Fallback silenzioso (DX 3.5)**: `_build_ensemble` scende silenziosamente da
  AdaptiveEnsemble a RegimeAwareEnsemble su ImportError (run_g6_wp2_paper_sessions.py:
  126-131) — una sostituzione di strategia silenziosa in un gate di ricerca, hazard di
  riproducibilità ADR-012; stampare warning. Anche `_PropFirmAllow.check_order` ingoia
  eccezioni restituendo False senza log.

### S3 — G7-G9 readiness (prop-firm, ops continue)
- S3.0 — Modello economico prop-firm (vedi S0.2): concentration risk (fallback firms),
  broker portability, controparte/payout policy.
- S3.1 — BL-071: ADR-015 policy automazione Topstep (ToS: niente VPS/VPN/residential bot).
  **Stale check**: ADR-015 è ✅ ACCEPTED (BACKLOG.md:268-269, commit 8f590d8) — S3.1 deve
  VERIFICARE la copertura, non scriverla.
- S3.2 — Monitoring giornaliero paper (alert Telegram via env-token, riepilogo
  giornaliero), journal dei trade, SLO + error budget, paging criteria e escalation.
  **Heartbeat/dead-man's switch**: se run_daily_monitor.py stesso muore (venv rotto,
  env non sourced sotto cron, disco pieno) non c'è alert — il 2am-Friday failure mode.
  `last_success` timestamp controllato da un secondo trigger, o alert-on-missing-report;
  testare anche dedup degli alert (stesso drift ogni 5 min) e token invalido (401 → warn,
  non crash).
- S3.3 — **Vertical slice esecuzione prop-firm presto**: strumento target, order types,
  session rules, trailing DD, restart/recupero — SENZA pretendere che validi l'alpha.
  Kill switch definito: chi lo ferma, quanto veloce, stato delle posizioni, restart-safe.

### S4 — Efficienza (ogni punto di vista)
- S4.1 — Compute: parallelizzare walk-forward multi-asset con **scrittura atomica +
  lock dei report (idempotenza)**, job/window IDs deterministici, manifest
  atteso-vs-fatto (dedup, ordine deterministico, completezza); rerun riprendono da
  partizioni immutabili (niente doppio conteggio di fold); vettorizzazione (vedi S1.7:
  il loop O(n²) va vettorizzato prima del parallelismo).
  **Report identity (M8)**: lock+tmp+rename garantisce atomicità ma non identità — due
  config candidate che scrivono lo stesso `walkforward.json` (default,
  run_multiasset_walkforward.py:47) si sovrascrivono silenziosamente. Key dei report
  per (assets, signals, cutoff, ledger_id) o content-hash.
  **Contratto determinismo (DX 5.2)**: run_walk_forward.py:248 chiama `np.random.seed(42)`
  GLOBALMENTE (dentro PBO noise) — worker paralleli + RNG globale condiviso = run
  non-riproducibili, VIOLA ADR-012. AC: seed per-worker derivato dal fold id; i risultati
  devono byte-matchare i run seriali; report atomici per asset (oggi run_walk_forward.py
  SOVRASCRIVE il singolo file output in modalità multi-asset — solo l'ultimo asset
  sopravvive; il "lock dei report" deve fixare questo).
- S4.2 — Dati: alert coverage drift (F-07 non più manuale), pin EXPECTED_ROWS a ogni
  refresh, backfill 1m futures via IBKR solo dopo S0.1.
  **Pinning anti-fatigue (H4)**: il pin per righe alza su OGNI crescita del lake live
  (walkforward.py:43-46+62-69: "bump when it grows") → ogni refresh legittimo innesca
  sia pin sia drift-alert → il drift alert diventa rumore. Per l'intraday (1m: 6714 righe
  in 8 giorni, righe intrinsecamente volatili per giorni parziali) il row-count è il
  MECCANISMO SBAGLIATO: pinnare (symbol, earliest, latest) o content-hash. coverage.json
  non ha `generated_at` e mischia tz-aware/tz-naive — pinnare lo schema PRIMA dell'alert.
- S4.3 — Processo: un comando per run+report (fatto), check simboli fail-fast
  (simbolo assente → errore chiaro), checklist pre-commit, CI.
  **Contratto exit code (H3)**: 0 = PASSED, 1 = REJECTED-verdict, 2 = error — oggi
  senza `--require-pass` un cron vede GREEN su una strategia falsificata (exit 0) ed
  exit 2 è sovraccarico (config error == verdetto fail, run_multiasset_walkforward.py:56
  vs 110-112). Gate runner documenta il contratto; test per tutti e tre.
  **Silent skips (H5)**: run_portfolio_v2.py:91-120 — regime mismatch `continue`,
  `except Exception: continue`, `n_trades==0: continue` → `results` si restringe
  silenziosamente e lo Sharpe aggregato (linea 162) si calcola sui sopravvissuti
  ("Sessioni attive: 0/100" stampa ma exit resta 0). `n_effective < threshold` →
  exit non-zero; `except Exception` logga il traceback, non sparisce.
- S4.4 — Debito: warning budget pytest sotto controllo; NATS/QuestDB/Qdrant/Redis:
  **decisione per architettura target** (rimuovere o documentare), non per tally.
- S4.5 — **Cache con fingerprint completo** (codice+dati+config+env): fail on
  provenance mismatch, mai riuso silenzioso di artefatti stale.

### S5 — Stabilità e sicurezza
- S5.1 — BL-040: OrderManager rifiuta risk_manager=None — **GIÀ implementato**
  (execution/order_manager/manager.py:30-31 alza ValueError); BACKLOG.md stale →
  marcare [x]; il test `test_risk_gate_not_configured_passes_through` è fuorviante
  (nome/docstring dicono "None → proceeds" ma la fixture passa sempre mock_risk):
  aggiungere test reale del path None (P2, ~1h). **Fix incompleto (M2)**: la fixture
  `manager` (test_order_manager.py:41) inietta SEMPRE mock_risk → il test è verde pur
  documentando un comportamento che il costruttore vieta; il fix reale è
  `pytest.raises(ValueError)` su `OrderManager(broker, None)` + scan dei construction
  site (avrebbe beccato showcase.py:574 che chiama `OrderManager(paper)` con un arg
  posizionale → TypeError oggi); l'AC BL-040 specifica `RiskRequired` ma il codice alza
  plain `ValueError` — allineare. **Adapter stand-in (DX 3.6)**: il RUNBOOK incident
  entry cita `_AllowAll` → fix BL-070, ma BL-070 è chiuso ✅ e l'adapter wired è uno
  script-local `_PropFirmAllow` stand-in — S5.1 include "sostituire `_PropFirmAllow`/
  `_AllowAll` con l'adapter reale".
- S5.2 — BL-060: CLI default --storage=postgres quando DATABASE_URL presente (~30min).
  **Path rotto (DX 3.3, CRITICAL)**: `_resolve_dsn` NON esiste da nessuna parte —
  run_g6_wp2_paper_sessions.py:175 e run_regime_paper_smoke.py:84 fanno
  `from apps.cli.trade_commands import _resolve_dsn` → ImportError su OGNI
  `--storage postgres`; l'esempio "path production" del RUNBOOK (linea 51) è morto.
  S5.2 include: definire `_resolve_dsn` (o leggere `postgres.dsn` da config/
  development.yaml) + smoke test `--storage postgres` in CI.
  **Comandi RUNBOOK fittizi (DX 3.4)**: `trade recover` non esiste (subcommands:
  submit/list/cancel/status/kill/reconcile); `--storage` non è flag su `trade submit`;
  `trade reconcile` hardcoda InMemoryOMS/InMemoryLedger (main.py:561-562) — non può
  mai riconciliare Postgres. Sync task: implementare `trade recover`, wired reconcile
  storage, fix `--quantity`→`--qty`.
- S5.3 — Secrets: env-only (Telegram/IBKR), gitleaks in CI (già attivo).
  **Cron leak vector**: token esportati in shell in un crontab world-readable sono un
  vettore di leak — usare `.env` loader o systemd `EnvironmentFile`; nessun endpoint
  in ingresso (il monitor è outbound-only Telegram: mantenerlo così).

### S6 — DX operatore (lezione Codex DX)
- S6.1 — **Entry point unificato `oracle`**: `oracle research run`, `oracle gate run`,
  `oracle monitor daily` — ogni comando emette artifact dir + manifest + summary
  terminale conciso (niente hand-chaining di 3 script).
- S6.2 — **Error codes machine-readable** con messaggio azionabile: check fallito,
  valore osservato, soglia attesa, artifact rilevante, comando di rerun esatto.
- S6.3 — **Resume/retry UX** per run lunghi: status, resume, retry-failed, cancel;
  distinguere failure transitorie da risultati invalidi.
- S6.4 — **`oracle doctor`**: preflight raggruppato (db, credenziali, systemd, dati
  pinnati) con remediation links ed exit codes CI-friendly.
- S6.5 — Monitor giornaliero con contratto artifact esplicito: report datato + status
  alert, freshness/coverage, failed checks, `NO_ACTIVITY` esplicito (mai vuoto o
  success-looking).
- S6.6 — Convenzione lingua: campi machine in inglese stabile, summary umano in
  italiano (`--lang it`), mappatura terminologica in RUNBOOK.
- S6.7 — RUNBOOK: aggiornare esempi obsoleti (30 sessions, reconcile manuale,
  sha256sum raw), aggiungere daily one-command workflow, documentare ledger/gate/monitor.
  **Sezione bootstrap**: come un clone fresco ottiene i dati lake (scripts/backfill_all.py
  --fast è oggi scopribile solo dall'error message di run_walk_forward.py:64);
  **migrare gli esempi al lake** e ritirare data/ohlcv a pinned-only (DX 4.2).
- S6.8 — **Disclosure dati sintetici (DX 1.1, CRITICAL)**: `oracle backtest run`
  (apps/cli/main.py:383) gira su `_synthetic_ohlcv()` (sine wave) e stampa una tabella
  completa ("Sharpe Ratio", "Total Return") SENZA dire che i dati sono finti — nel
  sistema la cui governance è "no fake signals" il default demo produce risultati fake
  credibili. Fix: print `⚠ synthetic demo data` prominente, rinominare in
  `backtest demo`, o caricare i dati lake di default.
- S6.9 — **Naming table + trap --max-dd (DX 2.1/2.2)**: `--asset` vs `--assets`, `--tf`
  vs `--timeframe`, `--qty` vs `--quantity` (l'esempio RUNBOOK crasha argparse). Trap:
  `--max-dd` default 5.0 guida l'hard stop di sessione ma il verdetto usa 4.0 hardcoded
  (g6: 3.0) — tre numeri DD, uno overridable. Una sola source of truth in config,
  il flag la overrida.
- S6.10 — **Soglie da config SOLO (DX 2.3, CRITICAL)**: le soglie vivono in 3 posti con
  3 valori — run_walk_forward.py (Sharpe > 0.3, DD < 4.0), run_multiasset_walkforward.py
  (S_test ≥ 0.3, luck < 0.1, > BH, 2-of-3), run_g6_wp2_paper_sessions.py:467
  (`pass_rate ≥ 0.90 AND mean_sharpe ≥ -0.5 AND mean_dd ≤ 3.0` — gate a Sharpe NEGATIVO)
  — mentre config/qualification/m31.yaml ha già i valori ADR-016 corretti (0.5, 0.04,
  0.10). La revisione S1.4 NON deve diventare una quarta copia hardcoded: AC = "tutti i
  gate runner leggono le soglie da config/qualification/*.yaml SOLO; delete dei blocchi
  hardcoded". Override flag per sensitivity: --sharpe-min / --dd-max / --confirm-min /
  --cost-config (i costi BrokerConfig spread 10bps / slippage 5bps / commission 0.85
  sono hardcoded in _run_session; point values 5.0/50.0 hardcoded per non-ES/MES) —
  o dichiarare i gate esplicitamente non-overridable e rimuovere il fuorviante --max-dd.

## Fuori scope (per ora)

- Live trading reale (G8/G9) — bloccato da G5+G6; la vertical slice S3.3 è solo esecuzione simulata.
- Dashboard UI — rimandata a G6-I/lane operations.
- Multi-agent intelligence (G6-I) — solo dopo edge.
- GA evolution — deferita; la ricerca manuale dei fattori DEVE rispettare la stessa governance (S0.3).
- Vendita infra/research come prodotto — annotato come ramo del decision tree (S1.6).

## Error & Rescue Registry

| # | Errore | Dove emerge | Rescue | Severity |
|---|--------|-------------|--------|----------|
| 1 | Simbolo assente nel lake / partizione vuota | gate runner (S1.2) | fail-fast con range disponibili; exit non-zero | High |
| 2 | EXPECTED_ROWS stale (pin lake cambiato) | walkforward.py:65 | errore con righe attese vs ottenute → bump pin | Medium |
| 3 | Run paper con 0 trade | run_g6_wp2_100_sessions.py | FAIL non-zero con motivo machine-readable (no signals/rejected/risk-block/infra) | High |
| 4 | Refresh lake fallito a metà | refresh giornaliero | retry 2x + backoff, poi alert Telegram; niente dati parziali nel lake | Medium |
| 5 | Report JSON semi-scritto da run paralleli | walkforward report | scrittura tmp+fsync+rename atomico; lock per-report; stale-lock recovery | High |
| 6 | Edge passa solo con costi ottimistici | gate (S1.4) | sensitivity worst-case pre-dichiarata; fail se non sopravvive | High |
| 7 | Ledger corrotto (JSONL parziale) | trial ledger | recovery hint; append-only + hash di integrità | Medium |
| 8 | Token Telegram/IBKR assente | monitor (S3.2/S6.5) | log warning + NO_ACTIVITY esplicito; mai crash silenzioso | Low |
| 9 | Rerun doppio-conteggia fold | walkforward parallelo | job/window IDs deterministici; resume da partizioni immutabili; manifest atteso-vs-fatto | High |
| 10 | Cache stale riusata silenziosamente | cache calcoli (S4.5) | fingerprint completo (codice+dati+config+env); fail on mismatch | Medium |
| 11 | `_resolve_dsn` mancante → ImportError su --storage postgres | run_g6_wp2_paper_sessions.py:175, run_regime_paper_smoke.py:84 | definire `_resolve_dsn` (o postgres.dsn da config); smoke test CI | High |
| 12 | `oracle backtest run` su dati sintetici senza disclosure | apps/cli/main.py:383 | print ⚠ synthetic demo data / rinominare in `backtest demo` | High |
| 13 | Gate runner fail-open (verdetto FAIL, exit 0) | tutti i gate runner | contratto exit code 0/1/2, strict by default; test per tutti e tre | High |

## Failure Modes Registry

| # | Failure mode | Fase di scoperta | Impatto se ignorato | Mitigazione nel piano |
|---|--------------|------------------|---------------------|----------------------|
| 1 | HARKing (ipotesi registrata dopo il risultato) | S0.3/S1.5 | luck test privo di significato | pre-registrazione obbligatoria + multiplicity su family |
| 2 | Sunk-cost (ricerca senza budget) | S1.6 | anni su un edge che non esiste | kill/pivot memo con budget tempo/trial/denaro |
| 3 | Beta scambiata per alpha | S1.4 (già in Fase 2) | verdetto falso positivo | S_test > BH_S + cost model + CI |
| 4 | Finestre dipendenti gonfiano il N | S2.1 | "250 sessioni" falsamente indipendenti | vincolo statistico (lake completo o Monte Carlo seed) |
| 5 | Paper run vuoto dichiarato pass | S2.1 | G6 "qualificato" senza trade | guardia zero-trade qualitativa + min trade/sessioni/coverage |
| 6 | Multiplicity non corretta | S0.3 | 1 su 20 falsi positivi attesi | family definite + correzione |
| 7 | Falsa fiducia dai gate | S3.3 | capitale reale su esecuzione non testata | vertical slice prop-firm presto |
| 8 | Debito infrastrutturale indeciso | S4.4 | NATS/QuestDB/Qdrant/Redis semi-integrato | decisione per architettura target |

## Criteri di completamento del piano

1. S0 completo: diagnosi documentata + modello economico + trial ledger operativo +
   tabella EV alternative (S0.4) + channel constraints front-loaded (S0.5).
2. G5: verdetto documentato con governance (PASSED con report riproducibile, o chiuso per decision tree).
3. G6: run qualificante con trade reali e guardia zero-trade (BL-024 rivisto).
4. S4: ogni voce ha AC misurabili e stato in BACKLOG.md.
5. Nessun nuovo debito introdotto (gate completo verde: pytest+ruff+mypy --strict).
6. Ogni S-item ha → file(s) link e AC (DX 4.3 — il piano non deve auto-referenziarsi
   con "fatto" non localizzabili).

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|
| 1 | CEO | Premesse P1-P4 confermate + P5 (limite ricerca) | Premise gate (timeout→default) | — | coerente con profilo e ADR-012 | nessuna |
| 2 | CEO | Approccio A (ideal architecture: diagnosi→governance→gate) | Auto | P1+P5 | completezza senza over-engineering | B (minimal), C (data-first) |
| 3 | CEO | S0 prerequisiti (diagnosi, modello economico, governance) | Auto | P2+Codex | più dati senza diagnosi = overfitting machine | — |
| 4 | CEO | Soglie ADR-016 riviste (cost model, CI, percentili) | Auto | P1+Codex | gate statisticamente significativo | soglie attuali |
| 5 | CEO | BL-024: 250-session, DD percentili, guardia zero-trade | Auto | P1+Codex | 100 sessioni/mean nascondono i tail | BL-024 attuale |
| 6 | CEO | S1.6 kill/pivot memo + decision tree 4 rami | Auto | P6+Codex | "G5 chiuso" senza rami = scappatoia | — |
| 7 | CEO | Vertical slice esecuzione prop-firm presto (S3.3) | Auto | P6+Codex | i gate da soli creano falsa fiducia | post-G5 |
| 8 | CEO | NATS/QuestDB/Qdrant/Redis: decisione architetturale | Auto | P3 | debito≠architettura | rimozione per tally |
| 9 | CEO | S4.2 alert coverage drift | Auto | P1 | F-07 scoperto a mano = monitoring assente | — |
| 10 | CEO | Dashboard → DEFER (G6-I) | Auto | P3 | non blocca l'edge discovery | in scope ora |
| 11 | Eng | S1.7 vettorizzare loop O(n²) walkforward.py:122-127 prima del parallelismo | Auto | P5 | subagent: np.append per barra esplode su intraday | "già polars" |
| 12 | Eng | S2.1 vincolo statistico: 250 finestre NON indipendenti su dataset default | Auto | P1 | subagent: finestre 95-bar su 250 barre si sovrappongono | 250-session su default |
| 13 | Eng | S2.1 guardia zero-trade qualitativa (min trade + sessioni + coverage + motivo machine-readable) | Auto | P1 | Codex Eng: 1 trade accidentale non è evidenza | solo "trades > 0" |
| 14 | Eng | S4.1 job/window IDs deterministici + manifest atteso-vs-fatto + resume da partizioni immutabili | Auto | P1 | Codex Eng: rerun possono doppio-conteggiare fold | parallel naive |
| 15 | Eng | S4.5 cache con fingerprint completo, fail on mismatch | Auto | P1 | Codex Eng: cache stale riusata silenziosamente | cache naive |
| 16 | Eng | S0.3/S1.5 pre-registrazione obbligatoria (anti-HARKing) + multiplicity su family | Auto | P1 | Codex Eng: registrare dopo l'esecuzione permette HARKing | post-registrazione |
| 17 | Eng | S1.4 sensitivity costi avversi (worst-case) | Auto | P1 | Codex Eng: edge fragile passa con assunzioni ottimistiche | solo costi nominali |
| 18 | Eng | S5.1 BL-040 GIÀ implementato → BACKLOG stale, test fuorviante da correggere | Auto (verificato) | P4 | manager.py:30-31 alza ValueError; test usa sempre mock_risk | marcare come TODO |
| 19 | Eng | S5.2 BL-060 confermato (storage memory hardcoded run_portfolio_v2.py:115) | Auto (verificato) | P4 | grep codice reale | — |
| 20 | Eng | DRY: walkforward.py:98 sharpe() duplica statistics.py:87 _sharpe() → unificare | Auto | P4 | duplicazione verificata | tenere entrambe |
| 21 | DX | S6.1 entry point unificato `oracle` (research/gate/monitor) | Auto | P5 | Codex DX: 3 tool senza entry point = hand-chaining | 3 script separati |
| 22 | DX | S6.2 error codes machine-readable con rerun command | Auto | P1 | Codex DX: REJECTED generico forza ispezione sorgente | messaggi free-text |
| 23 | DX | S6.3 resume/retry UX per run lunghi | Auto | P5 | Codex DX: nessun resume per walk-forward | kill & rilancio |
| 24 | DX | S6.4 `oracle doctor` preflight | Auto | P5 | Codex DX: failure di setup senza preflight | debug manuale |
| 25 | DX | S6.5 monitor con NO_ACTIVITY esplicito | Auto | P1 | Codex DX: report vuoto sembra successo | report vuoto |
| 26 | DX | S6.6 --lang it (campi machine EN, summary IT) | Auto | P5 | Codex DX: operatore italiano, output misto | solo EN |
| 27 | DX | S6.7 RUNBOOK aggiornato (daily one-command workflow) | Auto | P5 | Codex DX: runbook documenta path obsoleti | — |
| 28 | CEO | S1.1 regime filter CONDIZIONALE al post-mortem M32a (29/30 "choppy") | Auto | P1 | subagent CEO: classificatore biasato dimostrato; lead idea senza post-mortem = ripetere l'errore | regime filter come lead |
| 29 | CEO | FinClaw 484 solo con pre-registrazione + FDR/Bonferroni + holdout; preferire spazi non affollati | Auto | P1 | subagent CEO: 484 fattori pubblici = massimo false-discovery nel momento sbagliato | 484 come default |
| 30 | CEO | S0.4 tabella EV alternative (productize/evals/consulting/alpha) | Auto | P1 | subagent CEO: il 0/9 è base rate; la lane ricerca deve giustificarsi | solo lane ricerca |
| 31 | CEO | S0.5 channel constraints front-loaded (S3→S1) + exit criterion | Auto | P1 | subagent CEO: vincoli scoperti al mese 8 = investimento channel-invalido | analisi a S3 |
| 32 | CEO | S1.6 meta-kill rule scritta PRIMA + calendario (reddito o "no" definitivo) | Auto | P1 | subagent CEO: gate senza deadline = treadmill | — |
| 33 | CEO | S1.4 net-of-cost come metrica di gate; benchmark cost/roll-adjusted per futures | Auto | P1 | subagent CEO: +2-6% gross può essere negativo netto su intraday | gross Sharpe |
| 34 | CEO | S2.1 timeline dichiarata (100 sess ≈ 4.7 mesi) + trade-frequency check pre-run | Auto | P1 | subagent CEO: ~3 trade su 100 sessioni se regime raro = statisticamente inutile | run 100 sess |
| 35 | Eng | S2.1 guardia per-window + floor totale (249 vuote + 1 NON passa) | Auto | P1 | subagent Eng C2: guardia a livello sessione non basta | guardia sola sessione |
| 36 | Eng | S2.1 `_verify_pin_hash` da warning → FATAL; NESSUN --no-guard; mean_sharpe ≥ -0.5 è negativa → > 0 | Auto | P1 | subagent Eng C2: hash mismatch oggi = run "approved"; soglia negativa lascia passare edge negativo | stato attuale |
| 37 | Eng | S2.1 non-overlapping come DEFAULT: assert n ≤ floor(N/window) | Auto | P1 | subagent Eng C1: step=1 su 250 barre → overlap ~94%, solo 2 finestre reali | "non-overlapping when possible" |
| 38 | Eng | S1.4 sizing bridge pre-registrato (convenzione sizing come campo ledger) PRIMA del cost model | Auto | P1 | subagent Eng H2: returns scale-free, costo per contratto non applicabile | cost model su returns |
| 39 | Eng | S1.4 sharpe unificato in statistics.py (0.0 vs inf divergenti; luck p≈0.002 su serie degenere) + regression test | Auto | P1 | subagent Eng H1: path degenere passa a livello RICERCA oggi | duplicazione attuale |
| 40 | Eng | S4.3 contratto exit code 0=PASSED/1=REJECTED/2=error + test | Auto | P1 | subagent Eng H3: cron senza --require-pass vede GREEN su strategia falsificata | exit 0/2 attuali |
| 41 | Eng | S4.2 pinning (symbol, earliest, latest) o content-hash per intraday; schema coverage.json prima dell'alert | Auto | P1 | subagent Eng H4: row-count su lake live = alert fatigue → silenzio alle 2am | EXPECTED_ROWS |
| 42 | Eng | S4.3 silent skips: n_effective < threshold → exit non-zero; except Exception logga traceback | Auto | P1 | subagent Eng H5: run_portfolio_v2.py:91-120 restringe results silenziosamente | continue attuali |
| 43 | Eng | S1.5 ledger: hash-chaining + concurrency + holdout access-log meccanico | Auto | P1 | subagent Eng M1: JSONL editabile, race sui run paralleli, holdout "a speranza" | ledger naive |
| 44 | Eng | S1.4 "0 breach" = cambio metodologico → ADR dedicato + definizione ledger; DD intraday sul path intraday | Auto | P1 | subagent Eng M6: breach per-window deterministico vs simulazione capovolge i verdetti | tweak di soglia |
| 45 | Eng | S4.1 report identity: key (assets, signals, cutoff, ledger_id) o content-hash | Auto | P2 | subagent Eng M8: due config → stesso walkforward.json si sovrascrivono | nome default |
| 46 | Eng | S2.2 refactor script-as-module (_run_session → library, via sys.path hack) | Auto | P2 | subagent Eng M4: run_g6_wp2_100_sessions.py:49-51 | sys.path hack |
| 47 | Eng | S5.1 showcase.py:574 OrderManager(paper) TypeError + AC RiskRequired vs ValueError + scan construction site | Auto | P2 | subagent Eng M2: BL-040 "fatto" è mezzo fatto | marcare [x] e basta |
| 48 | Eng | S3.2 heartbeat/dead-man's switch (last_success, alert-on-missing-report, dedup, 401→warn) | Auto | P2 | subagent Eng M3: monitor morto = nessun alert, 2am Friday | — |
| 49 | Eng | S3.1 ADR-015 ACCEPTED → BL-071 verifica copertura, non scrittura | Auto | P2 | subagent Eng M2: BACKLOG.md:72 stale | scrivere ADR-015 |
| 50 | DX | S6.8 disclosure dati sintetici in `oracle backtest run` (sine wave senza avviso) | Auto | P1 | subagent DX 1.1: default demo produce risultati fake credibili nel sistema "no fake signals" | stato attuale |
| 51 | DX | S6.9 naming table + trap --max-dd (3 numeri DD, 1 overridable) | Auto | P1 | subagent DX 2.1/2.2: RUNBOOK crasha argparse (--quantity); flag non guida il verdetto | stato attuale |
| 52 | DX | S6.10 soglie da config/qualification/*.yaml SOLO; delete hardcoded; override flag sensitivity | Auto | P1 | subagent DX 2.3: 3 posti, 3 valori, gate g6 a Sharpe NEGATIVO; m31.yaml ha già i valori giusti | 4a copia hardcoded |
| 53 | DX | S5.2 `_resolve_dsn` NON esiste → ImportError su --storage postgres; fix + CI smoke | Auto | P1 | subagent DX 3.3: path production RUNBOOK morto; S5.2 costruisce su path rotto | S5.2 come specced |
| 54 | DX | S5.2 RUNBOOK sync: trade recover, reconcile storage, --quantity→--qty | Auto | P1 | subagent DX 3.4: 3 comandi fittizi nel doc de-facto | — |
| 55 | DX | S1.5 trial ledger contract (storage, CLI, pre-registrazione, holdout enforcement) | Auto | P1 | subagent DX 5.3: il deliverable di governance centrale non ha interface spec | — |
| 56 | DX | S4.1 determinismo: seed per-worker da fold id, byte-match seriale, fix output per-asset sovrascritto | Auto | P1 | subagent DX 5.2: np.random.seed(42) globale viola ADR-012; run_walk_forward sovrascrive | parallel naive |
| 57 | DX | S2.2 fallback silenzioso AdaptiveEnsemble→RegimeAwareEnsemble: warning; _PropFirmAllow logga | Auto | P2 | subagent DX 3.5: sostituzione strategia silenziosa = hazard riproducibilità | — |
| 58 | DX | S5.1 sostituire _PropFirmAllow/_AllowAll con adapter reale (BL-070 closed) | Auto | P2 | subagent DX 3.6: RUNBOOK incident stale | — |

## Dual Voices — Consensus

### CEO (Claude subagent + Codex)
| Dimension | Claude | Codex | Consensus |
|---|---|---|---|
| 1. Premesse valide? | ⚠️ (P4 = asserzione; economia goal non regge) | ✅ (con sfumatura P4) | CONFIRMED con fix S0.2/S0.4 |
| 2. Problema giusto? | ⚠️ (reframing: €3K/mese, non "segnale") | ✅ (diagnosi prima) | CONFIRMED con fix S0.2/S0.4 |
| 3. Scope calibrato? | ✅ (S0 prerequisito) | ✅ | CONFIRMED |
| 4. Alternative esplorate? | ⚠️ (serve tabella EV) | ✅ | CONFIRMED con fix S0.4 |
| 5. Rischi competitivi? | HIGH (spazio esausto, base rate canale) | ✅ | CONFIRMED con fix S0.4/S0.5 |
| 6. Traiettoria 6 mesi? | ⚠️ (kill criterion + calendario mancanti) | ✅ (con governance) | CONFIRMED con fix S1.6 |

### Eng (Claude subagent + Codex)
| Dimension | Claude | Codex | Consensus |
|---|---|---|---|
| 1. Architettura solida? | ✅ | ✅ | CONFIRMED |
| 2. Test coverage sufficiente? | ⚠️ (250-session void; zero-trade hole confermato E2E) | ✅ | CONFIRMED dopo fix C1/C2 |
| 3. Rischi performance? | ⚠️ (O(n²) loop + pin fatigue) | ✅ | CONFIRMED dopo fix |
| 4. Security coperta? | ⚠️ (pin-hash warning = provenance bypassabile) | ✅ | CONFIRMED dopo fix C2b |
| 5. Error paths gestiti? | ⚠️ (silent skips; exit code contract) | ✅ | CONFIRMED dopo fix H3/H5 |
| 6. Deployment risk? | ✅ (cron env leak vector) | ✅ | CONFIRMED dopo fix S5.3 |

### DX (Claude subagent + Codex)
| Dimension | Claude | Codex | Consensus |
|---|---|---|---|
| 1. Getting started < 5 min? | ⚠️ (sintetico senza disclosure; bootstrap non documentato) | ✅ | CONFIRMED dopo fix S6.7/S6.8 |
| 2. CLI naming guessable? | ⚠️ (entry point unico + naming table + --max-dd trap) | ✅ | CONFIRMED dopo fix S6.9 |
| 3. Error messages actionable? | ⚠️ (fail-open exit 0; raw tracebacks) | ✅ | CONFIRMED dopo fix S4.3/H3 |
| 4. Docs findable? | ⚠️ (obsolete paths + 3 comandi fittizi) | ⚠️ | CONFIRMED dopo fix S6.7/S5.2 |
| 5. Upgrade path safe? | ✅ | ✅ | CONFIRMED |
| 6. Dev env friction-free? | ⚠️ (doctor mancante; _resolve_dsn rotto) | ✅ | CONFIRMED dopo fix S6.4/S5.2 |

## Findings completi subagent (estratto dai transcript)

### Claude subagent — CEO (deleg_dc7ebc26) — output completo (10 findings, 4 critical)
1. **CRITICAL — L'economia del goal non regge**: +2-6%/anno → per €3K/mese netti servono €1M-4M+ di capitale (split 80/20), non un account prop. Le soglie (Sharpe 0.5, DD 4%) sono state scelte per raggiungibilità, non per sufficienza rispetto al goal. Fix: modello economico one-page PRIMA di S1; le soglie derivano dal goal.
2. **HIGH — Il problema giusto è "€3K/mese affidabili", non "trova un segnale"**: 8/8 + 0/9 è un posterior forte che QUESTO spazio non ha edge; l'asset differenziato è il platform (lake 316M righe, stack risk/OMS, gate riproducibili). Fix: tabella EV delle alternative (S0.4).
3. **HIGH — P4 è un'asserzione, non una premessa**: l'infra "solida" ha 20,879 partizioni senza lineage, coverage.json stale, BL-040, 4 servizi inutilizzati, G6 passato con 0 trade. L'evidenza è compatibile sia con "ricerca troppo stretta" sia con "qui non c'è edge" — il piano deve distinguerle.
4. **HIGH — Il regime filter è contraddetto dall'evidenza del progetto stesso**: M32a fallì PERCHÉ il classificatore era rotto (29/30 "choppy"). E +2-6% è gross; su intraday con commissioni/spread è plausibilmente negativo netto. Fix: post-mortem prima; net-of-cost dal primo candidato (S1.1/S1.4).
5. **CRITICAL — I gate sono giocabili e il piano li fixa a metà**: 0 trade passa trivially pass_rate≥0.90; "P&L>0 + Sharpe non-zero" passa con 1 trade fortunato. Servono min N trade, min exposure, net-of-cost, entrambi i regimi. 100 sessioni ≈ 4.7 mesi di calendario mai dichiarati (S2.1).
6. **CRITICAL — Nessun kill criterion, nessun ramo di fallimento, nessuna deadline**: "verdetto definitivo" mai definito; cosa succede al goal se G5 chiude "no edge"? Fix: budget bounded (max N family, max 3 mesi), meta-rule scritta (lane chiusa PERMANENTEMENTE se fallisce), calendario (S1.6).
7. **HIGH — Channel constraints sequenziati male**: ToS/daily loss/trailing DD analizzati a S3, DOPO aver fissato le soglie; se il DD realizzato (15.94% M31) confligge con le regole del firm, tutto l'investimento è channel-invalido. Fix: front-load in S1 (S0.5); secondo canale o exit criterion.
8. **CRITICAL — FinClaw 484 è l'espansione peggio temporizzata possibile**: 8/8 appena respinti + cultura luck-test → espandere a 484 fattori pubblici (già arbitrati dalle istituzioni) massimizza il false discovery. Fix: pre-registrazione + FDR/Bonferroni + holdout; meglio spazi non affollati (S1.1).
9. **MEDIUM — Classi di strategia escluse per omissione**: theta/options, stat-arb, crypto MM, latency; "trend = beta" ≠ "trend morto"; il benchmark buy&hold per futures intraday è sotto-esaminato (deve essere cost/roll-adjusted). Fix: una pagina per classe scartata (S1.4).
10. **HIGH — Il moat costruito è infra commodity, lo spazio di ricerca è istituzionalmente esausto**: 0/9 è crowding; il platform è un asset personale, non competitivo; la generazione fattori via LLM è già in costruzione altrove. Fix: nicchie non affollate o pivot al process asset (S0.4).

### Claude subagent — Eng (deleg_55b53c75) — output completo (15 findings, 2 critical)
- **Verdict**: direzione sana (S0-before-S1, gates-before-live, kill/pivot). 15 findings totali: 2 critical / 5 high / 8 medium. Verificato ogni claim contro il codice.
- **C1 CRITICAL — "250 sessioni indipendenti" è teatro sul dataset default**: `run_g6_wp2_100_sessions.py:54` defaulta `data/pinned/ES_1d_m31.parquet` = 250 righe (verificato). Con `--n 250 --window 95`, step=1 → overlap ~94%, solo 2 finestre non sovrapposte; anche n=100 ha overlap identico; `--monte-carlo` campiona con replacement (stesso problema). Alzare 100→250 NON cambia nulla statisticamente. Fix: non-overlapping di default con assert `n ≤ floor(N/window)`, o lake ES completo.
- **C2 CRITICAL — Il buco zero-trade è reale (confermato end-to-end)**: `_run_session` restituisce sharpe=0.0 su std_ret==0; `passed = len(hard_incidents)==0` → sessione 0-trade "passed"; gate: `pass_rate ≥ 0.90 AND mean_sharpe ≥ -0.5 AND mean_dd ≤ 3.0` → run 0-trade = approved, exit 0. Due gap aperti dal piano: (a) serve min trade per-window + floor totale; (b) `_verify_pin_hash` è WARNING non fatale → dataset corrotto = "approved". Inoltre `mean_sharpe ≥ -0.5` è NEGATIVA.
- **H1 — sharpe duplicati con comportamento degenere OPPOSTO**: walkforward.sharpe → 0.0 su varianza zero; statistics._sharpe → inf su costante positiva → luck p ≈ 0.002 "significativo" su serie degenere. Il path che la guardia zero-trade blocca, a livello ricerca oggi PASSA.
- **H2 — cost model unimplementabile come specced**: returns scale-free senza contratti → per-contract commission non applicabile. Fix: sizing convention pre-registrata nel ledger.
- **H3 — Contratto exit code**: senza `--require-pass` un cron vede green su strategia falsificata; exit 2 sovraccarico (config error == verdetto fail).
- **H4 — EXPECTED_ROWS pin vs live lake = alert fatigue**: ogni refresh legittimo innesca sia pin sia drift → rumore; row-count è il meccanismo sbagliato per intraday.
- **H5 — Silent skips in run_portfolio_v2.py:91-120**: `continue` silenziosi → results si restringe, Sharpe sui sopravvissuti, exit 0.
- M1 ledger concurrency/tamper/holdout; M2 showcase.py:574 + ADR-015 ACCEPTED; M3 no heartbeat monitor; M4 sys.path hack; M5 O(n²) loop; M6 "0 breach" metodologico; M7 test verde fuorviante (fixture sempre mock_risk); M8 report path clobbering.
- **Security**: nessuna nuova superficie di rete (monitor outbound-only) — mantenerla così; cron-sourced env = leak vector (usare .env loader/systemd EnvironmentFile); l'auth boundary vero è la decisione gate stessa (pin-hash warning = provenance bypassabile → verification fatale).

### Claude subagent — DX (deleg_ab7a4cb9) — output completo (16 findings)
- **Verdict**: il piano è forte su governance metodologica ma sottile sulla superficie dev che crea; il rischio più grande: i gate runner che producono i verdetti G5/G6 sono **fail-open** (exit 0 su FAIL, Sharpe negativo passa, sessioni 0-trade = PASS) e il piano non lo chiama come fix item. Un operatore solo brucia più tempo a riconciliare verdetti contraddittori di quanto il piano risparmi.
- **DX 1.1 CRITICAL — `oracle backtest run` gira su dati SINTETICI**: apps/cli/main.py:383 genera `_synthetic_ohlcv()` (sine wave) e stampa tabella completa senza disclosure; nel sistema "no fake signals" il default demo produce risultati fake credibili.
- **DX 1.3 HIGH — Due superfici CLI parallele**: scripts/run_*.py (usati dal RUNBOOK) vs CLI `oracle` installata (documentata da nessuna parte).
- **DX 2.1 HIGH — Naming inconsistente**: --asset vs --assets, --tf vs --timeframe, --qty vs --quantity (esempio RUNBOOK crasha argparse).
- **DX 2.2 HIGH — Trap --max-dd**: flag default 5.0 guida l'hard stop di sessione ma il verdetto usa 4.0 hardcoded (g6: 3.0) — tre numeri DD, uno overridable.
- **DX 2.3 CRITICAL — Soglie in 3 posti con 3 valori**: run_walk_forward (0.3/4.0), run_multiasset (0.3/0.1/>BH/2-of-3), g6 (0.90/-0.5/3.0 — Sharpe NEGATIVO); m31.yaml ha già i valori ADR-016 corretti (0.5/0.04/0.10).
- **DX 3.1 CRITICAL — Gate fail-open**: FAIL verdetti exit 0 (salvo --require-pass opt-in); un wrapper CI/Makefile non può distinguere pass da fail.
- **DX 3.2 HIGH — Il fake G6 pass è già nei dati**: STATUS.md post-fix 30/30 "0 trade, 0 P&L, Sharpe 0"; S2.1 deve citare il sito del codice (run_g6_wp2_paper_sessions.py:467).
- **DX 3.3 CRITICAL — `_resolve_dsn` NON esiste**: run_g6_wp2_paper_sessions.py:175 e run_regime_paper_smoke.py:84 lo importano → ImportError su ogni --storage postgres; l'esempio "path production" del RUNBOOK è morto.
- **DX 3.4 HIGH — 3 comandi RUNBOOK fittizi**: trade recover non esiste; --storage non è flag su trade submit; trade reconcile hardcoda InMemoryOMS/InMemoryLedger (main.py:561-562).
- **DX 3.5 MEDIUM/HIGH — Fallback silenzioso**: _build_ensemble scende da AdaptiveEnsemble a RegimeAwareEnsemble su ImportError senza warning (riproducibilità ADR-012); _PropFirmAllow.check_order ingoia eccezioni → False.
- **DX 3.6 MEDIUM — RUNBOOK incident stale**: BL-070 chiuso ✅; adapter wired è script-local _PropFirmAllow, non PropFirmOrderRiskAdapter.
- **DX 4.2 MEDIUM — Data-path confusion**: RUNBOOK usa data/ohlcv legacy; gate runner usano data/lake; nessuna dichiarazione di quale sia canonico.
- **DX 5.1 HIGH — Nessun override soglie**: mancano --sharpe-min/--dd-max/--confirm-min/--cost-config; costi hardcoded (spread 10bps/slippage 5bps/commission 0.85 in _run_session); point values hardcoded 5.0/50.0.
- **DX 5.2 HIGH — Parallelismo senza determinismo**: np.random.seed(42) globale (run_walk_forward.py:248) viola ADR-012; run_walk_forward sovrascrive il singolo file output per asset in multi-asset.
- **DX 5.3 HIGH — Trial ledger senza interface spec**: storage, superficie CLI, workflow pre-registrazione, holdout enforcement non definiti.
- **DX 5.4 MEDIUM — Monitor senza failure-detection**: niente heartbeat/watchdog per il monitor stesso.
