# MoonDev Repos — Note di studio per trading-os

Studio completo di 19 repo MoonDev. Obiettivo: colmare il gap research↔execution
e trovare fattori con edge reale per Fase 3 di trading-os.

---

## P1 — Harvard-Algorithmic-Trading-with-AI (RBI core) ★448

### Cosa è
Sistema didattico RBI: Research→Backtest→Implement. 3 fasi in cartelle separate.
Filosofia Jim Simons: solo robot tradano, zero emozione.

### Come è strutturato
- `research/README.md` — metodologia: Google Scholar, libri (Lopez de Prado, Carver, Douglas),
  podcast (Chat with Traders), Quantopian archives. Processo: broad→narrow, documenta tutto,
  cross-reference, risk-first.
- `backtest/` — `data.py` (fetch Hyperliquid candleSnapshot, 5000 bar max, fix timestamp offset bug),
  `template.py` (Backtesting.py, BollingerBandBreakoutShort, optimize su window/std/TP/SL),
  `bb_squeeze_adx.py` (BB squeeze + Keltner + ADX, squeeze release → breakout direction)
- `implement/` — `nice_funcs.py` (lib condivisa: ask_bid, get_sz_px_decimals,
  adjust_leverage_usd_size, get_ohlcv2, get_position, limit_order),
  `bot.py` (bot live: 5x lev, $10 size, LIMIT orders, TP 5%/SL 3%, schedule.every(1).minutes,
  loop gestione errori con traceback)

### Cosa rubiamo per trading-os
1. **RBI come mental model** — il nostro gap è che research (fattori) e execution (WF backtest)
   sono disconnessi. RBI impone: prima research, poi backtest, poi implement. Noi abbiamo
   saltato la research phase andando diretti al ML.
2. **bb_squeeze_adx come fattore Fase 3** — volatility contraction (BB dentro Keltner) + ADX > 25
   → breakout. Noi abbiamo bollinger_pctb e adx in factors.py ma non il squeeze detection
   (BB dentro Keltner). Implementabile come fattore binario.
3. **nice_funcs pattern** — lib condivisa per exchange ops. Noi non abbiamo un layer del genere
   (SignalBridge mai attivato). Utile se arriviamo a paper trading.
4. **Backtesting.py optimize()** — più semplice del nostro Optuna per prototipi rapidi.
   MoonDev lo usa per scan veloce prima di passare al backtest serio.

### Decisione
- Adottare bb_squeeze come fattore Fase 3 (complementare a volume_z + adx)
- nice_funcs pattern come riferimento per futuro execution layer
- RBI mental model per roadmap: research phase esplicita prima di modellare

---

## P1 — Trading-Algos (TomData, 19 strategie)

### Cosa è
19 strategie da video YouTube, ognuna in cartella con README + backtest.py.
Qualità variabile: alcune pseudocode non funzionanti, altre operative.

### Valutazione per fattore Fase 3

| Strategia | Logica | Fattore testabile? | Edge plausibile? | Verdetto |
|-----------|--------|-------------------|------------------|----------|
| trend_is_fren | Trend 6h, durata media trend | No (pseudocode, shift(1) nel next()) | Basso | SKIP |
| capitulation_trade | Volume spike daily ETH → long | Sì: volume_spike_multiplier | Medio (mean reversion) | FORSE |
| buy_the_dip | Dip 20% da high → long, TP 10% | Sì: drawdown from high | Medio | FORSE |
| breakout_wick | Breakout 5min + wick 3 bar → buy | Complesso, intrabar, 15min | Basso su 1h | SKIP |
| first_hr_breakout | QQQ prima ora → BTC long/flat | Sì: cross-asset session | Alto (seasonality) | SÌ |
| first_vs_lasthr | QQQ mattina vs chiusura | Sì: session momentum | Medio | FORSE |
| funding_arbitrage | Long low funding, short high funding | Sì: funding rate spread | ALTO | SÌ ★ |
| liquidation_bot | Volume spike 10x + price down → buy near spike | Sì: liq cascade reversal | ALTO | SÌ ★ |
| quant_gpt | EMA 9/21 crossover + RSI 30/70 | Già abbiamo (ema, rsi in factors.py) | Basso | SKIP |
| lowcapgem | CoinGecko trending → website | Non un factor (screening) | N/A | SKIP |
| demand_zone_vol | Demand zone 30bar + vol spike 2x → buy | Sì: support + volume | Medio | FORSE |
| fund_demand_bot | Funding < -22 → long, > 14 → short | Sì: funding rate extremum | ALTO | SÌ ★ |
| btc_etf | News monitoring ETF approval | Non quantitative | N/A | SKIP |
| futures_open | Domenica 20:45 long, 23:45 close | Sì: time-based seasonality | Medio | FORSE |
| mexc_bots | VWAP su MEXC | VWAP già testabile con nostri dati | Basso | SKIP |
| arb.py | Funding arb BTC/ETH su Hyperliquid | Sì: funding spread + HL nice_funcs | ALTO | SÌ ★ |
| coinglass-liq | Fetch liq data da Coinglass | Data source, non strategy | N/A (data) | DATA |

### Shortlist 5 fattori con edge plausibile per Fase 3
1. **FUNDING RATE EXTREMUM** (fund_demand_bot + funding_arb + arb.py)
   - Logica: funding rate estremamente negativo → long (short squeeze), estremamente positivo → short
   - Dato: Hyperliquid funding via MoonDev API, o Binance via CCXT
   - Perché edge: funding negativo estremo = overcrowded shorts = squeeze risk. Meccanismo economico reale.
   - Implementazione: aggiungere `funding_rate` e `funding_z` a factors.py

2. **LIQUIDATION CASCADE REVERSAL** (liquidation_bot + coinglass + Ideas.md)
   - Logica: spike di liquidazioni unilaterali → reversal (cascade exhaustion)
   - Dato: MoonDev API get_liquidations / get_all_liquidations (multi-exchange)
   - Perché edge: liquidazioni forzano chiusure → overshoot → mean reversion
   - Implementazione: `liq_volume_z` e `liq_long_short_ratio` come fattori

3. **BB SQUEEZE** (RBI bb_squeeze_adx)
   - Logica: BB dentro Keltner (volatility contraction) + squeeze release + ADX > 25 → breakout
   - Dato: OHLCV nostri (già disponibile)
   - Perché edge: volatility contraction precede espansione. Confermato in letteratura.
   - Implementazione: `bb_squeeze` (bool) + `bb_squeeze_release` (bool) in factors.py

4. **ORDER FLOW / CVD DIVERGENCE** (Hyperliquid API orderflow + CVD scanner)
   - Logica: price up ma CVD down → divergence → reversal
   - Dato: MoonDev API get_orderflow / get_imbalance
   - Perché edge: cumulative delta rivela direzione reale del flow vs prezzo
   - Implementazione: `cvd` e `cvd_price_divergence` come fattori (richiede MoonDev API)

5. **SESSION SEASONALITY** (first_hr_breakout + futures_open)
   - Logica: pattern ricorrenti in specifici time slot (futures open, prima ora US)
   - Dato: OHLCV con timestamp (già disponibile)
   - Perché edge: flussi ricorrenti (institutional, settlement) in specifici orari
   - Implementazione: `hour_of_day` e `day_of_week` come feature categoriche

### Implementare top fattore
Priorità: FUNDING RATE (dato disponibile via CCXT, edge economico forte, semplice da testare).
Dopo: BB SQUEEZE (nessun dato esterno richiesto, veloce da implementare).

---

## P2 — Hyperliquid-Data-Layer-API (data layer) ★113

### Cosa è
40+ endpoint API su dati Hyperliquid: liquidations, whale positions, orderflow, smart money,
HLP sentiment, multi-exchange liquidations, HIP3 (stocks/commodities).
Richiede MOONDEV_API_KEY (gratuita su moondev.com).

### Come è strutturato
- `api.py` (2025 righe) — classe MoonDevAPI, ~60 metodi get_*
- `examples/` 01-38 — ognuno standalone con output rich terminal
- `ai_agents/` — swarm_agent.py (6 modelli OpenRouter), director_agent.py (orchestrazione)
- `docs/polymarket-profitable-traders.md`
- `examples/Ideas.md` — 15+ idee alpha extraction per ogni endpoint

### Endpoint utili per trading-os Fase 3
| Endpoint | Metodo | Dato | Fattore potenziale |
|----------|--------|------|-------------------|
| /api/liquidations/{tf} | get_liquidations | HL liq per timeframe | liq_volume_z, liq_ls_ratio |
| /api/all_liquidations/{tf} | get_all_liquidations | Multi-exchange liq | liq_global_cascade |
| /api/orderflow | get_orderflow | Buy/sell pressure, CVD | cvd, cvd_divergence |
| /api/imbalance/{tf} | get_imbalance | Buy/sell imbalance | imbalance_ratio |
| /api/smart_money/signals | get_smart_money_signals | Smart money positioning | smart_money_signal |
| /api/hlp/sentiment | get_hlp_sentiment | Z-score retail positioning | hlp_z (squeeze signal) |
| /api/positions/all | get_all_positions | Whale positions 182 sym | whale_crowding |
| /api/position_snapshots | get_position_snapshots | Positions near liq | near_liq_cluster |
| /api/candles/{coin} | get_candles | OHLCV 80 symbols | (conferma dati nostri) |
| /api/prices | get_prices | 224 prices realtime | cross_coin_corr |

### Pattern AI
- swarm_agent.py: 6 modelli (Claude, GPT-4o, Qwen, GLM, Gemini, DeepSeek) in parallelo via OpenRouter
  con ThreadPoolExecutor. Pattern replicabile con nostro VSLLM/OpenRouter.
- director_agent.py: LLM che conosce tutti gli endpoint, propone piani di analisi,
  distribuisce dati al swarm. Simile al nostro ai_cycle_v2 ma più strutturato.

### Decisione
- Endpoint da integrare in trading-os (priorità):
  1. get_liquidations (fattore liq cascade)
  2. get_orderflow + get_imbalance (fattore CVD)
  3. get_hlp_sentiment (fattore retail squeeze)
  4. get_smart_money_signals (fattore smart money)
- Richiede MOONDEV_API_KEY → verificare se gratuita o a pagamento
- Non integrare swarm_agent (abbiamo già VSLLM routing, è ridondante)

---

## P3 — Altri bot di trading

### Cosa sono
Bot per exchange alternativi, prediction market, battles AI. Pattern operativi ricorrenti.

### Moon-Dev-AI-Trading-Battles
6 modelli AI (Claude Opus, GPT-5.6, Gemini 3.1, Grok 4.5, Kimi K3, DeepSeek V4 Pro)
su $100 reali Hyperliquid, 1000 decisioni, 1x lev, BTC only.
Architettura: battle_core (shared logic), run_battle (arena 1 processo), watch_battle (watchtower),
preflight (6-check go-live), heartbeat relay (outbound-only POST).
Pattern interessante: indicatori hand-rolled (_sma/_rsi) non TA-Lib per riproducibilità cross-machine.

### Pattern ricorrenti da adottare
1. **nice_funcs pattern** (RBI + HL bots + Hibachi + Extended + short-bot):
   lib condivisa con ask_bid, get_position, limit_order, adjust_leverage, cancel_all_orders,
   pnl_close, kill_switch. Ogni exchange ha la sua variante ma struttura identica.
   → Per trading-os: creare `execution/exchange_client.py` con questa interfaccia
   quando arriviamo a paper trading.

2. **schedule loop** (RBI bot + arb.py + tutti i bot):
   `schedule.every(N).minutes.do(bot)` + `while True: schedule.run_pending()`
   → Pattern semplice per bot live. Noi usiamo NautilusTrader LiveEngine (più robusto)
   ma per prototipi rapidi questo basta.

3. **Heartbeat + Watchtower** (AI Battles):
   Bot headless pubblica heartbeat ogni 5s, watchtower su altra macchina allarma se stale.
   → Per trading-os live: implementare heartbeat in run_cycle.sh + alert Telegram
   (abbiamo già Telegram bot attivo).

4. **DCA Acceleration** (housecoin-100x):
   Below 20-SMA → aggressive buy, above → selective at daily lows.
   → Pattern sizing dinamico basato su regime. Noi abbiamo regime detection (Hurst/ADX)
   ma non lo usiamo per sizing. Idea per Fase 3: sizing ∝ confidence regime.

5. **Multi-exchange liquidation aggregation** (MoonDev API):
   HL + Binance + Bybit + OKX in un unico endpoint.
   → Per trading-os: usare get_all_liquidations per fattore liq globale, non solo 1 exchange.

### Altri bot (verdetto)
- Polymarket/Limitless: prediction market, non rilevanti per trading-os (crypto perp)
- Hibachi/Extended: exchange alternativi, stesso nice_funcs pattern
- short-crypto-to-0: bear market short, nessun fattore nuovo
- prize-picks: sports, non rilevante

---

## P4 — Materiale vario

### Moon-Dev-Code/strategy_pdfs/
3 PDF accademici:

1. **jrfm-12-00067** (Kyriazis 2019) — Survey EMH in crypto.
   Trova: Bitcoin inefficiente ma sempre più efficiente nel tempo → edge fade.
   Metodi: R/S, DFA, Hurst, GARCH.
   Per trading-os: conferma che edge esiste ma svanisce. Walk-forward essenziale.
   Il nostro Hurst in factors.py è giusto ma dobbiamo monitorarne il decay.

2. **applsci-10-01506** (Sattarov 2020) — DRL per crypto trading.
   Double crossover strategy (golden/death cross) + DRL.
   Risultato: 14.4% profit BTC in 1 mese con DRL.
   Per trading-os: conferma approccio ML. Golden/death cross è banale (già testato implicitamente
   nelle nostre EMA). DRL (FinRL) è nella nostra roadmap Fase 3.5.

3. **2006-article-p201** (Delfabbro 2021) — Psicologia crypto trading.
   FOMO, overconfidence, 24/7 availability come risk factor.
   Non tecnico. Utile come contesto per risk management mentale, non per codice.

### Altri
- learn-typescript-from-python: 2433 file, solo consultazione. SKIP.
- YouTube-Strike-Analysis: analisi strike YouTube con OpenAI. Non rilevante.
- Tool minori (computer-cleaner, remove-vowels, espn-rundown): non rilevanti.

---

## Sintesi: cosa portiamo in trading-os

### Fattori Fase 3 (priorità ordinata)
1. **funding_rate + funding_z** — edge economico forte, dato via CCXT/Hyperliquid
2. **bb_squeeze + bb_squeeze_release** — nessun dato esterno, veloce
3. **liq_cascade_z** — dato via MoonDev API, edge mean-reversion
4. **cvd + cvd_divergence** — dato via MoonDev API, edge order flow
5. **session_seasonality** (hour_of_day, day_of_week) — dato interno, seasonality

### Gap research↔execution (colmato)
RBI ci dice: research phase esplicita prima di modellare. Noi abbiamo saltato diretti
al LightGBM. Fix: per ogni fattore sopra, documentare:
- Ipotesi economica (perché dovrebbe funzionare)
- Fonte dati
- Implementazione factors.py
- Test IC (information coefficient) prima di metterlo nel modello

### Execution layer (riferimento futuro)
nice_funcs pattern come blueprint per `execution/exchange_client.py`:
ask_bid, get_position, limit_order, adjust_leverage, pnl_close, kill_switch.
Non implementare ora (Fase 4), ma salvato come riferimento.

### Monitoring (riferimento futuro)
Heartbeat + watchtower pattern per bot live autonomo.
Abbiamo già Telegram bot → integrare alert su stale/missed-round.

---

## Collegamento video (item 6.2)

I repo MoonDev derivano da video YouTube sul canale @moondevonyt.
Associazioni video→repo da studiare con hermes-video-watch quando serve spiegazione:

| Repo | Video YouTube (URL nel README) | Quando guardare |
|------|-------------------------------|-----------------|
| Harvard-RBI | https://youtu.be/Vu62g43_1aE | Per capire flusso R→B→I e come MoonDev spiega il research phase |
| Trading-Algos (tutti) | https://www.youtube.com/@moondevonyt | Ogni strategia ha un video dedicato. Guardare prima di implementare il fattore corrispondente |
| Hyperliquid-Data-Layer | Non ha video unico — endpoint documentati su moondev.com/docs | Consultare docs quando si integra un endpoint |
| AI-Trading-Battles | https://moondev.com/ai (live leaderboard) | Per pattern architetturale heartbeat/watchtower |
| Hibachi/Extended | Video sul canale | Per pattern nice_funcs su exchange alternativi |

Priorità video:
1. RBI core (per ricerca fattori) — prima di implementare bb_squeeze
2. funding_arbitrage + liquidation_bot — prima di implementare funding_rate e liq_cascade_z
3. AI Trading Battles — per pattern monitoring live

URL specifici nei README di ogni repo. Usare skill hermes-video-watch per analisi.
