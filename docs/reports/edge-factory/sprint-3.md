# Sprint 3 — BL-742 portfolio SR-max v2 (NO-GO complessivo onesto)

**Generated**: 2026-09-05
**Task**: BL-742 (Sprint Renaissance-parity 2026-09-04, Task 5)
**Piano**: `docs/plans/2026-09-04-renaissance-parity-sprint.md` §Task 5
**Brief**: `.superpowers/sdd/2026-09-04-renaissance-parity-sprint/task-5-brief.md`

---

## Verdetto di sintesi

**NO-GO complessivo onesto — 0/3 famiglie qualificate.**

Nessuna gamba ortogonale nuova è stata aggiunta a `LEGS` in
`scripts/run_portfolio_sr_max.py`. Il portafoglio SR-max resta congelato alla
versione v1 (baseline BL-736) — nessun ricalcolo, nessuna promozione.

Questa scelta è vincolata dal prereg del piano: *se NESSUNA delle 3 famiglie
supera i gates → report onesto `sprint-3.md` con verdetto NO-GO complessivo e
le famiglie REJECTED nel registry. Non si costruisce nulla attorno a zero
edge.* Il rispetto del prereg è la prova di serietà del processo: nessun
risultato silenzioso, nessuna promozione senza evidenza.

---

## 1. Verdetti letti programmaticamente dai JSON (Task 2/3/4)

Lettura **NON hardcoded**: eseguita da `scripts/read_sprint3_verdicts.py` sui
report JSON prodotti dai runner precedenti. Il task 5 non ricalcola i verdetti
dei task BL-739/740/741 — li legge.

```bash
$ uv run python scripts/read_sprint3_verdicts.py
```

| Famiglia | BL | Campo JSON usato | Valore | Numeri chiave |
|---|---|---|---|---|
| EF-004 overnight-drift-dealer-inventory | BL-739 | `verdict` | **`NO_GO`** | `n_passing_assets=0/5` (XAUUSD, XAGUSD, EURUSD, GBPUSD, USDJPY) |
| EF-004 fx-carry-policy-rate-differential | BL-740 | `verdict` | **`NO_GO`** | `n_passing_pairs=0/7` (tutte le coppie FRED missing, chiave vuota) |
| EF-004 cross-pillar-conditioning-overlay | BL-741 | `overall` | **`REJECTED`** | `n_pillars_negative=2/3` (vix_z=NEUTRAL, funding_z=NEUTRAL) — pista conditioning-lite CHIUSA |

Output integrale dello script (riferimento per futuri task 5):

```
Famiglia                            BL       Verdict field          Valore
------------------------------------------------------------------------------------------
EF-004 overnight-drift              BL-739   verdict                NO_GO  (passing=0/5 asset)
EF-004 fx-carry-policy-rate         BL-740   verdict                NO_GO  (passing=0/7 coppie, FRED missing=8)
EF-004 cross-pillar-conditioning    BL-741   overall                REJECTED  (negative=2/3 pilastri)
------------------------------------------------------------------------------------------
Famiglie GO/qualificate: 0/3
→ nessuna gamba da aggiungere a LEGS in run_portfolio_sr_max.py
→ report sprint-3.md = NO-GO complessivo onesto
```

### 1.1 Attenzione sulla lettura del JSON conditioning (BL-741)

`pillar-conditioning-sprint.json` contiene sia `verdicts` per-pillar sia il
campo top-level `overall`. Il per-pillar `vix_z+funding_z` risulta `HELPFUL`
ma è un artefatto del fix di review: il test combinato è stato eseguito solo
su ETHUSDT (1/1 gambe) e resta informativo. Il verdetto **OVERALL** è
`REJECTED` perché il kill-switch della famiglia è sul pilastro **primario**
VIX-z = `NEUTRAL` e, coerentemente col prereg di Task 4, la pista
conditioning-lite è **CHIUSA** senza retry su altri pilastri
(`morta_per_evidenza` nel registry). BL-742 legge il verdetto overall di
famiglia, NON il per-pillar.

---

## 2. Dettaglio per famiglia

### 2.1 BL-739 — Overnight drift (EF-004@10-seasonal)

**Report dettagliato**: [`overnight-drift-sprint.md`](overnight-drift-sprint.md) /
[`overnight-drift-sprint.json`](overnight-drift-sprint.json)

**Stato registry**: `REJECTED`
(transizione `in_qualifica → REJECTED: BL-739 walk-forward > 2022-12-31: 0/5 asset passanti`,
data 2026-09-05T10:34:16.527238+00:00, ref `overnight-drift-sprint.md`).

**Numeri chiave** (campione aggregato dal JSON):

| Asset | Leg | Sharpe | Haircut Sharpe | DSR | MaxDD | Annual ret | Verdetto |
|---|---|---|---|---|---|---|---|
| XAUUSD | overnight_hold_close_to_open | +1.407 | -0.552 | 0.986 | 7.5% | +12.0% | OK ma haircut negativo |
| XAUUSD | window_0203_hold | -3.001 | -4.890 | 0.000 | 13.4% | -5.7% | KO |
| XAGUSD | overnight_hold_close_to_open | +0.106 | -1.878 | 0.565 | 9.9% | +0.5% | OK ma haircut negativo |
| XAGUSD | window_0203_hold | -0.962 | -2.931 | 0.065 | 5.9% | -1.8% | KO |
| EURUSD | overnight_hold_close_to_open | -1.860 | -3.770 | 0.001 | 34.7% | -14.4% | KO |
| GBPUSD | overnight_hold_close_to_open | -2.250 | -4.155 | 0.000 | 39.6% | -17.0% | KO |
| USDJPY | overnight_hold_close_to_open | -1.704 | -3.571 | 0.002 | 34.5% | -14.6% | KO |

Verdetto famiglia: **0/5 asset passanti** (kill-switch: ≥2 asset-pass con
haircut Sharpe > 0 E DSR > 0.5 sul test window). Tutti i risultati su XAU/XAG
hanno haircut negativo: SR lordo positivo solo grazie alla position-sizing
vol-target, NON alpha edge (overfitting/regime shift evidente post-2022).

### 2.2 BL-740 — FX carry policy-rate (EF-004@02-macro)

**Report dettagliato**: [`fx-carry-policy-rate.md`](fx-carry-policy-rate.md) /
[`fx-carry-policy-rate.json`](fx-carry-policy-rate.json)

**Stato registry**: `REJECTED`
(transizione `in_qualifica → REJECTED: BL-740 walk-forward > 2022-12-31: 0/7 coppie passanti`,
data 2026-09-05T11:10:01.753071+00:00, ref `fx-carry-policy-rate.md`).

**Numeri chiave** (campione aggregato dal JSON): **0/7 coppie passanti**. Tutte
le 7 coppie G10 sono `EXCLUDED_NO_RATES` perché `ORACLE_DATA_FRED_KEY` non è
valorizzata nell'ambiente di questo run (`data.fred_unavailable` = 8/8
valute, `rates_shape = [0, 0]`). Il verdetto **NO_GO è per mancanza dati**,
NON per squalifica dell'edge (vedi §4 nota umana).

### 2.3 BL-741 — Cross-pillar conditioning (EF-004@13-meta-synthesis)

**Report dettagliato**: [`pillar-conditioning-sprint.md`](pillar-conditioning-sprint.md) /
[`pillar-conditioning-sprint.json`](pillar-conditioning-sprint.json)

**Stato registry**: `REJECTED`
(transizione `in_qualifica → REJECTED: BL-741 walk-forward > 2022-12-31: 3/3 pilastri NEGATIVI → pista conditioning-lite CHIUSA (morta_per_evidenza)`,
data 2026-09-05T16:08:42.978122+00:00, ref `pillar-conditioning-sprint.md`).

**Numeri chiave** (campione aggregato dal JSON):

| Pillar | Leg | Variant | SR baseline → conditioned | ΔSR | Verdetto |
|---|---|---|---|---|---|
| vix_z | ES_1d ema(20/50) | baseline → conditioned | 0.600 → 0.544 | -0.055 | NEUTRAL |
| vix_z | ES_1d donchian(20) | baseline → conditioned | -0.252 → -0.175 | +0.077 | NEUTRAL |
| vix_z | ETHUSDT_1h ema(20/50) | baseline → conditioned | 0.467 → 0.610 | +0.143 | NEUTRAL |
| funding_z | ETHUSDT_1h ema(20/50) | baseline → conditioned | 0.467 → 0.416 | -0.052 | NEUTRAL |
| vix_z+funding_z | ETHUSDT_1h ema(20/50) | baseline → conditioned | 0.467 → 0.633 | +0.166 | HELPFUL* |

\* per-pillar — informativo (ETH-only, 1/1 gambe). Vedi §1.1 per la
distinzione pillar vs overall.

Verdetto famiglia: **REJECTED** (kill-switch sul pilastro primario vix_z =
NEUTRAL; nessuna gamba soddisfa ΔSR ≥ +0.10 senza turnover > 2× baseline in
modo consistente sui pilastri). Conferma il precedente NEGATIVO di Sprint 2d
funding-z e chiude la pista conditioning-lite senza retry, come da prereg.

---

## 3. Contesto portfolio SR-max v1 (baseline, non toccata)

Il portafoglio SR-max consolidato in BL-736 resta la baseline su cui
sarebbe dovuto atterrare il delta di BL-742. Riepilogo (estratto da
[`portfolio-sr-max.json`](portfolio-sr-max.json), 16 gambe, vol-target 10%,
walk-forward > 2022-12-31):

| Leva | Annual ret | Annual vol | **Sharpe** | MaxDD | P(m≥5%) |
|---|---|---|---|---|---|
| 1.0× | +4.06% | 2.87% | **1.400** | 2.59% | 0.0% |
| 1.5× | +6.11% | 4.30% | **1.400** | 3.90% | 0.0% |
| 2.0× | +8.18% | 5.73% | **1.400** | 5.19% | 0.0% |
| 3.0× | +12.38% | 8.60% | **1.400** | 7.77% | 8.9% |
| 4.0× | +16.64% | 11.47% | **1.400** | 10.33% | 13.3% |

`SR(N) = 1.40` è la saturazione documentata in BL-737 (SR(N) satura a 1.2-1.5
con la famiglia tecnica corrente). BL-742 nasceva per testare se 3 nuove
famiglie ortogonali (overnight, carry, conditioning) potessero rompere la
saturazione. **Test fallito per 3/3 famiglie**: nessuna integrazione, nessuna
riqualifica portafoglio, baseline intatta.

---

## 4. Nota umana sul carry (BL-740) — NO_GO "per mancanza dati", non squalifica

Il verdetto NO_GO di BL-740 è tecnicamente corretto ma non è una
squalifica dell'edge carry:

- il basket G10 carry (Lustig-Roussanov-Verdelhan 2011 RFS; Menkhoff et al
  2012 JF) ha Sharpe ~0.5 documentato in letteratura;
- il runner ha calcolato tutto correttamente: segnale mensile ±1 = segno
  (tasso_A − tasso_B) con `CARRY_LAG_MONTHS=2` anti-lookahead, basket
  dollar-neutral vol-target 10%, costi 1.5 bps/turnover, walk-forward >
  2022-12-31, tail-check separato su 2020-03 + 2022-USD-rally (finestre
  documentate vuote, ma il meccanismo di tail-check è implementato);
- la causa del fallimento è puramente operativa: `ORACLE_DATA_FRED_KEY`
  non valorizzata (`data.fred_unavailable` = 8/8 valute, vedi
  `fx-carry-policy-rate.json:38`). Senza dati policy rates non c'è segnale,
  per definizione.

**Fork di follow-up (non pianificato in questo sprint)**: quando la chiave
FRED sarà disponibile, rilanciare il runner con un nuovo ID ipotesi
`EF-005@02-macro` (il EF-004 resta REJECTED con la nota "per mancanza dati"
nel registry — la transizione è append-only, ADR). Costo: ~15 minuti (il
runner è già pronto, manca solo il dato). Rischio: anche con dati validi,
la letteratura documenta Sharpe 0.5 sul basket HML originale — per
saturare SR(N) sopra 1.40 servirebbero ~3 gambe carry ortogonali qualificate,
non 1. Decisione fuori scope per Task 5.

---

## 5. Perché zero integrazioni è la risposta giusta (coerenza col prereg)

Tre famiglie testate, tre verdetti negativi. L'istinto sarebbe di "forzare"
almeno una gamba (es. includere il solo XAUUSD overnight_hold perché ha SR
+1.407 / DSR 0.986 / MaxDD 7.5%) per non consegnare un report "vuoto". Ma:

- **Il kill-switch della famiglia è su `haircut_sharpe`**: XAUUSD overnight
  ha haircut -0.552 → SR positivo SOLO grazie alla position-sizing
  vol-target, NON alpha edge. Includerlo viola il gate preregistrato
  `HAIRCUT_SHARPE_GATE = 0.0`;
- **Risultato silenzioso = vietato** (global constraint §"Nessun risultato
  silenzioso" del piano). Se integriamo, dobbiamo dirlo; se non
  integriamo, dobbiamo dire perché. Questo report sceglie la seconda;
- **Promozione senza evidenza = ADR-018/023 violatione**. Nessuna eval si
  paga senza sim canonica pass, e questo sprint NON qualifica nuova
  promozione.

La scelta di zero integrazioni **NON è un fallimento dello sprint**: è il
risultato onesto del processo pre-registrato. Lo sprint ha risposto a una
domanda precisa (le 3 famiglie ortogonali alzano SR(N) sopra 1.40?) e la
risposta è no. Sapere che la risposta è no è informazione utile — il
prossimo sprint può allocare lo stesso budget di ricerca altrove (es.
famiglie macro factor-based, positioning CFTC, o ritorno al carry quando i
dati sono disponibili).

---

## 6. Note per il futuro (Step 4-5 del brief — restano rilevanti)

Quando la prossima famiglia ortogonale si qualificherà (futuro sprint non
ancora pianificato), il task di integrazione portafoglio dovrà includere:

### 6.1 Cap leva 4× — scelta LOCALE di questo sprint, NON soglia ADR-023

Il cap 4× dichiarato in BL-742 è una **scelta conservativa locale**, non
una soglia ADR-023 (ADR-023 regola consistency ≤0.35 e risk-per-trade, non
la leva). Razionale locale:

- restare sotto DLL 5% / trailing 4% dell'envelope funded documentato nel
  dossier C;
- coerente con BL-737 che documentava leva ~10× necessaria per 5%/mese a
  vol 30% — ma ~10× è FUORI envelope funded, è il canale personal.

Quando BL-742 (o un suo successore) integrerà una famiglia qualificata, il
cap 4× e la nota "scelta locale, non ADR" vanno mantenuti nel report.

### 6.2 Dipendenza Channel B (ADR-023) per la promozione funded

SR(N) > 1.40 da solo **NON autorizza eval**. La promozione a portafoglio
funded passa da `check_dual_channel` ADR-023:

- **Channel A**: sim canonica pass (BL-737 o successore);
- **Channel B**: 100+ sessioni paper IBKR, pass-rate ≥ 0.60, MC ≥ 0.60,
  consistency ≤ 0.35.

Questa nota va riportata nel report v2 quando una famiglia si qualificherà,
anche se SR(N) > 1.40 dovesse essere raggiunto — la promozione funded è
condizionata a entrambi i canali.

---

## 7. Cosa NON è stato fatto (per trasparenza)

| Cosa | Stato | Motivo |
|---|---|---|
| Modifica a `scripts/run_portfolio_sr_max.py` | NON fatta | 0 famiglie GO, prereg piano: "Non si costruisce nulla attorno a zero edge" |
| Esecuzione `run_portfolio_sr_max.py` per v2 | NON fatta | Senza gambe nuove da integrare, l'output sarebbe identico alla v1 |
| Generazione `portfolio-sr-max-v2.{md,json}` | NON fatta | Idem |
| Transizione stati registry oltre EF-004 REJECTED | NON fatta | Le 3 EF-004 sono già REJECTED nei rispettivi domini (Task 2/3/4) |
| Fork EF-005@02-macro carry | NON pianificato | Out of scope Task 5; da aprire quando `ORACLE_DATA_FRED_KEY` arriva |

---

## 8. Link ai report dettagliati

- BL-739 overnight drift: [`overnight-drift-sprint.md`](overnight-drift-sprint.md) · [`.json`](overnight-drift-sprint.json)
- BL-740 FX carry: [`fx-carry-policy-rate.md`](fx-carry-policy-rate.md) · [`.json`](fx-carry-policy-rate.json)
- BL-741 cross-pillar conditioning: [`pillar-conditioning-sprint.md`](pillar-conditioning-sprint.md) · [`.json`](pillar-conditioning-sprint.json)
- Baseline portfolio v1: [`portfolio-sr-max.md`](portfolio-sr-max.md) · [`.json`](portfolio-sr-max.json)
- Script lettura verdetti: [`scripts/read_sprint3_verdicts.py`](../../scripts/read_sprint3_verdicts.py)
- Piano sprint: [`docs/plans/2026-09-04-renaissance-parity-sprint.md`](../../plans/2026-09-04-renaissance-parity-sprint.md)
- Brief Task 5: [`.superpowers/sdd/2026-09-04-renaissance-parity-sprint/task-5-brief.md`](../../../.superpowers/sdd/2026-09-04-renaissance-parity-sprint/task-5-brief.md)
