# Lane B Composite — Qualificazione ADR-017 (BL-OPC-12)

**Generated**: 2026-08-20T07:57:06.708999+00:00
**Window**: 2020-01-01 → 2025-08-14 (bear: 2022-01-01 → 2022-12-31)
**n_trials (discovery sweep)**: 8 — documentato nello script

## Verdetto: **REJECTED**

| Gate | Valore | Soglia | Stato |
|---|---|---|:---:|
| Observed Sharpe (canonical) | 0.8999 | — | — |
| DSR | 0.9665092140631631 | ≥ 0.95 | ✅ |
| PSR | 0.9694877806912864 | ≥ 0.95 | ✅ |
| PBO | 0.635042735042735 | < 0.5 | ❌ |
| CPCV OOS Sharpe median | 1.0310028432649005 | — | — |

## Motivi del rigetto

- PBO 0.6350 >= 0.5 (in-sample optimum likely OOS-mediocre)

## Bear market 2022 (separato)

```
{
  "n_bars": 247,
  "sharpe": 0.04911189954796302,
  "max_drawdown": 0.1633161387639197,
  "dsr": 0.49683236197464553,
  "psr": 0.5063621571235797,
  "cpcv_oos_median": 0.10846120803807646,
  "verdict": "REJECTED"
}
```

## Family summary

| Config | Sharpe | Total return | MaxDD |
|---|---|---|---|
| composite_default | 0.907810127291212 | 110.2157% | 23.2303% |
| legacy_and | 0.25180486629025156 | 12.2622% | 32.4508% |
| composite_threshold_055 | 1.017493293854897 | 138.3545% | 23.2448% |
| composite_threshold_070 | 0.854986863222479 | 98.1570% | 25.7367% |
| composite_weights_50_30_20 | 0.926478851835618 | 112.6045% | 24.8505% |
