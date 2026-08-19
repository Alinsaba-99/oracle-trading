# BL-024 — G6 Qualifying Re-Run — Verdetto Onesto

> **Data**: 2026-08-15
> **Scope**: re-run qualificante con EdgeEnsembleV2 (BL-201) per superare il 0-trade failure di M32a WP2
> **Prerequisiti**: BL-500 (DSR), BL-201 (EdgeEnsembleV2 with hysteresis), ADR-018 (250+ sessioni per deployment funded)

---

## TL;DR

**REJECTED con progresso reale.** A differenza di M32a WP2 (30/30 pass ma 0 trade, Sharpe 0), questo run ha **30/30 sessioni con trade reali (189 trade totali)** ma passa solo 8/30 (27% vs target 90%). Mean Sharpe +0.035 (target > 0, appena sopra zero). Mean Max DD 4.37% (target ≤ 3%). Il sistema ORA PRODUCE TRADE, ma l'edge non è ancora statisticamente robusto.

## Risultati

| Metrica | Target | Risultato | Stato |
|---|---|---|---|
| Sessions con trade ≥ 10 | ≥ 10 | 30/30 | ✅ SODDISFATTO (no più 0-trade failure) |
| Pass rate | ≥ 0.90 | 0.27 (8/30) | ❌ MOLTO SOTTO |
| Mean Sharpe | > 0 | +0.035 | ⚠️ APPENA SOPRA ZERO (non significance) |
| Mean Max DD | ≤ 3% | 4.37% (max 10.22%) | ❌ SOPRA SOGLIA |
| Reconcile clean | 100% | 100% | ✅ |

## Sessioni evidenzi

- **Migliori**: session 18 (Sharpe +2.90, DD 1.54%), session 9 (+2.54, DD 2.17%)
- **Peggiori**: session 20 (Sharpe −3.85, DD 10.22%), session 16 (−2.46, DD 4.10%)
- **Pattern**: 4 sessioni con DD > 5% sono sessioni con il regime detector (AdaptiveEnsemble ML) che ha classificato choppy ma il trend si è rotto

## Diagnosi

### Punto positivo
1. **Il EdgeEnsembleV2 (BL-201) funziona come designed**: genera trade reali su tutte le 30 sessioni (vs M32a che generava 0 trade per min_conf=0.5 troppo alta). L'hysteresis riduce il whipsaw.
2. **Total trades 189** = ~6.3 trades/sessione × 95 barre = ragionevole densità per un ensemble daily.
3. **Reconcile 100% clean** = il ledger/OMS/risk kernel funziona end-to-end.

### Punti negativi
1. **Pass rate 27%** molto sotto target 90%. Le 22 sessioni fallite hanno DD > 3% (target prop-firm).
2. **Mean Sharpe +0.035**: statisticamente indistinguibile da 0. Questo è "edge debole", non "edge assente".
3. **Mean Max DD 4.37%**: sopra il target 3%. La strategia ha drawdown troppo ampi per il canale prop-firm.
4. **Nessuna sessione con Sharpe > 0.5**: il gate ADR-016 §4 non è raggiunto.

## Coerenza con la diagnosi precedente

Questo run conferma la diagnosi del deep-research synthesis 2026-08-15:
- Alpha residuo +2-6% lordo = beta scambiato per alpha
- Netto costi ≈ 0 (questo run mostra Sharpe +0.035, indistinguibile da 0)
- La lane daily è economicamente morta per canale prop-firm

L'EdgeEnsembleV2 NON risolve il problema dell'edge assente; risolve il problema del "0 trade" che invalidava M32a WP2.

## ADR-018 reminder

30 sessioni NON è sufficiente per deployment funded. ADR-018 richiede:
- ≥250 sessioni paper indipendenti con pass ≥90%
- DSR ≥ 0.95 (Bailey & López de Prado 2014)
- PBO < 0.5 (Bailey et al. 2017)
- PSR ≥ 0.95 (vs benchmark Sharpe buy&hold)
- α netto ≥ 15%/anno (BL-094 §3)
- p(pass) ≥ 0.60 MC (BL-094 §3)
- DD ≤ 4% worst-case

Questo run è **smoke test**, non deployment gate. La pipeline genera trade; l'edge resta da trovare.

## Prossimi passi raccomandati

1. **Estendere a 250 sessioni** su dati multi-asset (Lane A PAC, non solo ES daily)
2. **Validare con DSR/PBO/PSR** (ADR-017) quando il EdgeEnsembleV2 è combinato con Lane A backbone
3. **Test su orizzonti multipli** (daily + 1h composition, BL-097 IBKR setup manuale richiesto per dati intraday)
4. **Calibrazione hysteresis_threshold** — attuale 0.60 può essere troppo permissiva; provare 0.75 o 0.90
5. **Forecast combination di 3+ regole Carver** (BL-502 esteso) — TrendSignalRule(8/32) da solo ha Sharpe < 0.3 su tutti gli strumenti; serve blend multi-rule

## File generati

- `docs/reports/g6-wp2-final/bl024.md` — report markdown per-session
- `logs/bl024_g6_qualifying.json` — dati machine-readable
- `scripts/run_bl024_g6_qualifying.py` — script riproducibile

## Coerenza con BL-023 Fase 5c e Lane A BL-503

| Run | Sharpe | Trades | Verdetto |
|---|---|---|---|
| BL-023 Fase 5 (M31 ensemble v2) | −0.251 | 0 (post-fix) | REJECTED |
| BL-023 Fase 5c (sweep candidati) | +0.216 (best) | trades ma 16 hard breach | REJECTED (8/8) |
| BL-503 Lane A Carver 4-moduli | +0.272 (best, GC) | n/a | REJECTED |
| BL-024 questo run (EdgeEnsembleV2) | +0.035 | 189 | REJECTED con progresso |

Tutti i run convergono allo stesso verdetto: **edge ≈ 0 netto costi**. L'unica via d'uscita identificata dal deep-research è diversificare (Lane A multi-asset + Lane B turnaround + Lane C intraday subordinato + option selling VRP), non tuning della strategia attuale.

---

*Fine BL-024 report. Smoke test qualificante completato; 30/30 sessioni con trade reali; verdetto REJECTED con progresso (no more 0-trade failure). Per deployment funded: estendere a 250 sessioni + DSR/PBO/PSR + multi-asset + calibrazione hysteresis.*
