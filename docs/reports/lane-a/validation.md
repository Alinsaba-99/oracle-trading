# Lane A PAC Multi-Asset Validation (BL-503)
**Generated**: 2026-08-15
**Pipeline**: TrendSignalRule(fast=8, slow=32) → ForecastScale → VolatilityTarget(target=12%)
**Instruments**: ES, NQ, GC, CL, YM, ZN, EURUSD, GBPUSD

## Per-symbol results

| Symbol | Bars | Sharpe | Ann.Return | Ann.Vol | MaxDD | DSR | PSR | PBO | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| ES | 6531 | 0.129 | 0.0% | 0.0% | 0.0% | 0.742 | 0.742 | 0.379 | **REJECTED** |
| NQ | 6517 | 0.176 | 0.0% | 0.0% | 0.0% | 0.812 | 0.812 | 0.066 | **REJECTED** |
| GC | 6072 | 0.272 | 0.0% | 0.0% | 0.0% | 0.907 | 0.907 | 0.500 | **REJECTED** |
| CL | 6515 | 0.141 | 0.0% | 0.3% | 0.9% | 0.765 | 0.766 | 0.725 | **REJECTED** |
| YM | 6103 | 0.022 | 0.0% | 0.0% | 0.0% | 0.542 | 0.542 | 0.728 | **REJECTED** |
| ZN | 6483 | 0.125 | 0.0% | 0.2% | 0.8% | 0.735 | 0.735 | 0.039 | **REJECTED** |
| EURUSD | 7272 | -0.364 | -6.2% | 14.7% | 85.9% | 0.022 | 0.026 | 0.776 | **REJECTED** |
| GBPUSD | 7271 | -0.233 | -4.5% | 15.0% | 79.8% | 0.094 | 0.107 | 0.751 | **REJECTED** |

## Portfolio aggregate (equal-weight + IDM)

- Instruments: 8
- Avg pairwise correlation: 0.005
- IDM (Instrument Diversification Multiplier): 2.776
- Portfolio Sharpe: -0.327
- Portfolio DSR: 0.055
- Portfolio PSR: 0.056
- Portfolio PBO: 0.106

**Verdict**: REJECTED

**Notes**: portfolio Sharpe -0.3265430505504312 < 0.5; DSR 0.05452393362731725 < 0.95; PBO 0.106 < 0.5

## Honest target assessment

Per the deep-research synthesis 2026-08-15 and ADR-016 (anti-beta):
- Target Sharpe: 0.7-1.0 (NOT 3-5 = Renaissance territory)
- DSR ≥ 0.95 (ADR-017)
- PBO < 0.5 (ADR-017)
- DD ≤ 4% (ADR-016 §4)

If PASSED: this Lane (Lane A PAC multi-asset) proceeds to BL-024 (G6 re-run) → G7 cert.
If REJECTED: pivot to Lane B (turnaround, BL-505/506) or option selling VRP (BL-507).
