# G6 Paper Attack — Diagnosi 77% → 90% Pass Rate

> Data: 2026-07-30
> Stato: analisi eseguita, soluzione identificata, non ancora implementata

## Problema

M32a WP2: 23/30 sessioni (77%) vs target 90%.
Causa primaria: **regime detector choppy-biased** → 29/30 sessioni classificate
come "choppy" → specialist `mean_rev` sempre selezionato → zero diversificazione.

## Root Cause

`_sma_regime_heuristic()` su ES 1d daily con finestra 30 barre:
- 97.3% choppy (misurato 2026-07-30 con BL-010..014 applicato)
- 2.7% bull
- 0% bear, volatile

Le soglie (vol ratio 1.35, trend sigma 0.45/0.60) non bastano: ES daily
semplicemente non produce abbastanza deviazione rispetto a una finestra
di ~6 settimane per attivare i gate trend/volatile.

## Soluzione: AdaptiveEnsemble (blending pesato)

Il file `analytics/strategy/adaptive_ensemble.py` (WIP, non ancora committato)
implementa:

1. **Weight blending** invece di routing binario: ogni regime ha un vettore
   di pesi per tutti gli specialisti, calcolato dallo sweep multi-asset.
   Per ES 1d choppy: mean_rev=0.6, breakout=0.3, trend=0.1

2. **Regime classifier opzionale**: PyTorch 8-regime (Kairos-v2, 36.45%
   accuracy su validation) + mapping ai 4 RegimeLabel Oracle.

3. **Weight evolver**: aggiornamento dinamico basato su Sharpe rolling.

## Passi per implementare

1. Commit `adaptive_ensemble.py` + `weight_evolver.py`
2. Aggiornare `run_g6_wp2_paper_sessions.py` per usare `AdaptiveEnsemble`
3. Eseguire 30 sessioni di test
4. Iterare pesi se pass_rate < 90%

## Alternative valutate

| Approccio | Voto | Motivo |
|-----------|------|--------|
| AdaptiveEnsemble blending | ✅ | Pronto, basato su sweep reale |
| PyTorch regime classifier | 🟡 | 36.5% accuracy, serve training |
| Multi-TF regime (1h+1d) | 🟡 | Dati disponibili ma non integrati |
| Solo mean_rev tuning | ❌ | Già provato, non basta |
