# ADR-022: MT5 Linux Bridge Architecture — $0 Zero-Cost Strategy (Wine + mt5linux)

**Data:** 2026-09-03
**Status:** ACCEPTED
**Deciders:** Alin (operator)
**Supersedes:** —
**Related:** ADR-013 (versioned prop-firm rule catalog), ADR-015 (Topstep automation policy),
ADR-020 (zero-cost data strategy), BL-722 (multi-firm governor), BL-723 (this spike),
BL-724 (macro calendar), BL-726..737 (paper stack); prop-firm decisioni D2 2026-08-22;
memoria `mt5-linux-execution-path`; `execution/brokers/metatrader.py` (scaffold + protocol).

## Context

Le firm target (FTMO, The5ers, Alpha Capital, E8, FundedNext) erogano il
loro conto funded su piattaforma **MetaTrader 5** (forex / metalli /
indici CFD), non su un broker IBKR/Binance-style con API pubblica. Oracle
deve parlare MT5 per eseguire ordini e leggere (balance, equity, margin,
positions) per il `PropFirmRiskGovernor` (BL-722) e per il flusso
end-to-end `BL-726..737`.

Lo scaffold è già in piedi:

- `execution/brokers/metatrader.py` definisce `MT5Client` Protocol +
  `MockMT5Client` (testabile oggi);
- `MetaTraderBroker` adatta `MT5Client` a `BrokerProtocol` con
  `SymbolMapper(suffix=<broker>)` per i suffissi firm-specific
  (`.r`, `.x`, `.m`, …);
- `metaapi_client.py` esiste già come implementazione del protocollo
  basata su `metaapi-cloud-sdk`.

Il problema residuo è il **backend** Linux per MT5. Il pacchetto
PyPI `MetaTrader5` è Windows-only (linka le DLL del terminale MT5). Tre
opzioni realistiche, con costi e trade-off molto diversi:

| Opzione | Costo | Latenza | Complessità |
|---|---|---|---|
| A. Wine + `mt5linux` + terminale MT5 in Wine | **$0** | ~5-20 ms overhead Wine | alta (Wine, RPyC bridge, terminale X11 headless) |
| B. MetaApi cloud (SaaS, REST/WebSocket) | $0 free tier / poi paid | ~50-150 ms round-trip | bassa |
| C. Windows VPS/container/VM self-hosted | $5-30/mo tipico | ~10-30 ms | media |

ADR-020 fissa il vincolo **$0/mo per dati e infrastruttura**. ADR-015
fissa i vincoli di residenzialità di TopstepX (no VPS). Lo stesso
operatore (vincolo $0 globale) e la decisione multi-firm D2 del
2026-08-22 (`propfirm-multifarm-decisions` memoria) hanno scelto
**Wine + mt5linux + conto demo forex gratuito come ponte MT5
universale**, con MetaApi solo come fallback.

Questo ADR codifica la scelta come norma architetturale, ne fissa i
confini operativi e i failure mode, e apre la strada alla Fase 5b
wiring (injection del client reale).

## Decision drivers

- **Hard constraint ADR-020**: $0/mo per dati E infrastruttura
  (l'operatore ha già il vincolo globale di costo);
- **Decisione D2 2026-08-22**: bridge MT5 unico come moltiplicatore
  multi-firm (FTMO + The5ers + Alpha + E8 + FundedNext = stesso codice,
  cambia solo `SymbolMapper(suffix=…)` e le credenziali);
- **Nessun conto prop-firm necessario in test**: qualsiasi broker
  forex MT5 (IC Markets, Pepperstone, Exness, FBS) offre un conto demo
  gratuito virtual-money-real-platform-real-history in 5 minuti;
- **Reversibilità**: il `MT5Client` Protocol + `MetaTraderBroker`
  significa che possiamo sostituire il backend in qualunque momento
  iniettando un client diverso — la scelta di oggi vincola solo il
  deploy, non il codice;
- **Residenzialità per le valutazioni**: alcune firm (TopstepX) vietano
  VPS, ma il deploy Wine gira sul **personal device** del trader —
  stesso vincolo di ADR-015 §"Local-only deployment";
- **Headless automation** (24/7 systemd service) richiede un display
  virtuale (xvfb) sotto Wine perché il terminale MT5 è una GUI Win32.

## Options considered

### Option A — Wine + `mt5linux` (DECISIONE)

Setup: pacchetto Wine (≥8.x, stable su CachyOS/Arch), `winetricks` per
i prerequisiti Windows (vcrun2019, corefonts), `xvfb` per il display
virtuale, installazione del terminale MT5 ufficiale in un prefisso
Wine (`~/.wine_mt5/drive_c/Program Files/MetaTrader 5/terminal64.exe`),
e `pip install mt5linux` (v1.0.3, Feb 2026, RPyC bridge). Da Python
Linux: `from mt5linux import MetaTrader5` — il pacchetto parla via RPyC
a `mt5linux.exe` che gira dentro Wine, il quale a sua volta carica le
DLL native MT5.

Pro:

- **$0 costo ricorrente** — Wine + MT5 + broker demo + `mt5linux` sono
  tutti gratis; rispetta ADR-020;
- **Nessun lock-in a SaaS** — i dati storici e le credenziali restano
  sul nostro hardware;
- **Coerente con ADR-015** — gira sul personal device, niente VPS;
- **Stesso protocollo del MetaApi cloud** — il codice applicativo
  (OMS, governor, signal source) non vede la differenza;
- **Reversibile** — basta iniettare `MetaApiClient` invece di
  `Mt5LinuxClient` e siamo sul cloud;
- **Latenza locale** — RPyC + named pipe Wine ≈ 5-20 ms round-trip
  per `order_send` / `positions_get`.

Contro:

- **Setup fragility** — Wine + MT5 + RPyC è una catena a tre anelli,
  ogni release Wine o MT5 può rompere la sequenza (es. Mt5linux ha
  una history di rotture su Wine 7.x → 8.x);
- **Footprint pesante** — Wine + terminale MT5 + RPyC ≈ 1.5-2.5 GB
  RAM a regime, non ideale su laptop con 8 GB;
- **Headless automation non banale** — `xvfb` deve partire prima del
  terminale MT5 e RPyC deve restare in ascolto;
- **Manutenzione** — aggiornamenti MT5 (mensili) richiedono re-test
  della sequenza `mt5linux` ↔ DLL;
- **Niente SL/TP server-side nativi per alcune firm** — alcune firm
  proppongono "virtual SL" lato server (FTMO): in quel caso l'OMS deve
  eseguire la protezione lato client (BL-722 governor).

Rischio: basso se teniamo il fallback MetaApi pronto e containerizzato.
Reversibilità: alta — il protocollo è già astratto.

### Option B — MetaApi cloud (SaaS)

Setup: account MetaApi.cloud, deploy del nostro account MT5
(credentials broker) sulla loro piattaforma, poi `pip install
metaapi-cloud-sdk` e consumiamo le quote / ordini via REST/WS.

Pro:

- **Setup minimo** — niente Wine, niente DLL, niente xvfb;
- **Stabile** — MetaApi gestisce le rotture Wine lato loro;
- **Multi-account facile** — uno SDK gestisce N account MT5 in
  parallelo, utile per multi-firm (D4: una strategia × N firm ×
  conti piccoli).

Contro:

- **Costo non-zero a regime** — il free tier copre lo sviluppo ma
  il pricing per produzione è per-account/mese. Viola ADR-020 a
  regime (anche se in dev/free tier è $0);
- **Latenza round-trip ~50-150 ms** via cloud REST/WS — misurabile
  per SL/TP veloci;
- **Lock-in al provider** — le credenziali MT5 vivono sul loro proxy,
  revocabili da MetaApi unilateralmente;
- **Dati positions/balance passano per un intermediario** — surface
  attack più ampia rispetto al locale.

Rischio: medio. È il fallback documentato (decisione D2). Lo
manteniamo come Option B.

### Option C — Windows VPS / container Windows

Setup: VM Windows o container `mcr.microsoft.com/windows` su un cloud
provider (Azure, AWS, Hetzner); installare MT5 lì; esporre un bridge
REST minimale che gira sul Windows.

Pro:

- **Stabile e "ufficiale"** — è come MetaApi ma self-hosted;
- **MT5 nativo Win32** — niente Wine.

Contro:

- **Costo mensile $5-30+** per VM/container;
- **Vincolo ADR-015 (residenzialità)** se la firm vieta VPS —
  inutilizzabile per TopstepX, dubbio per alcune altre;
- **Manutenzione OS Windows** mensile (patch, restart, update MT5);
- **Latenza WAN** verso la VM (dipende dalla regione).

Rischio: viola ADR-020 + ADR-015. Rifiutata come opzione primaria.

## Decision

**Adottiamo Option A — Wine + mt5linux + conto demo forex gratuito.**

Norma architetturale:

1. **Backend Linux MT5 canonico** = `mt5linux` v1.0.3 (Feb 2026) sopra
   Wine ≥ 8.x, display `xvfb`, terminale MT5 in prefisso Wine dedicato
   (`~/.wine_mt5/`). Nessun SaaS di default.
2. **Injection point**: `MetaTraderBroker` continua a consumare
   `MT5Client` Protocol (vedi `execution/brokers/metatrader.py`).
   `Mt5LinuxClient` (nuovo, BL-723 follow-up) inietta
   `mt5linux.MetaTrader5` nel costruttore. `MetaApiClient` resta nel
   codice come fallback Option B attivabile per env-var
   `ORACLE_MT5_BACKEND=metaapi`.
3. **Credenziali**: account demo broker forex MT5 (IC Markets /
   Pepperstone / Exness / FBS), creati in 5 minuti senza carta.
   Le credenziali prop-firm vere (FTMO, The5ers, Alpha, E8,
   FundedNext) si configurano solo dopo il gate BL-722 + BL-727.
4. **Residenzialità**: il deploy Wine gira sul **personal device**
   del trader. Nessun VPS per esecuzione reale, coerente con ADR-015.
5. **Headless automation**: `xvfb-run -a` wrapper intorno al terminale
   MT5 + RPyC bridge (`mt5linux` server). `x11vnc` opzionale per debug
   visuale quando il servizio gira.
6. **systemd unit**: `ops/systemd/oracle-mt5-bridge.{service, socket}`
   che lancia `xvfb-run mt5linux` come user service. Restart su exit
   non-zero con backoff esponenziale (5s → 60s).
7. **Monitoring**: heartbeat ogni 60s via RPyC `mt5.terminal_info()`;
   alerting su channel `alerting/` (BL-733/734) se il terminale non
   risponde in 5s o se `connected=False`.
8. **Free tier MetaApi documentato**: per scopo di smoke-test in
   ambiente CI (dove Wine non è disponibile), `MetaApiClient` resta
   il percorso — accettabile perché il free tier è $0 e non
   tocca dati di produzione.

## Consequences

### Positive

- **ADR-020 rispettato**: zero costo ricorrente, lago dati e bridge
  entrambi free;
- **ADR-015 rispettato**: deploy local-only, niente VPS;
- **Coerente con decisione multi-firm D2**: un solo bridge serve tutte
  le firm prop MT5, cambia solo `SymbolMapper(suffix=…)` + creds;
- **Testabilità preservata**: `MockMT5Client` continua a funzionare in
  CI senza Wine;
- **Reversibile**: passare a MetaApi = cambiare una env-var, non un
  design.

### Negative

- **Fragilità Wine**: un upgrade Wine o MT5 può rompere il bridge.
  Mitigazione: pinning versioni in `pyproject.toml [tool.mt5]`,
  snapshot del prefisso Wine funzionante in
  `infra/wine/mt5-snapshot-{wine,mt5,mt5linux}.txt`;
- **Headless automation**: `xvfb` aggiunge complessità al service
  manager. Mitigazione: script `scripts/mt5_bridge.sh` che incapsula
  `xvfb-run + mt5linux` e gestisce il lock file;
- **Footprint**: ~1.5-2.5 GB RAM. Mitigazione: il bridge gira solo
  durante le sessioni (no 24/7HFT) e sui timeframe Oracle (1m+,
  bar-close sufficient);
- **Tempo di spike non-zero**: la prima installazione Wine + MT5 +
  RPyC + xvfb richiede 2-4h di configurazione una tantum.

### Failure modes

| Failure | Detection | Mitigation |
|---|---|---|
| Wine non riesce ad avviare il terminale MT5 | exit code ≠ 0, alerting CRITICAL | restart systemd con backoff; alerting su Telegram/email |
| RPyC bridge muore | heartbeat mancato > 5 min | systemd restart + reconnect automatico |
| MT5 terminal crash (update MSVC redist, etc.) | exit code, log Wine | re-run `winetricks vcrun2019` + restart |
| xvfb muore | display `:99` unreachable | restart xvfb prima di MT5; wrapper `scripts/mt5_bridge.sh` |
| Account demo broker scade (30-90 giorni inattività) | login fallisce | policy: ruotare demo account ogni 60 giorni, doc in runbook |
| Firm rifiuta l'IP / device (residenzialità) | login fallisce su prop-firm | ADR-015 già impedisce scenario (no VPS) |

### Enforcement

- File `infra/wine/MT5_VERSION` + `WINE_VERSION` + `MT5LINUX_VERSION`
  pinnati in repo; bump = emendamento a questo ADR;
- `tests/unit/test_metatrader.py` continua a girare su `MockMT5Client`
  (CI verde senza Wine);
- `tests/integration/test_mt5_wine_smoke.py` (TODO, post-BL-723) —
  facoltativo, richiede Wine installato e gira solo in ambienti che lo
  dichiarano via marker pytest;
- Pre-commit hook: asserisce che `MetaApiClient` non venga importato
  da `execution/` se `ORACLE_MT5_BACKEND != 'metaapi'` (TODO);
- `docs/runbooks/mt5-linux-setup.md` (questo PR) è la reference
  operativa: ogni anomalia → runbook.

## Implementation guidelines

1. **Layout file**:
   - `execution/brokers/metatrader.py` — invariato (già contiene
     `MT5Client` Protocol + `MockMT5Client` + `MetaTraderBroker`);
   - `execution/brokers/mt5linux_client.py` — NUOVO (BL-723
     follow-up). Implementa `MT5Client` su `mt5linux.MetaTrader5`.
     Iniettato via costruttore;
   - `execution/brokers/metaapi_client.py` — invariato (fallback);
   - `scripts/mt5_bridge.sh` — wrapper `xvfb-run + mt5linux`
     (env-vars: `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`,
     `WINE_PREFIX`);
   - `ops/systemd/oracle-mt5-bridge.service` — user service
     `Type=simple`, `Restart=on-failure`, `RestartSec=5s`,
     `EnvironmentFile=$HOME/.config/oracle/mt5.env`;
   - `infra/wine/MT5_VERSION`, `WINE_VERSION`, `MT5LINUX_VERSION` —
     pin file;
   - `docs/runbooks/mt5-linux-setup.md` — questo PR.

2. **Configurazione env**:
   ```bash
   # ~/.config/oracle/mt5.env (chmod 600)
   ORACLE_MT5_BACKEND=mt5linux     # oppure 'metaapi' per fallback
   MT5_LOGIN=12345678
   MT5_PASSWORD=...
   MT5_SERVER=ICMarkets-Demo
   MT5_BROKER_SUFFIX=.r            # oppure '' o '.m' o '.x'
   WINE_PREFIX=$HOME/.wine_mt5
   ```

3. **Smoke test end-to-end**:
   ```python
   from mt5linux import MetaTrader5
   mt5 = MetaTrader5(host="127.0.0.1", port=18812)
   assert mt5.initialize(path=..., login=..., password=..., server=...)
   info = mt5.terminal_info()
   assert info.connected
   ```

4. **Migrazione a MetaApi** (se necessario):
   ```bash
   ORACLE_MT5_BACKEND=metaapi \
   METAAPI_TOKEN=... \
   METAAPI_ACCOUNT_ID=... \
   python scripts/run_paper.py --config config/paper.yaml
   ```
   Nessuna modifica al codice; solo env-vars.

## References

- mt5linux (PyPI / GitHub `lukaszsus/mt5linux`) v1.0.3, Feb 2026;
- WineHQ staging 8.x / 9.x — `wine-staging` su CachyOS/Arch;
- `metaapi-cloud-sdk` (fallback Option B);
- ADR-013: versioned prop-firm rule catalog;
- ADR-015: Topstep automation policy (residenzialità);
- ADR-020: zero-cost data strategy;
- BACKLOG.md BL-723 (questo spike), BL-722 (governor), BL-727
  (qualifier), BL-728 (paper adapter);
- Memoria `mt5-linux-execution-path` (Fase 5b wiring);
- Memoria `propfirm-multifarm-decisions` (decisione D2 multi-firm).

## Demo account verification (BL-723 spike deliverable)

La verifica operativa del bridge Wine + mt5linux richiede un **account
demo forex gratuito**. Procedura (5 minuti, $0):

1. Scegliere un broker MT5 qualsiasi (IC Markets, Pepperstone,
   Exness, FBS — tutti offrono demo gratuiti senza carta).
2. Aprire un conto demo via web: si ricevono `login`, `password`,
   `server` (es. `ICMarkets-Demo01`).
3. Annotare le credenziali in `~/.config/oracle/mt5.env` (chmod 600).
4. Lanciare il bridge locale:
   ```bash
   xvfb-run -a scripts/mt5_bridge.sh
   ```
5. Da Python:
   ```python
   from execution.brokers.mt5linux_client import Mt5LinuxClient
   from execution.brokers.metatrader import MetaTraderBroker
   client = Mt5LinuxClient(host="127.0.0.1", port=18812)
   broker = MetaTraderBroker(client=client, ...)
   snap = broker.account_snapshot()
   assert snap.balance > 0 and snap.equity > 0
   ```
6. Se `account_snapshot()` ritorna numeri coerenti con la demo del
   broker → il bridge è funzionante end-to-end.

Questa verifica NON richiede un conto prop-firm reale. Il passaggio a
conti prop (FTMO, The5ers, Alpha, E8, FundedNext) avviene solo dopo il
gate BL-722 (governor) + BL-727 (qualifier) e l'approvazione
esplicita dell'operatore.
