# Dominio 11 — On-chain / crypto

> Knowledge base Oracle — studio approfondito 2026-08-17 via Tavily API.
> **Edge forte + free data** per crypto.

## Sintesi esecutiva

L'analisi on-chain è **edge documentato** per crypto, dati largely free:

1. **MVRV ratio** (Market Value / Realized Value): > 3.5 = market top, < 1.0 = market bottom. Standard crypto valuation metric.
2. **NVT ratio** (Network Value / Transactions): "P/E ratio of crypto". High NVT = overvalued. Woo + Kalichkin improved with 90-day moving average (NVT Signal).
3. **SOPR** (Spent Output Profit Ratio): > 1 = profit-taking, < 1 = loss-selling. Overall market sentiment.
4. **Exchange flows**: inflow = bearish (deposit to sell), outflow = bullish (accumulate self-custody).
5. **Active addresses**: proxy of network activity. Trend correlate con price.
6. **Stablecoin supply**: USDT + USDC + DAI market cap = "dry powder" for crypto purchases.
7. **Hash rate + difficulty**: Bitcoin miner activity. Hash rate drop = miner capitulation = bottom signal.

**Cap to build Oracle**:
1. Etherscan API adapter (free, Ethereum blockchain)
2. Btcscan API adapter (free, Bitcoin blockchain)
3. MVRV + NVT + SOPR calculator
4. Exchange flows tracker
5. Lane J crypto on-chain strategy

Vedi [literature.md](literature.md), [data-audit.md](data-audit.md), [edge.md](edge.md), [capability-map.md](capability-map.md).
