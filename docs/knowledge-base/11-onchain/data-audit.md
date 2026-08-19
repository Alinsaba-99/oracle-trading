# 11 On-chain — Data Audit (free $0 verified 2026-08-17)

> Regola hard: $0/mo per dati. Vedi ADR-020.

## Fonti on-chain free verificate

| Fonte | Coverage | Format | API Key | Limit | Note |
|---|---|---|---|---|---|
| **Etherscan API** | 60+ EVM chains (Ethereum + L2s) | REST JSON | `ETHERSCAN_API_KEY` free email | 5 req/sec, 100k req/day | https://docs.etherscan.io. Balances, transactions, token transfers, contract code, logs |
| **Btcscan API** | Bitcoin blockchain | REST JSON | nessuna | rate-limited | https://btcscan.org/api. Block + tx + address data |
| **Blockchain.com API** | Bitcoin + Ethereum | REST JSON | nessuna | rate-limited | https://blockchain.info/q. Address + tx + UTXO |
| **BlockCypher API** | Bitcoin + Ethereum + others | REST JSON | `BLOCKCYPHER_API_KEY` free | 100 req/hour free | https://www.blockcypher.com. Better rate limits with key |
| **CoinGecko API** | crypto market data + on-chain | REST JSON | nessuna (free tier) | 30 req/min, 100k req/month | https://www.coingecko.com/api. Price + market cap + supply |
| **CoinGlass** | MVRV + funding rate | Web + API | nessuna | soft limit | https://www.coinglass.com. MVRV free chart + CSV |
| **Glassnode (free tier)** | subset of on-chain metrics | REST JSON | `GLASSNODE_API_KEY` free | 30 req/day free | https://studio.glassnode.com. MVRV, SOPR, NVT limited free |
| **CryptoQuant (free)** | exchange flows + miner | REST JSON | nessuna | limited | https://cryptoquant.com/asset/btc/chart/exchange-flows. Some charts free |
| **DefiLlama API** | TVL DeFi protocols | REST JSON | nessuna | rate-limited | https://defillama.com/docs/api. Total Value Locked across DeFi |

## Capabilities Oracle esistenti

- ✅ `market/ingestion/sources.py:BinanceVisionHistorical` — bulk CSV 1m+5m+1h+1d
- ✅ `market/ingestion/sources.py:BinanceREST` — real-time L1 + klines
- ✅ Dukascopy lake (crypto majors cached)
- ✅ `analytics/strategy/catalog/` signal classes structure

## Gap dichiarati

1. **Etherscan API adapter** NON implementato. TODO BL-KB-79.
2. **Btcscan API adapter** NON implementato. TODO BL-KB-80.
3. **MVRV + NVT + SOPR calculator** NON implementato. TODO BL-KB-81.
4. **Exchange flows tracker** NON implementato. TODO BL-KB-82.
5. **Stablecoin supply tracker** NON implementato. TODO BL-KB-83.
6. **Hash rate + difficulty ribbon** NON implementato. TODO BL-KB-84.
7. **Lane J crypto on-chain strategy** NON implementata. TODO BL-KB-85.

## Cap da NON usare (paywalled)

| Fonte | Perché esclusa | Alternativa free |
|---|---|---|
| Glassnode Premium | $30-800/mo | Glassnode free tier + CoinGlass + CryptoQuant |
| Coin Metrics Enterprise | enterprise | Etherscan + Btcscan + CoinGecko |
| Santiment Pro | $50/mo | CoinGecko + Glassnode free |
| IntoTheBlock | $50/mo | CoinGecko + custom metrics |
| Nansen Premium | $150/mo | Etherscan + free scrapers |
| Arkham Intelligence | enterprise | Etherscan + DefiLlama |

## Reference implementations free

- **Etherscan docs**: https://docs.etherscan.io
- **Btcscan API**: https://btcscan.org/api
- **Glassnode free tier**: https://studio.glassnode.com (sign-up required for free metrics)
- **CoinGecko API**: https://www.coingecko.com/api/documentation
- **CoinGlass MVRV**: https://www.coinglass.com/pro/i/mvrv-ratio
- **DefiLlama API**: https://defillama.com/docs/api
- **CryptoQuant free charts**: https://cryptoquant.com/asset/btc/chart/exchange-flows
