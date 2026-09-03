# ADR-023 — Dual-Channel Strategy Promotion Policy (Personal High-Vol vs Funded Sigma-Scaled)

**Data:** 2026-09-03
**Status:** ACCEPTED
**Deciders:** Alin (operator)
**Supersedes:** —
**Related:** ADR-013 (versioned prop-firm rule catalog), ADR-018 (prop-firm structural EV),
ADR-019 (Lane B personal portfolio), ADR-021 (canonical performance metrics),
ADR-022 (MT5 Linux bridge); BACKLOG BL-709 (this ADR + impl), BL-707 (haircut Sharpe),
BL-722 (PropFirmRiskGovernor), BL-728 (paper simulator); memoria
`propfirm-multifarm-decisions`; `policy/prop_firm/dual_channel.py` (impl).

## Context

Oracle sta per costruire strategie che possono essere eseguite su due
contesti operativi strutturalmente diversi:

* **Capitale proprio (Lane B / brokerage IBKR)** — l'operatore accetta
  volatilità più alta, drawdown più profondi, in cambio di un ritorno
  assoluto maggiore. Il sizing segue vol-target 25-40% (Lane B stack,
  ADR-019). Il gate di promozione è *qualità dell'edge*: la domanda è
  "questo edge è reale e merita di essere sized nel mio book personale?"
* **Capitale funded (prop-firm account)** — il conto vive sotto
  l'envelope hard-risk di una prop-firm (governor BL-722 + catalogo
  ADR-013). Ogni ordine che rischia breach fallisce closed. Il gate di
  promozione è *edge + sopravvivenza*: la domanda è "questo edge è reale
  E sopravviverà all'envelope hard-risk della firm su 100+ sessioni
  paper canoniche?"

Sono due domande diverse e richiedono metriche diverse. Una strategia può
passare una senza passare l'altra:

* una strategia con `haircut_sharpe=0.7` ma che trippa il daily-loss
  limit su 70% delle sessioni paper è **Channel A-pass / Channel B-fail**
  (l'edge c'è, ma il book prop-firm non lo regge);
* una strategia che sopravvive 120 sessioni paper senza breach ma con
  `walk_forward_alpha=0` è **Channel B-pass / Channel A-fail**
  (sopravvive al rischio, ma l'edge non si vede OOS — il sizing
  brokerage su questa sarebbe un HARKing trap).

Il codice pre-BL-709 non distingueva i due canali: ogni strategia
"qualificata" veniva trattata come deployment-ready su entrambi. Questo
è il difetto architetturale che BL-709 chiude: ogni canale ha i propri
criteri pre-registrati e il verdetto è per-canale.

## Decision drivers

- **Edge quality vs survivability**: il capitale proprio accetta edge
  imperfetto purché statisticamente distinguibile dal rumore (haircut
  Sharpe); il capitale funded richiede che l'edge sia anche *operable*
  sotto envelope hard-risk.
- **HARKing trap**: promuovere a Channel B un edge che non sopravvive
  al daily-loss envelope significa pagare eval fees inutili ($155-500 per
  challenge The5ers + tempo + opportunity cost). Gate fail-closed su
  consistenza, pass-rate, MC.
- **Pre-registrazione**: ogni soglia in questo ADR è *pre-registered*
  (Bailey-López de Prado 2014 + 2018, deep-research synthesis
  2026-08-15). Modificare una soglia richiede un emendamento a questo
  ADR e una riscrittura cosciente dei golden vectors nel test file.
- **Fail-closed semantics**: input non-finite o out-of-domain
  (NaN/inf/negative DD/consistency > 1.0) **falliscono chiuso** —
  lesson dell'M31 evidence loss (ADR-014). Mai silent pass.
- **Independenza dei canali**: passare Channel A **NON** implica
  promozione a Channel B. La promozione è per-canale; ogni canale
  richiede le metriche che contano per la *sua* capital source.
- **ADR-021 canonical metrics**: tutti i calcoli Sharpe/Calmar/MaxDD
  delegano a `analytics/metrics/canonical.py`. Mai local re-derivations.
- **Coerenza multi-firm (decisione 2026-08-22)**: le soglie Channel B
  sono il minimo comune multi-firm (TopstepX 40%, APEX 30%, TPT 50%
  → noi promuoviamo al più stretto + margine, 35%); le firm che
  applicano soglie più morbide restano eligible (Channel B non blocca
  TPT/TopstepX), ma i golden vectors bloccano la soglia a 35%.

## Options considered

### Option A — Una sola soglia unificata (RIFIUTATA)

Un unico set di criteria (es. "edge deve passare DSR ≥ 0.95 AND
consistency ≤ 30%") applicato a tutte le strategie. Le strategie che
superano vengono deployate ovunque.

Pro: semplice, un solo gate.

Contro:

- Confonde "edge quality" (brokerage) con "survivability" (funded);
- Una strategia brokerage-pass può fallire su consistency (40% del
  profitto in un giorno — perfettamente OK per un brokerage che fa
  sizing 2-3% per idea, micidiale per una prop-firm);
- Una strategia funded-pass (zero breach) può avere edge negativo OOS —
  promuoverla a brokerage è HARKing.

Rischio: alto. Riproduce esattamente il bug M31 (decisioni di gate
  sbagliate per mismatch semantico).

### Option B — Due canali indipendenti con soglia dedicata (DECISIONE)

Ogni canale ha i suoi criteria pre-registrati, il verdetto è
per-canale, e la promozione avviene *al canale* che passa (un
sottoscrittore di Channel A non è automaticamente iscritto a Channel B
e viceversa).

Pro:

  - Semantica corretta: ogni canale gating sulle metriche che contano
    per la *sua* capital source;
  - Fail-closed esplicito: NaN/inf ⇒ fail con criterio nominato
    (audit trail);
  - Modificare una soglia = emendamento ADR (no drift silenzioso);
  - Coerente con multi-firm (TopstepX/TPT/APEX più morbidi di noi →
    noi siamo il sottoinsieme stretto);
  - Indipendenza: l'edge può esistere senza la survivability, e
    viceversa, e questo è *informazione*, non fallimento.

Contro:

- Due set di criteria da mantenere (raddoppia la superficie di test);
- Rischio di sotto-promozione (strategia che passa A ma non B resta
  non deployata su B finché non riqualifica);
- Golden vectors vanno aggiornati con coscienza a ogni soglia che
  cambia (no shortcut).

Rischio: basso. Reversibilità alta (le soglie sono costanti module-level).

### Option C — Canale sequenziale (A implica B se passa) (RIFIUTATA)

Channel A passa + survives 100 sessioni paper → promosso a Channel B
automaticamente.

Pro: meno gate, meno test.

Contro:

- Il punto è proprio che passare A non dice nulla sulla survivability
  sotto envelope hard-risk. Una strategia può essere statisticamente
  significativa ma operativamente disastrosa (es. mean-reversion che
  passa IC + haircut ma che entra in posizione su spike giornaliero);
- Sequenzialità accoppiata rende impossibile rifiutare Channel B su
  strategia brokerage-OK (caso d'uso reale per Lane B / personal-only
  strategies).

Rischio: alto. Rifiutata.

## Decision

**Adottiamo Option B — Due canali indipendenti con soglia dedicata.**

Implementazione: `policy/prop_firm/dual_channel.py`. API pubblica:

```python
from policy.prop_firm import (
    Channel,
    PersonalPromotionMetrics,
    FundedPromotionMetrics,
    PromotionDecision,
    check_personal_channel,
    check_funded_channel,
    check_dual_channel,
    eligible_profiles,
    governor_clean,
    PERSONAL_HAIRCUT_SHARPE_MIN,
    PERSONAL_DSR_MIN,
    PERSONAL_MAX_DRAWDOWN_MAX,
    PERSONAL_WALK_FORWARD_ALPHA_MIN,
    FUNDED_CONSISTENCY_PCT_MAX,
    FUNDED_MIN_PAPER_SESSIONS,
    FUNDED_SIMULATED_PASS_RATE_MIN,
    FUNDED_MONTE_CARLO_PASS_RATE_MIN,
)
```

### Soglie Channel A (Personal) — pre-registrate, frozen 2026-09-03

| Criterio | Soglia | Rationale | Source |
|---|---|---|---|
| `haircut_sharpe` | ≥ 0.50 | Edge statisticamente distinguibile dal best-of-N null dopo haircut multi-testing | BL-707, BL-KB-99 (Bailey-López de Prado 2018) |
| `dsr` | ≥ 0.95 | Probabilità post-haircut ≥ 95% che il vero SR superi il benchmark | BL-KB-99 (Bailey-López de Prado 2014) |
| `max_drawdown` | < 0.15 (15%) | Compatibile con Lane B sizing 2-3% per idea; sopra 15% il tail loss erode il sizing | ADR-019 |
| `walk_forward_alpha` | > 0.0 | OOS alpha strettamente positivo (coin-flip = 0 ⇒ fail, lesson M31) | ADR-014 |

### Soglie Channel B (Funded) — pre-registrate, frozen 2026-09-03

| Criterio | Soglia | Rationale | Source |
|---|---|---|---|
| `hard_risk_compliant` | True | BL-722 governor non ha raisato breach sulla validation envelope | BL-722 |
| `consistency_pct` | ≤ 0.35 | Mieterharvester best-day rule; strictest tra TopstepX 40% / APEX 30% / TPT 50% + margine | decisione D multi-firm 2026-08-22 |
| `daily_pause_terminate_supported` | True | DailyLossAction ∈ {PAUSE, TERMINATE}; senza enforcement la strategia può re-entrare dopo daily loss | BL-722 |
| `n_paper_sessions` | ≥ 100 | CLT richiede ≥ 100 sample per pass-rate MC stabile | standard statistico |
| `simulated_pass_rate` | ≥ 0.60 | ≥ 60% pass-rate su sessioni paper BL-728 (sopra coin-flip, margine slippage) | BL-728 |
| `monte_carlo_pass_rate` | ≥ 0.60 | Same gate, MC-replay (protezione da fluke order-dependent) | BL-728 |

### Failure semantics

- Tutti i gate sono **AND** (un fail = verdetto FAIL con
  `failed_criteria` populated).
- Tutti gli input **fail-closed** su NaN, inf, out-of-domain (es.
  consistency > 1.0, DD < 0). Mai silent pass.
- I `failed_criteria` sono una tuple di stringhe con il nome del campo
  e il valore incriminato — audit trail completo.
- Decision è `@dataclass(frozen=True)` + `__bool__` → `if decision:`
  è la sintassi idiomatica; mutation impossible (immutabile).

### Promotion semantics

- **Per-channel**: pass Channel A ⇒ brokerage sizing; pass Channel B
  ⇒ firm-funded sizing. No inheritance.
- **Structural eligibility** (`eligible_profiles`): un profilo firm
  deve avere `SupportMode ∈ {AUTO_SUPPORTED, ASSISTED_ONLY}` (no
  RESEARCH_ONLY / UNSUPPORTED) e `DailyLossAction ∈ {PAUSE, TERMINATE}`
  per essere strutturalmente promotabile. RESEARCH_ONLY = backtest
  only, no live deploy.
- **Governor clean** (`governor_clean`): il governor BL-722 deve
  restituire una breach list vuota sulla validation window.

## Consequences

### Positive

- **Semantica corretta**: ogni canale gating sulle metriche che
  contano per la sua capital source;
- **No HARKing**: pass Channel B richiede `walk_forward_alpha > 0` (e
  Edge quality globale dal canale A); pass Channel A richiede haircut
  Sharpe + DSR (no inflated SR che passa come edge);
- **Audit trail completo**: ogni fail nomina il campo e il valore
  (regolatori, operatori, debugging);
- **Coerente con ADR-014** (fail-closed su M31 evidence loss): NaN/inf
  falliscono esplicitamente, mai silent pass;
- **Coerente con ADR-021**: nessuna ricalcolo locale di Sharpe/Calmar;
  tutto delega al modulo canonico;
- **Coerente con decisione multi-firm 2026-08-22**: 35% consistency è
  strictest + margine; firme più permissive (TPT 50%, TopstepX 40%)
  restano eligible;
- **Reversibilità**: le soglie sono costanti module-level — modificarle
  richiede un emendamento ADR esplicito.

### Negative

- **Due set di criteria da mantenere**: la superficie di test è
  raddoppiata vs single-channel (55 test ora, 4 sotto-pacchetti);
- **Sotto-promozione strutturale**: una strategia Channel A-pass non
  viene auto-promossa a Channel B; richiede un secondo run di
  validazione (sotto envelope hard-risk). Questo è intenzionale —
  è il punto del doppio canale.
- **Costante mentale**: operatori devono ricordare che passare un
  canale NON significa passare l'altro (mitigato dal `notes` campo
  della decision che esplicita il canale).

### Failure modes

| Failure | Detection | Mitigation |
|---|---|---|
| NaN nel DSR (calcolo MC fallito) | gate fail con `dsr (non-finite)` | fail-closed esplicito, mai silent pass |
| `max_drawdown` = 0.0 (no trades) | gate fail con `max_drawdown (out-of-domain: 0.0)` | fail-closed (Lane B sizing assumes DD > 0) |
| Strategy firm-modified post-validation | guardrail: pre-register le metriche, validare post-deploy | pre-registration BL-708 preregistry |
| Mock governor returns clean list anche se breach in realtà c'è | test integration che legge `Breach.breach_type` direttamente | BL-722 surfaces breach via `BreachType` enum; test in `tests/policy/` |
| Soglie bumpate silenziosamente in production | ruff + golden vectors | bumpare soglia = rompere i test; ADR amendment obbligatorio |

## Enforcement

- **Codice**: `policy/prop_firm/dual_channel.py` (impl, ~370 righe);
- **Test**: `tests/unit/test_dual_channel_policy.py` (55 test, 4
  sotto-pacchetti: `TestPersonalChannelPasses`, `TestPersonalChannelFails`,
  `TestPersonalChannelFailClosed`, `TestFundedChannelPasses`,
  `TestFundedChannelFails`, `TestFundedChannelFailClosed`,
  `TestChannelIndependence`, `TestEligibleProfiles`, `TestGovernorClean`,
  `TestDecisionShape`, `TestCatalogSanity`);
- **Golden vectors**: ogni soglia è fissata da un test parametrico che
  pinna il verdetto al valore di confine (`>=`/`>`); ogni bump di
  soglia richiede aggiornamento ADR + riscrittura cosciente dei
  golden vectors;
- **Architecture boundaries**: il modulo è in `policy/` (importabile
  da `analytics/` per la validation flow); l'enforcement è coperto da
  `tests/unit/test_architecture_boundaries.py`;
- **Imports**: tutti gli utilizzatori importano da `policy.prop_firm`
  (re-export pubblico), non da `dual_channel` direttamente;
- **Decisioni che richiedono emendamento a questo ADR**:
  1. qualsiasi modifica a una delle 10 soglie pre-registrate;
  2. aggiunta di un nuovo criterio a uno dei due canali;
  3. modifica della semantica fail-closed (es. accettare NaN);
  4. modifica della independence semantics (es. cross-contamination);
  5. aggiunta di un nuovo canale (Channel C, D, ...).

## Follow-up

- **BL-708** (Sprint 1 qualification): promuove i primi 46+ fattori
  Stage 1 al canale appropriato. Output: report sprint-1 con verdict
  per ogni fattore × canale.
- **BL-728** (paper simulator): la soglia `simulated_pass_rate ≥ 0.60`
  richiede un canonical paper runner con 100+ sessioni. Già scaffoldato
  (memory `factory-stage1-2026-08-22`). Implementazione completa in
  corso; questo ADR rimane valido indipendentemente.
- **BL-722** (PropFirmRiskGovernor): `governor_clean()` consuma la
  breach list del governor; integration in `apps/run_paper.py` in BL-732.
- **Future** (post-paper-runner): aggiungere Channel C "research-only
  backtest" come pre-filter per Channel A/B (sottoinsieme che non passa
  nessuno dei due ma che vale la pena studiare). Richiederà ADR
  amendment perché aggiunge un canale.

## Implementation pointers

- `policy/prop_firm/dual_channel.py` — impl completa (Channel enum,
  PersonalPromotionMetrics, FundedPromotionMetrics, PromotionDecision,
  check_personal_channel, check_funded_channel, check_dual_channel,
  eligible_profiles, governor_clean, 10 soglie module-level);
- `policy/prop_firm/__init__.py` — re-esporta tutti i simboli pubblici;
- `tests/unit/test_dual_channel_policy.py` — 55 test, golden vectors
  congelati;
- `docs/ADR/ADR-023-dual-channel-promotion-policy.md` — questo file.

## References

- Bailey, D. & López de Prado, M. (2014). "The Deflated Sharpe Ratio:
  Correcting for Selection Bias, Backtest Overfitting, and
  Non-Normality." *Journal of Portfolio Management* 40(5):94-107.
  → BL-KB-99, hair-cut DSR.
- Bailey, D. & López de Prado, M. (2018). "The Right Way to Select
  Investments." *Journal of Portfolio Management* 45(1):133-138.
  → BL-707, haircut_sharpe_ratio.
- ADR-013 — versioned prop-firm rule catalog.
- ADR-014 — M31 evidence loss (fail-closed discipline).
- ADR-018 — prop-firm structural EV (gate ≥250 sessioni paper).
- ADR-019 — Lane B priority (brokerage personal portfolio).
- ADR-021 — canonical performance metrics (semantic frozen).
- ADR-022 — MT5 Linux bridge architecture.
- BACKLOG.md BL-709 (this ADR + impl), BL-707 (haircut Sharpe),
  BL-722 (governor), BL-728 (paper simulator).
- Memoria `propfirm-multifarm-decisions` (decisioni D1-D5 multi-firm).
- Memoria `factory-stage1-2026-08-22` (46 ipotesi Stage 1, IC screen).
