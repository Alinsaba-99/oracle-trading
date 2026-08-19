# 03 Quant — Data Audit (free $0 verified 2026-08-17)

> Regola hard: $0/mo per dati. Vedi ADR-020.

## Fonti quant methodology free

| Fonte | Coverage | Format | API Key | Note |
|---|---|---|---|---|
| **purgedcv (MIT OSS)** | Purged K-Fold, embargo, CPCV, DSR, PSR | Python lib | nessuna | `pip install purgedcv`. https://github.com/eslazarev/purged-cross-validation |
| **mlfinpy docs** | AFML implementations (triple barrier, meta-labeling, frac diff) | Python lib + docs | nessuna | https://mlfinpy.readthedocs.io. Open source reference |
| **Kenneth French Data Library** | FF3/FF5/MOM/PEAD factors returns 1963+ | CSV zip | nessuna | https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html. **Fonte ufficiale fattori Fama-French** |
| **AQR Data Library** | QMJ, BAB, Momentum, Quality factors returns | CSV | nessuna | https://www.aqr.com/Insights/Datasets. Free factor returns |
| **YCharts/Sharpe ratio docs** | formulas reference | docs | nessuna | Reference per PSR/DSR formula |

## purgedcv capabilities (to integrate)

```
pip install purgedcv
```

- `PurgedKFold` — scikit-learn-compatible time-series CV with purging
- `Embargo` — additional gap to handle serial correlation
- `CPCV` — Combinatorial Purged Cross-Validation with multi-path backtest
- `deflated_sharpe_ratio(returns, n_trials, sr_benchmark)` — DSR calculator
- `probabilistic_sharpe_ratio(returns, sr_benchmark)` — PSR
- `pbo(returns_matrix)` — Probability of Backtest Overfitting via CSCV

## Backtesting frameworks installed in Oracle

| Framework | Stato | Use case |
|---|---|---|
| NautilusTrader | ✅ Installed (vedi `live-readiness-assessment`) | Event-driven, production-grade, realistic |
| vectorbt | ✅ Installed | Vectorized, fast parameter sweeps, multi-asset |
| polars | ✅ Installed | DataFrame operations (vs pandas, 10x faster) |
| cvxpy | ✅ Installed | Convex optimization (portfolio weights, risk parity) |
| scikit-learn | ✅ Installed | PCA, ML models |
| statsmodels | ✅ Installed | HP filter, regression, ADF test |

## Gap dichiarati

1. **purgedcv NON installato** — TODO BL-KB-19. Critico per ADR-017 G5 gate.
2. **mlfinpy NON installato** — alternative implementation di AFML. Opzionale (purgedcv ha same functionality).
3. **Kenneth French data adapter** NON implementato — serve per FF5F regression (vedi BL-KB-06 dominio 01).
4. **AQR data adapter** NON implementato — per QMJ/BAB factor regression.

## Cap da NON usare

| Fonte | Perché esclusa | Alternativa free |
|---|---|---|
| Bloomberg Backtester | $24k/yr | vectorbt + purgedcv |
| QuantConnect Premium | $20-100/mo | vectorbt + NautilusTrader |
| Quantopian (defunct 2020) | defunct | local stack |
| Quantpedia Premium | $50/mo | paper literature review manuale |
| Alphalens (Quantopian) | defunct | vectorbt + custom analysis |
| pyfolio (maintained) | OK | open source, OK |
| zipline-reloaded | OK | open source, OK |

## Reference implementations free

- **mlfinpy**: https://mlfinpy.readthedocs.io — AFML reference (triple barrier, meta-labeling, fractional differencing)
- **purgedcv docs**: https://github.com/eslazarev/purged-cross-validation — example notebooks su BTC, S&P
- **QuantConnect research**: https://www.quantconnect.com/research — PSR + DSR examples
- **MQL5 CSCV article**: https://www.mql5.com/en/articles/13743 — implementation reference

## Documentation access free

- **Bailey/Lopez de Prado publications**: https://www.quantresearch.org/Publications.htm — paper PDFs free
- **AFML book snippets**: https://hudsonthames.org — meta-labeling, triple barrier explained
- **AQR Insight articles**: https://www.aqr.com/Insights — research free
