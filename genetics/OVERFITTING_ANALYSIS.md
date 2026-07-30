# Overfitting Risk Analysis — GA Pipeline (oracle-trading/genetics/)

**Data:** 2026-07-30  
**Analyst:** Hermes Agent

---

## Tabella Riepilogativa

| File/Modulo | Walk-Forward? | Train/Val/Test Split? | Holdout Set? | Severità |
|---|---|---|---|---|
| `evolution.py` | ❌ NO | ❌ NO | ❌ NO | 🔴 CRITICAL |
| `ga_evolution.py` | ❌ NO (docstring dice sì, ma è placeholder) | ❌ NO | ❌ NO | 🔴 CRITICAL |
| `fitness/evaluator.py` | ✅ SÌ (WF Engine) | ✅ SÌ (walk-forward folds) | ❌ NO | 🟡 HIGH |
| `engine.py` (GeneticEngine) | ✅ SÌ (delega a FitnessEvaluator) | ✅ SÌ | ❌ NO | 🟡 HIGH |
| `gates/` (ast_audit, subprocess, protocol) | N/A (sicurezza) | N/A | N/A | 🟢 NONE |
| `genome/` (signal, codec, parametri) | N/A (data model) | N/A | N/A | 🟢 NONE |
| `population/` (seeding, stats, migration) | N/A (GA operators) | N/A | N/A | 🟢 NONE |

---

## Analisi Dettagliata per File

### 1. `evolution.py` — 🔴 CRITICAL

**Ruolo:** Pipeline semplificata per candidate strategy: AST audit → subprocess → protocol → backtest → fitness.

**Problemi:**
- **Nessuno split dei dati.** `_quick_backtest()` processa l'intero array `close_prices` in un unico segmento.
- **Nessuna separazione train/test.** La strategia viene addestrata e testata sugli stessi identici dati.
- **Fitness calcolata sull'intero dataset.** Sharpe, Calmar, DD, Win Rate sono calcolati su tutto il periodo senza validazione out-of-sample.
- **Usa dati sintetici se `close_prices` è None** — in quel caso genera OHLC random e testa su quelli (nessun overfitting ma anche nessuna significatività).

**Verdetto:** Overfitting totale. Qualsiasi strategia che passa questo pipeline ha il 100% di probabilità di essere overfittata.

### 2. `ga_evolution.py` — 🔴 CRITICAL

**Ruolo:** Classe `StrategyEvolution` — GA semplificato per pesi di fattori. Docstring menziona "walk-forward fitness evaluation".

**Problemi:**
- **Walk-forward non esiste.** `evaluate_fitness()` è un placeholder che calcola `sharpe * calmar / (1 + turnover)` da attributi attesi (non calcolati internamente).
- **Nessun backtest embeddato.** La classe si aspetta che sharpe/calmar/turnover siano settati esternamente.
- **Nessuna validazione incrociata dei dati.**

**Verdetto:** Anche se fosse usato solo come scheletro/test, la mancanza di split dei dati rende qualsiasi fitness calcolata potenzialmente overfittata.

### 3. `fitness/evaluator.py` — Il Punto Migliore, ma Ancora 🟡 HIGH

**Ruolo:** `FitnessEvaluator` — il cuore della valutazione fitness. Usa `WalkForwardEngine` per validazione walk-forward.

**Cosa fa BENE:**
- ✅ **Walk-forward reale** tramite `WalkForwardEngine` con splittatori:
  - `time_series_split()` — expanding window con purge_window
  - `cpcv_split()` — Combinatorial Purged CV con purge_window
- ✅ **Purge window** (default 5) — gap tra train e test fold per evitare leakage
- ✅ **Multi-oggettivo** — 4 obiettivi: Sharpe, Sortino, Calmar, MaxDD. NSGA-II seleziona fronti di Pareto.
- ✅ **Espansione incrementale senza look-ahead** — nelle funzioni feature (KNN, Alpha) le normalizzazioni usano solo dati passati (expanding Welford).
- ✅ **Vincoli** — `_apply_constraints()`: min_trades, CAGR penalty, MaxDD hard cap (50%), Profit Factor penalty.
- ✅ **Caching fitness** — `FitnessCache` con hash di genome+fold+data (non causa overfitting, solo performance).

**Cosa manca — 🔴 NO HOLDOUT SET:**
- **TUTTI i dati vengono usati per walk-forward.** Non c'è un segmento finale di dati tenuto nascosto per validazione finale.
- Il walk-forward copre il 100% del dataset. Il gold standard per GA in finanza è: training (WF) → validation (WF metrics) → **holdout finale**.
- **Selezione basata sulla media across folds** — NSGA-II seleziona i migliori genomi sulla media delle metriche dei fold. Questo può overfittare a pattern specifici dei fold.
- **Nessun early stopping** basato su validation score.

**Verdetto:** La walk-forward riduce il rischio ma l'assenza di un holdout set lascia una finestra di overfitting significativa. Il GA può ancora adattarsi ai pattern medi dei fold.

### 4. `engine.py` (GeneticEngine) — 🟡 HIGH

**Ruolo:** Orchestratore GA con island model + checkpoint/restart.

**Problemi:**
- Delega a `FitnessEvaluator` → stessi issue del punto 3
- **Nessun holdout finale** separato nel `run()` method
- I checkpoint salvano lo stato completo ma non preservano un test set separato
- **Hall of Fame** (20 best) basato su fitness WF, non su un validation set indipendente

### 5. `gates/` — 🟢 NONE

**Ruolo:** 3 gate di sicurezza pre-backtest.

- AST audit (Gate 1) — sicurezza statica del codice
- Subprocess isolation (Gate 2) — esecuzione isolata con timeout/memory limit
- Protocol check (Gate 3) — verifica che la strategia rispetti il contratto BacktestSignal

**Nota:** Usano dati casuali per i test (random uniform per OHLC). Non rilevanti per overfitting.

### 6. `genome/` — 🟢 NONE

Genome data model, encoding/decoding, e 5 implementazioni signal:
- `GenomeToSignal` — 4 feature weights + soglia
- `AlphaGenomeToSignal` — 8 categorie alpha factors + 1 threshold (fino a 50 fattori)
- `KNNGenomeToSignal` — KNN con Lorentzian distance (15 parametri GA-ottimizzabili)
- `HybridGenomeToSignal` — KNN + Alpha + Heikin Ashi (26 parametri GA-ottimizzabili)
- `PairTradingSignal`, `ExpressionGenomeToSignal`

**Rischio:** Più parametri = più gradi di libertà per overfittare. Hybrid (26 params) è il più a rischio. Le feature sono calcolate senza look-ahead, ma il GA può comunque adattarsi al rumore dei fold WF.

### 7. `population/` — 🟢 NONE

- `seeding.py` — 10 template strategia (inizializzazione con bias)
- `stats.py` — Metriche popolazione + Pareto front
- `migration.py` — Ring migration topology

Nessun impatto diretto su overfitting. La migrazione ad anello aiuta la diversità (indirettamente riduce overfitting prematuro).

### 8. `islands.py` — 🟢/🟡 LOW (indiretto)

- Island model con NSGA-II e migrazione periodica. Aiuta la diversità genetica.
- **Rischio:** `merge_pareto_fronts()` combina tutti i fronti degli island — seleziona su tutta la popolazione senza validazione incrociata aggiuntiva.

---

## Riepilogo dei Rischi Principali

| # | Rischio | Impatto | Dove |
|---|---|---|---|
| 1 | **Nessun holdout set finale** | 🔴 CRITICAL | Ovunque: fitness/evaluator, engine, evolution.py |
| 2 | **evolution.py usa 100% dati per backtest** | 🔴 CRITICAL | evolution.py |
| 3 | **Selezione su media WF folds** | 🟡 HIGH | fitness/evaluator.py → NSGA-II |
| 4 | **Nessun early stopping su validation** | 🟡 HIGH | engine.py |
| 5 | **Alta dimensionalità (26 params in Hybrid)** | 🟡 MEDIUM | genome/hybrid_signal.py |
| 6 | **Fitness caching può mascherare stale data** | 🟢 LOW | fitness/cache.py |

---

## Raccomandazioni

### 1. Aggiungere Holdout Set Finale 🔴 PRIORITY 1
Nel `GeneticEngine.run()` o `FitnessEvaluator.evaluate()`, riservare un 20% finale dei dati come holdout. Fitness = metriche WF medie sui fold **MA** il miglior genome finale viene validato sull'holdout.

### 2. Early Stopping Basato su Validation 🟡 PRIORITY 2
Introdurre un validation set (es. penultimo 10-15% dei dati) e fermare il GA quando la fitness di validation smette di migliorare per N generazioni.

### 3. Walk-Forward + Holdout a Due Stadi 🟡 PRIORITY 2
```
Train (60%) | Val (20%) | Holdout (20%)
     ↓          ↓
   WF folds   Validation   →   Final test (1x, mai visto)
```

### 4. Complexity Penalty per Signal Types 🟢 PRIORITY 3
Applicare una penalità di complessità (AIC/BIC-style) per segnali con molti parametri (Hybrid 26 params).

### 5. evolution.py — Fix Immediato 🟢 PRIORITY 3
Se usato, aggiungere split train/test base (es. 70/30) prima del backtest.

---

## Conclusione

La pipeline GA di oracle-trading ha **una solida base di walk-forward con purge window e multi-oggettivo**, ma **manca un holdout set finale** che è essenziale in qualsiasi sistema di ottimizzazione genetica finanziaria. Senza holdout, il GA può overfittare ai pattern dei fold specifici e produrre strategie che sembrano eccellenti in walk-forward ma falliscono in produzione.

**Giudizio complessivo: 🟡 ALTO RISCHIO OVERFITTING**
- La walk-forward mitigativa esiste ma è incompleta
- La selezione GA opera su metriche aggregate senza validazione finale indipendente
- I signal types più complessi (Hybrid, KNN) moltiplicano i gradi di libertà
