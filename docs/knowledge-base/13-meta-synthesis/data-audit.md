# 13 Meta-synthesis — Data Audit (free $0 verified 2026-08-17)

> Regola hard: $0/mo per dati. Vedi ADR-020.

## Fonti meta-synthesis free

| Fonte | Coverage | Format | API Key | Note |
|---|---|---|---|---|
| **`PyPortfolioOpt` Python lib** | portfolio optimization + HRP | Python lib | nessuna | `pip install PyPortfolioOpt`. Includes HRP implementation |
| **`riskparity.py`** | risk parity portfolio | Python lib | nessuna | `pip install riskparityportfolio`. Advanced RP methods |
| **`hmmlearn` Python lib** | Hidden Markov Models | Python lib | nessuna | `pip install hmmlearn`. Hamilton regime switching |
| **`scikit-learn` (installed)** | ML models + meta-labeling | Python lib | nessuna | RandomForest, GradientBoosting for meta-labels |
| **`statsmodels` (installed)** | regime switching + HMM | Python lib | nessuna | Markov switching regression |
| **Lane A+B+C+D+E+F+G+H+I+J+K ensemble** | 11 lanes from 12 domains | Python | nessuna | Costruire da dominio 01-12 backlog items |

## Capabilities Oracle esistenti

- ✅ Lane B backtester (Sharpe 0.93 fundamental equity)
- ✅ Lane D VRP backtester (Sharpe -0.08, edge assente — da fixare con regime filter)
- ✅ AI Analyst Swarm (5 analysts + Synthesizer + Skeptic + Risk Manager)
- ✅ PaperBroker + PaperOrchestrator (Step 4 Opzione C)
- ✅ NautilusTrader + vectorbt + polars + cvxpy installed
- ✅ purgedcv to install (BL-KB-19 dominio 03)

## Gap dichiarati

1. **Meta-synthesis orchestrator** NON implementato. TODO BL-KB-92.
2. **Hamilton HMM regime classifier** NON implementato. TODO BL-KB-93.
3. **HRP portfolio allocator** NON implementato. TODO BL-KB-94.
4. **Meta-labeling position sizer** NON implementato. TODO BL-KB-95.
5. **Ensemble validation pipeline** NON implementato. TODO BL-KB-96.

## Cap da NON usare (paywalled)

| Fonte | Perché esclusa | Alternativa free |
|---|---|---|
| Bloomberg B-Pipe + terminal | $24k/yr | yfinance + FRED + SimFin + Etherscan |
| Refinitiv Eikon | $1.8k/mo | same |
| AQR style factors Premium | institutional | AQR free + Kenneth French |
| WorldQuant Alpha | institutional | custom signals |
| Two Sigma Vint | institutional | custom signals |
| Numerai historical | limited free | custom signals |

## Reference implementations free

- **PyPortfolioOpt HRP**: https://pyportfolioopt.readthedocs.io/en/latest/HierarchicalRiskParity.html
- **hmmlearn regime switching**: https://hmmlearn.readthedocs.io
- **Lopez de Prado AFML**: https://github.com/hudson-and-thames/research — snippets free
- **QuantConnect meta-labeling**: https://www.quantconnect.com/research — example notebooks
- **RiskParityPortfolio PyPI**: https://pypi.org/project/riskparityportfolio/
