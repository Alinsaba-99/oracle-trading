# 11 On-chain — Literature Review

> Fonti: Tavily API (advanced) 2026-08-17. URL verified.

## 1. MVRV ratio

### Murad Makhmudov / David Puell 2018

- **MVRV formula**: Market Cap / Realized Cap (sum of all UTXOs at last-move price).
- **Thresholds**:
  - MVRV > 3.5: market top, overvalued.
  - MVRV 2-3.5: bull market normal.
  - MVRV 1-2: undervalued.
  - MVRV < 1: market bottom, capitulation.
- **2026-08-17**: MVRV suggests overvalued (Coinglass).
- **Edge**: signal of cycle top/bottom. Robust since 2010.

### Realized cap

- Sum of all UTXOs valued at their last-move price.
- Better proxy of "true" BTC value than spot price × supply.
- Filter long-dormant coins vs actively traded.

## 2. NVT ratio

### Willy Woo — NVT origin

- **NVT formula**: Network Value (Market Cap) / Transactions Value (daily USD transaction volume).
- **P/E ratio analogy**: P = network value, E = transaction throughput.
- **High NVT**: overvalued (network value > actual usage).
- **Low NVT**: undervalued.

### Dmitry Kalichkin 2017 — NVT Signal

- **Improvement**: use 90-day moving average of transactions (smoothing).
- **NVT Signal**: better predictor than raw NVT.
- **Cross-asset**: methodology holds across Bitcoin, Ethereum, Litecoin.

### NVT ratio limitations

- Only 9 years of data for Bitcoin.
- Doesn't capture Layer 2 (Lightning Network) + sidechains.
- Transaction value ≠ economic activity (mixers + internal wallets inflate).

## 3. SOPR

### Aakash Sherwani + Renato Shirakashi 2019

- **SOPR formula**: Σ(spent value) / Σ(created value) per UTXO moved.
- **SOPR > 1**: profit-taking (holders selling in profit).
- **SOPR < 1**: loss-selling (capitulation).
- **SOPR = 1**: breakeven support line.
- **Edge**: SOPR drops below 1 = bottom signal.

### Variants

- **aSOPR** (adjusted SOPR): excludes miner + exchange addresses, focuses on retail.
- **Long-Term Holder SOPR** (LTH-SOPR): coins held > 155 days. Better signal of cycle.
- **Short-Term Holder SOPR** (STH-SOPR): coins held < 155 days. Recent buyers.

## 4. Exchange flows

### CryptoQuant methodology

- **Exchange Inflow** (total): crypto transferred into exchange wallets. Bearish (deposit to sell).
- **Exchange Outflow**: crypto leaving exchanges. Bullish (self-custody accumulation).
- **Stablecoin Inflow**: capital entering exchanges for buying. Bullish.
- **Stablecoin Outflow**: capital leaving for self-custody. Bearish (no immediate purchase).
- **Edge**: BTC exchange outflow spike + stablecoin inflow spike = bullish setup.

## 5. Active addresses

### Network activity proxy

- **Daily active addresses (DAA)**: unique addresses transacting per day.
- **DAA trend correlates con price**: network adoption → price appreciation.
- **Decoupling**: price up + DAA flat = bubble (2017, 2021). DAA up + price flat = accumulation.

## 6. Stablecoin supply

### "Dry powder" indicator

- **USDT + USDC + DAI market cap**: total stablecoin supply.
- **Growth = capital inflow to crypto ecosystem**.
- **2026 stablecoin supply**: ~$200B+ total.
- **Edge**: rising stablecoin supply + falling BTC price = bullish setup (dry powder ready).

## 7. Hash rate + difficulty

### Miner capitulation signal

- **Hash rate drop > 30% from ATH**: miner capitulation (unprofitable → shut down).
- **Difficulty ribbon**: 30d + 60d + 90d MA compress. Compression = miner capitulation = bottom.
- **Edge**: historical bottom signal. 2018, 2020, 2022 all had difficulty ribbon compression before rally.

## 8. Cap summary

**Edge forte maintained**:
- MVRV ratio (cycle top/bottom).
- SOPR (profit-taking vs loss-selling).
- Exchange flows (inflow bearish, outflow bullish).
- Stablecoin supply (dry powder).
- Hash rate / difficulty ribbon (miner capitulation = bottom).

**Edge medium**:
- NVT ratio (9y data, methodological caveats).
- Active addresses (correlates with price but noisy).

**Edge hard-blocked**:
- Glassnode historical chart data (paywalled $30/mo+).
- Coin Metrics terminal (enterprise).
- Santiment (paywalled).

**Free raw data sources**:
- Etherscan API (Ethereum blockchain, 60+ EVM chains, free 5 req/sec with key).
- Btcscan API (Bitcoin blockchain, free).
- Blockchain.com API (Bitcoin + Ethereum, free).
- CoinGecko API (crypto market data, free tier 30 req/min).
- CryptoQuant (free limited tier for some metrics).
- CoinGlass (free MVRV chart).
