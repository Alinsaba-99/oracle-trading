# BL-741 — Cross-pillar conditioning (EF-004@13-meta-synthesis)

**Generated**: 2026-09-05T16:42:18.446066+00:00

Prereg: ipotesi EF-004 nel registry 13-meta-synthesis.  Gambe baseline FROZEN nel CONCETTO da BL-736 (ES_1d ema(20/50) vol-target 10%, ES_1d donchian(20), ETHUSDT_1h ema(20/50) vol-target 20%) — implementazione signal segue stile Sprint 2d (long/short su ema crossover, donchian breakout long-only sulle ES daily), NON letteralmente identica a BL-736 EmaTrend/DonchianBreakout long-only.  Pilastri: VIX z-score (rolling 252d, sorgente `analytics/strategy/lane_d_vrp_backtest.py:210` via curated `^VIX_1d.parquet`) + funding-z (BL-718).  Forma: `pos *= 1 - clip(|z|, 0, 2)/2` SOLO quando `sign(z) == sign(pos)` (crowding against, identica Sprint 2d).  `full_z = 2` FROZEN — nessuna ricerca di soglia.  Baseline ES qui +0.60/−0.25 vs BL-736 +1.13/+1.08: il ΔSR resta valido (confronto baseline-vs-conditioned stesso signal).

**PRECEDENTE NEGATIVO (Sprint 2d, 2026-09-03)**: stesso meccanismo di veto con funding-z su ETH/BTC 1h trend legs è risultato NEGATIVO (ETHUSDT SR +0.51→+0.46, P(m≥5%) 28.9%→15.8%; BTCUSDT −0.02→−0.52).  Questo Task 4 è un test INDIPENDENTE su pilastro DIVERSO (VIX-z vs funding-z).  Se anche VIX-z risulta NEGATIVO → pista conditioning-lite CHIUSA definitivamente senza retry su altri pilastri.

Walk-forward test > 2022-12-31.

## Risultati per gamba × pilastro

| leg | pillar | variant | SR | ΔSR | ann ret | MaxDD | trades | turnover | CPCV OOS median | surv. CPCV |
|---|---|---|---|---|---|---|---|---|---|---|
| ES_1d_donchian20 | vix_z | baseline | -0.25 | — | -0.9% | 7.8% | 1216 | 967.5 | +0.03 | base=False |
| ES_1d_donchian20 | vix_z | conditioned | -0.17 | +0.08 | -0.6% | 6.8% | 1175 | 941.0 | +0.03 | NO |
| ES_1d_ema2050 | vix_z | baseline | +0.60 | — | +5.8% | 11.6% | 179 | 162.4 | +0.73 | base=True |
| ES_1d_ema2050 | vix_z | conditioned | +0.54 | -0.06 | +4.6% | 11.2% | 383 | 221.8 | +0.73 | YES |
| ETHUSDT_1h_ema2050 | funding_z | baseline | +0.47 | — | +8.3% | 25.9% | 1030 | 724.2 | +0.37 | base=True |
| ETHUSDT_1h_ema2050 | funding_z | conditioned | +0.42 | -0.05 | +5.7% | 27.1% | 1564 | 775.1 | +0.37 | YES |
| ETHUSDT_1h_ema2050 | vix_z | baseline | +0.47 | — | +8.3% | 25.9% | 1030 | 724.2 | +0.60 | base=True |
| ETHUSDT_1h_ema2050 | vix_z | conditioned | +0.61 | +0.14 | +10.5% | 25.5% | 979 | 564.5 | +0.60 | YES |
| ETHUSDT_1h_ema2050 | vix_z+funding_z | baseline | +0.47 | — | +8.3% | 25.9% | 1030 | 724.2 | +0.59 | base=True |
| ETHUSDT_1h_ema2050 | vix_z+funding_z | conditioned | +0.63 | +0.17 | +8.7% | 23.3% | 1300 | 587.4 | +0.59 | YES |

## Verdetto per pilastro

| pillar | verdict | rationale |
|---|---|---|
| funding_z | **NEUTRAL** | ETH-only (no funding su futures ES).  Stessa regola di VIX-z. |
| vix_z | **NEUTRAL** | ΔSR ≥ +0.10 senza turnover > 2× baseline E entrambi sopravvivono CPCV → HELPFUL; se tutti ΔSR < -0.10 → HARMFUL; altrimenti NEUTRAL. |
| vix_z+funding_z | **HELPFUL** | Combinato ETHUSDT-only (min delle scale); ES skip per design.  Regola identica. |

**Interpretazione di NEGATIVO**: qui usato come 'non HELPFUL' (NEUTRAL ∪ HARMFUL); NEUTRAL significa nessun valore di conditioning — la pista è chiusa sotto questa interpretazione.  Nota: ETHUSDT_1h vix-z ΔSR +0.14 resta positivo ma minoritario (1/3 gambe HELPFUL, non maggioranza stretta); la pista è chiusa non perché la gamba ETH non mostri segnale, ma perché il verdetto richiede maggioranza su TUTTE le gambe BL-736 (ES + ETH).

## Confronto con precedente Sprint 2d (funding-z)

| sprint | pillar | leg | SR baseline | SR conditioned | ΔSR |
|---|---|---|---|---|---|
| Sprint 2d (2026-09-03) | funding-z | ETHUSDT_1h ema2050 | +0.51 | +0.46 | -0.05 |
| Sprint 2d (2026-09-03) | funding-z | BTCUSDT_1h ema2050 | -0.02 | -0.52 | -0.50 |

## Verdetto finale EF-004@13-meta-synthesis

**NEGATIVO** — VIX-z (pilastro primario del test) verdict = `NEUTRAL`; pista conditioning-lite **CHIUSA definitivamente**.

Precedente Sprint 2d funding-z = NEGATIVO (ETHUSDT SR +0.51→+0.46; BTCUSDT -0.02→-0.52).  Questo Task 4 con VIX-z (pilastro indipendente) replica l'esito negativo: `NEUTRAL` su VIX-z (soglia HELPFUL = ΔSR ≥ +0.10 su maggioranza delle gambe SENZA turnover > 2× baseline E entrambe sopravvivono CPCV).

**Nessun retry su altri pilastri** (carry, sentiment, positioning, etc.) è giustificato senza una riformulazione teorica (meta-labeling secondario vero, non veto univariato).  Verdetto registry: `morta_per_evidenza` (mappato sullo stato terminale `REJECTED` dello state-machine — `morta` non è raggiungibile da `in_qualifica`).

Risultato per gli altri pilastri testati (informativo, non rilevante per la pista): funding_z = `NEUTRAL`, vix_z+funding_z = `HELPFUL`.

## Limitazioni oneste

- **VIX-z è una serie daily ffill-ata su barre 1h ETHUSDT**: stesso valore per tutte le 24 barre dello stesso giorno; il conditioning è effettivamente daily-frequency anche su leg 1h (accettabile: VIX è un segnale macro-regime, non intraday).
- **Signal ES divergenti da BL-736 letterale**: ema crossover implementato long/short in stile Sprint 2d (non long-only come BL-736 EmaTrend); donchian breakout long-only sulle ES daily.  Baseline numeriche ES qui +0.60/−0.25 vs BL-736 +1.13/+1.08 (delta di implementazione signal, non di conditioning).  ΔSR resta un confronto valido perché baseline e conditioned usano lo stesso signal — il delta riflette l'effetto del conditioning, non la divergenza di implementazione.
- **Funding-z solo su ETHUSDT 1h**: futures ES non hanno perpetual funding; per gli ES legs la pista funding-z è `INSUFFICIENT_DATA` per design.
- **Combined pillar (VIX-z × funding-z) — ETHUSDT-only**: prende min(scale_vix, scale_funding) — entrambi i pilastri devono acconsentire.  Le gambe ES sono skippate per design (funding-z non applicabile a futures ES); produrre righe combined su ES con solo VIX-z sarebbe ridondante del branch VIX-z puro.
- **CPCV libreria `purgedcv`** (già installata): usata via `analytics.qualification.dsr.combinatorial_purged_cv` e `analytics.qualification.lane_b.cpcv_oos_sharpes`.  OOS median richiede ≥24 bars test; sotto soglia il verdetto è segnalato come `survived_cpcv=NO`.
- **Nessuna soglia tunata**: `full_z=2` FROZEN per prereg.  Cambiarlo richiede un ADRRUNNER separato, non un edit in-sprint.
- **PIT**: il valore del pilastro al tempo T condiziona solo barre > T (shift(1) in `load_funding_onto_prices` per funding; in `fuse_vix_z_onto_grid` per VIX).  La review del Task 3 ha trovato un bug sistematico di lookahead — qui coperto da test PIT esplicito (`test_vix_z_pit_*`).
