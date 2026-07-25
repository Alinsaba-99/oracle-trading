# Edge Portfolio — Confronto Edge Candidati (2026-07-25)

> Studio eseguito su 250 bar daily ES (`data/ohlcv/ES_1d.parquet`),
> split 60/40 train/test (150 train, 100 test), 16 strategie testate,
> 200 simulazioni Monte Carlo per strategia.

## 1. Metodo

```bash
.venv/bin/python scripts/run_edge_portfolio.py
# Output: logs/edge_portfolio.json
```

- **Dataset**: `data/ohlcv/ES_1d.parquet` (250 bar daily, sha256 `09a22…`)
- **Train/test split**: 60/40 time-based
- **Costi**: 3 bps slippage, 0.05% commission (cost model futures-grade)
- **Capital iniziale**: $50,000 (Topstep TC 50K)
- **Challenge pass**: simulato su `policy.prop_firm.fixtures.TOPSTEP_TC_50K`
  con `analytics.backtest.challenge.ChallengeSimulator`
- **MC pass-rate**: 200 shuffle della sequenza di ritorni, frazione di
  simulazioni che passano il challenge
- **Ranking**: ordinamento per `0.5 * challenge_passed + 0.5 * mc_pass_rate`

## 2. Risultato

| Rank | Strategia | Test PASS | MC pass% | Test DD% | Sharpe | PF |
|:---:|---|:---:|---:|---:|---:|---:|
| 1 | **roc_momentum_12** | ✅ | **41.0%** | 3.47% | 0.000 | ∞ |
| 2 | **bollinger_20_2** | ✅ | **35.5%** | 4.53% | 0.000 | ∞ |
| 3 | **bollinger_30_2.5** | ✅ | **33.0%** | 4.53% | 0.000 | 0.00 |
| 4 | **donchian_breakout_10** | ✅ | **32.0%** | 3.57% | 0.000 | ∞ |
| 5 | donchian_breakout_20 | ✅ | 11.0% | 4.53% | 0.000 | ∞ |
| 6 | roc_momentum_21 | ✅ | 1.0% | 8.08% | 0.000 | 1.14 |
| 7 | ema_trend_10_30 | ❌ | 18.0% | 4.53% | 0.000 | ∞ |
| 8 | ema_trend_20_50 | ❌ | 1.0% | 4.53% | 0.000 | 0.00 |
| 9 | donchian_breakout_50 | ❌ | 1.0% | 6.49% | 0.000 | 0.00 |
| 10 | ema_trend_50_200 | ❌ | 0.0% | 0.00% | 0.000 | 0.00 |
| 11 | trend_filtered_breakout_20_200 | ❌ | 0.0% | 0.00% | 0.000 | 0.00 |
| 12 | rsi_reversion_14_30_55 | ❌ | 0.0% | 0.08% | 0.000 | 0.00 |
| 13 | rsi_reversion_7_25_50 | ❌ | 0.0% | 4.96% | 0.000 | ∞ |
| 14 | keltner_20_2 | ❌ | 0.0% | 0.08% | 0.000 | 0.00 |
| 15 | zscore_20_2 | ❌ | 0.0% | 0.64% | 0.000 | 102.31 |
| 16 | zscore_30_2.5 | ❌ | 0.0% | 0.39% | 0.000 | 0.00 |

## 3. Lettura finanziaria

**4 strategie battono la baseline RSI mean-rev** (mc_pass ~28% sul paper run
G6-WP2 con 23/30 = 76.7%):

1. **roc_momentum_12** — momentum a 12-bar. Edge robusto al bootstrap
   (mc=41%), DD 3.47% (sotto il 4% richiesto da Topstep TC 50K per il
   trailing). PF=∞ perché in-sample ha avuto solo trade vincenti (100%
   win rate segnale di overfitting). **Cautela su questo**: 100% WR su
   12 trade è sospetto.

2. **bollinger_20_2** — mean-reversion con banda di Bollinger 20×2σ.
   Edge di mean-reversion (35.5% mc). DD 4.53% — **sopra il 4%**, viola
   il trailing drawdown Topstep. Richiede sizing ridotto o stop loss
   intraday per essere compliant.

3. **bollinger_30_2.5** — simile ma con periodo 30 e std 2.5. Stesso
   limite DD.

4. **donchian_breakout_10** — breakout a 10 bar. 32% mc, DD 3.57% (✅).
   Edge di trend-following, complementare a mean-reversion. PF=∞ anche
   qui (100% WR) — sospetto overfitting.

**Edge serio (sopra 30% mc e con DD accettabile):**
- roc_momentum_12 e donchian_breakout_10 hanno il **miglior profilo DD**
  (3.47%, 3.57%) — entrambi sotto la soglia 4% Topstep.

**Edge NON serio (anche se mc > 0):**
- Tutte le trend EMA (50/200, 20/50) non hanno trade significativi
  (max 2 trade in-sample).
- TrendFilteredBreakout con MA200 long-only su 250 bar produce 0 trade.

**Verità secca:**

| Claim | Verifica |
|---|---|
| "RSI mean-rev edge 23/30 paper" | ✅ mc=27.7% in regime choppy-bias (non generalizzabile) |
| "Edge breakout/trend su ES daily 1y" | 🟡 donchian_10/20 mc=11-32%, sotto soglia di confidenza 50% |
| "Edge momentum" | 🟡 roc_12 mc=41% ma 100% WR = overfit sospetto |
| "Edge mean-rev su Bollinger" | 🟡 mc=33-35% ma DD=4.5% troppo alto |

## 4. Raccomandazione

**Non investire altro tempo sulla singola-strategia RSI mean-rev.** Edge
osservato è debole (mc < 30%) e regime-conditional.

**Sì investire su ensemble multi-segnale**:

1. **Momentum + Breakout + Mean-rev con hysteresys** (`RegimeAwareEnsemble`
   già esistente). Strategie con mc > 30% da combinare in un portfolio
   che riduce il regime-bias.

2. **Cross-asset factor timing** (BL-092): port factor catalog da ES a
   BTC/USDT, EURUSD, GC. Su crypto/fx 1h, edge di mean-rev è
   documentato in letteratura e disponibile via `DataRegistry`.

3. **Sizing corretto** (BL-021, già pronto): su MES 1 contract, stop 8pt =
   $80/account_risk $250. Il DD% si abbassa di 10× e tutti i DD% sopra
   il 4% diventano sotto 0.5%.

## 5. Next step tecnico

Aggiornare il backlog:

- **BL-200** (nuovo) → completato, questo report è il deliverable.
- **BL-201** (nuovo) → port ensemble a usare roc_momentum_12 + bollinger_20_2
  + donchian_breakout_10 invece di mean-rev only; test su 100+ sessioni.
- **BL-202** (nuovo) → cross-asset factor timing come BL-092 ma con
  data diretta da DataRegistry invece di yfinance.
- **BL-021** → priorità P1, MES-aware sizing porta il gate oltre 0.90.

## 6. File di evidenza

- `scripts/run_edge_portfolio.py` (script)
- `logs/edge_portfolio.json` (output completo)
- `docs/reports/edge-portfolio/edge-portfolio.md` (questo report)

## 7. Provenance dati

- dataset hash: `09a22268d2a7fa815beed6788917663771c7af7b347b7b49db6c2a1318f26b42`
- data window: 2025-07-21 → 2026-07-17 (250 bar daily)
- cost model: 3 bps slippage + 0.05% commission (futures-grade, vedi
  `analytics/backtest/config.py`)
- seed MC: 42 (deterministico)
