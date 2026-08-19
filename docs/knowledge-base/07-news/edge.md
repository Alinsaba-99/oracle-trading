# 07 News automated — Edge Plausibility

> Valutazione critica per ogni news sentiment signal.

## Edge summary

| Signal | Source | Edge | Free $0 | Orizzonte | Decay |
|---|---|---|---|---|---|
| WSJ column pessimism (Tetlock 2007) | Tetlock 2007 | +1-2% weekly | ✅ (RSS + FinBERT) | 1-2w | medio |
| Dow Jones Newswires sentiment (Garcia 2013) | Garcia 2013 | +2-3% in recessions | ✅ (RSS) | 1-2w | basso (regime-dep) |
| Internet message board (Antweiler-Frank 2004) | Antweiler-Frank 2004 | predicts vol, marginal returns | ✅ (Reddit PRAW) | 1-3d | alto |
| Google Trends recession searches (Da 2015) | Da 2015 | +3-5% reversals | ✅ (pytrends) | 1-2w | medio |
| Seeking Alpha articles (Chen 2013) | Chen 2013 | +2-3% contrarian low sentiment | ✅ (RSS) | 1-2w | medio |
| IPO prospectus tone (Jegadeesh-Wu 2012) | Jegadeesh-Wu 2012 | +5% IPO underperf | ✅ (SEC EDGAR) | 6-12m | basso |
| News short-term (Heston 2015) | Heston 2015 | +1% 1-2d | ✅ (RSS) | 1-2d | alto (decayed by HFT) |
| Reddit WSB mentions | practitioners | +5-10%/1w on volume spike | ✅ (PRAW + ApeWisdom) | 1-7d | alto |
| StockTwits cashtag sentiment | practitioners | marginal | ✅ (StockTwits) | 1-5d | alto |
| SEC 8-K event detection | practitioners | +2-5%/1d on earnings/M&A | ✅ (SEC EDGAR FTS) | 1-5d | medio |

## Verdetto edge

**Edge forte e persistente**:
- Tetlock 2007 — RSS + FinBERT replication, maintained OOS.
- Garcia 2013 — regime-dependent (stronger in recessions).
- SEC 8-K event detection — earnings/M&A announcement effect.

**Edge debole**:
- Antweiler-Frank — predicts vol, marginal on returns.
- Heston-La-Poncin — 1-2d horizon decayed by HFT.

**Edge too long-horizon**:
- Jegadeesh-Wu IPO prospectus — 6-12m horizon, slow.
- Da 2015 Google Trends — 1-2w reversal signal.

**Edge regime-dependent**:
- News sentiment stronger in recessions (Garcia 2013).
- Reddit WSB edge concentrated in meme stocks (GME, AMC, etc).

## Regime dipendenza

News sentiment edge è:
- **Crisis regime amplification**: news pessimism stronger in 2008-2009, 2020-COVID, 2022-bear. Tetlock/Garcia both confirm.
- **Bull market decay**: news sentiment weak signal in extended bull (2017-2021).
- **Meme stock anomaly**: Reddit WSB edge concentrated in 2021-2023 meme cycle, less reliable now.

## Cost-realism check

- **Trading costs**: news trading è high-frequency (daily/weekly), 100-500 trades/yr → 0.5-1.5% slippage costs.
- **Tax**: same as equity (~26% IT capital gains).
- **Net edge realistico**: +1-3%/yr post-cost su 5y. Sharpe 0.3-0.6.

## Validazione G5 (ADR-017)

Per promozione news strategy:
- DSR ≥ 0.95 (con molti test multipli, threshold alto)
- PBO < 0.5
- CPCV OOS Sharpe > 0.5
- 250+ paper sessions con pass-rate ≥ 90%

News signals sono rumorosi + decayed → threshold più alto richiesto. Sentiment classifier (FinBERT vs LLM) calibration critical.
