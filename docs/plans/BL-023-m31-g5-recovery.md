# BL-023 — M31 sopra le soglie G5: piano di recupero

> Stato: DRAFT (input per /autoplan)
> Branch: main | Data: 2026-08-03
> Gate: G5 Research Truth | Priorità: P1
>
> ✅ /autoplan: APPROVED 2026-08-03 (auto-decisione, timeout utente).
> Verdetto chiave: run 18a6836 = UNKNOWN (misurazione corrotta), non REJECTED.
> 17 decisioni in audit trail, 21 task aggregati (15 P1 / 6 P2).
> Taste decisions: N onesto 30-36 + probe fattibilità DD/breach al decision
> point (Fase 2) — override possibile in qualunque momento.

## 1. Problema

M31 (historical replay qualification) è il gate G5: certifica che il
backtest engine produce evidenza riproducibile e che la strategia ha
edge statistico. Stato attuale: **REJECTED** dal tentativo `18a6836`.

| Metrica | Target G5 | Ultimo run | Gap |
|---|---:|---:|---:|
| Median Sharpe | ≥ 0.5 | 0.1331 | -0.37 |
| Worst drawdown | ≤ 4% | 15.38% | -11.4pp |
| Hard breaches | = 0 | 96 | -96 |
| Osservazioni | ≥ 48 | 80 | ✅ |

## 2. Diagnosi root cause (REVISIONATA da review avversariale — verdetto UNKNOWN, non REJECTED)

> Il verdetto 0.1331/15.38%/96 del run 18a6836 è **invalido**: la misurazione
> è corrotta da 4 difetti del runner (tutti verificati sul codice, conf 9-10/10).

**F1 — CRITICAL: stop loss da 5 punti su MES ($25) su barre daily ES.**
`stop_distance_points=Decimal("5")` (execution.py:177), MES = $5/punto →
stop a $25 su account $50K. ATR daily medio ES = 53 punti: lo stop viene
toccato nella stessa barra d'ingresso quasi sempre (`_stop_fill_price`).
Spiega DD 15.38% e 100% challenge fallite. Fix: probe sensitivity stop
(5/15/30/60pt e ATR-multiple) + stop ATR-derived PRIMA di ogni verdetto.

**F2 — CRITICAL: warmup posizionato DOPO il periodo, non prima.**
`slice(start_offset, n_bars_period + 30)`: i 30 bar "warmup" sono appesi
dopo la fine del periodo → indicatori freddi a inizio finestra (EMA30,
RSI14, Donchian20, Lorentzian b80, SMA100) + 30 barre fuori periodo
entrano nelle metriche. La finestra regime-specifica è contaminata.
Fix: warmup PRIMA del periodo nel runner.

**F3 — CRITICAL: le 8 varianti 2×2×2 sono 8 copie identiche.**
`ReplayVariant.factorial()` cambia solo flag scouts/debate/fund_manager
che non toccano segnale né esecuzione → 80 osservazioni = 10 curve uniche
(5 periodi × 2 qty) replicate 8×. Il requisito "≥48 osservazioni" è
soddisfatto per duplicazione. Fix: varianti realmente diverse (config
segnale/risk) O N onesto = periodi × quantità indipendenti.

**F4 — HIGH: il 6° regime (macro_surprise) non esiste.**
`select_replay_periods` senza `macro_events` → blocker "Macro surprise
regime missing" sempre attivo; nessuna sorgente macro nel repo. Fix:
workstream ingestione macro (NFP+consensus) O re-spec G5 a "5+1 regimi
condizionati a disponibilità dati" con blocker onesto (decisione utente).

**F5 — HIGH: numeri stale.** Il lake ES 1d ha 6522 barre (2913 ≥ 2015),
non 842. Corretto nella risk table (§6). Nota: anche 2913 barre daily danno
~34 osservazioni uniche — ES 1h (13.7K bar) va promosso a timeframe primario
o cross-check OBBLIGATORIO, non opzionale.

**H1 (dataset)**: direzione giusta, fix insufficiente → ES 1h obbligatorio.
**H2 (breaches)**: MISDIAGNOSI — i 96 breach sono perdite reali (F1+F2),
non un bug di conteggio; l'adapter è nel path e funziona. Il probe H2
diventa probe stop-sensitivity + warmup-placement.
**H3 (nessun edge)**: PREMATURA — il runner rotto non può sostenere
"nessun edge"; i candidati BL-200 sono selezionati in-sample sulle stesse
250 bar. Nuovi candidati: derivati su train pre-2023, validati su holdout
2023+, mai sulla finestra M31.

## 3. Obiettivo (AC — REVISIONATE)

1. **Fix di misura completati e verificati**: stop ATR-based (F1), warmup
   PRIMA del periodo (F2), varianti reali o N onesto (F3) — con test
   dedicati e diff numerico prima/dopo documentato.
2. **Decision point G5 re-spec esplicito** (prima dell'infra): timeframe
   primario (daily vs 1h), soglie, e integrazione dei guardrail esistenti
   che oggi non pesano nella decisione (`luck_p_value`, `factor_attribution`
   calcolati ma ignorati, conf 10/10 verificato in models.py:240).
   Macro regime: o workstream ingestione o re-spec "5+1 condizionato".
   Approvazione utente richiesta qui.
3. **Dataset M31 dal lake, pinned**: ES 1d 6522 bar (2913 ≥ 2015) + ES 1h
   13.7K bar (cross-check OBBLIGATORIO), sha256 in header + provenance da
   lineage.json (BL-307). Numeri verificati, non stale.
4. **Re-run M31 con misurazione corretta**: N onesto di osservazioni
   indipendenti, 0 hard breaches con stop ATR-based, parity broker/ledger.
   Verdetto: APPROVED / REJECTED documentato / UNKNOWN se la misurazione
   non è ancora affidabile. Niente promozione fittizia.
5. **Report `docs/reports/m31-rerun/m31.md`** con dataset hash, config
   segnale completa, regime distribution, liquidated count, luck test.
6. **Gate verdi**: ruff, format, mypy, pytest.

**Principio anti-overfitting (RINFORZATO):**
- Nessun parametro calibrato sulla finestra di valutazione M31.
- Registry di provenance parametri versionato + test di gate che blocca
  se un parametro M31 non ha provenance (enforcement, non solo principio).
- Walk-forward PER ASSET con split temporale fisso (train pre-2023,
  holdout 2023+), mai pool misto ES/NQ/EURUSD/GC.
- Selezione candidati SOLO su train — mai toccare la finestra M31.

## 4. Fasi di lavoro

> ⚙️ Auto-decisioni CEO review (audit trail /autoplan):
> 1. **Refactor, non duplicazione**: modificare `scripts/run_m31_rerun.py` con
>    `--data-source lake|legacy` invece di creare `run_m31_v2.py` (DRY, P4).
> 2. **Guard regime 6/6**: se un regime ha 0 osservazioni nel report, verdetto
>    non può essere APPROVED — GAP marcato esplicitamente.
> 3. **Normalizzatore colonne esplicito** nel runner (lake `timestamp` lowercase
>    vs legacy `Date/Close` uppercase) + testato.
> 4. **`--specialists ensemble|momentum|bollinger`** per testare gli edge BL-200
>    senza toccare codice.
> 5. **Test dedicato probe breaches**: `tests/unit/test_m31_breach_accounting.py`
>    (conteggio per-barra vs per-trade, adapter nel path).
> 6. **Multi-asset M31 solo daily/1h** — mai 1m (8.67M righe EURUSD fuori scope).
> 7. **Report JSON con configurazione completa** del segnale (specialist, min_conf,
>    periodi) per re-run confrontabili.
> 8. **Provenance JSON del pin committato** (pattern BL-001) per rollback via git.
>
> 🔧 Finding ENG review (execution.py verificato, conf 9/10):
> 9. **Liquidazione al primo hard breach** nel loop di replay
>    (execution.py:255-317): chiudere posizioni e fermare nuovi trade per il
>    resto del periodo, osservazione marcata `liquidated`. Senza, il DD può
>    superare il max_overall_loss 4% (run reale: 15.38%).
> 10. **Conteggio breaches esplicito**: `len({breach.type})` (execution.py:389)
>     conta tipi distinti, non eventi. Passare a conteggio eventi + flag
>     `liquidated` per osservazione.
> 11. **Guard regime 6/6 esteso**: se `select_replay_periods` non copre i 6
>     regimi (run 18a6836: 5/6), il run è INVALIDO, non APPROVED/REJECTED.
> 11bis. **FIX CONTABILE FUTURES (scoperto in esecuzione Fase 1, conf 10/10)**:
>     `core/ledger.py` e `QualificationPaperBroker` trattavano i future come
>     cash-equity — ogni BUY addebitava `price × qty` (MES a 4998.5 →
>     −$4998.5), facendo crollare il balance sotto il floor Topstep $48.000
>     alla PRIMA barra di ogni osservazione → hard breach spurio + DD
>     gonfiato. **Questa è la vera fonte dei 96 breach e del DD 15.38% del
>     run 18a6836 — più grave dello stop 5pt.** Fix implementato: flag
>     `futures=True` in `InMemoryLedger.record_fill`/`InMemoryOMS`/broker —
>     il cash si muove solo per P&L + commissione (margine separato),
>     nozionale mai addebitato. Default `False` → nessun impatto sugli altri
>     consumer (simulazioni cash-equity, test esistenti). Verificato: con il
>     fix, il governor non vede più breach spuri (daily_used 0.3% invece di
>     100%).
> 12. **Blocker macro_surprise è il vincolo vero** (conf 10/10): il runner
>     ignora `selection.blockers` (periods.py:133-141) — il run 18a6836
>     risultò "completo" con 5/6 proprio perché il blocker non è mai letto.
>     macro_surprise richiede eventi actual+consensus point-in-time
>     (`MacroSurpriseEvent`): i dati fred nel lake danno solo actual, manca
>     il consensus → o si integra una fonte consensus (forexfactory/
>     investing.com = scraping) o il GAP resta documentato e il run INVALIDO.
>     Decisione: **Fase 1 include il probe di fattibilità macro**; se la fonte
>     consensus non è ottenibile a costo zero, l'AC M31 viene riscritta con
>     5 regimi + blocker esplicito (approvazione utente richiesta al gate).
>
> 🔧 Finding ENG review (22 finding: 11 P1, 9 P2, 2 P3 — tutti verificati):
> 13. **F-01 Liquidazione orfana**: il fix chiave (chiudi pos + halt trade)
>     non è assegnato a nessuna fase/deliverable → nuova "Fase 2b — Risk
>     loop" con test dedicati (F-11).
> 14. **F-02 Bug calendario-vs-barre**: `n_bars_period=(end-start).days+1`
>     (run_m31_rerun.py:116) conta giorni, non barre → sforamento
>     `period.end` di ~17 bar anche post-warmup. Esiste GIÀ
>     `slice_period(data, period, warmup_bars)` (periods.py:147) basata su
>     search_sorted + filtro `<= period.end` — usarla.
> 15. **F-03 Warmup 30 < lookback reale** (SMA100, Lorentzian b80):
>     `warmup_bars ≥ 100` o scartare i primi N bar dalle metriche.
> 16. **F-04 DataRegistry cache-shadow**: `data/ohlcv/ES/1d.parquet` (503
>     bar, 2024-2026) vince sul lake (6522) — DataRegistry è cache-first
>     (providers.py:268). Fix: `force=True` + assert row-count + pin sha256,
>     o cancellare i cache legacy.
> 17. **F-08 N onesto = 10-12 osservazioni**: "≥48" è fittizio anche dopo
>     F3. Re-spec AC: top-3 finestre per regime × 2 qty = 30-36, o 12 con
>     bootstrap a livello finestra; `observation_count ≥ min` nel gate.
> 18. **F-12 DD ≤ 4% non garantito dalla liquidazione**: breach a close,
>     exit a next open, floor fisso $48k → gap overshoot 4.5-6%. Fix:
>     liquidazione a close documentata O soglia ridichiarata O probe
>     overshoot su tutto il lake PRIMA di committare l'AC.
> 19. **F-13 "0 breaches" con qty 2 probabilmente irraggiungibile**: 2-3
>     stop consecutivi = liquidazione giornaliera ($1k daily). Fix: probe
>     fattibilità liquidazione su tutte le finestre del lake in Fase 1;
>     AC riscritto ex-ante se serve ("≤1", "≥90% sopravvissute", qty1-only).
> 20. **F-16 Stop ATR = calibrazione**: il multiplo ATR va scelto SOLO su
>     train pre-2023 e registrato nel registry provenance — altrimenti F1
>     diventa il nuovo veicolo di overfit.
> 21. **F-17 sqrt(252) hardcoded** (execution.py:721, 736): su 1h lo Sharpe
>     è sovrastimato ~4.8×. Fix: parametrizzare `periods_per_year` per
>     timeframe nel runner + statistics + report JSON.
> 22. **F-15 Semantica gate cambiata dalla liquidazione**: DD diventa
>     vincolo di sopravvivenza (tautologico), path-dependency e
>     survivorship vs run storico. Fix: report con metriche troncate +
>     controfattuale "senza liquidazione" + luck test definito su curva
>     troncata o non (esplicito).
> 23. **F-05 Due runner paralleli + gate hand-rolled**: consolidare
>     `run_m31_rerun.py` e `run_replay_qualification.py`; usare
>     `QualificationThresholds` esistente (models.py:230) e includere
>     `luck_p_value`/`factor_attribution` nella decisione.
> 24. **F-09 Rollover UTC vs America/Chicago**: su 1h il daily-loss reset
>     è sistematicamente sbagliato → rollover al fuso del profilo.
> 25. **F-10 Finestre 1h da 1.7 giorni** (window_bars=40 su 1h): servono
>     window dedicate 1h (120-240 bar) e warmup proporzionato.
> 26. **F-14 Test parità col run 18a6836** su dataset legacy (250 bar)
>     entro tolleranza — il refactor non deve cambiare i numeri.
> 27. **F-18 Probe stop non eseguibile**: manca flag CLI
>     `--stop-distance-points` / `--stop-mode atr` → aggiungere.
> 28. **F-20 Walk-forward per-asset fattibile su 1d per tutti**
>     (ES/NQ/EURUSD/GC/BTC 2000+); ES/NQ/GC 1h partono dal 2024 → solo
>     holdout (cross-check legittimo, da dichiarare).
> 29. **F-21 Soglie identiche cross-asset ingenue**: distinguere (a) gate
>     M31 = replay prop su ES/MES; (b) validazione OOS multi-asset =
>     metriche segnale con soglie per-asset dichiarate a priori.
> 30. **F-19 Fallback silenzioso `start_offset=0`** (run_m31_rerun.py:117):
>     usare search_sorted e fallire esplicitamente.

### Fase 1 — FIX DI MISURA (prima di qualunque verdetto, ~1 giornata)

> Ordine corretto dalla review: il runner è rotto, quindi ogni diagnosi
> fatta con esso è spazzatura. Prima si riparano i 4 difetti, poi si misura.
>
> ✅ Stato 2026-08-03 (esecuzione in corso): P1b ✅ (slice_period+warmup≥100
> in run_m31_rerun.py), P1c ✅ (N onesto = periodi × qty), P1e ✅ (6522 bar
> reali via read_from_lake, guard row-count), P1f ✅ (probe riformulato +
> liquidazione), **11bis ✅ fix contabile futures** (ledger/broker: cash =
> P&L+commissione, niente nozionale). Ancora aperti: P1a (stop ATR probe) e
> P1d (probe macro consensus).

- P1a. **Fix F1 — stop ATR-based**: probe sensitivity (5/15/30/60pt,
  ATR-multiple 1/2/3) su ES 1d lake; scegliere la regola stop con
  giustificazione; test dedicato.
- P1b. **Fix F2 — warmup prima del periodo**: spostare i 30 bar di warmup
  PRIMA di `period.start` nel runner; diff numerico prima/dopo.
  ✅ Implementato: `slice_period` (search_sorted + filtro ≤ period.end) +
  `--warmup-bars 100` default; test T2/T4.
- P1c. **Fix F3 — varianti reali o N onesto**: ogni variante = config
  segnale/risk diversa, oppure abolire il fattoriale e riportare
  N = periodi × quantità indipendenti. Il "≥48 osservazioni" deve essere
  N di curve uniche, non replicate. ✅ Implementato: `unique_curves` nel
  report + gate su `min_obs = max(48, unique_curves)`.
- P1d. **Fix F4 — probe macro**: fattibilità sorgente consensus macro
  (forexfactory/investing.com) a costo zero; se non fattibile → opzione
  re-spec "5+1 regimi" da presentare al decision point (AC2).
- P1e. **Fix F5 — numeri veri**: dataset lake ES 1d (6522 bar) + ES 1h
  (13.7K bar) misurati e documentati; niente numeri stale.
  ✅ Implementato: `read_from_lake` (6522 verificato) + EXPECTED_ROWS
  guard + fix `force=True` che saltava il lake (DataRegistry caveat).
- P1f. **Probe H2 riformulato**: i 96 breach sono perdite reali (F1+F2),
  non un bug di conteggio — la verifica è "con stop ATR e warmup corretto,
  quante challenge falliscono ancora?". ✅ Implementato: liquidazione al
  primo hard breach (Fase 2b) + conteggio eventi + test T9/T10.

### Fase 2 — DECISION POINT G5 RE-SPEC (prima dell'infra, ~2h)

> ⛔ GATE UTENTE: nessuna Fase 3 finché non è deciso.

- P2a. Proposta re-spec: timeframe primario (daily vs 1h vs both),
  soglie (Sharpe ≥ 0.5 resta? luck_p_value nel gate? DD ≤ 4% vs
  "vincolo di sopravvivenza"? qty 1-2 vs 1-only?), regimi
  (6 vs 5+1 condizionato), N onesto (top-3 finestre per regime × qty
  = 30-36, o 12 con bootstrap a livello finestra — F-08).
- P2b. Presentare con evidenza: distribuzione Sharpe delle strategie
  esistenti, probe fattibilità liquidazione (F-13: quante finestre del
  lake sopravvivono con qty 2?), probe overshoot DD (F-12), costi di
  ciascuna opzione, impatto su G6/G7.
- P2c. Decisione registrata in ADR (se modifica le soglie o i regimi).

### Fase 2b — RISK LOOP: liquidazione + metriche (NUOVA, ~3h)

> Owner del fix F-01 (era orfano): la modifica a execution.py che
> "spiega il DD" ora ha fase, deliverable e test dedicati.

- P2b1. **Liquidazione al primo hard breach** (execution.py:255-317):
  breach a barra i → chiudi posizioni a market → halt nuovi trade fino
  a fine periodo → `ReplayObservation(liquidated=True)` +
  `ReplayMetrics.liquidated` (models.py).
- P2b2. **Conteggio eventi esplicito**: primo hard breach per
  osservazione (max 1 liquidazione), non `len({breach.type})`.
- P2b3. **Periodi annualizzati parametrizzati**: `periods_per_year`
  per timeframe (F-17: 252 daily, ~5796 1h) in runner + statistics +
  report JSON — altrimenti Sharpe 1h sovrastimato 4.8×.
- P2b4. **Rollover al fuso del profilo** (F-09): America/Chicago per
  Topstep, non UTC.
- P2b5. Test: `tests/unit/test_m31_liquidation.py` (F-11) — breach →
  flat a open i+1, zero nuovi ordini, equity piatta (Sharpe ≈ 0,
  truncation bias verso 0 non negativo), gap overshoot, max 1 evento;
  `tests/unit/test_m31_sharpe_annualization.py` (F-17).

### Fase 3 — Infrastruttura dataset M31 (~2h, ridimensionata)

> La review ha mostrato che pinning/hashing/audit esistono GIÀ
> (`check_dataset_pin.py`, hashing nel runner, `audit_lake_metadata.py`).
> Fase ridotta al minimo: punto di ingresso lake + fix slicing.

- P3a. `scripts/run_m31_rerun.py`: `--data-source lake|legacy` +
  `--specialists` + `--stop-distance-points`/`--stop-mode atr`
  (F-18) (refactor, non duplicazione).
- P3b. **Slicing con `slice_period`** (F-02/F-19): niente bug
  calendario-vs-barre, niente fallback `start_offset=0` silenzioso —
  search_sorted + fail esplicito. Warmup ≥ 100 bar (F-03) o scarto
  dei primi N bar dalle metriche.
- P3c. **DataRegistry `force=True` + assert row-count + pin sha256**
  (F-04): il cache legacy `data/ohlcv/ES/1d.parquet` (503 bar) non
  deve oscurare il lake (6522). Cancellare i cache legacy o pin
  committato con conteggio atteso.
- P3d. Consolidare i due runner (F-05): deprecare
  `run_replay_qualification.py`, verdetto da `QualificationThresholds`
  (models.py:230) con `luck_p_value`/`factor_attribution` nel gate.
- P3e. Numeri validati dal parquet (F-07): row-count atteso nel pin
  (guardia anti-stale; coverage.json è inaffidabile: ES|1d dice 13042,
  reale 6522).
- P3f. Report: config segnale completa, regime distribution, liquidated
  count, luck test (curva troncata o non — esplicito, F-15),
  controfattuale senza liquidazione (F-15).

### Fase 4 — Segnale (condizionato da AC1+AC2, ~1 giornata)

- P4a. Se il re-run con misurazione corretta mostra Sharpe ≥ 0.5: nessuna
  modifica al segnale, validazione walk-forward per-asset (train pre-2023,
  holdout 2023+) come enforcement.
- P4b. Se sotto soglia: candidati derivati su train pre-2023 SOLO
  (roc_momentum_12, bollinger, donchian — ri-derivati, non presi dal
  BL-200 in-sample), validati su holdout 2023+; mai sulla finestra M31.
- P4c. Registry provenance parametri + test di gate (blocco se parametro
  senza provenance) — include il multiplo ATR dello stop (F-16).
- P4d. **Walk-forward per-asset**: fattibile su 1d per tutti
  (ES/NQ/EURUSD/GC/BTC 2000+); ES/NQ/GC 1h = solo holdout (F-20).
  Soglie per-asset dichiarate a priori (F-21): gate M31 = replay prop
  ES/MES; OOS multi-asset = metriche segnale con soglie proprie.
- P4e. Specialist: parametri invarianti per asset o evidenza che la
  calibrazione ES regge su holdout per-asset (F-22) — mai "correzioni"
  asset per asset.

### Fase 5 — Re-run M31 e gate (~2h)

- P5a. Esecuzione completa con misurazione corretta: N onesto di
  osservazioni indipendenti, stop ATR-based, warmup prima, 0 hard breach.
- P5b. Report versionato `docs/reports/m31-rerun/m31.md` + JSON.
- P5c. Gate G5: APPROVED / REJECTED documentato / UNKNOWN (se la
  misurazione non è ancora affidabile). Pivot esplicito se REJECTED.
- P5d. Aggiornare BACKLOG.md (correggere numeri stale: 0.34/88/15.9%
  → 0.1331/96/15.38%) + STATUS.md.

## 5. Cosa NON è in scope

- G6 paper sessions (BL-024) — gate separato, dipende da G5.
- G7 prop-firm selection (BL-100) — dopo G5+G6.
- Cross-asset factor timing completo (BL-202) — solo se serve per il
  segnale M31, altrimenti resta backlog.
- Strategy catalog (BL-400+) — backlog.
- Ottimizzazione iperparametri con GA/genetics — esplicitamente fuori:
  rischio overfit su dataset piccolo.

## 6. Rischi

| Rischio | Prob. | Impatto | Mitigazione |
|---|---|---|---|
| Sharpe ≥ 0.5 irraggiungibile su daily ES anche con misura corretta | Alta | G5 resta REJECTED | Decision point AC2 (re-spec timeframe/soglie) + pivot esplicito |
| Overfit su 2913 bar daily | Media | G5 falso positivo | Walk-forward per-asset con split fisso pre-2023/2023+ + registry provenance parametri con enforcement |
| ES 1h (13.7K bar) non basta come cross-check | Media | Dataset ancora piccolo | Multi-asset (NQ, EURUSD 1h/4h) nel walk-forward, mai pool misto |
| Blocker macro_surprise irrisolto | Alta | AC "6 regimi" irraggiungibile | Re-spec "5+1 condizionato" al decision point (AC2) |
| Varianti replicate (F3) gonfiano N | Certa | Falso "≥48 osservazioni" | N onesto = curve uniche (fix F3 in Fase 1) |
| BACKLOG/STATUS con numeri stale | Certa | Confusione decisionale | Correzione documentata in P5d |

## 7. Dipendenze

- BL-307 (lineage/coverage lake) — ✅ completato, lineage verificabile.
- BL-301/302 (DataRegistry lake-aware) — ✅ esistente.
- BL-021 (MES sizing) — ✅ esistente.
- BL-070 (PropFirm risk adapter) — ✅ esistente, da VERIFICARE nel path
  M31 (H2).

## 7bis. Architecture (Eng review)

```
scripts/run_m31_rerun.py (refactor: --data-source, --specialists)
  │
  ├─ DataRegistry (BL-302) ──> lake normalized (ES 1d 6522 bar, multi-asset)
  ├─ legacy path: data/ohlcv/ES_1d.parquet (250 bar, invariato)
  │
  └─ EventDrivenQualificationRunner (execution.py, refactor)
       ├─ PropFirmRiskGovernor (update+eval a ogni barra)
       ├─ PropFirmOrderRiskAdapter (risk.check_order, riga 462)
       ├─ InMemoryOMS/Ledger + QualificationPaperBroker (reconcile)
       └─ [NEW] liquidazione: hard breach → close posizioni + halt trade
            → osservazione ReplayObservation(liquidated=True)
  │
  └─ Report m31.md/.json (hash, config segnale, regime dist, liquidated)
```

Copia esistente: nessun nuovo componente di infrastruttura. Unico punto di
accoppiamento nuovo: runner → DataRegistry (già usato da altri script).

## 7ter. Failure Modes Registry (Eng — aggiornato con i fix)

| CODPATH | FAILURE MODE | RESCUED? | TEST? | USER SEES? | LOGGED? |
|---|---|---|---|---|---|
| runner loop | hard breach senza liquidazione → DD > 4% | Y (Fase 2b) | Y T9/T10 | verdetto onesto | Y |
| breach count | tipi distinti vs eventi (96 ambigui) | Y (Fase 2b) | Y T1 | conteggio eventi | Y |
| select_replay_periods | blockers ignorati → 5/6 "completo" | Y (Fase 3d) | Y T2 | run INVALIDO | Y |
| slicing | calendario-vs-barre + sforamento end | Y (Fase 3b) | Y T4/T5 | barre fuori periodo | Y |
| DataRegistry | cache-shadow 503 vs lake 6522 | Y (Fase 3c) | Y T4/T5 | assert row-count | Y |
| annualizzazione | sqrt(252) su 1h → Sharpe 4.8× | Y (Fase 2b3) | Y T11 | metrica corretta | Y |
| pin mismatch | dataset cambiato | Y | Y | exit 1 | Y |
| DataRegistry | simbolo assente | Y | Y | errore esplicito | Y |

CRITICAL GAP: le prime 4 righe — tutte coperte dai test T1-T12 (vedi test plan) + guard regime (P2a/C2).

Mappatura finding ENG → fasi/deliverable/test (F-01, F-06):

| Finding | Fase | Deliverable | Test |
|---|---|---|---|
| F-01 liquidazione orfana | 2b | execution.py + models.py | T9/T10 |
| F-02 calendario-vs-barre | 3b | run_m31_rerun.py (slice_period) | T4/T5 |
| F-03 warmup 30 < lookback | 3b | warmup ≥ 100 | T4/T5 |
| F-04 cache-shadow DataRegistry | 3c | force=True + pin | T4/T5 |
| F-05 due runner + gate hand-rolled | 3d | consolidamento + QualificationThresholds | T8 |
| F-07 numeri stale (coverage.json) | 3e | row-count atteso nel pin | T6 |
| F-08 N onesto fittizio | 2a | re-spec AC | T2 |
| F-09 rollover UTC vs Chicago | 2b4 | fuso profilo | T9 |
| F-10 blockers ignorati | 2a/3d | gate INVALIDO nel codice | T2 |
| F-11 test liquidazione mancanti | 2b5 | test_m31_liquidation.py | T9/T10 |
| F-12 DD ≤ 4% non garantito | 2b | liquidazione a close o re-spec soglia | T10 |
| F-13 0 breaches con qty 2 | 2b | probe fattibilità su lake | T12 |
| F-14 parità run 18a6836 | 3b | test regressione legacy | T4/T5 |
| F-15 semantica gate cambiata | 2b/3f | report troncato + controfattuale | T8 |
| F-16 stop ATR = calibrazione | 4c | registry provenance + train-only | T12 |
| F-17 sqrt(252) hardcoded | 2b3 | periods_per_year parametrizzato | T11 |
| F-18 probe stop non eseguibile | 3a | flag CLI | T12 |
| F-19 fallback start_offset=0 | 3b | search_sorted + fail esplicito | T4/T5 |
| F-20 walk-forward per-asset | 4d | split temporale fisso per asset | — |
| F-21 soglie cross-asset ingenue | 4d | soglie per-asset a priori | — |
| F-22 specialist ES-centrici | 4e | invarianza o evidenza holdout | — |

## 8. Deliverable

- `docs/reports/m31-rerun/notes.md` — diagnosi root cause (F1-F5 + ENG)
- `analytics/qualification/execution.py` — liquidazione + periods_per_year
  + rollover fuso profilo (Fase 2b)
- `analytics/qualification/models.py` — `liquidated` flag + conteggio eventi
- `scripts/run_m31_rerun.py` (refactor: `--data-source`, `--specialists`,
  `--stop-mode`, slicing con `slice_period`) + deprecazione
  `run_replay_qualification.py` (F-05)
- `data/pinned/ES_1d_m31_v2.parquet` + provenance (row-count 6522 atteso)
- `docs/reports/m31-rerun/m31.md` + `.json` — report gate (troncato +
  controfattuale, luck test, periods_per_year)
- Test: T1-T12 (breach accounting, liquidazione, annualizzazione, stop
  sensitivity, regime coverage, runner lake, pin, report schema, parity)
- BACKLOG.md / STATUS.md aggiornati (numeri corretti, non stale)

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|
| 1 | CEO-S1 | Refactor run_m31_rerun.py con `--data-source` invece di nuovo script | Mechanical | P4 DRY | Due script paralleli = duplicazione | run_m31_v2.py |
| 2 | CEO-S2 | Guard regime 6/6: verdetto APPROVED impossibile con regimi mancanti | Mechanical | P1 Completeness | Report "completo" con 5/6 regimi = falso verde | nessuna |
| 3 | CEO-S4 | Normalizzatore colonne esplicito + testato | Mechanical | P5 Explicit | lake lowercase vs legacy uppercase | rename silenzioso |
| 4 | CEO-S5 | `--specialists ensemble\|momentum\|bollinger` | Taste | P5 Explicit | Edge BL-200 testabili senza toccare codice | hardcoded |
| 5 | CEO-S6 | Test dedicato probe breaches (H2) | Mechanical | P1 Completeness | H2 è il fix potenzialmente decisivo, va testato | nessun test |
| 6 | CEO-S7 | Multi-asset M31 solo daily/1h, mai 1m | Mechanical | P3 Pragmatic | 8.67M righe 1m fuori scope gate daily | EURUSD 1m in M31 |
| 7 | CEO-S8 | Report JSON con config completa del segnale | Mechanical | P1 Completeness | Re-run confrontabili | report minimale |
| 8 | CEO-S9 | Provenance pin committata (pattern BL-001) | Mechanical | P2 Boil lakes | Rollback via git revert | pin non versionato |
| 9 | ENG-F01 | Fase 2b Risk loop: liquidazione con owner+fase+test | Mechanical | P1 Completeness | Il fix che spiega il DD era orfano | liquidazione senza owner |
| 10 | ENG-F02 | Usare slice_period esistente (search_sorted) | Mechanical | P4 DRY | slice_period esiste già, corretto | slicing hand-rolled |
| 11 | ENG-F04 | DataRegistry force=True + assert row-count + pin | Mechanical | P5 Explicit | 503 bar non devono vincere su 6522 | cache-first silenzioso |
| 12 | ENG-F08 | AC N onesto: 30-36 (top-3×qty) o 12+bootstrap finestra | Taste | P1 Completeness | "≥48" è fittizio per duplicazione | N replicato |
| 13 | ENG-F12/F13 | AC DD/breach ridefiniti al decision point con probe ex-ante | Taste | P3 Pragmatic | DD≤4% e 0 breach probabilmente irraggiungibili come scritti | AC promessi |
| 14 | ENG-F17 | periods_per_year parametrizzato per timeframe | Mechanical | P5 Explicit | sqrt(252) su 1h = Sharpe x4.8 | annualizzazione hardcoded |
| 15 | ENG-F05 | Consolidare i due runner + QualificationThresholds + luck test nel gate | Mechanical | P4 DRY | Gate hand-rolled, luck ignorato | due runner paralleli |
| 16 | ENG-F15 | Report troncato + controfattuale senza liquidazione | Mechanical | P1 Completeness | Separare effetto fix da effetto segnale | solo metriche troncate |
| 17 | ENG-F16 | Multiplo ATR stop scelto solo su train pre-2023 + registry | Mechanical | P1 Completeness | Altrimenti F1 = nuovo overfit | ATR su lake intero |
