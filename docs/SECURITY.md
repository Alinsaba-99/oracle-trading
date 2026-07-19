# Oracle Security Incident Runbook

## Threat Model Summary

| Plane | Threat | Mitigation |
|-------|--------|------------|
| **Data** | Data exfiltration | API RBAC, network segmentation, read-only keys |
| **LLM** | Prompt injection | LLM = consultant, mai execution authority |
| **Execution** | Unauthorized order | RiskManager obbligatorio, API RBAC, kill switch |
| **Credentials** | Key leak | gitleaks pre-commit, .env gitignored, rotation policy |

## Incident Response

### 1. Credential Leak
```bash
# 1. Revoke leaked key
export ORACLE_API_KEY="<new-key>"

# 2. Check git history for secrets
gitleaks detect --source . --config .gitleaks.toml -v

# 3. Rotate ALL credentials (see docs/CREDENTIALS.md)
python scripts/check_credentials.sh
```

### 2. Unauthorized Order Attempt
```bash
# 1. Block all new orders
export ORACLE_BLOCK_ORDERS=true

# 2. Check audit trail
python -c "
from core.audit import AuditTrail
audit = AuditTrail()
print(f'Chain valid: {audit.verify_chain()}')
"

# 3. Kill switch if needed
curl -X POST http://localhost:8000/api/v1/kill -H "X-API-Key: $ORACLE_API_KEY"
```

### 3. API Key Compromise
```bash
# 1. Rotate the compromised key
# 2. Check audit logs for suspicious activity
# 3. Review RBAC permissions and restrict if needed
```

### 4. Data Breach
```bash
# 1. Isolate the affected service
docker compose stop api

# 2. Preserve logs and audit trail
cp -r /var/log/oracle /var/log/oracle-incident-$(date +%Y%m%d)

# 3. Rotate all credentials
# 4. Restore from clean backup
```

## Prevention

- [x] gitleaks pre-commit hook
- [x] API RBAC (5 roles: readonly, research, operator, admin, emergency)
- [x] API fail-closed in production (no key = no startup)
- [x] Environment credential isolation (paper ≠ funded)
- [x] .env gitignored with 600 permissions
- [x] Dependency pinning via uv.lock
- [x] Container non-root user
- [x] Network segmentation (127.0.0.1 binding)
- [x] Immutable audit trail (SHA-256 chain)
- [ ] Container image scanning
- [ ] Signed config/rule artifacts
