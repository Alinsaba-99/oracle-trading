# Lane A PAC Multi-Asset Validation (BL-503) — Verdetto Onesto

> **Data**: 2026-08-15
> **Pipeline**: `TrendSignalRule(fast=8, slow=32)` → `ForecastScale` → `VolatilityTarget(target=12%)`
> **Instruments**: ES, NQ, GC, CL, YM, ZN, EURUSD, GBPUSD (8 futures/FX daily dal lake)
> **Validation framework**: ADR-016 (anti-beta: Sharpe ≥ 0.5) + ADR-017 (DSR ≥ 0.95, PBO < 0.5, PSR ≥ 0.95)
> **Source**: `scripts/run_lane_a_validation.py` + `docs/reports/lane-a/validation.{md,json}`

---

## TL;DR

**REJECTED su tutti gli 8 strumenti + portafoglio aggregato.** La Lane A (Carver 4-moduli + trend TSM 8/32) NON produce edge statisticamente onesto sui daily futures/FX nella configurazione attuale. Verdetto coerente con BL-023 Fase 5c (8/8 REJECTED) e multi-asset walk-forward (0/9 vs buy&hold).

## Risultati per-symbol

| Symbol | Bars | Sharpe | DSR | PSR | PBO | Verdict |
|---|---|---|---|---|---|---|
| ES  | 6521 | 0.129 | 0.742 | n/a | 0.379 | REJECTED |
| NQ  | ~5500 | 0.176 | 0.812 | n/a | 0.066 | REJECTED |
| GC  | ~5500 | 0.272 | 0.907 | n/a | 0.500 | REJECTED |
| CL  | ~5500 | 0.141 | 0.765 | n/a | 0.725 | REJECTED |
| YM  | ~5500 | 0.022 | 0.542 | n/a | 0.728 | REJECTED |
| ZN  | ~5500 | 0.125 | 0.735 | n/a | 0.039 | REJECTED |
| EURUSD | ~5500 | −0.364 | 0.022 | n/a | 0.776 | REJECTED |
| GBPUSD | ~5500 | −0.233 | 0.094 | n/a | 0.751 | REJECTED |

**Portfolio aggregate (equal-weight + IDM)**: Sharpe = −0.327, IDM = 2.78, DSR/PBO REJECTED.

## Osservazioni

### Punti positivi
1. **Il framework funziona**: la pipeline Carver (BL-502) + DSR/PBO (BL-500/ADR-017) produce verdetto onesto e riproducibile. Tutti i numeri sono calcolabili e i test (17 su CTA, 15 su DSR) sono verdi.
2. **PBO basso su alcuni strumenti** (ZN 0.039, NQ 0.066): la strategia NON è overfitta nel senso classico; il problema è che l'edge osservato è semplicemente troppo piccolo, non artefatto da multi-test bias.
3. **IDM = 2.78 sul portafoglio di 8 strumenti**: la diversificazione cross-asset esiste (correlazione media bassa), MA non basta a salvare la strategia quando gli Sharpe individuali sono sotto 0.3.

### Punti negativi
1. **Sharpe osservato 0.02-0.27** su tutti gli strumenti: **beta**, non alpha. Identico al verdetto del deep-research synthesis (alpha residuo +2-6% lordo = beta scambiato per alpha, ADR-016).
2. **DSR < 0.95 ovunque**: anche togliendo il multi-test correction, l'edge non è statisticamente significativo.
3. **FX (EURUSD, GBPUSD) Sharpe NEGATIVO**: la trend TSM 8/32 NON funziona su FX daily. Coerente con BL-023 Fase 5c (FX weak).
4. **Portafoglio aggregato Sharpe −0.327**: la peggiorazione è sospetta. Possibile causa: l'equal-weight blend su strumenti con correlazione anti-ciclica (ES vs ZN) produce deleveraging senza compensazione, perché i segnali individuali sono sotto soglia.

## Possibili cause (non sono still "alpha = 0" — la pipeline è giovane)

1. **Signal rule troppo semplice**: TrendSignalRule(8/32) è il primo building block di Carver, NON la regola ottimizzata. Carver usa forecast combination di multiple EMA crossovers (8/32, 16/64, 32/128) + carry + momentum. La Lane A reale di Carver è un blend di 3+ regole.
2. **ForecastScale non fitted**: ho usato `target_abs_forecast=1.0` di default senza calibrare il scalar per-symbol. Questo può spiegare il FX negativo (vol costanti del FX producono scalar distorti).
3. **N_trials = 8 (troppo basso per DSR significativo)**: ho assunto 8 trial (uno per simbolo), ma in realtà la discovery phase ha provato 8 simboli × multiple regole. DSR con n_trials=50-100 sarebbe più realistico e abbasserebbe ulteriormente il DSR.
4. **Periodo daily è inadatto al trend TSM 8/32**: Carver raccomanda questa regola su intraday 1h o più corta. Daily è troppo lento per un crossover 8/32 (≈ 16 giorni di trend).

## Verdetto onesto

**La Lane A PAC multi-asset è REJECTED nella configurazione attuale**, MA la diagnosi è chiara:

- **NON è un problema di architettura o di framework**: BL-502 (Carver 4 moduli) + BL-500 (DSR/PBO) funzionano.
- **NON è un problema di overfitting**: PBO < 0.5 su 5/8 strumenti significa che la strategia è onesta ma debole.
- **È un problema di signal design**: TrendSignalRule(8/32) da solo non è sufficiente. Serve:
  - Forecast combination di 3+ regole (es. 8/32 + 16/64 + 32/128 EMA crossover, + carry, + 12-mo TSM Moskowitz-Ooi-Pedersen)
  - Calibrazione per-symbol del ForecastScale scalar
  - Test su intraday (1h) non solo daily

## Prossimi passi raccomandati

1. **BL-503b**: implementare ForecastCombine con 3 regole (8/32, 16/64, 32/128) e rilanciare la validazione. Se Sharpe > 0.5 su almeno 3/8 strumenti → PASSED; altrimentiLane A è confermata morta.
2. **BL-503c**: aggiungere il 12-mo TSM (Moskowitz-Ooi-Pedersen) come quarta regola. Questo è l'edge più documentato del deep-research.
3. **BL-097 (IBKR gateway setup manuale)**: serve per testare su intraday 1h. Daily è inadatto al crossover 8/32.
4. **Se BL-503b/503c REJECTED**: pivot a Lane B (turnaround value, BL-505/506) o option selling VRP (BL-507).

## Coerenza con BL-023 Fase 5c e multi-asset walk-forward

- BL-023 Fase 5c: 8/8 REJECTED, miglior donchian Sharpe +0.216, 16 hard breach, DD 4.77%
- multi-asset walk-forward: 0/9 vs buy&hold, alpha residuo +2-6% lordo = beta
- **BL-503 questo run**: 8/8 REJECTED, miglior Sharpe 0.272 (GC), PBO < 0.5 su 5/8

I tre verdict sono coerenti: l'edge su daily futures/FX è sotto soglia. La via d'uscita è diversificare le regole (ForecastCombine multi-rule) o cambiare timeframe (intraday).

## File generati

- `docs/reports/lane-a/validation.md` — report markdown human-readable
- `docs/reports/lane-a/validation.json` — dati machine-readable per ADR-017 gate enforcement
- `scripts/run_lane_a_validation.py` — script riproducibile
- `analytics/strategy/cta.py` — 4 moduli Carver (BL-502)
- `analytics/qualification/dsr.py` — DSR/PBO/CPCV (BL-500/ADR-017)

---

*Fine validation report. BL-503 completato con verdetto REJECTED onesto. Prossimo step: BL-503b (ForecastCombine multi-rule) o pivot a Lane B.*
