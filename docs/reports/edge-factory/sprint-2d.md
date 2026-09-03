# Sprint 2d — funding-z as conditioning feature (EF-006 APPROVED use)

**Generated**: 2026-09-03T21:53:50.317369+00:00

EMA(20/50) trend leg on 1h, vol-target 20%, taker 10bps/turnover, reband 0.25.
Conditioned: position scaled by 1 − clip(|funding_z|, 0, 2)/2 when crowding
 is against the trade.

| variant | asset | SR | ann ret | MaxDD | trades | P(m≥5%) |
|---|---|---|---|---|---|---|
| baseline | ETHUSDT | +0.51 | +9.4% | 25.9% | 1028 | 28.9% |
| conditioned | ETHUSDT | +0.46 | +6.6% | 26.3% | 1562 | 15.8% |
| baseline | BTCUSDT | -0.02 | -2.7% | 37.5% | 454 | 24.2% |
| conditioned | BTCUSDT | -0.52 | -10.1% | 43.8% | 887 | 15.2% |
