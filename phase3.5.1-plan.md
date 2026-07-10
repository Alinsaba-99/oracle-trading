# Phase 3.5.1 — GA Convergence Fix

> Fix: NSGA-II "no-trade" local optimum · PF come obiettivo esplicito
> Dati: SPY Daily yfinance (1510 bar, 2015-2020)

---

## 1. Dati Utilizzati

| Proprietà | Valore |
|-----------|--------|
| **Fonte** | Yahoo Finance (`yfinance`) |
| **Simbolo** | SPY (SPDR S&P 500 ETF Trust) |
| **Timeframe** | **Daily (1D)** — 1 barra = 1 giorno di trading |
| **Periodo** | 2015-01-01 → 2020-12-31 (6 anni) |
| **Barre totali** | **1.510** (~252/anno) |
| **Range prezzo** | $170.47 → $345.41 (+103% B&H) |
| **Informazioni** | `pip install yfinance` — dati EOD gratuiti |

**Nota:** Daily data è il punto di partenza standard per strategie sistematiche. Per eseguire strategie a più alta frequenza (intraday) servirebbero dati tick/minute, che hanno costi. Il nostro obiettivo attuale è provare il concetto su daily — se funziona, possiamo scalare a frequenze più alte.

---

## 2. Problema

Il GA (NSGA-II) converge a "no trade" come soluzione Pareto-ottimale perché:

```
Strategia A (no trade):   Sharpe = 0, MaxDD = 0%,   Calmar = 0
Strategia B (trade):       Sharpe = X, MaxDD = Y%,   Calmar = Z
```

NSGA-II trova A Pareto-ottimale perché ha MaxDD=0 e Calmar=0 — nessuna strategia con drawdown > 0 la domina sul fronte rischio.

**Causa radice:** la fitness function a 4 obiettivi (Sharpe, Sortino, Calmar, MaxDD) non include il **Profit Factor** o il **rendimento assoluto**. Una strategia che non trade ha drawdown zero e viene preferita.

---

## 3. Soluzione

### Fix 1: Minimo trade constraint

Aggiungere un constraint nella fitness function: **se total_trades < 10 → fitness sentinel** (penalizzata). Questo elimina la strategia "no trade" dal Pareto front.

### Fix 2: Profit Factor come obiettivo (o vincolo soft)

Aggiungere Profit Factor come 5° obiettivo, OPPURE aggiungere una penalità lineare:
- `fitness_penalty = -abs(n_trades - target_trades) * 0.01`
- Se PF < 1.0 → fitness ulteriormente penalizzata

### Fix 3: Rendimento minimo

Penalizzare strategie con rendimento annuo < 5%:
- `if cagr < 0.05: fitness *= 0.5`

### Implementazione

| File | Modifica |
|------|----------|
| `genetics/fitness/evaluator.py` | Aggiungere `min_trades` parameter, PF check, CAGR check |
| `genetics/engine.py` | Passare `min_trades` da GAConfig |
| `genetics/config.py` | Aggiungere `min_trades: int = 10` a GAConfig |

---

## 4. Dati Alternativi (futuro)

Se vogliamo frequenze più alte o più simboli:

| Fonte | Timeframe | Costo | Volume dati |
|-------|-----------|-------|-------------|
| yfinance | Daily, 1h | Gratis | Illimitato |
| Polygon.io | Minute, tick | $29/mese | 5 anni storici |
| Alpha Vantage | Daily, intraday | Gratis (5 req/min) | 100k chiamate/giorno |
| QuestDB (locale) | Tick | Infrastruttura | Nostro storage |

---

## 5. Prossimo Passo

Applicare i 3 fix e rilanciare GA (pop=12, gen=20) per verificare che il Pareto front contenga strategie con PF > 1.67 E MaxDD < 6%.
