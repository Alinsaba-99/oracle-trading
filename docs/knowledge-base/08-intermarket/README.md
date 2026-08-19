# Dominio 08 — Intermarket / 4 asset-class

> Knowledge base Oracle — studio approfondito 2026-08-17 via Tavily API.

## Sintesi esecutiva

L'analisi intermarket è **framework classico** (Murphy 1991) con edge documentato:

1. **Murphy 1991** — *Trading with Intermarket Analysis*. 4 asset-class: stocks, bonds, commodities, currencies. Tre relazioni chiave:
   - Stocks ↔ Bonds: negative correlation in normal regime, positive in inflation regime (2022 flip)
   - Bonds ↔ Commodities: inverse (rates up → commodities down)
   - Commodities ↔ USD: inverse (strong dollar → commodities cheaper)
2. **Stock-bond correlation regime** (Baur-Lucey 2010): flight-to-quality in crises → negative. 2022 Fed hiking cycle → positive. Re-normalization 2024-2026.
3. **Baur-Lucey 2010** — gold as safe haven, negative correlation to stocks + bonds during crises (4.6% US crashes coincide con US bond booms).
4. **Commodity-currency** — DXY strength inversely correlates oil/gold/copper. CAD, AUD, BRL = commodity currencies.
5. **Bitcoin safe haven debate** — fibo-crypto research 2026: BTC correlation with Nasdaq/tech increased since 2020. NOT a gold proxy. Risk asset, not safe haven.
6. **Sector rotation** (Sam Stovall): 4 stages business cycle (expansion, peak, contraction, recovery). Lead time 6-9m. Tech early expansion, energy/materials peak, utilities/staples/healthcare contraction, financials recovery.
7. **Credit spread predict equity** (Asness 2013): Baa-AAA spread predicts equity returns. High spread → low future equity returns.

**Free data sources**:
- yfinance ETF cross-asset: SPY (stocks), AGG/IEF (bonds), DBC (commodities), UUP (USD), GLD (gold), USO (oil)
- Dukascopy lake (forex) cached Oracle 21 symbols
- FRED for spreads: BAA_AAA, T10YIE, BAMLH0A0HYM2

**Cap to build Oracle**:
1. Cross-asset correlation matrix calculator (rolling 60d/120d/252d)
2. Sector rotation signal (4-stage business cycle classifier)
3. Credit spread signal (Baa-Aaa)
4. Flight-to-quality detector (stock-bond correlation breakdown)
5. Commodity-currency pair signal (DXY + oil/gold/copper)

Vedi [literature.md](literature.md), [data-audit.md](data-audit.md), [edge.md](edge.md), [capability-map.md](capability-map.md).
