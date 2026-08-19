# Dominio 01 — Fundamental Analysis

> Knowledge base Oracle — studio approfondito 2026-08-17 via Tavily API (AI-optimized web search).
> Obiettivo: mappare letteratura, fonti dati free, edge plausibile, capability map per Oracle.

## Sintesi esecutiva

L'analisi fondamentale ha **edge documentato in letteratura** ma con caveat critici:

1. **Edge storico forte** (Piotroski 2000: +13.4% annuo su high-F-Score value stocks; Lakonishok-Shleifer-Vishny 1994: value premium sostanzioso su 3-5y orizzonti; Novy-Marx 2013: gross profitability premium; Asness-Frazzini-Pedersen QMJ).
2. **Edge decaduto 2014-2020** — growth ha battuto value di ~5%/anno per 10y. Poi **rimbalzo 2020-2023** con value +11%/anno su growth. Cycle-dipendente.
3. **Edge in parte spieghibile come fattori** — Fama-French 5-factor (HML + RMW + CMA) riduce l'alpha di Piotroski/Lakonishok. Buffett alpha (Frazzini-Kabiller-Pedersen 2018) diventa insignificante controllando per BAB + QMJ.
4. **Edge residuo = behavioral + mispricing** — Lakonishok 1994 attribuisce premium a errori di estrapolazione (glamour stocks over-extrapolated), NON a rischio. Shiller CAPE (1988) conferma: market level predice 10y returns meglio su orizzonti lunghi.
5. **Anomalie complementari**: accrual anomaly (Sloan 1996), PEAD (Piotroski-So 2012), 52-week high (George-Hwang 2004), fundamental momentum (Chen-Lakonishok 2020). Si combinano, non si sostituiscono.
6. **Cap fattore zoo** — Harvey-Liu-Zhu (2016) + Hou-Xue-Zhang (2020): 400+ fattori pubblicati, ~1/3 non replicano OOS. McLean-Pontiff (2016): post-publication decay ~30%.

## Capacità Oracle esistente

- ✅ `analytics/strategy/catalog/value.py` — PiotroskiFScore, GreenblattMagicFormula, LakonishokValueMomentum
- ✅ `analytics/fundamental/simfin_loader.py` — SimFin bulk 185 tickers US (income/balance/cashflow + prices)
- ✅ `analytics/strategy/lane_b_backtester.py` — Lane B con `CompositeLaneBScore` (Piotroski 40% + Greenblatt 40% + Lakonishok 20%, threshold 0.65)
- ✅ Lane B backtest 2020-2025: Sharpe 0.93, annual 19.2%, alpha +59% vs SPY (vedi `composite-lane-b-default-2026-08-17` memory)

## Gap da colmare

1. **SEC EDGAR bulk adapter** — free $0, illimitato, raw XBRL. SimFin ha 185 tickers + 5y history. EDGAR dà 6.000+ tickers US dal 1993. TODO BL-KB-01
2. **Altman Z-score** (1968, 72% accuracy bankruptcy prediction) — NON implementato. Da aggiungere a catalog/value.py. TODO BL-KB-02
3. **Sloan accrual anomaly** (1996) — non implementato. Da aggiungere. TODO BL-KB-03
4. **PEAD signal** (Piotroski-So 2012) — non implementato. Richiede earnings dates + surprise. TODO BL-KB-04
5. **Novy-Marx gross profitability** — non in catalog. (gross profit / assets). TODO BL-KB-05
6. **Fama-French 5-factor regression** — per misurare alpha residuo di Lane B. TODO BL-KB-06
7. **Shiller CAPE** — market timing signal a 10y orizzontale. Non implementato. TODO BL-KB-07
8. **Fundamental momentum** (Chen-Lakonishok 2020) — combo price+earnings+revenue momentum. Non in catalog. TODO BL-KB-08

Vedi [literature.md](literature.md) per dettaglio paper + citazioni, [data-audit.md](data-audit.md) per fonti free, [edge.md](edge.md) per edge plausibility, [capability-map.md](capability-map.md) per implementazione Oracle.
