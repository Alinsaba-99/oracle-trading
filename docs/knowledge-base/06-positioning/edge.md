# 06 Positioning — Edge Plausibility

> Valutazione critica per ogni COT/positioning signal.

## Edge summary

| Signal | Source | Edge | Free $0 | Orizzonte | Decay |
|---|---|---|---|---|---|
| Commercial hedger extremes | Asness 2013 | +3-5%/yr commodity deciles | ✅ CFTC weekly | 1-3m | basso |
| Smart Money Indicator (SMI) | Bhansali 2014 | long-or-flat +4-6%/yr | ✅ CFTC weekly | 1-3m | basso |
| Hedging pressure (De Roon 2000) | De Roon 2000 | R² 5-10% on 1-3m | ✅ CFTC weekly | 1-3m | medio |
| Open interest growth | Hong-Yogo 2012 | +2-3%/3m | ✅ CFTC weekly | 1-3m | medio |
| Broker-dealer risk aversion | Etula 2013 | +2-3%/3m | hard (need BDAI proxy) | 1-3m | medio |
| T-bill rate predict (Bessembinder-Chan) | Bessembinder 1992 | R² 5-10% commodity | ✅ FRED | 3-6m | medio |
| OVX variance risk premium oil | literature | R² 5% | ✅ CBOE OVX | 1-3m | medio |

## Verdetto edge

**Edge forte maintained**:
- **Bhansali SMI** — robusto a multiple testing (72/78 combinations significant at α=0.025). **Long-or-flat strategy beats trend-following**.
- **Asness commercial extremes** — top/bottom decile commodity portfolios +3-5%/yr.
- **De Roon hedging pressure** — R² 5-10% su 1-3m.

**Edge regime-dependent**:
- Commodity markets (energy + metals): edge più forte. Tend to have more informed commercial hedgers.
- Financial futures (Treasury + equity index): edge più debole. Less concentrated positioning.
- Crypto: NO COT report. Hard-blocked.

**Edge decayed post-2014**:
- Some COT signals decayed with disaggregated report attention. SMI maintained (Bhansali 2014 OOS).

## Cost-realism check

- **Trading costs**: weekly rebalance futures, ~50 trades/yr → ~0.5% slippage costs.
- **Tax**: futures 60/40 tax treatment (US) — 60% LT cap gains, 40% ST. Italian futures ~26% cap gains.
- **Net edge realistico**: +2-4%/yr post-cost su 5y. Sharpe 0.5-0.8.

## Validazione G5 (ADR-017)

Per promozione COT strategy:
- DSR ≥ 0.95 (con pochi test multipli)
- PBO < 0.5
- CPCV OOS Sharpe > 0.5
- 250+ paper sessions con pass-rate ≥ 90%

COT signals sono settimanali (low-frequency) → meno rumorosi di L2/intraday. Edge più stabile di short-term signals.
