# 06 Positioning — Data Audit (free $0 verified 2026-08-17)

> Regola hard: $0/mo per dati. Vedi ADR-020.

## Fonti COT free verificate

| Fonte | Coverage | Format | API Key | Limit | Note |
|---|---|---|---|---|---|
| **CFTC COT bulk historical** | 1986-2026 weekly | CSV compressed (.tar.gz) | nessuna | nessuna | https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed |
| **CFTC COT current year** | 2025-2026 weekly | CSV | nessuna | rate-limit soft | https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm |
| **`cot_reports` Python lib** | 1986+ all reports | pandas DataFrame | nessuna | pip install | https://github.com/NDelventhal/cot_reports. MIT license. Handles legacy + disaggregated + TFF |
| **CFTC SMS API** | real-time | JSON | nessuna | rate-limited | https://publicreporting.cftc.gov/rest-api/press/v1.0/. Programmatic COT queries |

## COT reports supported by `cot_reports` lib

1. **Legacy Futures-only** (`FUT`): 1986+
2. **Legacy Futures-and-Options Combined** (`FOC`): 1995+
3. **Supplemental Futures-and-Options Combined** (`SUP`): 2007+ (13 financial markets)
4. **Disaggregated Futures-only** (`DIS`): 2006+ (more granular: Producer/Swap Dealer/Managed Money/Other)
5. **Disaggregated Futures-and-Options Combined** (`DIS_FOC`): 2009+
6. **Traders in Financial Futures (TFF) Futures-only** (`TFF`): 2009+
7. **TFF Futures-and-Options Combined** (`TFF_FOC`): 2009+

## Capabilities Oracle esistenti

- ❌ **No COT adapter** in Oracle. TODO BL-KB-48.
- ✅ Dukascopy forex lake (legacy) cached in Oracle.

## Gap dichiarati

1. **COT adapter NON implementato** — `cot_reports` lib non integrato. TODO BL-KB-48.
2. **Smart Money Indicator calculator** NON implementato. TODO BL-KB-49.
3. **Hedging pressure signal** NON implementato (De Roon 2000). TODO BL-KB-50.
4. **Open interest signal** NON implementato (Hong-Yogo 2012). TODO BL-KB-51.
5. **Lane G COT positioning strategy** NON implementata. TODO BL-KB-52.

## Cap da NON usare (paywalled)

| Fonte | Perché esclusa | Alternativa free |
|---|---|---|
| Refinitiv real-time COT | $1.8k/mo | CFTC weekly (3-day lag) |
| Bloomberg positioning | $24k/yr | CFTC weekly |
| CME Live COT | paid | CFTC weekly |
| TradingVolume.com | $50/mo | CFTC + cot_reports lib |
| QuikStrike COT | paid | CFTC + cot_reports lib |

## Future markets covered by COT

**Commodities** (legacy + disaggregated): ES, NQ, YM (equity index futures), CL, NG, HO, RB (energy), GC, SI, HG, PL (metals), ZB, ZN, ZF, ZT (rates), 6 currencies (DX), agricultural (corn, soy, wheat, cattle, hogs, coffee, sugar, cocoa, cotton).

**Financials** (TFF): US Treasury bonds, S&P 500 E-mini, NASDAQ 100, Russell 2000, DJIA, Euro FX, Japanese Yen, British Pound, Swiss Franc, Canadian Dollar, Australian Dollar, Mexican Peso, Eurodollar.

**Crypto**: NO COT report (CFTC non pubblica ancora crypto COT). Use Binance Vision + Etherscan for crypto positioning (see dominio 11 on-chain).

## Reference implementations free

- **cot_reports lib**: https://github.com/NDelventhal/cot_reports — top Python wrapper
- **CFTC SMS API**: https://publicreporting.cftc.gov/rest-api/press/v1.0/ — official REST
- **Alpha Architect Bhansali 2014 replication**: https://alphaarchitect.com/relative-sentiment-a-unique-market-timing-tool-that-isnt-trend-following
