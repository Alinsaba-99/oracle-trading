# Phase 3.5 — Signal Optimization & GA Convergence

> 2-3 settimane · 4 task · Obiettivo: Sharpe > 0.8 in backtest WalkForward
> Documenti allineati: PROJECT.md (roadmap), SPECIFICATION.md (architettura)
> Dipendenze: nessuna nuova — tutto già in `genetics/`

---

## 1. Problema (perchè Sharpe è piatta)

Il GA esegue 144 backtest in 19s ma Sharpe resta -1.0. Cause:

| Causa | Effetto |
|-------|---------|
| **KNN polarizzato BUY** | 80% segnali BUY su SPY 2015-2020 (+103%) |
| **Nessuna feature direzionale** | KNN su feature tecniche (RSI/CCI/ADX) non cattura trend |
| **Segnale non combinato** | AlphaGenomeToSignal e KNN sono separati — nessun hybrid |
| **GA settings timidi** | pop=12, gen=12 è dimostrativo, non convergente |

## 2. Soluzione: 3 Segnali, 1 GA Unificato

```
                    ┌──────────────┐
                    │  Heikin Ashi  │  OHLCV → HA smooth
                    └──────┬───────┘
                           ▼
               Feature Extraction Layer
         ┌──────────────┬──┴──┬──────────────┐
         ▼              ▼                  ▼
   ┌──────────┐   ┌──────────┐     ┌──────────────┐
   │KNN Signal│   │Alpha Sig │     │  Hybrid Sig  │
   │Lorentzian│   │50 factors│     │  KNN + Alpha │
   │+balance  │   │8 categ.  │     │  + regime    │
   └────┬─────┘   └────┬─────┘     └──────┬───────┘
        └──────────────┴──────────────────┘
                           ▼
                 ┌──────────────────┐
                 │    GA Engine      │  pop=20, gen=30
                 │  NSGA-II, 4 isole  │  4-fold WFA, SPY
                 │  Sharpe, Sortino,  │
                 │  Calmar, MaxDD     │
                 └──────────────────┘
```

---

## 3. Task Dettagliati

### T1: Heikin Ashi ✅ (COMPLETATO)

| File | Cosa |
|------|------|
| `genetics/signal/heikin_ashi.py` | `to_heikin_ashi(data) → pl.DataFrame` |
| `tests/genetics/test_heikin_ashi.py` | 6 test (shape, valori, edge cases) |

### T2: KNN Class Balancing ✅ (COMPLETATO)

Modifiche a `genetics/genome/knn_signal.py`:

| Miglioramento | Dettaglio |
|---------------|-----------|
| **class_weight** | Nuovo parametro GA (0.3-3.0): boost classe minoritaria |
| **Distance-weighted vote** | Neighbors più vicini pesano di più |
| **Adaptive threshold** | Minimo 0.5 floor per stabilità |
| **Risultato** | Segnali da 96% → 44% attivi, ratio buy/sell più bilanciato |

### T3: Hybrid Signal (KNN + Alpha Factors)

**File:** `genetics/genome/hybrid_signal.py`

Combina KNN e AlphaFactors in un unico segnale con peso ottimizzabile dal GA:

```python
class HybridGenomeToSignal:
    """Combina KNN Lorentziano + 50 Alpha Factors + Regime Filter.

    Parametri GA:
    - knn_weight (0.0-1.0): quanto contribuisce KNN
    - alpha_weight (0.0-1.0): quanto contribuiscono alpha factors
    - regime_filter: toggle filtro per regime di mercato
    - ... tutti i parametri KNN + alpha esistenti
    """

    def compute(self, data):
        # 1. Heikin Ashi conversion
        ha_data = to_heikin_ashi(data)
        # 2. KNN signal on HA data
        knn_sig = knn_model.compute(ha_data)
        # 3. Alpha signal on HA data
        alpha_sig = alpha_model.compute(ha_data)
        # 4. Combine with GA-optimised weights
        combined = knn_weight * knn_sig + alpha_weight * alpha_sig
        # 5. Regime filter (optional): skip trades in choppy regimes
        return combined
```

**Parametri GA totali:** 6 (alpha) + 10 (KNN) + 2 (hybrid weights) = **18 parametri**

### T4: GA Run Ottimizzata

| Parametro | Dimostrazione | Produzione |
|-----------|---------------|------------|
| pop_size | 12 | **20** |
| generations | 12 | **30** |
| n_islands | 1 | **4** |
| WFA folds | 2 | **4** |
| WalkForward | purge=5, embargo=5 | purge=20, embargo=40 |
| Seed | 42 | **3 seeds** (42, 123, 999) |
| Tempo stimato | 21s | **~8-12 min** |

**Metriche obiettivo:**
- Sharpe medio su 3 seed > 0.8
- Pareto front ≥ 10 strategie non-dominanti
- Sortino > 0.6, Calmar > 0.3
- MaxDD < 25%
- Almeno 1 strategia outperform B&H

---

## 4. File Plan

### Nuovi files
| File | Task | Righe |
|------|------|-------|
| `genetics/genome/hybrid_signal.py` | T3 | ~200 |
| `genetics/signal/__init__.py` | T1 | 20 |
| `tests/genetics/test_hybrid_signal.py` | T3 | ~100 |
| `tests/genetics/test_heikin_ashi.py` | T1 | ~80 |

### Modifiche
| File | Task | Cosa |
|------|------|------|
| `genetics/genome/knn_signal.py` | T2 | ✅ Class balancing già fatto |
| `genetics/genome/signal.py` | T3 | Export HybridGenomeToSignal |
| `genetics/genome/__init__.py` | T3 | Export HybridGenomeToSignal |
| `showcase.py` | T4 | GA run ottimizzata |

---

## 5. Rischi e Mitigazioni

| Rischio | Prob. | Mitigazione |
|---------|-------|-------------|
| Hybrid signal non meglio dei singoli | Media | GA sceglie i pesi — se KNN non serve, knn_weight→0 |
| Heikin Ashi introduce lag | Bassa | HA è smooth, non leading — accettabile per daily |
| GA 30 gen × 20 pop × 4 fold × 4 isole = 9.600 backtest | Alta | Esecuzione overnight o su macchina dedicata |
| Overfitting su periodi specifici | Media | 3 seed diversi + 4-fold WFA + embargo 40gg |

---

## 6. Esecuzione

```
Giorno 1-2: T3 (Hybrid Signal) — creazione e test unitari
Giorno 3-4: T4a (GA dimostrativa pop=12, gen=12) — verifica ibrido
Giorno 5-7: T4b (GA produzione pop=20, gen=30, 4 isole) — overnight
Giorno 8:   Analisi risultati, showcase, commit
```
