# BL-708 — Edge Factory Sprint 1 Qualification Report

**Generated**: 2026-09-03T14:15:08.037358+00:00
**Framework**: Edge Research Factory · ADR-017 (DSR/PSR) · BL-706 (IC screen) · BL-707 (Haircut Sharpe).
**Reference**: `docs/plans/2026-08-21-edge-research-factory-design.md` §3 (Stage 1 corpus mining), §6 (qualification gauntlet), §8 (kill criteria).

## Top-line verdict

- **Trend CTA** (`trend_cta`) → **NO-GO** (slots: 0 IC-pass / 6 OK / 6 total; median haircut Sharpe 0.3329, median DSR 0.9989)
- **Value Composite** (`value_composite`) → **NO-GO** (slots: 0 IC-pass / 1 OK / 2 total; median haircut Sharpe 1.4683, median DSR 1.0000)
- **Reversion** (`reversion`) → **NO-GO** (slots: 5 IC-pass / 5 OK / 5 total; median haircut Sharpe -0.9125, median DSR 0.1359)
- **Crypto Carry** (`crypto_carry`) → **NO-GO** (slots: 0 IC-pass / 5 OK / 5 total; median haircut Sharpe 0.0321, median DSR 0.9609)

## Per-candidate qualification tables

### Trend CTA (`trend_cta`)

Long-horizon trend-following: close/SMA200 − 1 (BL-093 trend family).
Notes: Direction fixed (long-factor): negative-IC trends FAIL, no sign-flip.

**Verdict**: `NO_GO`

Reasons:
- only 0 slots pass the IC screen (kill criterion: >= 2 required)

| asset | tf | n_bars | n_pairs | IC | IC mean | ICIR raw | ICIR haircut | t-block | obs SR | haircut SR | PSR | DSR | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ES | 1d | 6545 | 6341 | ❌ | -0.3906 | -2.2941 | -1.6059 | -24.658 | 0.651 | 0.322 | 0.999 | 0.999 | OK |
| NQ | 1d | 6531 | 6327 | ❌ | -0.4240 | -2.4700 | -1.7290 | -25.794 | 0.674 | 0.344 | 1.000 | 1.000 | OK |
| CL | 1d | 6529 | 6325 | ❌ | -0.3675 | -1.8603 | -1.3022 | -19.464 | -0.006 | -0.335 | 0.487 | 0.487 | OK |
| GC | 1d | 6086 | 5882 | ❌ | -0.3731 | -2.2089 | -1.5462 | -23.176 | 0.912 | 0.569 | 1.000 | 1.000 | OK |
| BTCUSDT | 1d | 3305 | 3101 | ❌ | -0.3218 | -1.6369 | -1.1458 | -11.385 | 0.763 | 0.296 | 0.996 | 0.996 | OK |
| ETHUSDT | 1d | 3305 | 3101 | ❌ | -0.2960 | -1.5362 | -1.0753 | -14.225 | 0.835 | 0.365 | 0.998 | 0.998 | OK |

### Value Composite (`value_composite`)

Cross-sectional value proxy: rank(1/close) on a multi-asset universe; defers fundamental composite (BL-728 edgar_loader).
Registry backref: `01-fundamental/EF-001`
Notes: Price-value proxy: real fundamental composite (Novy-Marx + Piotroski + Sloan) is BL-728 work.  Sprint 1 exercises the cross-sectional factor pipeline end-to-end.

**Verdict**: `NO_GO`

Reasons:
- only 0 slots pass the IC screen (kill criterion: >= 2 required)

| asset | tf | n_bars | n_pairs | IC | IC mean | ICIR raw | ICIR haircut | t-block | obs SR | haircut SR | PSR | DSR | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| UNIVERSE | 1d | n/a | 6702 | ❌ | n/a | n/a | n/a | n/a | 1.809 | 1.468 | 1.000 | 1.000 | OK |
| UNIVERSE | 1h | n/a | 0 | ❌ | n/a | n/a | n/a | n/a | 0.000 | n/a | n/a | n/a | INSUFFICIENT_DATA |

### Reversion (`reversion`)

Short-horizon mean-reversion: − zscore(close, 20).
Notes: Direction fixed: positive-IC reversion expects long negative-z.

**Verdict**: `NO_GO`

Reasons:
- median haircut Sharpe -0.9124985284457103 not > 0.0
- median DSR 0.13585994424607611 < 0.5 after deflated-SR penalty

| asset | tf | n_bars | n_pairs | IC | IC mean | ICIR raw | ICIR haircut | t-block | obs SR | haircut SR | PSR | DSR | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ES | 1d | 6545 | 6521 | ✅ | 0.2042 | 1.1212 | 0.7849 | 9.948 | 0.099 | -0.225 | 0.692 | 0.692 | OK |
| BTCUSDT | 1d | 3305 | 3281 | ✅ | 0.1057 | 0.5897 | 0.4128 | 4.522 | -1.044 | -1.495 | 0.000 | 0.000 | OK |
| BTCUSDT | 1h | 79174 | 79131 | ✅ | 0.2997 | 1.0418 | 0.7293 | 37.822 | -0.366 | -0.912 | 0.136 | 0.136 | OK |
| ETHUSDT | 1d | 3305 | 3281 | ✅ | 0.1139 | 0.4777 | 0.3344 | 3.844 | -1.104 | -1.554 | 0.000 | 0.000 | OK |
| EURUSD | 1d | 7272 | 7248 | ✅ | 0.2107 | 1.0499 | 0.7349 | 11.194 | 0.534 | 0.225 | 0.998 | 0.998 | OK |

### Crypto Carry (`crypto_carry`)

Crypto funding-basis proxy: rolling-mean of 1h log-returns (Binance Vision funding lands via BL-718).
Registry backref: `crypto-microstructure/EF-007`
Notes: Real perp-basis funding lands with BL-718; Sprint 1 uses a direction proxy.

**Verdict**: `NO_GO`

Reasons:
- only 0 slots pass the IC screen (kill criterion: >= 2 required)

| asset | tf | n_bars | n_pairs | IC | IC mean | ICIR raw | ICIR haircut | t-block | obs SR | haircut SR | PSR | DSR | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 1d | 3305 | 3295 | ❌ | -0.0977 | -0.5371 | -0.3760 | -4.557 | 0.562 | 0.110 | 0.980 | 0.980 | OK |
| BTCUSDT | 1h | 79174 | 79126 | ❌ | -0.3758 | -1.1374 | -0.7962 | -39.510 | -0.079 | -0.626 | 0.406 | 0.406 | OK |
| ETHUSDT | 1d | 3305 | 3295 | ❌ | -0.0698 | -0.3274 | -0.2292 | -3.022 | 0.486 | 0.032 | 0.961 | 0.961 | OK |
| ETHUSDT | 1h | 79171 | 79123 | ❌ | -0.3764 | -1.1494 | -0.8046 | -37.562 | 0.302 | -0.245 | 0.818 | 0.818 | OK |
| SOLUSDT | 1d | 2215 | 2205 | ❌ | -0.0837 | -0.4402 | -0.3082 | -3.810 | 0.905 | 0.353 | 0.996 | 0.996 | OK |

## Thresholds (frozen)

- `icir_threshold`: 0.05
- `ic_block_t_threshold`: 2.5
- `ic_haircut_pct`: 30.0
- `haircut_sharpe_min`: 0.0
- `dsr_min`: 0.5
- `psr_min`: 0.5
