# 01 Fundamental — Edge Plausibility

> Valutazione critica per ogni sotto-edge: persists OOS? Decay rate? Regime-dependent? Costs?

## Edge plausibility summary

| Edge | Paper | Edge storico | Edge OOS 2020-2025 | Decay | Regime |
|---|---|---|---|---|---|
| Piotroski F-Score | Piotroski 2000 | +13.4%/yr | +3-5%/yr (~30% decay) | medio | Bull value regime |
| Lakonishok value | LSV 1994 | +5%/yr (3-5y) | +3-5%/yr | basso | Bull value regime |
| Greenblatt Magic Formula | Greenblatt 2006 | +18.4%/yr | +4-6%/yr (~70% decay) | alto | Bull value regime |
| Novy-Marx gross profitability | Novy-Marx 2013 | +3.7%/yr | +2-3%/yr (~30% decay) | medio | All-weather |
| QMJ quality | Asness 2019 | +5%/yr (4-factor alpha) | +2-3%/yr | basso | All-weather |
| Fama-French 5F HML+RMW+CMA | Fama-French 2015 | +3-5%/yr | +1-2%/yr (HML often redundant) | alto | Cycle |
| Accrual anomaly | Sloan 1996 | +5%/yr | +1-2%/yr (~70% decay) | alto | All-weather |
| Altman Z-score | Altman 1968 | 72% bankruptcy accuracy | maintained | basso | All-weather |
| PEAD | Piotroski-So 2012 | +4%/yr | +2-3%/yr | medio | All-weather |
| Shiller CAPE | Campbell-Shiller 1988 | 10y predict -0.5 corr | maintained | basso | 10y orizzonte |
| Buffett alpha | Frazzini-Kabiller-Pedersen 2018 | 19% yr 1976-2011 | post-1995 -1.9% | alto | Cycle |
| 52-week high | George-Hwang 2004 | +6%/yr | +2-3%/yr | medio | All-weather |
| Earnings momentum | Chan-Jegadeesh-Lakonishok 1996 | +8%/yr | +3-4%/yr | medio | All-weather |

## Verdetto edge

**Edge reale documentato** ma:
1. **Decay post-publication ~30%** (McLean-Pontiff 2016) → aspettati ~70% del backtest storico.
2. **Regime-dependent** — value ha underperformed 2014-2020 (-5%/yr), rimbalzato 2020-2023 (+11%/yr). Lane B Oracle 2020-2025 = bull market bias.
3. **Edge residuo dopo FF5F + BAB + QMJ** ≈ 0 per Buffett, ~1-2% per Magic Formula, ~2-3% per Piotroski.

## Edge conditioning

Per ridurre decay + exploit edge reale:
1. **Combinare signals** (Piotroski + Greenblatt + Lakonishok + Novy-Marx + accruals) → già fatto in `CompositeLaneBScore`.
2. **Orizzonti lunghi** (3-5y Lakonishok, 10y CAPE) — NON quarterly.
3. **Regime filter** — long value quando value-growth spread è compressed.
4. **Fundamental momentum overlay** — preferire tickers con improving F-Score (ΔROA positive), non solo high absolute.
5. **PEAD overlay** — long high-F-Score + recent positive earnings surprise.

## Cost-realism check

- **Trading costs**: 0.05% spread + 0.10% slippage + $1 commission per trade. Su 25-stock portfolio quarterly rebalance = 100 trades/yr × ($1 + 0.15% × $10k) = $2.5k/yr su $100k = 2.5% drag.
- **Tax**: 26% IT capital gains → +5% post-tax alpha needed.
- **Net edge realistico** post-cost: +2-5%/yr su 5y (vs ~10% historical backtest). Sharpe 0.5-0.8.

## Validazione G5 (ADR-017)

Per promozione Lane B paper → shadow → evaluation → funded serve:
- DSR (Deflated Sharpe Ratio) > 0.95
- PBO (Probability of Backtest Overfitting) < 0.5
- CPCV (Combinatorial Purged Cross-Validation) OOS Sharpe > 0.5
- 250+ sessioni paper con pass-rate ≥ 90%

`purgedcv` (MIT, free, OSS) implementa DSR/PBO/CPCV. Vedi deep-research synthesis 2026-08-15.
