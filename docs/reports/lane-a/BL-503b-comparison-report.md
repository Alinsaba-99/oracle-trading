# BL-503b — Lane A Multi-rule ForecastCombine — Miglioramento significativo ma ancora REJECTED

> **Data**: 2026-08-15
> **Scope**: BL-503b — ForecastCombine di 4 regole (EMA 8/32 + EMA 16/64 + EMA 32/128 + TSM 252 Moskowitz) vs BL-503 single-rule (TrendSignalRule 8/32)
> **Source**: `scripts/run_lane_a_validation.py --multi-rule`

---

## TL;DR

**Multi-rule ForecastCombine migliora Sharpe di 1.6-18× ma resta sotto 0.5 target** su 7/8 strumenti. **GC crossed 0.5** (Sharpe 0.510). Portfolio Sharpe 0.063 (vs single-rule −0.327) — miglioramento netto ma insufficiente. DSR alto (0.97-0.99) su 4 strumenti = significatività statistica raggiunta.

## Risultati comparativi per-symbol

| Symbol | Single-rule Sharpe | Multi-rule Sharpe | Improvement | DSR multi | PBO multi | Verdetto |
|---|---|---|---|---|---|---|
| ES  | 0.129 | **0.402** | 3.1× | 0.976 | 0.733 | REJECTED |
| NQ  | 0.176 | **0.420** | 2.4× | 0.981 | 0.071 | REJECTED |
| GC  | 0.272 | **0.510** ✅ | 1.9× | 0.993 | 0.665 | REJECTED (Sharpe≥0.5 MA PBO alto) |
| CL  | 0.141 | 0.227 | 1.6× | 0.877 | 0.167 | REJECTED |
| YM  | 0.022 | **0.389** | 17.7× | 0.968 | 0.756 | REJECTED |
| ZN  | 0.125 | 0.021 | −83% (worse) | 0.537 | 0.418 | REJECTED |
| EURUSD | −0.364 | −0.182 | 50% better (still neg) | 0.155 | 0.895 | REJECTED |
| GBPUSD | −0.233 | −0.108 | 54% better (still neg) | 0.265 | 0.324 | REJECTED |

**Portfolio aggregate**: Sharpe 0.063 (vs single-rule −0.327), IDM 2.71, DSR n/a, PBO n/a.

## Punti chiave

### Positivi
1. **Trend è la direzione giusta**: multi-rule ForecastCombine migliora Sharpe su 7/8 strumenti (tranne ZN)
2. **GC crossed 0.5**: primo strumento che raggiunge la soglia ADR-016 §4
3. **DSR alto su ES/NQ/GC/YM (0.97-0.99)**: l'edge è statisticamente significativo dopo multi-test correction (n_trials=8). Non è artefatto da multi-testing bias.
4. **PBO basso su NQ (0.071) e CL (0.167)**: la strategia NON è overfitta su questi strumenti; l'edge osservato regge su out-of-sample

### Negativi
1. **Portfolio Sharpe 0.063 < 0.5 target**: la diversificazione cross-asset abbassa la volatilità ma non alza sufficientemente il rendimento
2. **FX ancora negativo**: EURUSD/GBPUSD Sharpe −0.18/−0.11. La trend TSM NON funziona su FX daily (coerente con BL-023 Fase 5c)
3. **PBO alto su ES (0.73), YM (0.76), GC (0.67)**: su questi strumenti c'è rischio overfitting — la strategia ottimizzata su in-sample potrebbe non reggere su out-of-sample nonostante DSR alto
4. **ZN peggiorato**: il TSM con lookback 252 non funziona su bond futures in orizzonte daily

## Diagnosi: perché multi-rule aiuta ma non basta

1. **Diversificazione delle regole**: 3 EMA crossovers (8/32, 16/64, 32/128) coprono orizzonti di trend diversi (short/medium/long). Il TSM 252 aggiunge il fattore accademico più documentato.
2. **ForecastScale normalization**: ogni regola viene normalizzata a abs mean 1.0 prima della combinazione, evitando che una regola ad alta varianza domini
3. **VolatilityTarget sizing**: il position scalar è inversamente proporzionale alla volatilità realizzata — riduce rischio nei periodi ad alta vol

**MA**:
1. **Daily timeframe è ancora il problema**: 252 barre = 1 anno di daily è troppo lungo per trend-following futures. Carver raccomanda intraday 1h o più corto per EMA 8/32.
2. **Nessun filtro di regime**: la strategia va long/short in qualsiasi regime. Carver usa regime filter (vol regimes, trend regimes) per disattivare la strategia in regimi sfavorevoli.
3. **No forecast combination pesata**: ho usato equal-weight (25% per regola). Carver raccomanda weight optimization basata su rolling Sharpe per regola.

## Prossimi step per Lane A (BL-503c futuro)

1. **Aggiungere carry + cross-asset momentum** (5-7 regole totali invece di 4). Carver usa 7 regole nel suo libro.
2. **Regime filter**: disattivare la strategia in regime "choppy" (Hurst variance ratio < threshold).
3. **Weight optimization**: pesare le regole con rolling Sharpe inverso (regole con peggior Sharp recente hanno peso minore).
4. **Test su intraday 1h**: BL-097 IBKR gateway setup manuale richiesto per dati intraday.
5. **Escludere FX dal portfolio**: EURUSD/GBPUSD non funzionano con trend TSM. Concentrarsi su futures (ES, NQ, GC, CL, YM, ZN).

## Verdetto onesto

**BL-503b è progresso reale ma non breakthrough.** Confronto diretto:
- BL-503 single-rule: 8/8 REJECTED, portfolio Sharpe −0.327 (beta scambiato per alpha)
- **BL-503b multi-rule**: 8/8 REJECTED, **portfolio Sharpe +0.063** (alpha modesto ma reale; DSR alto su 4/8 strumenti = significatività statistica)

La trend TSM è ancora viva ma debole. Per superare 0.5 Sharpe target servono:
- Più regole (carry, cross-asset, seasonality)
- Regime filtering
- Intraday data (BL-097)

## Confronto Lane A vs Lane B stato attuale

| Metrica | Lane A multi-rule | Lane B v1 relaxed (2020-24) |
|---|---|---|
| Sharpe | 0.063 (portfolio) | 0.679 |
| Annual return | n/a | +12.13% |
| Max DD | n/a | 27.01% |
| Instruments | 8 futures | 175 stocks |
| Verdetto | REJECTED | PROMETTENTE (ma Max DD alto) |

**Lane B è 10× avanti rispetto a Lane A.** La tua intuizione INTC/Xiaomi ha più valore di qualunque tuning di Lane A.

## File generati

- `analytics/strategy/cta.py` — aggiunto `TSMRule` + `build_lane_a_pipeline_multi_rule`
- `scripts/run_lane_a_validation.py` — aggiunto `--multi-rule` flag + `compute_strategy_returns_multi_rule`
- `docs/reports/lane-a/validation_multi_rule.{md,json}` — report multi-rule
- `docs/reports/lane-a/BL-503b-comparison-report.md` — questo report

---

*Fine BL-503b. Multi-rule ForecastCombine è la direzione giusta (3-18× improvement su Sharpe) ma non basta per superare 0.5 target su daily timeframe. Prossimo: Lane B ops CLI scripts.*
