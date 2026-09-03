# Oracle Terminal — UI operativa + live paper loop (design)

> Data: 2026-09-02 · Stato: APPROVATO (direzione confermata in chat)
> Metodo di clonazione UI ispirato a `JCodesMore/ai-website-cloner-template`
> (estrazione referenze → spec per componente → builder), adattato al nostro
> stack esistente.

## 1. Obiettivo

Dare a Oracle una UI di livello "broker vero" per usare bene il sistema:
un terminale di paper trading (Fase A) alimentato dal loop live che oggi
manca (Fase B), più una vista ricerca sullo stato della factory. Il tutto
nel dashboard esistente (`apps/dashboard`, servito da `apps/api` FastAPI).

## 2. Referenze di design (design language, non pixel+asset)

| Referenza | Cosa prendiamo | Pagina |
|---|---|---|
| Binance spot trade | order ticket, order book, densità mercato, palette dark | `binance.com/en/trade/BTC_USDT` (pubblica) |
| TradingView | chart + toolbar, pannelli laterali, interazioni chart | `tradingview.com/symbols/BTCUSD/` (pubblica) |
| Alpaca | tabelle posizioni/P&L, pulizia dashboard | dashboard (richiede login: screenshot forniti dall'utente, fase 2) |
| IBKR Client Portal | densità informativa, watchlist | richiede login (fase 2) |

**Policy IP (vincolo duro):** nessun asset proprietario (loghi, icone,
immagini, CSS copiato) entra nel repo. Si clona il design language —
layout, palette, tipografia, spaziatura, pattern di interazione — con
branding e asset nostri ("Oracle Terminal"). Artefatti di estrazione
(screenshot, token) vivono in `docs/design-references/oracle-terminal/`
e non vengono serviti né committati asset binari dei siti originali.

## 3. Schermate

### 3.1 Terminal (route `/terminal`, schermata principale)

Layout 4 zone, dark, densità alta, monospace per i numeri:

- **Sinistra**: watchlist (simboli, ultimo prezzo, variazione %) + stato feed.
- **Centro**: candlestick chart (`lightweight-charts` già in dipendenza)
  con toolbar timeframe (1m/5m/15m/1h/4h/1d) e indicatori minimi (SMA/EMA).
- **Destra**: order ticket (side buy/sell, tipo market/limit, quantità,
  prezzo, stima costo/fee) + order book sintetico dal feed.
- **Basso**: tab Posizioni / Ordini / Fill / Equity con P&L live e
  drawdown vs limiti firm (collegamento a `PropFirmRiskGovernor`).
- **Status bar**: modalità (RESEARCH/REPLAY/PAPER), stato feed
  (live/stale da `StaleFeedDetector`), alert `RiskAlertBus`, sessione,
  git-commit del manifest.

### 3.2 Ricerca (route `/research`, fase 3)

Registry ipotesi factory (`docs/knowledge-base/edge-factory/registry/`)
con stato (da_amplificare → APPROVED), IC screen results, gate status da
`docs/ORACLE_AUTOPILOT_STATUS.md` §3. Lettura, niente editing da UI.

## 4. Architettura dati

- **Backend** (`apps/api`): nuovi endpoint `paper` —
  `GET /api/paper/session` (stato loop: running, strategy, uptime,
  equity, drawdown), `GET /api/paper/positions`, `GET /api/paper/orders`,
  `GET /api/paper/fills`, `GET /api/paper/equity?window=` (serie per
  chart), SSE `/api/paper/stream` (aggiornamenti push: posizioni, fill,
  alert). Auth/bind fail-closed già esistenti (P0 fix) restano attivi.
- **Loop live** (nuovo modulo `execution/live_loop.py`): asyncio,
  `CCXTWebSocketFeed` (ccxt.pro, MIT, già dipendenza) → barre chiuse →
  segnale (adapter pluggabile; default: strategia neutra SMA-cross per
  validare l'infra SENZA promuovere alcun edge, gate BL-OPC-7 intatto) →
  `PaperBroker` + `RealisticPaperFillEngine` + guards
  (`StaleFeedDetector`, `SignalProviderCircuit`, `RiskAlertBus`) →
  snapshot/restore periodico (`PaperBroker.snapshot` già esiste) →
  scrittura su ledger Postgres. Systemd user unit
  `systemd/oracle-paper-live.{service,timer}` con restart policy.
- **Frontend**: react-query per polling/SSE, zustand per stato UI locale;
  componenti nuovi sotto `apps/dashboard/src/components/terminal/`.

## 5. Fasi di esecuzione

- [ ] **F0 — Estrazione referenze** (Playwright già installato):
  screenshot full-page desktop+mobile e token di design (palette,
  tipografia, spacing via `getComputedStyle`) da Binance trade e
  TradingView symbol page. Output: `docs/design-references/oracle-terminal/`.
- [ ] **F1 — Design tokens + spec componenti**: token nostri derivati
  dalle referenze in `apps/dashboard/src/styles/terminal.css` (Tailwind
  config esteso); spec per componente (order ticket, book, watchlist,
  positions table, status bar) come file markdown sotto
  `docs/design-references/oracle-terminal/components/`.
- [ ] **F2 — Terminal UI con dati mock**: route `/terminal` completa e
  navigabile con mock data realistici; vitest sui componenti chiave;
  screenshot Playwright del Terminal per verifica visiva.
- [ ] **F3 — Loop live MVP**: `execution/live_loop.py` + adapter segnale
  + test unit (feed finto) + smoke su BTCUSDT/ETHUSDT con dati pubblici
  ($0) in PAPER mode; systemd unit.
- [ ] **F4 — Endpoint + wiring**: endpoint `/api/paper/*` + SSE; il
  Terminal passa da mock a dati reali del loop.
- [ ] **F5 — Chiusura**: suite verde (pytest sui path toccati, ruff,
  mypy --strict), BACKLOG/STATUS aggiornati, commit.

## 6. Vincoli

- $0/mese (ADR-020): feed pubblici crypto (ccxt.pro WS); niente Polygon
  paid, niente market data IBKR a pagamento in questa fase.
- PAPER mode only: nessun ordine reale; mode guard fail-closed.
- Nessun asset binario dei siti referenziati committato (solo token
  testuali e note; screenshot in gitignore locale se troppo grandi).
- cryptofeed (BL-716) resta fuori: licenza AGPL+7(b) verificata oggi;
  ccxt.pro copre lo stesso bisogno.
- nautilus_trader: presente in pyproject ma non usato per il loop
  (engine alternativo, costo integrazione non giustificato).

## 7. Decisioni aperte (non bloccanti)

- Referenze login-required (Alpaca dashboard, IBKR Client Portal):
  screenshot forniti dall'utente in fase 2, o secondo turno di
  estrazione con sessione autenticata.
- IBKR paper via ib_async (BSD-2, fork mantenuto di ib_insync che è
  archiviato): migrazione dipendenza da fare in sessione dedicata.
