# scripts/legacy — Untracked scripts con mypy errors

> Directory di quarantena. Questi script sono stati committati untracked
> in working tree prima del 25-lug-2026 e hanno **errori mypy bloccanti**.
>
> Per chi tocca il repo: NON eseguire questi script senza prima risolvere
> i loro errori mypy (BL-030 del [BACKLOG.md](../../BACKLOG.md)).

## Lista

| Script | Stato | AC per promuovere a `scripts/contrib/` |
|---|---|---|
| `run_backtest_evaluation.py` | mypy errori | refactor: type hints + `from __future__ import annotations` + rimuovere monkey patches |
| `run_lorentzian_test.py` | mypy errori | idem |
| `run_lorentzian_v2.py` | mypy errori | idem |
| `run_risk_sized_eval.py` | mypy errori | idem |
| `run_rolling_challenge.py` | mypy errori | idem |

## Decisione (da BL-030)

- se il refactor mypy è veloce (< 30min per script): promuovere a `scripts/contrib/`
- se il refactor è grande: lasciare qui e marcare come "frozen" con un
  warning in cima al file

## Come sono finiti qui

Sono stati creati durante sessioni precedenti (vedi git history
`a5ef2dc` e `ffe91b4`) ma mai committati — rimasero come untracked.
La sessione 25-lug li ha spostati qui invece di committarli per evitare
di rompere `make typecheck` (vedi BL-031 warning budget).