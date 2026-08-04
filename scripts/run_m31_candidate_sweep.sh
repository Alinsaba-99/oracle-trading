#!/usr/bin/env bash
# BL-023 Fase 5 (opzione A): qualifica i candidati segnale del probe nel
# gate ufficiale ADR-016 con N onesto (top-3 finestre per regime, default
# del runner). Ogni candidato produce docs/reports/candidates/<signal>.{json,md}.
#
# I segnali e i parametri sono identici a scripts/probe_signal_candidates.py
# (derivazione train-pre-2023): il verdetto del gate si applica al segnale
# esatto che il probe ha chiamato VIABLE.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p docs/reports/candidates

for signal in \
    roc_momentum_12 \
    bollinger_reversion \
    donchian_breakout \
    rsi_reversion \
    ema_trend \
    zscore_reversion \
    keltner_reversion \
    trend_filtered_breakout; do
    echo "=== $signal ==="
    uv run --frozen python scripts/run_replay_qualification.py \
        --data-source lake --symbol ES --timeframe 1d \
        --window-bars 1000 --warmup-bars 200 \
        --stop-mode atr --atr-multiple 1.0 --atr-period 14 \
        --config config/qualification/m31.yaml \
        --macro-events data/macro/m31-events.json \
        --signal "$signal" \
        --json-output "docs/reports/candidates/$signal.json" \
        --markdown-output "docs/reports/candidates/$signal.md"
    echo "exit=$?"
done
echo "SWEEP DONE"
