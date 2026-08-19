# 10 Seasonal — Capability Map per Oracle

> Cosa costruire in Oracle (edge robusto + free data + stack esistente).

## ✅ Già in Oracle

| Capability | File | Note |
|---|---|---|
| Lane B backtester | `analytics/strategy/lane_b_backtester.py` | Fundamental equity, seasonal overlay candidate |
| FRED VIX loader | `analytics/macro/fred.py:FREDClient` | Macro context |
| Dukascopy lake | 21 symbols cached | Global data |

## 🔨 P1 — Implementare prossimo (edge robusto + free data)

### BL-KB-74: Halloween signal (Sell in May)
- **Perché**: Bouman-Jacobsen 2002, 323y robust.
- **Cosa**: `analytics/strategy/catalog/seasonal.py:HalloweenSignal` con:
  - Long SPY Nov 1 to April 30
  - Flat May 1 to Oct 31
  - Output: regime label (in-market vs out-market)
- **Tempo**: ~1 giorno.

### BL-KB-75: Santa Claus rally signal
- **Perché**: +1.3% avg, 76% positive since 1950.
- **Cosa**: `analytics/strategy/catalog/seasonal.py:SantaRallySignal` con:
  - Last 5 trading days of December + first 2 of January
  - Long SPY only in window, flat otherwise
- **Tempo**: ~1 giorno.

### BL-KB-76: Turn of month signal
- **Perché**: TOM (7 days) ~50% of total monthly returns.
- **Cosa**: `analytics/strategy/catalog/seasonal.py:TurnOfMonthSignal` con:
  - Long last 4 trading days of month + first 3 of next month
  - Flat otherwise
- **Tempo**: ~1 giorno.

### BL-KB-77: Calendar anomaly composite signal
- **Perché**: combo Halloween + Santa + TOM + January (decayed, low weight) → stronger.
- **Cosa**: `analytics/strategy/catalog/seasonal.py:CalendarCompositeSignal` con:
  - Inputs: Halloween (BL-KB-74) + Santa Claus (BL-KB-75) + TOM (BL-KB-76)
  - Weights: 50% Halloween + 25% Santa + 25% TOM
  - Output: composite seasonal score [-1, +1] (in/out of market)
- **Tempo**: ~1-2 giorni.

## 🔨 P2 — Implementare per ensemble

### BL-KB-78: Lane I seasonal overlay
- **Perché**: nuova lane per seasonal-timing overlay.
- **Cosa**: `analytics/strategy/lane_i_seasonal.py:SeasonalOverlayStrategy` con:
  - Universe: SPY + Dukascopy forex majors + crypto majors
  - Signal: CalendarCompositeSignal (BL-KB-77)
  - Long-or-flat per Bouman-Jacobsen methodology
  - Risk: 1% equity per asset, max 5 concurrent
- **Target**: Sharpe > 0.5 su 1990-2025.
- **Tempo**: ~3-5 giorni.

## 🔄 P3 — Deferrire

- Presidential cycle (small sample)
- Holiday effect (marginal)
- January effect (decayed)

## ❌ Hard-blocked (paywalled)

- Bloomberg seasonal analytics — $24k/yr
- Refinitiv calendar — $1.8k/mo
- Stock Trader's Almanac premium — $200/yr

## Sequenza implementazione raccomandata

```
BL-KB-74 Halloween signal     (~1g)
BL-KB-75 Santa Claus signal   (~1g)
BL-KB-76 Turn of month        (~1g)
BL-KB-77 Composite seasonal  (~1-2g)
BL-KB-78 Lane I overlay       (~3-5g)
```

Totale: **~7-10 giorni** per seasonal P1+P2.

## Prossimo step

Dopo P1+P2:
1. Backtest Lane I su 1990-2025 con Halloween + Santa + TOM
2. DSR/PBO/CPCV validation (dominio 03)
3. **Target**: Sharpe > 0.5 on Lane I. Combina con Lane B + macro overlay per ensemble.
