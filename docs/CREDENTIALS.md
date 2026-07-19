# Credential Rotation & Management

> **Data:** 2026-07-19
> **Stato:** 🔴 CREDENZIALI ATTUALI DA ROTARE

## Credenziali da rotare

| Credenziale | Tipo | Stato | Azione |
|---|---|---|---|
| `METAAPI_TOKEN` | JWT (MetaApi cloud) | 🔴 **Da rotare** | Rigenerare su https://app.metaapi.cloud/token |
| `LLM_KEY` | API key (OpenAI-compatible) | 🔴 **Da rotare** | Rigenerare su dashboard del provider LLM |

## Procedura di rotazione

### 1. MetaApi Token

1. Vai su https://app.metaapi.cloud/token
2. Revoca il token corrente
3. Genera un nuovo token
4. Aggiorna `.env`: `METAAPI_TOKEN=<nuovo_token>`
5. Verifica: `curl -H "auth-token: $METAAPI_TOKEN" https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/current`

### 2. LLM Key

1. Vai sul dashboard del provider LLM (es. https://platform.openai.com/api-keys)
2. Revoca la key corrente
3. Genera una nuova key
4. Aggiorna `.env`: `LLM_KEY=<nuova_key>`

## Verifica post-rotazione

```bash
# Verifica che .env sia gitignorato e con permessi corretti
stat -c '%a' .env        # → 600
git check-ignore .env    # → .env

# Verifica che nessun secret sia finito in commit
gitleaks detect --source . --config .gitleaks.toml -v

# Verifica che il sistema fallisca gracefulmente senza credenziali
ORACLE_API_KEY="" uv run --frozen python -c "from apps.api.main import settings" 2>&1
# → deve fallire con: FATAL: ORACLE_API_KEY is required in production mode
```

## Guards implementati

- [x] `.env` in `.gitignore` (600 permessi)
- [x] `gitleaks` hook in pre-commit (blocca commit con secret)
- [x] `gitleaks` job in CI
- [x] `.env.example` come template (senza valori reali)
- [x] API fail-closed in produzione (G0 P0.2)
- [x] Warning startup quando `ORACLE_API_KEY` è vuota
