# Piano Sistema Profittevole — Multi-Strategy Core/Satellite/Speculativo

> **STATUS**: piano strategico (deliverable), 2026-08-10. Nessuna implementazione.
> **Contesto**: evolve il piano production-grade (`docs/plan-production-grade.md`)
> con la dimensione "come un sistema profittevole" richiesta dall'operatore:
> core PAC multi-asset a pesi dinamici + satellite direzionale "turnaround"
> + speculativo a coda. Lo scalping sistematico resta subordinato a dati e edge.
> **Metodo**: ogni claim su stato repo è verificato (file:line). Ogni EV è ordine
> di grandezza, non precisione.
> **Fonti**: BACKLOG.md · docs/plan-production-grade.md · docs/reports/s0-1-bl023-autopsy.md ·
> docs/reports/s0-2-economic-model.md · docs/reports/multiasset/walkforward.md ·
> docs/reports/live-readiness-gap-analysis.md ·
> docs/ADR/ADR-010-deterministic-execution-safety-boundary.md ·
> docs/ADR/ADR-011-backtest-discovery-qualification.md · docs/ADR/ADR-012-capability-gates-replace-phases.md ·
> data/lake/metadata/coverage.json · core/domain/mode.py · analytics/strategy/catalog/alpha101.py

## 0. Obiettivo ridefinito (onestamente)

**"Sistema profittevole" qui significa: una struttura che massimizza la
probabilità di profitto nel lungo periodo, non una promessa di rendimento.** La
base di evidenza del repo è chiara: l'alpha sistematico misurato è ≈0 netto
(G5/G6 REJECTED, 0/9 walk-forward, alpha residuo +2-6% lordo). Un sistema
profittevole parte da questo e costruisce in modo diverso:

- **Profitto probabile** = beta gestito (esposizione multi-asset con tilt da
  regime/momentum/vol-target) + rischio controllato. È la lane A.
- **Profitto possibile** = edge *se* un processo sopravvive a test onesti. Le
  lane B (turnaround) e C (scalping) sono costruite per *scoprire* edge con
  gate, non per scommetterci da subito.
- **Nessuna lane viola i gate**: RESEARCH → REPLAY → PAPER → SHADOW →
  EVALUATION → FUNDED è una progressione irregressibile
  (`core/domain/mode.py:82-87`). Il capitale reale arriva solo via gate.

## 1. Evidenza base (verificata)

| Fatto | Valore | Fonte |
|---|---|---|
| Edge sistematico | 0/9 asset×segnale battono buy&hold | `docs/reports/multiasset/walkforward.md` |
| Alpha residuo | +2.3..+6.1% lordo → ~0 netto costi | `docs/reports/s0-2-economic-model.md` §0 |
| Lane daily | economicamente morta (meta-kill) | BACKLOG BL-094 |
| Lake | 101 simboli; daily profondi per ETF/indici/futures/FX/crypto; azioni singole = solo AAPL, MSFT | `data/lake/metadata/coverage.json` |
| Datagen intraday futures | ~8 giorni di 1m/5m/15m (blocco BL-052) | BACKLOG BL-094 nota dati |
| Gate | G5/G6 REJECTED; live DISABLED fino a G7 | `docs/ORACLE_AUTOPILOT_STATUS.md:37-38,84` |
| Alpha101 | catalogo 101 fattori implementato | `analytics/strategy/catalog/alpha101.py` |
| Regime | detector multi-regime + adaptive ensemble (WIP) | `analytics/regime/` · `docs/G6-PAPER-ANALYSIS.md` |

## 2. Le 3 lane e il loro EV onesto

| Lane | Cos'è | EV realistico | Dati oggi | Testabile ora |
|---|---|---|---|---|
| **A. Core PAC dinamico** | Buy&hold multi-asset, tilt regime/momentum/vol-target, ribilanciamento | **Più alto** — beta gestito + diversificazione; non pretende alpha | ✅ daily SPY/QQQ/TLT/GLD/XLE + FX | ✅ **sì** |
| **B. Direzionale turnaround** | Tesi formalizzata su paniere (depressione multipli + catalizzatore), sizing satellite, invalidation | Neutro→positivo *se* il processo sopravvive; negativo se scommessa singola | ⚠️ solo AAPL/MSFT come azioni | ⚠️ richiede universo azionario |
| **C. Scalping/intraday** | Lane aggressiva, edge da microstruttura | **Più basso** — affollata, costi alti, dati mancanti, edge già falsificato (8/8 REJECTED, 0 trade G6) | ❌ ~8 giorni intraday futures | ❌ no |

**Regola**: la priorità di investimento è inversa all'entusiasmo — prima A
(noiosa, profittevole), poi B (tua intuizione formalizzata), infine C (solo
quando dati + edge passano il gate). Ignorare quest'ordine è il pattern che
distrugge il retail.

## 3. Architettura di portafoglio

```
┌─ CORE (60-70% capitale) ── Lane A: PAC multi-asset con pesi dinamici ─┐
│  regime → tilt espositivo; momentum → rotazione; vol-target → size    │
│  ribilanciamento periodico + PAC periodico (media del costo)          │
├─ SATELLITE (20-30%) ── Lane B: direzionale turnaround su paniere ─────┤
│  screening depressione + catalizzatore; ≤2-3% per idea; invalidation  │
├─ SPECULATIVO (5-10%) ── Lane C oggi / opportunità a coda ─────────────┤
│  sizing piccolo; perderlo non cambia il conto                         │
└────────────────────────────────────────────────────────────────────────┘
```

L'allocazione è una *linea guida iniziale*, non un dogma: va calibrata sul
profilo di rischio dell'operatore e sui risultati paper delle lane.

## 4. Lane A — Core PAC dinamico (costruibile OGGI)

**Design**: posizione lunga multi-asset (azioni/ETF, obbligazioni TLT, oro GLD,
commodity XLE, FX hedge) con:

1. **Regime classifier** → tilt espositivo (risk-on/off). Già esistente:
   `analytics/regime/` + lezione M32a (choppy-bias → AdaptiveEnsemble).
2. **Momentum cross-asset** → rotazione pesi tra asset con momentum relativo.
   Testabile con i daily del lake.
3. **Vol-targeting** → size inversamente proporzionale alla volatilità
   realizzata; il lever della lane secondo S0.2 (p(pass) sale da 30% a 53% a
   σ bassa).
4. **Ribilanciamento** periodico (mensile) + PAC periodico.

**Ingredienti esistenti**: regime detector, alpha101, walk-forward engine,
`analytics/backtest/engines/vectorized.py` (vectorbt) e `nautilus.py` già
cablati. **Sizing**: cvxpy è installato ma morto (gap #2 del
live-readiness-assessment) — lane A è il punto dove cablarlo (Markowitz o
Kelly con vincoli).

**Criterio di avanzamento**: A parte in RESEARCH (walk-forward sui daily
esistenti); passa a PAPER quando il walk-forward onesto (S_test > buy&hold,
cost model aggressivo) è verde su ≥2/3 asset core. A è profittevole *anche
senza alpha*: il suo scopo è catturare beta con meno drawdown del buy&hold
naive (vol-targeting + diversificazione).

## 5. Lane B — Direzionale turnaround (il tuo "INTC" formalizzato)

**Da scommessa a processo.** La tua intuizione su INTC era una tesi di
turnaround: azienda in depressione di multipli/sentiment, un catalizzatore, un
orizzonte ~1 anno. Formalizzata:

1. **Universo**: aggiungere azioni singole al lake (BL-099 equities intraday
   via IBKR, o daily via yahoo/polygon — vedi §9).
2. **Screening**: seleziona titoli con drawdown da massimi ≥ X% da Y mesi,
   multipli compressi, e un catalizzatore identificabile (utili, buyback,
   cambio management, settoriale).
3. **Paniere, non singolo nome**: la tesi si testa su 20-30 titoli
   contemporanei; l'edge, se esiste, è statistico sulla media, mai garantito
   su un nome.
4. **Sizing**: ≤2-3% del capitale per idea; perdere l'idea non scalfisce il
   conto.
5. **Invalidation predefinita**: quando la tesi fallisce (target o stop o
   tempo), si esce — nessuna "speranza".
6. **Gate onesto**: backtest del processo su dati storici (screening
   retroattivo con PIT — attenzione: **FRED lookahead**, gap #1 del
   live-readiness-assessment, vale anche per i fondamentali: usare solo dati
   disponibili all'epoca).

**Relazione col repo**: è una lane nuova. Va costruita come modulo in
`analytics/` con lo stesso rigore (walk-forward, trial ledger S0.3, no-HARKing).

## 6. Lane C — Scalping/intraday (subordinata, non oggi)

**Verdetto onesto**: non è una priorità. Motivi verificati:
- Dati: il lake ha ~8 giorni di futures intraday (BL-052). Servono backfill
  IBKR (BL-097) e Databento (BL-098) — entrambi **bloccati su setup manuale
  operatore** (login gateway, API key).
- Edge: gli 8 candidati segnale del gate sono 8/8 REJECTED; G6 paper ha
  prodotto 0 trade. Non c'è edge intraday verificato.
- Costi/latenza: è la lane più sensibile a slippage e fill — esattamente il
  gap #3 (fill-on-touch senza queue position) del live-readiness-assessment.

**Quindi**: C entra nel piano solo come *speculativo* (5-10%, sizing piccolo)
finché (i) i dati intraday profondi non esistono, e (ii) un backtest onesto
con pessimistic-fill non passa il gate. La road per C è: dati → pessimistic
fill → walk-forward → gate → solo allora sizing normale.

## 7. Sizing e risk (tutte le lane)

- **Risk kernel deterministico**: già presente e PASSED (G4,
  `policy/prop_firm/governor.py`). Resta il confine di autorità per ogni lane.
- **cvxpy da cablare**: installato, 0 import (gap #2). Per A: ottimizzazione
  pesi; per B: Kelly per-idea con vincoli di concentrazione.
- **Fill realistico**: aggiungere pessimistic-fill al paper broker (gap #3)
  PRIMA di qualunque verdetto G6 — nessuna lane passa a PAPER con fill-on-touch.
- **Lookahead**: FRED e fondamentali senza vintage (gap #1) escludono i dati
  macro-conditional dai walk-forward finché non c'è PIT.

## 8. Gate di promozione per lane (paper → live)

La progressione `core/domain/mode.py:82-87` è unica e irregressibile; le lane
ci passano sopra con evidenza per-lane:

| Lane | RESEARCH → PAPER | PAPER → SHADOW | → EVALUATION/FUNDED |
|---|---|---|---|
| **A Core PAC** | walk-forward onesto su daily (S_test > BH, cost model aggressivo, ≥2/3 asset) | 30+ sessioni paper con trade, reconcile 100%, DD≤limite | solo dopo G6/G7 del programma |
| **B Turnaround** | screening retroattivo PIT su paniere, tesi pre-registrata (trial ledger S0.3) | 20+ idee paper con invalidation rispettata | solo dopo G6/G7 |
| **C Scalping** | dati intraday + pessimistic-fill + walk-forward verde | 30+ sessioni paper intraday, 0 trade = FAIL | solo dopo G6/G7 |

Nessuna lane salta il gate: il live è DISABLED finché G7 non è PASSED
(STATUS.md:84), qualunque sia la lane.

## 9. Dati necessari per lane (mappa)

| Lane | Serve | Stato | Azione |
|---|---|---|---|
| A | daily multi-asset | ✅ presente (SPY/QQQ/TLT/GLD/XLE/FX) | nessuna |
| B | universo azioni singole + fondamentali PIT | ❌ solo AAPL/MSFT | BL-099 equities / daily yahoo/polygon; attenzione vintage fondamentali |
| C | intraday 1m/5m/15m profondi | ❌ ~8 giorni | BL-097 IBKR + BL-098 Databento (blocco: setup operatore) |

## 10. Sequenza di esecuzione

1. **Lane A prima** (settimane, no blocker): walk-forward su daily esistenti,
   cablare cvxpy per pesi, regime/momentum/vol-target. Deliverable: report
   paper/backtest di A con verdict onesto.
2. **Pessimistic-fill + lookahead fix** (1-2 giorni, parallelo): i due gap del
   live-readiness-assessment che invalidano qualunque verdetto.
3. **Lane B** (dopo universo azionario): screening turnaround come processo,
   test PIT, pre-registrazione tesi.
4. **Lane C solo dopo**: dati intraday → pessimistic fill → walk-forward →
   gate.
5. **Committare la S0** già completata (working tree verde: BL-094/096/104 +
   report s0-2 e live-readiness) come prerequisito di igiene.

## 11. Criteri di stop / meta-kill

- **A**: se dopo walk-forward onesto A non batte il buy&hold naive *su DD
  risk-adjusted* (es. Sharpe>BH o DD<BH), A si riduce a passivo puro (nessun
  tilt) — il beta resta, il "management" si ferma.
- **B**: se lo screening retroattivo PIT su paniere non mostra edge statistico
  (luck p, multiplicity), B si chiude e resta solo l'allocazione speculativa
  (5-10%) a discrezione.
- **C**: meta-kill già scritto: se il gate fallisce dopo dati + pessimistic
  fill, la lane C è chiusa permanentemente (piano S1.6 "meta-kill rule scritta
  PRIMA del run", `docs/plan-production-grade.md:102`).
- **Globale**: qualunque dubbio su dati/regole/ledger/risk mantiene il sistema
  in RESEARCH/PAPER (ROADMAP stop condition).

## 12. Cosa NON fare

- Non mettere capitale su C oggi: edge non verificato + dati mancanti.
- Non trasformare B in "scommessa singola INTC-style": è un processo su
  paniere o non è.
- Non pretendere alpha da A: A è beta gestito; se A "batte il mercato" è
  tilt/regime, e va misurato come tale (alpha vs beta, lezione BL-023).
- Non saltare i gate: la progressione mode è irregressibile e il live è
  disabilitato fino a G7.
- Non iniziare C prima di dati + pessimistic-fill: sarebbe ri-fare lo stesso
  errore di G6 (0 trade, verdict senza significato).

## 13. ADR proposto (draft — NON accettato)

**Titolo**: Sistema profittevole = core beta gestito + satellite con gate;
scalping subordinato a dati e edge.

- **Contesto**: il repo ha alpha ≈ 0 misurato; l'operatore vuole un sistema
  profittevole includendo la propria esperienza direzionale (INTC turnaround).
- **Decisione**:
  1. Costruire prima la lane A (core PAC dinamico) con walk-forward onesto su
     daily esistenti.
  2. Formalizzare la lane B come processo su paniere con gate e invalidation,
     mai come scommessa singola.
  3. Posticipare la lane C (scalping) finché dati intraday profondi +
     pessimistic-fill + gate verde.
  4. Cablare i 3 gap del live-readiness-assessment (FRED lookahead, cvxpy,
     pessimistic-fill) PRIMA di qualunque verdetto di lane.
  5. Nessuna lane salta la progressione mode; live solo dopo G7.
- **Conseguenze positive**: il profitto probabile (beta gestito) arriva prima
  e senza alpha; l'entusiasmo (B/C) è incanalato in processi con gate invece
  che in scommesse.
- **Conseguenze negative**: il sistema non "vanta" rendimenti da scalping;
  B richiede universo dati nuovo; la gratificazione è dilazionata.
- **Enforcement**: BACKLOG riceve le lane come blocchi S7 (A), S8 (B), S9 (C)
  con i gate sopra; nessun commit che abilita ordini live senza questo ADR
  accettato.

## 14. Limiti di questo piano

- Gli EV sono ordini di grandezza, non stime: vanno aggiornati con i report
  paper reali (S0.4 resta la tabella canonica).
- Il lake ha dati daily solo da ~2000/2003 per i core: l'universo B e il
  lookback di A sono vincolati a questo.
- L'allocazione 60/70-20/30-5/10 è un default da calibrare sul profilo
  dell'operatore, non una prescrizione.
- Nessuna stima di rendimento assoluto è inclusa di proposito: ogni numero
  andrebbe prima verificato in paper.

## Fonti

- `BACKLOG.md` — stato gate/task (BL-094 meta-kill, BL-097/098 dati, BL-099 equities)
- `docs/plan-production-grade.md` — piano S0-S6 (meta-kill S1.6, trial ledger S0.3, EV S0.4)
- `docs/reports/s0-1-bl023-autopsy.md` — lezione alpha vs beta
- `docs/reports/s0-2-economic-model.md` — modello economico, leva σ
- `docs/reports/multiasset/walkforward.md` — 0/9 anti-beta
- `docs/reports/live-readiness-gap-analysis.md` — 3 gap (FRED, cvxpy, fill)
- `docs/ORACLE_AUTOPILOT_STATUS.md` — gate matrix
- `core/domain/mode.py:82-87` — progressione irregressibile
- `analytics/strategy/catalog/alpha101.py` — catalogo fattori esistente
- `data/lake/metadata/coverage.json` — 101 simboli, universo azionario assente
