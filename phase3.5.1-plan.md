# Phase 3.5.1 — GA Convergence Fix

> Fix: NSGA-II "no-trade" local optimum · CAGR + PF come vincoli su obiettivi esistenti
> Review: CEO (Revise) · Eng (Moderate Risk) · Design (Conditional Approve)

---

## 1. Problema

NSGA-II converge a "no trade" perché 4 obiettivi (Sharpe, Sortino, Calmar, MaxDD) sono tutti ratio/rischi — nessuno premia il rendimento assoluto. Strategia no-trade ha MaxDD=0 → Pareto-ottimale.

**Review: CAGR assente è la causa radice** (CEO/Design). Aggiungere CAGR come vincolo risolve con 1 modifica.

## 2. Decisioni Post-Review

| Review | Issue | Decisione |
|--------|-------|-----------|
| **CEO** | Fix 2: penalty simmetrica | **RIMOSSA** — CAGR come moltiplicatore, non penalty |
| **CEO** | Penalty-stacking senza priorità | **Singolo moltiplicatore** combinato (CAGR + PF), non 3 indipendenti |
| **Design** | 5 obiettivi rompe FitnessValue | **4 obiettivi mantenuti**. CAGR/PF come modifiche a Sharpe/Sortino/Calmar |
| **Design** | Sortino ridondante con Sharpe | **MANTENUTO** (non rompe, ottimizzazione futura) |
| **Eng** | `fitness *= 0.5` crasha (tuple) | **Tuple comprehension**: moltiplicare solo obiettivi positive-direction |
| **Eng** | Cache consistency | **Constraint params nel cache key** |
| **Eng** | CAGR/PF default 0.0 rompe test | **Solo quando key esiste E non-None** |

## 3. Implementazione (3 modifiche, 2 file)

### genetics/fitness/evaluator.py

```python
# A — Aggiungere a __init__
self._min_trades: int = 10

# B — Dopo _extract_fitness, PRIMA di cache write
constraints = self._apply_constraints(fitness_tuple, combined)
if constraints is None:
    return _EMPTY_FITNESS  # ← sentinel per low trades
return constraints

# C — Nuovo metodo
def _apply_constraints(self, fitness: tuple, combined: dict) -> tuple | None:
    # Fix 1: Min trade sentinel
    total_trades = sum(r.total_trades for r in self._fold_results)
    if total_trades < self._min_trades:
        return None  # caller returns _EMPTY_FITNESS

    # Fix 2: CAGR multiplier (solo se key esiste)
    cagr = combined.get("cagr_mean")
    cagr_mult = 1.0
    if cagr is not None and cagr < 0.05:
        cagr_mult = cagr / 0.05  # penalità lineare sotto 5%

    # Fix 3: PF multiplier (solo se key esiste)
    pf = combined.get("profit_factor_mean")
    pf_mult = 1.0
    if pf is not None and pf < 1.0:
        pf_mult = max(pf, 0.01)  # penalità lineare sotto 1.0

    # Applica moltiplicatori solo a obiettivi positive-direction (0,1,2)
    mult = min(cagr_mult, pf_mult)  # il più restrittivo
    if mult < 1.0:
        sharpe, sortino, calmar, maxdd = fitness
        return (sharpe * mult, sortino * mult, calmar * mult, maxdd)
    return fitness
```

### genetics/engine.py + genetics/config.py

- GAConfig: `min_trades: int = 10`
- GeneticEngine.run: pass `min_trades` a FitnessEvaluator
- Cache key: include min_trades parameter

## 4. Esecuzione

```
Ora:   Applicare 3 fix (evaluator.py + engine.py + config.py)
       pytest tests/ -q (verificare 1200+ test)
       GA run pop=12, gen=20, hybrid signal, min_trades=10
Attesa: ~2 min per fix, ~3 min per GA run
```
