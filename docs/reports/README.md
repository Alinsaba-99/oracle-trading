# Report — Indice per gate

> Indice dei report versionati con mappatura al gate/stato di appartenenza.
> Ogni gate ha evidenza riproducibile: i numeri in STATUS.md devono essere
> tracciabili a un report di questo indice. Aggiornato: 2026-08-10.
> Nota: `.json` è l'evidenza machine-readable; il `.md` omonimo è la lettura.

## G5 — Research truth

| Report | Esito | Nota |
|---|---|---|
| `docs/reports/m31-rerun-final/m31.{json,md}` | **REJECTED** | report canonico ADR-016 (ensemble v2, N onesto): median Sharpe -2.51, 0 breach, N=8<48 ⚠️ |
| `docs/reports/m31-rerun/m31.{json,md}` + `notes.md` | REJECTED | re-run BL-023 (regime ribilanciato) |
| `docs/reports/candidates/<signal>.{json,md}` (8) | 8/8 REJECTED | sweep candidati nel gate reale (BL-023 Fase 5c) |
| `docs/reports/multiasset/walkforward.{json,md}` | 0/9 vs buy&hold | multi-asset walk-forward ES/SPY/BTC (BL-023 Fase 2) |
| `docs/reports/s0-1-bl023-autopsy.md` | autopsia | BL-023: benchmark = beta scambiato per alpha (BL-093) |
| `docs/reports/s0-2-economic-model.md` + `s0-2/eval_*.json` | lane daily morta | modello economico prop-firm (BL-094) |
| `docs/reports/m31-historical-replay-qualification.{json,md}` | storico | primo replay M31 (pre-ADR-014, invalidato) |
| `docs/reports/2026-07-19-m31-closeout.md` | storico | chiusura M31 19-lug (invalidato da ADR-014) |

## G6 — Paper & shadow

| Report | Esito | Nota |
|---|---|---|
| `docs/reports/m32-paper-replay-diagnostic.json` | 20/20, DD 0.21% | primo diagnostic M32 (WP1) |
| `docs/reports/2026-07-22-m32a-20y-analysis.json` | 20y | M32a analisi 20 anni |
| `docs/reports/2026-07-23-m32a-post-beta.{json,md}` | 23/30 | M32a post-beta fix (WP2) = REJECTED |
| `docs/reports/g6-wp2-final/g6-wp2-final.md` | 30/30, 0 trade | run post-fix senza trade → non qualifica (BL-024) |

## G2 — Contract data

| Report | Esito | Nota |
|---|---|---|
| `docs/reports/import-graph-analysis-20260730.md` | analisi | grafo import (07-30) |
| `data/lake/metadata/*.json` | audit | coverage/lineage/ingestion (BL-096/BL-307) |

## Trasversali

| Report | Esito | Nota |
|---|---|---|
| `docs/reports/live-readiness-gap-analysis.md` | 3/3 chiusi | FRED vintage + pessimistic-fill + cvxpy KEEP (2026-08-10) |
| `docs/reports/edge-portfolio/edge-portfolio.md` | 4 edge > baseline | BL-200 (probe, non gate) |
| `docs/reports/signal-candidates/signal-candidates.json` | candidati | probe segnali (input Fase 5c) |
| `docs/reports/quant-finance-analysis.md` | analisi | quant finance (2026-07-28) |

## Convenzioni

1. Ogni verdetto di gate deve citare un report di questo indice (file:riga o
   hash). Nessun numero orfano in STATUS/BACKLOG.
2. I report con `.json`+`.md` omonimi devono essere allineati (stesso commit,
   stessi numeri). Disallineamento = drift documentale.
3. I report storici invalidati da un ADR restano nell'indice marcati "storico"
   — mai cancellare l'evidenza.
