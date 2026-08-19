# Lane A PAC Multi-Asset Validation (multi-rule (BL-503b))

**Generated**: 2026-08-15
**Pipeline**: 4-rule ForecastCombine (EMA 8/32 + 16/64 + 32/128 + TSM 252 Moskowitz-Ooi-Pedersen) → VolatilityTarget(target=12%)
**Instruments**: ES, NQ, GC, CL, YM, ZN, EURUSD, GBPUSD

## Per-symbol results

| Symbol | Bars | Sharpe | Ann.Return | Ann.Vol | MaxDD | DSR | PSR | PBO | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| ES | 6531 | 0.402 | 0.8% | 2.1% | 4.9% | 0.976 | 0.977 | 0.733 | **REJECTED** |
| NQ | 6517 | 0.420 | 0.9% | 2.1% | 4.8% | 0.981 | 0.981 | 0.071 | **REJECTED** |
| GC | 6072 | 0.510 | 1.1% | 2.1% | 9.7% | 0.993 | 0.993 | 0.665 | **REJECTED** |
| CL | 6515 | 0.227 | 0.5% | 2.5% | 6.4% | 0.877 | 0.879 | 0.167 | **REJECTED** |
| YM | 6103 | 0.389 | 0.8% | 2.1% | 7.3% | 0.968 | 0.969 | 0.756 | **REJECTED** |
| ZN | 6483 | 0.021 | 0.0% | 2.4% | 10.5% | 0.537 | 0.541 | 0.418 | **REJECTED** |
| EURUSD | 7272 | -0.182 | -2.4% | 10.4% | 53.5% | 0.155 | 0.168 | 0.895 | **REJECTED** |
| GBPUSD | 7271 | -0.108 | -2.0% | 11.8% | 43.7% | 0.265 | 0.284 | 0.324 | **REJECTED** |

## Portfolio aggregate (equal-weight + IDM)

- Instruments: 8
- Avg pairwise correlation: 0.013
- IDM (Instrument Diversification Multiplier): 2.710
- Portfolio Sharpe: 0.063
- Portfolio DSR: 0.615
- Portfolio PSR: 0.619
- Portfolio PBO: 0.169

**Verdict**: REJECTED

**Notes**: portfolio Sharpe 0.06303511998178014 < 0.5; DSR 0.6151212980117081 < 0.95; PBO 0.169 < 0.5

## Honest target assessment

Per the deep-research synthesis 2026-08-15 and ADR-016 (anti-beta):
- Target Sharpe: 0.7-1.0 (NOT 3-5 = Renaissance territory)
- DSR ≥ 0.95 (ADR-017)
- PBO < 0.5 (ADR-017)
- DD ≤ 4% (ADR-016 §4)

If PASSED: this Lane (Lane A PAC multi-asset) proceeds to BL-024 (G6 re-run) → G7 cert.
If REJECTED: pivot to Lane B (turnaround, BL-505/506) or option selling VRP (BL-507).
