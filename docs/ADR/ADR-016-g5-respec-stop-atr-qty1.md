# ADR-016: G5 Re-spec — stop ATR 1x, qty 1-only, daily primario, 6 regimi

**Data:** 2026-08-03
**Status:** ACCEPTED (approvazione utente)

---

## Context

BL-023 (M31 sopra le soglie G5) richiedeva di rivedere le regole di
qualifica dopo i fix di misura (Fase 1). Il run 18a6836 era REJECTED ma con
misurazione corrotta (verdetto UNKNOWN). Dopo i fix (contabilità futures,
liquidazione al primo hard breach, annualizzazione, runner su lake) i probe
P1a (stop sensitivity) e P1d (macro consensus) hanno prodotto evidenza:

- 0 hard breaches in TUTTE le config stop (prima: 96) — il fix contabile ha
  risolto alla radice il problema breach.
- Il risk gate prop-firm (budget $500/trade, 1% di 50K) RIFIUTA stop ATR
  2x/3x su MES (rischio $650/$975) e qty 2 con stop ATR nei periodi stress
  (rischio $540-590). Solo ATR 1x o fixed <=60pt passano con qty 1; con
  qty 2 solo stop <=30pt.
- Il segnale ensemble v2 (min_conf 0.5) produce ZERO trade nelle finestre
  M31 (tutti i target nel warmup) → Sharpe 0.0, REJECTED onesto. Il segnale
  è il vero lavoro rimasto (Fase 4).
- Il blocker macro_surprise è risolto: fonte consensus NASDaq economic
  calendar (costo zero, actual+consensus point-in-time) → 6/6 regimi.

## Decision

La qualifica M31 (G5) usa:

1. **Timeframe primario: daily** (ES 1d, 6522 bar dal lake, 2913 >= 2015).
   ES 1h (13.7K bar, solo dal 2024) come cross-check obbligatorio dichiarato
   (F-20: 1h = solo holdout).
2. **Stop: ATR 1x** (period 14, point-in-time, calcolato sul prefix, mai
   lookahead) come default. Fixed 30pt resta disponibile come alternativa
   eseguibile con qty 2 (verificato: passa il risk gate ovunque).
3. **Quantità: 1-only** con stop ATR. N onesto = regimi × finestre × qty
   (curve uniche, F-08). qty 2 solo con stop 30pt se si vuole N maggiore.
4. **Soglie**: Sharpe >= 0.5 resta; `luck_p_value` entra nel gate
   (era calcolato ma ignorato); DD <= 4% ridefinito come vincolo di
   sopravvivenza (liquidazione attiva al primo hard breach) con report
   troncato + controfattuale senza liquidazione (F-15).
5. **Regimi: 6/6** (macro_surprise ora selezionabile). Se un regime ha 0
   osservazioni nel report → verdetto non APPROVED (guard esistente).
6. **N onesto**: top-3 finestre per regime × 1 qty = 18 curve uniche
   (o 30-36 con qty 1-2 + stop 30pt).

## Rationale

- ATR 1x è l'unico multiplo ATR che il risk gate prop-firm accetta su tutti
  i regimi con qty 1 (misurato: bear 54.3pt, high_vol 58.8pt, liq_shock
  58.1pt, bull 24.1pt, sideways 35.4pt; 1x*qty1 passa ovunque).
- qty 1-only elimina la classe di rifiuti risk gate nei periodi stress.
- daily primario perché 1h parte dal 2024: senza train pre-2023 la
  calibrazione dei candidati segnale violerebbe l'anti-overfit (F-16/F-20).
- luck_p_value nel gate perché è già calcolato (models.py:240) e ignorarlo
  renderebbe il verdetto vulnerabile a serie fortunate corte.
- 6 regimi resta perché la fonte consensus esiste a costo zero (P1d) — la
  re-spec "5+1 condizionato" non è più necessaria.

## Consequences

- Fase 3 (infra): già quasi tutta implementata (slice_period, warmup >= 100,
  DataRegistry force, macro events cablati). Resta: consolidamento runner
  (F-05), report con luck test + controfattuale, deprecazione
  run_replay_qualification.py.
- Fase 4 (segnale): il lavoro vero — l'ensemble v2 non trade nelle finestre
  M31. Candidati BL-200 (roc_momentum_12, bollinger, donchian) ri-derivati
  su train pre-2023, validati su holdout 2023+, MAI sulla finestra M31.
- Se il re-run con misurazione corretta e segnale che trade mostra Sharpe
  < 0.5 → pivot esplicito documentato (non promozione fittizia).
- Backlog: pulire dipendenze morte (ta-lib, pyportfolioopt — dichiarate ma
  mai importate, verifica 2026-08-03) o documentarne l'uso.

## Audit Trail

- Probe P1a: docs/reports/m31-rerun/stop-probe.json (7 config, 5 regimi,
  0 breach, risk gate rifiuta ATR 2x/3x).
- Probe P1d: data/macro/m31-events.json (13 eventi high-impact NASDaq) →
  6/6 regimi selezionati.
- Finding segnale: ensemble v2 = 0 trade nelle finestre M31 (diagnosi
  script probe, 2026-08-03).
