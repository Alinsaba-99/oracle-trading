# IBKR Paper Trading Setup — guida operatore (BL-097)

> **Data**: 2026-08-15
> **Scope**: istruzioni operative per ottenere dati IBKR paper trading (TWS Gateway, NON API key classica)

---

## TL;DR

**IBKR NON ha una "API key" classica** come SimFin o Polygon. Invece:

1. **Account IBKR paper trading** (gratis): apri da Account Management → Open Paper Trading Account
2. **TWS o IB Gateway software**: scarica, login con credenziali PAPER
3. **API settings su TWS**: Configure → API → Settings → "Enable ActiveX and Socket Clients" su porta 7497
4. **Oracle si connette via `ib_insync`** (già installato) a `localhost:7497`

Il login è interattivo (devi avere TWS aperto), NON c'è una chiave da mettere in `.env`.

## Setup step-by-step (~1h, una tantum)

### Step 1: Apri paper trading account

1. Vai su https://www.interactivebrokers.com/
2. Login con il tuo account IBKR (già esistente)
3. Vai su **Account Management** (icona in alto a destra)
4. Click **Settings** → **Paper Trading Account**
5. IBKR crea un account paper con credenziali separate (username + password diverso dal live)
6. Annotati username/password PAPER (NON quelli live)

### Step 2: Scarica TWS o IB Gateway

**IB Gateway** (consigliato per trading sistematico — più leggero):
1. https://www.interactivebrokers.com/en/index.php?f=5054
2. Scarica "IB Gateway Latest" per Linux/macOS/Windows
3. Installa

**OPPURE TWS** (più completo, ha anche grafici/UI):
1. https://www.interactivebrokers.com/en/index.php?f=1603
4. Scarica "TWS Latest"

### Step 3: Login con credenziali PAPER

1. Apri IB Gateway o TWS
2. Sotto "Authentication Type" → **Paper Trading**
3. Username = tuo paper username
4. Password = tua paper password
5. Click **Log In**
6. IBKR manda un'email "Paper trading login" per confermare (se 2FA attivo)

### Step 4: Abilita API su TWS

1. In TWS: **Configure** (menu) → **Settings** → **API** → **Settings**
2. Spunta **"Enable ActiveX and Socket Clients"**
3. Spunta **"Read-Only API"** (off se vuoi anche piazzare ordini via API; per dati storici lascia ON)
4. **Socket port** = `7497` (default per paper; 7496 per live)
5. Click **OK**

### Step 5: Avvia il gateway (Linux/macOS)

Oracle include uno script helper:

```bash
./scripts/start_ibkr_gateway.sh
```

Verifica connessione:

```bash
.venv/bin/python scripts/metaapi_smoke.py  # se esiste
# oppure
.venv/bin/python -c "from ib_insync import IB; ib = IB(); ib.connect('127.0.0.1', 7497, clientId=1); print(ib.accountValues())"
```

Output atteso: connection OK + account values del paper account.

## Verifica IBKR connection

Oracle ha un helper di smoke test:

```bash
.venv/bin/python scripts/metaapi_smoke.py
```

Se funziona, vedi:
- Account paper balance
- Posizioni open
- Download storico ES 1m (ultimo mese)

## Cosa sblocca IBKR paper trading

| Capabilities | Status pre-IBKR | Status post-IBKR |
|---|---|---|
| ES/NQ/GC/CL 1m futures 2010→ | ❌ (lake ha solo ~8 giorni) | ✅ (~4M barre 1m ES 2010-2025) |
| SPY/QQQ/DIA/IWM 1m equities 2000→ | ❌ | ✅ (~6M barre 1m SPY) |
| Single stocks 1m (AAPL, MSFT, INTC, AMD, NVDA, TSLA) | ❌ (lake daily only) | ✅ |
| Lane A validation su intraday 1h | ❌ | ✅ (target 1h invece di daily) |
| Lane C scalping intraday | ❌ | ✅ |
| Live paper trading (invio ordini) | ❌ (solo sim paper broker) | ✅ (paper con broker reale) |

## Quanto tempo ci vuole per il setup

| Step | Tempo |
|---|---|
| Aprire paper account | 5 min (se hai account IBKR live; altrimenti 1-2 giorni per verifiche KYC) |
| Scaricare IB Gateway | 10 min |
| Login + 2FA email | 5 min |
| Configurare API settings | 5 min |
| Smoke test Oracle | 5 min |
| **Totale** | **~30 min** (se account live esiste) |

## Troubleshooting

### Errore "Connection refused on port 7497"

- TWS non sta runnando → aprilo e fai login
- API non abilitato → Configure → API → Settings → Enable ActiveX
- Porta sbagliata → controlla 7497 (paper) vs 7496 (live)
- Firewall Linux → `sudo ufw allow 7497/tcp`

### Errore "ClientId already in use"

Hai già un altro client IB collegato. Cambia `clientId`:

```bash
IBKR_TWS_CLIENT_ID=oracle-paper-2 .venv/bin/python scripts/metaapi_smoke.py
```

### Errore "Market data farm connection failed"

IBKR paper account non ha subscription per i dati. Per paper trading:
- Free: US equities snapshot (real-time)
- $1.50/mo: US Securities Snapshot Bundle (real-time OPRA)
- $10/mo: CME/CBOT Futures (real-time, includes Globex)
- Free: CME futures 1m history dal 2018 (10 min delayed)

Per **backtest** il dato delayed è sufficiente. Per **live trading** serve la subscription.

## Alternativa: Databento (BL-098)

Se non vuoi setup IBKR, alternativa è Databento free tier:

1. Vai su https://databento.com/
2. Registrati (gratis, 1GB/mese free)
3. Vai su **Account → API Keys** → copy your `DATABENTO_API_KEY`
4. Export in `.env`:
   ```
   DATABENTO_API_KEY=your_key_here
   ```

Databento offre:
- CME futures 1m 2018→ (~2 mesi di 1m ES al mese con 1GB free)
- Più robusto via API rispetto a IBKR TWS (no TWS required)
- Limitato al 1GB/mese

## File di riferimento

- `scripts/start_ibkr_gateway.sh` — helper avvio gateway
- `scripts/metaapi_smoke.py` — smoke test connection
- `analytics/fundamental/simfin_loader.py` — esempio di bulk data loader (SimFin, non IBKR; per IBKR vedi `market/ingestion/sources.py::IBKRRestSource`)
- `docs/free-1m-data-strategy.md` — strategia multi-tier per dati 1m zero-cost

---

*Fine IBKR setup guide. ~30 min del tuo tempo per sbloccare ~4M barre 1m futures + 6M barre 1m equities.*
