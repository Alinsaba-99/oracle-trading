# TASKS — Studio Repo MoonDev per trading-os

Scala di studio legata al gap noto: research↔execution disconnessi + Fase 3 (fattori con edge).
Spunta con [x]. Fonti: C:\Users\Administrator\moondev-repos\

---

## P1 — Harvard-Algorithmic-Trading-with-AI (RBI core) ★448
- [x] 1.1 Leggere README root + struttura 3 fasi (research/ backtest/ implement/)
- [x] 1.2 research/ — come organizza le idee prima del codice (metodo da replicare)
- [x] 1.3 backtest/data.py — fetch dati yfinance, confronto col nostro data layer
- [x] 1.4 backtest/template.py — template Backtesting.py, valutare adozione in trading-os
- [x] 1.5 backtest/bb_squeeze_adx.py — logica BB Squeeze + ADX, estrarre regole entry/exit
- [x] 1.6 implement/nice_funcs.py — lib condivisa (ask/bid/SMA/EMA/BB/size/posizioni)
- [x] 1.7 implement/bot.py — bot live: 5x lev, ordini LIMIT, TP 5% / SL 3%, loop gestione errori
- [x] 1.8 Confronto RBI vs nostro pipeline (FactorLab→WF→Wall): mappare cosa manca a trading-os
- [x] 1.9 DECISIONE: quali pattern RBI adottare (es. template backtest unico, nice_funcs-style lib)

## P1 — Trading-Algos (TomData, 19 strategie)
Per ogni strategia: leggere README → capire logica → giudicare fattore testabile Fase 3 → [sì/no]
- [x] 2.1 trend_is_fren (trend following) — SKIP: pseudocode, shift(1) nel next(), non funzionante
- [x] 2.2 capitulation_trade (capitazione/panic) — FORSE: volume_spike_multiplier testabile
- [x] 2.3 buy_the_dip (dip buying) — FORSE: drawdown from high testabile
- [x] 2.4 breakout_wick_algo (breakout + wick) — SKIP: intrabar 15min, non adatto a 1h
- [x] 2.5 first_hr_breakout (prima ora) — SÌ: cross-asset session seasonality
- [x] 2.6 first_vs_lasthr_algo (prima vs ultima ora) — FORSE: session momentum
- [x] 2.7 funding_arbitrage (funding rate) — SÌ ★: funding spread, edge economico forte
- [x] 2.8 liquidation_bot (liquidazioni) — SÌ ★: liq cascade reversal, mean reversion
- [x] 2.9 quant_gpt (AI-driven) — SKIP: EMA/RSI crossover, già abbiamo in factors.py
- [x] 2.10 lowcapgem_algo (lowcap screening) — SKIP: non è un factor, è screening
- [x] 2.11 demand_zone_vol (demand zone + volume) — FORSE: support + volume spike
- [x] 2.12 fund_demand_bot (fund demand) — SÌ ★: funding rate extremum, edge alto
- [x] 2.13 btc_etf (ETF flow) — SKIP: news monitoring, non quantitative
- [x] 2.14 futures_open (open interest futures) — FORSE: time-based seasonality
- [x] 2.15 mexc_bots (bot exchange MXC) — SKIP: VWAP, già testabile con nostri dati
- [x] 2.16 HyperLiquid-Trading-Bots/arb.py (arbitraggio) — SÌ ★: funding spread + HL nice_funcs
- [x] 2.17 coinglass-liqudations (dati Coinglass) — DATA: data source per liq factor
- [x] 2.18 Riassunto: shortlist 3-5 fattori con edge plausibile da portare in Fase 3
- [x] 2.19 Implementare top fattore in trading-os FactorLab + walk-forward

## P2 — Hyperliquid-Data-Layer-API (data layer) ★113
- [x] 3.1 README + requirements — cosa serve (API key moondev.com?)
- [x] 3.2 api.py (2025 righe) — mappa dei 40+ endpoint
- [x] 3.3 examples 01-12: liquidations, positions, whales, events, contracts, ticks, orderflow, trades, smart_money, user_positions/fills, hlp
- [x] 3.4 examples 13-24: multi-exchange liq, buyers, depositors, hlp sentiment/analytics, market data, hip3, snapshots
- [x] 3.5 examples 25-38: ai_chat, bulk liq CSV, CVD scanner, near-liquidation, liq stream, funding/OI, tick stream, polymarket, OHLCV, proxy, fills polling
- [x] 3.6 ai_agents/swarm_agent.py — 6 modelli via OpenRouter (pattern multi-modello)
- [x] 3.7 ai_agents/director_agent.py — orchestrazione
- [x] 3.8 examples/Ideas.md — ideeTODO di MoonDev
- [x] 3.9 docs/polymarket-profitable-traders.md
- [x] 3.10 DECISIONE: quali endpoint (liq/whales/CVD) integrare in trading-os come dati fattore

## P3 — Altri bot di trading
- [x] 4.1 Moon-Dev-AI-Trading-Battles — battle_core, run_battle, watch_battle, HEARTBEAT_API_SPEC (6 AI su $100 reali)
- [x] 4.2 Limitless-Prediction-Market-Bots (★59)
- [x] 4.3 Polymarket-Trading-Bot-Examples (23 file)
- [x] 4.4 housecoin-100x-bot (scale-in)
- [x] 4.5 short-crypto-to-0-trading-bot
- [x] 4.6 prize-picks-bot (PrizePicks API)
- [x] 4.7 Hibachi-examples + Extended-examples (API exchange alternative)
- [x] 4.8 Riassunto P3: pattern ricorrenti (risk mgmt, sizing, loop bot) da adottare

## P4 — Materiale vario
- [x] 5.1 Moon-Dev-Code: 3 PDF accademici (strategy_pdfs/) — leggere ed estrarre strategie testabili
- [x] 5.2 learn-typescript-from-python (2433 file — solo consultazione, skip profondo)
- [x] 5.3 YouTube-Strike-Analysis-With-OpenAI, espn-rundown, tool minori — solo se serve

## Trasversale
- [x] 6.1 Per ogni repo P1/P2: note in moondev-repos/NOTES.md (cosa, come, cosa rubiamo)
- [x] 6.2 Collegamento video: associare repo ↔ video MoonDev (hermes-video-watch) quando serve spiegazioni
- [x] 6.3 Update memoria/skill al termine con i pattern adottati in trading-os
- [x] 6.4 DOMANDE_APerte.md — 15 domande aperte per handoff approfondimenti
