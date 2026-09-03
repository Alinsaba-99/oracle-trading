# Runbook — Paper Trading Stack (BL-729..737)

Operational guide for the always-on paper trading stack. Target reader:
an operator (or future you) who has never seen this repo and needs to
start, stop, monitor, and troubleshoot the paper runner using this
document alone.

## Architecture (one paragraph)

`scripts/run_paper.py` boots `execution/runner.PaperRunner`, a tick loop
that fetches prices (lake parquet), asks a signal source for order
intents (currently `NoopSignalSource` — the Lane B adapter ships in
BL-728), routes them through `PaperOrchestrator`/`PaperBroker`, and
persists everything to a durable SQLite store (BL-729, WAL mode,
idempotent fills). Alerts (fills, errors, kill-switch, stale heartbeat)
are emitted through the `alerting/` package (BL-733/734) — Telegram
and/or e-mail when credentials are set, logs otherwise. A tearsheet can
be rendered from the live store at any time (BL-735).

## Start / stop

```bash
# foreground smoke (2 cycles)
uv run python scripts/run_paper.py --config config/paper.yaml --db /tmp/paper.db --max-cycles 2

# as a systemd user service (recommended)
cp ops/systemd/oracle-paper.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now oracle-paper.service

systemctl --user stop oracle-paper.service      # graceful: finishes the current cycle
journalctl --user -u oracle-paper -f            # live logs
```

Exit code 2 means three consecutive cycle failures — systemd restarts
after 10s. Restarts are safe: fill ingestion is idempotent (dedupe on
`fill_id`), so a crash mid-cycle neither loses nor duplicates fills.

## IBKR 1m backfill timer (BL-731)

The runner reads prices from `data/lake/normalized`; going-forward data
is collected by `scripts/backfill_1m_ibkr_paper.py` (IBKR paper gateway,
port 4002, Read-Only). Install its hourly timer:

```bash
cp ops/systemd/oracle-backfill.service ops/systemd/oracle-backfill.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now oracle-backfill.timer
systemctl --user list-timers oracle-backfill.timer
```

`Persistent=true` catches up missed runs after downtime; the script's
7-day window makes re-runs idempotent.

## Configuration

`config/paper.yaml` — symbols, tick interval, store path, heartbeat
cadence. CLI flags override YAML. See the comments in the file.

## Monitoring

- **Heartbeat**: every `heartbeat_cycle_s` cycles the runner writes an
  audit `heartbeat` row; if the last one is older than
  `heartbeat_timeout_s` (default 900s), a `HEARTBEAT_MISSED` alert fires
  on the next cycle.
- **Alerts**: set `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` (and/or
  `EMAIL_*`) in the service environment to receive fill/error/kill-switch
  notifications. Without credentials the stack degrades to logs — it
  never crashes for lack of a channel (fail-open).
- **Store stats**: `scripts/paper_report.py --db data/paper/paper.db`
  prints fills/orders/equity/heartbeat and writes
  `docs/reports/paper/paper_tearsheet.html`.

## Troubleshooting

| Symptom | Check | Fix |
|---|---|---|
| Missing prices in audit log | lake parquet for symbol exists? backfill timer firing? | check `systemctl --user list-timers`, run backfill script manually |
| Service restarts repeatedly (exit 2) | `journalctl --user -u oracle-paper` | three cycle failures — usually a missing/corrupt lake path or store lock |
| No alerts | env credentials set? | channels auto-disable with a warning in the log at startup |
| Store locked | another runner instance running? | one runner per db_path; check `systemctl --user status oracle-paper` |

## Safety invariants

- The paper runner never places real orders: `PaperBroker` only.
- Kill-switch: 3 consecutive cycle failures stop the runner with exit 2
  and emit a CRITICAL alert; systemd restart is bounded by backoff.
- The store is the source of truth: positions are mirrored from broker
  state every cycle, so the DB cannot drift after a restart.

## Promotion gate

The default signal source is a no-op on purpose. Promoting a strategy to
paper (BL-732) requires an APPROVED qualification verdict (BL-727,
gauntlet ADR-017 against the pre-registered variant BL-726 — see
`docs/research/prereg/BL-726-lane-b-composite-variant.md`).
