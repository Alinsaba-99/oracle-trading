# 08 Intermarket — Edge Plausibility

> Valutazione critica per ogni intermarket signal.

## Edge summary

| Signal | Source | Edge | Free $0 | Orizzonte | Decay |
|---|---|---|---|---|---|
| Murphy 3 correlations | Murphy 1991 | regime-dep +3-5%/yr | ✅ yfinance | 3-12m | basso |
| Stock-bond flight to quality | Baur-Lucey 2010 | asymmetric in crises +5-8% | ✅ yfinance SPY/AGG | 1-3m crises | basso |
| Stock-bond regime break | 2022 experience | detection +2-3% avoid 60/40 | ✅ yfinance | 1-3m | basso |
| Commodity-currency (DXY vs oil) | literature | inverse -0.3 to -0.5 | ✅ yfinance DXY/USO | 1-3m | basso |
| Sector rotation (Stovall) | Sam Stovall | +3-5%/yr top decile sector | ✅ yfinance sector ETFs | 6-9m | basso |
| Credit spread (Baa-Aaa) | Asness 2013 | predict equity +2-3%/yr | ✅ FRED BAA_AAA | 3-12m | basso |
| HY spread predict equity | Collin-Dufresne 2001 | high HY spread → low equity | ✅ FRED BAMLH0A0HYM2 | 3-6m | medio |
| Bitcoin safe haven | fibo-crypto 2026 | NON safe haven, marginal | ✅ yfinance BTC-USD | n/a | n/a (rischio asset) |
| 10y-2y yield curve | dominio 02 | 12-18m recession predict | ✅ FRED T10Y2Y | 12-18m | basso |

## Verdetto edge

**Edge forte maintained**:
- Murphy 3 correlations — regime-dep ma persistenti.
- Baur-Lucey flight-to-quality — asymmetric in crises (concentrato in drawdowns).
- Stovall sector rotation — 6-9m lead, robusto dal 1948.
- Baa-Aaa credit spread — recession predict, maintained.

**Edge decayed**:
- 2022 stock-bond positive correlation broke Murphy framework. Re-normalized 2024-2026 ma con caveats.

**Edge non-edge**:
- Bitcoin safe haven — debunked. BTC = risk asset, no flight-to-quality.

## Regime dipendenza

Intermarket edge è:
- **Regime-amplified**: flight-to-quality only in crises (1998 LTCM, 2008 GFC, 2020 COVID, 2022 inflation regime). Normal regime → bonds hedge equities, correlation -0.3.
- **Inflation regime flip**: 2022 inflation↑ → stock-bond correlation +0.5. 60/40 broke.
- **Sector rotation lead**: 6-9m anticipate business cycle.

## Cost-realism check

- **Trading costs**: intermarket è low-frequency (quarterly/annual rebalance), 20-50 trades/yr → marginal costs.
- **Tax**: ETFs tax-efficient (most LT cap gains).
- **Net edge realistico**: +1-3%/yr post-cost su 5y. Sharpe 0.3-0.6.

## Validazione G5 (ADR-017)

Per promozione intermarket strategy:
- DSR ≥ 0.95 (con pochi test multipli)
- PBO < 0.5
- CPCV OOS Sharpe > 0.5
- 250+ paper sessions con pass-rate ≥ 90%

Intermarket edge è meno rumoroso di L2/news ma più lento (3-12m horizon). Combina con Lane B + macro overlay per ensemble.
