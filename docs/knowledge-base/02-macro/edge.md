# 02 Macro — Edge Plausibility

> Valutazione critica per ogni sotto-edge macro.

## Edge plausibility summary

| Edge | Paper | Edge storico | Edge OOS 2020-2026 | Decay | Regime |
|---|---|---|---|---|---|
| Taylor rule deviation | Taylor 1993, Orphanides 2003 | bond alpha +2%/yr | marginale | alto | Regime-specific (non-ZLB) |
| Yield curve inversion (10Y-2Y) | literature 1970-2020 | 12-18m recession predict | maintained | basso | All-weather |
| Output gap predict | Cooper-Priestley 2009 | R² 5-10% on 1y equity | R² 3-5% (reduced) | medio | All-weather |
| Macro factors (8-factor) | Ludvigson-Ng 2009 | R² 21-26% on 1y bonds | R² 10-15% | medio | All-weather |
| Pre-FOMC drift | Lucca-Moench 2015 | +33bps/day 1994-2011 | +10-15bps/day 2015+ | alto | Pre-FOMC window |
| FOMC 3-day window (bonds) | Hillenbrand 2021 | +13-18bps/day 1989-2021 | maintained | basso | FOMC cycle |
| Growth × Inflation regime | Bridgewater 1996 | diversified Sharpe ~0.7 | maintained | basso | All-weather |
| 60/40 portfolio | benchmark | +7.5%/yr 1990-2021 | -17% 2022 (regime flip) | medio | Bull + deflation regime |
| TIPS breakeven trading | Haubrich-Pennacchi-Ritchken 2011 | +2-3%/yr | +1-2%/yr | medio | Inflation↑regime |
| CPI surprise straddle | practitioners | +50-200bps per CPI | ~50bps (decayed by HFT) | alto | Event-driven |
| Trade balance → USD | literature | lagged 6-12m, R² 5% | marginal | alto | USD regime |
| Nonfarm payrolls surprise | practitioners | intraday 200bps | ~50bps (decayed) | alto | Event-driven |

## Verdetto edge

**Edge macro più forte è nei fattori persistenti non negli eventi**:
1. **Yield curve + output gap + macro factors** → 1-year horizon signals, R² 5-25%.
2. **Growth × Inflation regime** → asset allocation overlay.
3. **FOMC drift** → ancora edge documentato ma decaying.

**Edge debole o troppo rumoroso**:
- Event-driven (CPI surprise, NFP straddle) — decayed by HFT + algorithmic front-running.
- Taylor rule deviation — noisy real-time data.
- Trade balance → USD — combined with rate differential, hard to isolate.

## Regime dipendenza

Macro edge è **fortemente regime-dependent**:
- **Inflation↑ regime** (2022-2023): stock-bond correlation flipped positive → 60/40 broken. Macro regime classifier essential.
- **ZLB regime** (2009-2015): Taylor rule deviates sharply, monetary policy rule signals weakened.
- **Liquidity trap**: output gap negative ma rates cannot fall → unconventional monetary policy (QE) → different signals.

Per Oracle: macro signals sono **overlay per sizing + regime classification**, NON standalone trading signals. Es.:
- Long Lane B (equity value) quando: yield curve >0.5% AND output gap positive AND CAPE < 25
- Reduce exposure quando: yield curve inverted OR output gap negative AND VIX > 30

## Cost-realism check

- **Trading costs**: macro trading è low-frequency (quarterly/macro event), 20-50 trades/yr → costs marginal.
- **Tax**: same as equity (~26% IT capital gains).
- **Net edge realistico**: +1-3%/yr post-cost su 5y. Sharpe 0.3-0.5.

## Validazione G5 (ADR-017)

Per promozione macro strategy serve:
- DSR > 0.95 (con molti test multipli, threshold alto)
- PBO < 0.5
- 250+ paper sessions con pass-rate ≥ 90%

Macro edge è meno rumoroso di L2 order flow ma meno edge di fundamental equity.
