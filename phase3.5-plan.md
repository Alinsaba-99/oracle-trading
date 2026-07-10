# Phase 3.5 — Signal Optimization & GA Convergence

> 3 settimane · 4 task · Obiettivo: Sharpe > 0.8 in WalkForward su SPY
> Review: CEO (Approve+cond) · Engineering (Blocker: GA wiring) · Design (60 gen, showcase)

---

## 1. Problema

GA esegue 144 backtest in 19s ma Sharpe = -1.0. Cause:

| Causa | Impatto |
|-------|---------|
| **KNN polarizzato BUY** | 80% segnali BUY su trend rialzista → no short → no edge |
| **Segnali separati** | KNN e Alpha factors mai combinati — nessun hybrid |
| **GA settings timidi** | pop=12, gen=12 non converge in 18-26D |
| **GA wiring mancante** | `genetics/fitness/evaluator.py:121` hardcodes GenomeToSignal |

---

## 2. Decisioni Post-Review

| Review | Issue | Decisione |
|--------|-------|-----------|
| **Eng** | GA evaluator hardcodes segnale | **BLOCKER**: parametrizzare evaluator con `signal_factory` in GAConfig |
| **Eng** | 18 parametri → ~26 reali | Ricalcolare: 12 KNN + 12 alpha + 2 hybrid = 26. Aggiungere `_knn`/`_alpha` suffix |
| **Eng** | KNN performance incerta | Benchmark: test 100 calls su SPY 1500. Se >100ms, precompute feature matrix |
| **CEO/Des** | 30 gen insufficienti | **50 generazioni** (non 30). 20 pop × 50 gen × 4 isole = 4.000 eval/isola |
| **Des** | HA posizione ambigua | **HA su features KNN**: RSI/CCI/ADX/WT/MOM calcolati su HA, non su raw OHLCV |
| **CEO** | Regime filter vaporware | **RIMOSSO** da Phase 3.5. Rimandato a Phase 6 (regime-aware switching) |
| **CEO** | Failure post-mortem | **Diagnostica**: GA weight analysis (KNN_weight vs alpha_weight post-run) |
| **Des** | Showcase non specificato | **Artefatti**: Pareto scatter, equity curve top-5, ablation table, hypervolume |

---

## 3. Architettura

```
                    ┌──────────────┐
                    │  Heikin Ashi  │  OHLCV → HA (smooth)
                    └──────┬───────┘
                           ▼
              ┌────────────────────────┐
              │  Feature Computation   │  RSI/CCI/ADX/WT/MOM su HA
              │  + Alpha Library (50)  │  z-score normalizzati
              └────────┬───────────────┘
                       │
           ┌───────────┴───────────┐
           ▼                       ▼
   ┌──────────────┐       ┌──────────────┐
   │  KNN Signal   │       │ Alpha Signal  │
   │  Lorentzian   │       │ 50 factors    │
   │  + balancing  │       │ 8 categorie   │
   └───────┬───────┘       └───────┬──────┘
           └───────┬───────────────┘
                   ▼
          ┌──────────────────┐
          │  Hybrid combiner  │  GA-ottimizzato: knn_weight, alpha_weight
          └───────┬──────────┘
                  ▼
         ┌──────────────────┐
         │   GA Pipeline     │  GeneticEngine + signal_factory → HybridGenomeToSignal
         │  pop=20, gen=50   │  4 isole, 4-fold WFA, embargo=40
         │  3 seed (42/123/999)
         └──────────────────┘
```

---

## 4. Task Dettagliati

### T1: Heikin Ashi ✅ (COMPLETATO)
`genetics/signal/heikin_ashi.py` — conversione OHLCV→HA.
`genetics/signal/__init__.py` — export.
Test: 6 (shape, valori, edge cases).

### T2: KNN Class Balancing ✅ (COMPLETATO)
`genetics/genome/knn_signal.py` — class_weight, distance-weighted vote, adaptive threshold.
Risultato: segnali 96% → 44% attivi.

### T3: Hybrid Signal + GA Wiring (7 giorni)

**T3a: GA Evaluator Refactor — GIORNO 1 (BLOCKER)**
| File | Cosa |
|------|------|
| `genetics/fitness/evaluator.py` | Aggiungere `signal_factory` parameter a FitnessEvaluator.__init__ |
| `genetics/config.py` | Aggiornare GAConfig con signal_type field |
| `tests/genetics/test_ga_integration.py` | Smoke test: pop=4, gen=2 con HybridGenomeToSignal |

**T3b: HybridGenomeToSignal — GIORNO 2-3**
| File | Cosa |
|------|------|
| `genetics/genome/hybrid_signal.py` | ~250 righe. 26 parametri GA. |
| `genetics/genome/__init__.py` | Export HybridGenomeToSignal |
| `tests/genetics/test_hybrid_signal.py` | 10+ test |

**Parametri GA completi (26):**

| # | Parametro | Range | Segnale |
|---|-----------|-------|---------|
| 1 | `knn_k` | 3-20 | KNN |
| 2 | `knn_train_len` | 2-10 | KNN |
| 3 | `knn_threshold` | 0.3-0.9 | KNN |
| 4 | `knn_class_weight` | 0.3-3.0 | KNN |
| 5 | `knn_rsi_period` | 7-21 | KNN |
| 6 | `knn_cci_period` | 10-30 | KNN |
| 7 | `knn_adx_period` | 7-21 | KNN |
| 8 | `knn_wt_channel` | 5-20 | KNN |
| 9 | `knn_wt_avg` | 7-21 | KNN |
| 10 | `knn_mom_period` | 5-20 | KNN |
| 11 | `knn_w_rsi` | 0-2 | KNN |
| 12 | `knn_w_cci` | 0-2 | KNN |
| 13 | `knn_w_adx` | 0-2 | KNN |
| 14 | `knn_w_wt` | 0-2 | KNN |
| 15 | `knn_w_mom` | 0-2 | KNN |
| 16 | `alpha_ret_w` | 0-2 | Alpha |
| 17 | `alpha_mom_w` | 0-2 | Alpha |
| 18 | `alpha_vol_w` | 0-2 | Alpha |
| 19 | `alpha_corr_w` | 0-2 | Alpha |
| 20 | `alpha_volu_w` | 0-2 | Alpha |
| 21 | `alpha_seas_w` | 0-2 | Alpha |
| 22 | `alpha_fund_w` | 0-2 | Alpha |
| 23 | `alpha_micr_w` | 0-2 | Alpha |
| 24 | `alpha_threshold` | 0.01-0.5 | Alpha |
| 25 | `hybrid_knn_w` | 0.0-1.0 | Hybrid |
| 26 | `hybrid_alpha_w` | 0.0-1.0 | Hybrid |

**T3c: Benchmark — GIORNO 1**
```bash
python -c "100 calls KNNGenomeToSignal.compute() on SPY 1500 bars"
```
Target: <100ms per call. Se >100ms → precomputare feature matrix con numpy.

### T4: GA Run Ottimizzata (7 giorni)

| Parametro | Demo (T4a) | Produzione (T4b) |
|-----------|------------|------------------|
| pop_size | 12 | 20 |
| generations | 12 | **50** |
| n_islands | 1 | 4 |
| WFA folds | 2 | 4 |
| purge/embargo | 5/5 | 20/40 |
| Seeds | 42 | 42, 123, 999 |
| Tempo stimato | ~30s | **~15-25 min per seed** |

**Metriche obiettivo:**
- Sharpe medio su 3 seed > 0.8
- Pareto front ≥ 10 strategie non-dominanti
- Sortino > 0.6, Calmar > 0.3
- MaxDD < 25%
- Ablation: hybrid batte KNN-only e alpha-only al punto ottimo

**Diagnostica (failure post-mortem):**
- Se `hybrid_knn_w` → 0: KNN non contribuisce → problema feature Lorentziane
- Se `hybrid_alpha_w` → 0: alpha factors non contribuiscono → problema segnale composito
- Sharpe medio < 0.5 su 3 seed: 26 parametri troppi per 50 gen → ridurre o aumentare pop

## 5. Task Esecuzione (Giorno per Giorno)

| Giorno | Task | Cosa | Output |
|--------|------|------|--------|
| 1 | T3a | Refactor evaluator + benchmark KNN + parametri definitivi | evaluator.py, smoke test, benchmark numbers |
| 2-3 | T3b | HybridGenomeToSignal + test | hybrid_signal.py, 10 test |
| 4 | T4a | GA demo pop=12, gen=12 su ibrido | Prime metriche di convergenza |
| 5-7 | T4b | GA produzione pop=20, gen=50, 4 isole, 3 seed (overnight) | Pareto front, 3 seed risultati |
| 8 | Analisi | Ablation table, Pareto plot, decisione finale | Showcase 20/20 |

## 6. Rischi (Post-Review)

| Rischio | Prob. | Mitigazione | Review |
|---------|-------|-------------|--------|
| GA evaluator wiring rotto | Alta | T3a blocker — fix prima di tutto | Eng |
| 26 params in 50 gen non converge | Media | Se Sharpe < 0.5, ridurre a KNN-solo + alpha-solo | CEO/Des |
| KNN performance 3x lenta | Alta | Benchmark Giorno 1; precompute feature matrix | Eng |
| Regime filter assente → no regime adaptation | Media | Rimandato a Phase 6 — non blocca | CEO |
| HA cambia statistica feature KNN | Bassa | Documentato: RSI/CCI/ADX su HA, non su raw | Des |

## 7. Showcase Deliverables (T4b output)

- **Pareto front scatter**: 4D (Sharpe, Sortino, Calmar, MaxDD) colorato per isola
- **Walkforward equity curves**: top-5 strategie, 4 fold ciascuna = 20 curve
- **Parameter sensitivity heatmap**: correlazione parametri → Sharpe
- **Hypervolume convergence**: per generazione, per isola
- **Ablation table**: hybrid vs KNN-only vs alpha-only allo stesso seed
- **Generations_log**: Sharpe max per generazione (bar chart convergenza)

---

## 8. The5ers Evaluation Targets (Prop Firm Barrier)

The5ers Hyper Growth (1-step) è il benchmark per le nostre strategie:

| Metrica | The5ers | Nostro Target |
|---------|---------|---------------|
| Profit target | 10% | ≥ 10% |
| Max drawdown (stop out) | 6% | < 6% |
| Daily loss limit | 3% | < 3% |
| Minimo giorni profittevoli | 3 | ≥ 3 |
| Tempo | Illimitato | N/A |
| Profit Factor | > 1.67 | > 1.67 |

Tradotto in metriche GA:
- Sharpe > 0.8 · Sortino > 0.6 · Calmar > 0.3
- Profit Factor > **1.67** (per passare la valutazione)
- MaxDD < **6%** · Daily Loss < **3%** (limiti hard)
- ≥ 3 giorni profittevoli su rolling 5gg (consistenza)

---

## 9. Benchmark: 3 Prop Firm Evaluation Rules

Target consolidato per l'ottimizzazione GA — le strategie devono passare ALMENO una
di queste valutazioni per essere considerate "efficienti":

| Metrica | The5ers Hyper | Lucid Pro | Lucid Flex |
|---------|---------------|-----------|------------|
| Profit target | **10%** | **6%** ($3k/$50k) | **8%** |
| Max drawdown | **6%** | **4%** ($2k/$50k) | **5%** |
| Daily loss limit | **3%** | **2.4%** ($1.2k/$50k) | **3%** |
| Min profitable days | 3 | Nessuno | 5 |
| Consistenza | No | Sì (30% max giornaliero) | Sì (30% max) |
| Profit Factor minimo | **> 1.67** | **> 1.50** | **> 1.60** |

### Target GA Unificato (The5ers + Lucid)

```
┌─────────────────────────────────────────────────────────────────────┐
│  PROFIT FACTOR > 1.67   (obiettivo primario — passare valutazione)  │
│  MAX DRAWDOWN < 6%       (hard constraint — stop out)                │
│  DAILY LOSS < 3%         (hard constraint — daily limit)             │
│  GIORNI PROFITTEVOLI ≥ 3 (consistenza)                              │
│  SHARPE > 0.8            (obiettivo secondario)                      │
│  SORTINO > 0.6           (downside risk)                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Come li integriamo nel GA

1. **Profit Factor** come 5° obiettivo NSGA-II (aggiunto ai 4 esistenti)
2. **MaxDD < 6%** e **Daily Loss < 3%** come hard constraint:
   - Se violati → fitness sentinel (penalizzato)
3. **Giorni profittevoli ≥ 3** come consistency bonus:
   - Se soddisfatto → moltiplicatore 1.2x sulla fitness
4. **Peso maggiorato su Sortino** (downside risk è critico per prop firm)
