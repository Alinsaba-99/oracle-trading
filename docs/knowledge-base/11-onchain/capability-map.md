# 11 On-chain — Capability Map per Oracle

> Cosa costruire in Oracle (edge forte + free data + stack ready).

## ✅ Già in Oracle

| Capability | File | Note |
|---|---|---|
| BinanceVisionHistorical adapter | `market/ingestion/sources.py:BinanceVisionHistorical` | Bulk CSV 1m+5m+1h+1d for crypto |
| BinanceREST adapter | `market/ingestion/sources.py:BinanceREST` | Real-time L1 + klines |
| Dukascopy lake crypto majors | `data/lake/normalized/symbol=BTCUSD/...` | Cached |

## 🔨 P1 — Implementare prossimo (edge forte + free data)

### BL-KB-79: Etherscan API adapter
- **Perché**: 60+ EVM chains free, smart contract + token transfers.
- **Cosa**: `analytics/onchain/etherscan_adapter.py:EtherscanAdapter` con:
  - `pip install web3` + `ETHERSCAN_API_KEY` env
  - Fetch: balances, tx history, token transfers, contract events, logs
  - Cache su `data/onchain/etherscan/{address}_{date}.json`
- **Tempo**: ~2-3 giorni.
- **Costo**: $0.

### BL-KB-80: Btcscan API adapter
- **Perché**: Bitcoin blockchain raw data free no key.
- **Cosa**: `analytics/onchain/btcscan_adapter.py:BtcscanAdapter` con:
  - Block + tx + address + UTXO data
  - Realized cap calculator (per UTXO at last-move price)
  - SOPR calculator (spent value / created value per moved UTXOs)
- **Tempo**: ~3-5 giorni.
- **Costo**: $0.

### BL-KB-81: MVRV + NVT + SOPR calculator
- **Perché**: top on-chain metrics, robust 2010-2026.
- **Cosa**: `analytics/onchain/metrics.py:OnChainMetrics` con:
  - `compute_mvrv(market_cap, realized_cap) -> float`
  - `compute_nvt(network_value, tx_volume, window=90) -> float` (NVT Signal via 90d MA)
  - `compute_sopr(spent_value, created_value) -> float`
  - Output: time series per BTC + ETH
- **Tempo**: ~3-5 giorni.

### BL-KB-82: Exchange flows tracker
- **Perché**: CryptoQuant methodology. Inflow bearish, outflow bullish.
- **Cosa**: `analytics/onchain/exchange_flows.py:ExchangeFlowsTracker` con:
  - Exchange addresses list (Binance, Coinbase, Kraken, OKX cold wallets)
  - Daily inflow / outflow sums via Etherscan + Btcscan
  - Stablecoin inflow (USDT/USDC transfer to exchanges)
- **Tempo**: ~5-7 giorni (requires exchange address mapping).
- **Costo**: $0.

### BL-KB-83: Stablecoin supply tracker
- **Perché**: dry powder indicator. Bullish setup: rising supply + falling price.
- **Cosa**: `analytics/onchain/stablecoins.py:StablecoinSupplyTracker` con:
  - Track USDT (Ethereum + Tron) + USDC + DAI + BUSD market cap
  - Output: total stablecoin supply time series
- **Tempo**: ~2-3 giorni.

### BL-KB-84: Hash rate + difficulty ribbon
- **Perché**: miner capitulation = cycle bottom signal. 2018, 2020, 2022 all had compression.
- **Cosa**: `analytics/onchain/bitcoin_miner.py:DifficultyRibbon` con:
  - Hash rate (TH/s) + difficulty (T) from Btcscan
  - 30d + 60d + 90d MA compression indicator
  - Output: ribbon compression flag
- **Tempo**: ~2-3 giorni.

## 🔨 P2 — Implementare per signal combos

### BL-KB-85: Lane J crypto on-chain strategy
- **Perché**: nuova lane per crypto cycle-timing.
- **Cosa**: `analytics/strategy/lane_j_onchain.py:OnChainStrategy` con:
  - Universe: BTC + ETH + top 10 altcoins
  - Signals: MVRV (BL-KB-81) + Exchange flows (BL-KB-82) + Stablecoin (BL-KB-83) + Hash rate (BL-KB-84)
  - Position sizing: long BTC 2% when MVRV < 1.5 + difficulty ribbon compressed
  - Reduce position when MVRV > 3.5
  - Rebalance monthly
- **Target**: +5-10%/cycle (annualized 1-3%/yr). Sharpe > 0.5.
- **Tempo**: ~5-7 giorni (depends on BL-KB-79..84).

## 🔄 P3 — Deferrire

- **DeFi TVL tracking** (DefiLlama API free).
- **NFT floor price tracking** — paywalled mainly.
- **Liquidation cascade signals** — real-time, requires Binance WS.

## ❌ Hard-blocked (paywalled)

- Glassnode Premium — $30-800/mo
- Coin Metrics Enterprise — enterprise
- Santiment Pro — $50/mo
- IntoTheBlock — $50/mo
- Nansen Premium — $150/mo
- Arkham Intelligence — enterprise

## Sequenza implementazione raccomandata

```
BL-KB-79 Etherscan adapter         (~2-3g)
BL-KB-80 Btcscan adapter           (~3-5g)
BL-KB-81 MVRV+NVT+SOPR calculator  (~3-5g)
BL-KB-82 Exchange flows tracker    (~5-7g)
BL-KB-83 Stablecoin supply         (~2-3g)
BL-KB-84 Hash rate / difficulty    (~2-3g)
BL-KB-85 Lane J on-chain          (~5-7g)
```

Totale: **~22-33 giorni** per on-chain P1+P2.

## Prossimo step

Dopo P1+P2:
1. Backtest Lane J su 2010-2025 BTC cycle history (3-4 cycles).
2. DSR/PBO/CPCV validation (dominio 03).
3. **Target**: Sharpe > 0.5 on Lane J. Combina con Lane F (crypto L2 order flow dominio 04) per crypto ensemble.
