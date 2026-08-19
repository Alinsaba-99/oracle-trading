# DOMANDE APerte — Handoff per approfondimenti

Generato dopo studio completo 19 repo MoonDev + implementazione fattori Fase 3.
Tutto quello che NON so e che richiede ricerca/decisione/experiment ulteriore.

---

## D1 — Funding rate: come ottenere lo storico?

Ho implementato `funding_rate` e `funding_z` in factors.py, ma il dato NON è nei
nostri parquet OHLCV. Domande:

- D1.1 Hyperliquid funding rate storico: l'API MoonDev (`get_candles`) include il funding?
  O serve un endpoint separato? Il README menziona `/api/prices` con funding ma sembra realtime,
  non storico.
- D1.2 CCXT ha `fetch_funding_rate_history()` per Binance/Bybit. Quale exchange usiamo
  per il backtest? I nostri dati sono Binance (data/binance/btc-usdt/1h/).
- D1.3 Il funding rate su Binance è ogni 8 ore (00/08/16 UTC). Il nostro timeframe è 1h.
  Come allineiamo? Forward-fill? Interpolazione? Questo cambia il significato del fattore.
- D1.4 Funding rate negativo estremo = short squeeze risk. Ma qual è la soglia?
  MoonDev usa -22 (fund_demand_bot) e -0.5% (funding_arb). Qual è quella giusta per crypto
  su 1h timeframe? Va ottimizzata o fissata a priori?
- D1.5 Il funding rate è disponibile solo per perpetual futures, non spot.
  I nostri dati sono spot (BTC/USDT). Dobbiamo scaricare anche i perp?

## D2 — BB Squeeze: validazione del segnale

Ho implementato `bb_squeeze` (BB inside Keltner). Domande:

- D2.1 Il fattore è binario (squeeze ON/OFF). Ma il modello LightGBM come lo usa?
  Come feature binaria o come filtro (entry solo quando squeeze_release)?
- D2.2 MoonDev usa `squeeze_released` (transizione ON→OFF) come trigger di entry.
  Io ho solo `bb_squeeze` (stato attuale). Serve anche `bb_squeeze_release`?
  Implementarlo richiede shift(1) e confronto — banale ma non l'ho fatto.
- D2.3 Il BB squeeze da solo non ha edge (identifica compressione, non direzione).
  Va combinato con ADX > 25 (MoonDev) o con breakout direction. Come lo combiniamo
  nel modello? Come feature separata o come interazione?
- D2.4 Quali parametri BB/Keltner? MoonDev usa window=20, std=2.0, kc_mult=1.5.
  Sono ottimali per crypto 1h o vanno ottimizzati?

## D3 — MoonDev API: API key e limiti

- D3.1 La API key su moondev.com è gratuita o a pagamento? Il README dice "free API key"
  ma alcuni endpoint (near-liquidation, tick stream) sembrano premium.
- D3.2 Quali endpoint hanno storico vs solo realtime? Per backtest serve storico:
  liquidations passate, orderflow passato, CVD storico. Il README non è chiaro.
- D3.3 Rate limits? Non documentati nel README. Per backtest su 6 mesi di dati 1h
  (~4300 bar) quanti endpoint posso chiamare?
- D3.4 Formato dati ritornato? JSON nested con stats e per-coin breakdown.
  Come lo trasformo in Series allineata al mio OHLCV 1h?

## D4 — Liquidation cascade: edge reale?

- D4.1 MoonDev dice "liquidation exhaustion → reversal" ma è un'ipotesi.
  Esiste letteratura accademica che conferma edge delle liquidazioni come segnale?
  Il paper di Kyriazis non ne parla.
- D4.2 Le liquidazioni sono disponibili solo su Hyperliquid (via MoonDev API) o anche
  su Binance? Coinglass ha dati multi-exchange ma l'API free ha limiti.
- D4.3 Le liquidazioni sono eventi rari. Su 6 mesi di dati 1h, quanti eventi
  significativi (>10x volume) ci sono? Abbastanza per statistiche?
- D4.4 Il fattore `liq_cascade_z` richiede volume di liquidazioni per timeframe.
  Ma il volume di liq non è la stessa cosa del volume di trading. Come li allineo
  al mio OHLCV?

## D5 — CVD / Order flow: fattore complesso

- D5.1 CVD (Cumulative Volume Delta) = buy volume - sell volume cumulativo.
  Richiede tick-by-tick data, non OHLCV. Dove lo prendo?
  MoonDev API ha `get_orderflow` ma è realtime.
- D5.2 Per backtest, serve storico CVD. Esiste un modo per ricostruirlo da OHLCV?
  No — serve proprio tick data. Questo significa che non posso backtestare
  CVD con i dati attuali.
- D5.3 Se scarico tick data storico da Binance (CCXT ha `fetchTrades`), quanto pesa?
  6 mesi di BTC tick = GB? E il tempo di download?
- D5.4 CVD divergence (price up, CVD down) è un concetto order-flow classico.
  Ma su crypto 24/7, quanto è affidabile? La letteratura è scarsa.

## D6 — Session seasonality: robustezza

- D6.1 Il pattern "futures open domenica 20:45" (MoonDev) è specifico del mercato
  tradizionale (CME futures). Su crypto 24/7, ha senso? O è solo un artifact?
- D6.2 "First hour breakout QQQ → BTC" richiede dati QQQ + BTC allineati.
  Dove prendo gli storici QQQ gratuiti? Polygon.io richiede API key.
- D6.3 L'ora del giorno come feature categorica: il modello la gestisce bene?
  LightGBM può fare label encoding, ma serve one-hot? E non è stagionalità
  ma solo bias orario — quanto è stabile OOS?
- D6.4 Crypto 24/7 vs stock market hours: l'effetto session è più debole su crypto.
  Esistono studi che lo confermano?

## D7 — Walk-forward con nuovi fattori

- D7.1 I nuovi fattori (bb_squeeze, funding_z) hanno NaN per le prime ~168 bar
  (funding) o ~60 bar (hurst). Il walk-forward gestisce i NaN? LightGBM sì,
  ma cambiano le fold boundaries?
- D7.2 Il funding_rate non è nei parquet attuali. Devo scaricarlo e mergearlo
  prima di poter fare walk-forward. Questo richiede:
  a) scaricare funding storico da CCXT/Binance
  b) allinearlo al timestamp OHLCV 1h
  c) salvarlo in parquet
  d) modificare compute_features per mergearlo
  Quanto tempo? Che script serve?
- D7.3 Il bb_squeeze è calcolabile subito (solo OHLCV). Posso fare un walk-forward
  solo con bb_squeeze aggiunto ai 10 fattori esistenti, senza funding?
  Sì — è il test più rapido. Va fatto prima.
- D7.4 Il walk-forward attuale (4 fold, 2600 train / 500 test) è sufficiente
  per validare 1 nuovo fattore? O serve più dati? I 6 mesi di BTC 1h
  = ~4300 bar totali. 2600+500 = 3100. Ne abbiamo abbastanza?

## D8 — HLP Sentiment / Smart money: fattori opachi

- D8.1 HLP sentiment z-score = retail positioning. Ma "retail" su Hyperliquid
  è chi? HLP è il market maker protocol. Z-score alto = retail long o short?
  Non è chiaro dalla doc.
- D8.2 Smart money rankings: top 100 vs bottom 100. Ma come lo uso come fattore?
  È un punteggio per wallet, non per timestamp. Devo aggregare?
  Es: % di smart money long su BTC in questo momento.
- D8.3 Questi dati sono realtime only. Per backtest storico non si possono usare.
  Quindi sono fattori solo per live/paper trading, non per backtest. Conferma?

## D9 — Execution layer (nice_funcs pattern)

- D9.1 nice_funcs usa hyperliquid-python-sdk (eth_account, Info, Exchange).
  Noi usiamo NautilusTrader. Come si collegano? NautilusTrader ha un adapter
  per Hyperliquid? O serve un adapter custom?
- D9.2 MoonDev usa ordini LIMIT a bid/ask. Noi usiamo ordini market nel backtest.
  Questo cambia i risultati (slippage). Come modelliamo il slippage nel backtest?
- D9.3 Il pattern schedule.every(1).minutes è primitivo. NautilusTrader LiveEngine
  ha un event loop. Come si integra il heartbeat/watchtower pattern?
- D9.4 Il kill_switch di MoonDev chiude tutto. Noi abbiamo risk gates R1-R4
  nella roadmap. Ma non sono implementati. Quando li costruiamo?

## D10 — AI Trading Battles: replicabilità

- D10.1 MoonDev hand-rolla SMA e RSI invece di TA-Lib per riproducibilità.
  Noi usiamo implementazioni custom in factors.py (non TA-Lib). Bene.
  Ma il nostro hurst è R/S, MoonDev non lo usa. Sono comparabili?
- D10.2 Il battle dà a 6 modelli lo stesso snapshot e misura chi decide meglio.
  Potremmo usare questo pattern per valutare i nostri fattori?
  Es: dare a N modelli lo stesso dataset + fattori e vedere chi performa.
- D10.3 Il battle usa 72 candle + bid/ask + RSI/SMA come prompt.
  Noi abbiamo 13 fattori. Come si presenta questo a un LLM?
  Tabella CSV? Quale formato?

## D11 — Dati: gap e qualità

- D11.1 I nostri parquet sono 6 mesi (gen-lug 2026). Per walk-forward robusto
  serve 1-2 anni. CCXT può scaricare più storia? Binance ha dati dal 2019.
- D11.2 Qualità dati: hai script di data quality check?
  MoonDev no. Il nostro scripts/health_check.py esiste ma è deleted.
  Va ripristinato.
- D11.3 I dati ETH hanno 7 CSV con ':' nel nome (invalidi su Windows).
  È un problema del filesystem o del download script? Come fix?

## D12 — Modelli: alternative a LightGBM

- D12.1 LightGBM non ha trovato edge OOS (Fase 1). Il problema è il modello
  o i fattori? Se aggiungo bb_squeeze, cambia qualcosa?
  Probabile che senza fattori con edge, nessun modello trova edge.
- D12.2 MoonDev usa DRL (FinRL) nel paper applsci. Vale la pena provare
  prima di avere fattori con edge? O è premature optimization?
- D12.3 Il battle usa LLM come decisore (non ML tradizionale).
  Potremmo usare VSLLM come signal generator invece di LightGBM?
  È un'idea, ma non è backtestabile facilmente.

## D13 — Processo: research phase esplicita

- D13.1 RBI impone research phase prima di backtest. Noi l'abbiamo saltata.
  Come si formalizza? Documento per ogni fattore con: ipotesi, fonte dato,
  formula, IC atteso, test?
- D13.2 L'IC (Information Coefficient) va misurato prima di mettere il fattore
  nel modello. Come si calcola? Correlazione (Spearman) tra fattore e forward return.
  Serve uno script.
- D13.3 Quanti fattori con edge servono per giustificare un nuovo walk-forward?
  MoonDev non lo dice. Regola empirica: almeno 3 fattori con IC > 0.03?
- D13.4 Il decay del edge (paper Kyriazis: crypto diventa più efficiente).
  Come lo monitoriamo? Rolling IC nel tempo?

## D14 — Polymarket / Prediction market

- D14.1 Polymarket e Limitless sono prediction market, non crypto perp.
  MoonDev ha bot per entrambi. Per trading-os (crypto perp) sono rilevanti?
  Solo come dato alternativo (sentiment)?
- D14.2 Il docs/polymarket-profitable-traders.md non l'ho letto in dettaglio.
  Contiene pattern trasferibili? Va letto prima di scartare.

## D15 — TypeScript / Tooling

- D15.1 learn-typescript-from-python ha 2433 file. Se serve convertire
  qualche tool MoonDev da TS a Python (es. Polymarket SDK è TS), può servire.
  Per ora SKIP ma tenerlo a mente.
- D15.2 Il MoonDev API ha un endpoint AI chat (OpenAI-compatible).
  Potremmo usarlo come backend alternativo a VSLLM? O è un conflitto?

---

## Priorità approfondimenti

1. **D7.3 + D2** — walk-forward con bb_squeeze (test più rapido, solo OHLCV)
2. **D1 + D7.2** — scaricare funding rate storico da Binance via CCXT
3. **D3.1-D3.4** — verificare MoonDev API key gratuita e endpoint storici
4. **D13.1-D13.3** — formalizzare research phase (IC test, documentazione fattori)
5. **D11.1** — scaricare più storia dati (1-2 anni)
6. **D4 + D5** — liquidation cascade e CVD richiedono dati non OHLCV
7. **D9** — execution layer (solo quando arriviamo a Fase 4 paper trading)
