# Lane B Composite — Qualificazione ADR-017 (BL-OPC-12)

**Generated**: 2026-09-03T09:55:13.655306+00:00
**Window**: 2020-01-01 → 2025-08-14 (bear: 2022-01-01 → 2022-12-31)
**n_trials (discovery sweep)**: 8 — documentato nello script

## Verdetto: **REJECTED**

| Gate | Valore | Soglia | Stato |
|---|---|---|:---:|
| Observed Sharpe (canonical) | 0.7938 | — | — |
| DSR | 0.9462102364804621 | ≥ 0.95 | ❌ |
| PSR | 0.9505358282632556 | ≥ 0.95 | ✅ |
| PBO | 0.5013986013986014 | < 0.5 | ❌ |
| CPCV OOS Sharpe median | 0.8141622306399715 | — | — |

## Motivi del rigetto

- DSR 0.9462 < 0.95 after correcting for 8 discovery trials
- PBO 0.5014 >= 0.5 (in-sample optimum likely OOS-mediocre)

## Bear market 2022 (separato)

```
{
  "n_bars": 247,
  "sharpe": 0.006937874007311494,
  "max_drawdown": 0.16331613876391962,
  "dsr": 0.48702959260607587,
  "psr": 0.49628916914034416,
  "cpcv_oos_median": 0.029719426851111876,
  "verdict": "REJECTED"
}
```

## Family summary

| Config | Sharpe | Total return | MaxDD |
|---|---|---|---|
| composite_default | 0.8018472233137239 | 89.1086% | 23.6798% |
| legacy_and | 0.25180486629025156 | 12.2622% | 32.4508% |
| composite_threshold_055 | 1.0988777533623073 | 156.3652% | 21.6714% |
| composite_threshold_070 | 0.9268896071525375 | 114.8326% | 25.8884% |
| composite_weights_50_30_20 | 0.8355906981451802 | 96.5128% | 25.0021% |
