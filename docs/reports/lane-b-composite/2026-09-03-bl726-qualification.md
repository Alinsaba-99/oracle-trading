# BL-727 — Pre-Registered Qualification Report

**Generated**: 2026-09-03T11:23:13.591177+00:00
**Manifest**: `BL-726` (lane_b_composite_aggressive)
**Pinned commit**: `7f4058a44e63a4c0740d1c6d0006224f503cc332`
**Actual HEAD**:  `7f4058a44e63a4c0740d1c6d0006224f503cc332`
**Tree-integrity check**: FAIL (HEAD drift)
**Sample window**: 2020-01-01 → 2025-08-14
**Bear subwindow**: 2022-01-01 -> 2022-12-31

## Verdict

## **REJECTED_TREE_INTEGRITY**

### Reasons

- Tree-integrity gate failed: HEAD 7f4058a44e63a4c0740d1c6d0006224f503cc332 != pinned 7f4058a44e63a4c0740d1c6d0006224f503cc332
- IC screen (pre-registered) 0.0000 failed (ICIR haircut=-0.1543, t=-1.7094)

## Gate table — qualification window

| Gate | Observed | Threshold | Direction | Status |
|---|---|---|---|:---:|
| DSR | 0.9991 | 0.9500 | ≥ | ✅ |
| PSR | 0.9991 | 0.9500 | ≥ | ✅ |
| PBO | n/a | 0.2000 | ≤ | ✅ |
| CPCV OOS Sharpe median | 1.4597 | 0.5000 | ≥ | ✅ |
| Haircut Sharpe | 0.6727 | 0.5000 | ≥ | ✅ |
| Bear 2022 Sharpe | 1.2070 | 0.0000 | ≥ | ✅ |
| IC screen (pre-registered) | 0.0000 | 1.0000 | = | ❌ |

## Headline metrics

- **Observed Sharpe (canonical)**: 1.4294
- **Total return**: 115.65%
- **Annual return**: 19.68%
- **Max drawdown**: 11.73%
- **PSR**: 0.9991
- **DSR (n_trials=1)**: 0.9991
- **CPCV OOS Sharpe median**: 1.4597
- **Haircut Sharpe**: 0.6727
- **n_bars**: 1078

## Bear 2022 subwindow (secondary gate)

- **Observed Sharpe**: 1.2070
- **Max drawdown**: 11.73%
- **PSR**: 0.9002
- **DSR**: 0.9002
- **CPCV OOS Sharpe median**: 1.3376
- **n_bars**: 251

## Pre-registered IC screen (BL-706)

- **n_windows**: 17
- **IC mean**: -0.0322
- **IC std**: 0.1463
- **ICIR (raw)**: -0.2205
- **ICIR (after 30% haircut)**: -0.1543
- **Block-bootstrap t**: -1.7094
- **Passes**: NO

**Methodology caveat**: the IC screen above is run with the portfolio's own
daily returns as the factor proxy and the equity curve as the price series.
This is a best-effort serialised IC test (autocorrelation-style); the canonical
BL-706 screen is designed for cross-sectional factor-vs-forward-return tests on
a single (factor, prices) pair per hypothesis. A per-rebalance composite-score
series would be the proper input — that requires extending
`LaneBBacktestResult` with the per-rebalance composite series, which we
deliberately avoided here so we do not diverge from the manifest's pinned code
commit. IC verdict in this report is **methodology-limited**, not a hard gate.

## Anti-HARKing clause

All thresholds in the BL-726 manifest were fixed before this run; this report does not modify the manifest.  Per §7 of `docs/research/prereg/BL-726-lane-b-composite-variant.md`, the only acceptable post-result action is to declare the variant `REJECTED` and re-open BL-726 with a new manifest version.
