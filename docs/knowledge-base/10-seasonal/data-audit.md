# 10 Seasonal — Data Audit (free $0 verified 2026-08-17)

> Regola hard: $0/mo per dati. Vedi ADR-020.

## Fonti seasonal free verificate

| Fonte | Coverage | Format | API Key | Note |
|---|---|---|---|---|
| **yfinance** | US stocks + ETFs 1993+ | pandas DataFrame | nessuna | For all seasonal signals (daily + intraday last 30d) |
| **Dukascopy lake** | 2003+ forex/crypto/commodities | parquet cached | nessuna | Higher resolution for global seasonal |
| **FRED (economic calendar)** | 1990+ | JSON | `FRED_API_KEY` | For presidential cycle + business cycle dating |
| **NBER business cycle dating** | 1854+ | CSV | nessuna | https://www.nber.org/research/data/us-business-cycle-expansions-and-contractions |

## Capabilities Oracle esistenti

- ✅ Lane B backtester (fundamental equity, seasonal overlay candidate)
- ✅ FRED VIX loader
- ✅ Dukascopy lake cached

## Gap dichiarati

1. **Halloween signal** NON implementato. TODO BL-KB-74.
2. **Santa Claus rally signal** NON implementato. TODO BL-KB-75.
3. **Turn of month signal** NON implementato. TODO BL-KB-76.
4. **Calendar anomaly composite** NON implementato. TODO BL-KB-77.

## Cap da NON usare

| Fonte | Perché esclusa | Alternativa free |
|---|---|---|
| Bloomberg holiday calendar | $24k/yr | NBER + FRED calendars |
| Refinitiv seasonal analytics | $1.8k/mo | yfinance + custom signals |
| Stock Trader's Almanac Premium | $200/yr | Wikipedia + Yale Hirsch references |

## Reference implementations free

- **Quantpedia**: https://quantpedia.com/strategies — calendar anomaly descriptions free
- **StockCharts**: https://chartschool.stockcharts.com — seasonal charting tools
- **Yale Hirsch Stock Trader's Almanac**: $20 book — reference manual
