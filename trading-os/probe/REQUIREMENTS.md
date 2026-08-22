# Requisiti del sistema — greenfield trading-os

> Cosa deve poter fare un sistema di trading sistematico completo, dalla
> ricerca all'execution. Questa lista è il metro con cui valutare OGNI
> voce del catalogo awesome-systematic-trading — nessuna esclusione a
> priori: si valuta il contributo di ciascuna al copertura dei requisiti.
> Vincolo permanente dell'utente: **$0/mese** (ogni costo dichiarato).

## R — Requisiti

| ID | Requisito | Dettaglio |
|---|---|---|
| R1 | Gestione ricerca/ipotesi | registry ipotesi, preregistrazione test, tracking verdetti |
| R2 | Dati OHLCV multi-asset | equity, futures, FX, crypto, indici; storico profondo; $0 |
| R3 | Dati alternativi/microstruttura | order book L2, trades, funding, liquidazioni, insider/13F, news, sentiment, macro PIT, on-chain |
| R4 | Storage dati + qualità | persistenza time-series, quality checks, lineage, versioning |
| R5 | Libreria indicatori/fattori | TA classica + fattori custom; analisi fattori (IC, turnover, quantile) |
| R6 | Backtest veloce (sweep) | vectorized, migliaia di varianti in secondi |
| R7 | Backtest event-driven realistico | fee, slippage, fill parziali, corporate actions, multi-asset |
| R8 | Backtest HFT/tick/L2 | queue position, latency, full tick data |
| R9 | Walk-forward + validazione anti-overfitting | CPCV, DSR/PBO, haircut Sharpe, block bootstrap |
| R10 | Modellazione ML/RL | supervised + reinforcement learning su dati finanziari |
| R11 | Ottimizzazione portafoglio + sizing | frontier, HRP, Black-Litterman, Kelly, target vol |
| R12 | Metriche rischio/performance + reporting | Sharpe/Sortino/Calmar/DD, tearsheet, attribuzione |
| R13 | Connettività broker/exchange | paper e live; equities, futures, crypto |
| R14 | Modellazione fill/slippage | realismo esecuzione nei backtest |
| R15 | Hard risk + governance | kill switch, limiti non bypassabili, regole prop-firm, audit |
| R16 | Streaming real-time | WebSocket feeds, message bus, streaming DB |
| R17 | Operations | scheduling, monitoring, alerting, recovery |
| R18 | UI/UX | dashboard, equity/trade review, esplorazione dati |
| R19 | Qualità sviluppo | lint, test, profiling, CI |
| R20 | Economia | tutto il sistema deve girare a $0/mese (dichiarare ogni costo) |

## Regole di valutazione (per ogni voce del catalogo)

1. **Nessun taglio a priori**: ogni voce riceve una card di valutazione.
2. Ogni card deve dire: cosa copre (R*), punti di forza, limiti/rischi,
   costo, cosa servirebbe per adottarla.
3. I claim di rendimento esterni sono NON VERIFICATI finché non auditati.
4. "Morto" o "fuori mercato" sono fatti registrati, non motivi di
   cancellazione: una libreria morta può essere riferimento valido.
