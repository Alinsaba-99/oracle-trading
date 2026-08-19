# 01 Fundamental — Capability Map per Oracle

> Cosa costruire prima in Oracle (edge > 0.5 + free data + stack esistente), cosa deferrire, cosa è hard-blocked.

## ✅ Già in Oracle (validato 2026-08-17)

| Capability | File | Test | Backtest |
|---|---|---|---|
| Piotroski F-Score | `analytics/strategy/catalog/value.py:PiotroskiFScore` | `test_composite_lane_b.py` 21/21 | 2020-2025 +alpha |
| Greenblatt Magic Formula | `analytics/strategy/catalog/value.py:GreenblattMagicFormula` | same | same |
| Lakonishok Value Momentum | `analytics/strategy/catalog/value.py:LakonishokValueMomentum` | same | same |
| Composite Lane B score | `analytics/strategy/lane_b_backtester.py:CompositeLaneBScore` | same | **Sharpe 0.93, alpha +59%** |
| SimFin loader (185 tickers US) | `analytics/fundamental/simfin_loader.py` | live | 5y 2020-2025 |

Vedi memory `composite-lane-b-default-2026-08-17`.

## 🔨 P1 — Implementare prossimo (edge forte + free data + stack ready)

### BL-KB-01: SEC EDGAR adapter
- **Perché**: SimFin ha 185 tickers + 5y. EDGAR ha 6.000+ tickers US + 30y storia, illimitato free.
- **Cosa**: `analytics/fundamental/edgar_loader.py` con XBRL parser. Estrai:
  - 10-K/10-Q quarterly: revenue, COGS, operating income, net income, total assets, total equity, total debt, operating cash flow, capex, accruals, shares outstanding
  - 8-K earnings releases (per PEAD)
  - 13-F institutional holdings (per smart money positioning, vedi dominio 06)
- **Output**: same interface as `SimFinLoader` → drop-in replacement.
- **Tempo**: ~3-5 giorni incluso XBRL parser (libreria `python-edgar` o `sec-edgar-downloader` PyPI).
- **Costo**: $0.

### BL-KB-02: Altman Z-Score signal
- **Perché**: 72% bankruptcy accuracy, maintained 50y. Signal di distress risk.
- **Cosa**: `analytics/strategy/catalog/value.py:AltmanZScore` con formula 5-ratio.
- **Output**: score (distress < 1.81, safe > 3.0). Aggiungere a `CompositeLaneBScore` come negative signal (high Z = bonus, low Z = penalty).
- **Tempo**: ~1 giorno.
- **Costo**: $0.

### BL-KB-03: Sloan Accrual Anomaly
- **Perché**: edge persistente +1-2%/yr OOS. Complementare a F-Score (accruals = componente di F-Score ma Sloan lo estrae esplicito).
- **Cosa**: `analytics/strategy/catalog/value.py:AccrualAnomaly` con formula (income - CFO) / assets. Sort by accrual decile.
- **Output**: low accruals = good signal. Combo con CompositeLaneBScore.
- **Tempo**: ~1 giorno.

### BL-KB-04: PEAD signal
- **Perché**: post-earnings drift +2-3%/yr. Richiede earnings dates + surprise.
- **Cosa**: `analytics/strategy/catalog/value.py:PEADSignal` con:
  - Earnings surprise = (actual EPS - consensus) / std(EPS surprises)
  - Drift window: 60 giorni post-announcement
  - Long high-surprise + high-F-Score → max alpha
- **Data**: EDGAR 8-K + yfinance `tk.earnings_dates` (free, rate-limited).
- **Tempo**: ~3-5 giorni (richiede earnings calendar).

### BL-KB-05: Novy-Marx Gross Profitability
- **Perché**: gross profit / assets, robust OOS. Spiega ~50% di Buffett alpha (Frazzini-Kabiller-Pedersen 2018).
- **Cosa**: `analytics/strategy/catalog/value.py:NovyMarxGrossProfit` con formula.
- **Output**: high gross profitability = positive signal.
- **Tempo**: ~1 giorno.

## 🔨 P2 — Implementare per validazione G5

### BL-KB-06: Fama-French 5-factor regression
- **Perché**: per misurare alpha residuo di Lane B vs FF5F. DSR/PBO/CPCV (ADR-017).
- **Cosa**: `analytics/strategy/factor_regression.py` con:
  - Carica factor returns da Kenneth French data library (free, illimitato)
  - OLS regression: `Lane_B_returns - RF ~ Mkt-RF + SMB + HML + RMW + CMA`
  - Output: alpha (intercept) + t-stat + R²
- **Data**: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
- **Tempo**: ~2-3 giorni.
- **Costo**: $0.

### BL-KB-07: Shiller CAPE market timing
- **Perché**: 10y return predict, regime indicator. Non tradabile short-term ma useful per sizing.
- **Cosa**: `analytics/macro/cape_signal.py` con:
  - CAPE = price / 10y avg earnings (inflation-adjusted)
  - ECY = CAPE inverse - 10y Treasury yield
  - Output: market overvalued (CAPE > 35) / undervalued (CAPE < 15) / neutral
  - Size Lane B exposure: 0.5x quando overvalued, 1.5x quando undervalued
- **Data**: Shiller monthly data http://www.econ.yale.edu/~shiller/data.htm + yfinance SPY
- **Tempo**: ~2 giorni.

### BL-KB-08: Fundamental momentum (Chen-Lakonishok 2020)
- **Perché**: earnings + revenue momentum, complementare a price momentum (BL-505d).
- **Cosa**: `analytics/strategy/catalog/momentum.py:FundamentalMomentum` con:
  - Earnings momentum = ΔEPS YoY + Δrevenue YoY
  - Sort by composite, top decile vs bottom decile
  - Combo con price momentum in `CompositeMomentumSignal`
- **Data**: SimFin/EDGAR quarterly statements.
- **Tempo**: ~2-3 giorni.

## 🔄 P3 — Deferrire a dominio successivo

- **52-week high** (George-Hwang 2004) → più appropriato in dominio 01 (TA price) o dominio 09 (cyclical). Ti-noto per P3 nel dominio corretto.
- **Buffett alpha decomposition** → gi studiato in `lane-b-aggressive-sharpe-149` memory (Sharpe 1.49 con stop-loss 5% + vol target 40% = similar mechanism).

## ❌ Hard-blocked (paywalled)

- **Sell-side analyst EPS estimates** (Refinitiv, Bloomberg, Zacks) → non free, PEAD approximato con yfinance `tk.earnings_dates` (free, dati storici limitati).
- **13-F institutional holdings real-time** — EDGAR ha 13-F quarterly (45-day delay free, OK).
- **SEC enforcement actions** → EDGAR AAER (Accounting and Auditing Enforcement Releases) free, integrabile per distress risk.

## Sequenza di implementazione raccomandata

```
BL-KB-02 Altman Z-Score       (~1g)  ← semplice, edge forte
BL-KB-05 Novy-Marx GP         (~1g)  ← semplice, spiega Buffett
BL-KB-03 Accrual anomaly      (~1g)  ← semplice, complementare
BL-KB-01 SEC EDGAR adapter    (~3-5g) ← unlock 30y + 6000 tickers
BL-KB-06 FF5F regression      (~2-3g) ← ADR-017 G5 gate
BL-KB-07 Shiller CAPE         (~2g)  ← market sizing overlay
BL-KB-08 Fundamental momentum (~2-3g) ← combo con price momentum
BL-KB-04 PEAD signal          (~3-5g) ← richiede earnings calendar
```

Totale: **~15-22 giorni di lavoro** per completare P1+P2 fundamental.

## Prossimo step

Dopo aver completato BL-KB-01..05, ri-run Lane B backtest 2020-2025 con:
- Dataset EDGAR (185→6.000 tickers, 5→30y storia)
- Signal aggiuntivi: Altman Z + Sloan accruals + Novy-Marx GP + PEAD + fundamental momentum
- FF5F regression per alpha decomposition
- DSR/PBO/CPCV per validazione G5

**Target**: Sharpe > 1.0 su 30y OOS (vs 0.93 attuale su 5y). Se confermato → promozione a paper trading live (Step 4 Opzione C followup).
