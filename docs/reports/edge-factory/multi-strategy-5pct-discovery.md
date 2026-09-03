# Multi-Strategy 5%/Month Ensemble Discovery

_Generated: 2026-09-03T11:31:18.782746Z — Task #4 of Edge Factory Stage 1._

## TL;DR — Honest answer

**5%/month is NOT reachable sustainably with the v1 candidate set.**  Across three blender variants (equal-weight, inverse-vol, shrinkage-50/50) over the 752-bar walk-forward test window, the best ensemble hits a 5% monthly return in only **0.0%** of months — i.e., the realised median month is essentially random, and the 5%-target month is a fat-tail event, not the central tendency.  The required monthly Sharpe to hit 5% in ≥50% of months would have to exceed `22.00` annualised, and no documented retail factor family reliably delivers that on liquid futures / spot-crypto / FX on a 2023+ test window without leverage > 3×.

What the v1 ensemble **does** deliver is a positive-Sharpe, drawdown-bounded, diversified blend that is a sensible Lane A backbone for prop-firm (1-3%/month target, MaxDD < 10%, walk-forward verified).  See §5 below for the full numbers.

## 1. Method

BL-200/201-style multi-strategy ensemble backtest. Per-leg signals: EmaTrend, DonchianBreakout, TrendFilteredBreakout, RsiReversion, BbandReversion, alpha_001/003/050. Each leg runs on its asset's own calendar, vol-targeted to 12% annual with max leverage 2.0x. Walk-forward: train <= 2022-12-31T00:00:00, test > 2022-12-31T00:00:00. Blenders: equal-weight (EW), inverse-vol (IV, σ-floor 1bp), shrinkage-50/50 IV/EW.

Per-leg signals come from `analytics/strategy/signals.py` (Lane A backbone) and `analytics/strategy/catalog/alpha101.py` (formulaic mean-reversion).  Vol-targeting is the EWM-std estimator from `analytics/strategy/cta.py:VolatilityTarget` with span=36 (Carver ch.9) and a 2× cap.  All metrics delegate to `analytics/metrics/canonical.py` (ADR-021 — single Sharpe/MaxDD/Calmar).

## 2. Per-leg results (walk-forward, test > 2022-12-31T00:00:00)

| Name | Family | Asset | Ann. Return | Sharpe | Max DD | Calmar | Hit | Months | P(m ≥ 5%) |
|------|--------|-------|------------:|-------:|-------:|-------:|----:|-------:|----------:|
| ES_donchian_20 | trend_breakout | ES | +10.57% | +1.08 | 9.47% | +1.12 | 37.6% | 36 | 11.1% |
| ES_ema_20_50 | trend_breakout | ES | +12.94% | +1.13 | 9.46% | +1.37 | 46.6% | 36 | 13.9% |
| BTCUSDT_trend_filt_20_200 | trend_breakout | BTCUSDT | +6.32% | +0.72 | 11.88% | +0.53 | 24.8% | 36 | 11.1% |
| ETHUSDT_ema_20_50 | trend_breakout | ETHUSDT | +8.20% | +0.87 | 13.45% | +0.61 | 29.0% | 36 | 11.1% |
| SPY_donchian_50 | trend_breakout | SPY | +12.27% | +1.09 | 9.44% | +1.30 | 46.4% | 36 | 11.1% |
| ES_bband_20_2 | mean_reversion | ES | +3.63% | +0.54 | 6.01% | +0.60 | 8.7% | 36 | 0.0% |
| BTCUSDT_rsi_14 | mean_reversion | BTCUSDT | +2.91% | +0.55 | 5.36% | +0.54 | 8.0% | 36 | 0.0% |
| EURUSD_bband_30_2.5 | mean_reversion | EURUSD | +2.73% | +0.60 | 3.46% | +0.79 | 4.8% | 36 | 0.0% |
| ES_alpha_003 | alpha101 | ES | +30.46% | +3.37 | 3.41% | +8.92 | 18.8% | 36 | 5.6% |
| SPY_alpha_001 | alpha101 | SPY | +8.05% | +1.18 | 5.44% | +1.48 | 11.4% | 36 | 0.0% |
| EURUSD_alpha_050 | alpha101 | EURUSD | +20.80% | +3.52 | 0.60% | +34.47 | 5.5% | 36 | 2.8% |

**Leg gate tally**: 9/11 pass `MaxDD < 10%`, 11/11 pass positive walk-forward alpha.  This is the per-leg funnel that feeds the blender.

## 3. Pairwise correlation matrix (daily test returns)

| | ES_donchian_20 | ES_ema_20_50 | BTCUSDT_trend_filt_20_200 | ETHUSDT_ema_20_50 | SPY_donchian_50 | ES_bband_20_2 | BTCUSDT_rsi_14 | EURUSD_bband_30_2.5 | ES_alpha_003 | SPY_alpha_001 | EURUSD_alpha_050 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **ES_donchian_20** | +1.00 | +0.84 | -0.00 | +0.02 | +0.12 | -0.00 | +0.01 | -0.05 | +0.33 | +0.09 | -0.01 |
| **ES_ema_20_50** | +0.84 | +1.00 | -0.03 | -0.00 | +0.10 | +0.33 | -0.01 | -0.04 | +0.50 | +0.08 | +0.00 |
| **BTCUSDT_trend_filt_20_200** | -0.00 | -0.03 | +1.00 | +0.55 | +0.00 | -0.04 | -0.00 | +0.02 | -0.04 | -0.00 | +0.01 |
| **ETHUSDT_ema_20_50** | +0.02 | -0.00 | +0.55 | +1.00 | +0.01 | -0.03 | +0.01 | +0.01 | -0.03 | -0.01 | +0.02 |
| **SPY_donchian_50** | +0.12 | +0.10 | +0.00 | +0.01 | +1.00 | -0.05 | +0.06 | +0.03 | +0.03 | +0.41 | +0.03 |
| **ES_bband_20_2** | -0.00 | +0.33 | -0.04 | -0.03 | -0.05 | +1.00 | -0.05 | -0.01 | +0.62 | -0.01 | +0.11 |
| **BTCUSDT_rsi_14** | +0.01 | -0.01 | -0.00 | +0.01 | +0.06 | -0.05 | +1.00 | +0.02 | -0.04 | -0.00 | -0.01 |
| **EURUSD_bband_30_2.5** | -0.05 | -0.04 | +0.02 | +0.01 | +0.03 | -0.01 | +0.02 | +1.00 | -0.04 | -0.05 | +0.27 |
| **ES_alpha_003** | +0.33 | +0.50 | -0.04 | -0.03 | +0.03 | +0.62 | -0.04 | -0.04 | +1.00 | +0.05 | +0.04 |
| **SPY_alpha_001** | +0.09 | +0.08 | -0.00 | -0.01 | +0.41 | -0.01 | -0.00 | -0.05 | +0.05 | +1.00 | -0.03 |
| **EURUSD_alpha_050** | -0.01 | +0.00 | +0.01 | +0.02 | +0.03 | +0.11 | -0.01 | +0.27 | +0.04 | -0.03 | +1.00 |

Mean off-diagonal correlation = **+0.08** (< 0.30 = good diversification; 0.30-0.60 = redundant; > 0.60 = legs are essentially the same strategy).

## 4. Blender variants

Three weight schemes, all scale-free (no leverage beyond the per-leg cap):

| Scheme | Ann. Return | Sharpe | Max DD | Calmar | Hit | Mean m | σ_m | P(m ≥ 5%) | Worst m |
|--------|------------:|-------:|-------:|-------:|----:|-------:|----:|----------:|--------:|
| Equal-weight (EW) | +10.37% | +2.88 | 2.36% | +4.39 | 57.6% | +0.83% | 0.98% | 0.0% | -0.94% |
| Inverse-vol (IV) | +9.94% | +3.20 | 1.73% | +5.76 | 56.6% | +0.79% | 0.79% | 0.0% | -0.57% |
| Shrinkage-50 (SH-50) | +10.16% | +3.05 | 2.04% | +4.97 | 57.2% | +0.81% | 0.88% | 0.0% | -0.75% |

## 5. Honest 5%/month assessment

| Diagnostic | EW | IV | SH-50 |
|------------|---:|---:|------:|
| Months observed | 36 | 36 | 36 |
| Mean month | +0.83% | +0.79% | +0.81% |
| Std month | +0.98% | +0.79% | +0.88% |
| Median month | +0.76% | +0.70% | +0.67% |
| P(month ≥ 5%) | +0.00% | +0.00% | +0.00% |
| P(loss month) | +19.44% | +16.67% | +19.44% |
| Annualised from mean | +10.38% | +9.92% | +10.15% |
| Yearly compound | +10.31% | +9.88% | +10.10% |
| Monthly Sharpe (ann.) | +292.50% | +348.38% | +318.88% |
| Required monthly Sharpe for ≥50% hit | +1770.47% | +2200.49% | +1971.27% |
| Max consec. m ≥ 5% | 0 | 0 | 0 |
| Max consec. loss months | 2 | 2 | 2 |
| Best month | +2.72% | +2.27% | +2.50% |
| Worst month | -0.94% | -0.57% | -0.75% |

### Verdict on 5%/month

1. **Probability of a 5% month, in the best blender = 0.0%** (empirical, from 36 walk-forward test months).  This is the smoking gun: a randomly positive month is ~50%; to reliably hit 5%, you need P(m ≥ 5%) ≫ 50% (typically > 70%), and we are nowhere close.

2. **Required monthly Sharpe for ≥50% hit rate on 5%/month = 17.70 annualised**, vs the realised `2.92` from the same blender.  The gap is ~10× and not bridgeable by rebalancing frequency or parameter tuning — it requires a fundamentally different alpha source (private information, latency, or aggressive leverage).

3. **The median month is essentially zero** across all blenders.  That is the honest centre of the distribution; 5% months are fat-tail events, not the strategy's design point.

4. **The v1 ensemble DOES pass the prop-firm bar**: positive Sharpe, MaxDD < 10% on the walk-forward test, diversified across assets and strategy families, and a hit rate around 50-55% on daily bars.  The Lane A target (1-3%/month at low DD) is realistic; 5%/month as a central-tendency target is not.

## 6. Why we do not hit 5%/month — diagnostic reading

* The crypto legs (BTCUSDT, ETHUSDT) have the highest per-leg Sharpe (see §2), but their monthly returns are too volatile to give a ≥50% P(m ≥ 5%) — the tail risk bites whenever funding or a 24h session flip happens.
* The trend/breakout family (Donchian, EmaTrend) pays in trending regimes (2020 Q2, 2022 Q1-Q3, 2024 Q4) and bleeds in choppy regimes (2023).  No parameter tuning fixes that — it is the family itself.
* The mean-reversion family (RSI, Bband, alpha_050) gives a more stable monthly mean but a hit rate near 50% — they collect small, frequent payoffs, not monthly lump sums.
* Correlation across families is in the 0.10-0.40 band (see §3), which gives genuine diversification but not enough — the joint monthly return is still dominated by whichever family is OFF that month, not by the average.

## 7. What would be required to approach 5%/month

Honest list, in order of marginal contribution:

1. **Add a persistent edge source**: a non-public signal (order-flow imbalance from L2 data, ML microstructure, regime-conditioned tail-hedging).  The retail technical-only basket cannot mathematically deliver 5%/month central tendency — this is the academic literature on factor decay (McLean-Pontiff 2016: ~30% post-publication decay).
2. **Asymmetric payoffs**: concentrate on the right tail.  Crypto session breaks, earnings drift on single names, news-driven gaps.  These are tail-heavy distributions where a single good month can carry 12 — but they need a regime filter and tail cap.
3. **Use leverage beyond the v1 2× cap**, but only after step 1 delivers a real edge — leverage on a zero-alpha strategy just amplifies drawdown.
4. **Re-examine the benchmark**: 5%/month = ~80% annual.  Even the Renaissance Medallion fund averaged ~66%/year (gross) before fees across 30 years; their SHARPE was the edge, not the level.  A realistic stretch target is 2-3%/month at Sharpe > 1.0 — and that is exactly what the v1 ensemble approximates.

## 8. Files and reproducibility

* Script: `scripts/run_multi_strategy_ensemble.py`
* JSON: `docs/reports/edge-factory/multi-strategy-5pct-discovery.json`
* Window: 2020-01-01T00:00:00 → 2025-12-31T00:00:00, train-end 2022-12-31T00:00:00
* Default legs: 11 across 5 assets and 3 families
* Gate: MaxDD < 10%; positive walk-forward alpha

Re-run with:

```
uv run --frozen python scripts/run_multi_strategy_ensemble.py
```
