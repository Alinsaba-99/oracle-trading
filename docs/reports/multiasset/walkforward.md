# Walk-forward multi-asset — family trend/breakout (BL-023 Fase 2)

- Metodo: multi-asset walk-forward, signal-level (long/flat, shift(1), no lookahead)
- Train cutoff: `2023-01-01T00:00:00` — test: `>= 2023-01-01 (walk-forward proxy of the M31 gate windows)`
- Regola verdetto: `edge confirmed = S_test>=0.3 AND luck_p<0.1 AND S_test>BH_S; survives = >=2/3 assets`
- Asset: ES, SPY, BTCUSDT — Segnali: donchian_breakout, trend_filtered_breakout, ema_trend

## Risultati per asset × segnale (test period)

| Asset | Segnale | S_test | alpha (annuo) | DD | hit | luck p | BH_S | esito |
|---|---|---|---|---|---|---|---|---|
| ES | donchian_breakout | +1.145 | +0.028 | 7.9% | 37% | 0.018 | +1.35 | ❌ non batte BH |
| ES | trend_filtered_breakout | +1.085 | +0.023 | 7.9% | 36% | 0.024 | +1.35 | ❌ non batte BH |
| ES | ema_trend | +1.232 | +0.024 | 8.9% | 46% | 0.006 | +1.35 | ❌ non batte BH |
| SPY | donchian_breakout | +1.320 | +0.040 | 7.7% | 41% | 0.010 | +1.40 | ❌ non batte BH |
| SPY | trend_filtered_breakout | +1.261 | +0.035 | 7.7% | 40% | 0.010 | +1.40 | ❌ non batte BH |
| SPY | ema_trend | +1.330 | +0.032 | 8.4% | 48% | 0.004 | +1.40 | ❌ non batte BH |
| BTCUSDT | donchian_breakout | +0.830 | +0.061 | 33.8% | 26% | 0.050 | +0.86 | ❌ non batte BH |
| BTCUSDT | trend_filtered_breakout | +0.740 | +0.044 | 29.6% | 21% | 0.072 | +0.86 | ❌ non batte BH |
| BTCUSDT | ema_trend | +0.790 | +0.041 | 40.4% | 30% | 0.056 | +0.86 | ❌ non batte BH |

## Verdetto multi-asset (sopravvive = ≥2/3 asset confermati)

- **donchian_breakout**: ❌ NON SOPRAVVIVE (0/3: nessuno) — mean S_test +1.099
- **trend_filtered_breakout**: ❌ NON SOPRAVVIVE (0/3: nessuno) — mean S_test +1.029
- **ema_trend**: ❌ NON SOPRAVVIVE (0/3: nessuno) — mean S_test +1.117

**Verdetto complessivo**: ❌ nessun segnale sopravvive fuori campione

> Nota anti-beta: un segnale quasi-sempre-long su mercato rialzista
> mostra Sharpe alto (beta). La conferma richiede S_test > Sharpe del
> buy&hold: l'alpha, non il beta.
