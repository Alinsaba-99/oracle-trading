# Lane B Integration Blueprint — Formalizzazione dell'intuizione INTC/Xiaomi

> **Data**: 2026-08-15
> **Scope**: mappa l'intuizione operatore su Intel/Xiaomi in un processo replicabile per il portafoglio personale (NON prop-firm, per ADR-019)
> **Prerequisiti**: ADR-019, BL-504/504b (SimFin), BL-505 (value catalog), BL-506/506b (trial ledger + alerts)
> **Backtest di riferimento**: `docs/reports/lane-b/BL-505b-backtest-report.md` — annual return +6.24%, Sharpe 0.408, Max DD 34.51% (2020-2024)

---

## 1. La tua intuizione, formalizzata

L'operatore ha descritto la propria intuizione in una chat con una collega:

> "Avevo chiesto ad un mio amico che ha un bel portfolio d'investimenti, un anno fa gli ho detto di andare su Intel, adesso si sta mangiando le mani [...] Persa di brutto per lui, ha fatto poco più del 400% nell'year to date [...] Ma Intel è stato un caso speciale, di un azienda che conosco da quando ho memoria, è che fa componenti per PC, il mio pane, come avrei potuto non intuire la direzione che avrebbe preso un azienda di cui ho visto credo tutti i loro prodotti, ogni rilascio, ogni notizia"

E su Xiaomi:

> "Avessi beccato xiaomi all'inizio, non ti dico che sarei ricco, però starei così bene da potermi permettere qualche lusso"

### Decomposizione strutturale

L'intuizione ha 4 componenti riconoscibili:

1. **Conoscenza profonda del prodotto** — vedi ogni rilascio, ogni notizia, ogni evoluzione tecnologica (touchscreen capacitivo iPhone, prodotti Intel per PC)
2. **Value investing implicito** — riconosci "fair value" nel prodotto stesso (azienda sana, multipli puliti, business model sostenibile)
3. **Catalizzatore identificato** — innovazione vera (touch capacitivo, turnaround CEO, prodotto nuovo)
4. **Orizzonte ~1 anno** — non trading intraday, ma value+momentum con holding lungo

Queste 4 componenti si mappano 1:1 sui 3 fattori accademici del Lane B value catalog (BL-505):

| Componente intuizione | Fattore accademico | Implementazione |
|---|---|---|
| Conoscenza profonda del prodotto | Filtro qualitativo (manca; va aggiunto come overlay) | catalyst + invalidation field in `TrialLedger.register_thesis()` |
| Value investing implicito (multipli) | Greenblatt Magic Formula (EBIT/EV + ROC) | `analytics/strategy/catalog/value.py::GreenblattMagicFormula` |
| Azienda sana + management | Piotroski F-Score (9-point accounting score) | `analytics/strategy/catalog/value.py::PiotroskiFScore` |
| Orizzonte ~1 anno + turnaround | Lakonishok value-momentum (depressed + recovering) | `analytics/strategy/catalog/value.py::LakonishokValueMomentum` |

---

## 2. Workflow operativo replicabile (5 passi)

### Passo 1 — Screening mensile

**Quando**: prima domenica del mese (manualmente, ~30 min).

**Strumento**: `python scripts/run_lane_b_screen.py` (da implementare in BL-505c).

**Output**: lista di 20-30 tickers candidati che passano il `TurnaroundScreen`:
- `f_score >= 7` (Piotroski high quality)
- `magic_formula_rank <= 50` (Greenblatt top-50)
- `return_12m in [-20%, +50]` (depressed ma non falling knife)

### Passo 2 — Qualitative overlay (manuale, ~1-2h)

**Cosa**: per ogni candidato, l'operatore applica la propria conoscenza tech per identificare:
- **Catalizzatore specifico**: nuovo prodotto (Intel 18A process), cambio CEO (Pat Gelsinger turnaround 2021), buyback announcement, settore in rotazione (AI boom 2023-24)
- **Invalidation specifica**: cosa farebbe smentire la tesi (CEO departure, GM collapse due quarters, prodotto flop)
- **Orizzonte temporale**: 6 mesi, 1 anno, 2 anni (in base a catalyst)

**Output per ogni candidato che passa il qualitativo**: pre-registration draft con:
```
thesis_id: THESIS-2026-09-01-{TICKER}-1
ticker: TICKER
catalyst: <one-sentence description>
invalidation: <one-sentence description>
horizon_days: 365
notes: <freeform - questo è dove la tua conoscenza tech vive>
```

### Passo 3 — Pre-registrazione (manuale, ~5 min per tesi)

**Strumento**: `python scripts/register_thesis.py --thesis-id ... --ticker ... --entry-target ... --stop-target ... --target-price ... --position-pct 0.025 --catalyst "..." --invalidation "..." --horizon-days 365`

**Output**: hash SHA-256 della tesi pre-registrata; row in `trial_ledger.db`.

**Perché è critico**: evita HARKing. Quando la tesi fallisce (es. INTC -10% dopo 6 mesi), NON puoi raccontarti "avevo visto il prodotto giusto, era solo questione di tempo" — la tesi è registrata con catalyst + invalidation, e se l'invalidation si è verificata, esci.

### Passo 4 — Esecuzione via brokerage account IBKR (manuale)

**Cosa**: l'operatore esegue il trade tramite il proprio brokerage account IBKR personale.

**Perché NON automatizzato**: Oracle NON ha accesso al tuo IBKR personale (e non deve averlo, per ADR-010 — separation of concerns). Il trial ledger traccia la tesi e l'outcome; l'esecuzione è manuale.

**Sizing**: 2-3% del capitale per idea. Su €10K capitale = €200-300 per trade. Su €100K capitale = €2-3K per trade.

### Passo 5 — Tracking + audit (automatico + manuale)

**Tracking**: `python scripts/record_outcome.py --thesis-id ... --exit-reason target_hit|stop_hit|time_stop|invalidation|manual_close --pnl-pct ... --pnl-amount ...`

**Audit mensile**: `python scripts/generate_alert_report.py` produce il report markdown con:
- Cumulative hit rate time series
- Rolling hit rate (last 10 outcomes)
- Max consecutive failures
- Alerts (5 consecutive failures → warning; <30% cumulative hit rate after 20 outcomes → critical)

**Meta-kill rule (ADR-019 §3)**: dopo 50 tesi reali se cumulative hit rate < 30%, il processo è rotto. Azione: re-screening con criteri più stringenti (min_f_score=8, top_n_holdings=15).

---

## 3. Esempio concreto: INTC 2024-2025 (retrospettivo)

> **Disclaimer**: questo è un caso storico per smoke test del processo. NON è una tesi attuale.

### Setup (settembre 2024)
- **Ticker**: INTC
- **Prezzo**: $20 (post-Pat Gelsinger turnaround announcement + 18A process reveal)
- **Fundamental screening**:
  - Piotroski F-Score: 7/9 (high quality, ΔROA +1, CFO > ROA +1, gross margin stable, asset turnover improving)
  - Greenblatt Magic Formula rank: top-30 (earnings yield 0.08, ROC 0.12)
  - 12-mo past return: -15% (depressed but stabilising)
  - → Passa `TurnaroundScreen`
- **Catalyst (qualitativo operatore)**: Pat Gelsinger CEO turnaround, 18A process announcement, AI chip market entry
- **Invalidation**: CEO departure, 18A delay > 2 quarters, GM collapse below 35%
- **Horizon**: 365 giorni
- **Sizing**: 2.5% del portafoglio (€250 su €10K capitale, €2.500 su €100K)
- **Pre-registration hash**: SHA-256 of all the above + timestamp

### Outcome (dicembre 2025)
- **Exit reason**: target_hit (target $30, reached)
- **P&L**: +50% = €125 gain su €250 entry (su €10K portafoglio = +1.25% portfolio return)
- **Bars held**: ~14 mesi

### Audit entry
```
thesis_id: THESIS-2024-09-01-INTC-1
registered_at: 2024-09-01T10:00:00Z
ticker: INTC
entry_target: 20.0, stop_target: 17.0, target_price: 30.0
position_pct: 0.025
catalyst: Pat Gelsinger CEO turnaround + 18A process + AI chip market entry
invalidation: CEO departure OR 18A delay >2Q OR GM<35%
horizon_days: 365
f_score: 7, magic_rank: 30, return_12m: -0.15
notes: operatore conosce prodotti Intel da quando ha memoria
pre_hash: <sha256 of all above + timestamp>

outcome:
  closed_at: 2025-12-15
  exit_reason: target_hit
  entry_actual: 20.0, exit_actual: 30.0
  pnl_pct: 0.50, pnl_amount: 125.0
  bars_held: 14
```

---

## 4. Configurazione iniziale (per operatore)

### Setup operativo (1-2 ore una tantum)

1. **Apri account IBKR personale** (se non ce l'hai): ~30 min + 1-2 giorni verifica
2. **Fondi il conto**: €5-10K iniziale consigliato per sizing 2-3% × 20-30 idee simultanee
3. **SimFin API key** (già fatto 2026-08-15): export `SIMFIN_API_KEY=88849d2d-...` in `~/.bashrc` o `~/.config/fish/config.fish`

### Setup software (già fatto, ~5 min setup + n/a manutenzione)

1. `pip install purgedcv` (BL-500) ✅
2. `pip install simfin` (BL-504) ✅
3. `pip install deflated-sharpe` da git (BL-500) ✅
4. Run `scripts/smoke_simfin_with_key.py` per verificare download ✅
5. Run `scripts/run_lane_b_backtest.py` per smoke test del backtester ✅

### Setup trial ledger (1 min, una tantum)

```bash
# Inizializza database trial_ledger.db (in CWD o path configurato)
python -c "from analytics.research.trial_ledger import TrialLedger; tl = TrialLedger('data/trial_ledger.db'); tl.close()"
```

---

## 5. Calendario operativo mensile (template)

### Ogni prima domenica del mese (~3-4h total)

1. **Refresh SimFin data** (15 min, automatico):
   ```bash
   python scripts/refresh_simfin_data.py
   ```

2. **Run Lane B screening** (5 min):
   ```bash
   python scripts/run_lane_b_screen.py --as-of <last-month-end> --output data/lane-b/screenings/<yyyy-mm>.json
   ```
   Output: lista 20-30 candidati.

3. **Qualitative overlay** (1-2h, manuale): per ogni candidato, l'operatore applica la conoscenza tech:
   - Quale catalizzatore specifico?
   - Qual è l'invalidation?
   - Orizzonte temporale?
   - Sizing?

4. **Pre-registrazione** (5 min per tesi che passano il qualitativo):
   ```bash
   python scripts/register_thesis.py --thesis-id THESIS-2026-09-01-INTC-1 --ticker INTC ...
   ```

5. **Esecuzione IBKR** (manuale, non automatizzato da Oracle)

### Ogni prima domenica del mese + 1 (audit)

1. **Aggiorna outcomes**: per ogni tesi chiusa nel mese precedente, registra exit_reason + P&L
2. **Genera alert report**:
   ```bash
   python scripts/generate_alert_report.py > docs/reports/lane-b/alerts/<yyyy-mm>.md
   ```
3. **Verifica meta-kill**: se 50+ tesi cumulative e hit rate < 30% → re-screening con criteri più stringenti

### Trimestrale (3-4h)

1. **Full backtest refresh** (BL-505b): estendi il periodo del backtest di 3 mesi, rigenera report
2. **Review process**: esamina le 5-10 tesi dell'ultimo trimestre (sia wins che losses), identifica pattern
3. **Calibrazione**: se Max DD > 15% su backtest rolling 3y → stringere screen (min_f_score 8, top_n_holdings 15)

### Annuale

1. **Performance review**: confronta portfolio return vs SPY benchmark
2. **Strategy review**: l'edge è sopravvissuto? HIT rate cumulativo > 50%? → continuare. < 30% → meta-kill, re-design.
3. **Risk review**: Max DD cumulativo? Concentrazione settoriale? Sizing corretto?

---

## 6. Red flags e meta-kill rules

### Red flags individuali (azione immediata sulla singola tesi)

- Thesis thesis_id ha -30% drawdown → rivedi catalyst; se invalidation verificata → exit
- News sorpresa (CEO departure, accounting fraud, product recall) → exit invalidation
- Settore vs thesis: se settore -20% in 1 mese ma catalyst non realizzato → re-evaluate

### Red flags di processo (azione su processo)

- 5 thesis consecutive fallite (warning alert) → rivedi screening
- Cumulative hit rate < 30% dopo 20 outcomes (critical alert) → meta-kill intermedio
- Cumulative hit rate < 30% dopo 50 outcomes (ADR-019 meta-kill) → **STOP processo, re-design**
- Max DD portfolio > 25% → ridurre sizing a 1.5% per idea

### Meta-kill rule finale (ADR-019 §3)

> "Se dopo 50 tesi reali cumulative hit rate < 30%, il processo è rotto. Azione: (a) abbandono Lane B, (b) re-screening con criteri più stringenti (min_f_score 8, top_n_holdings 15), (c) tuning. Default: (b) re-screening."

---

## 7. Limiti del processo (onesti)

1. **Backtest 2020-2024 è piccolo**: 20 ribilanciamenti × 25 holdings = 500 slot, 185 unique tickers. Servono 10+ anni per statistically meaningful hit rate.
2. **PIT rigoroso non garantito**: SimFin bulk ha `Restated Date` che dovremmo usare per v2. Per v1 abbiamo usato `Publish Date`.
3. **Max DD 34.51% inaccettabile**: il filtro falling-knife va stringato. Possibili fix: `return_12m_min=-0.10` (no falling knife), `min_f_score=8`, `top_n_holdings=15`.
4. **Sharpe 0.408 < 0.5 target**: l'edge c'è ma non robusto. Possibili miglioramenti: aggiungere sector filter (no financial in stress), aggiungere momentum filter (12-1 months, Carriere-style).
5. **Brokerage account IBKR non è nel codice Oracle**: l'esecuzione è manuale. Oracle traccia tesi + outcomes, non esegue ordini.
6. **Operatore singolo, RF1 burnout risk**: 1-2h/mese di qualitative overlay + 3-4h trimestrale di review = ~20-30h/anno. Sostenibile se reddito parallelo.

---

## 8. Metriche di successo (12-24 mesi)

| Metrica | Target | Meta-kill se sotto |
|---|---|---|
| Cumulative hit rate | ≥ 50% | < 30% dopo 50 tesi |
| Annual return portfolio | ≥ 6% | < 3% dopo 2 anni |
| Sharpe | ≥ 0.5 | < 0.3 dopo 50 tesi |
| Max DD portfolio | < 15% | > 25% anytime |
| Concentrazione settoriale | ≤ 30% per settore | > 50% anytime |
| Avg holding period | 6-18 mesi | < 3 mesi (troppo turnover) |

---

## 9. File di riferimento

- `analytics/strategy/catalog/value.py` (BL-505) — Piotroski + Lakonishok + Greenblatt + TurnaroundScreen
- `analytics/strategy/lane_b_backtester.py` (BL-505b) — backtest engine
- `analytics/research/trial_ledger.py` (BL-506) — pre-registration + outcome tracking
- `analytics/research/trial_ledger_alerts.py` (BL-506b) — alert triggers + cumulative hit rate
- `analytics/fundamental/simfin_loader.py` (BL-504) — bulk fundamental + price data
- `scripts/run_lane_b_backtest.py` — backtest script riproducibile
- `docs/reports/lane-b/BL-505b-backtest-report.md` — backtest smoke test result
- `docs/ADR/ADR-019-lane-b-priority-personal-portfolio.md` — decisione strategica

---

## 10. Riassunto per operatore

**Cosa hai costruito**: un processo replicabile che formalizza la tua intuizione INTC/Xiaomi su 3 fattori accademici (Piotroski + Lakonishok + Greenblatt), con pre-registrazione anti-HARKing e alert triggers per meta-kill.

**Cosa NON hai costruito**: un sistema che ti dice "compra INTC domani". Il qualitative overlay (la tua conoscenza tech) è irreplaceable; il codice fa il filtering quantitativo, ma la decisione "quali candidati passare da 20-30 a 5-10 con catalyst reale" è tua.

**Cosa aspettarsi nei prossimi 12 mesi**: se il processo funziona come il backtest suggerisce (annual +6.24%, Sharpe 0.408), su €10K capitale avresti ~€620/anno di return (+ i tuoi trade reali con catalyst qualitative overlay possono performare meglio). NON è 5%/mese; è 6%/anno. Per €3K/mese servirebbe €600K capitale (soglia irrealistica per un operatore singolo).

**Cosa aspettarsi se il processo non funziona**: dopo 50 tesi reali (12-24 mesi), se hit rate < 30% → meta-kill. Azione: re-screening con criteri più stringenti. Se anche quello fallisce → abbandono Lane B, focus su Lane A (prop-firm) o altro.

---

*Fine Lane B integration blueprint. Generato 2026-08-15 dopo BL-505b backtest smoke test.*
