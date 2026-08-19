# 05 Sentiment — Edge Plausibility

> Valutazione critica per ogni sentiment signal.

## Edge summary

| Signal | Source | Edge | Free $0 | Orizzonte | Decay |
|---|---|---|---|---|---|
| Brown-Cliff sentiment (II + closed-end) | Brown-Cliff 2005 | +3-5%/yr | ✅ | 1-3y | basso |
| Baker-Wurgler composite | BW 2006 | +5-8%/yr on small+growth | ✅ (monthly data free) | 1-3y | basso |
| CNN Fear&Greed extreme | CNN since 2011 | +4-6%/3m post extreme fear | ✅ scraper | 1-3m | medio |
| CBOE P/C ratio extreme | CBOE historical | +2-3%/1m contrarian | ✅ CSV free | 1-4w | medio |
| AAII survey extreme | AAII since 1987 | +3-5%/6m contrarian | ✅ free weekly | 3-12m | basso |
| VIX mean reversion | Whaley 2000 | +2-4%/1m post VIX > 30 | ✅ FRED | 1-3m | basso |
| VRP predict | Bollerslev-Tauchen-Zhou 2009 | R² 10-17% quarterly | ✅ FRED VIX + realized vol | 1-3m | basso |
| StockTwits cashtag | practitioners | marginal | ✅ free real-time | 1-5d | alto |
| Reddit mentions | ApeWisdom | +5-10%/1w on volume spike | ✅ free | 1-7d | alto |
| Google Trends retail attention | practitioners | +3-5%/1-2m | ✅ pytrends | 1-2m | medio |

## Verdetto edge

**Sentiment edge forte su orizzonti lunghi (Brown-Cliff + Baker-Wurgler 1-3y)**, medio su orizzonti brevi (VIX + CNN F&G + CBOE P/C 1-3m), debole su social real-time (StockTwits + Reddit 1-7d).

**Edge persistente**:
- **VRP (Bollerslev-Tauchen-Zhou 2009)** — R² 10-17% quarterly, seminale. **Già in Lane D Oracle**, ma Lane D backtest storico mostra Sharpe -0.08 (edge assente nella implementazione attuale — vedi memoria `lane-d-vrp-backtest-real-2026-08-17`). Da fixare con regime filter + tail cap.
- **AAII contrarian extremes** — since 1987, lead 6m, maintained.
- **CNN F&G extreme** — 5y stats mostrano Extreme Fear < 10 = 16 volte, con rebound medio +5-8% nei 3m successivi.

**Edge contestato**:
- **Social real-time (StockTwits + Reddit)** — signal noise alto, HFT decayed, regime-dependent (meme stocks only).

**Edge too long-horizon**:
- **Brown-Cliff + Baker-Wurgler 1-3y** — slow, low-frequency trading. Overlay per asset allocation, non standalone.

## Regime dipendenza

Sentiment edge è:
- **Crisis regime amplification**: AAII extreme bear (>50%) → +8% 6m future returns post 2008, 2020, 2022. Sentiment massimo → reversal massimo.
- **Bull market decay**: CNN F&G greed (75+) → -3% next 3m in 2017-2021 bull, meno utile in extended bull.
- **Crypto-specific**: sentiment proxy (Fear & Greed crypto index da alternative.me) più volatile, edge maggiore su intraday.

## Cost-realism check

- **Trading costs**: sentiment trading è low-frequency (quarterly/monthly + weekly extremes), 20-50 trades/yr → marginal costs.
- **Tax**: same as equity (~26% IT capital gains).
- **Net edge realistico**: +1-3%/yr post-cost su 5y per VRP + F&G + AAII combo. Sharpe 0.3-0.5.

## Validazione G5 (ADR-017)

Per promozione sentiment strategy serve:
- DSR ≥ 0.95 (con pochi test multipli, threshold più basso di L2)
- PBO < 0.5
- CPCV OOS Sharpe > 0.5
- 250+ paper sessions con pass-rate ≥ 90%

Sentiment signals sono meno rumorosi di L2 order flow ma meno edge di fundamental equity. Edge concentrato in regime extremes, non continuous signals.
