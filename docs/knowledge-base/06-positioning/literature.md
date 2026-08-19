# 06 Positioning — Literature Review

> Fonti: Tavily API (advanced) 2026-08-17. URL verified.

## 1. COT report fundamentals

### CFTC Commitments of Traders

- **Source**: CFTC (Commodity Futures Trading Commission), US federal agency.
- **Publication**: weekly Friday, data as of Tuesday close (3-day lag).
- **3 categories**:
  1. **Commercial** (hedgers): producers/users of commodity using futures to hedge. "Smart money".
  2. **Non-commercial** (large speculators): hedge funds, CTAs, money managers.
  3. **Nonreportable** (small speculators): retail.
- **Reports**:
  - Legacy (futures only): 1986+
  - Legacy (futures + options combined)
  - Supplemental (financial traders, 13 select markets)
  - Disaggregated (more granular: Producer/Merchant/Processor; Swap Dealer; Managed Money; Other Reportables)
  - TFF (Traders in Financial Futures): Dealer/Asset Manager/Levered Funds/Other Reportables

### Historical archives

- **Bulk historical compressed**: https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed (1986+)
- **Python lib `cot_reports`** (NDelventhal): https://github.com/NDelventhal/cot_reports
  - `cot_hist()` — 1986-2016 bulk
  - `cot_year()` — single year
  - `cot_all()` — complete archive
  - Free, MIT license

## 2. Smart money + edge

### Asness 2013 — Commercial hedgers positioning

**Paper**: Asness, C. (2013). *Smart Money*. AQR research note.

- **Hypothesis**: commercial hedgers ("smart money") better informed on commodity fundamentals.
- **Result**: extreme commercial net long positions → high future returns in commodities. Extreme net short → low future returns.
- **Edge**: ~+3-5%/yr on top decile vs bottom decile commodity portfolios.

### Bhansali 2014 — Smart Money Indicator (SMI)

**Paper**: Bhansali, V. (2014). *The Smart Money Indicator: A New Risk Management Tool*. Alpha Architect.

- **SMI formula**: relative sentiment = (non-commercial net - commercial net) / open interest.
  - SMI positive → non-commercial (speculators) net long vs commercial.
  - SMI negative → non-commercial net short.
- **Strategy**: long-or-flat when SMI positive, flat when negative.
- **Result**: 72 of 78 parameter combinations significant at α=0.025, 64 at α=0.01, 38 at α=0.001 (robust to data snooping).
- **Edge**: SMI is NOT trend following. It's a positioning-based market timing signal.
- **Limitation**: imperfect timing over discrete intervals, but reliable intermediate-term (1-3m).

### De Roon et al 2000 — Hedging pressure

**Paper**: De Roon, F., Nijman, T., Veld, C. (2000). *Hedging Pressure Anomalies in Futures Markets*.

- **Hedging pressure** = net position of commercials (hedgers).
- **Result**: hedging pressure forecasts commodity futures returns.
- **Edge**: R² ~5-10% on 1-3m horizon.

### Hong-Yogo 2012 — Open interest

**Paper**: Hong, H., Yogo, M. (2012). *What does futures market interest tell us about the macroeconomy and asset prices?*

- **Open interest growth** → commodity returns.
- **Edge**: high open interest growth → high future returns. Complements hedging pressure.

### Etula 2013 — Broker-dealer risk aversion

**Paper**: Etula, E. (2013). *Risk Appetite of Broker-Dealers and Commodity Returns*.

- **Broker-dealer risk aversion** proxy → commodity returns.
- **Mechanism**: when BDs are risk-averse → commodity prices fall.

### Bessembinder-Chan 1992 — Commodity predictability

**Paper**: Bessembinder, H., Chan, K. (1992). *Time-Varying Risk Premia and Forecastable Commodity Returns*.

- **Predictors**: T-bill rate, dividend yield, default spread.
- **T-bill strongest** in-sample predictor.

## 3. Cap summary

**Edge forte e free**:
- CFTC COT weekly free (1986+)
- Smart Money Indicator (Bhansali 2014) — robust to data snooping
- Hedging pressure (De Roon 2000) — R² 5-10% on 1-3m
- Open interest (Hong-Yogo 2012) — complements
- Commercial extremes (Asness 2013) — reversal signal

**Edge decay**:
- Post-2014 COT reform with disaggregated data → some signals decayed due to attention.

**Edge hard-blocked**:
- Real-time futures positioning (post-COT data) paywalled at Refinitiv/Bloomberg.
- CFTC weekly + 3-day lag → not tradable intraday.
