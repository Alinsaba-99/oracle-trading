# Oracle — Operational Runbook (paper mode, 2026-07-25)

> Operatività developer + paper. **NON copre live/funded.** Per quelli serve
> passare da `RESEARCH_ONLY` a `AUTO_SUPPORTED` con G7 PASSED (vedi
> [ROADMAP.md §G7](../ROADMAP.md) e [BACKLOG.md BL-100](../BACKLOG.md)).
>
> Stato corrente: PAPER parziale (gate rejected — vedi
> [STATUS §3](ORACLE_AUTOPILOT_STATUS.md)). Questo runbook descrive le
> operazioni che puoi fare OGGI senza violare la policy.

## Modalità autorizzate oggi

| Modalità | Comando | Cosa fa | Limite |
|---|---|---|---|
| `RESEARCH` | default | Legge/esegue backtest discovery | niente live |
| `REPLAY` | `ORACLE_MODE=replay` | Esegue replay storico deterministico | niente live |
| `PAPER` (parziale) | `ORACLE_MODE=paper` | Esegue sessioni paper su PaperBroker | gate rejected per regime choppy-biased — vedi [BL-020](../BACKLOG.md) |

## Sviluppo quotidiano

```bash
# 1. Sync dipendenze
uv sync --frozen --all-extras --all-groups

# 2. Baseline verde
make lint                # ruff
make typecheck           # mypy --strict
make test-fast           # pytest -m "not slow"

# 3. Sotto test pieno (slow)
make test                # pytest

# 4. Smoke regime→paper→OMS→reconcile
.venv/bin/python scripts/run_regime_paper_smoke.py
```

## Paper trading

> Stato corrente: G6-WP2 REJECTED, l'ultimo log è `logs/g6_wp2_paper_sessions.json`.
> Prima di rilanciare: BL-001..003 + BL-010..014.

```bash
# Storage in-memory (default — veloce, per dev)
.venv/bin/python scripts/run_g6_wp2_paper_sessions.py \
    --sessions 30 \
    --data data/ohlcv/ES_1d.parquet \
    --storage memory \
    --output logs/g6_wp2_paper_sessions.json

# Storage Postgres (path production, richiede db schema applicato)
.venv/bin/python scripts/run_g6_wp2_paper_sessions.py \
    --sessions 30 \
    --data data/ohlcv/ES_1d.parquet \
    --storage postgres \
    --dsn postgresql://oracle:oracle@localhost:5432/oracle

# Output atteso: media pass_rate, mean_sharpe, mean_max_dd + verdict REJECTED/PASS
```

## Postgress / OMS / ledger

> Setup iniziale (`db/schema.sql` esiste; vedi [commit `ffe91b4`](../../log/)).

```bash
# 1. Verifica db
psql -U oracle -d oracle -c '\dt'
# atteso: accounts, orders, fills, positions, outbox, account_snapshots, schema_migrations

# 2. Recovery dopo restart
.venv/bin/python -m apps.cli.main trade recover --storage postgres

# 3. Reconciliation periodico (manuale)
.venv/bin/python -m apps.cli.main trade reconcile --storage postgres

# 4. CLI paper orders (esempio)
ORACLE_MODE=paper .venv/bin/python -m apps.cli.main \
    trade submit --instrument ES --side buy --quantity 1 --storage memory
```

## Dataset pinning (BL-001..003 in corso)

```bash
# Calcola hash corrente
sha256sum data/ohlcv/ES_1d.parquet
# Atteso: 09a22268d2a7fa815beed6788917663771c7af7b347b7b49db6c2a1318f26b42  (M31 provenance)

# Se hai sovrascritto per errore:
git show 8708d74:data/ohlcv/ES_1d.parquet > data/ohlcv/ES_1d.parquet

# Future-proof (BL-001):
cp data/ohlcv/ES_1d.parquet data/pinned/ES_1d_m31.parquet
```

## Refresh giornaliero data lake (BL-304)

Il data lake si aggiorna da solo: timer systemd utente, ogni giorno alle
07:00 local, con `Persistent=true` (recupera il run se il PC era spento).

```bash
# Stato timer
systemctl --user list-timers oracle-lake-refresh.timer

# Run manuale (stesso percorso del timer)
cd ~/_repos/oracle-trading && uv run python scripts/refresh_lake.py

# Log dell'ultimo run
journalctl --user -u oracle-lake-refresh.service -n 50 --no-pager
```

Cosa fa `scripts/refresh_lake.py`:
1. `run-plan` incrementale — riprende da `data/lake/metadata/ingestion_state.json`,
   scarica solo i giorni mancanti (coverage `latest` → oggi), salta le entry già
   fresche; i fallimenti (es. ibkr/databento senza credenziali) finiscono in
   `failed` senza bloccare il resto.
2. Ricostruzione `curated/` — consolida le partizioni Hive in
   `data/lake/curated/<SYMBOL>_<TF>.parquet` (default: 1m, 1h, 1d).

Unit file: `~/.config/systemd/user/oracle-lake-refresh.{service,timer}`
(template nel repo: `scripts/systemd/`).

### Pitfall memoria: backfill 1m storia intera (OOM-kill)

Il fetch 1m dell'intera storia di un simbolo (2003→oggi, ~7.2M barre) tiene
in RAM ~8GB (oggetti bar + Decimal + DataFrame polars). Su macchine con
altri workload residenti può innescare l'OOM-killer (verificato 31-lug:
`global_oom`, processo killato a 7.9GB anon-rss). Workaround: fetch in chunk
annuali, ~250MB di picco per anno:

```bash
for y in $(seq 2004 2026); do
  uv run python -m market.ingestion.cli fetch SYMBOL 1m dukascopy \
    --start "$y-01-01" --end "$y-12-31"
done
```

Idempotente e riprendibile (merge + dedupe sulle partizioni). Il refresh
incrementale quotidiano non ha questo problema (scarica solo pochi giorni).

## Incident response (research/paper)

### Regime detector choppy-biased

`mean_rev` vince nel 96% delle sessioni? → calibra le soglie di
`_sma_regime_heuristic` (vedi [BL-010..014](../BACKLOG.md)). Workaround
temporaneo: abbassare `min_confidence` dell'ensemble a 0.3 per aumentare la
frequenza dei cambi specialist.

### OrderManager senza risk_manager

Appare un `_AllowAll` invece di `PropFirmOrderRiskAdapter` in
`scripts/run_g6_wp2_paper_sessions.py`? → fix BL-070.

### Test rossi dopo un merge

```bash
make test 2>&1 | tee logs/test_$(date +%Y%m%d).log
```

## Reference

- [BACKLOG.md](../BACKLOG.md) — task atomiche
- [STATUS.md](ORACLE_AUTOPILOT_STATUS.md) — gate status e rischi residui
- [AUDIT_FINDINGS.md](AUDIT_FINDINGS.md) — gap secco
- [ARCHITECTURE.md](ARCHITECTURE.md) — architettura e confini
- `logs/` — output di tutti gli script paper, smoke, run
- `docs/ADR/` — decisioni normative
