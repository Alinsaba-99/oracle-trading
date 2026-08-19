# ADR-017: Backtest overfitting validation upgrade — DSR + PBO + CPCV mandatory

**Data:** 2026-08-15
**Status:** ACCEPTED (post deep-research synthesis 2026-08-15)
**Supersedes:** partial — ADR-016 `luck_p_value` clause (deprecato come gate qualifier; retained come diagnostic)
**Related:** ADR-016 (anti-beta benchmark), ADR-011 (discovery/qualification), ADR-014 (M31 evidence loss)

---

## Context

ADR-016 ha introdotto `luck_p_value` come gate qualifier per il G5 (research truth). Il deep-research del 2026-08-15 (`docs/reports/2026-08-15-deep-research-synthesis.md`) ha verificato che `luck_p_value` **non è sufficiente** per validare onestamente l'edge quando il sistema testa centinaia di combinazioni (8 candidati × 6 regimi × N finestre × varianti):

1. **Multi-test bias non gestito**: `luck_p_value` è un per-slice bootstrap che non corregge per il numero di strategie testate nella discovery phase. Qualsiasi claim "α = 6%" è candidato artefatto senza questa correzione.

2. **Esiste un'implementazione open-source MIT-licensed** che riempie il gap metodologico:
   - `purgedcv` (eslazarev/purged-cross-validation, v0.1.3 PyPI 1-ago-2026): scikit-learn-compatible, implementa `CombinatorialPurgedCV` (CPCV), `PurgedKFold` (purge+embargo), `deflated_sharpe_ratio` (DSR), `probability_of_backtest_overfitting` (PBO), `probabilistic_sharpe_ratio` (PSR).
   - `mnemox-ai/deflated-sharpe` (Apache-2.0, verified matematicamente contro Bailey & López de Prado 2014 JPM 40(5):94-107).

3. **`mlfinlab` non è più open-source OSI**: il repo pubblico `hudson-and-thames/mlfinlab` ha licenza "all rights reserved", esiste solo come bug tracker. NON è incorporabile in Oracle senza licenza commerciale Business/Enterprise.

## Decision

La qualifica M31 (G5) e tutte le discovery/qualification successive adottano i seguenti test di overfitting obbligatori, sostituendo `luck_p_value` come gate qualifier:

### 1. Deflated Sharpe Ratio (DSR) — Bailey & López de Prado 2014
- **Implementazione**: `analytics/qualification/dsr.py::deflated_sharpe_ratio()` (wrapper di `purgedcv.deflated_sharpe_ratio`).
- **Funzione**: corregge l'observed Sharpe per il numero di trial `n_trials` (varianti nella discovery sweep). L'expected max Sharpe da puro caso cresce come `O(sqrt(ln(M)))` su M trial; il DSR sottrae questo dall'observed e normalizza per SE.
- **Soglia gate**: `DSR ≥ 0.95` (probabilità che lo Sharpe vero sia > 0 dopo multi-test correction).

### 2. Probability of Backtest Overfitting (PBO) — Bailey, Borwein, López de Prado & Zhu 2017
- **Implementazione**: `analytics/qualification/dsr.py::probability_of_backtest_overfitting()` via CSCV (Combinatorially Symmetric Cross-Validation).
- **Funzione**: stima la probabilità che la strategia in-sample ottimale sia mediocre out-of-sample. Prende una matrice (n_trials, n_periods) di returns.
- **Soglia gate**: `PBO < 0.5` (minimo bar di robustezza; < 0.1 è eccellente).

### 3. Combinatorial Purged CV (CPCV) — López de Prado AFML ch.12
- **Implementazione**: `analytics/qualification/dsr.py::combinatorial_purged_cv()` (wrapper di `purgedcv.CombinatorialPurgedCV`).
- **Funzione**: sostituisce walk-forward standard con fold combinatoriali + purge + embargo per prevenire label-overlap leakage. Ricostruisce C(n_groups, n_test_groups) path.
- **Uso gate**: obbligatorio per qualunque backtest che faccia model selection su parameters. Sostituisce il walk-forward standard quando si vuole stima robusta di OOS performance.

### 4. Purged K-Fold — López de Prado AFML ch.7
- **Implementazione**: `analytics/qualification/dsr.py::purged_k_fold()` (wrapper di `purgedcv.PurgedKFold`).
- **Funzione**: come KFold standard ma con purge e embargo attorno ai boundary train/test per prevenire information leakage.
- **Uso gate**: obbligatorio per cross-validation su time-series. NON usare sklearn.model_selection.KFold su dati finanziari.

### 5. Probabilistic Sharpe Ratio (PSR) — Bailey & López de Prado 2012
- **Implementazione**: `analytics/qualification/dsr.py::probabilistic_sharpe_ratio()`.
- **Funzione**: dà la probabilità che lo Sharpe vero superi un benchmark (default 0), account per skew, kurtosis e lunghezza sample.
- **Soglia gate**: `PSR ≥ 0.95` contro benchmark_sharpe=0 (o contro buy&hold Sharpe per test anti-beta).

## Deprecation

- `bootstrap_luck_p_value` (`analytics/qualification/statistics.py:60`) è **DEPRECATED come gate qualifier**. Ritenuto come diagnostic backward-compatible per report M31 esistenti. NON usare in nuovi gate.
- ADR-016 §4 "Soglie" — la clausola "`luck_p_value` entra nel gate" è **superceded** da questo ADR. Le soglie anti-overfit sono ora DSR + PBO + PSR (sopra).

## Rationale

1. **Multi-test bias è il rischio maggiore**: Oracle testa centinaia di combinazioni nella discovery phase. Senza DSR/PBO, ogni "Sharpe positivo" è sospetto artefatto. Il deep-research ha validato che `luck_p_value` per-slice non è sufficiente.

2. **`purgedcv` è open-source MIT**: adozione diretta, costo 2-4 giorni. Nessun lock-in commerciale.

3. **`mnemox-ai/deflated-sharpe` è Apache-2.0 fallback**: verificato matematicamente contro il paper originale.

4. **`mlfinlab` NON è più open-source**: il repo pubblico ha licenza "all rights reserved" (LICENSE.txt, GitHub API `license.key: "other"`, `spdx_id: "NOASSERTION"`). NON incorporabile senza licenza Business/Enterprise a pagamento.

5. **Coerenza con ADR-014 (M31 evidence loss)**: il lesson appreso (invalidare run non riproducibili) si estende al "invalidare run con gate statistico non sufficiente". DSR+PBO+CPCV è il nuovo standard di evidenza.

## Consequences

### Positive
- Gate G5 statisticamente onesto: ogni claim di edge passa multi-test correction.
- Reusable per tutti i backtest futuri (Lane A/B/C, option selling VRP, ecc.).
- Implementazione open-source, niente lock-in commerciale.

### Negative
- BL-023 Fase 5/5b/5c va **ri-valutata** con DSR+PBO se si vuole confermare il verdetto REJECTED. Verdetto atteso: REJECTED più severo (DSR sarà ≤ luck_p_value per costruzione quando n_trials è alto).
- Costo implementazione: 2-4 giorni per integrazione (BL-500) + 1 giorno per ADR-017 (BL-501).
- Necessario trackare `n_trials` esplicitamente nella discovery phase (campo `ReplayVariant.factorial()` conta 8 varianti default, ma una discovery sweep su 50 parametri conta 50 trial).

## Enforcement

- **Codice**: `analytics/qualification/dsr.py` wrapper + `tests/unit/test_dsr.py` (15 test verdi).
- **Gate**: `analytics/qualification/evaluator.py` deve richiamare `deflated_sharpe_ratio()` e `probability_of_backtest_overfitting()` nel summary; `QualificationThresholds` deve avere `min_dsr: float = 0.95`, `max_pbo: float = 0.5`, `min_psr: float = 0.95`.
- **Documentation**: BACKLOG.md BL-500/BL-501 riferimento questo ADR. ADR-016 annotato "partial supersede by ADR-017 per `luck_p_value` clause".
- **Test**: `tests/unit/test_dsr.py` (15 test) verifica ogni funzione con input sintetici e sanity (più trial → DSR più basso, ecc.).

## Alternatives considered

1. **Mantenere `luck_p_value` come gate**: rifiutato perché non corregge per multi-test bias. Il deep-research ha identificato come RF critico "qualsiasi α = 6% è candidato artefatto senza multi-test correction".

2. **Adottare `mlfinlab`**: rifiutato perché NON più OSI (licenza "all rights reserved"). NON incorporabile senza licenza commerciale. Il deep-research ha verificato il LICENSE.txt direttamente.

3. **Implementare DSR/PBO/CPCV from scratch**: rifiutato perché `purgedcv` MIT-licensed è scikit-learn-compatible e già verificato. Reinventare la ruota consumerebbe 1-2 settimane senza valore aggiunto.

4. **Adottare pysystemtrade**: rifiutato per il gate (valutato per Lane A backbone BL-502). pysystemtrade è reference per CTA, NON per DSR/PBO (non li implementa nativamente; Carver non segue López de Prado).

## Open questions

1. **`n_trials` counting**: come contare le varianti testate nella discovery? È 8 (varianti factoriali M31)? È 50 (parameter sweep)? È 8×6×3 = 144 (varianti × regimi × finestre)? Default: contare il numero di strategie distinte valutate nella discovery phase, non il numero di slice nel qualification.

2. **Re-run M31 con DSR**: necessario eseguire BL-023 Fase 5d con DSR+PBO per validare onestamente il REJECTED verdetto. Expected: conferma REJECTED con DSR ≤ 0.5 (n_trials alto, observed Sharpe negativo).

3. **Integration con existing `evaluator.py`**: il `QualificationSummary` attuale non ha campi `worst_dsr`, `pooled_dsr`, `pbo`. Va esteso. Bloccato da BL-500 completion + questo ADR.

## References

- Bailey, D. & López de Prado, M. (2014). "The Deflated Sharpe Ratio." *Journal of Portfolio Management* 40(5):94-107. DOI: 10.3905/jpm.2014.40.5.094.
- Bailey, D., Borwein, J., López de Prado, M. & Zhu, Q. (2017). "The Probability of Backtest Overfitting." *Algorithmic Finance*.
- López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. ch.7 (PurgedKFold), ch.8 (DSR), ch.11/12 (CPCV/PBO).
- ESLazarev (2026). `purgedcv` v0.1.3. https://github.com/eslazarev/purged-cross-validation (MIT).
- mnemox-ai (2026). `deflated-sharpe`. https://github.com/mnemox-ai/deflated-sharpe (Apache-2.0).
- Deep-research synthesis 2026-08-15: `docs/reports/2026-08-15-deep-research-synthesis.md`.

## Implementation pointers

- `analytics/qualification/dsr.py` (wrapper; 15 test verdi).
- `tests/unit/test_dsr.py` (15 test; smoke validazione DSR/PSR/PBO/CPCV/PurgedKFold).
- `scripts/smoke_dsr_packages.py` (smoke test import).
- `scripts/inspect_purgedcv_sigs.py` (introspection helper).
- BL-500 (install): DONE.
- BL-501 (questo ADR): DONE con questo file.
- BL-508 (deprecate mlfinlab aspirational reference in `docs/integration-blueprint-4-frameworks.md`): TODO.
