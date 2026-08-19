> **ARCHIVIO STORICO.** Questo documento era parte del modello Phase,
> deprecato da ADR-012 e sostituito dai capability gate G0-G9.
> Roadmap canonica: [ROADMAP.md](../../ROADMAP.md). Stato corrente:
> [ORACLE_AUTOPILOT_STATUS.md](../ORACLE_AUTOPILOT_STATUS.md). Non aggiornare — solo git archaeology.

 6 — Oracle Dashboard: Piano di Sviluppo (rev. 2)

> WebUI custom per il monitoraggio e controllo del sistema Oracle.
> Trading terminal professionale, self-hosted, dark mode.

---

## 0. Decisioni Architetturali (ADR)

| # | Decisione | Motivazione |
|---|-----------|-------------|
| D1 | **SSE invece di WebSocket** per real-time | Nessuna dipendenza (Redis). `asyncio.Queue` in-process. SSE unidirezionale è sufficiente: server → client per metriche e posizioni. |
| D2 | **REST polling 30s** per dati batch | GA checkpoint, equity curve, trade history sono snapshot, non stream. Polling + React Query cache. |
| D3 | **Plotly.js per Pareto 4D**, TradingView per OHLCV | Plotly ha supporto nativo per scatter 4D (x, y, color, size). D3 solo per custom viz semplici (gauge, mini-chart). |
| D4 | **3 pagine per v1** | Dashboard, Trades, GA. Agents, Risk, Settings in v2. |
| D5 | **FastAPI serve static files** in produzione | Unico processo. `uvicorn apps.api.main:app`. In sviluppo: Vite proxy `/api/*` a FastAPI. |
| D6 | **React Router v6** (non v7) | Stabile, documentato, layout nidificati via `Outlet`. |
| D7 | **Tailwind CSS v3** (non v4) | Nessun breaking change, configurazione stabile. |
| D8 | **API key semplice** per auth v1 | Header `X-API-Key`. Config in env. JWT in v2. |
| D9 | **Vitest + MSW + RTL** per test | Vitest (Vite-native), MSW (mock API), React Testing Library (componenti). |

---

## 1. Architettura

```
┌──────────────────────────────────────────────────────────┐
│                   CLIENT (Browser)                       │
│  React 18 + TypeScript + Vite 5                          │
│  Tailwind CSS v3 + shadcn/ui                             │
│  TradingView Lightweight Charts + Plotly.js              │
│  TanStack React Query + Zustand + React Router v6        │
├──────────────────────────────────────────────────────────┤
│                SSE (Server-Sent Events)                  │
│  /api/v1/stream/positions ── asyncio.Queue ── Python     │
│  /api/v1/stream/risk      ── asyncio.Queue              │
├──────────────────────────────────────────────────────────┤
│              FastAPI (unico processo)                    │
│  apps/api/main.py                                        │
│  Endpoint REST: /api/v1/*                                │
│  Endpoint SSE:  /api/v1/stream/*                         │
│  Auth: X-API-Key header                                  │
│  Static: serve apps/dashboard/dist/ in produzione        │
└──────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Tecnologia | Perché |
|-------|-----------|--------|
| **Frontend** | React 18 + TypeScript | Ecosistema più ricco, stabile |
| **Build** | Vite 5 | Build veloce, HMR istantaneo |
| **Styling** | Tailwind CSS v3 + shadcn/ui | Utility-first, dark mode nativa, componenti copiabili e personalizzabili |
| **Charts OHLCV** | TradingView Lightweight Charts | Free, financial-grade, candlestick |
| **Charts scatter** | Plotly.js | Pareto 4D nativo (x, y, color, size), zoom, hover, click |
| **Charts custom** | D3.js (minimo) | Solo gauge e mini-chart |
| **HTTP + cache** | TanStack React Query | Polling 30s, cache, retry, SSR-compatibile |
| **State** | Zustand | Leggero, TypeScript, persistente |
| **Routing** | React Router v6 | Stabile, `Outlet` per layout nidificati |
| **Backend** | FastAPI (Python) | Già in dipendenze, async, SSE nativo |
| **Real-time** | SSE via `asyncio.Queue` | Nessuna dipendenza extra, unidirezionale |
| **Auth** | API key via env | Header `X-API-Key`, config in `.env` |
| **Test FE** | Vitest + MSW + RTL | Vite-native, mock API, component testing |

---

## 2. Struttura Repository

```
apps/
  api/
    __init__.py
    main.py                     ← FastAPI app + CORS + auth middleware + static mount
    config.py                   ← Settings from env (API key, broker config)

    routers/
      __init__.py
      performance.py            ← GET /api/v1/performance/summary, /equity
      trades.py                 ← GET /api/v1/trades (paginato + filtri), /positions
      ga.py                     ← GET /api/v1/ga/runs, /ga/runs/{id}
      stream.py                 ← GET /api/v1/stream/positions (SSE)

    services/
      __init__.py
      equity_service.py         ← Legge equity curve da checkpoint/BacktestResult
      trade_service.py          ← Legge trade log da OrderManager/DB
      checkpoint_reader.py      ← Legge checkpoint GA JSON

    models.py                   ← Pydantic response models

    ws.py                       ← SSE manager (asyncio.Queue + broadcast)

  dashboard/                    ← Frontend React (nuovo)
    package.json
    tsconfig.json
    vite.config.ts               ← proxy /api → localhost:8000 in dev

    index.html
    public/
      favicon.svg

    src/
      main.tsx
      App.tsx

      routes/
        index.tsx                ← createBrowserRouter
        layout.tsx               ← Root layout (sidebar + header + <Outlet/>)
        dashboard-page.tsx       ← / (dashboard principale)
        trades-page.tsx          ← /trades
        ga-page.tsx              ← /ga

      components/
        layout/
          sidebar.tsx            ← Navigation (Dashboard, Trades, GA)
          header.tsx             ← Status, clock, connection indicator

        charts/
          equity-chart.tsx       ← TradingView line chart (equity curve)
          drawdown-chart.tsx     ← TradingView area chart (drawdown)
          pareto-scatter.tsx     ← Plotly scatter 4D (Sharpe, Sortino, Calmar, MaxDD)
          convergence-chart.tsx  ← Plotly line chart (per-generation metrics)
          risk-gauge.tsx         ← D3 gauge (semplice, SVG)

        data/
          metrics-grid.tsx       ← Metric cards (Sharpe, PF, MaxDD...)
          trade-table.tsx        ← Trade log con paginazione
          positions-table.tsx    ← Open positions (SSE update)

        ui/
          page-shell.tsx         ← Titolo + descrizione + children
          empty-state.tsx        ← "No data yet" con azione
          error-boundary.tsx     ← Catch error + retry
          loading-skeleton.tsx   ← Skeleton loader
          connection-badge.tsx   ← Connected/disconnected indicator

      hooks/
        use-equity.ts            ← React Query: GET /api/v1/performance/equity (30s polling)
        use-summary.ts           ← React Query: GET /api/v1/performance/summary (30s)
        use-trades.ts            ← React Query: GET /api/v1/trades (paginated)
        use-ga-runs.ts           ← React Query: GET /api/v1/ga/runs
        use-sse.ts               ← EventSource connection per SSE
        use-positions.ts         ← Zustand store aggiornato via SSE

      lib/
        api.ts                   ← Fetch wrapper con auth header
        types.ts                 ← TypeScript interfaces (Trade, Position, GARun, ...)
        formats.ts               ← Formattazione numeri, date, percentuali
        constants.ts             ← API base URL, polling intervals
```

---

## 3. Pagine — v1 (3 pagine)

### 3.1 Dashboard (`/`)

```
┌────────────────────────────────────────────────────────────┐
│  [● Connected]  [12:34:56]  [Last update: 2s ago]          │
├────────────────────────────────────────────────────────────┤
│  Sharpe  1.24 │ Sortino 0.89 │ PF 1.67 │ MaxDD -12.3%     │
├──────────────────────────────────┬─────────────────────────┤
│                                  │ Drawdown                │
│  Equity Curve                    │ ████████████████████     │
│  ╱╲    ╱╲    ╱╲                  │ ████████████             │
│ ╱  ╲  ╱  ╲  ╱  ╲                │ ██████                   │
│                                  │ Current: -4.2%          │
├──────────────────────────────────┴─────────────────────────┤
│  Open Positions                         │ Trade Today       │
│  SPY  100 ▲ +$230  +0.23%              │ 5 trades          │
│  BTC    2 ▲ +$1.2k +1.1%              │ 3 win / 2 loss     │
│  QQQ   50 ▼ -$120  -0.40%             │ PF: 1.89           │
└────────────────────────────────────────────────────────────┘
```

**Dati:** equity curve (TradingView), metriche (4 card), drawdown (area chart), posizioni (tabella live via SSE), trade oggi (riepilogo)

**Caricamento:** 4 skeleton cards mentre loading
**Vuoto:** messaggio "Esegui un backtest per vedere i dati" + link a `/ga`
**Errore:** Error boundary con retry

**API:**
- `GET /api/v1/performance/summary` (30s polling)
- `GET /api/v1/performance/equity` (30s polling, ultimi 252 giorni)
- `GET /api/v1/positions` (30s polling, refresh su SSE event)
- `GET /api/v1/stream/positions` (SSE, push su nuova posizione)

### 3.2 Trade Log (`/trades`)

```
┌────────────────────────────────────────────────────────────┐
│  Filtri: [Date] → [Date] │ [Asset: All ▼] │ [Side ▼]      │
│  [Export CSV]  [24 totali — 1 selected]                    │
├────────┬───────┬──────┬──────┬────────┬──────────┬─────────┤
│ Time   │ Asset │ Side │ Qty  │ Price  │ P&L      │ Status  │
├────────┼───────┼──────┼──────┼────────┼──────────┼─────────┤
│ 12:34  │ SPY   │ BUY  │ 100  │ 543.21 │          │ filled  │
│ 12:30  │ BTC   │ SELL │    2 │ 67,890 │ +$1,240  │ filled  │
│ 11:15  │ QQQ   │ BUY  │   50 │ 487.65 │ -$120    │ filled  │
├────────┴───────┴──────┴──────┴────────┴──────────┴─────────┤
│  ← Prev  1-20 of 245  Next →                               │
└────────────────────────────────────────────────────────────┘
```

**Dati:** tabella paginata, filtri (data, asset, side), export CSV, click per dettaglio

**Caricamento:** Table skeleton (6 righe)
**Vuoto:** "Nessun trade trovato" + suggerimenti (cambia filtro, esegui backtest)
**Errore:** toast + retry button

**API:** `GET /api/v1/trades?limit=20&offset=0&asset=SPY&side=buy&from=2026-01-01&to=2026-07-11`
**Export:** `GET /api/v1/trades/export?format=csv` (stessi filtri)

### 3.3 GA Viewer (`/ga`)

```
┌────────────────────────────────────────────────────────────┐
│  Run: pb_seed42  Seed: 42  Gen: 20/20  Status: ✅ Done     │
│  [Select run ▼]                                            │
├────────────────────────────────┬───────────────────────────┤
│  Pareto Front (Plotly 4D)      │ Convergence               │
│  ┌────────────────────────┐    │ ┌───────────────────────┐ │
│  │  ● Sharpe 1.24         │    │ │ ╱╲   ╱╲              │ │
│  │  ● Sortino 0.89        │    │ │╱  ╲ ╱  ╲  ╱╲        │ │
│  │  ● Calmar 1.67         │    │ │     ╱    ╲╱  ╲       │ │
│  │  ○ MaxDD 12.3%         │    │ └───────────────────────┘ │
│  └────────────────────────┘    │ Gen 1 → 20                │
├────────────────────────────────┴───────────────────────────┤
│  Best Individual                                           │
│  knn_k: 8 │ train_len: 4 │ threshold: 0.5 │ class_w: 0.5  │
│  Sharpe: 1.24  Sortino: 0.89  Calmar: 1.67  MaxDD: 12.3%  │
└────────────────────────────────────────────────────────────┘
```

**Dati:** selector run, Pareto scatter 4D (Plotly), convergenza (line chart), parametri miglior individuo

**Caricamento:** skeleton cards + "Loading GA runs..."
**Vuoto:** "Nessuna run GA trovata. Lancia una GA run da CLI."
**Errore:** "Impossibile caricare checkpoint" + retry

**API:**
- `GET /api/v1/ga/runs` — lista run disponibili (legge `checkpoints/`)
- `GET /api/v1/ga/runs/{run_id}` — Pareto front + convergenza + best params

---

## 4. Design System

```css
/* Palette dark mode */
--bg:        #0d0d0f;     /* fondo principale */
--surface:   #161618;     /* card, sidebar */
--border:    #232326;     /* bordi */
--text:      #e4e4e7;     /* testo primario */
--text-dim:  #71717a;     /* testo secondario */
--green:     #22c55e;     /* BUY / positivo */
--red:       #ef4444;     /* SELL / negativo */
--accent:    #3b82f6;     /* highlight, link */
--chart:     #3b82f6;     /* equity curve line */

/* Font: Inter (UI) + JetBrains Mono (dati numerici) */
```

```
┌──────────────────────────────────────────────────────────┐
│  ● ORACLE                         Dashboard Trades GA   │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  [superfici scure · dati numerici in mono · zero fronzoli]│
│  [metriche immediate · charts minimali · tutto visibile]  │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

Ispirato a: Bloomberg Terminal (densità), TradingView (charts), Warp (design).

### Formati numerici

| Tipo | Formato | Esempio |
|------|---------|---------|
| Prezzo azione | `$123.45` | 2 decimali |
| Prezzo crypto > $100 | `$67,890` | 2 decimali, separatore migliaia |
| Prezzo crypto < $1 | `$0.123456` | 6 decimali |
| P&L | `+$1,234.56` / `-$567.89` | 2 decimali, segno, separatore |
| Percentuale | `+12.3%` / `-4.2%` | 1 decimale, segno |
| Sharpe / Sortino | `1.24` | 2 decimali |
| MaxDD | `12.3%` | 1 decimale |
| Profit Factor | `1.67` | 2 decimali |
| Data | `2026-07-11` | ISO |
| Ora | `12:34:56` | 24h |
| Data+ora | `11 Jul 12:34` | Abbreviato per tabelle |

---

## 5. API Endpoints (v1)

```
# Performance
GET /api/v1/performance/summary       → {sharpe, sortino, pf, maxdd, cagr, total_return}
GET /api/v1/performance/equity        → [{date, equity, drawdown}]  (ultimi 252 punti)
GET /api/v1/performance/today         → {trades, wins, losses, pf, pnl}

# Trades
GET /api/v1/trades                    → {items: Trade[], total, limit, offset}
    ?limit=20&offset=0&asset=SPY&side=buy&from=2026-01-01&to=2026-07-11
GET /api/v1/trades/{id}               → Trade (detail)
GET /api/v1/positions                 → Position[] (open positions)

# GA
GET /api/v1/ga/runs                   → {runs: [{id, seed, generations, status, timing}]}
GET /api/v1/ga/runs/{run_id}          → {run, pareto: Individual[], convergence: [{gen, sharpe, ...}]}

# SSE (real-time)
GET /api/v1/stream/positions          → SSE: new position / close position
GET /api/v1/stream/risk-alerts        → SSE: VaR breach, daily loss limit
```

---

## 6. Fasi di Implementazione

### Fase 1 — Scaffolding (1 sessione)

```
Backend:
  □ apps/api/main.py            — FastAPI app base + CORS + auth middleware
  □ apps/api/config.py          — Settings da env
  □ apps/api/models.py          — Pydantic models
  □ apps/api/routers/__init__.py — Router aggregator
  □ apps/api/routers/*.py       — 4 router stub
  □ apps/api/ws.py              — SSE manager (asyncio.Queue)

Frontend:
  □ apps/dashboard/             — Vite + React 18 + TS scaffolding
  □ Tailwind v3 + shadcn/ui setup
  □ React Router v6 config
  □ Layout: sidebar + header + Outlet
  □ Dark mode (class-based)
  □ vite.config.ts proxy per API
```

### Fase 2 — API Backend (1 sessione)

```
  □ GET /api/v1/performance/summary    — legato a BacktestResult / checkpoint
  □ GET /api/v1/performance/equity     — equity curve from checkpoint
  □ GET /api/v1/trades                 — trade log da experiments.db
  □ GET /api/v1/positions              — posizioni aperte da OrderManager
  □ GET /api/v1/ga/runs                — lista checkpoint
  □ GET /api/v1/ga/runs/{id}           — pareto + convergenza
  □ GET /api/v1/stream/positions       — SSE push
```

### Fase 3 — Dashboard page (1 sessione)

```
  □ MetricsGrid — 4 metric cards (Sharpe, Sortino, PF, MaxDD)
  □ EquityChart — TradingView line chart
  □ DrawdownChart — TradingView area chart
  □ PositionsTable — tabella posizioni (SSE update)
  □ TodaySummary — trade oggi riepilogo
  □ use-summary, use-equity, use-positions hooks
  □ Loading / Empty / Error states
```

### Fase 4 — Trades page (1 sessione)

```
  □ TradeTable — paginata, filtri
  □ Export CSV
  □ Trade detail panel (sheet)
  □ use-trades hook
  □ Loading / Empty / Error states
```

### Fase 5 — GA Viewer page (1 sessione)

```
  □ RunSelector — dropdown run disponibili
  □ ParetoScatter — Plotly 4D scatter
  □ ConvergenceChart — Plotly line chart
  □ BestParams — tabella parametri
  □ use-ga-runs hook
  □ Loading / Empty / Error states
```

### Fase 6 — Integrazione + Polish (1 sessione)

```
  □ Error boundary globale
  □ SSE reconnection
  □ Theme persistence (dark mode)
  □ Responsive adjustments
  □ Keyboard shortcuts (for power users)
  □ README + run instructions
```

---

## 7. Testing

### Backend (API)
- `pytest tests/api/` — test endpoint con `TestClient`
- Mock dei servizi dati (checkpoint, trade db)

### Frontend (componenti)
- `Vitest` + `React Testing Library` + `MSW`
- Test per ogni componente: render, interazioni, stati
- Coverage target: >70%

### Esempio test
```typescript
// tests/components/metrics-grid.test.tsx
import { render, screen } from '@testing-library/react'
import { MetricsGrid } from '@/components/data/metrics-grid'

test('mostra 4 metric cards con loading skeleton', () => {
  render(<MetricsGrid loading />)
  expect(screen.getAllByTestId('skeleton')).toHaveLength(4)
})

test('mostra metriche quando dati disponibili', () => {
  render(<MetricsGrid data={{ sharpe: 1.24, sortino: 0.89, pf: 1.67, maxdd: 0.123 }} />)
  expect(screen.getByText('1.24')).toBeInTheDocument()
  expect(screen.getByText('1.67')).toBeInTheDocument()
})

test('mostra empty state quando nessun dato', () => {
  render(<MetricsGrid data={null} />)
  expect(screen.getByText(/nessun dato/i)).toBeInTheDocument()
})
```

---

## 8. Comandi per Sviluppo

```bash
# Backend (da ~/_repos/oracle-trading/)
source .venv/bin/activate
uvicorn apps.api.main:app --reload --port 8000

# Frontend (da ~/_repos/oracle-trading/apps/dashboard/)
npm install
npm run dev
# → http://localhost:5173 (Vite proxy /api → :8000)

# Produzione
cd apps/dashboard && npm run build
# → FastAPI serve apps/dashboard/dist/ → http://localhost:8000
```

---

## 9. Timeline

```
Sessione 1:  Scaffolding (Vite + FastAPI + shadcn + layout + router stub)
Sessione 2:  API Backend (tutti gli endpoint + SSE)
Sessione 3:  Dashboard page (metriche + equity + posizioni)
Sessione 4:  Trades page (tabella + filtri + export)
Sessione 5:  GA Viewer page (Pareto + convergenza)
Sessione 6:  Polish, error handling, test, README
```

**6 sessioni** · ~8-12 ore totali · 3 pagine v1 · 20 componenti · zero dipendenze extra (niente Redis, niente DB)<｜end▁of▁thinking｜>Piano riscritto in `docs/phase6-plan.md`. 10 sezioni, 6 fasi, 3 pagine v1.

### Cosa è cambiato rispetto alla prima versione

| Aspetto | Prima | Dopo (rev. 2) |
|---------|-------|---------------|
| **Real-time** | WebSocket + Redis | SSE + `asyncio.Queue` (zero dipendenze) |
| **Dati batch** | WebSocket | REST polling 30s + React Query cache |
| **Pareto chart** | D3.js 4D | Plotly.js (nativo 4D, zoom, hover) |
| **Pagine v1** | 6 | **3** (Dashboard, Trades, GA) |
| **Routing** | React Router v7 | v6 (stabile) |
| **Tailwind** | v4 | v3 (no breaking change) |
| **Auth** | "JWT future" | API key via env + header |
| **Stati** | non specificati | 4-stati: Loading/Empty/Error/Data |
| **Deploy** | non specificato | FastAPI static + Vite proxy |
| **Test** | non specificato | Vitest + MSW + RTL |
| **Formati** | non specificati | Tabella completa formati numerici |

### Stack finale

```
React 18 + TS + Vite 5 + Tailwind v3 + shadcn/ui
TradingView Charts (OHLCV) + Plotly.js (scatter 4D)
FastAPI + SSE (asyncio.Queue) + REST polling
React Router v6 + TanStack Query + Zustand
API key auth · Vitest + MSW + RTL
```

Pronto a partire con la **Fase 1** (scaffolding) quando vuoi.
