# ADR-018: Prop-firm structurally negative EV — funded capital deployment gate

**Data:** 2026-08-15
**Status:** ACCEPTED (post deep-research synthesis 2026-08-15)
**Related:** ADR-013 (versioned prop-firm rule catalog), ADR-015 (Topstep automation policy), ADR-010 (deterministic execution safety boundary)

---

## Context

Il deep-research del 2026-08-15 (`docs/reports/2026-08-15-deep-research-synthesis.md`) ha verificato con fonti primarie che il modello di business "prop-firm funded account" è **strutturalmente negativo per il trader**:

1. **MyForexFunds (Traders Global Group Inc.)** — caso FTC/CFTC 222-7010, Sept 2023:
   - $310M challenge-registration fees raccolti dal 2022-2023
   - $137M payouts pagati ai trader "vincitori"
   - **$172M net income per la firm** > payouts totali ($137M)
   - Il modello NON è "trova talenti e falli crescere" — è "vendi sfide al 97% che fallirà"

2. **Base rate retail catastrofico** (Chague, De-Losso, Giovannetti 2019, n=1.551 BMF Bovespa futures 2012-2017):
   - 97% dei day trader persistenti (>300 giorni) perde soldi netto commissioni
   - Solo 17 (1.1%) guadagnavano >minimum wage BR (~$16/day)
   - Solo 8 (0.5%) guadagnavano >bank teller starting salary (~$54/day = ~$13K/anno)

3. **Retail paradox** (Barber, Odean, Lin 2023, JFQA 59(6):2547-2581):
   - I retail prevedono positivamente i rendimenti a breve termine
   - MA come gruppo restano unprofitable
   - L'edge documentato NON è transferable al conto bancario senza vantaggio strutturale (latenza, costo, informazione privata)

4. **Modello economico Oracle** (BL-094 / `docs/reports/s0-2-economic-model.md`):
   - €3K/mese netti su singolo account 50K richiede α ≥ 118,9%/anno
   - Su 5-7 account 150-200K richiede α ≥ 39,6-59,5%/anno
   - Soffitto misurato: +2-6% lordo annuo → ~0 netto costi
   - **Gap 5-16× dal target**

## Decision

Definiamo un **gate di deployment capitale funded** che richiede evidenza statistica robusta PRIMA di mettere capitale reale a rischio in account prop-firm:

### Gate di deployment (prerequisito per capitale reale funded)

1. **≥250 sessioni paper indipendenti** con pass rate ≥90% (non 30 sessioni come nel M32a WP2). Le 30 sessioni sono insufficienti per distinguere edge da varianza.

2. **DSR ≥ 0.95** (Bailey & López de Prado 2014) sulla Sharpe observed, con `n_trials` = numero di strategie testate nella discovery phase. Implementato in `analytics/qualification/dsr.py` (ADR-017).

3. **PBO < 0.5** (Bailey et al. 2017) via CSCV. Implementato in `analytics/qualification/dsr.py` (ADR-017).

4. **PSR ≥ 0.95** contro benchmark_sharpe = Sharpe buy&hold (test anti-beta, ADR-016 §4 clausola sopravvissuta).

5. **α netto ≥ 15%/anno** (requisito pre-registrato BL-094 §3).

6. **DD ≤ 4%** worst-case (ADR-016 §4 clausola sopravvissuta).

7. **p(pass) ≥ 0.60** Monte Carlo sotto regole prop-firm target (requisito pre-registrato BL-094 §3).

8. **Consistency rule respected**: se la firm ha consistency rule (es. Lucid 40% funded), le vincite devono essere distribuite su ≥4 settimane, non concentrate in 1-2 trade fortunati.

### Modello "5-20 account concorrenti" — RIFIUTATO

Il deep-research + consulenza hanno validato che il modello "5-20 account concorrenti" per superare il base rate è **sbagliato**:

- **Correlazione cross-account**: stessa strategia, stesso giorno, stesso broker → blowup simultaneo su 2σ event
- **Funded capital allocation**: **massimo 1-3 account focused**, espansione solo post-250 sessioni paper pass ≥90% con DSR/PBO/PSR verdi

### Lane B turnaround — NON prop-firm strategy

Il deep-research ha confermato che la Lane B (turnaround su paniere azionario, formalizzazione dell'intuizione INTC/Xiaomi dell'operatore) **NON è compatibile con prop-firm**:

- The5ers offre MT5/CFD su FX/metals/indices — non single stocks
- Lucid offre futures CME — non single stocks
- MyFundedFutures offre futures — non single stocks

**Implicazione**: la Lane B è per il **portafoglio personale dell'operatore** (brokerage account IBKR/Interactive Brokers), NON per conto funded. La intuizione INTC/Xiaomi NON è monetizzabile via prop-firm.

## Rationale

1. **MyForexFunds è case study paradigmatico**: $172M net income firm > $137M payouts totali. Il "modello prop-firm" NON è payout business, è fee-extraction business. Le prop-firm sopravvivono perché la maggioranza dei challenger fallisce.

2. **0.5% guadagna >bank teller**: il base rate per un retail day trader è 0.5% (Chague 2019). Questo è il numero reale contro cui Alin sta competendo, non il marketing "passa la challenge e diventa funded".

3. **Consulenza esterna (2026-08-15)** ha validato: "il modello '5-20 account concorrenti' è sbagliato per operatore singolo — correlazione cross-account (stessa strategia/stesso giorno/stesso broker = blowup simultaneo 2σ event); raccomandazione 1-3 account focused, espansione solo post-250 sessioni paper pass≥90%".

4. **Retail paradox** (Barber-Odean-Lin 2023): l'edge documentato non è transferable al conto bancario senza vantaggio strutturale. Oracle ha stack istituzionale (NautilusTrader + vectorbt + PostgreSQL + IBKR + cvxpy + purgedcv) che è un vantaggio strutturale, MA non basta da solo: serve edge reale validato con DSR/PBO/CPCV (ADR-017).

5. **Coerenza con ADR-013**: ADR-013 ha reso i profili prop-firm versionati e immutabili; questo ADR estende il discipline al deployment gate (quando è lecito mettere capitale reale).

## Consequences

### Positive
- Definizione quantitativa di "quando è lecito mettere capitale reale a rischio".
- Allineamento con il modello economico BL-094 (requisiti pre-registrati).
- Diffida dall'illusione "passa 1 challenge → diventa funded → €3K/mese".
- Obbliga a validare onestamente con DSR/PBO (ADR-017) prima di deployment.

### Negative
- **BL-024** (G6 re-run qualificante con 30 sessioni) è **insufficiente** sotto questo ADR. Va esteso a 250 sessioni o esplicitamente marcato come "smoke test, non deployment gate".
- **Bar alto**: 250 sessioni paper pass ≥90% con DSR ≥0.95 è un bar molto alto. Realisticamente raggiungibile solo dopo Lane A PAC multi-asset (BL-502/503) o Lane B turnaround (BL-504/505/506) convalidati.
- **Costo opportunità riconosciuto**: ML engineer/quant developer guadagna €60-120K/anno. Oracle working 2-3 anni prima di primo € netto consistente = €150-450K salary foregone. Mitigazione: reddito alternativo parallelo (RF2 burnout).

## Enforcement

- **Codice**: `analytics/qualification/dsr.py` (BL-500/ADR-017) fornisce DSR/PSR/PBO. `analytics/qualification/evaluator.py` da estendere per richiedere `min_dsr`, `max_pbo`, `min_psr` in `QualificationThresholds`.
- **Policy**: `policy/prop_firm/governor.py` da estendere con `FundedDeploymentGate` che richiede evidenza DSR/PBO/PSR + 250 sessioni paper + p(pass) MC.
- **Documentation**: questo ADR + `docs/POLICY_ENGINE.md` + `docs/PROP_FIRM_READINESS_ROADMAP.md` referenziati ovunque si discuta di "funded capital deployment".
- **BACKLOG**: BL-509 (questo ADR). Le soglie quantitative (250 sessioni, 90%, DSR ≥0.95, PBO <0.5, PSR ≥0.95) sono registrate come requisito pre-registrato.

## Alternatives considered

1. **Mantenere bar a 30 sessioni**: rifiutato. Insufficiente per distinguere edge da varianza. M32a WP2 ha prodotto 30/30 pass con 0 trade → verdetto non qualificante.

2. **Affidarsi al fee model prop-firm come "filtro naturale"**: rifiutato. Il fee model è strutturalmente negativo per il trader (MyForexFunds $172M > $137M payouts). NON è un filtro, è un drag.

3. **Perseguire 5-20 account concorrenti**: rifiutato. Correlazione cross-account = blowup simultaneo. Consulenza esterna + deep-research validano "1-3 account focused".

4. **Saltare il gate per "operatore informato"**: rifiutato. Violerebbe ADR-010 (deterministic execution safety boundary) e ADR-014 lesson (invalidare run non riproducibili).

## Open questions

1. **250 sessioni paper — come generarle?**: 250 finestre indipendenti su lake ES_1d richiedono dati storici lunghi (252 × 250 / 252 ≈ 250 anni se finestre sono 1 anno). Soluzione: finestre più corte (30-100 barre) su dati intraday (BL-097 IBKR sblocco) O multi-asset (Lane A PAC su 8-12 futures × 20-30 finestre ciascuno = 160-360 sessioni).

2. **Consistency rule enforcement**: come verificare che le vincite sono distribuite su ≥4 settimane? Necessario hook in `policy/prop_firm/governor.py::record_trade()` per tracciare la distribuzione temporale dei P&L.

3. **Meta-kill rule**: se dopo 250 sessioni paper il sistema NON passa il gate, qual è la policy? (a) abbandono prop-firm path, (b) cambio di lane, (c) tuning? Default: (b) cambio di lane (Lane A → Lane B → Lane C → option selling VRP → declare NO edge for prop-firm model).

## References

- FTC case 222-7010, MyForexFunds / Traders Global Group Inc. (Sept 2023). https://www.ftc.gov/legal-library/browse/cases-proceedings/222-7010-myforexfunds-mfx-premium-inc
- Chague, F., De-Losso, R., Giovannetti, B. (2019). "Day Trading for a Living?" *Review of Asset Pricing Studies*.
- Barber, B., Odean, T., Lin, S. (2023). "Resolving a Paradox: Retail Trades Positively Predict Returns but are Not Profitable." *JFQA* 59(6):2547-2581.
- BL-094 economic model: `docs/reports/s0-2-economic-model.md`.
- Deep-research synthesis 2026-08-15: `docs/reports/2026-08-15-deep-research-synthesis.md`.
- ADR-013 (versioned prop-firm rule catalog).
- ADR-015 (Topstep automation policy).
- ADR-017 (DSR+PBO+CPCV mandatory).

## Implementation pointers

- `analytics/qualification/dsr.py` (DSR/PBO/CPCV/PurgedKFold/PSR, BL-500 DONE).
- `analytics/qualification/evaluator.py` (to be extended; BL-511 futuro).
- `policy/prop_firm/governor.py` (to be extended with FundedDeploymentGate; BL-512 futuro).
- BACKLOG BL-509 (questo ADR): DONE con questo file.
