# Oracle — Prossime Task / Next Tasks

> Prioritizzato per impatto. Ogni task ha: stima tempo, dipendenze, criterio di completamento.

---

## FASE LIVE — Mettere soldi in tasca

### P0 — MFF Challenge Reale (se vuoi fare sul serio)

| # | Task | Tempo | Dipende da | Done quando |
|---|------|:-----:|:----------:|-------------|
| 1 | Aprire account MyFundedFutures 50K | 1h | — | Account creato |
| 2 | Collegare Oracle al paper trading MFF | 2gg | — | Paper trades su account demo MFF |
| 3 | Eseguire challenge con BTC alpha_003 | 3gg | #2 | Challenge passato con profilo certificato |
| 4 | Raddoppiare: 5 account invece di 1 | 1gg | #3 | 5 account finanziati in parallelo |

**Rischio**: un bad week può bloware un account. Con 5 account, la probabilita' di sopravvivenza e' molto piu' alta.

---

## FASE RICERCA — Trovare piu' edge

### P1 — Data Expansion

| # | Task | Tempo | Dipende da | Done quando |
|---|------|:-----:|:----------:|-------------|
| 5 | Login IBKR → backfill ES/NQ/GC/CL 1m | 30min | **TU**: apri https://localhost:7497 | 1m data nel lake |
| 6 | Backfill crypto aggiuntive (ADA, DOT, LINK, MATIC) | 30min | — | 7+ crypto nel lake |
| 7 | Backfill commodity futures (HG, ZC, ZW, ZS) | 30min | — | 9+ futures nel lake |
| 8 | Backfill ETF settoriali (XLF, XLE, XLK, XLV) | 30min | — | 13+ equities nel lake |

### P2 — Strategy Expansion (FinClaw 484 factors)

| # | Task | Tempo | Dipende da | Done quando |
|---|------|:-----:|:----------:|-------------|
| 9 | Tradurre 484 fattori FinClaw in signals_r3.py | 5gg | — | 484 fattori registrati |
| 10 | GA evolution con 484 fattori | 2gg | #9 | DNA pesato su 484 fattori |
| 11 | Sweep 484 fattori × 45 simboli | 1gg | #9-10 | Tabella edge per (fattore, simbolo) |
| 12 | Walk-forward validation su ogni candidato | 2gg | #11 | Lista edge con Sharpe OOS > 0.5 |

### P3 — ML Improvement

| # | Task | Tempo | Dipende da | Done quando |
|---|------|:-----:|:----------:|-------------|
| 13 | Migliorare regime labeling (vol ratio, range expansion, trend strength) | 1gg | — | 8 regimi con distribuzione > 2% ciascuno |
| 14 | 72-dim ML con proper training (weighted sampler, focal loss) | 2gg | #13 | Test accuracy > 50% |
| 15 | Integrare 72-dim classifier nel routing del paper runner | 1gg | #14 | Paper runner usa regime 72-dim |

---

## FASE ENGINEERING — Stabilizzare

### P4 — Paper Runner Reliability

| # | Task | Tempo | Dipende da | Done quando |
|---|------|:-----:|:----------:|-------------|
| 16 | GA fitness con walk-forward reale (calcolo segnali dentro ogni fold) | 2gg | — | Sharpe OOS < 5.0 (realistico) |
| 17 | Test 100 sessioni continue senza errori | 1gg | #16 | 100/100 sessioni con trade |
| 18 | Alert su Telegram per paper trading giornaliero | 1gg | cronjob | Notifica ogni giorno con riepilogo |
| 19 | Dashboard Streamlit per monitorare paper trading | 3gg | #17 | Overview: P&L, Sharpe, DD, trades |

### P5 — Code Quality

| # | Task | Tempo | Dipende da | Done quando |
|---|------|:-----:|:----------:|-------------|
| 20 | Fix 12 lint errori pre-esistenti (E501, F841) | 1gg | — | `make lint` exit 0 |
| 21 | Fix 7 test LLM falliti (mock API calls) | 1gg | — | `make test` exit 0 |
| 22 | Aggiungere test per nuovo codice (regime labeler, GA evolution, 72-dim) | 2gg | — | Coverage > 70% sui nuovi file |
| 23 | Documentazione API per i moduli principali | 2gg | — | README per analytics, genetics, execution |

---

## RIEPILOGO TEMPI

| Categoria | Task | Giorni stimati |
|-----------|:----:|:--------------:|
| LIVE (P0) | 1-4 | **6gg** |
| RICERCA (P1-P3) | 5-15 | **14gg** |
| ENGINEERING (P4-P5) | 16-23 | **10gg** |
| **TOTALE** | **23 task** | **~30gg** |

## PRIORITA' CONSIGLIATA

Se il tuo obiettivo e' **staccare lo stipendio dal trading**:

1. **P0 (6gg)** — Fai il challenge MFF reale con BTC alpha_003
2. **P1 (1.5gg)** — Espandi i dati, IBKR login + backfill
3. **P2 (10gg)** — 484 fattori FinClaw per trovare piu' edge

Il resto (P3-P5) e' miglioramento continuo, non bloccante per il trading live.

---

## COSA SERVE DA TE

| Cosa | Per quale task | Urgenza |
|------|:--------------:|:-------:|
| Login IBKR su https://localhost:7497 | #5 — dati 1m futures | Alta |
| Decidere se aprire MFF challenge | #1 — trading live | Media |
| Credenziali API per alert Telegram | #18 — notifiche | Bassa |
