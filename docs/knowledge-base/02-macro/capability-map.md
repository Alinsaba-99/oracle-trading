# 02 Macro — Capability Map per Oracle

> Cosa costruire prima in Oracle (edge > 0.5 + free data + stack esistente), cosa deferrire, cosa è hard-blocked.

## ✅ Già in Oracle

| Capability | File | Note |
|---|---|---|
| FRED VIX loader | `analytics/macro/fred.py:FREDClient` + `lane_d_vrp_backtest.py:_load_vix` | VIXCLS series only. Fallback yfinance ^VIX |

## 🔨 P1 — Implementare prossimo (edge forte + free data + stack ready)

### BL-KB-09: FRED series adapter esteso
- **Perché**: VIX è l'unica series usata. Servono 8+ series chiave (CPIAUCSL, GDP, UNRATE, DGS10, T10Y2Y, FEDFUNDS, PAYEMS, T5YIE).
- **Cosa**: estendere `analytics/macro/fred.py` con `fetch_series_bulk(series_ids)` + cache su `data/macro/fred/`.
- **Output**: Polars DataFrame per series, PIT filtered by publish_date.
- **Tempo**: ~1-2 giorni.
- **Costo**: $0 (FRED_API_KEY free email).

### BL-KB-10: ECB SDMX adapter
- **Perché**: euro-area rates, M3, HICP non disponibili in FRED. ECB ha API RESTful free.
- **Cosa**: `analytics/macro/ecb.py:ECBClient` con `fetch_series(flow_ref, key_desc)` → es. IRS.M.U2_EUR.LB.A.1Y.A.R.GR.BAS.
- **Output**: Polars DataFrame.
- **Tempo**: ~2-3 giorni.
- **Costo**: $0.

### BL-KB-13: Yield curve inversion signal
- **Perché**: 12-18m recession predict, edge robusto maintained 50y.
- **Cosa**: `analytics/strategy/catalog/macro.py:YieldCurveSignal` con:
  - 10Y-2Y spread (T10Y2Y from FRED)
  - Near-term forward spread (Engstrom-Sharpe 2019)
  - Output: bullish (>0.5%), neutral (0-0.5%), bearish (inverted)
- **Output**: regime indicator per asset allocation overlay.
- **Tempo**: ~1 giorno.

### BL-KB-12: Output gap signal (Cooper-Priestley 2009)
- **Perché**: R² 5-10% su 1-year equity returns, edge persistente.
- **Cosa**: `analytics/strategy/catalog/macro.py:OutputGapSignal` con:
  - Industrial production (INDPRO from FRED)
  - HP filter per trend extraction (`statsmodels.tsa.filters.hp_filter`)
  - Output gap = log(actual) - log(trend)
- **Output**: long when gap negative, reduce when positive.
- **Tempo**: ~2 giorni.

### BL-KB-15: Growth × Inflation regime classifier
- **Perché**: Bridgewater All Weather pattern. Asset class rotation per regime.
- **Cosa**: `analytics/strategy/catalog/macro.py:RegimeClassifier` con:
  - Growth signal: ΔGDP YoY (FRED GDP) or industrial production
  - Inflation signal: ΔCPIAUCSL YoY
  - 4 regimes: growth↑inflation↑, growth↑inflation↓, growth↓inflation↑, growth↓inflation↓
  - Output: regime label + asset class weights (stocks/bonds/commodities/cash)
- **Output**: macro overlay per Lane A/B/C allocation.
- **Tempo**: ~3-5 giorni.

## 🔨 P2 — Implementare per validazione G5

### BL-KB-14: FOMC drift signal (Lucca-Moench 2015)
- **Perché**: +33bps/day pre-FOMC storico, +10-15bps OOS 2015+.
- **Cosa**: `analytics/strategy/catalog/macro.py:FOMCDriftSignal` con:
  - FOMC meeting calendar from federalreserve.gov
  - Long SPY 24h before FOMC, flat altri giorni
- **Data**: FOMC calendar (free) + yfinance SPY.
- **Tempo**: ~2-3 giorni.

### BL-KB-16: TIPS breakeven trading
- **Perché**: +2-3%/yr storico, +1-2%/yr OOS. Inflation regime overlay.
- **Cosa**: `analytics/strategy/lane_e_tips.py:TIPSBreakevenStrategy` con:
  - 5y breakeven = DGS5 - DFII5 (FRED)
  - Realized CPI from CPIAUCSL
  - Long TIPS when breakeven < realized, short when breakeven > realized
- **Tempo**: ~3-5 giorni.

### BL-KB-11: BIS data adapter
- **Perché**: international banking statistics, cross-border flows. Per macro globale.
- **Cosa**: `analytics/macro/bis.py:BISClient` con fetch da `data.bis.org`.
- **Tempo**: ~2 giorni.

### BL-KB-17: BLS + BEA adapters
- **Perché**: employment + GDP releases official source. FRED redistributes ma BLS/BEA hanno release più tempestive.
- **Cosa**: `analytics/macro/bls.py:BLSClient`, `analytics/macro/bea.py:BEAClient`.
- **Tempo**: ~2-3 giorni.

### BL-KB-18: Macro PCA factor (Ludvigson-Ng 2009)
- **Perché**: 21-26% variance explained su 1y bond returns.
- **Cosa**: `analytics/strategy/catalog/macro.py:MacroPCASignal` con:
  - Bulk download 132 FRED series
  - PCA via scikit-learn (8 factors)
  - Use F1 (real activity) + F2 (interest rates) as signals
- **Tempo**: ~5-7 giorni (richiede FRED adapter esteso BL-KB-09).

## 🔄 P3 — Deferrire

- **CPI surprise straddle** — intraday only, decayed by HFT. Skip MVP.
- **Nonfarm payrolls surprise** — intraday only, decayed. Skip MVP.
- **Taylor rule deviation** — noisy real-time data, low signal-to-noise. Skip MVP.
- **Trade balance → USD** — too noisy, hard to isolate. Skip MVP.

## ❌ Hard-blocked (paywalled)

- **Bloomberg economic calendar** — $24k/yr. Alternative: FRED + BLS/BEA calendars (free).
- **Refinitiv real-time macro** — $1.8k/mo. Alternative: FRED (slight delay, free).

## Sequenza implementazione raccomandata

```
BL-KB-09 FRED adapter esteso   (~1-2g) ← unlock 8+ series
BL-KB-13 Yield curve signal    (~1g)   ← semplice, edge forte
BL-KB-12 Output gap signal     (~2g)   ← HP filter + FRED INDPRO
BL-KB-15 Regime classifier     (~3-5g) ← macro overlay
BL-KB-10 ECB adapter           (~2-3g) ← euro-area
BL-KB-14 FOMC drift signal    (~2-3g) ← calendar-driven
BL-KB-16 TIPS breakeven        (~3-5g) ← inflation regime
BL-KB-11 BIS adapter           (~2g)   ← international
BL-KB-17 BLS+BEA adapters      (~2-3g) ← releases
BL-KB-18 Macro PCA factor      (~5-7g) ← Ludvigson-Ng
```

Totale: **~23-33 giorni** per completare P1+P2 macro.

## Prossimo step

Dopo P1+P2, test end-to-end:
- Macro regime classifier su 1990-2025 → simulate asset rotation (stocks/bonds/commodities/cash per regime)
- Output gap signal su 1990-2025 → long-only equity timing overlay
- FOMC drift signal → event-driven backtest

**Target**: +1-3%/yr post-cost Sharpe 0.3-0.5 su macro overlay. Combina con Lane B fundamental (Sharpe 0.93 attuale) per ensemble Sharpe ~1.0+.
