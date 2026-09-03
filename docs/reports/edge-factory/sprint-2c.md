# Sprint 2c — Trading-strategy qualification (funding-z & basis, sized + costs)

**Generated**: 2026-09-03T21:40:18.935353+00:00

Costs: 10 bps per unit turnover; position = clip(z/2, ±2) × vol scalar (target 20%).
Test window: > 2022-12-31 (walk-forward).

| strategy | asset | SR | ann ret | MaxDD | trades | cost/yr | P(m≥5%) | months |
|---|---|---|---|---|---|---|---|---|
| funding_z_sized | ETHUSDT | +0.51 | +4.1% | 20.5% | 512 | 2.17% | 5.3% | 76 |
| funding_z_sized | XRPUSDT | -0.63 | -6.0% | 27.7% | 430 | 1.84% | 1.3% | 76 |
| funding_z_sized | ADAUSDT | -0.90 | -9.1% | 34.6% | 330 | 1.40% | 2.6% | 76 |
| basis_carry | ETHUSDT | -0.17 | -2.2% | 26.1% | 221 | 0.57% | 1.8% | 110 |
| basis_carry | BTCUSDT | +0.19 | +1.3% | 18.8% | 410 | 1.15% | 2.7% | 110 |
| portfolio | MULTI | -0.35 | -2.2% | 16.2% | 0 | 0.00% | 0.0% | 110 |
