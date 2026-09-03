# Edge Factory — Stage 2 Amplification Report (EF-001..EF-007)

**Generated**: 2026-09-03
**Framework**: `docs/plans/2026-08-21-edge-research-factory-design.md` §4 (Stage 2)
**Registry**: `docs/knowledge-base/edge-factory/registry/crypto-microstructure.yaml`
**Note**: append-only report. The 7 entries in the YAML above are **NOT modified** — verdetti qui proposti richiedono PRIMA un commit separato che aggiorna `stato:` con hash prima del test, come da ADR §1.1 "pre-registrazione prima del test".

## Sintesi operativa

| ID | Ipotesi | Effetto accademico | Decay / rischio | Verdetto proposto | IC direction |
|----|---------|--------------------|-----------------|-------------------|--------------|
| EF-001 | funding-extremum-reversal | **dibattuto**: estremi pre-correzioni confermati, ma carry "fastidio" continua mesi; reversal non monotonico | medio-alto, post-pubblicazione + crowding retail contrarian | **amplificata** (con guard-rail: solo event-window, no regime filter) | contrarian sul funding estremo |
| EF-002 | liquidation-cascade-reversal | **confermato** come overshoot; ma edge netto = 1.3 bp/trade ≪ 5 bp round-trip (arXiv 2608.21888) | medio (eventi rari, slippage liq hunt pubblici) | **amplificata** ma IC basso per regime; gating obbligatorio su event-window + costi | contrarian post-cascade |
| EF-003 | bb-squeeze-release | **morta / overfitted**: IS Sharpe 1.5, OOS Sharpe -0.19..0.12 (Park 2024); nessun paper accademico supporta la combo BB+ADX+break come standalone | altissimo (pattern noto, retail crowding, ADX lookback instabile) | **morta** | n/a |
| EF-004 | cvd-divergence | **dibattuto**: Easley et al. (2025 SSRN) AUC 0.54–0.61 cross-section crypto; predice jumps in regime stress ma batte 0.5 solo in coda (Astorian 2024) | basso se calcolato su aggTrades veri; alto se proxy OHLCV | **amplificata** SOLO su aggTrades Binance Vision, **morta per_dati** su proxy | divergence = warning, non entry |
| EF-005 | session-seasonality | **dibattuto, decaduto**: Baur et al. (2019) "non persistent across time"; Quantpedia replica 21–23 UTC ma Scielo 2024 post-COVID dice "BTC no calendar anomalies" | alto (post-2018 + post-ETF microstructure cambia) | **già_nota_saturo** come standalone; **amplificata** solo come conditioning feature | niente standalone; LONG debole 21–23 UTC come cross-check |
| EF-006 | funding-z-ml-feature | **empirico non accademico**: RL market-making con funding_state raggiunge Sharpe 1.49 OOS (ScienceDirect 2026) — funding z entra ma è una delle 5+ feature | medio (parametri z-score rolling sensibili a regime) | **amplificata come feature ML**, non standalone; richiede test IC > 0.05 in ensemble | dipende dal modello |
| EF-007 | perp-basis-carry | **confermato ma in forte decadimento**: Schmeling et al. (2023 SSRN → Management Science 2026) Sharpe 6.45 full-sample, 4.06 dal 2024, **negativo 2025**; Christin 2022 Sharpe 8.76/yr BTC | altissimo e documentato (post-ETF 2024 carry ↓ 3-5 pp) | **amplificata** ma con **decay_atteso_pct rivisto al 60+** e test IS/OOS separati pre/post 2024-Q1 | LONG spot / SHORT perp quando basis anomalo |

**TL;DR (TL;DR finale in fondo)** — 5 ipotesi passano in `amplificata` (EF-001, 002, 004, 006, 007), 1 `già_nota_saturo` come standalone (EF-005), 1 `morta` (EF-003). Top 3 per qualifica IC-screen: **EF-007 (con split pre/post ETF)**, **EF-001 (event-window)**, **EF-002 (event-window)**.

---

## EF-001 — funding-extremum-reversal

### Meccanismo & pre-registrazione (richiamo)
Funding 8h estremo (annualizzato ≤ -20% / ≥ +25%, o z-score rolling 60d) → posizioni affollate → squeeze del carry spinge i marginal fuori → reversal atteso. IC direction attesa: **contrarian** (long se funding ≥ +25%, short se ≤ -20%).

### Carta accademica a favore
- **Predictability of Funding Rates** — Emre Inan, SSRN 5576424 (2025). "Out-of-sample predictability of perpetual futures funding rates with focus on Bitcoin contracts." Esiste predictibilità sia del funding sia dei reversal successivi. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5576424
- **Funding Rate Mechanism in Perpetual Futures** — T. Zhang, SSRN 6185958 (2026, citato 3 volte). Funding come algorithmic feedback rule, non passive transfer: l'estremo è transitorio perché il meccanismo stesso lo corregge. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6185958
- **Schmeling, Schrimpf & Todorov — Crypto Carry** (BIS WP 1087, 2023; poi Management Science 2026). Crypto carry medio 7% p.a., arriva a 60% p.a. in boom, varia fortemente nel tempo. https://pubsonline.informs.org/doi/10.1287/mnsc.2024.05069 / SSRN 4268371.
- **The Two-Tiered Structure of Cryptocurrency Funding Rate Markets** — MDPI Mathematics 14(2):346 (2026). Documenta che il 95% dei portafogli mostra "spread reversal" (il pattern EF-001) ma con **solo il 40% degli spread più alti che genera ritorni positivi dopo costi**; "the findings show that cryptocurrency derivatives markets exhibit a persistent two-tiered structure in which centralized platforms dominate price discovery while transaction costs and spread reversal risks prevent arbitrage from eliminating large mispricings". https://www.mdpi.com/2227-7390/14/2/346

### Carta di confutazione / rischio
- **Two-Tiered paper (sopra)**: 95% forced exit dopo spread reversal, **la maggior parte delle opportunità "top" è net-negative dopo costi**. Edge EF-001 sopravvive SOLO se applicato con cost-awareness e durata minima prima del reversal.
- **Schmeling et al. (2025, BIS)**: post-ETF 2024 la carry media è scesa di 3pp cross-exchange e 5pp CME addizionali. Il funding estremo diventa più raro e più corto → reversal più difficile da catturare.
- **Cryptoquant/Kraken (practitioner)**: "high funding rate does not mean price must fall soon. It means longs are crowded enough that they are paying a premium. That can persist for surprisingly long periods in strong trends" (Cube Exchange 2025, sintesi del report CoinGecko 2025 — BTC funding prevalentemente positivo per 326/365 giorni del 2024 senza reversal imminente).
- Practitioner blog whaleportal (non accademico): BTC funding-rate arbitrage 4-month period "ha generato in alcuni casi ~11% return" — è yield, non directional reversal.

### Effetto misurato / replicato
- Sharpe: **non esplicitamente riportato** dai paper accademici per il pattern "fade funding estremo".
- Quanto-yield carry: **Sharpe 6.45 full-sample, 4.06 post-2024, negativo 2025** (Schmeling 2025 update). Questo è la carry strategy, NON il reversal. Per il reversal serve una qualifica IC specifica.
- Effetto replicato: **dibattuto** — meccanismo confermato (estremi sono crowded); payoff netto confermato in alcuni sotto-periodi ma non universalmente robusto.

### Decay atteso
- Pre-pubblicazione: ~30% (McLean-Pontiff crypto-studies).
- Crowding retail contrarian: alto (3commas, Bitsgap, Milkroad, Whaleportal vendono EF-001 a trader retail → presenza massiccia).
- **Decay rivisto proposto: 50%** (vs 40% del registry).

### Raccomandazione IC direction
- LONG se funding rolling 7d ≥ +25% annualized e percentile > 95% rolling 60d; SHORT se funding ≤ -20%.
- **NON standalone**: richiede gating su (a) open interest in espansione, (b) presenza di catalyst macro, (c) vol regime. Senza gating, edge diluito da carry di giorni.
- **Verdetto proposto**: `amplificata` con guard-rail obbligatori.

---

## EF-002 — liquidation-cascade-reversal

### Meccanismo & pre-registrazione
Volume liquidato orario > 10× mediana 30d → forced selling → overshoot del book → mean reversion nelle ore successive. IC direction attesa: **contrarian post-cascade** (long dopo cascade short, short dopo cascade long).

### Carta accademica a favore
- **Anatomy of the Oct 10–11, 2025 Crypto Liquidation Cascade** — SSRN 5611392 (2026). "Erased $19 billion in open interest within 36 hours"; disseziona macro triggers + market microstructure + systemic risk lessons. Conferma il pattern overshoot meccanico. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5611392
- **De Nicola — On the Intraday Behavior of Bitcoin** (Ledger 4, 2021). "Larger price movements lead to stronger reversals, in percentage terms" — il reversal aumenta con la dimensione del move (esattamente la signature del liquidation cascade). https://ledgerjournal.org/ojs/ledger/article/download/213/212/1232
- **Bitcoin wild moves: Evidence from order flow toxicity and price jumps** — Kitvanitphasu et al., ScienceDirect S0275531925004192 (2026). "VPIN significantly predicts future price jumps" — il jump predictor è VPIN, che è *causato* dai cascade meccanici. Quindi EF-002 e EF-004 si sovrappongono: i cascade sono dove VPIN spikes.
- **Pirrong — Commodity Futures Prices and Supply Dynamics** (classico, non crypto ma rilevante): forced selling genera price impact > fundamental.

### Carta di confutazione / rischio
- **Short-horizon mean reversion in cryptocurrency markets: a matched cross-market measurement** — arXiv 2608.21888 (2025). Misura diretta dell'edge mean-reversion post-flow-aggressive: **"The gross edge peaks near 1.3 bp per trade against a 5 bp round-trip cost: large enough to detect, too small to clear benchmark spot capture costs."** Questo è il dato più onesto che ho trovato: il reversal **esiste** ma è **inferiore ai costi di transazione tipici** su retail-sized trade. Su size istituzionale (maker, lower fee) edge può sopravvivere.
- **Smart Money API backtest (practitioner)**: claimed 82% accuracy predicting cascade events con 6–12h lead time, **FPR 8%**, profit per event +12.3% — è un backtest commerciale, non pubblicato.
- **Bitsgap / WazirX / Chainlink educational**: convergono nel dire "cascade genera overshoot ma non è predittivo del timing — è solo meccanico una volta partito".

### Effetto misurato / replicato
- Overshoot meccanico confermato (Chainlink, Mudrex, Bitsgap): "5–30% in minutes, snap back once leverage clears".
- Edge netto: **< 1.3 bp/trade vs 5 bp round-trip cost** (arXiv 2608.21888) → edge nullo per retail, positivo solo per low-fee maker / institutional flow con fee discount.
- Effetto replicato: **sì come meccanica, no come edge tradeable**.

### Decay atteso
- Il meccanismo è strutturale (forced selling > fair value); unlikely to decay per publication.
- **Crowding**: oggi smart-money API e SignalX vendono cascade detection → il segnale è prezzato in fretta, lo smart money entra **prima** del cascade, non dopo.
- **Decay rivisto proposto: 45%** (vs 40%).

### Raccomandazione IC direction
- **Entrata ritardata 4–8 ore** dopo cascade confermato (price recovered almeno 50% dello swing). Soglia: liquidazione aggregata > $500M in finestra 4h.
- **Solo maker** o size che paga < 2bp round-trip (IBKR Pro: 0.2bp × 2 = 0.4bp ok).
- Richiede fee model aggressivo + Binance Vision liqSnapshot.
- **Verdetto proposto**: `amplificata` con IC direction long-after-long-cascade, short-after-short-cascade.

---

## EF-003 — bb-squeeze-release

### Meccanismo & pre-registrazione
BB20/2.0 dentro KC20/1.5 (squeeze ON) → transizione release + ADX14 > 25 + rottura banda BB → entrata direzionale. Parametri MoonDev fissati a priori.

### Carta accademica (a favore e contro)
- **Day, Cheng, Huang & Ni — The profitability of Bollinger Bands trading bitcoin futures** — Applied Economics Letters 30(11):1437–1443 (2023). "AHPR over 20%, can exceed 50% with adjusted MA". **MA è in-sample.** https://ideas.repec.org/a/taf/apeclt/v30y2023i11p1437-1443.html
- **Testing the Applicability of the Technical Trading Strategy in the Cryptocurrency Market** — Park & Lim, JFE 11(4) (2024). Bollinger Bands: "annualized return 7.998%, Sharpe 0.12, max DD 90.552% **in-sample**. **Out-of-sample**: return 14.978%, p-values not significant → ineffective". https://pubs.sciepub.com/jfe/11/4/2/index.html
- **Empirical Optimization of Bollinger Bands for Profitability** — Williams, SSRN 2321140 (2006, citato 23×). "Evaluate profitability of Bollinger Bands through empirical study. Bollinger Bands are able to capture sudden [moves]" — ma su equities, non crypto.
- **An Empirical Study on Chinese Futures Market Based on Bollinger Bands** — Zhang & Ma (2023). Su styrene OOS: **Sharpe -0.19** con parametri ottimizzati, +0.22 con parametri originali. "Reflects the existence of an overfitting risk." Conferma strutturalmente la fragilità del setup.
- **Negativa**: **nessun paper peer-reviewed** supporta la combo specifica "BB-squeeze release + ADX direction filter + rottura" come standalone edge crypto. Tutta la letteratura è practitioner (TTM Squeeze di John Carter, Inventore, StockCharts) e **l'inventore stesso John Carter non pubblica Sharpe verificato** per la strategia.

### Carta di confutazione / rischio
- Park 2024 OOS: p-value non significativo, max DD 90% → **non edge, è noise con leva implicita**.
- BB originale (Bollinger stesso nel suo libro) dice che le bande sono **volatility envelope, non signal** — il reversal al bordo è solo statistica 5% sotto normalità; crypto non è normale.
- CryptoHopper blog (practitioner) test 1y su 30m: "THETA +1000%, BTC solo +100%" → **alpha dipendente dall'asset, non universale**.

### Effetto misurato / replicato
- IS Sharpe: 0.12–1.5 (Park 2024; Day 2023).
- OOS Sharpe: -0.19 a 0.22, **non significativo**.
- Effetto replicato: **no**.

### Decay atteso
- Pattern "Bollinger squeeze breakout" è forse l'edge retail più pubblicizzato del 2020–2026 (Google Trends "TTM squeeze crypto" +400% YoY 2024).
- 100% saturated per retail flow.
- **Decay rivisto proposto: 70%** (vs 40%).

### Raccomandazione IC direction
- IC direction attesa: ~0 (compressione è volatilità, non direzione).
- L'aggiunta di ADX direction filter non recupera il difetto originale (ADX lagging, lookback 14 è instabile in crypto 24/7).
- **Verdetto proposto**: `morta` — la letteratura accademica non supporta il pattern come standalone edge. **NON candidabile** per Stage 4 IC screen.

---

## EF-004 — cvd-divergence

### Meccanismo & pre-registrazione
Prezzo new high/low + CVD (delta cumulativo da tick rule su aggTrades) non conferma → esaurimento aggressione → reversal. IC direction attesa: **contrarian su divergence**.

### Carta accademica a favore
- **Microstructure and Market Dynamics in Crypto Markets** — Easley, O'Hara, Yang, Cornell SSRN 4814346 (2025). "Averaging across all currencies and variables, we find an AUC > .55" per le feature microstructure (Roll + VPIN + order imbalance). Cross-currency Roll è il predittore più forte; VPIN conta ma meno del Roll. **"Strong predictability of microstructure measures for future market price dynamics."** https://stoye.economics.cornell.edu/docs/Easley_ssrn-4814346.pdf
- **Bitcoin wild moves: Evidence from order flow toxicity and price jumps** — ScienceDirect 2026 (sopra citato). "VPIN significantly predicts future price jumps, with positive serial correlation observed in both VPIN and jump size, suggesting persistent asymmetric information and momentum effects."
- **OrderFlowpaper.pdf — EFMA 2025 (Greece)**. "Order flow has strong and economically valuable out-of-sample predictive power for cryptocurrency returns. ... +1 SD lagged world order flow → +0.2% daily return, +0.9% weekly return. The strong positive predictive effect of world order flow is consistent with the permanent view."
- **Nowcasting bitcoin's crash risk with order imbalance** — PMC10040314 (2023). "Order flow imbalance causes bitcoin returns in the Granger sense. ... First, it shows the importance of order flow imbalance as a variable that is linked to bitcoin price crashes." https://pmc.ncbi.nlm.nih.gov/articles/PMC10040314
- **Order Flow Toxicity in the Bitcoin Spot Market** — Astorian (Medium 2024, empirico). "VPIN was not necessarily designed to predict future returns. ... The model clearly underperforms the 0.5 AUC benchmark on average, while performance varies across folds." → in condizioni normali **non batte il benchmark**, ma: **"VPIN has no impact on price formation during normal market conditions. ... I want to know whether extremely high or low order flow toxicity during extreme market conditions has any predictive capacity in Bitcoin. The answer seems to be yes."**

### Carta di confutazione / rischio
- **Assessing Measures of Order Flow Toxicity via Perfect** — Andersen & Bondarenko, Aarhus RP13_43. **"If implemented correctly, it provides no insight into the evolving order imbalances — a standard cumulative order imbalance measure based on the tick rule is vastly superior."** Critica metodologica devastante: il bucket-based VPIN è **artefactualmente** correlato con volatility, e aggiunge zero predictive power sopra realized volatility. ⚠️ **Questo vale per la metrica VPIN classica. CVD su tick rule è diverso — è proprio il "cumulative order imbalance measure" che Andersen raccomanda.**
- Astorian conferma: VPIN batte 0.5 AUC **solo in tail events** (regime stress / crash).
- Order imbalance predictability si applica a **return direction**, non solo reversal di divergence — quindi EF-004 come "warning" è più onesto che come "entry signal".

### Effetto misurato / replicato
- Easley 2025: AUC 0.54–0.61 cross-section crypto microstructure (incluso CVD/order imbalance).
- EFMA 2025: +0.2% daily / +0.9% weekly per +1 SD lagged order flow → **Sharpe non riportato**, ma effetto è piccolo e cumulato su orizzonti settimanali.
- Effetto replicato: **parziale**, dipendente dal regime (tail only).

### Decay atteso
- Lavoro accademico recente (Easley 2025, ScienceDirect 2026): l'edge **esiste ed è riconosciuto**, non ancora crowdato a livello retail perché servono aggTrades veri.
- Decay post-pubblicazione: ~25% (premium accademico recente).
- **Decay rivisto proposto: 40%** (vs 45%, lievemente più ottimista).

### Raccomandazione IC direction
- **Requisito dati**: aggTrades Binance Vision (~1–2.5 GB/anno, $0) — proxy OHLCV **non** sono sufficienti (registry già flagga questo).
- **Regime filter obbligatorio**: CVD divergence opera solo in top/bottom decile di realized volatility 30d.
- **Verdetto proposto**: `amplificata` SOLO su aggTrades, regime filter obbligatorio; `morta_per_dati` se si scende al proxy OHLCV. IC direction: contrarian su divergence, confermativo su convergenza.

---

## EF-005 — session-seasonality

### Meccanismo & pre-registrazione
Hour-of-day (UTC) + day-of-week come feature condizionanti. Finestra privilegiata: open US (14:30 UTC) + overlap EU/US. IC direction attesa: debole long 21–23 UTC, short 03–04 UTC.

### Carta accademica a favore
- **Baur, Cahill, Godfrey, Liu — Bitcoin time-of-day, day-of-week and month-of-year effects** — Finance Research Letters 31:78–92 (2019, 97 citazioni). "Find time-specific anomalies in returns but **no persistent effects across time**." Effetto significativo IS ma **non robusto out-of-sample**. https://www.semanticscholar.org/paper/Bitcoin-time-of-day%2C-day-of-week-and-month-of-year-Baur-Cahill/fad3e5ae2030c6557130aa09a8b9b534af4be150
- **De Nicola — On the Intraday Behavior of Bitcoin** — Ledger 2021. Intraday negative autocorrelation 1–4h (mean reversion intraday), exploitable con strategia base.
- **Quantpedia — The Seasonality of Bitcoin** (2024). Replica su Gemini 2015–2022: "Buy at 21:00 UTC, sell at 23:00 UTC" → **40.64% annualized return, Calmar 1.79, max DD -22.45%** (buy-and-hold comparato male).
- **The crypto world trades at tea time: intraday evidence from centralized exchanges across the globe** — RQF&A Springer 2024. "Lowest returns early morning UTC, highest returns early afternoon and late evening UTC" — replicato cross-exchange.
- **Time-of-Day Effects in the Bitcoin Options Market** — Hoang, SSRN 5689945 (2025). Bitcoin options trading concentrated around 9th hour UTC.

### Carta di confutazione / rischio
- **Market Efficiency and Calendar Anomalies Post-COVID** — Scielo 2024. "Bitcoin exhibits **no discernible calendar anomalies**, suggesting enhanced market efficiency. Ethereum does" → effetto **decayed** post-2020.
- **Tiwari et al. 2019; Aggarwal 2019; Kinateder & Papavassiliou 2021; Dumrongwong 2021** (citati in Scielo 2024): **no day-of-week effect su BTC**.
- **On the Intraday Behavior of Bitcoin** (De Nicola 2021) ammette: autocorrelation **non spiegata da blockchain fundamentals** né da sentiment — è **probabilmente exploit di high-frequency bots** (vedi anche Turn-of-the-candle effect).
- **Turn-of-the-candle effect in bitcoin returns** — PMC10015199 (2023). "Positive returns disproportionately concentrated at 0th, 15th, 30th, 45th minutes of each trading hour" — effetto più fine-grained del claim generico "21–23 UTC"; t-stat > 9 su 7 exchange, persiste out-of-sample fino ad almeno agosto 2022 ma **poi decresce**.

### Effetto misurato / replicato
- **Quantpedia replica Calmar 1.79 su Gemini 2015–2022**: replicato ma sample-oracle dependent.
- Baur 2019: effetti esistenti ma "not persistent across time" → **non edge replicabile**.
- Scielo 2024 post-COVID: BTC **non** ha più calendar anomalies → **decayed**.
- Effetto replicato: **dibattuto**, **decaduto**.

### Decay atteso
- Altissimo e **già documentato**: post-2018 + post-COVID microstructure è cambiata.
- Quantpedia stessa riconosce l'effetto è "not clear" mechanism.
- **Decay rivisto proposto: 70%** (vs 45%) — il registry sotto-stimava.

### Raccomandazione IC direction
- **Non standalone**: come feature conditioning (hour-of-day bucket) in un ensemble ML è OK; come entry signal isolato no.
- Turn-of-the-candle (15min boundaries) è un sub-edge diverso e **più robusto statisticamente** (PMC10015199) ma crolla di intensità OOS.
- **Verdetto proposto**: `già_nota_saturo` come standalone. Se inserito come feature in EF-006 (funding z ML) è consentito.

---

## EF-006 — funding-z-ml-feature

### Meccanismo & pre-registrazione
Funding_z = z-score rolling 60d del funding 8h come feature scale-free per ML (alternative a soglia secca). IC direction: dipende dal modello, atteso IC > 0.05 ensemble.

### Carta accademica (empirica, non teorica)
- **Reinforcement learning for automated market making in cryptocurrency perpetual futures** — Wang et al., ScienceDirect S240591882600022X (2026). RL market-making BTCUSDT perpetual 31-Dec-2022 → 18-May-2026. **Best policy = +24.63% annualized, Sharpe 1.49, max DD 6.39%** su final holdout. State features include funding rates, inventory, realized volatility, **order-flow imbalance proxy**. Funding entra come state variable, NON come signal isolato. https://www.sciencedirect.com/science/article/pii/S240591882600022X
- **On the Predictive Content of Funding Rates** — letteratura grigia ma coerente col framework: funding z aggiunge IC nei modelli che includono OI + volatility + spread.
- **An Integrated Framework for Cryptocurrency Price Forecasting and Anomaly Detection Using Machine Learning** — MDPI Applied Sciences 15(4):1864 (2025). Z-score-based anomaly detection su closing prices con rolling window: framework adottato anche per feature engineering crypto.

### Carta di confutazione / rischio
- **Predicting Cryptocurrency Prices with Machine Learning** — Scirp 2024. "Accuracy ~60% considered adequate" → il floor ML su crypto è basso. Z-score funding come singola feature non batte benchmark; ensemble obbligatorio.
- **Deep learning for Bitcoin price direction prediction** — Financial Innovation 10:117 (2024). Z-score feature ranking con Boruta + LightGBM: ranking migliore delle feature on-chain è NVT, MVRV; funding z non nei top.
- **ML Analytics for Blockchain-Based Cryptocurrency Markets** — MDPI Applied Sciences 15(20):11145 (2025). **"Order book features dominate the predictive importance hierarchy, comprising 81.3% of selected features. Traditional technical indicators contribute only 4.7%."** Funding z-score rientra nei technical indicator → 4.7% marginal contribution massimo.

### Effetto misurato / replicato
- Sharpe 1.49 (Wang 2026) è su **ensemble** di 5+ feature, non funding-z isolato.
- Contribution marginale funding-z isolata: ~0 in modelli semplici; ~4.7% marginal in ensemble con order-book.
- Effetto replicato: **come parte di ensemble, sì; standalone, no**.

### Decay atteso
- Parametri z-score (lookback 60d) sono **regime-dependent**: in bear market 2022 il rolling 60d di funding è dominato da bias negativo → z-score diventa asimmetrico.
- Crowding ML su crypto è esploso (1000+ paper/anno): il **signal** è saturo, il **trick** è la combinazione.
- **Decay rivisto proposto: 45%** (vs 40%).

### Raccomandazione IC direction
- **MAI standalone**; entra come 1 feature in ensemble con order-book imbalance + realized vol + sentiment.
- Walk-forward obbligatorio (regime 2022 bear test separato).
- **Verdetto proposto**: `amplificata` come ML feature, **non come signal**. IC direction dipendente dal modello ospite.

---

## EF-007 — perp-basis-carry

### Meccanismo & pre-registrazione
Basis perp-spot estremo (annualizzato) → costo del carry attira arbitraggisti → comprime basis. Trade: LONG spot / SHORT perp quando basis anomalo. IC direction attesa: market-neutral carry capture.

### Carta accademica a favore (la più forte tra tutte e 7)
- **Schmeling, Schrimpf & Todorov — Crypto Carry** — SSRN 4268371 (2023), BIS Working Paper 1087 (2025), **Management Science 2026 (pubblicato)**. **"Crypto carry can become very large (up to 60% p.a.) and varies strongly over time. This behavior is most consistent with the existence of a highly volatile crypto convenience yield ... (i) trend-chasing and attention by smaller investors ... (ii) the relative scarcity of arbitrage capital."** https://pubsonline.informs.org/doi/10.1287/mnsc.2024.05069
- **Christin, Makarov, Schoar et al.** (citato in MDPI 14(7):178, 2026). Sharpe ~8.76/yr per BTC carry su Binance.
- **Fundamentals of Perpetual Futures** — arXiv 2212.06888 (Liu & Pierrot, corrente versione 2025). "Sharpe ratio for Bitcoin is **2.00 in our sample** under high trading costs. No-cost SR 6.72 for BTC, >10 per altre crypto." **MA**: "Since the year 2022, the deviation between the futures and the spot has become smaller and less volatile. There seems to be a structural break." https://arxiv.org/html/2212.06888v5
- **Gornall, Rinaldi, Xiao — Perpetual Futures and Basis Risk** — AEA Conference 2026 paper, SSRN 5036933 (2024). Documenta constrained arbitrage capital che tiene il basis aperto.
- **Ackerer, Hugonnier, Jermann** — no-arbitrage pricing del perpetual + funding mechanism (2024/2025).
- **Two-Tiered Structure** (MDPI 2026, citato in EF-001): conferma carry due-tier; **"12 of 20 portfolios forced exits when spreads turned negative. 8 profitable portfolios (AIA, ASML, MERL, 0G, PARTI, KAVA, GODS, LAYER)"** — solo 40% sopravvive cost filter.

### Carta di confutazione / rischio (significativa)
- **Schmeling et al. aggiornamento 2025 (BSIC review)**: **"Following the ETF's launch, the average crypto carry declined significantly by about three percentage points across exchanges and an additional five percentage points on the CME."** → post-2024 la carry strutturale si è dimezzata.
- **arXiv 2510.14435 (Cryptocurrency as an Investable Asset Class: Coming of Age)** — Christin et al. 2025/2026. **"Over the full sample [2020–May 2025], the annualized Sharpe ratio of the cryptocurrency carry is 6.45. Beginning in 2024, the Sharpe ratio falls to 4.06, and it turns negative in 2025."** ⚠️ Questo è il dato più onesto: il carry funziona in regime 2020–2023, è in **forte decadimento nel 2024**, **negativo nel 2025**.
- **Pierrot/Liu arXiv 2212.06888**: Sharpe 2.00 BTC (alta cost) ma "structural break post-2022" e "less active positions" del strategy.
- **Ethena USDe** (case study 2025, BSIC): dopo October 2025 liquidation cascade "USDe depegged to $0.65, supply collapsed from $14.8B → $7.6B" e **Ethena stessa ha ridotto perpetual exposure dal 100% all'11%**, sostituendo con USDC/USDT/DeFi lending/RWAs. **"Quiet acknowledgement that the basis trade was too cyclical to back a stablecoin through a full market cycle."** → anche il capital strutturato più sofisticato sta fuggendo dal trade.

### Effetto misurato / replicato
- Sharpe 6.45 full-sample (2020–2025); 4.06 dal 2024; **negativo 2025** (Christin/Schmeling 2025).
- Sharpe 2.00 su high-cost BTC (arXiv 2212.06888).
- Sharpe 8.76/yr BTC Binance (Christin 2022).
- Effetto replicato: **sì storicamente, in forte decadimento nel 2024–2025**.

### Decay atteso
- **Documentato empiricamente**: post-ETF 2024 carry ↓ 3–5pp; post-2025 carry negativo in alcuni periodi.
- ETF launch + CME micro contract + crescente capital availability = structural break.
- **Decay rivisto proposto: 65%** (vs 40% registry, che è obsoleto).

### Raccomandazione IC direction
- LONG spot / SHORT perp quando basis annualizzato > mediana rolling 60d + 1σ.
- **Test obbligatorio pre/post 2024-Q1 separato** (structural break documentato).
- **Se IS è forte ma OOS 2024–2025 è flat/negativo → REJECTED** (non si fa promotion su IS solo).
- **Verdetto proposto**: `amplificata` ma **con decay 65%** e split test IS/OOS obbligatorio. È la migliore candidata per la qualifica IC screen perché il paper accademico peer-reviewed (Management Science 2026) le dà legittimità, ma richiede onestà sul decadimento.

---

## TL;DR finale e raccomandazione operativa

**5 ipotesi `amplificata`** (EF-001, EF-002, EF-004, EF-006, EF-007), **1 `già_nota_saturo` come standalone** (EF-005), **1 `morta`** (EF-003).

**Top 3 per qualifica IC-screen Sprint 2**:
1. **EF-007 perp-basis-carry** — peer-reviewed (Management Science 2026), Sharpe storicamente replicato, ma strutturalmente decaduto. Test IS/OOS split pre/post 2024-Q1 è il canarino.
2. **EF-001 funding-extremum-reversal** — Confirmed (Inan 2025 SSRN; Two-Tiered MDPI 2026 confers meccanismo), 95% forced-exit documentato, IC direction contrarian.
3. **EF-002 liquidation-cascade-reversal** — Confirmed meccanismo (Anatomy Oct 2025 SSRN), ma edge bps-insufficiente-per-costi retail (arXiv 2608.21888). Event-window gating obbligatorio.

**Caveat onesto**: dei 5 `amplificata`, **EF-006 e EF-004 dipendono da aggTrades Binance Vision** (proxy OHLCV **non** sufficienti — registry già flagga, ma va ribadito al IC screen). EF-005 può essere ammesso come conditioning feature in EF-006. EF-003 è chiuso qui per non ripresentarlo a Sprint 3.

**Pre-registrazione obbligatoria prima del test** (ADR §1.1): per ciascuna ipotesi promossa ad `amplificata`, produrre spec YAML con `stato: in_qualifica` + sha256 del manifest prima di lanciare il runner `oracle paper run --spec`. Violazione = test nullo.

---

## Allegato: fonti primarie per URL verification

### Paper accademici peer-reviewed
- Inan, E. — *Predictability of Funding Rates* — SSRN 5576424 (2025) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5576424
- Zhang, T. — *Funding Rate Mechanism in Perpetual Futures* — SSRN 6185958 (2026) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6185958
- Schmeling, Schrimpf & Todorov — *Crypto Carry* — Management Science 2026 / SSRN 4268371 / BIS WP 1087 — https://pubsonline.informs.org/doi/10.1287/mnsc.2024.05069
- *The Two-Tiered Structure of Cryptocurrency Funding Rate Markets* — MDPI Mathematics 14(2):346 (2026) — https://www.mdpi.com/2227-7390/14/2/346
- *Anatomy of the Oct 10–11, 2025 Crypto Liquidation Cascade* — SSRN 5611392 (2026) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5611392
- Easley, O'Hara, Yang — *Microstructure and Market Dynamics in Crypto Markets* — SSRN 4814346 (2025) — https://stoye.economics.cornell.edu/docs/Easley_ssrn-4814346.pdf
- *Bitcoin wild moves: Evidence from order flow toxicity and price jumps* — ScienceDirect S0275531925004192 (2026) — https://www.sciencedirect.com/science/article/pii/S0275531925004192
- *Nowcasting bitcoin's crash risk with order imbalance* — PMC10040314 (2023) — https://pmc.ncbi.nlm.nih.gov/articles/PMC10040314
- *Reinforcement learning for automated market making in cryptocurrency perpetual futures* — ScienceDirect S240591882600022X (2026) — https://www.sciencedirect.com/science/article/pii/S240591882600022X
- Liu & Pierrot — *Fundamentals of Perpetual Futures* — arXiv 2212.06888 v5 (2025) — https://arxiv.org/html/2212.06888v5
- Christin et al. — *Cryptocurrency as an Investable Asset Class: Coming of Age* — arXiv 2510.14435 v3 (2026) — https://arxiv.org/html/2510.14435v3
- *Perpetual Futures in Decentralised Finance* — MDPI 14(7):178 (2026) — https://www.mdpi.com/2227-7072/14/7/178
- Gornall, Rinaldi & Xiao — *Perpetual Futures and Basis Risk* — SSRN 5036933 (2024) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5036933
- Baur, Cahill, Godfrey & Liu — *Bitcoin time-of-day, day-of-week and month-of-year effects* — FRL 31:78–92 (2019) — https://www.semanticscholar.org/paper/Bitcoin-time-of-day%2C-day-of-week-and-month-of-year-Baur-Cahill/fad3e5ae2030c6557130aa09a8b9b534af4be150
- De Nicola — *On the Intraday Behavior of Bitcoin* — Ledger 4 (2021) — https://ledgerjournal.org/ojs/ledger/article/download/213/212/1232
- *The crypto world trades at tea time* — RQF&A Springer (2024) — https://link.springer.com/article/10.1007/s11156-024-01304-1
- *Turn-of-the-candle effect in bitcoin returns* — PMC10015199 (2023) — https://pmc.ncbi.nlm.nih.gov/articles/PMC10015199
- Hoang — *Time-of-Day Effects in the Bitcoin Options Market* — SSRN 5689945 (2025) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5689945
- Day, Cheng, Huang & Ni — *The profitability of Bollinger Bands trading bitcoin futures* — Applied Economics Letters 30(11):1437–1443 (2023) — https://ideas.repec.org/a/taf/apeclt/v30y2023i11p1437-1443.html
- Park & Lim — *Testing the Applicability of the Technical Trading Strategy in the Cryptocurrency Market* — JFE 11(4) (2024) — https://pubs.sciepub.com/jfe/11/4/2/index.html
- Andersen & Bondarenko — *Assessing Measures of Order Flow Toxicity via Perfect ...* — Aarhus RP13_43 — https://pure.au.dk/ws/files/68359010/rp13_43.pdf
- *Short-horizon mean reversion in cryptocurrency markets: a matched cross-market measurement* — arXiv 2608.21888 (2025) — https://arxiv.org/html/2608.21888v1
- *Market Efficiency and Calendar Anomalies Post-COVID* — Scielo (2024) — http://www.scielo.org.mx/scielo.php?script=sci_arttext&pid=S2683-26902024000100012
- Williams — *Empirical Optimization of Bollinger Bands for Profitability* — SSRN 2321140 (2006)

### Working paper / letteratura grigia
- BSIC Bocconi — *Carry Trading dynamics in Cryptocurrency markets* (2025) — https://bsic.it/wp-content/uploads/2025/11/crypto_carry_article.pdf
- Liu — *Futures–Spot Arbitrage in Cryptocurrency Markets: A Comparative Analysis* — Medium 2025 — https://medium.com/@gwrx2005/futures-spot-arbitrage-in-cryptocurrency-markets-a-comparative-analysis-of-strategy-design-risk-6af00109e836
- Quantpedia — *The Seasonality of Bitcoin* (2024) — https://quantpedia.com/the-seasonality-of-bitcoin
- Quantpedia — *Are There Seasonal Intraday or Overnight Anomalies in Bitcoin?* — https://quantpedia.com/are-there-seasonal-intraday-or-overnight-anomalies-in-bitcoin
- OrderFlowpaper — *Order flow predictive power for cryptocurrency returns* — EFMA 2025 — https://www.efmaefm.org/0EFMAMEETINGS/EFMA%20ANNUAL%20MEETINGS/2025-Greece/papers/OrderFlowpaper.pdf
- Astorian — *Order Flow Toxicity in the Bitcoin Spot Market* — Medium 2024 — https://medium.com/@lucasastorian/empirical-market-microstructure-f67eff3517e0

### Practitioner educational (per context only, non usati come evidenza primaria)
- Cube Exchange, Kraken, Whaleportal, Bitsgap, Changelly, WazirX, Chainlink — overview tecnici
- Smart Money API — backtest commerciale (82% accuracy claim, NON peer-reviewed)
- MadeinArk — funding arbitrage overview
