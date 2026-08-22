# VALUTAZIONE F — Sintesi: copertura R1-R20, gap, decisioni

> Lotto finale. Sintetizza i lotti A-E: quanto è coperto ogni requisito
> del greenfield, cosa manca davvero, e quali decisioni restano aperte.
> Nessun taglio è stato fatto nei lotti precedenti; qui si tirano le somme.

## F.1 — Copertura dei requisiti (R1-R20)

| R | Requisito | Copertura catalogo | Migliori opzioni (valutate, non scelte) | Gap |
|---|---|---|---|---|
| R1 | Ricerca/ipotesi | ⚠️ parziale | Hamilton (DAG), OpenBB (mappa), Hudson&Thames (metodo); **nessun hypothesis registry OSS esiste** | da costruire |
| R2 | OHLCV multi-asset | ⚠️ | yfinance, FinanceDatabase, CoinPaprika, Binance Vision (nostro) | **equity/futures intraday storico = assente a $0** |
| R3 | Dati alternativi | ✅ buona | edgartools (SEC), AlphaSMO, AlphaAI (news), Microverse (L2), DexPaprika, Shingou | opzioni assenti; news storico limitato |
| R4 | Storage+qualità | ✅ | DuckDB, ArcticDB, lance, parquet-lake (nostro) | — |
| R5 | Indicatori/fattori | ✅✅ | TA-Lib, alphalens (jansen), tsfresh, volest, ml-quant-trading (mining) | — |
| R6 | Sweep veloce | ✅✅ | vectorbt, Manifold-BT (osservato) | — |
| R7 | Backtest event-driven | ✅✅ | nautilus_trader, backtesting.py, aat | — |
| R8 | Backtest HFT/L2 | ⚠️ | hftbacktest (unico) | dipende da L2 storico (Microverse probe) |
| R9 | Validazione overfitting | ⚠️ | honest-signals (metodo), Hudson&Thames, purgedcv/DSR (nostro) | il catalogo è debole qui; il nostro stack è più avanti |
| R10 | ML/RL | ✅ | torch, lightgbm, qlib (riferimento), FinRL (riferimento) | — |
| R11 | Ottimizzazione/sizing | ✅✅ | Riskfolio-Lib, skfolio, PyPortfolioOpt, cvxpy | — |
| R12 | Metriche/reporting | ✅✅ | quantstats, ffn, pyfolio, alphalens | — |
| R13 | Broker/exchange | ✅ | ccxt (crypto), ib_async (futures/equity), Hummingbot (MM) | — |
| R14 | Fill/slippage modeling | ⚠️ | hftbacktest, flashalpha-fill-sim, FillBench (dati latenza) | nessuno lo fa bene a livello daily |
| R15 | Hard risk/governance | 🔴 **VUOTO** | **nessuno nel catalogo** | da costruire (nostro G4 è l'unico riferimento) |
| R16 | Streaming | ✅ | cryptofeed, csp, Tributary, NATS (nostro) | — |
| R17 | Operations | ⚠️ | freqtrade (telegram), systemd/cron | maturo ma sparso |
| R18 | UI/UX | ⚠️ | Perspective, Dash, Streamlit, D-Tale | **nessun trading terminal OSS completo** |
| R19 | Qualità dev | ✅ | py-spy, pyinstrument, Memray, ruff/mypy (nostro) | — |
| R20 | $0/mese | ✅ vincolo applicato | tutte le opzioni sopra sono $0 | gap solo dove il dato è intrinsecamente paid |

## F.2 — I 4 gap strutturali (non risolvibili dal catalogo)

1. **Equity intraday storico a $0** — non esiste nel catalogo. Conseguenza:
   il greenfield non può fare ricerca intraday su equity senza pagare.
   Mitigazione: IBKR paper going-forward (accumulo) + daily per ora.
2. **Futures intraday storico a $0** — idem. Il nostro IBKR cron accumula
   going-forward; lo storico resta a pagamento (Databento, Polygon).
3. **Dati opzioni** — solo pricing libraries, nessun dato OPRA free.
   La pista opzioni è chiusa a $0.
4. **Prop-firm governance + terminal UI completo** — nessun progetto OSS
   li ha. Sono i due spazi dove il greenfield può essere *originale*,
   non assemblaggio.

## F.3 — Cose che il catalogo NON dice (verificate dal probe)

- 11 repo linkati sono **morti** (GONE_404): pandas-ta, marketstore,
  blackbird, openalpha, helium-mcp, openFinclaw, solana-sdk-tools,
  chart-patterns, MyClone/curistat, perp-arbitrageur, klinepic-examples.
  Il catalogo non viene mantenuto su questi.
- **Hummingbot** è traslocato (19.5K★, non 214).
- **ib_insync** è archiviato; il vivo è ib_async.
- **Redis** non è più open-source (RSALv2/SSPL).
- **RedPanda** è BSL, non OSS pieno.
- Il fork di alphalens linkato è quello sbagliato.

## F.4 — Inventario finale: "tutto quello che ci serve"

### Nucleo già nostro (non si tocca, è il vantaggio competitivo)
- Motore GA (DEAP), qualificazione (purgedcv, deflated-sharpe, DSR),
  data lake (parquet+polars+duckdb), IBKR/ccxt adapter, NATS, regime
  detection, metriche canoniche, G4 hard-risk.

### Da acquisire — Tier 1 (alta confidenza, coprono R scoperti, licenza pulita)
| Item | R coperto | Licenza | Perché |
|---|---|---|---|
| edgartools | R3 SEC | MIT | fundamental/13F/insider a $0 |
| quantstats | R12 | Apache-2.0 | reporting standard |
| ffn | R12 | MIT | calcoli finanziari |
| alphalens (stefan-jansen) | R5/R9 | Apache-2.0 | factor analysis |
| Riskfolio-Lib | R11 | BSD-3 | ottimizzazione completa |
| FinanceDatabase | R2 simboli | MIT | universe 300K |
| CoinPaprika + DexPaprika | R2/R3 crypto | free API | metadati + DeFi |
| py-spy + pyinstrument + Memray | R19 | MIT/BSD/Apache | profiling dev |

### Da acquisire — Tier 2 (condizionale a probe/verifiche)
| Item | Condizione |
|---|---|
| cryptofeed | leggere licenza NOASSERTION |
| Microverse | verificare limiti/ToS del free L2 |
| AlphaAI | verificare 100 req/day bastino |
| sharpe.ai | verificare free tier |
| tessera (dati) | GPL solo sul client; valutare il dato |
| hftbacktest | solo se pista L2 confermata |
| Tectonicdb | solo se pista L2; licenza da leggere |
| ArcticDB | leggere licenza NOASSERTION |
| Hamilton | valutare per pipeline fattori |
| csp | valutare per streaming |
| Perspective / Dash | decidere stack UI |
| tsfresh | valutare costo computazionale |
| volest | o riscrivere i 5 stimatori (GPL) |
| cvxportfolio | GPL da valutare vs Riskfolio |
| pmxt / pykalshi | solo se pista prediction markets |

### Solo studio/riferimento (zero adozione)
- QLib, Inalpha, FinClaw, pysystemtrade, Hudson&Thames, ML-for-Trading
  (Jansen), honest-signals (metodo), Shingou (metodo onestà), quant shops
  blogs, OpenBB (mappa fonti), je-suis-tm + Finance (mining strategie).

### Morti / non adottabili (registrati, non tagliati dalla storia)
- zipline, gobacktest, bTrader, Kelp, fastquant, openlimits, finta,
  Peregrine, anchormdf, graphkit, mdf + tutti i GONE_404 (11) + tutti i
  licenza-assente (BetterQuant, FlashFunk, MyCryptoBot, PandoraTrader,
  czsc-CN, Sequoia, analyzingalpha, QuantsPlaybook, strategies-CN, ecc.)
  + tutti i CN-only + tutti i Go/Rust/C++ fuori perimetro linguistico.

## F.5 — Decisioni aperte per la sessione congiunta

1. **Stack backtest unico o doppio?** vectorbt (sweep) + nautilus
   (event-driven/live) è la combinazione più coperta dal catalogo;
   alternativa: un solo framework (nautilus o freqtrade).
2. **Frequenza crypto**: fare market-making (Hummingbot, Apache-2.0) o
   ricerca direzionale (Jesse/Freqtrade)? Sono piste diverse con dati
   diversi.
3. **UI**: React-dashboard (già nostra), Dash (Python), o Perspective
   (grid streaming)? Il catalogo non offre un terminal completo.
4. **Pista L2/microstruttura**: si apre (Microverse+hftbacktest) o si
   resta su OHLCV+funding? È la scelta che più allarga il perimetro.
5. **Licenza del progetto greenfield**: se si useranno AGPL (backtesting.py,
   freqtrade, hummingbot no—Apache) serve una policy; MIT/Apache/BSD
   disponibili per quasi tutto il Tier-1.

## F.6 — Verifica finale "abbiamo tutto?"

- **Sì** per: backtest (tutti i livelli), ottimizzazione, metriche,
  connettività, ML, indicatori, storage, dev-tools, metodo di validazione
  (anzi: siamo avanti rispetto al catalogo).
- **Sì con probe** per: dati alternativi (SEC, L2, news, DeFi) — le fonti
  $0 esistono ma vanno verificate una per una (Tier 2).
- **No, e non dipende dal catalogo** per: equity/futures intraday storico
  (paid), opzioni (paid), governance prop-firm e terminal UI (da
  costruire — ed è qui che il greenfield può differenziarsi).

> Conclusione onesta: il catalogo fornisce ~90% degli strumenti software
> necessari a $0. Il restante 10% sono dati a pagamento (strutturale) e
> due spazi vuoti (governance, UI) che nessun OSS copre — cioè le due
> cose che il greenfield dovrebbe costruire da zero, non comprare.
