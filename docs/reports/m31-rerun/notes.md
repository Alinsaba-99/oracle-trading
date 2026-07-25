# M31 Rerun — Note post-fix (2026-07-25)

> Questo report documenta il risultato del M31 re-run DOPO i fix del
> 25-lug (G3 Postgres + reconciliation worker + recovery service +
> factor timing + Lorentzian causal fix + regime ensemble). M31 è
> **ancora REJECTED**, ma è una riproducibilità accertata, non più un
> dataset lineage GAP (vedi [ADR-014](../../docs/ADR/ADR-014-m31-evidence-loss.md)).

## Decisione raw

- **Decisione**: REJECTED
- **Median Sharpe**: 0.3424 vs threshold ≥ 0.5 ❌
- **Median Sortino**: 0.4921 vs threshold ≥ 0.5 ❌
- **Worst drawdown**: 15.94% vs threshold ≤ 4% ❌
- **Hard breaches**: 88 (troppi, threshold = 0) ❌

## Cosa è cambiato dal M31 vecchio

1. **Dataset pinned** (sha256 `09a22…`) — verificabile con
   `scripts/check_dataset_pin.py`.
2. **Regime detection ribilanciata** (BL-010..014) — ma questo report
   è eseguito col regime vecchio perché `run_replay_qualification.py`
   non è stato ancora aggiornato per usare il regime ribilanciato.
3. **PropFirm risk adapter testato** (BL-070) — ma NON cablato nel
   paper run di M31 (richiede BL-070 → run_g6_wp2 update).
4. **Lorentzian causal fix** — non ancora integrato in M31 run.

## Cosa serve per green-light M31 (BL-022 completato)

1. **Aggiornare `run_replay_qualification.py`** per usare:
   - regime ribilanciato (BL-010..014)
   - PropFirmOrderRiskAdapter come risk_manager (BL-070)
   - Lorentzian causal fix (commit `ffe91b4`)
   - MES-aware sizing (BL-021)

2. **Ri-eseguire 6 regimi × 8 varianti** (48 osservazioni) con
   dataset pinned, regime ribilanciato, risk adapter cablato.

3. **AC per G5 PASSED**:
   - Median Sharpe ≥ 0.5
   - Worst drawdown ≤ 4%
   - Hard breaches = 0
   - Dataset hash in header
   - 6 regimi coperti (bull, bear, choppy, volatile, macro-up, macro-down)

## Cosa NON cambia anche dopo BL-022

- M31 copre solo historical replay (G5 dice: "certifica QUALITY del
  backtest engine", non "autorizza live").
- G6 paper + G7 firm + G8 evaluation sono gate separati. M31
  verde non promuove automaticamente a live.

## Comandi usati

```bash
.venv/bin/python scripts/run_replay_qualification.py
# Output:
#   docs/reports/m31-historical-replay-qualification.{json,md}
#   Decisione: REJECTED
#   6 periodi × 8 varianti = 48 osservazioni
```

## File di evidenza

- `docs/reports/m31-historical-replay-qualification.json` (raw)
- `docs/reports/m31-historical-replay-qualification.md` (markdown)
- Questo file (`docs/reports/m31-rerun/notes.md`) — note post-fix
- `scripts/check_dataset_pin.py` — verifica pin
- `logs/regime_distribution.json` — distribuzione regime ribilanciata

## Status

| Gate | Stato | Note |
|---|---|---|
| G5 | ❌ REJECTED | questo report documenta la **ripetibilità** ma non la PROMOTE |
| G6 paper | 🟡 vedi BACKLOG.md BL-020..024 | dipende da BL-022 + ensemble |
| G7 firm | ⚪ BL-100 + ADR-015 | Topstep local-only |

M31 resta REJECTED in STATUS.md fino a quando il rerun con regime
ribilanciato + risk adapter + Lorentzian dà median Sharpe ≥ 0.5 e
worst drawdown ≤ 4%.