# Oracle — Distillazione del repository — design spec

> Data: 2026-09-17 · Stato: PROPOSED (attende review utente)
> Branch: `feat/p1-metrics-truth` (63 commit avanti su `main`, 0 dietro)
> Gerarchia: questa spec → piano di implementazione (`writing-plans`) → BACKLOG → ADR
> Approccio scelto: **confine dichiarato, poi demolizione** (non demolizione diretta,
> non split in due repository).
> Traguardo 3-6 mesi: **Lane B in paper reale su IBKR come canale personale, e G7
> su firm CFD con single-stock CFD**.

---

## 0. Contesto — lo stato misurato

Tutte le cifre di questa spec sono misurate, non stimate. Gli strumenti di misura
(`census.py`, `reach.py`, `boundary.py`, `boundary2.py`, `dirloc.py`) vivono oggi
in `.scratch/`, che è gitignored: la **Fase 1 li promuove in `scripts/measure/`**,
così i numeri di questa spec sono riproducibili da chiunque e non solo da chi li
ha prodotti. Senza quello, "misurato" è un'affermazione non verificabile.

### 0.1 Il progetto

| | |
|---|---|
| Disco occupato | 28 GB (12 GB escludendo `.venv`, `.git`, `.lint_venv`, `node_modules`) |
| File `.py` | 2.269 — di cui 184.346 LOC (51%) sono copie in `.omx`, 34.281 vendored in `trading-os/` |
| Codice Oracle reale | ~145.000 LOC |
| File tracciati | 1.240 |
| Documenti | 316 file / 13 MB |
| Test | **3.681 passed, 7 skipped, 0 failed in 4m25s** |
| CI | ruff, ruff-format, mypy --strict, import-linter, gitleaks, uv-lock, tutti bloccanti |

### 0.2 L'edge

| | |
|---|---|
| G0, G1, G3, G4 | ✅ PASSED |
| G2 | 🟡 PARTIAL |
| **G5 research truth** | ❌ REJECTED — median Sharpe −0.251, luck p=1.0 |
| **G6 paper** | 🟡 REJECTED — pass-rate 0.35 vs 0.90 richiesto |
| G7, G8, G9 | ⚪ NOT_STARTED |
| Edge Factory | 49 ipotesi: 39 `da_amplificare`, 3 amplificate, 4 REJECTED, 1 morta, 1 in qualifica, **1 APPROVED** (EF-006, ETH funding-z) |
| Sprint Renaissance-parity (2026-09-04/05) | 0/3 famiglie qualificate → NO-GO |
| Portafoglio SR-max | 16 leg, SR(N) saturo a **1.40** |

L'unica cosa qualificata è **Lane B composite value** (Piotroski 40% +
Greenblatt 40% + Lakonishok 20%, threshold 0.65, top-15, rebalance trimestrale),
e — vedi §1.1 — il suo verdetto di qualifica è **fallito**.

### 0.3 I due difetti bloccanti trovati in fase di analisi

**D1 — Il gate di qualifica di Lane B è fallito, e il documento di stato dice il contrario.**

`docs/reports/lane-b-composite/2026-09-03-bl726-qualification.json`:

```
.verdict                      = 'REJECTED_TREE_INTEGRITY'
.metadata.tree_integrity_ok   = False
.ic_screen.passes             = False
```

`docs/ORACLE_AUTOPILOT_STATUS.md` riporta lo stesso file come
«🟢 QUALIFICATO (BL-727)». I numeri di performance passano tutti i gate
(DSR 0.999, PSR 0.999, CPCV OOS median 1.46, haircut Sharpe 0.673, bear 2022
Sharpe 1.21) — ma un prereg fallito non è un prereg passato.

Il messaggio d'errore è anche fuorviante: `reasons[0]` recita
`HEAD 7f4058a… != pinned 7f4058a…` con le due stringhe **identiche**.
`analytics/research/factory/prereg.py:205` (`verify_clean_tree`) solleva
`PreregError` per due cause distinte — HEAD diverso **oppure** working tree
sporco nei percorsi che invalidano il prereg — e
`scripts/run_bl726_prereg_qualification.py:415-421` le riporta entrambe come
"HEAD drift". Dato che HEAD combacia, la causa reale era un working tree
sporco, e il run è stato forzato con `--allow-head-mismatch`.

**D2 — Il runner paper non può eseguire Lane B.**

- `config/paper.yaml`: simboli `SPY, QQQ, AAPL, MSFT`, `tick_interval_s: 60.0`,
  `timeframe: 1m`.
- `execution/runner.py:501`: `self._signal_source = signal_source or NoopSignalSource()`
  — nessun segnale reale cablato.
- Lane B: rebalance trimestrale, 15 holdings, 120 ticker unici, universo SimFin.

Il runbook dichiara il gap («the Lane B adapter ships in BL-728»); BL-728 ha
consegnato l'adapter, non il cablaggio. Oggi "Lane B in produzione" significa un
loop a 1 minuto che non emette ordini, su simboli che Lane B non traderebbe.

---

## 1. Decisioni chiuse

Prese in conversazione il 2026-09-17. Sono vincolanti per il piano.

### 1.1 Approccio

**Confine dichiarato, poi demolizione.** Il confine si fa prima, è reversibile in
un giorno, e la distinzione «questo è produzione, quello è ricerca» è il guadagno
vero — non i gigabyte. La demolizione segue, e viene dopo perché senza un confine
scritto la schifezza si riforma: è il processo che l'ha generata.

Scartate: demolizione diretta (nessun confine ⇒ ricaduta garantita); split in due
repository (con un solo sviluppatore il costo di coordinamento supera il beneficio).

### 1.2 Allowlist lean-ctx

Estesa in modo **additivo** (`lean-ctx allow`, che appende a `shell_allowlist_extra`
senza intaccare la lista built-in): `xargs`, `paste`, `pgrep`, `tee`, `jq`, `comm`,
`file`, `stat`, `tree`, `rsync`. Effetto verificato: 216 → 221 comandi permessi,
`xargs`/`paste`/`pgrep` funzionanti.

Restrizioni permanenti che **non** si possono togliere per via additiva, e che il
piano deve assumere:

| Vietato | Regola operativa |
|---|---|
| `find … -exec` | usare `find … -print \| xargs …` (ora possibile) |
| heredoc (`<<EOF`) | scrivere un file e poi eseguirlo |
| `python3 -c` | scrivere un file e poi eseguirlo |
| `$(…)` / backtick in posizione di comando | niente command substitution |
| `\|` dentro un pattern quotato | il wrapper spezza il comando e valida ogni pezzo come eseguibile ⇒ niente alternanza nelle regex |

`Monitor` è risultato bloccato dallo stesso meccanismo; il wait affidabile si fa
con `Bash` in `run_in_background` + lettura del file di output.

### 1.3 G7

**Lane B → G7 su firm CFD** (FTMO / The5ers, single-stock CFD via MT5).
L'aritmetica di convenienza (Monte Carlo 200k path, barriere statiche, dai numeri
BL-726: 19,68%/anno, σ 13,77%/anno) dà 68,3% di pass a 1× su FTMO 2-Step P1, e
**peggiora con la leva** (41,1% a 3×) — coerente con BL-094: in un envelope eval
il vincolo dominante è il drawdown, non il rendimento.

Le firm futures del repo (Topstep `allowed_products=["ES","MES"]`, Apex, TPT,
MFFU, FundedNext) sono escluse: Lane B è selezione cross-sectional di singole
azioni USA e non è esprimibile su un venue ES/MES.

**Rischio aperto, da chiudere in Fase 0b**: (i) FTMO/The5ers offrono single-stock
CFD sui 15 value small/mid cap che Lane B seleziona? Le liste simboli CFD sono
tipicamente ristrette a large cap, e un universo ristretto cambia la strategia,
non solo il venue. (ii) Quanto costa lo swap su un hold trimestrale, su un
rendimento annuo del 19,7%? Se (i) fallisce, G7-CFD cade.

### 1.4 Il confine — ampiezza

Il confine tiene **tutto** salvo un elenco esplicito di esclusione.

| | file | LOC |
|---|---:|---:|
| **dentro** | 361 | 57.928 |
| fuori | 205 | 52.079 |
| di cui vendored (`trading-os/`, già gitignored) | 116 | 34.281 |
| **codice first-party fuori** | 89 | **17.798** |

Dentro: `core`, `market`, `execution`, `policy`, `analytics`, `agents`, `apps`,
`alerting`.
Fuori: `genetics/` (7.553), i moduli off-path di `analytics/strategy/` (8.791),
`application/` (129), `audit/`, `orchestration/`, `research/`, `trading-os/`.

**Criterio per `analytics/strategy/`, non una lista a mano.** Il package ha 40
moduli; sono fuori quelli **non raggiungibili** dai root del percorso di
produzione (`scripts/run_paper`, `paper_report`, `backfill_1m_ibkr_paper`,
`run_bl726_prereg_qualification`, `analytics.strategy.lane_b_adapter`,
`analytics.qualification.lane_b`). La lista si **genera** con `.scratch/boundary.py`
(promosso in Fase 1), non si mantiene a mano: una lista scritta a mano in una spec
drift-a entro un mese, ed è esattamente il modo in cui il repo è arrivato qui.

Il confine tiene il **76%** del codice first-party. Va detto con chiarezza: **a
questa ampiezza il confine non distilla, certifica.** Il suo valore è la regola di
chiusura, lo split del CLI, e l'esclusione definitiva degli off-path. La riduzione
vera deve venire dalle Fasi 1 e 3.

---

## 2. Il design

### 2.1 Due contratti, non uno

Dentro 57.928 LOC ci sono moduli che non devono poter mandare ordini. Un solo
contratto non basta.

**Contratto A — chiusura del confine.**
Nessun modulo dell'insieme «dentro» può importare un modulo dell'insieme «fuori».
Meccanismo: `[[tool.importlinter.contracts]]` in `pyproject.toml` (già configurato
e bloccante, riga 418), più un test che asserisce la chiusura dell'insieme.
Effetto collaterale necessario: **`apps/cli/main.py` va spezzato** in `oracle`
(produzione) e `oracle-lab` (laboratorio). Oggi la sua closure transitiva tira
dentro `agents.*` (26 moduli) e cinque moduli di `analytics.strategy`: con il CLI
come radice, "produzione" sono 162 moduli / 26.381 LOC, cioè tutto.

**Contratto B — percorso ordini.**
Insieme stretto e **non allargabile per comodità**: mode guard → risk kernel →
OMS → broker. Vietato importare `agents`, `apps`, `analytics/research`, e
`analytics` salvo i contratti di segnale. È il contratto che protegge i soldi, ed
è l'unico che non si allarga mai.

Lavoro già noto per il Contratto B: `analytics/strategy/lane_b_adapter.py` importa
`execution.paper_orchestrator` (il docstring lo chiama «P2 parity-port exception»).
La dipendenza va invertita: l'adapter espone un protocollo, `execution` lo consuma.

### 2.2 Cosa NON è nel design

- Nessun cambio alla logica dei gate di qualifica (vedi §3.0a).
- Nessuna modifica a `policy/prop_firm/fixtures.py` senza ADR (vietato da PROJECT.md).
- Nessuna cancellazione di documenti. I report **sono** l'evidenza dei verdetti:
  è l'unica categoria dove cancellare distrugge valore vero.
- Nessun merge su `main`, nessun push, nessun `git branch -D` nel run autonomo.

---

## 3. Le fasi

### Fase 0 — verifiche bloccanti

Da fare **prima** di qualunque pulizia: senza queste, ogni igiene è cosmetica.

**0a — BL-726 v2 + BL-727 v2.**
Il commit pinnato nel manifest cambia quando si include il fix, quindi non è un
"re-run": è una riapertura. La §7 di `docs/research/prereg/BL-726-lane-b-composite-variant.md`
lo prescrive: *«the only acceptable post-result action is to declare the variant
REJECTED and re-open BL-726 with a new manifest version»*.

Ordine:
1. Fix di `prereg.py`: due cause d'errore distinte (`HEAD_MISMATCH` vs
   `DIRTY_TREE`), messaggio che nomina la causa vera e stampa i path offensivi.
   **Il fix tocca solo messaggio e classificazione — mai la logica.** `verify_clean_tree`
   deve continuare a rifiutare sia HEAD diverso sia tree sporco.
2. Nuovo manifest BL-726 v2 (commit pinnato, parametri, finestra, soglie).
3. Re-run **senza** `--allow-head-mismatch`, su tree pulito.
4. Correzione di `docs/ORACLE_AUTOPILOT_STATUS.md`: oggi dichiara QUALIFICATO un
   report il cui verdetto è REJECTED_TREE_INTEGRITY.
5. Qualunque sia il verdetto, si scrive. Se fallisce di nuovo, Lane B non è
   qualificato e il piano cambia.

**0b — Verifica G7-CFD.** Le tre domande di §1.3. Richiede ricerca web (Tavily
primario, SearXNG secondario) e lettura delle liste simboli ufficiali FTMO/The5ers.
Popolamento di `allowed_products` per i profili CFD: oggi il campo esiste
(`policy/prop_firm/profile.py:211`) ed è popolato **solo** per Topstep
(`fixtures.py:58`).

**0c — IC screen sul fattore vero.** Estendere `LaneBBacktestResult` con la serie
per-rebalance e rifare lo screen. Oggi la §«Methodology caveat» del report ammette
che vengono passati i rendimenti giornalieri del portafoglio come proxy del
fattore: misurare l'autocorrelazione di una equity curve e chiamarla IC non è un
test del fattore. Alternativa scartata: dichiararlo non-applicabile nel manifest,
che è un buco nel gate — e il valore di questo repo è di non averne.

**0d — Forma del runtime.** EOD batch sui giorni di rebalance, **riusando**
`execution/runner.py` come motore di ciclo (store durevole idempotente BL-729,
kill-switch, alerting, heartbeat, SIGTERM graceful sono già corretti). Si
sostituiscono clock e signal source con un `LaneBEodSignalSource` e un clock a
giorni di rebalance. Non si riscrive il runner.

### Fase 1 — igiene (reversibile, zero cambi di semantica)

**Fisica:**

| | |
|---|---|
| `.omx/` + 3 worktree registrati | 6,8 GB — `.venv` per-worktree da 2,5 GB l'una |
| `.lint_venv/` | 912 MB (secondo venv solo per il lint) |
| `.mypy_cache/` | 252 MB |
| `.ruff_cache/`, `.pytest_cache/`, `.coverage` | ~3,8 MB + 320 KB |
| `checkpoints/`, `oracle.egg-info`, `.import_linter_cache` | residui |
| worktree `/tmp/oracle-trading-wt` | prunable |

**Documenti** (consolidare, mai cancellare):
- un `docs/INDEX.md` che dice cosa è canonico e cosa è storico;
- `BACKLOG.md` (68 KB monolite) spezzato per area, con il file indice che resta;
- `ROADMAP.md` (41 KB) potato della tassonomia G10–G14, **congelata** da §14 e mai
  eseguita;
- i 28 doc sciolti in `docs/` ricollocati in `docs/plans/`, `docs/reports/` o
  `docs/archive/`.

**Script** (126 → ~15): i 51 `run_*` di sprint conclusi, i 5 `probe_*`, i 3
`introspect_*`, i 2 `investigate_*`, i 7 `check_*` e `scripts/legacy/` vanno in
`scripts/archive/` — **spostati, non cancellati**. Regola di ammissione a
`scripts/`: lo script o è un entrypoint operativo, o rigenera un artefatto
committato.

**Shell vuoti**: `probe/` (0 file), `orchestration/`, `research/`, `application/`,
`audit/` — esistono solo come `__init__.py` eppure sono nello scope di mypy strict
e import-linter in CI.

**Branch**: si decide con l'utente presente. Nel run autonomo, al massimo un branch
di lavoro dedicato.

### Fase 2 — i due contratti in CI

Contratto A + Contratto B in `pyproject.toml`, test di chiusura, split del CLI.
Criterio di uscita: i due contratti passano **e** i 3.681 test restano verdi.

### Fase 3 — distillazione

- Archivio con tag di `genetics/`, `experiments/`, dei moduli off-path di
  `analytics/strategy/` (elenco generato da `.scratch/boundary.py`, non scritto a
  mano).
- Ricerca esterna sui quattro assi richiesti: sostituzione di codice custom con
  OSS; infrastruttura free/self-hosted ($0/mese, vincolo noto: nessun dato
  finanziario a pagamento); tool sistematic-trading esistenti (aggiornamento del
  BOM `awesome-systematic-trading` già fatto in agosto); fonti dati per allargare
  l'universo di Lane B.
- Prima candidata alla sostituzione: la dashboard custom (~50 file TSX, 176 MB di
  `node_modules`, React + Vite + nginx) per un operatore singolo che guarda i
  grafici. Seconda: `alerting/` (1.049 LOC) contro un servizio self-hosted.

### 3.1 Decomposizione in piani

Questa spec è una sola, ma **non è un solo piano di implementazione**. Tre piani
separati, in quest'ordine, ciascuno con il suo criterio di uscita:

| Piano | Copre | Dipende da |
|---|---|---|
| **P1** | Fase 0a, 0c, 0d (prereg v2, IC screen, runtime EOD) | niente — è autonomo |
| **P2** | Fase 1 + Fase 2 (igiene, contratti, split CLI) | P1 non è prerequisito |
| **P3** | Fase 0b (verifica G7-CFD) + Fase 3 (archivio, ricerca esterna, sostituzioni) | P3 non parte finché 0b non ha risposta |

P1 e P2 sono indipendenti e possono procedere in parallelo. P3 è bloccato dalla
verifica esterna, che è la ragione per cui è ultimo: se FTMO/The5ers non offrono
CFD sui 15 titoli, il traguardo G7-CFD cade e P3 va riscritto, mentre P1 e P2
restano validi.

---

## 4. Verifica

| Fase | Criterio | Evidenza |
|---|---|---|
| 0a | verdetto preregistrato emesso su tree pulito, senza `--allow-head-mismatch`; STATUS.md coerente col report | report `.md`/`.json` + diff di STATUS.md |
| 0b | tre domande risposte con fonte primaria citata | doc in `docs/firm_sources/` con snapshot |
| 0c | IC screen eseguito sulla serie per-rebalance | report aggiornato |
| 0d | runner EOD esegue un rebalance completo in smoke | test + log |
| 1 | nessun test cambia esito; `du` misurato prima/dopo | output pytest + `du -sh` |
| 2 | i due contratti passano e i 3.681 test restano verdi | output import-linter + pytest |
| 3 | LOC dentro il confine in discesa; CI verde | `.scratch/boundary2.py` + pytest |

La rete di sicurezza è reale: **3.681 test in 4m25s**, girabile più volte per
notte. È abbastanza veloce da essere il criterio di non-regressione di ogni fase.

---

## 5. Guardrail per il run autonomo

**Fuori dal run notturno**, da fare con l'utente presente:

- `git worktree remove`, `git branch -D`, prune dei branch;
- merge su `main` e qualunque push;
- `policy/prop_firm/fixtures.py` (vietato da PROJECT.md senza ADR);
- **qualsiasi cancellazione di documenti**.

**Dentro il run notturno** — solo lavoro reversibile: spostamenti dietro tag,
`.gitignore`, `git rm` su branch dedicato, consolidamento documentale, misurazioni.

---

## 6. Rischi aperti

| # | Rischio | Impatto | Mitigazione |
|---|---|---|---|
| R1 | il re-run di 0a rifalla: Lane B non qualificato | il traguardo G7-CFD perde il suo oggetto | è il motivo per cui 0a è in Fase 0: si scopre prima di costruirci sopra |
| R2 | FTMO/The5ers non offrono CFD sui 15 small/mid cap USA | G7-CFD cade | 0b è bloccante; fallback dichiarato in §1.3 |
| R3 | lo swap trimestrale erode il 19,7%/anno oltre la soglia | l'eval diventa non conveniente | quantificato in 0b prima di impegnare lavoro |
| R4 | il confine al 76% non riduce la superficie di manutenzione | la distillazione non produce il guadagno atteso | la riduzione è spostata su Fase 1 e Fase 3, dove è misurabile |
| R5 | 63 commit non mergiati su `main` restano tali | `main` continua a essere inutile come riferimento | decisione di merge esplicita dopo Fase 2, con l'utente presente |
| R6 | il run autonomo tocca qualcosa che non doveva | danno non reversibile | §5: nessuna cancellazione, nessun push, nessun merge |

---

## 7. Fuori scope

- Cambiare la strategia Lane B o i suoi parametri (è preregistrata).
- Costruire nuovi moduli di ricerca: ROADMAP §14 vieta di costruire attorno a zero
  edge, e la Fase 3 lo rende machine-checked.
- Il portafoglio SR-max a 16 leg: resta la baseline, non è toccato da questa spec.
- Qualunque cosa che richieda dati finanziari a pagamento ($0/mese è un vincolo
  duro).
