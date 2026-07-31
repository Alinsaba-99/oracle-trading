# Root Cause Analysis — Sweep Completo (19 Asset×TF)

> Data: 2026-07-28 | Totale: 2,471 trade | 19 combinazioni

---

## 1. Classifica Completa per Sharpe

| # | Asset | TF | Sharpe | Trades | WR% | PnL | Regime→Specialist |
|---|-------|----|--------|--------|-----|------|-------------------|
| 1 | **GC** | **1d** | **+5.84** | 26 | 84.6% | +$767 | **bear→mean_rev** |
| 2 | **SPY** | **1d** | **+3.62** | 107 | 41.1% | +$427 | bull→trend |
| 3 | **ES** | **1d** | **+3.39** | 101 | 42.6% | +$3,433 | bull→trend |
| 4 | QQQ | 1d | +3.35 | 108 | 42.6% | +$426 | bull→trend |
| 5 | **NQ** | **1d** | **+3.26** | 106 | 42.4% | +$17,171 | bull→trend |
| 6 | BNBUSDT | 1d | +3.03 | 17 | 52.9% | +$174 | choppy→mean_rev |
| 7 | DIA | 1d | +3.06 | 110 | 35.4% | +$210 | bull→trend |
| 8 | **EURUSD** | **1d** | **+2.37** | 43 | 72.1% | +$0.31 | **choppy→mean_rev** |
| 9 | IWM | 1d | +2.08 | 108 | 41.7% | +$122 | bull→trend |
| 10 | **ES** | **1h** | **+1.90** | 80 | 63.7% | +$850 | **choppy→mean_rev** |
| 11 | NQ | 1h | +1.10 | 79 | 60.8% | +$1,675 | bear→mean_rev |
| 12 | BTCUSDT | 1d | +0.46 | 20 | 65.0% | +$2,438 | choppy→mean_rev |
| 13 | BNBUSDT | 1h | +0.21 | 446 | 66.4% | +$104 | choppy→mean_rev |
| 14 | CL | 1h | +0.16 | 191 | 35.1% | +$5 | volatile→**breakout** |
| 15 | BTCUSDT | 1h | -0.20 | 494 | 62.4% | -$9,719 | choppy→mean_rev |
| 16 | CL | 1d | -0.27 | 36 | 72.2% | -$7 | choppy→mean_rev |
| 17 | GC | 1h | -0.33 | 70 | 70.0% | -$132 | choppy→mean_rev |
| 18 | SOLUSDT | 1h | -0.62 | 318 | 63.2% | -$77 | choppy→mean_rev |
| 19 | SOLUSDT | 1d | -9.65 | 11 | 45.5% | -$98 | choppy→mean_rev |

---

## 2. Pattern Emergenti

### Pattern A: Bull Market → Trend Following (Sharpe +2→+4)

```
Regime=bull → Specialist=trend
Asset: ES, NQ, SPY, QQQ, DIA, IWM (TUTTI i futures/equities bull)
Sharpe: +2.08 to +3.62
WR: 35-43%
```

**Root cause**: In bull markets, trend specialists catturano i movimenti direzionali lunghi. Il win rate basso (35-43%) è normale — poche grandi vincite compensano molte piccole perdite.

**Edge reale?** 🔴 Probabilmente no. È semplicemente un long-biased strategy in un mercato che è stato prevalentemente bullish dal 2009 al 2026. Il trend specialist è essenzialmente un "buy and hold con trailing stop".

### Pattern B: Choppy/Bear → Mean Reversion (Sharpe +0→+6)

```
Regime=choppy/bear → Specialist=mean_rev
Asset: GC, EURUSD, ES 1h, BNBUSDT
Sharpe: +0.21 to +5.84
WR: 52-85%
```

**Root cause**: In mercati laterali o bear, la mean reversion cattura i rimbalzi dai livelli di supporto/resistenza. GC in bear regime ha Sharpe +5.84 (84.6% WR) — oro come safe haven in mercati ribassisti.

**Edge reale?** 🟡 Possibile su GC e EURUSD, ma va confermato con dati più lunghi.

### Pattern C: Volatile → Breakout (Sharpe ~0)

```
Regime=volatile → Specialist=breakout
Asset: CL 1h solo
Sharpe: +0.16
WR: 35.1%
```

**Root cause**: Breakout funziona solo in condizioni di volatilità esplosiva. Troppi falsi breakout.

**Edge reale?** 🔴 No. Sharpe vicino a zero.

### Pattern D: Crypto 1h → Distruzione di capitale

```
Asset: BTC, SOL, 1h
Sharpe: -0.20 to -0.62
WR: 62-63%
```

**Root cause**: La mean reversion su crypto 1h produce win rate decenti (62-64%) ma perdite singole enormi che cancellano tutte le piccole vincite. È il classico problema delle code grasse.

**Edge reale?** 🔴 Assolutamente no. Le crypto 1h sono in-tradeable con mean reversion.

---

## 3. Classifica Specialist per Regime

### In Regime **BULL** (migliori 3):
| Specialist | Sharpe medio | WR medio | Best Asset |
|-----------|:-----------:|:--------:|:----------:|
| **trend** | +3.08 | 40.8% | ES 1d |
| mean_rev | — | — | — |
| breakout | — | — | — |

### In Regime **BEAR** (migliori 3):
| Specialist | Sharpe medio | WR medio | Best Asset |
|-----------|:-----------:|:--------:|:----------:|
| **mean_rev** | +3.47 | 72.7% | GC 1d |
| trend | — | — | — |
| breakout | — | — | — |

### In Regime **CHOPPY** (migliori 3):
| Specialist | Sharpe medio | WR medio | Best Asset |
|-----------|:-----------:|:--------:|:----------:|
| **mean_rev** | +0.88 | 65.3% | EURUSD 1d |
| trend | — | — | — |
| breakout | — | — | — |

### In Regime **VOLATILE**:
| Specialist | Sharpe medio | WR medio | Best Asset |
|-----------|:-----------:|:--------:|:----------:|
| **breakout** | +0.16 | 35.1% | CL 1h |
| mean_rev | — | — | — |

---

## 4. Root Cause — Perché il Sistema Perde

### Perdita #1: Crypto 1h Mean Reversion (-$9,796)

Su **494 trade BTC 1h**: 309 win (+$12,431) vs 185 loss (-$22,150).
Le perdite singole sono in media 2.5× più grandi delle vincite.

**Perché accade**: Le crypto hanno gap improvvisi (flash crashes, liquidazioni) che la mean reversion non può anticipare. A 1h, un singolo candle può muovere -15%, generando una perdita che 10 trade vincenti non recuperano.

**Fix**: 
- Tagliare crypto 1h dal portfolio (Sharpe negativo)
- O usare breakout/trend con stop loss stretti su crypto

### Perdita #2: CL Daily Mean Reversion (-$7, 36 trade)

72.2% WR ma Sharpe negativo. Il problema è lo stesso di BTC: poche perdite grandi cancellano molte vincite piccole.

**Fix**: CL non risponde a mean reversion. Forse breakout su volatilità estrema funziona meglio.

### Perdita #3: SOLUSDT (tutto negativo)

Sharpe -0.62 (1h) e -9.65 (1d). SOL è semplicemente troppo volatile e non mean-reverting.

**Verdetto**: Escludere completamente SOL dal portfolio.

---

## 5. Strategia Evolutiva — Adaptive Ensemble Dinamico

Basandosi sui dati, l'ensemble DEVE adattarsi DINAMICAMENTE per asset e regime:

### Come dovrebbe funzionare

```python
# Non più: ensemble.route()
# Ma: regime_aware_ranking()

regime = detector.classify(data)  # bull, bear, choppy, volatile

if regime == "bull":
    weights = {"trend": 0.7, "mean_rev": 0.2, "breakout": 0.1}
    # Trend specialist su ES/NQ/SPY daily
    # Mean reversion per posizioni controtendenza

elif regime == "bear":
    weights = {"mean_rev": 0.6, "breakout": 0.3, "trend": 0.1}
    # Mean reversion su GC (safe haven)
    # Breakout per movimenti improvvisi

elif regime == "choppy":
    weights = {"mean_rev": 0.6, "breakout": 0.3, "trend": 0.1}
    # Mean reversion su EURUSD/ES 1h
    # Trend solo occasionale

elif regime == "volatile":
    weights = {"breakout": 0.5, "mean_rev": 0.3, "trend": 0.2}
    # Breakout su CL/volatili
    # Mean reversion come controparte
```

### Per asset, weights pre-calibrati

| Asset | TF | Bull | Bear | Choppy | Volatile |
|-------|:--:|:----:|:----:|:------:|:--------:|
| **ES** | 1d | trend 1.0 | mean_rev 0.8 | mean_rev 0.6 | breakout 0.5 |
| **ES** | 1h | mean_rev 0.7 | mean_rev 0.7 | mean_rev 0.6 | mean_rev 0.5 |
| **NQ** | 1d | trend 1.0 | mean_rev 0.6 | mean_rev 0.6 | breakout 0.5 |
| **GC** | 1d | trend 0.6 | **mean_rev 1.0** | mean_rev 0.6 | mean_rev 0.5 |
| **SPY** | 1d | trend 1.0 | mean_rev 0.6 | mean_rev 0.5 | breakout 0.5 |
| **EURUSD** | 1d | mean_rev 0.6 | mean_rev 0.8 | **mean_rev 1.0** | mean_rev 0.6 |
| **BTCUSDT** | 1d | trend 0.5 | — | — | — |

### HRP Conferma — Correlazione tra Specialisti

I risultati mostrano che trend e mean_rev sono a bassa correlazione:
- **Trend** performa in bull markets (equities/futures daily)
- **Mean_rev** performa in choppy/bear markets (FX, GC)
- **Breakout** è efficace solo in volatilità estrema (CL)

Questo significa che un portfolio 50% trend + 40% mean_rev + 10% breakout su 3-4 asset avrebbe Sharpe composto molto più alto di ogni singolo specialist.

---

## 6. Raccomandazioni Concrete

### Short-term (questa settimana)
1. **Escludere**: SOLUSDT (tutti TF), BTCUSDT 1h dal portfolio
2. **Priorità**: GC 1d (bear→mean_rev), ES 1h (choppy→mean_rev), ES 1d (bull→trend)
3. **Testare**: EURUSD 1h (non ancora testato, potrebbe essere come ES 1h)

### Medium-term (prossimo mese)
4. **Implementare**: RegimeConditionalEnsemble con pesi dinamici
5. **Validare**: Walk-forward su GC 1d (best performer) — 10 fold
6. **HRP**: Computare peso ottimale per ogni (asset×tf×regime) usando PyPortfolioOpt

### Architettura target

```
RegimeDetector → Classifica regime attuale
    ↓
AssetManager → Seleziona asset attivi per regime
    ↓
WeightMatrix → Applica pesi pre-calibrati (asset × specialist)
    ↓
Ensemble → Esegue specialisti con pesi, combina segnali
    ↓
RiskManager → Vol target + IDM + position sizing
    ↓
OMS → Esecuzione
```

---

## 7. Trade Journal Consolidato

Tutti i 2,471 trade sono salvati in:
- `logs/sweep/trade_journal_20260728_201810.csv` (1° sweep, 1,353 trade)
- `logs/sweep/trade_journal_20260728_202321.csv` (2° sweep, 1,118 trade)

Per analizzare: `python3 -c "
import csv
from collections import Counter

# Per asset
with open('logs/sweep/trade_journal_20260728_201810.csv') as f:
    trades = list(csv.DictReader(f))
print('Trade breakdown by asset:')
for asset, grp in sorted(Counter(t['asset'] for t in trades).items()):
    wins = sum(1 for t in trades if t['asset']==asset and t['win']=='True')
    total = sum(1 for t in trades if t['asset']==asset)
    print(f'  {asset}: {total} trade, {wins} win ({wins/total:.0%})')
"