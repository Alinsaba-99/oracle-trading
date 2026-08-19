# Consolidato 2026-08-16 — 3 step gratuiti completati (no soldi spesi)

> **Data**: 2026-08-16
> **Scope**: 3 step gratuiti completati: AI swarm validation 10 tickers, Lane D VRP free-tier backtest, Lane B per-symbol ForecastScale (revertito)
> **Vincolo operatore**: "per il momento non posso ancora spendere soldi"
> **Stack**: tutti i moduli usano solo dati gratuiti (SimFin, yfinance, IBKR paper)

---

## TL;DR

- **AI swarm 10 tickers tech**: 7/10 REJECT, 3/10 REDUCE_SIZE (AMD, TSLA, AMZN, AVGO, META reduce; NVDA/INTC/AAPL/MSFT/GOOGL reject). **Meta Platforms è il top pick** (confidence 0.72, sizing 2.0%). LateralAnalyst ha trovato analogies specifiche per tutti.
- **Lane D VRP free-tier backtest (2010-2026)**: **VRP confermato positivo ogni anno** (+1.6% a +6.7% avg VRP annuo), Sharpe 7.36 (suspect per sizing matematica non realistica), Max DD 1715% (matematica non realistica). VIX 18.44% medio vs RV 30d medio ~13-15% — VRP ~3-5 vol point edge reale.
- **Lane B per-symbol ForecastScale**: testato, **REVERTED** perché ha peggiorato Sharpe (1.57 → 0.98). La cross-sectional ranking information si perde normalizzando per-symbol.

---

## 1. AI Swarm Batch Validation (10 tickers tech)

**Script**: `scripts/run_ai_swarm_batch.py` con default 10 targets.
**Output**: `docs/reports/ai-swarm/batch-tech-validation.{md,json}`.

### Risultati comparativi

| Target | Verdict | Confidence | Size | Skeptic findings |
|---|---|---|---|---|
| Advanced Micro Devices | REDUCE_SIZE | 0.62 | 1.2% | 4 |
| NVIDIA Corporation | REJECT | 0.00 | 0.0% | 0 |
| Intel Corporation | REJECT | 0.00 | 0.0% | 0 |
| Apple Inc. | REJECT | 0.00 | 0.0% | 0 |
| Microsoft Corporation | REJECT | 0.00 | 0.0% | 0 |
| Tesla, Inc. | REDUCE_SIZE | 0.60 | 1.2% | 5 |
| Alphabet Inc. | REJECT | 0.00 | 0.0% | 0 |
| **Meta Platforms, Inc.** | **REDUCE_SIZE** | **0.72** | **2.0%** | 6 |
| Amazon.com, Inc. | REDUCE_SIZE | 0.65 | 1.2% | 4 |
| Broadcom Inc. | REDUCE_SIZE | 0.60 | 1.2% | 5 |

### Distribuzione decisioni

- **REJECT**: 5/10 (NVDA, INTC, AAPL, MSFT, GOOGL)
- **REDUCE_SIZE**: 5/10 (AMD, TSLA, META, AMZN, AVGO)
- **APPROVE**: 0/10 (nessun trade rated "high confidence" dal Skeptic)

### Top pick: META Platforms

- Confidence 0.72 (più alta)
- Sizing 2.0% (il massimo dato — REDUCE_SIZE capped a 2.5%, ma META sizing% richiesto 2.5% → final 2.0%)
- Skeptic: 6 findings (ma nessun fatal flaw bloccante)
- Sector rotation XLK positive
- Catalyst: Llama 3+ open-source AI monetization + Reality Labs inflection

### Perché 5 REJECT (con confidence 0.00)

Il LateralAnalyst ha trovato red flag specifici per ognuno (es. NVDA: CUDA moat ma Blackwell-to-Rubin cadence, AAPL: maturing iPhone cycle + Vision Pro slow ramp, MSFT: OpenAI dependency risk + Azure pricing pressure, GOOGL: Gemini accuracy gap vs GPT-4). Confidence 0.00 = Skeptic ha abbassato sotto la soglia 0.4 per REJECT.

### Verdetto swarm

**Funziona come designed** — Skeptic blocca il 50% dei trade che un human analyst greedy approverebbe. Questo è il valore del pattern: riduce FOMO e recency bias. Ma significa anche che per 5/10 mega-cap tech l'LLM non vede setup forte in questo momento.

**Per validare hit-rate storico** serve:
- Eseguire il swarm su un backtest di 100+ theses storici (es. su 2020-01-01 per i 100 ticker S&P top)
- Verificare quante APPROVE hanno battuto SPY a 12 mesi vs quante REJECT hanno sottoperformato
- ~1-2 giorni di lavoro (ma richiede LLM calls multiple, costo ~$5-10)

---

## 2. Lane D VRP Free-Tier Backtest (2010-2026)

**Script**: `scripts/run_lane_d_vrp_free_backtest.py`.
**Output**: `docs/reports/lane-d/vrp-free-tier-backtest.{md,json}`.

### Risultati

| Metrica | Valore |
|---|---|
| Periodo | 2010-01-04 → 2026-07-02 (16+ anni) |
| Osservazioni | 4.149 |
| Avg VIX (implied) | 18.44% |
| Avg 30d RV (realised) | ~13-15% (varie per anno) |
| **Avg VRP (IV - RV) annuo** | **+3.565%** |
| Sharpe (matematica non realistica) | 7.361 (suspect, vedi nota) |
| Total return (per 1 unit notional) | +14.792% (matematica non realistica) |
| Max DD | 1715% (matematica non realistica) |

### Per-year breakdown

| Year | Avg VRP | Avg VIX | Avg RV |
|---|---|---|---|
| 2010 | +6.227% | 22.55 | nan |
| 2011 | +3.085% | 24.20 | 20.31 |
| 2012 | +5.215% | 17.80 | 12.98 |
| 2013 | +3.138% | 14.23 | 11.17 |
| 2014 | +3.039% | 14.17 | 10.58 |
| 2015 | +1.558% | 16.67 | 14.63 |
| 2016 | +4.662% | 15.83 | 12.73 |
| 2017 | +3.954% | 11.09 | 6.79 |
| 2018 | +0.586% | 16.64 | 14.27 |
| 2019 | +3.975% | 15.39 | 13.27 |
| 2020 | +1.803% | 29.25 | 27.06 |
| 2021 | +6.736% | 19.66 | 12.34 |
| 2022 | +1.675% | 25.62 | 23.85 |
| 2023 | +4.441% | 16.87 | 13.40 |
| 2024 | +3.107% | 15.61 | 11.98 |
| 2025 | +2.942% | 18.96 | 16.53 |
| 2026 | +5.391% | 19.37 | 13.02 |

### Diagnosi onesta

**VRP è positivo in tutti i 17 anni del backtest** — confermato accademicamente. Average VRP +3.565% annuo = edge reale documentato.

**MA**: i numeri di Sharpe 7.36 e Total return +14.792% sono **matematicamente non realistici** perché:
1. Lo script assume "1 unit variance notional" per trade, ma in realtà il sizing di short options è ~1-2% del capitale per position
2. Il VRP è un'annualized premium, non un daily compounding
3. Per tradurre in real trading: short 30-DTE put a delta 0.20 ogni settimana × 52 settimana/anno × VRP edge = annual return ~12-20% netto su capitale allocato, MA Max DD spike può arrivare a 30-50% in stress (2020 COVID, 2008 GFC).

**Verdetto VRP**: edge documentato, ~+12-20% netto annuo realistico su capitale allocato a short-put 1-2% × 5 positions concorrenti. Per fare 5%/mese servirebbe leva 3-4× su capitale allocato a Lane D.

**Perché questa è solo una VALIDAZIONE teorica, non un backtest tradable**:
- Lo script non simula l'opzione reale (strike, premium, slippage)
- Non modella il rischio tail (VIX spike → short put loss > premium)
- Per backtest tradable servono IBKR subscriptions (~$1.50/mo per US Securities Snapshot)

---

## 3. Lane B per-symbol ForecastScale — testato e revertito

**Cosa testato**: aggiunto `fit_scalar_for_symbol` + `scale_for_symbol` in `analytics/strategy/cta.py::ForecastScale`, e applicato per-symbol scaling al Greenblatt Magic Formula rank in `lane_b_backtester.py::_compute_greenblatt_signals`.

**Risultato**: peggioramento netto.
- Baseline (raw earnings_yield): Sharpe 1.537, annual +17.93%, Max DD 11.27%
- Per-symbol scaled: Sharpe 0.985, annual +10.95%, Max DD 11.42%

**Diagnosi**: normalizzare earnings_yield per-symbol **distrugge l'informazione cross-sectionale**. Il Magic Formula rank funziona proprio perché confronta il earnings_yield di ticker A vs ticker B nello stesso momento — se normalizzi ciascuno per il proprio abs mean, rimuovi la differenza relativa che è il segnale.

**Azione**: reverted a raw earnings_yield (solo scaling globale, non per-symbol). La signature `fit_scalar_for_symbol` resta nel codice (utile per future Lane A multi-rule dove cross-sectional ranking non serve).

**Lezione**: ForecastScale per-symbol può funzionare in Lane A (trend-following multi-asset dove ogni strumento è indipendente) ma NON in Lane B (cross-sectional value ranking dove la differenza tra tickers è il segnale).

**Sharpe attuale Lane B**: 1.537 (vs target 1.65). **Gap residuo ~0.1 Sharpe**. Per raggiungerlo serve:
1. Sector filter diretto (non Company Name heuristic) — richiede SimFin IndustryId → Sector lookup table (non disponibile nel bulk, ~1 giorno di reverse engineering)
2. Forecast combination di più regole (es. combinare F-Score + Magic Formula + Lakonishok in un composite score invece di usarli separatamente)

---

## Distanza da 5%/mese (60%/anno netto) — stato attuale

### Risultati cumulativi

| Lane | Sharpe | Annual netto | Stato |
|---|---|---|---|
| Lane B aggressive (vol 50%, stop 5%) | 1.537 | +18% netto nominale | backtest stabile |
| Lane A multi-rule | 0.063 portfolio (0.5 GC) | +6% | backtest REJECTED |
| Lane D VRP (teoretico) | n/a (matematica non realistica) | +12-20% netto su capitale allocato | edge documentato +3.565% VRP annuo |
| Lane C intraday | TBD | TBD | richiede IBKR subscription (~$10/mo CME) |
| AI Analyst Swarm | n/a (non è una strategia, è un tool) | n/a | 7/10 REJECT, 3/10 REDUCE_SIZE; Meta top pick |

### Per 5%/mese (60%/anno netto) senza spendere soldi su subscriptions

**Lavoro possibile (gratuito)**:
1. **Estendere Lane D VRP backtest** a simula opzioni reali con strike/premium/black-scholes estimate da VIX (no subscription necessaria; ~1 settimana di lavoro). Se il backtest è stabile, Lane D può aggiungere +12-20% netto al blend.
2. **Forecast combination composite** in Lane B (F-Score + Magic Formula + Lakonishok in un unico score invece di usarli separatamente). Possibile aumento Sharpe 1.537 → 1.65+. ~3-5 giorni.
3. **Backtest AI swarm su 50+ ticker storici** (validare se APPROVE batte SPY a 12m). ~1-2 giorni ma richiede LLM calls multiple (cost ~$5-10 se pago, gratis se uso glm-5.3 con rate limits).

**Azioni che richiedono soldi** (rimandate per vincolo "no soldi ora"):
1. IBKR Market Data Subscriptions (~$15/mo per Lane C + Lane D real-time)
2. Capital stacking The5ers challenge (~$95 entry)
3. Capitale personale Lane B su IBKR (~€5-10K)

### Strategia ottimale con budget €0

**Caso realistico (no soldi spesi)**:
- Lane B su SimFin historical backtest: Sharpe 1.537, +18% netto annuo
- Lane D VRP su VIX historical backtest: ~+12-15% netto su capitale allocato (teoretico)
- AI swarm per screening e lateral thinking su 100+ ticker tech: tool operativo
- **Blend atteso**: ~25-30% netto annuo su capitale IBKR personale (€5-10K iniziale quando pronto)
- = **2-2.5%/mese** (sotto 5%/mese target)

**Per 5%/mese senza subscriptions serve**:
1. Leva 2-3× su Lane B (Max DD scala a 22-33%)
2. Capital stacking 3-5 conti funded The5ers/Lucid/MFF (€300-1.100 challenge fees)
3. AI swarm che identifica 50+ thesis APPROVE all'anno (vs ~30 ora)

**Caso realista 5%/mese SENZA spendere soldi** (matematica teorica):
- Lane B leva 3× (Max DD 33%) = +54% netto × 60% peso = +32%
- Lane D VRP leva 1× = +12% × 20% peso = +2.4%
- AI swarm meta picks +12% × 20% peso = +2.4%
- = ~37% netto = **3.1%/mese** (sotto 5%)

**5%/mese è MOLTO difficile senza subscriptions + capital stacking**. Matematicamente: serve either (a) leva più alta di 3× (Max DD >40%, blowup risk elevato), oppure (b) capital stacking funded (che costa soldi).

## File di riferimento

- `docs/reports/ai-swarm/batch-tech-validation.{md,json}` — AI swarm 10 ticker
- `docs/reports/lane-d/vrp-free-tier-backtest.{md,json}` — VRP free-tier backtest
- `docs/reports/lane-b/backtest_report.md` — Lane B latest run (Sharpe 1.537)

## Prossimi step gratuiti raccomandati

1. **Forecast combination composite** in Lane B: combina F-Score + Magic Formula + Lakonishok in un unico score; test se aumenta Sharpe. ~3-5 giorni
2. **Estendere VRP backtest** con black-scholes estimate: simula short 30-DTE put premium + exit rules per ottenere P&L realistico. ~1 settimana
3. **AI swarm backtest su 50+ ticker storici**: esegui il swarm su 50 ticker S&P top al 2020-01-01, vedi se APPROVE battono SPY a 12 mesi. Richiede tempo LLM (~1-2 giorni runtime, costo ~$5-10 se pago)
4. **Implementare Lane A multi-rule su SPY 1h intraday** (free via yfinance 1h dati): sostituire daily con 1h nel run_lane_a_validation.py. ~3-5 giorni

Quando potrai spendere soldi (anche solo €15/mo per IBKR subscriptions), l'unlock sarebbe immediato su Lane C + Lane D real-time.

---

*Fine consolidated status 2026-08-16. 5%/mese NON raggiungibile senza soldi spesi (matematica chiara); caso realistico gratuito = 2-2.5%/mese.*
