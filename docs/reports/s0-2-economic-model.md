# S0.2 — Modello economico prop-firm (BL-094)

> STATUS: report BL-094, 2026-08-05. Evidenza MC riproducibile: `docs/reports/s0-2/eval_economics.json`
> (generato da `scripts/run_eval_economics.py`, seed 42, N=10.000/parametro).
> Input vincolante: autopsia S0.1 — alpha residuo misurato **+2.3%..+6.1% lordo/anno**,
> netto costi → verso lo zero.

## 0. Tesi quantificata (risposta in una riga)

**€3K/mese netti richiede alpha ≥ ~30-120%/anno su un singolo account (o 5-20 account
concorrenti a alpha 6%): 5-16× il soffitto misurato. L'obiettivo è incompatibile con
l'edge attuale — la lane daily è economicamente morta, indipendentemente dai segnali
provati. Il "capitale mancante" non è denaro: è l'edge.**

## 1. Parametri del canale (stato 2026-08, da riconfermare in S0.5 con snapshot hash)

| Parametro (50K) | MyFundedFutures | Topstep TC |
|---|---|---|
| Profit target | $3.000 (6%) — Core/Pro/Builder | $3.000 (6%) |
| Max loss | $2.000 EOD trailing (4%) | $2.000 trailing EOD, lock su initial |
| Daily loss | **assente** sui piani correnti | $1.000 (optional) |
| Fee eval | Core $77/mese · Pro $227/mese · Builder **$153 one-time** | $49/mese + $149 activation (o ~$95/mese senza) |
| Activation | $0 (eliminata lug-2025) | $149 (una tantum) |
| Split | 80/20 (Core/Pro/Flex/Builder) · 90/10 (Rapid) | **90/10 flat** (post 12-gen-2026) |
| Consistency | 50% in eval (Core/Pro); niente da funded (Pro/Rapid) | XFA: 5 giorni vincenti $150+ · path consistency ≤40% |
| Payout | Core: ogni 5 giorni vincenti, min $250, **cap $1.000**; Pro: 14gg, buffer $2.100, min $1.000 | cap $2.000/richiesta (Standard), $3.000 (Consistency path) |
| Fee payout | $15 flat (Rise) | $30 ACH/wire |
| Automation | consentita (no HFT/fill exploitation) | TopstepX API sì, **no VPS/VPN** (ADR-015) |

Nota: entrambe le firm sono migrate al target **6%/4%** (2025-26). **I fixture del repo
sono stale**: `scripts/simulate_mff_challenge.py` (target $5.000=10%, daily loss 5%) e
`data/prop_firm/topstep_tc_50k.json` (target $5.000) → da aggiornare in S0.5 (BL-095).

## 2. Il vincolo di fondo: la varianza, non l'alpha

Monte Carlo del percorso eval (returns daily iid, target +6%, trailing DD 4% EOD,
barriera ratchet). **p(pass) per alpha (righe) × volatilità daily (colonne):**

| alpha/anno | σ=0.4% | σ=0.8% | σ=1.2% | σ=1.6% |
|---|---|---|---|---|
| **0%** (random walk) | 25.5% | 27.8% | **30.1%** | 32.8% |
| 2% | 34.0% | 30.1% | 31.3% | 33.3% |
| 4% | 43.3% | 32.6% | 32.5% | 33.9% |
| **6%** (soffitto lordo misurato) | 53.4% | 35.0% | **33.7%** | 34.6% |
| 12% (mai misurato) | 77.3% | 42.8% | 37.3% | 36.8% |

Lettura:

- **Base case (σ=1.2%, ES 1d)**: un random-walk disciplinato senza alcun edge passa
  l'eval il 30.1% delle volte. L'alpha misurato (+6%) la porta a 33.7%: **+3.6 punti**.
  Anche un alpha doppio del soffitto (12%) vale +7 punti. La differenza tra "niente
  edge" e "edge misurato" è un soffio — coerente con i verdetti BL-023 (0/9, 8/8 REJECTED).
- **La leva vera è il rischio per-trade (σ), non l'alpha**: a parità di alpha 6%,
  σ 0.4% → 53.4% (vs 33.7%); con α=12% e σ 0.4% → 77.3%. È la conferma formale del
  "daily-fail lever" storico — ma σ↓ senza turnover = flat (lezione G6-WP2: 0 trade in
  30/30 sessioni).
- **Tempo**: i passaggi sono eventi di varianza, non di drift — mediana 10-30 giorni a
  σ≥0.8% (i sims che passano lo fanno con streak fortunate). Ma servono E≈3 tentativi
  (p≈33%): **funded in ~2-6 mesi di calendario** se si rilanciano gli eval in serie.
- Le barriere EOD "trailing" sono ratchet (seguono i massimi): mantengono p sotto la
  parity a barriere fisse (B/(A+B)=40%) — il trailing DD non perdona.

### 2bis — Verifica empirica su dati reali (replay, `scripts/run_eval_simulation.py`)

La p(pass) del gate §2 è sintetica (gaussiana). Qui è **misurata** replayando i
segnali reali sul lake con le regole eval (6%/4% trailing EOD, consistency 50%,
costi $8.4/RT, sizing 1 contratto ES su $50K — convenzioni pre-registrate nel
JSON): ogni attempt parte flat a un inizio walk-forward (step 63 barre) e corre
finché pass/breach/daily-loss/timeout.

**ES 1d — 6.524 barre (2000-2026), N=99 attempt:**

| Segnale | p(pass) | CI 95% | Mediana giorni a pass | Consistency bloccata (su pass) |
|---|---|---|---|---|
| donchian_breakout | 26.3% | [18.6%, 35.7%] | 17.5 | 10/26 |
| trend_filtered_breakout | 30.3% | [22.1%, 40.0%] | 22.5 | 8/30 |
| ema_trend | 26.3% | [18.6%, 35.7%] | 13.5 | 6/26 |
| **buy_hold** (baseline) | 23.2% | [16.0%, 32.5%] | 9.0 | 9/23 |
| Riferimento gaussiano α=0 (MC §2) | 30.1% | — | 15 | — |
| **Requisito pre-registrato S1.1** | **≥ 60%** | — | — | — |

**ES 1h — 13.770 barre (2024-03 → 2026-08), N=214 attempt:**

| Segnale | p(pass) | CI 95% | Mediana barre a pass |
|---|---|---|---|
| donchian_breakout | 23.4% | [18.2%, 29.5%] | 40 |
| trend_filtered_breakout | 25.7% | [20.3%, 31.9%] | 55 |
| ema_trend | 29.9% | [24.2%, 36.4%] | 47 |
| buy_hold | 28.0% | [22.4%, 34.4%] | 24 |

Lettura empirica:

- **Nessun candidato trend supera il caso**: 26-30% su 1d contro il 30.1% del
  random-walk senza edge e il 23.2% del buy&hold — differenze dentro il CI.
  L'alpha residuo misurato dall'autopsia (+2-6% lordo) **non si traduce in
  p(pass) sopra il base rate nel canale reale**: l'eval è un test di varianza,
  e il vantaggio di drift è sotto il rumore.
- **Buy&hold a 23.2% su 26 anni**: le code reali (2000-02, 2008, 2022) fanno
  breach rapido — sotto la gaussiana a drift zero (30.1%).
- **La cadenza 1h non aiuta**: p invariata (23-30%), solo i giorni scendono
  (mediana ~2 giorni di trading a passare). Il trailing DD domina; il tempo no.
- **La consistency rule morde davvero**: ~1/3 dei passaggi bloccati al primo
  touch del target (diluizione richiesta, pass più lunghi).
- **Massimo CI superiore di qualunque candidato: 40%** — 1.5× sotto il
  requisito 0.60 pre-registrato. Su dati reali, la family trend è falsificata
  anche nel canale prop-firm.

## 3. Requisiti per €3K/mese netti

Catena: €36K/anno netto-pocket → pre-tax 26% (IT) → $53.5K/anno ricevuti (FX 1.10) →
lordo strategia con split s. Numero di account funded concorrenti per alpha (split 90%):

| Size | Alpha richiesto per **1** account | Account @ α=2% | @ 4% | @ 6% |
|---|---|---|---|---|
| 50K | 118.9%/anno | 59.5 | 29.7 | 19.8 |
| 100K | 59.5% | 29.7 | 14.9 | 9.9 |
| 150K | 39.6% | 19.8 | 9.9 | 6.6 |
| 200K | 29.7% | 14.9 | 7.4 | 5.0 |

(split 80%: ×1.125 gli account; α richiesti proporzionali. Tabella completa in JSON.)

Lettura:

- **Con l'alpha realistico netto (0-4%)**: 10-30 account concorrenti. Non fattibile
  né operativamente né per fair-play (multi-account = flag risk, e la capacità di
  gestione di un solo operatore).
- **Con il soffitto lordo (6%, ottimistico)**: 5-7 account da 150-200K — ancora
  borderline su compliance e payout caps ($2-3K/richiesta Topstep, $1K MFF Core
  limitano la velocità di prelievo per account).
- **Il singolo account da 150-200K renderebbe €180-370/mese netti a α=6%**: l'obiettivo
  €3K/mese equivale a ~10-16 di quelle rendite. La prop firm è leva sul capitale, non
  moltiplicatore di alpha.

## 4. Costo del percorso (bankroll)

- **Fee**: MFF Builder $153 one-time; Topstep $49/mese + $149 activation. Fee P90 (5-7
  tentativi per ≥90% di vedere un pass a p≈33%): **~$400-1.100**. Il denaro non è il
  collo di bottiglia.
- **Tempo**: ~3 tentativi × 15-90 giorni = **2-6 mesi per funded** (se l'edge esistesse);
  sul percorso attuale (senza edge misurato) non c'è un tempo atteso finito di rientro.
- **Post-funded**: il trailing 4% del funded è lo stesso ratchet — ogni ciclo di payout
  è una corsa tra prelievo e breach; un breach = nuova eval (fee + tempo). La
  consistency rule (50% eval / ≤40% path) estende i cicli: il giorno migliore può
  superare metà del target su percorsi a basso drift (non quantificato qui — S0.5).

## 5. Verdetto e regole pre-registrate per S1

1. **La lane daily è chiusa anche economicamente**: l'EV è negativo per costruzione
   (requisito vs misurato: gap 5-16×). Nessun nuovo segnale daily può riaperla — la
   meta-kill rule (piano S1.6) è scattata per l'orizzonte daily.
2. **Requisiti quantificati per riapertura (S1.1 intraday 5m/15m/30m)**, tutti e tre:
   - p(pass) ≥ **0.60**, ora MISURATO con `run_eval_simulation.py` sul lake (non
     solo MC): la family trend attuale misura 23-30% con CI superiore a 40% —
     falsificata; il requisito va raggiunto con un candidato nuovo;
   - alpha netto ≥ **15%/anno** e E[giorni a passare] ≤ 60 (cadenza payout mensile);
   - DD ≤ 4% con ADR-016 (S_test > BH_S, N onesto, walk-forward multi-asset).
   Sotto una sola di queste tre → stop e pivot alla lane alternativa (S0.4).
   **Dati nuovi richiesti per misurare 5-30m**: il lake ha solo ~8 giorni di
   1m/5m/15m sui futures (BL-052, Polygon) — il requisito non è testabile oggi.
3. **Prerequisito non negoziabile**: post-mortem del classificatore M32a prima di
   toccare il regime filter (piano S1.1 — 29/30 "choppy" = bias documentato).
4. **Obiettivo ridimensionato del canale**: se l'edge intraday si materializzasse,
   il target sostenibile è **€1.000-1.500/mese netti** con 2-3 account 150-200K (90/10)
   — il modello sconsiglia di pianificare >2 account prima della verifica fair-play
   multi-account (BL-100).

## 6. Assumptions dichiarate e checklist S0.5

- **Assumptions**: returns iid gaussiani (no regime/autocorrelazione, no consistency
  rule nel MC); α netto dei costi di trading (autopsia: 0.23-0.79% per finestra —
  l'α lordo +2-6% va considerato come tetto teorico); tasse 26% (capital gains IT,
  da verificare per i payout prop-firm); FX 1.10; fee/split da fonti web 2026-08.
- **Checklist S0.5 (ToS deep-read con snapshot hash, roadmap §9)**: riconfermare
  target/MLL/daily-loss/split/consistency/payout caps per il programma scelto;
  aggiornare i fixture stale (BL-095); decisione canale G7 — Topstep (no VPS, ADR-015,
  split 90/10, caps $2-3K) vs MFF (automation ok, split 80/90, MFFU non regolamentata,
  segnalazioni di ban post-withdrawal); compliance multi-account.

## Fonti

- **Evidenza MC sintetica**: `docs/reports/s0-2/eval_economics.json` + `scripts/run_eval_economics.py`
- **Evidenza empirica (replay)**: `docs/reports/s0-2/eval_simulation.json` (ES 1d),
  `docs/reports/s0-2/eval_simulation_1h.json` (ES 1h) + `scripts/run_eval_simulation.py`
- **Repo**: autopsia `docs/reports/s0-1-bl023-autopsy.md` · `data/prop_firm/topstep_tc_50k.json`
  · `scripts/simulate_mff_challenge.py` · `docs/ADR/ADR-015-topstep-automation-policy.md`
  · `docs/PROP_FIRM_READINESS_ROADMAP.md` §7-9
- **Web 2026-08** (verifica con snapshot in S0.5): [MFF Pro plan](https://help.myfundedfutures.com/en/articles/11802674-pro-plan-sim-funded-and-live-account-highlights),
  [MFF Rapid 50K](https://help.myfundedfutures.com/en/articles/13134709-rapid-plan-50k-a-comprehensive-look),
  [MFF Builder 50K](https://help.myfundedfutures.com/en/articles/14290805-builder-plan-50k-a-comprehensive-guide),
  [MFF pricing guide (TradersPost)](https://blog.traderspost.io/article/my-funded-futures-pricing-evaluation-guide),
  [MFF review — payout-ban complaints](https://theindustryspread.com/myfundedfutures-review-payouts-ban-complaints/),
  [Topstep accounts overview](https://proptradingvibes.com/blog/topstep-accounts-overview),
  [Topstep 2026 pricing/payout caps](https://fundedprogramfinder.com/topstep-updates-pricing-payout-caps/)
