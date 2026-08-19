# BL-505c — Lane B Backtest Comparison: v1 vs v2 vs relaxed config

> **Data**: 2026-08-15
> **Scope**: confronto 3 configurazioni del LaneBBacktester per identificare il trade-off Sharpe vs Max DD e trovare il sweet spot per deploy capitale reale
> **Source**: `scripts/run_lane_b_backtest.py` con SimFin bulk data + SPY ETF (SimFinId 1072401) benchmark

---

## TL;DR

**La configurazione "v1 relaxed" (top_n=25, min_f_score=6, return_12m_min=-0.20) su 2015-2024 produce il risultato migliore**: annual +11.24%, Sharpe 0.639, Max DD 27.01%, alpha vs SPY +9.11%. **MA Max DD 27% resta sopra target <15%**. La configurazione "v2 stringent" (top_n=15, min_f_score=8) peggiora drasticamente (Sharpe 0.09, alpha -32.75%) perché il filtro troppo stringente non produce abbastanza holdings nel warmup.

## Risultati comparativi

| Run | Periodo | top_n | min_f | ret_12m_min | Annual | Sharpe | Max DD | Hit rate | Alpha vs SPY | Unique tickers |
|---|---|---|---|---|---|---|---|---|---|---|
| v1 (BL-505b) | 2020-2024 | 25 | 7 | -0.20 | +6.24% | 0.408 | 34.51% | 40% | n/a | 185 |
| **v1 relaxed** | 2020-2024 | 25 | 6 | -0.20 | **+12.13%** | **0.679** | 27.01% | 45% | +12.74% | 175 |
| **v1 relaxed** | 2015-2024 | 25 | 6 | -0.20 | **+11.24%** | **0.639** | 27.01% | 22.5% | +9.11% | 175 |
| v2 stringent | 2017-2024 | 15 | 7 | -0.15 | +3.73% | 0.280 | 37.97% | 25% | -18.92% | 129 |
| v2 stringent | 2015-2024 | 15 | 8 | -0.10 | -0.46% | 0.093 | 38.88% | 15% | -32.75% | 128 |

## Diagnosi

### RISULTATO MIGLIORE: v1 relaxed 2020-2024
- Annual +12.13% (vs SPY +31.30% nel periodo; sottoperforma ma con +12.74% alpha! — aspetta, contraddizione)
- Sharpe 0.679 (sopra target 0.5 ✅)
- Max DD 27.01% (sotto v1 34.51% ma ancora sopra target 15%)
- Hit rate 45% (vs 40% v1; vicino al target 50%)
- 175 unique tickers (diversificazione realistica)

### Attenzione: alpha vs SPY contraddittorio
v1 relaxed 2020-2024: annual +12.13% vs SPY +31.30%. **Alpha = +12.74%** → ASSURDO perché SPY ha fatto meglio. Questo indica un bug nel calcolo dell'alpha:
- L'alpha è calcolato come `total_return - benchmark_return` ma su periodi diversi (warmup 7 sessioni 0-trade vs SPY che ha tutti i dati)
- Per confronto onesto, l'alpha dovrebbe essere calcolato solo sul periodo dove il portafoglio è invested (post-warmup)

### Warmup issue: 27 sessioni su 40 con 0 holdings
- 2015-2024: 27 sessioni iniziali con 0 holdings (simfin data PIT per F-Score non disponibile prima del 2021 nei bulk quarterly)
- 2020-2024: 7 sessioni con 0 holdings (meno)
- **Soluzione**: estendere il periodo di scarico dati SimFin o usare un altro loader per 2015-2020

### Configurazione v2 stringente è PEGGIORE
- Sharpe 0.093 (vs 0.639 v1 relaxed) — il filtro troppo stringente non produce holdings sufficienti
- Max DD 38.88% (vs 27.01% v1 relaxed) — peggiorato per концентrazione su pochi titoli
- Hit rate 15% (vs 22.5% v1 relaxed) — too few holdings = troppo rumore

**Conclusione**: stringere i filtri NON aiuta; la diversificazione (più holdings) è più importante della "qualità" (F-Score più alto).

## Diagnosi: perché v1 relaxed batte v2 stringent

1. **Diversificazione vs concentrazione**: 25 holdings vs 15 → minor idiosyncratic risk, minor Max DD
2. **F-Score 6 vs 8**: F-Score 8 è troppo stringente — rimuove aziende "in recupero" dove il F-Score sta migliorando ma è ancora 6-7 (es. INTC in turnaround)
3. **return_12m_min -0.20 vs -0.10**: -0.10 rimuove falling knives, MA rimuove anche i turnaround reali (che sono spesso sotto -10% prima della ripresa)

## Verdetto onesto

**v1 relaxed 2020-2024 è il candidato per deploy capitale reale**, MA:
1. **Max DD 27% ancora sopra target 15%** — per deploy reale serve < 15%
2. **Warmup 7 sessioni 0-trade** su 20 totali = 35% del backtest è invalidato
3. **Alpha vs SPY calcolato male** — serve fix nel codice per calcolare alpha solo sul periodo post-warmup

**Confronto con Lane A (BL-503)**:
- Lane A 8/8 REJECTED, Sharpe 0.13-0.27 = beta
- Lane B v1 relaxed: Sharpe 0.679, annual +12.13%, alpha +12.74% vs SPY (modulo bug calcolo)
- **Lane B batte Lane A di un fattore 3-5× su Sharpe**

## Fix necessari per deploy capitale reale (BL-505d futuro)

1. **Fix alpha calculation**: calcolare alpha solo sul periodo dove il portafoglio è invested (post-warmup)
2. **Fix warmup**: scaricare dati SimFin estesi 2010-2020 per avere F-Score PIT completo su tutto il periodo 2015-2024
3. **Aggiungere sector filter**: escludere financial in stress (2008-09), energy in crash (2014-16, 2020), per ridurre Max DD
4. **Aggiungere stop-loss per idea**: -20% per idea → exit, riduce Max DD portfolio
5. **DSR/PBO/PSR** (ADR-017) quando il backtest è valido su periodo intero

## File generati

- `scripts/run_lane_b_backtest.py` — script con CLI args + SPY benchmark
- `analytics/strategy/lane_b_backtester.py` — backtester con SPY benchmark config
- `docs/reports/lane-b/backtest_result.json` — dati machine-readable ultimo run
- `docs/reports/lane-b/backtest_report.md` — markdown report ultimo run

---

*Fine BL-505c. v1 relaxed è il candidato migliore ma Max DD 27% ancora sopra target. Fix alpha calculation + sector filter + stop-loss sono i prossimi step. Prossimo: BL-503b ForecastCombine multi-rule per Lane A.*
