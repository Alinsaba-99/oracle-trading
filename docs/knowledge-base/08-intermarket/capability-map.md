# 08 Intermarket — Capability Map per Oracle

> Cosa costruire in Oracle (edge > 0.5 + free data + stack esistente).

## ✅ Già in Oracle

| Capability | File | Note |
|---|---|---|
| Dukascopy forex lake (21 symbols) | `data/lake/normalized/symbol=EURUSD/...` | Cached 1m+5m+1h+1d |
| Lane B backtester | `analytics/strategy/lane_b_backtester.py` | Sharpe 0.93 fundamental equity |
| FRED VIX loader | `analytics/macro/fred.py:FREDClient` | VIXCLS series |

## 🔨 P1 — Implementare prossimo (edge forte + free data)

### BL-KB-61: Cross-asset correlation matrix calculator
- **Perché**: Murphy 1991 framework. Free yfinance ETFs.
- **Cosa**: `analytics/strategy/catalog/intermarket.py:CrossAssetCorrelation` con:
  - Universe: SPY, AGG, DBC, UUP, GLD, USO
  - Rolling correlation: 60d, 120d, 252d
  - Output: matrix per date + historical series
- **Tempo**: ~2-3 giorni.
- **Costo**: $0.

### BL-KB-62: Sector rotation signal (Stovall 4-stage)
- **Perché**: Sam Stovall 6-9m lead, robusto 1948+.
- **Cosa**: `analytics/strategy/catalog/intermarket.py:SectorRotationSignal` con:
  - Universe: SPDR sector ETFs (XLY, XLK, XLI, XLE, XLB, XLU, XLV, XLP, XLF)
  - Stage classifier: relative performance + business cycle indicators (FRED GDP, INDPRO, unemployment)
  - Output: stage label (Early Expansion, Peak, Contraction, Recovery) + sector weights
- **Tempo**: ~3-5 giorni.

### BL-KB-63: Credit spread signal
- **Perché**: Asness 2013 Baa-Aaa predict equity. FRED free.
- **Cosa**: `analytics/strategy/catalog/macro.py:CreditSpreadSignal` con:
  - Baa-Aaa spread (FRED BAA_AAA)
  - HY spread (FRED BAMLH0A0HYM2)
  - High spread → defensive positioning (low equity, high bond)
  - Low spread → aggressive (high equity)
- **Tempo**: ~2 giorni.

### BL-KB-64: Flight-to-quality detector
- **Perché**: Baur-Lucey 2010. 4.6% US stock crashes coincide US bond booms.
- **Cosa**: `analytics/strategy/catalog/intermarket.py:FlightToQualityDetector` con:
  - Stock-bond rolling correlation 252d
  - Detect correlation breakdown (negative → positive = stress signal)
  - Output: stress flag → switch to defensive bonds
- **Tempo**: ~1-2 giorni.

### BL-KB-65: Commodity-currency pair signal
- **Perché**: DXY + oil/gold/copper inverse. CAD/AUD commodity currencies.
- **Cosa**: `analytics/strategy/catalog/intermarket.py:CommodityCurrencySignal` con:
  - Inputs: DXY (UUP), oil (USO), gold (GLD), copper (CPER), CAD, AUD
  - Signal: divergence DXY vs commodities → mean reversion
- **Tempo**: ~2-3 giorni.

### BL-KB-66: Bitcoin regime classifier
- **Perché**: fibo-crypto 2026 research. BTC is risk asset, not safe haven.
- **Cosa**: `analytics/strategy/catalog/intermarket.py:BitcoinRegimeClassifier` con:
  - BTC correlation with Nasdaq (rolling 252d)
  - BTC correlation with gold (rolling 252d)
  - Regime: BTC Nasdaq correlation > 0.5 = risk-on; < 0.3 = decoupling
- **Tempo**: ~1-2 giorni.

## 🔨 P2 — Implementare per ensemble

### BL-KB-67: Intermarket composite signal
- **Perché**: combinare 6 signals → stronger composite.
- **Cosa**: `analytics/strategy/catalog/intermarket.py:CompositeIntermarketSignal` con:
  - Inputs: correlation matrix (BL-KB-61) + sector rotation (BL-KB-62) + credit spread (BL-KB-63) + flight-to-quality (BL-KB-64) + commodity-currency (BL-KB-65) + BTC regime (BL-KB-66)
  - Output: regime label + asset class weights
- **Tempo**: ~3-5 giorni.

### BL-KB-68: Lane H intermarket rotation strategy
- **Perché**: nuova lane per asset allocation macro overlay.
- **Cosa**: `analytics/strategy/lane_h_intermarket.py:IntermarketRotationStrategy` con:
  - Universe: SPY, AGG, DBC, UUP, GLD, USO + 11 SPDR sectors
  - Signal: CompositeIntermarketSignal (BL-KB-67)
  - Rebalance: quarterly
  - Risk: 5% equity per asset, max 8 concurrent
- **Target**: Sharpe > 0.6 su 2003-2025.
- **Tempo**: ~5-7 giorni (depends on BL-KB-61..67).

## 🔄 P3 — Deferrire

- **Cross-asset futures real-time** — paywalled Refinitiv. ETFs via yfinance sufficient.
- **International cross-asset (EU + Japan + EM)** — yfinance covers some, defer.

## ❌ Hard-blocked (paywalled)

- Bloomberg cross-asset — $24k/yr
- Refinitiv cross-asset — $1.8k/mo
- ICE Data Services — $5k+/yr
- FactSet — enterprise

## Sequenza implementazione raccomandata

```
BL-KB-61 Cross-asset correlation  (~2-3g)
BL-KB-62 Sector rotation (Stovall) (~3-5g)
BL-KB-63 Credit spread signal     (~2g)
BL-KB-64 Flight-to-quality detect (~1-2g)
BL-KB-65 Commodity-currency pair  (~2-3g)
BL-KB-66 Bitcoin regime           (~1-2g)
BL-KB-67 Composite intermarket    (~3-5g)
BL-KB-68 Lane H rotation          (~5-7g)
```

Totale: **~19-29 giorni** per completare P1+P2 intermarket.

## Prossimo step

Dopo P1+P2:
1. Backtest Lane H su 2003-2025 con ETFs cross-asset
2. DSR/PBO/CPCV validation (dominio 03)
3. **Target**: Sharpe > 0.6 on Lane H. Combina con Lane B (fundamental, Sharpe 0.93) + Lane G (COT positioning, ~0.7) per ensemble.
