# Oracle Dashboard

Trading terminal web per il sistema Oracle — 3 pagine, dati reali da checkpoint GA e DB esperimenti.

## Requisiti

- Python 3.12+ (con dipendenze progetto)
- Node.js 20+

## Setup rapido

```bash
# 1. Backend — attiva virtualenv e avvia API
cd ~/_repos/oracle-trading
source .venv/bin/activate
uvicorn apps.api.main:app --reload --port 8000

# 2. Frontend — in un altro terminale
cd apps/dashboard
npm install    # prima volta soltanto
npm run dev    # → http://localhost:5173
```

Vite proxy le richieste `/api/*` a `localhost:8000`.

## Produzione

```bash
cd apps/dashboard
npm run build
# → FastAPI serve apps/dashboard/dist/ su http://localhost:8000
```

## Comandi

| Comando | Descrizione |
|---------|-------------|
| `npm run dev` | Sviluppo con HMR su :5173 |
| `npm run build` | Build produzione (TypeScript + Vite) |
| `npm run preview` | Preview della build |
| `npm test` | Test unitari (Vitest) |
| `npm run test:watch` | Test in watch mode |

## Test

```bash
# Backend (dalla root del progetto)
python3 -m pytest tests/api/ -v

# Frontend
cd apps/dashboard && npm test
```

## API Endpoints

| Endpoint | Descrizione |
|----------|-------------|
| `GET /api/v1/performance/summary` | Metriche dal miglior checkpoint |
| `GET /api/v1/performance/equity` | Equity curve |
| `GET /api/v1/performance/today` | Riepilogo trade odierni |
| `GET /api/v1/trades` | Esperimenti paginati (filtri: engine, fold, from, to) |
| `GET /api/v1/trades/export` | Export CSV |
| `GET /api/v1/ga/runs` | Lista run GA disponibili |
| `GET /api/v1/ga/runs/{id}` | Dettaglio run (Pareto + convergenza) |
| `GET /api/v1/stream/positions` | SSE posizioni in tempo reale |

## Shortcut Tastiera

| Tasto | Pagina |
|-------|--------|
| `1` o `n` | Dashboard |
| `2` o `t` | Trades |
| `3` o `g` | GA |

## Architettura

```
React 18 + TypeScript + Vite 5 + Tailwind CSS v3
TradingView Lightweight Charts (equity/drawdown)
Plotly.js (Pareto 4D scatter, convergence) — lazy loaded
FastAPI + SSE (asyncio.Queue) + REST polling
React Router v6 + TanStack Query + Zustand
```
