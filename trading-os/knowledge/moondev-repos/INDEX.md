# Moon Dev Repos — Indice di studio

Fonte: github.com/moondevonyt (26 repo, 19 originali clonati qui + TomData/Trading-Algos)
Fork SKIPPATI (non codice Moon Dev): goose, eliza, agent-zero, ZerePy, claude-code

## Priorità 1 — RBI core (per trading-os)
- `Harvard-Algorithmic-Trading-with-AI/` — sistema RBI completo (★448)
  - `research/` → fase R
  - `backtest/` → bb_squeeze_adx.py, template.py (Backtesting.py), data.py (yfinance)
  - `implement/` → bot.py (live BB Squeeze+ADX, 5x lev, ordini LIMIT), nice_funcs.py (lib condivisa: ask/bid/SMA/EMA/BB/posizioni)
- `Trading-Algos/` (TomData) — 19 strategie complete da video
  - trend_is_fren, capitulation_trade, buy_the_dip, breakout_wick_algo, first_hr_breakout,
    funding_arbitrage, liquidation_bot, quant_gpt, lowcapgem_algo, demand_zone_vol, fund_demand_bot,
    btc_etf, first_vs_lasthr_algo, futures_open, mexc_bots, HyperLiquid-Trading-Bots (arb.py)
  - NB: 7 CSV storici ETH saltati (nomi con ":" invalidi su Windows) — nei repo originali su GitHub

## Priorità 2 — Data layer (fonti dati per fattori Fase 3)
- `Hyperliquid-Data-Layer-API/` — 40+ endpoint (★113)
  - api.py (2025 righe), api_monitor.py
  - examples/ 01-38: liquidations, whales, orderflow, smart_money, CVD scanner, funding/OI, tick stream
  - ai_agents/: swarm_agent.py (6 modelli via OpenRouter), director_agent.py
  - docs/polymarket-profitable-traders.md
  - Richiede API key moondev.com per la maggior parte degli endpoint

## Priorità 3 — Altri bot di trading
- `Moon-Dev-AI-Trading-Battles/` — 6 modelli AI che tradeano $100 reali su Hyperliquid (battle_core, run_battle, watch_battle)
- `Limitless-Prediction-Market-Bots/` — bot prediction market (★59)
- `Polymarket-Trading-Bot-Examples-By-Moon-Dev/` — esempi Polymarket
- `housecoin-100x-bot/`, `housecoin-dollar-cost-average-bot` (repo vuoto 0KB, non clonato)
- `short-crypto-to-0-trading-bot/` — short in bear market
- `prize-picks-bot/` — DraftKings PrizePicks + API
- `Hibachi-Crypto-Exchange-Trading-Python-Examples/` — exchange Hibachi
- `Extended-Exchange-Crypto-Trading-Bot-Code---Examples/` — exchange Extended

## Priorità 4 — Varie / tooling
- `Moon-Dev-Code/` — 3 PDF accademici di strategie (jrfm, applsci, 2006 article)
- `YouTube-Strike-Analysis-With-OpenAI/` — analisi strike YouTube
- `espn-rundown-in-python/`, `Delete-OpenAI-Assistants-In-Bulk/`, `computer-cleaner-free-up-space/`,
  `remove-all-vowels-from-text-in-python/`, `custom-crypto-addresss/` (138MB, solana vanity),
  `learn-typescript-from-python/`

## Collegamento a trading-os
Il gap noto del nostro sistema: research layer disconnesso da execution (double-track).
Studiare in ordine: (1) Harvard RBI per il flusso R→B→I, (2) Trading-Algos per idee fattori
concreti da testare in Fase 3, (3) Hyperliquid-Data-Layer per dati alternativi (liquidations,
whales, CVD) non disponibili su yfinance/ccxt.
