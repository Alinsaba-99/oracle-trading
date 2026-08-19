# ADR-019: Lane B priority — portafoglio personale operatore, NON prop-firm

**Data:** 2026-08-15
**Status:** ACCEPTED (post deep-research synthesis 2026-08-15 + operatore decisione)
**Related:** ADR-018 (prop-firm structural EV), ADR-013 (versioned prop-firm rule catalog), ADR-014 (M31 evidence loss)

---

## Context

Il deep-research del 2026-08-15 (`docs/reports/2026-08-15-deep-research-synthesis.md`) ha confermato che la Lane B (turnaround su paniere azionario, formalizzazione dell'intuizione INTC/Xiaomi dell'operatore) **NON è compatibile con le prop-firm target**:

- **The5ers** offre MT5/CFD su FX/metals/indices — non single stocks
- **Lucid LucidPro** offre futures CME — non single stocks
- **MyFundedFutures** offre futures — non single stocks

L'operatore ha espresso l'obiettivo di perseguire **Lane A (prop-firm path) e Lane B (turnaround portafoglio personale) in parallelo**, con Lane B come **primo step immediato** (no setup manuale richiesto oltre la SimFin API key, già fornita).

## Decision

### 1. Lane B è **portafoglio personale operatore**, NON prop-firm strategy

Lane B è il percorso dove l'operatore ha **vantaggio informativo strutturale** (deep tech knowledge su aziende come Intel/Xiaomi, know-how sui prodotti, familiarità con bilanci e communicationi aziendali). Questo vantaggio NON è monetizzabile via conto funded prop-firm; lo è via **brokerage account personale** (Interactive Brokers, ecc.).

### 2. Prerequisiti di deploy capitale personale (Lane B)

A differenza di ADR-018 (prop-firm gate: ≥250 sessioni paper pass ≥90% + DSR/PBO/PSR), Lane B ha prerequisiti più soft:

1. **Trial ledger S0.3 (BL-506)** attivo: ogni tesi pre-registrata con hash SHA-256 (no HARKing)
2. **Hit rate cumulativo target ≥ 50%** (vs base rate retail ~3% che batte il mercato; target più realistico per operatore informato)
3. **Sharpe target ≥ 0.5** su paniere 20-30 titoli turnaround simultanei
4. **Sizing ≤ 2-3% per idea** (riduzione rischio blowup su singolo nome)
5. **Invalidation rigorosa**: ogni tesi ha criterio di invalidation predefinito (target/stop/tempo); uscita disciplinata

Questi prerequisiti sono meno rigidi di ADR-018 perché:
- Non c'è la fee-extraction drag di ADR-018 (brokerage account non ha il "modello prop-firm")
- Operatore può uscire dal trade in qualsiasi momento senza vincoli di "challenge target"
- Capitale personale = rischio proprio, non rischio di "perdere il conto funded"

### 3. SimFin (BL-504) è la fonte dati PIT ufficiale

`SimFinLoader` (`analytics/fundamental/simfin_loader.py`) con API key `SIMFIN_API_KEY` (env var, già fornita dall'operatore 2026-08-15) è la fonte dati primaria per fundamental data point-in-time.

Dati scaricati verificati 2026-08-15:
- 6.537 US companies nell'universo
- 49.020 income statements trimestrali
- 49.017 balance sheets trimestrali
- 49.019 cash-flow statements trimestrali
- 6.225.717 righe di daily share prices

### 4. Universo Lane B

- **20-30 titoli** per tesi di turnaround simultanea (diversificazione cross-settore)
- **Screening criteria** (`analytics/strategy/catalog/value.py::TurnaroundScreen`):
  - `f_score >= 7` (Piotroski high quality)
  - `magic_formula_rank <= 50` (Greenblatt top-50)
  - `return_12m in [-0.20, +0.50]` (depressed ma non falling knife)

### 5. Workflow Lane B (5 passi)

1. **Screening** (settimanale): `TurnaroundScreen.screen()` su universo SimFin
2. **Pre-registrazione** (prima del trade): `TrialLedger.register_thesis()` con catalyst + invalidation + sizing 2-3%
3. **Esecuzione**: tramite brokerage account personale (es. IBKR; non automatizzato da Oracle)
4. **Tracking**: `TrialLedger.record_outcome()` con exit_reason (target_hit/stop_hit/time_stop/invalidation/manual_close)
5. **Audit** (trimestrale): `TrialLedger.export_for_audit()` + `hit_rate()` per verifica processo

## Rationale

1. **Vantaggio informativo strutturale dell'operatore**: deep tech knowledge su aziende come Intel, AMD, Xiaomi è il vero edge che Oracle non ha sui futures daily. Riconoscerlo come Lane B è onesto.

2. **RF-DR5 (deep-research synthesis §red flags)**: "Lane B turnaround NON è prop-firm strategy (equities non su MT5/futures) → portafoglio personale operatore". Questo ADR formalizza la decisione.

3. **Coerenza con ADR-018**: ADR-018 è per capitale funded (prop-firm); questo ADR è per capitale personale (brokerage). Le soglie sono diverse perché i constraint sono diversi.

4. **Coerenza con ADR-014 (M31 evidence loss)**: il lesson appreso (invalidare run non riproducibili) si estende a "pre-registrare le tesi prima del trade" (no HARKing). Trial ledger S0.3 è l'estensione naturale.

## Consequences

### Positive
- **Operatore ha il vero edge su Lane B**: la sua intuizione INTC/Xiaomi è formalizzata come processo replicabile.
- **No fee-extraction drag**: brokerage account IBKR non ha il modello "challenge fee" delle prop-firm.
- **Capitale personale = rischio proprio**: disciplina naturale (non si "gioca con i soldi degli altri").
- **Validazione su dati SimFin reali** (49K statements × 6.5K companies = sufficiente per statistically meaningful backtest).
- **Trial ledger S0.3** pre-registra ogni tesi: no HARKing, processo auditable.

### Negative
- **Non è prop-firm path**: NON contribuisce al target 5%/mese via prop-firm (Lane A/C restano per quello).
- **Capitale personale richiesto**: operatore deve finanziare il portafoglio con proprie risorse (€5-10K iniziale consigliato per sizing 2-3% × 20-30 titoli).
- **Edge non garantito**: anche con vantaggio informativo, il backtest può mostrare hit rate < 50% su 100+ tesi. Meta-kill rule se dopo 20 tesi reali l'hit rate < 30%.
- **Time-intensive**: 1-2 anni per accumulare 50+ tesi reali con outcomes (vs 30 sessioni paper in un weekend per futures).

## Enforcement

- **Codice**: `analytics/strategy/catalog/value.py` (BL-505 DONE) + `analytics/research/trial_ledger.py` (BL-506 DONE) + `analytics/fundamental/simfin_loader.py` (BL-504 DONE).
- **Backtester**: `LaneBBacktester` da implementare (BL-505b, in corso) per validare Piotroski + Lakonishok + Greenblatt su SimFin historical data.
- **Trial ledger report**: estensione `trial_ledger.py` con report cumulativo + alert trigger 5 thesis consecutive fallite (BL-506b, in corso).
- **Documentation**: questo ADR + `docs/reports/lane-b/integration-blueprint.md` (BL-integration blueprint, in corso).

## Alternatives considered

1. **Lane B come prop-firm via single-stock CFD**: rifiutato. The5ers MT5 non offre single-stock CFD in modo affidabile; anche se offerto, lo spread CFD sui single-stock erode l'edge. Inoltre la leva 1:30 CFD è inadatta al turnover multi-anno di Lane B.

2. **Lane B come futures via single-stock futures**: rifiutato. Single-stock futures (SSF) su CME sono illiquid tranne che per i top 10 nomi. Inadatto a paniere 20-30 small/mid cap.

3. **Saltare Lane B, concentrarsi su Lane A/C**: rifiutato dall'operatore (decisione 2026-08-15: "both in parallelo"). RF-DR5 (deep-research) indica che Lane B è dove l'operatore ha vero edge strutturale.

4. **Aspettare Lane B fino a dopo Lane A verde**: rifiutato. Lane B può procedere in parallelo; non competono per lo stesso capitale (Lane A = prop-firm funded, Lane B = portafoglio personale).

## Open questions

1. **Brokerage account IBKR setup**: l'operatore deve aprire un account IBKR personale se non ce l'ha. Setup manuale ~1-2 ore + funding iniziale €5-10K. NON blocca il backtest Lane B (può validare su dati SimFin senza account live).

2. **Meta-kill rule per Lane B**: se dopo 50 tesi reali l'hit rate cumulativo < 30%, il processo è rotto. Definire policy: (a) abbandono Lane B, (b) re-screening con criteri più stringenti, (c) tuning. Default: (b) re-screening.

3. **Frequenza di screening**: settimanale, mensile, o solo su trigger di catalyst (es. earnings, cambio CEO, buyback announcement)? Default: mensile + alert su trigger.

## References

- Deep-research synthesis 2026-08-15: `docs/reports/2026-08-15-deep-research-synthesis.md` §2.5 (Lane B value-turnaround).
- Consulenza esterna 2026-08-15: `docs/reports/2026-08-15-consultation-observations.md`.
- Piotroski, J. (2000). "Value Investing." J. Accounting Research 38(Suppl):1-41.
- Lakonishok, Shleifer, Vishny (1994). "Contrarian Investment, Extrapolation, and Risk." J. Finance 49(5):1541-1578.
- Greenblatt, J. (2005). "The Little Book That Beats the Market."
- SimFin: https://github.com/SimFin/simfin (MIT, bulk data API).
- BL-504 (SimFin install + smoke), BL-505 (Lane B value catalog), BL-506 (trial ledger S0.3).

## Implementation pointers

- `analytics/fundamental/simfin_loader.py` (BL-504 DONE) — bulk fundamental + price data
- `analytics/strategy/catalog/value.py` (BL-505 DONE) — Piotroski + Lakonishok + Greenblatt + TurnaroundScreen
- `analytics/research/trial_ledger.py` (BL-506 DONE) — pre-registration + outcome tracking
- `analytics/strategy/lane_b_backtester.py` (BL-505b, in corso) — backtest engine per validare le 3 strategie su SimFin historical
- `analytics/research/trial_ledger_alerts.py` (BL-506b, in corso) — alert trigger 5 thesis fallite
- `docs/reports/lane-b/integration-blueprint.md` (in corso) — mappa INTC/Xiaomi → processo replicabile
