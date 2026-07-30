# Sprint 1 Results — G6 Paper with AdaptiveEnsemble

> Data: 2026-07-30
> Eseguito: `run_g6_wp2_paper_sessions.py --sessions 30`
> Dati: ES 1d lake (6517 bars, 217/sessione)
> Ensemble: AdaptiveEnsemble con 72-dim ML classifier

## Risultati

| Metrica | Valore | Target | Esito |
|---------|--------|--------|-------|
| Pass rate | **10%** (3/30) | ≥90% | ❌ Peggio del 77% precedente |
| Mean Sharpe | **-1.0652** | ≥-0.5 | ❌ |
| Mean Max DD | **4.01%** | ≤3.0% | ❌ |

## Analisi

Tutti gli specialist hanno IC negativo o nullo su ES 1d con finestre 217 bar:
- trend: IC=+0.008 (neutro)
- mean_rev: IC=-0.091 (negativo) 
- breakout: IC=-0.220 (fortemente negativo)

Causa: i parametri default (EmaTrend fast=10 slow=30, RsiReversion period=14,
DonchianBreakout period=20) non sono calibrati per finestre lunghe su ES 1d.

## Prossimi passi

1. Shorter window (95 bar come M32a originale)
2. Specialist parameter sweep per ES 1d
3. O usare direttamente il RegimeAwareEnsemble (routing binario) 
   con finestre 95 bar che dava 77% — poi migliorare il regime detector
