# Oracle Deployment Runbook

> Versione: 1.0 (2026-07-19)

## Stack

```
postgres:16-alpine   → Ledger/OMS authoritative store
redis:7-alpine       → Cache (non-authoritative, ricostruibile)
oracle-api           → FastAPI (control/read API)
oracle-dashboard     → React static (nginx)
oracle-scheduler     → Cron jobs (reconciliation, data refresh)
```

## Avvio

```bash
# Sviluppo
docker compose -f infra/docker/docker-compose.yml up -d

# Production
ORACLE_MODE=paper ORACLE_API_KEY=<key> docker compose -f infra/docker/docker-compose.yml up -d

# Logs
docker compose -f infra/docker/docker-compose.yml logs -f api

# Fermare
docker compose -f infra/docker/docker-compose.yml down
```

## Health Checks

| Servizio | Endpoint | Cosa verifica |
|----------|----------|---------------|
| postgres | `pg_isready` | DB accessibile |
| redis | `redis-cli ping` | Cache accessibile |
| api | `GET /api/health` | API e dipendenze |
| dashboard | `GET /` | Static assets |

## Incident Response

### API crash
```bash
docker compose restart api
docker compose logs api --tail=50
```

### Database corruption
```bash
# Stop all services
docker compose down
# Restore from backup
docker run --rm -v oracle_postgres_data:/data -v $(pwd)/backups:/backup alpine \
    tar xzf /backup/postgres-$(date +%Y%m%d).tar.gz -C /data
# Restart
docker compose up -d
```

### Ledger/OMS drift (reconciliation failure)
1. `docker compose logs scheduler` — verifica errori reconciliation
2. Fermare new order entry: `export ORACLE_BLOCK_ORDERS=true`
3. Run manual reconciliation: `uv run python -c "from core.reconciliation import ..."`
4. Risolvere mismatch, unblock: `export ORACLE_BLOCK_ORDERS=false`

### Kill switch (emergency flatten)
```bash
# Flatten all positions via API
curl -X POST http://localhost:8000/api/v1/kill \
    -H "X-API-Key: $ORACLE_API_KEY"
```

## Backup

```bash
# PostgreSQL backup
docker exec oracle-postgres pg_dump -U oracle oracle > backups/oracle-$(date +%Y%m%d).sql

# Restore
cat backups/oracle-20260719.sql | docker exec -i oracle-postgres psql -U oracle oracle
```
