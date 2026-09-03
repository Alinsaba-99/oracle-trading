# BL-718 — Edge Factory Sprint 2 (real funding factors) Qualification Report

**Generated**: 2026-09-03T21:03:10.308407+00:00
**Framework**: Edge Research Factory · ADR-017 (DSR/PSR) · BL-706 (IC screen) · BL-707 (Haircut Sharpe).

## Top-line verdict

- **Funding Extremum Reversal** (`funding_extremum_reversal`) → **NO_GO** (slots: 2 IC-pass / 3 OK / 3 total; median haircut Sharpe -2.5884, median DSR 0.0002)
- **Funding Z (continuous)** (`funding_z_feature`) → **GO** (slots: 2 IC-pass / 3 OK / 3 total; median haircut Sharpe 0.6448, median DSR 0.9963)

## Per-slot tables

### funding_extremum_reversal

| asset | tf | n_bars | n_pairs | IC | ICIR haircut | t-block | obs SR | haircut SR | DSR | status |
|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 1h | 23433 | 23409 | ❌ +0.0066 | +0.0148 | +0.24 | -2.077 | -3.053 | 0.0002 | OK |
| ETHUSDT | 1h | 54825 | 54801 | ✅ +0.0754 | +0.1588 | +4.39 | -0.500 | -1.156 | 0.1022 | OK |
| SOLUSDT | 1h | 52316 | 52292 | ✅ +0.0538 | +0.1184 | +3.14 | -1.928 | -2.588 | 0.0000 | OK |

### funding_z_feature

| asset | tf | n_bars | n_pairs | IC | ICIR haircut | t-block | obs SR | haircut SR | DSR | status |
|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 1h | 23433 | 23320 | ❌ +0.0151 | +0.0283 | +0.85 | +1.654 | +0.645 | 0.9963 | OK |
| ETHUSDT | 1h | 54825 | 54193 | ✅ +0.0987 | +0.1752 | +6.94 | +4.703 | +4.037 | 1.0000 | OK |
| SOLUSDT | 1h | 52316 | 52008 | ✅ +0.0407 | +0.0737 | +2.75 | -0.541 | -1.215 | 0.0819 | OK |


## Thresholds (frozen)

- `icir_haircut_min`: 0.05
- `ic_block_t_min`: 2.5
- `haircut_pct`: 30.0
- `haircut_sharpe_min`: 0.0
- `dsr_min`: 0.5
- `kill_min_passing_slots`: 2
