# Oracle Autopilot — Capability-Gated Master Roadmap

> Versione: 3.1 — Mutageno + Opzione C
> Ultimo aggiornamento: 2026-08-18 (allineamento post-Opzione C 2026-08-17 + knowledge base 13 domini)
> Stato: roadmap canonica
> Modello di avanzamento: capability gate con evidenza, non phase temporali
> Gerarchia fonti: ROADMAP (perché) → STATUS (cosa) → BACKLOG (come) → ADR (decisioni) → report (evidenza).
> La matrice gate/stato fresca è in ORACLE_AUTOPILOT_STATUS.md.

## 1. Risultato atteso — Visione Mutageno

Oracle deve evolvere da piattaforma di ricerca a **meta-sistema di trading
auto-adattivo** che opera come un'intera trading firm: analizza, decide,
esegue e impara continuamente, mutando la propria composizione di strategie
in risposta alle condizioni di mercato.

Come un organismo mutageno, il sistema:
- **percepisce** il mercato su ogni asset, timeframe e regime;
- **adatta** il proprio portafoglio di strategie in tempo reale;
- **impara** dai propri errori attraverso memoria e feedback;
- **evolve** eliminando strategie morte e sperimentandone di nuove;
- **opera** simultaneamente su trend, mean-reversion, breakout, price action,
  volumetriche, macro e quantitative —
  **100+ strategie, ogni condizione, ogni asset, ogni timeframe**.

### Fasi di realizzazione

| Fase | Cosa | Gate target |
|------|------|-------------|
| **Fondazione** | Pipeline dati, risk, OMS, qualificazione | G0–G6 |
| **Meta-Intelligence** | Research Memory, meta-optimizer, signal blender | G6-I → G10 |
| **Espansione orizzontale** | 100+ strategie, tutti gli asset, tutti i TF | G10–G11 |
| **Mutageno** | Real-time adaptation, evolution loop, auto-discovery | G12–G14 |

### Risultato immediato (pre-G6)

La base di partenza era **regime-conditional mean-reversion su RSI in choppy
daily ES** (23/30 sessioni paper, commit `ffe91b4`). La verifica S0
(BL-093 autopsia + BL-094 modello economico) ha mostrato che quell'edge era
in realtà **beta scambiato per alpha**: alpha residuo misurato +2.3%..+6.1%
lordo/anno, netto costi → verso lo zero. La lane daily è **economicamente
morta** (€3K/mese netti richiedono alpha 5-16× il soffitto misurato). Quindi
oggi **non esiste un edge sfruttabile**: prima di G5/G6 serve un cambio di
canale (multi-asset, sweep candidati, orizzonte >1d), non più tuning della
mean-reversion. Vedi [docs/reports/s0-1-bl023-autopsy.md](docs/reports/s0-1-bl023-autopsy.md)
e [docs/reports/s0-2-economic-model.md](docs/reports/s0-2-economic-model.md).

Il risultato finale della **Fase Fondazione** richiede contemporaneamente:

- dati point-in-time e specifiche contratto verificati;
- decisioni riproducibili e versionate;
- ledger, OMS e reconciliation durevoli;
- risk kernel deterministico e non bypassabile;
- adapter broker certificato;
- qualificazione economica out-of-sample;
- promozione replay → paper → shadow → evaluation → funded;
- audit, osservabilità, recovery e kill switch operativi.

Non sono obiettivi validi:

- massimizzare il numero di feature o agenti;
- dichiarare completezza perché un modulo o un test isolato esiste;
- usare risultati sintetici come prova di edge;
- usare LLM, GA o dashboard per compensare dati, ledger o risk incompleti;
- garantire profitti, payout o superamento di challenge.

## 2. Fonti canoniche

| Documento | Autorità |
|---|---|
| [`PROJECT.md`](PROJECT.md) | Perimetro e stack (informale, single source of truth delle scelte di massima) |
| [`ROADMAP.md`](ROADMAP.md) | Sequenza dei capability gate, principi non negoziabili |
| [`docs/ORACLE_AUTOPILOT_STATUS.md`](docs/ORACLE_AUTOPILOT_STATUS.md) | **Checkpoint operativo e matrice gate/stato** (unica tabella gate/stato autoritativa) |
| [`BACKLOG.md`](BACKLOG.md) | **Task atomiche per gate** (ID stabile BL-NNN) |
| [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md) | Gerarchia documentale e regole |
| [`docs/AUDIT_FINDINGS.md`](docs/AUDIT_FINDINGS.md) | Audit secco 25-lug, gap e stato reale vs dichiarato |
| [`docs/PROP_FIRM_READINESS_ROADMAP.md`](docs/PROP_FIRM_READINESS_ROADMAP.md) | Regole di supporto e certificazione prop-firm (da rinominare) |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Architettura corrente, target e confini di autorità |
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | Operatività (dev + paper) |
| [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) | Coverage matrix per asset class / TF |
| [`docs/ADR/`](docs/ADR/) | Decisioni normative immutabili |
| [`docs/plans/`](docs/plans/) | Archivio dei vecchi piani Phase, **non eseguibile** |

I file `phase*-plan.md` in `docs/plans/` (archiviati qui) e i vecchi backlog
(`docs/plans/oracle-autopilot-*-backlog-*.md`) sono solo archivio. Non
possono cambiare stato, architettura o priorità del programma.

## 3. Regole di avanzamento

### 3.1 Stati

- NOT_STARTED: nessun lavoro verificato;
- IN_PROGRESS: deliverable parziali con evidenza;
- BLOCKED: blocker esplicito e owner del recupero;
- PASSED: exit gate soddisfatto con verifica fresca;
- REGRESSED: un gate precedentemente passato non è più valido;
- NOT_APPLICABLE: escluso tramite ADR.

### 3.2 Evidenza obbligatoria

Un gate può diventare PASSED soltanto se il report registra:

1. commit o build immutabile;
2. configurazione e dataset versionati;
3. comandi di verifica e risultato;
4. test negativi e failure mode rilevanti;
5. security e dependency scan applicabili;
6. rischi residui e limiti noti;
7. reviewer e data di approvazione.

Un checkbox, una demo o una suite che usa fallback sintetici non sono evidenza
sufficiente.

### 3.3 Politica di regressione

Un gate torna REGRESSED quando cambia uno dei seguenti elementi:

- contratto di dominio o schema dati;
- motore di sizing, risk, OMS o ledger;
- adapter broker o piattaforma;
- regola ufficiale della firm;
- strategia, dataset, cost model o motore di backtest;
- dipendenza con finding high/critical nel percorso interessato.

## 4. Confini non negoziabili

- LLM ed ElizaOS sono intelligence e decision support, mai execution authority.
- Nessun output LLM può essere inviato direttamente a un broker.
- Ogni ordine passa da modalità operativa, rule profile, risk kernel e OMS.
- Il ledger riconciliato è la fonte autorevole per account e posizioni.
- NATS è trasporto; non è fonte autorevole di ordini, fill o saldo.
- Redis è cache; una perdita Redis non può perdere stato economico.
- Un dato mancante, stale o non verificabile produce NO_TRADE, PAUSE o FLATTEN.
- Replay, paper, shadow, evaluation e funded sono ambienti e credenziali separati.
- Nessun profilo prop-firm incompleto o scaduto può essere AUTO_SUPPORTED.
- Il percorso safety-critical rimane deterministico e testabile senza LLM.
- Il live trading resta disabilitato finché G7 non è PASSED.

## 5. Workstream

### S — Safety control plane, bloccante

Contratti, ambienti, ledger, OMS, risk, broker, reconciliation, kill switch,
security e audit. È il percorso critico.

### D — Data e research integrity, bloccante per qualificazione

Contract data, point-in-time lineage, backtest, costi, WFA, holdout, stress ed
economics.

### I — Intelligence con feedback loop (Mutageno Core)

Investment Committee, LLM gateway, Eliza scouts, memoria, debate, GA,
meta-optimizer, strategy catalog, signal blender, evolution loop.
Questi moduli possono migliorare decision quality soltanto dopo aver rispettato
i confini S e D.

La visione mutageno estende il feedback loop classico in un **ciclo evolutivo
completo** che copre:

#### I-A — Strategy Catalog (100+ strategie)

Tassonomia completa coprendo ogni famiglia di trading:

| Famiglia | Strategie | Esempi |
|----------|-----------|--------|
| **Trend Following** | 10 | Golden/Death Cross, Donchian, Supertrend, EMA21, Parabolic SAR, Ichimoku, ADX, Elder Triple, Heikin Ashi, Linear Regression |
| **Mean Reversion** | 10 | Bollinger Bands, RSI 30/70, Stochastic, Williams %R, CCI, DPO, Envelopes, Z-Score, Pivot Point, Standard Deviation |
| **Breakout** | 10 | ORB, Support/Resistance, Trendline, Volatility Squeeze, Triangle, Rectangle, Cup&Handle, Flag&Pennant, Volume Profile, Previous Day HL |
| **Price Action** | 10 | Pin Bar, Engulfing, Inside Bar, Fakey, Morning/Evening Star, Tweezer, 3 Soldiers/Crows, Piercing Line, Doji Star, 1-2-3 Pattern |
| **Volumetric** | 10 | POC, Volume Imbalance, Volume Exhaustion, Order Book Absorption, Liquidity Sweep, Delta Divergence, Iceberg Detection, T&S Acceleration, VWAP, Cumulative Delta |
| **Scalping/Intraday** | 10 | Micro-Scalping, EMA8 1m, Fibonacci Intraday, Gap Fill, News Straddle, Elliott Waves, Momo, Time-of-Day, Tick Chart, Fade First Move |
| **Macro/Fondamentali** | 10 | Interest Rates, NFP, Earnings Surprise, Carry Trade, EIA Stocks, Insider Tracking, Dividend Arb, COT Report, Intermarket Correlation, CPI |
| **Quantitative** | 10 | Pairs Trading, Grid, Market Making, Cross-Exchange Arb, Slipped MA, HFT Momentum, PCA, Kalman Filter, Sentiment NLP, Monte Carlo |
| **Opzioni** | 10 | Covered Call, Iron Condor, Protective Put, Long Straddle, Bull Call Spread, Bear Put Spread, Calendar Spread, Cash-Secured Put, Iron Butterfly, Gamma Scalping |
| **Portafoglio** | 10 | All Weather, Systematic Rebalancing, Currency Hedge, Smart Beta, Seasonal Commodity, Crypto DCA, Funding Rate Arb, Value+Technical Exit, Calendar Spreads, Anti-Martingala |

Ogni strategia è:
- **implementata** come signal puro (regime-aware o meno);
- **testabile** su qualsiasi asset via DataRegistry;
- **valutabile** con walk-forward + gauntlet;
- **componibile** in ensemble multi-segnale.

#### I-B — Meta-Optimizer (Signal Blender)

Non un singolo segnale, ma un **portafoglio di segnali** pesato dinamicamente:

- **Strategy Performance Registry**: ogni strategia tiene traccia di Sharpe,
  win rate, drawdown, pass rate per regime (bull/bear/choppy/volatile).
- **Per-Regime Weighting**: in regime choppy → più peso a mean-reversion;
  in trend → più peso a trend following.
- **Decay Detection**: se una strategia degrada, il peso cala
  esponenzialmente fino a esclusione.
- **Portfolio Allocation Engine**: distribuisce il rischio tra strategie
  scorrelate per minimizzare il drawdown complessivo.

#### I-C — Research Memory (BL-090)

Ogni decisione è registrata con:
- `decision_id, timestamp, regime al momento, strategia, confidence,
   outcome (win/loss), P&L, feature correnti`
- Backend SQLite (dev) / PostgreSQL (prod)
- Hook nel decision path del `RegimeAwareEnsemble.compute()`
- Report periodici: "cosa sta funzionando ora?" per regime/asset/TF

#### I-D — Strategy Evolution Loop

Il sistema **non è statico**: impara, muta, elimina:

1. **Monitoraggio continuo**: ogni strategia ha metriche di fitness in tempo
   reale per regime corrente.
2. **Segnalazione decadimento**: se una strategia non performa più nel suo
   regime target, viene depromossa.
3. **GA evolution**: nuove varianti di parametri vengono esplorate via GA
   (già implementato in R4).
4. **Edge Discovery**: l'agente cerca nuovi pattern statisticamente validati
   (VARRD model).
5. **Promozione**: solo edge che passano walk-forward + gauntlet + paper
   vengono promossi a live.

#### I-E — Altri moduli intelligence

- **Factor Timing**: i fattori alpha (50+) vengono classificati per Rank IC
  corrente, con decay detection. L'agente vede quelli che funzionano *ora*.
- **Regime Ensemble**: HMM + Lorenzian classification + BOCD per rilevare
  transizioni di regime non-lineari e pesare i fattori di conseguenza.
- **Multi-Timeframe Regime Detection**: il regime su 1d vs 1h può essere
  diverso — ogni timeframe ha la propria classificazione.
- **Investment Committee LLM**: output strutturato, versionato, scadibile.
- **ElizaOS scouts**: observation firmate, read-only.

### O — Operations e UI, trasversale

API, dashboard, deployment, observability, incident response e runbook.
La UI osserva lo stato autorevole; non lo ricostruisce da artefatti ad hoc.

## 6. Capability gate

I gate sono descritti nei deliverable e exit evidence sottostanti.
**Lo stato attuale di ogni gate è in [ORACLE_AUTOPILOT_STATUS.md](docs/ORACLE_AUTOPILOT_STATUS.md).**

## G0 — Baseline veritiera e riproducibile

**Obiettivo:** repository e CI descrivono esattamente ciò che è costruibile e
verificabile.

**Deliverable minimi:**

- working tree consolidata e artefatti generati esclusi;
- Python 3.12 e Node 24 dichiarati;
- installazione da uv.lock in CI;
- lock Node per ogni applicazione;
- suite, lint, format, typecheck e build verdi;
- audit dependency completo, incluse dev dependency esposte da dev server;
- warning budget e coverage scope espliciti;
- documentazione senza claim non verificati;
- SBOM, secret scan e dependency review pianificati o attivi.

**Exit evidence:**

- build da checkout pulito;
- uv sync --frozen riuscito;
- nessun finding high/critical non accettato;
- report di baseline con commit, comandi e conteggi;
- zero file runtime o credenziali tracciati per errore.

## G1 — Autorità, ambienti e confini applicativi

**Dipendenze:** G0.

**Obiettivo:** nessun percorso pubblico può acquisire autorità live per default.

**Deliverable minimi:**

- enum operativo REPLAY, PAPER, SHADOW, EVALUATION, FUNDED;
- credenziali, account e configurazioni separati per modalità;
- startup fail-closed per ambiente production;
- API authentication obbligatoria fuori dallo sviluppo locale;
- CLI live disabilitata fino a certificazione;
- contratti portfolio/trade spostati in un layer inward, non in agents;
- porte e adapter espliciti per broker, ledger, risk e market data;
- access scope read-only per intelligence e scope execution solo per OMS;
- threat model e matrice dei bypass.

**Exit evidence:**

- test che nessun comando o endpoint senza profilo e credenziali certificate
  possa inviare ordini;
- test di environment crossing;
- test di startup senza segreti;
- dependency graph senza cicli safety-critical.

## G2 — Verità futures e point-in-time data

**Dipendenze:** G1.

**Obiettivo:** prezzo, P&L, sizing e disponibilità dei dati usano unità e tempo
reali.

**Deliverable minimi:**

- ContractSpec versionato con multiplier, point/tick value, currency e scadenze;
- mapping continuous contract → tradable contract;
- calendari exchange, DST, holiday, maintenance e liquidation deadline;
- roll e back-adjustment policy;
- event_time, published_at, available_at, ingested_at e revision_id;
- raw data immutabile, normalized data e lineage feature;
- provider, licenza, hash e adjustment version;
- duplicate, gap, outlier e stale-data detection.

**Exit evidence:**

- P&L e sizing campione uguali a exchange/broker;
- replay DST, holiday e roll week;
- leakage test su news, macro revision e filing;
- nessun fallback generico di prezzo, point value o contract size.

## G3 — Ledger, OMS e reconciliation durevoli

**Dipendenze:** G1, G2.

**Obiettivo:** lo stato economico sopravvive a retry, restart e disconnessioni.

**Deliverable minimi:**

- PostgreSQL come source of truth production; SQLite solo dev/test;
- ledger double-entry o invarianti equivalenti per balance, equity, P&L,
  commissioni e margin;
- intent, order, fill, position e account snapshot durevoli;
- idempotency key e transactional outbox;
- partial fill, cancel, amend, reject e reversal idempotenti;
- reconciliation startup, periodica e on-demand;
- CLI, API e agent pipeline sullo stesso servizio OMS.

**Exit evidence:**

- restart senza perdita o duplicazione;
- duplicate e out-of-order fill non alterano il ledger;
- mismatch broker/ledger rilevato e bloccante;
- audit reconstruction da intent a saldo finale.

## G4 — Hard risk non bypassabile

**Dipendenze:** G2, G3 e rule profile versionato.

**Obiettivo:** nessun ordine può superare un limite hard.

**Deliverable minimi:**

- risk dependency obbligatoria, mai None, sul percorso eseguibile;
- support mode e rule version verificati;
- daily loss, trailing/static drawdown e contract cap;
- sizing da stop distance e tick value;
- session, news, overnight e liquidation gate;
- stale data, clock drift, reconciliation e profile mismatch circuit breaker;
- cancel + flatten kill switch con verifica broker-side;
- bracket/OCO broker-side quando disponibile.

**Exit evidence:**

- property test dei limiti;
- zero bypass da CLI, API, MAS o adapter;
- replay di breach ufficiali;
- time-travel test;
- fire drill di kill e flatten.

## G5 — Research truth e strategy qualification

**Dipendenze:** G2; G3 per parity paper/live.

**Obiettivo:** i risultati supportano una decisione economica riproducibile.

**Deliverable minimi:**

- motore vectorized solo per discovery veloce;
- un solo motore event-driven certificato per qualification;
- PyBroker deprecato; Nautilus è candidato, non ancora certificato;
- train index, purge, embargo e nested walk-forward reali;
- holdout intatto e strategia preregistrata;
- costi futures, commissioni, slippage, latency e roll;
- sizing identico tra qualification e paper;
- benchmark semplici e leakage probes;
- experiment registry con code, data, config e seed hash;
- policy legale esplicita per Commons Clause, LGPL e altre licenze del percorso.

**Exit evidence:**

- nessuna eccezione o fallback silenzioso nel calcolo delle metriche;
- report IS, validation, OOS e holdout separati;
- parity entro tolleranza;
- stress costi e regime;
- power analysis o numerosità adeguata.

**Nota:** M31 è stato APPROVED per historical replay il 2026-07-19. Lo stato in STATUS può
essere REGRESSED se dataset, motore o configurazione non sono più riproducibili.

## G6 — Paper e shadow operations

**Dipendenze:** G3, G4, G5.

**Obiettivo:** failure reali non producono drift o violazioni.

**Deliverable minimi:**

- paper broker event-driven con quote reali o replay deterministico;
- un solo adapter futures prioritario;
- sandbox contract tests;
- streaming account/order/fill/position;
- deployment riproducibile e non-root;
- metriche, tracing, alert e audit reali;
- chaos test per disconnect, delayed fill, duplicate event e clock drift;
- emergency stop indipendente dal processo principale;
- runbook e incident response.

**Exit evidence (G6 completo):**

- almeno 30 sessioni paper indipendenti (non sovrapposte) senza policy breach;
- almeno 20 sessioni shadow riconciliate;
- recovery da restart di processo, rete e broker;
- kill-to-flat entro SLO;
- nessuna credenziale statica o porta dati pubblica.

**G6-I — Intelligence Feedback Loop** (parallelo, non bloccante per G6 ops).

Obiettivo: chiudere il loop tra agenti, backtest e paper trading creando
un sistema che impara e migliora autonomamente.

| Milestone | Cosa | Riferimento |
|:---------:|------|:-----------:|
| I-01 | Factor Timing — 50 fattori classificati per Rank IC corrente | `docs/plan-integration-inalpha-varrd.md §3` |
| I-02 | Research Memory — decisioni registrate, confidence calibrata | `docs/plan-integration-inalpha-varrd.md §5` |
| I-03 | HMM + Lorenzian Ensemble — regime detection ibrida | `docs/plan-integration-inalpha-varrd.md §6` |
| I-04 | Strategy Evolution Loop — LLM scrive strategie, 3 sandbox, cross-val | `docs/plan-integration-inalpha-varrd.md §4` |
| I-05 | Edge Discovery — event study per nuovi pattern (VARRD) | `docs/plan-integration-inalpha-varrd.md §7` |
| I-06 | Three-step Orders — propose→approve→execute con token | `docs/plan-integration-inalpha-varrd.md §4` |

**Nota:** M32 "rolling paper replay" (60 finestre sovrapposte su storico) è diagnostico,
non costituisce le 30 sessioni paper indipendenti richieste da G6.

## G7 — Certificazione di uno specifico programma

**Dipendenze:** G6 e policy di [PROP_FIRM_READINESS_ROADMAP.md](docs/PROP_FIRM_READINESS_ROADMAP.md).

**Obiettivo:** promuovere un solo firm/program/stage/platform/account profile.

**Exit evidence:**

- automazione consentita da fonte ufficiale e vincoli operativi rispettati;
- rule profile immutabile e fonti fresche;
- adapter e piattaforma certificati;
- replay, stress, paper e shadow passati;
- expected value netto positivo con intervallo di confidenza;
- support mode approvato;
- manifest con versioni di codice, dati, regole, strategia e adapter.

Il superamento di G7 autorizza soltanto la smallest evaluation esplicitamente
approvata.

## G8 — Funded limited rollout

**Dipendenze:** G7 e evaluation senza policy breach.

**Obiettivo:** usare il minimo capitale/risk budget e dimostrare operatività
controllata.

**Exit evidence:**

- payout e costi reali verificati;
- nessun incident high irrisolto;
- rischio iniziale non oltre il 25% del budget consentito;
- rollback e demotion testati;
- review umana prima di ogni aumento di account, strategia o size.

## G9 — Continuous operations

**Dipendenze:** G8.

**Obiettivo:** regole, strategie, modelli e dipendenze restano aggiornati.

Richiede review periodiche di risk, reconciliation, firm rules, broker,
dipendenze, modelli, prompt, strategie, DR e incidenti. G9 non termina: una
regressione riapre il gate interessato.

## 7. Lane intelligence

Le lane seguenti non possono bloccare G2-G4 e non acquisiscono autorità:

| Lane | Entry | Gate proprio |
|---|---|---|
| Investment Committee LLM | G1 | output strutturato, versionato, scadibile e riproducibile |
| ElizaOS scouts | G1 + provenance G2 | observation firmate, read-only, allowlist e injection defense |
| Debate e memory | G5 | beneficio incrementale misurato OOS, nessun simulated reward presentato come reale |
| Genetic research | G5 | holdout intatto, compute budget e promotion policy |
| Dashboard | G0 | legge API/ledger autorevoli, nessuna ricostruzione operativa da file locali |

## 8. Sequenza minima

```
G0 → G1 → G2 → G3 → G4
G2 → G5
G3 → G6
G4 → G6
G5 → G6 → G7 → G8 → G9

G1 → I[LLM ed Eliza read-only]
G5 → R[GA e research avanzata]
I → G6
R → G7
```

LLM, Eliza e GA possono essere rimossi senza rendere insicuro il control plane.
Non vale il contrario.

## 9. Sequenza minima aggiornata

```
G0 → G1 → G2 → G3 → G4
G2 → G5
G3 → G6, G4 → G6, G5 → G6
G6 → G7 → G8 → G9

G5 → G6-I (Intelligence loop)
G6 → G10 (Strategy Catalog 100+)
G10 → G11 (Cross-Asset Universal)
G11 → G12 (Meta-Optimizer real-time)
G12 → G13 (Evolution Loop automatico)
G13 → G14 (Edge Discovery autonomo)

G1 → I[LLM ed Eliza read-only]
G5 → R[GA e research avanzata]
I → G6
R → G7
```

LLM, Eliza e GA possono essere rimossi senza rendere insicuro il control plane.
Non vale il contrario.

## 10. Mutageno Gates — G10 → G14

### G10 — Strategy Catalog (100+ strategie)

**Dipendenze:** G6 (paper operations stabili), G6-I (research memory).

**Obiettivo:** implementare, testare e validare l'intero catalogo di 100+
strategie su ogni famiglia di trading (trend, mean-reversion, breakout,
price action, volumetrico, intraday, macro, quant, opzioni, portafoglio).

**Deliverable minimi:**

- ogni strategia implementata come signal puro in `analytics/strategy/`
  o `analytics/signals/`;
- ogni strategia testabile via `DataRegistry` su qualsiasi asset;
- ogni strategia valutabile con walk-forward + stress gauntlet;
- metriche di fitness registrate in Research Memory per ogni (strategia,
  asset, regime, timeframe);
- signal blender che compone segnali multipli con pesatura per-regime;
- report di copertura: quante strategie sono attive per regime/asset/TF.

**Exit evidence:**

- 100+ strategie implementate con test unitari;
- almeno 60 strategie con fitness validato su almeno 3 asset ciascuna;
- signal blender produce un segnale composito con Sharpe OOS > baseline
  a strategia singola;
- copertura: ogni regime ha almeno 5 strategie con fitness positivo;
- report `docs/reports/strategy-catalog/` con matrice strategie × asset × regime.

### G11 — Cross-Asset Universal Coverage

**Dipendenze:** G10, Data Lake (BL-301 maturo).

**Obiettivo:** ogni strategia del catalogo opera su ogni asset disponibile
nel data lake, con parametri auto-calibrati per asset class.

**Deliverable minimi:**

- calibrazione automatica dei parametri per strategia per asset (vol-scaled,
  non hardcoded);
- regime detection multi-asset (non solo ES, ma FX, crypto, commodities,
  tassi);
- coverage matrix aggiornata: quanti asset × quante strategie × quanti TF;
- report per-asset: quali strategie funzionano su quell'asset;
- portfolio allocation cross-asset: distribuzione del rischio tra asset
  scorrelati.

**Exit evidence:**

- 80%+ delle strategie funzionano su almeno 5 asset ciascuna;
- portfolio cross-asset ha Sharpe > strategia single-asset;
- drawdown massimo del portafoglio < drawdown del singolo asset migliore;
- report `docs/reports/cross-asset/` con matrice completa.

### G12 — Meta-Optimizer Real-Time

**Dipendenze:** G10, G11.

**Obiettivo:** il sistema adatta in tempo reale i pesi delle strategie
in base alle performance recenti per regime corrente.

**Deliverable minimi:**

- **Strategy Performance Registry** live: ogni strategia aggiorna le proprie
  metriche (Sharpe rolling, win rate, drawdown) dopo ogni trade;
- **Regime-aware blender**: pesi delle strategie cambiano al cambiare del
  regime;
- **Decay detection**: se una strategia degrada per N finestre consecutive,
  peso azzerato con escalation alert;
- **Portfolio risk allocation**: rischio distribuito tra strategie scorrelate
  con target volatility;
- **Backtest del meta-ottimizzatore**: simulazione storica del blending
  dinamico vs static baseline.

**Exit evidence:**

- meta-optimizer batte static baseline su walk-forward (Sharpe, DD, pass rate);
- decay detection identifica correttamente strategie degradate (test unitario);
- rolling rial location funziona con latenza < 1 bar;
- report `docs/reports/meta-optimizer/` con evidenza.

### G13 — Strategy Evolution Loop (Mutageno)

**Dipendenze:** G12, GA search (R4).

**Obiettivo:** il sistema elimina autonomamente strategie morte e ne sperimenta
di nuove via GA + qualificazione automatica.

**Deliverable minimi:**

- **GA evolution scheduling**: ogni N sessioni paper, GA search lancia nuove
  varianti di strategie esistenti;
- **Automatic qualification**: ogni nuova strategia passa walk-forward +
  stress gauntlet prima di entrare in produzione;
- **Strategy淘汰 (eliminazione)**: strategie con fitness negativo per X
  finestre consecutive rimosse dal catalogo attivo;
- **Human-in-the-loop gate**: strategie nuove richiedono approval umano prima
  di paper live (fino a G14);
- **Evolution log**: ogni ciclo evolutivo registrato con parametri, fitness,
  esito.

**Exit evidence:**

- GA scopre almeno 1 strategia che batte il catalogo esistente;
- strategie morte correttamente rimosse (test su degradazione simulata);
- evolution log completo e consultabile;
- report `docs/reports/evolution/` con storia dei cicli.

### G14 — Edge Discovery Autonomo

**Dipendenze:** G13.

**Obiettivo:** il sistema scopre autonomamente nuovi pattern di mercato
statisticamente validati, senza intervento umano.

**Deliverable minimi:**

- **Event study engine**: dati storici scanditi per eventi (macro, pattern,
  vol spike) con bucket pre/durante/post;
- **VARRD model**: Variance Analysis of Returns in Regime Dimensions —
  scoperta di pattern che producono edge in regimi specifici;
- **Auto-qualification pipeline**: nuovo pattern → walk-forward → gauntlet →
  paper → (se passa) promozione a strategia del catalogo;
- **Research memory feedback**: il sistema sa cosa ha funzionato in passato
  e cerca pattern simili nel presente;
- **Full automation option**: se G13 + G14 passati, il loop può operare senza
  intervento umano (con kill switch remoto).

**Exit evidence:**

- edge discovery trova almeno 1 pattern valido non pre-programmato;
- auto-qualification pipeline funziona end-to-end;
- full automation option documentata e testata;
- report `docs/reports/edge-discovery/` con pattern scoperti.

## 11. Tassonomia Mutageno — Strategie 1–100

### Trend Following (10)

| # | Strategia | Logica |
|---|-----------|--------|
| 1 | Golden/Death Cross | SMA50/200 crossover |
| 2 | Donchian Channel | Rottura massimo/minimo N periodi |
| 3 | Supertrend | Combinazione volatilità + prezzo |
| 4 | EMA21 Trend Ride | Prezzo sopra EMA21 = long |
| 5 | Elder Triple Screen | Trend lungo filtro per trade breve |
| 6 | Parabolic SAR | Stop-and-reverse come trailing |
| 7 | Linear Regression Channel | Rimbalzo su linea inferiore |
| 8 | Heikin Ashi Trend | Colore/persistenza candele HA |
| 9 | Ichimoku Kumo Breakout | Prezzo esce dalla nuvola |
| 10 | ADX Trend Strength | ADX > 25 = trend forte |

### Mean Reversion (10)

| # | Strategia | Logica |
|---|-----------|--------|
| 11 | Bollinger Bounce | Compra a banda inferiore, vendi a superiore |
| 12 | RSI 30/70 | Ipercomprato > 70, ipervenduto < 30 |
| 13 | Stochastic Oscillator | %K/%D crossover in zone estreme |
| 14 | Std Dev from Spanning | Deviazione dalla media geometrica |
| 15 | Williams %R Reversal | Letture estreme per correzioni |
| 16 | CCI +100/-100 | Oltre +100 o -100 per rientri statistici |
| 17 | DPO (Detrended Price Osc.) | Isola cicli rimuovendo trend lungo |
| 18 | Envelopes | Deviazione % fissa da media centrale |
| 19 | Z-Score Mean Reversion | Deviazioni standard dal prezzo medio |
| 20 | Pivot Point Bounce | Pivot giornaliero come magnete |

### Breakout (10)

| # | Strategia | Logica |
|---|-----------|--------|
| 21 | Previous Day HL Breakout | Rottura massimo/minimo giorno prima |
| 22 | Opening Range Breakout | Rottura primi 15-30 min |
| 23 | S/R Horizontal Breakout | Rottura supporti/resistenze statici |
| 24 | Trendline Breakout | Violazione linea di tendenza |
| 25 | Volatility Squeeze | Bollinger si espande da Keltner |
| 26 | Triangle Pattern | Compressione geometrica → esplosione |
| 27 | Rectangle Breakout | Uscita da fase laterale |
| 28 | Cup & Handle | Rottura resistenza tazza |
| 29 | Flag & Pennant | Rottura bandiera/gagliardetto |
| 30 | Volume Profile Breakout | Superamento nodi ad alto volume |

### Price Action (10)

| # | Strategia | Logica |
|---|-----------|--------|
| 31 | Pin Bar / Hammer | Rifiuto minimi/massimi con ombra lunga |
| 32 | Engulfing Pattern | Corpo ingloba candela precedente |
| 33 | Inside Bar Breakout | Ordini sopra/sotto mother bar |
| 34 | Fakey Setup | Falsa rottura Inside Bar → direzione opposta |
| 35 | Morning / Evening Star | 3-candle reversal pattern |
| 36 | Tweezer Tops & Bottoms | Massimi/minimi identici consecutivi |
| 37 | 3 Soldiers / 3 Crows | 3 candele direzionali consecutive |
| 38 | Piercing Line / Dark Cloud | Penetrazione corpo candela precedente |
| 39 | Doji Star Reversal | Doji in punto di massimo/minimo |
| 40 | 1-2-3 Pattern (Ross) | Cambio struttura: minimi/massimi crescenti |

### Volumetric & Order Flow (10)

| # | Strategia | Logica |
|---|-----------|--------|
| 41 | Point of Control (POC) | Livello con maggior volume come S/R |
| 42 | Volume Imbalance | Sbilanciamento compratori/venditori |
| 43 | Volume Exhaustion | Trend accelera, volume cala |
| 44 | Order Book Absorption | Ordini passivi assorbono flussi |
| 45 | Liquidity Sweep | Stop puliti sopra massimi relativi |
| 46 | Delta Divergence | Prezzo vs delta volumi divergono |
| 47 | Iceberg Detection | Ordini nascosti di grandi dimensioni |
| 48 | T&S Acceleration | Velocità esecuzione nastro aumenta |
| 49 | VWAP Trading | Compra sotto VWAP in uptrend |
| 50 | Cumulative Delta Trend | Accumulo contratti conferma trend |

### Scalping & Intraday (10)

| # | Strategia | Logica |
|---|-----------|--------|
| 51 | Micro-Scalping Book | Spread bid-ask in frazioni di pip |
| 52 | EMA8 1m Bounce | Rimbalzo su EMA8 a 1 minuto |
| 53 | Fibonacci Intraday | Ritracciamento 38.2% / 61.8% |
| 54 | Gap Fill | Chiusura gap di apertura |
| 55 | News Straddle | Buy-stop + sell-stop pre-macro |
| 56 | Elliott Waves Scalping | Sotto-onda 3 su 3-5 min |
| 57 | Momo Strategy | Accelerazione volumetrica iniziale |
| 58 | Time-of-Day Trading | Sovrapposizione London/New York |
| 59 | Tick Chart Chasing | Grafici a tick, senza timeframe |
| 60 | Fade First Move | Vendi prima fiammata post-apertura |

### Macro & Fundamentali (10)

| # | Strategia | Logica |
|---|-----------|--------|
| 61 | Interest Rate Trading | Differenziali tassi banche centrali |
| 62 | NFP Momentum | Non-Farm Payrolls volatilità |
| 63 | Earnings Surprise | Utili vs stime analisti |
| 64 | Carry Trade | Compra valute alto rendimento |
| 65 | EIA Stocks (Oil/Gas) | Report settimanali scorte energetiche |
| 66 | Insider Trading Tracking | Acquisti legali di insider |
| 67 | Dividend Arbitrage | Asimmetrie prezzo stacco cedola |
| 68 | COT Report Sentiment | Posizionamento fondi istituzionali |
| 69 | Intermarket Correlation | Oro/USD, Bond/Equity, etc. |
| 70 | CPI Trading | Reazione ai dati inflazione |

### Quantitative & Algoritmiche (10)

| # | Strategia | Logica |
|---|-----------|--------|
| 71 | Pairs Trading | Spread tra asset correlati |
| 72 | Grid Trading | Rete ordini a intervalli regolari |
| 73 | Market Making Algo | Fornitura liquidità, cattura spread |
| 74 | Cross-Exchange Arb | Differenze prezzo tra exchange |
| 75 | Slipped Moving Average | SMA sfasata per ridurre falsi segnali |
| 76 | HFT Momentum | Ordini istituzionali frazionati |
| 77 | PCA Analysis | Fattori matematici dominanti |
| 78 | Kalman Filter | Tracciamento dinamico riduce rumore |
| 79 | Sentiment NLP | Social media + news feed |
| 80 | Monte Carlo Path | Scenari probabilistici per TP/SL |

### Opzioni & Derivati (10)

| # | Strategia | Logica |
|---|-----------|--------|
| 81 | Covered Call | Compra asset, vendi Call |
| 82 | Iron Condor | Lateralità: vendi Put + Call distanti |
| 83 | Protective Put | Put a protezione portafoglio |
| 84 | Long Straddle | Call + Put stesso strike (vol esplosiva) |
| 85 | Bull Call Spread | Call inferiore + Call superiore |
| 86 | Bear Put Spread | Put superiore + Put inferiore |
| 87 | Calendar Spread | Scadenze diverse stesso strike (Theta) |
| 88 | Cash-Secured Put | Vendi Put su titoli desiderati |
| 89 | Iron Butterfly | Put + Call attorno a strike centrale |
| 90 | Gamma Scalping | Delta-neutral su opzioni lunghe |

### Portafoglio & Esotiche (10)

| # | Strategia | Logica |
|---|-----------|--------|
| 91 | All Weather Portfolio | Azioni, bond, oro, commodity |
| 92 | Systematic Rebalancing | Vendi vincenti, compri perdenti |
| 93 | Currency Hedge | Posizioni contrarie su Forex spot |
| 94 | Smart Beta | Fattori: bassa volatilità, alto valore |
| 95 | Seasonal Commodity | Cicli semina/raccolto su futures agricoli |
| 96 | Crypto DCA Trend | Accumulo solo in mercati rialzisti |
| 97 | Funding Rate Arb | Differenziali tassi Spot/Perpetui |
| 98 | Value + Technical Exit | Acquisti value, uscita tecnica |
| 99 | Futures Calendar Spread | Compra/vendi stessa materia prima, mesi diversi |
| 100 | Anti-Martingala | Size aumenta dopo win, cala dopo loss |

## 12. Stop condition

L'Autopilot non è completo quando "funziona una demo".

**Fase Fondazione**: completa quando G7 è PASSED e la smallest evaluation
autorizzata è stata completata senza policy breach. Il funded rollout richiede
inoltre G8.

**Fase Mutageno**: completa quando G14 è PASSED — il sistema scopre,
sperimenta e promuove autonomamente nuove strategie, adattandosi al mercato
in tempo reale senza intervento umano (con kill switch remoto).

Qualunque dubbio su dati, regole, ledger, risk, broker o licenza mantiene il
sistema in RESEARCH_ONLY, PAPER o ASSISTED_ONLY.

## 13. Opzione C — Zero-cost workflow (2026-08-17)

**PIVOT 2026-08-15 → formalizzato 2026-08-17**:
dopo l'audit `live-readiness-assessment` (2026-08-10) + il `comprehensive-state-report`
(2026-08-15) + il `deep-research-synthesis` (2026-08-15 con 102 agenti / 20 fonti),
il verdetto è: **bloccante è l'edge, non l'architettura**. Lo stack istituzionale
(nautilus/vectorbt/polars/cvxpy) è già installato. Pivot a "Opzione C" = workflow
gratuito Phase 1+2 per validare 3 lane su dati free, prima di spendere budget per
architettura aggiuntiva. Vedi [ADR-020](docs/ADR/ADR-020-zero-cost-data-strategy.md)
per l'inventario fonti verificate.

| Step | Cosa | Stato | Output |
|---|---|---|---|
| Pre | BinanceVisionHistorical adapter per lake crypto 1m | ✅ DONE | 27 test, BTCUSDT 1m 2880 bars smoke |
| 1 | AI swarm storico 50 ticker (as-of 2020-01-01, 12mo fwd) | ✅ DONE 2026-08-17 | REDUCE_SIZE 66.7% beat SPY (edge real, Haiku synthesis ~30% vuote) — `docs/reports/ai-swarm/historical-2020-01-01-50tickers.md` |
| 2 | VRP BS backtest su SPY+VIX 2010-2025 reale | ✅ DONE 2026-08-17 | Sharpe -0.08 (vs 7.36 deep-research claim = 95× inflated, stesso bug R5 BL-503). 69/798 tail events = 8.6% abbattono premium. NON tradabile senza regime filter + tail cap. `docs/reports/lane-d-vrp/2026-08-17-spy-vix-2010-2025.md` |
| 3 | Composite Lane B vs Legacy AND su SimFin real 185 tickers | ✅ DONE 2026-08-17 | Sharpe 0.93 vs 0.25, alpha +59% vs -32%. Composite adottato come default `use_composite=True`. `docs/reports/lane-b-composite/2026-08-17-compare.md` |
| 4 | Paper trading orchestrator (signal→order→fill, slippage ledger) | ✅ MVP DONE 2026-08-17 | `execution/paper_orchestrator.py` + 14 test. Real-time loop + Lane B/D signal adapters deferred |
| 5 | Docs update (ADR-020 + ROADMAP Opzione C + BACKLOG items) | ✅ DONE 2026-08-17 | questo ADR-020 + sezione ROADMAP §13 + BACKLOG BL-OPC-1..5 |
| 6 | Backfill IBKR paper 1m cron (ES/NQ/GC/CL going forward) | 🟡 MVP DONE, timer NON installato | `scripts/backfill_1m_ibkr_paper.py` validato 2026-08-17 (equities 1m); timer systemd non ancora in `~/.config/systemd/user/`; futures = expiry resolution TODO (BL-OPC-6) |

**Verdetto intermedio Opzione C (aggiornato 2026-08-18):**
- Lane B composite **edge reale confermato** (Sharpe 0.93, alpha +59%) —
  prima della promozione paper serve qualificazione DSR/PBO/CPCV (ADR-017, BL-OPC-12).
- Lane D VRP **edge assente** senza regime filter + tail cap — non deployable.
- AI swarm **edge condizionale** (REDUCE_SIZE 66.7% beat SPY su 2020-2021
  bull market) — da validare su 2022 bear + fix Haiku parsing.

**Cosa NON risolve Opzione C**:
- Edge su Lane D VRP (manca OPRA options real, sostituito da BS synthetic);
- Futures 1m storico pre-2025 (solo going forward via Step 6 cron);
- Validazione AI swarm 2022 bear (todo Step 1 followup).

**Prossimo gate richiesto**: G5 (Research truth + strategy qualification) —
le 3 lane di Opzione C devono superare DSR/PBO/CPCV (ADR-017) prima
di promozione paper → shadow → evaluation → funded.
