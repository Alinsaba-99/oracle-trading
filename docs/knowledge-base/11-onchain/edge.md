# 11 On-chain — Edge Plausibility

> Valutazione critica per ogni on-chain signal.

## Edge summary

| Signal | Source | Edge | Free $0 | Orizzonte | Decay |
|---|---|---|---|---|---|
| MVRV ratio | Murad/Puell 2018 | +5-10%/cycle top detection | ✅ | 3-12m | basso |
| NVT ratio | Willy Woo | +3-5%/3m undervalued | ✅ | 1-3m | medio (methodological caveats) |
| NVT Signal (90d MA) | Kalichkin 2017 | +5-7%/3m | ✅ | 1-3m | basso |
| SOPR | Sherwani/Shirakashi 2019 | +2-4%/1-3m | ✅ | 1-3m | basso |
| LTH-SOPR | academic | cycle bottom +5-10% | ✅ | 3-12m | basso |
| Exchange inflow bearish | CryptoQuant | +2-3%/1w | ✅ | 1-2w | basso |
| Exchange outflow bullish | CryptoQuant | +2-3%/1w | ✅ | 1-2w | basso |
| Stablecoin supply (dry powder) | practitioners | +5-10%/3m | ✅ | 3-6m | basso |
| Hash rate drop (miner capitulation) | difficulty ribbon | +5-15%/6m | ✅ | 3-6m | basso |
| Active addresses | academic | +2-4%/3m | ✅ | 1-3m | medio |
| TVL DeFi | DefiLlama | +2-3%/1-3m | ✅ | 1-3m | medio |

## Verdetto edge

**Edge forte maintained**:
- **MVRV** (cycle top/bottom, > 3.5 top, < 1.0 bottom) — robusto 2010-2026.
- **SOPR** (profit-taking vs capitulation).
- **Exchange flows** (inflow bearish, outflow bullish).
- **Stablecoin supply** (dry powder for BTC purchases).
- **Hash rate / difficulty ribbon** (miner capitulation = cycle bottom).

**Edge medium**:
- **NVT** (9y data, methodological caveats — Lightning + L2 don't show).
- **Active addresses** (correlates with price but noisy).

## Regime dipendenza

- MVRV/SOPR: cycle timing (years, not weeks).
- Exchange flows: weekly signals.
- Stablecoin + hash rate: monthly regime.
- NVT: regime-dependent (bull vs bear divergent).

## Cost-realism check

- **Trading costs crypto**: 0.04% taker Binance (vs 0.02% maker).
- **Tax crypto**: 26% IT capital gains.
- **Net edge realistico**: +3-7%/cycle (annualized 1-3%/yr since cycles are 3-4y). Sharpe 0.5-1.0.
- **Edge per cycle**: +5-15% su buy-and-hold BTC over 3-4y cycle.

## Validazione G5 (ADR-017)

Per promozione on-chain strategy:
- DSR ≥ 0.95 (con pochi test multipli, cycle data limited)
- PBO < 0.5
- CPCV OOS Sharpe > 0.5
- 250+ paper sessions con pass-rate ≥ 90%

Cycle-based signals sono slow (3-12m horizon) ma edge forte. Combina con Lane F (crypto L2 order flow) per ensemble crypto.
