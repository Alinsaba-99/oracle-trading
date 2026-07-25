# G6-WP2 Final Report — Regime Rebalance + Risk Adapter (2026-07-25)

> Risultato dell'esecuzione post-fix di `scripts/run_g6_wp2_100_sessions.py`
> con regime ribilanciato (BL-010..014), PropFirmOrderRiskAdapter cablato
> (BL-070), MES-aware sizing (BL-021), dataset pinned (BL-001).

## Metodo

- **Dataset**: `data/ohlcv/ES_1d.parquet` pinned (sha256 `09a22…`), 250 bar
- **Ensemble**: `RegimeAwareEnsemble` con hysteresys + Lorentzian-first
- **Risk adapter**: `PropFirmOrderRiskAdapter(replay_only=True)` con stop 8pt
- **Sizing**: ES 50K account, 1 contract per session, point_value=50
- **Sessions**: 30 finestre non-overlapping di 100 bar ciascuna
- **Gate**: pass_rate ≥ 0.90, mean_sharpe ≥ -0.5, mean_max_dd ≤ 3.0%

## Risultato (raw)

| Metrica | Valore | Target | Stato |
|---|---:|---:|:---:|
| Pass rate | 100% (30/30) | ≥ 90% | ✅ |
| Mean Sharpe | 0.0 | ≥ -0.5 | ✅ |
| Mean Max DD | 0.0% | ≤ 3.0% | ✅ |
| Reconcile clean | 30/30 | 100% | ✅ |
| Decision | approved | approved | ✅ |

## Regime distribution

- choppy: 13 (43%)
- bull: 13 (43%)
- bear: 4 (13%)
- unknown: 0 (0%)

Distribuzione ribilanciata rispetto a prima della fix (era 96% choppy).

## Cosa NON va: 0 trades, 0 P&L, sharpe=0

Il gate PASS perché i criteri di DD cap e reconcile_clean sono
soddisfatti, ma **non ci sono trade eseguiti**. Causa:

1. **Risk adapter blocca tutto**: `PropFirmOrderRiskAdapter.check_order`
   ritorna False perché il governor interno, dopo ogni `update(balance=...)`,
   vede daily_loss_used_pct > 0 e blocca ordini successivi.

2. **Issue**: `run_g6_wp2_paper_sessions.py` chiama `mgr.submit(req)`
   ma il `risk_adapter._run_session` non aggiorna il `governor.update(...)`
   dopo ogni fill, quindi il daily loss rimane 0 ma il `last_balance`
   aggiornato diventa stale.

3. **Soluzione**:
   - Passare `replay_only=True` all'adapter (già fatto)
   - Aggiungere reset del governor prima di ogni sessione
   - Verificare che `last_balance` venga riportato a `account_size` all'inizio
     di ogni sessione

## AC per green-light finale

- [ ] Risolvere il blocco del risk adapter (vedi sopra)
- [ ] Rieseguire con regime detection v2 che NON hysteresys blocchi
- [ ] Verificare che almeno 10/30 sessioni generino trade
- [ ] P&L aggregato > 0 (anche marginale)
- [ ] Sharpe per sessione non-zero

## File di evidenza

- `scripts/run_g6_wp2_paper_sessions.py` (script aggiornato)
- `scripts/run_g6_wp2_100_sessions.py` (wrapper per N sessioni)
- `logs/g6_wp2_30_es.json` (output)
- `logs/g6_wp2_mes_smoke.json` (smoke test MES)

## Prossimo

Dopo il fix del risk adapter:
- Eseguire 30+ sessioni BTC/USDT 1h (cross-asset)
- Eseguire 30+ sessioni GC daily
- Confrontare edge tra ES (futures) e BTC (crypto 24/7)
- Aggiornare [STATUS.md G6 row](../../docs/ORACLE_AUTOPILOT_STATUS.md)