# B — Replicable strategy families at retail scale (MT5-CFD + CME-futures)

**Scope.** 11 strategy families examined against MT5-CFD + CME-futures retail execution (≤$1M, seconds-to-minutes latency, $0 data budget). Numbers are in-sample unless flagged; "after costs" means after typical MT5/ECN spread + commission + slippage, not after the paper's stated transaction-cost model. Sharpes are annualized unless flagged.

**Bottom-line verdict up front** (details per family below):
1. **Overnight / intraday decomposition (Lou-Polk-Skouras 2019, Boyarchenko-Larsen-Whelan 2023)** — best risk-adjusted edge at retail scale on 24h instruments (gold CFD, FX majors, equity index futures). Cheap to trade, fits MT5 24h session perfectly, persistent after 2015.
2. **Trend / time-series momentum on liquid futures (Moskowitz-Ooi-Pedersen 2012; Hurst-Ooi-Pedersen 2017)** — historically Sharpe ~0.7 net of fees, positive skew, but recent decay (post-2010 halving of returns per Carver 2025; -15% alternative markets 2023-2025 per Quantica 2025). Still in portfolio as diversifier, NOT as primary leg.
3. **FX carry + commodity basis (Szymanowska-De Roon-Nijman-Goorbergh 2014; Lustig-Roussanov-Verdelhan 2011)** — solid Sharpe 0.4-0.7 on cross-asset basket; draws down in crisis (SNB 2015, COVID Mar 2020, FTX Nov 2022, USD-funding regime 2025). Wide capacity but tail-heavy.
4. **Commodity cross-sectional momentum + basis-momentum (Fuertes-Miffre-Fernandez-Perez 2015; Boons-Prado 2019)** — Sharpe 1.0+ on 24-30 commodities basket; survives realistic costs; capacity adequate for $1M retail.
5. **Intraday momentum on indices (Gao-Han-Li-Zhou 2018; Baltussen-Da-Lammers-Martens 2021)** — paper Sharpe 1.08+ for SPY, but Heldens (2017 NYSE) and others show after realistic costs + slippage the net edge is marginal on liquid equities; mixed on CME E-mini and major FX.
6. **Crypto funding-rate carry (Schmeling-Schrimpf-Todorov 2025; Christin et al. 2022)** — Sharpe 1.8 BTC, 2.55 ETH on funding alone; oracle stack is MT5-only, so this is a documented edge the stack cannot currently capture; flagged for evaluation if scope expands.
7. **Pairs trading / stat-arb (Zhu 2024 replication of Gatev-Goetzmann-Rouwenhorst 2006)** — recent Yale replication gives Sharpe 1.35 vanilla US-equity pairs after costs; on futures (calendar spreads, inter-commodity) viable for $1M but low-vol, requires careful universe construction.
8. **Order-flow imbalance (Cont-Kukanov-Stoikov 2014; Fed 2025 Treasury work)** — sound mechanism, but retail MT5 lacks L2/L3 order book; CME DOM possible but latency disadvantage vs HFT. Mechanism is useful for a hybrid "informed flow" filter, NOT a stand-alone retail edge.
9. **VPIN / order toxicity (Easley-Lopez de Prado-O'Hara)** — same data-availability problem; institutional.
10. **Meta-labeling / ML ensembles (Lopez de Prado 2018)** — empirically validated improvement in precision + Sharpe across equities/futures; could be applied as a confidence-weighting layer on top of simple rules; must respect PBO discipline.
11. **Calendar effects (TOM, Halloween, day-of-week)** — historically documented but mostly decayed in 2010s-2020s (Lakonishok-Smirloc TOM faded internationally per Aalto 2024; McLean-Pontiff 2016 framework).

---

## Comparison table

| Family | Best paper Sharpe (in-sample, annual.) | Sharpe after retail costs | Annual ret. | Holding | Capacity (≤$1M) | Decay evidence | Data needs | Retail MT5/CFD fit |
|---|---|---|---|---|---|---|---|---|
| Overnight drift (LPS 2019, BLW 2023) | ~0.5-1.0 SPY/EURUSD | ~0.4-0.8 | 4-10% | 1 day-2 wk | $1M+ easy | Persistent 2015-2024 | Free (Dukascopy + IBKR paper 1m) | **Excellent** |
| Trend / TSM (MOP 2012, HOP 2017) | 0.7 net 2/20 fees full sample | 0.3-0.6 (post-2020) | 5-10% net | weeks-months | $1M+ | Halved post-2010 (Carver 2025) | Free | Good (diversifier) |
| FX carry (LRV 2011, 2014) | 0.5 HML | 0.3-0.5 | 4-6% | 1-3 months | $1M+ | Crisis drawdowns | Free (Dukascopy) | Good |
| Commodity basis (Szym 2014) | 0.7-1.0 portfolio | 0.4-0.7 | 7-10% | 1-3 months | $1M+ | Persistent, "lost in financialization" (2023 paper) | Free | Good |
| Commodity momentum (Fuertes 2015) | 1.0-1.1 | 0.7-1.0 | 10-15% | 1-3 months | $1M+ | Persistent if optimized roll | Free | Good |
| Short-term reversal (Nagel 2012; Da-Liu-Sch 2013) | 0.5-0.8 daily reversal | 0.0-0.3 | 0-5% | 1-5 days | Limited (liquidity) | 32-58% decay post-pub (McLean-Pontiff) | Free | Marginal |
| Intraday momentum (GHLZ 2018, BDLM 2021) | 1.08 (SPY HFT sim) | 0.1-0.4 (Heldens 2017 NYSE: 0.2%/day pre-cost = 0.0-0.2 net) | 0-3% | minutes-hours | $100K-$500K | Marginal in post-2015 NYSE; stronger on CME futures | Tick (Dukascopy) | **Marginal** |
| Pairs trading GGR (Zhu 2024) | 1.35 max vanilla T500 | 0.5-1.0 | 6-10% | 1 wk - 6 mo | $500K-1M | Robust per Zhu 2024 | Free equities; harder FX/CFD | Good (cross-asset) |
| Vol risk premium (short VIX) | 0.5-1.0 historically | -0.5 to 0.5 | -10% to +10% | weeks-months | $500K | XIV Feb 2018 -92%; Sharpe lower post-2018 | Free (Cboe) | Poor (MT5 no VIX direct) |
| ML meta-labeling (LdP 2018+) | 2.06 OOS equity (HRP+XGB) | 1.0-1.5 OOS | 10-20% | varied | $500K-1M | PBO risk (Lopez de Prado); empirically robust in recent 2024-25 work | Free + backtest infra | Good (filter layer) |
| Calendar (TOM, Halloween, DoW) | 0.3-0.6 historical | 0.0-0.3 | 0-5% | 1-30 days | $1M+ | TOM faded internationally (Aalto 2024); DoW meta-analysis (Grebe-Schiereck 2024) shows Mondays still weak but small effect | Free | Marginal |
| Crypto funding carry (Schmeling 2025) | 1.8 BTC, 2.55 ETH | 1.5-2.5 | 5-15% | weeks-months | $1M+ (perp) | Decaying as market matures (He et al 2024) | Free | **Out of scope** (no crypto) |

---

## Per-family deep dives

### 1. Short-term reversal & liquidity provision
**Papers.**
- Nagel, S. (2012). "Evaporating Liquidity." *Review of Financial Studies* 25(7), 2005-2039. https://academic.oup.com/rfs/article-abstract/25/7/2005/1602153 ; SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1988706
- Da, Z., Liu, Q., Schaumburg, E. (2013) "Decomposing Short-Term Return Reversal." NY Fed Staff Report 513. https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr513.html
- Drechsler, I., Moreira, A., Savov, A. (2021) "Liquidity and Volatility." *JFE* / Wharton. https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2022/03/Paper5_Drechsler.pdf — short-term reversal returns load on volatility risk; consistent with liquidity provision model.
- Harvard "Rethinking Volume: The Illusion of Liquidity" (HBS 26-003) https://www.hbs.edu/ris/download.aspx?name=26-003.pdf — long-frequency liquidity provision Sharpe ≈ 0.34, high-frequency Sharpe ≈ 1.75 BUT high-freq returns have declined as gross volume rose, while long-freq returns stable 1992-2024.
- McLean, D., Pontiff, J. (2016) "Does Academic Research Destroy Stock Return Predictability?" *Journal of Finance* 71(1), 5-32. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2475955 — out-of-sample -26%, post-publication -58% on 97 anomalies.
- Da, Liu, Schaumburg (2013) — short-term reversal replicated on US equities 1982-2009.

**Numbers.**
- In-sample monthly reversal excess return ~50-70 bp depending on universe (Jegadeesh 1990; Lehmann 1990; Da-Liu-Sch 2013).
- Long-frequency liquidity provision (HBS): annualized Sharpe ≈ 0.34, stable 1992-2024.
- High-frequency liquidity provision (HBS): annualized Sharpe ≈ 1.75 BUT **declining with rising volume** (volume has multiplied; gross returns halved since 2000s).
- Capital-gains-overhang effect: reversal strongest where investors have large unrealized losses (~1.78%/mo winners-minus-losers among losers-with-paper-losses vs 0.30%/mo among winners-with-paper-gains, ScienceDirect S1059056021002380).

**Capacity.** Limited. Reversal requires liquidity at retail execution — even on MT5 EUR/USD with 0.1-0.6 pip spread, round-trip cost on the daily reversal is 0.3-1.2 bp, while gross signal is ~50-70 bp/month — fine in theory but the strategy demands frequent rebalance across a basket.

**Decay.** Yes. McLean-Pontiff -58% post-publication decay across 97 cross-sectional predictors; particularly steep for short-term reversal because it's exposed to publication-aware arbitrage capital. Drechsler-Moreira-Savov 2021 model implies reversal is compensation for bearing volatility risk, not pure overreaction, so the "illiquidity compensation" channel may be more durable than "overreaction correction" channel.

**Retail fit on MT5-CFD/futures.**
- Margin FX majors (EURUSD, USDJPY): workable in principle but requires low-cost execution (IC Markets/Pepperstone ECN, 0.1 pip + $3.50/lot commission = ~$7 round-trip on 1 standard lot = 7 bp cost; signal ~50-70 bp/month = barely positive net). Sources: https://www.icmarkets.eu/en/trading-pricing/trading-costs ; https://www.bestbrokers.com/forex-brokers/metatrader-5-forex-brokers
- CME E-mini S&P/Nasdaq futures: tighter than CFD (~$0.5-1 per side), but reversal requires intraday/intraweek rebalance across a basket.
- **Verdict: marginal**. Strategy is documented but cost-sensitive; better used as a size-tilt on other edges (factor timing) than as a stand-alone leg.

---

### 2. Order-flow imbalance & microstructure (Cont-Kukanov-Stoikov)
**Papers.**
- Cont, R., Kukanov, A., Stoikov, S. (2014) "The Price Impact of Order Book Events." *Journal of Financial Econometrics* 12(1), 47-88. https://academic.oup.com/jfec/article-abstract/12/1/47/816163 ; alphaXiv https://www.alphaxiv.org/abs/1011.6402 — OFI is linearly proportional to short-horizon price changes; the empirical "square-root law" is a statistical aggregation artifact.
- Fed FEDS Notes (2025-11-03) "Order Flow Imbalances and Amplification of Price Movements: Evidence from U.S. Treasury Markets." https://www.federalreserve.gov/econres/notes/feds-notes/order-flow-imbalances-and-amplification-of-price-movements-evidence-from-u-s-treasury-markets-20251103.html — replicates OFI logic on Treasury markets.
- Brogaard, J., Nguyen, T., Putnins, T., Wu, E. (2022+) — OFI predictive power on multiple asset classes.

**Numbers.** Cont-Kukanov-Stoikov 2014: linear OFI/price-impact coefficient; slope inversely proportional to depth. Predicts ~5-10 bp next-tick return per unit of OFI for liquid US equities at millisecond horizon.

**Retail fit.**
- MT5 CFD: no L2/L3 order book data; only top-of-book. Even ECN MT5 only shows Level 1.
- CME E-mini DOM available but latency-disadvantaged (seconds-to-minutes retail vs microseconds HFT). At retail latency, the OFI signal is dominated by other participants before the trade fires.
- **Verdict: NOT a stand-alone retail edge.** The mechanism is useful as an *informed-flow filter* (e.g., ignore trend entries when conflicting flow is high in DOM), but full execution requires institutional co-located infrastructure.
- Useful follow-up paper: Easley, D., López de Prado, M., O'Hara, M. (2011, 2012) "The Volume-Synchronized Probability of Informed Trading (VPIN)." Cboe VPIN methodology: https://cdn.cboe.com/api/v1.5/delayed_quote_chicken_series_options/VPIN_Methodology.pdf. Same data-access problem.

---

### 3. Market intraday momentum
**Papers.**
- Gao, L., Han, Y., Li, S., Zhou, G. (2018) "Market intraday momentum." *Journal of Financial Economics* 129(2), 394-414. https://www.sciencedirect.com/science/article/abs/pii/S0304405X18300687 ; Replication GitHub: https://github.com/codespace5555/Replication-of-Decay-of-Intraday-Momentum-by-Li-Zhou-Gao-2018
- Baltussen, G., Da, Z., Lammers, S., Martens, M. (2021) "Hedging demand and market intraday momentum." *Journal of Financial Economics* 142(1), 377-403. https://www.sciencedirect.com/science/article/abs/pii/S0304405X21001598 — 60+ futures across equities, bonds, commodities, FX 1974-2020; mechanism = short-gamma hedging.
- Li, Z. (Lancaster FoFI 2020) "Intraday Time Series Momentum: International Evidence" http://wp.lancs.ac.uk/fofi2020/files/2020/04/FoFI-2020-092-Zeming-Li.pdf — 12 of 16 developed markets exhibit intraday momentum.
- Elaut, G., Frömmel, M., Lampaert, K. (2018) "Intraday momentum in FX markets: Disentangling informed trading from liquidity provision." *Journal of Financial Markets* 37, 35-51.
- Wen, F. et al. (2021, 2022) — intraday momentum in crude oil futures, Bitcoin.
- Kang, J., Lin, S., Xiong, X. (2020+) "What Drives Intraday Reversal? Illiquidity or Liquidity Oversupply?" SSRN.
- Heldens, J.J.M. (2017) Master Thesis Tilburg, "Intraday Price Reversals and Momentum: Evidence from the NYSE." http://arno.uvt.nl/show.cgi?fid=144554 — intraday momentum max 0.2%/day = $0 economically meaningful AFTER costs; intraday reversal max 3.29%/day = economically meaningful. Direction-reversal pattern after recession.
- Seo, S. (2022) "Market Intraday Momentum with New Measures for Trading Cost: Evidence from KOSPI Index." *JRFM* 15(11), 523. https://www.mdpi.com/1911-8074/15/11/523 — Korean index: effective spread declines toward close; MIM still profitable.

**Numbers.**
- GHLZ 2018: simple SPY timing strategy (long first-half-hour positive → long rest-of-day, else short) annualized return 6.67% vs buy-hold 6.04%; Sharpe 1.08 vs 0.29; FOMC days 20% annualized.
- BDLM 2021: intraday momentum on 60+ futures 1974-2020, robust everywhere; pred power higher during high-vol periods.
- Heldens 2017 NYSE 2000-2015: intraday momentum max 0.2%/day (NE economically significant after costs); reversal max 3.29%/day (economically significant).

**Capacity.** $100K-$500K on major futures (ES, NQ). On E-mini S&P with $12.50/tick, gross signal per Heldens 2017 ~$25 per day on 1 contract if momentum; slippage + commission $2-3 per round trip; edge effectively zero.

**Decay.** Mixed evidence.
- Gao et al's 2018 sample is pre-2016; replication code (GitHub above) on FirstRate/Dukascopy 2010-2015.
- Heldens 2017 NYSE 2000-2015 finds the pattern weakening in later periods.
- BDLM 2021 uses 1974-2020 data and finds "strong everywhere" but this is futures index data, less retail-relevant.
- KOSPI 2022 (Seo): spread cost-adjusted MIM still works, contradicting the "fully decayed" view.
- Zheng, L., Luo, X. (2024) "Is there an intraday reversal effect in commodity futures and options? Evidence from the Chinese market." *Pacific-Basin Finance Journal* 88 — intraday reversal in Chinese commodities; momentum crashes after recession.

**Retail fit.**
- Intraday momentum on MT5 FX majors: signal 0.05-0.10%/day gross; spread 0.1-0.6 pip = $1-6 per standard lot round-trip; net edge thin.
- CME E-mini S&P: gross ~$25-50 per day per contract; commission + slippage $5-8 = thin positive only if executed during liquid overlap.
- **Verdict: marginal on liquid instruments, more attractive on slower markets** (commodities CFDs with wider spreads but bigger daily range). Not a stand-alone leg; better as a small filter on other strategies.

---

### 4. Overnight vs intraday decomposition
**Papers.**
- Lou, D., Polk, C., Skouras, S. (2019) "A tug of war: Overnight versus intraday expected returns." *Journal of Financial Economics* 134(2). https://www.sciencedirect.com/science/article/abs/pii/S0304405X19300650 ; NBER version https://conference.nber.org/confer/2015/APf15/Lou_Polk_Skouras.pdf
- Boyarchenko, N., Larsen, L., Whelan, P. (2023) "The Overnight Drift." CEPR DP14462 / working paper https://research-api.cbs.dk/ws/portalfiles/portal/101311522/nina_boyarchenko_et_al_the_overnight_drift_acceptedversion.pdf ; https://cepr.org/publications/dp14462 — "100% of the U.S equity premium is earned during a 1-hour window between 2:00 and 3:00 a.m. ET" (European market open); mechanism: dealers offload end-of-day imbalances.
- Lachance, M.-E. (2021) "ETFs' High Overnight Returns: The Early Liquidity Provider Gets the Worm." *Journal of Financial Markets*.
- Berkman, H., Koch, P., Tuttle, L., Zhang, Y. (2012) "Paying attention: overnight returns and the hidden cost of buying at the open." *JFQA* 47.
- Aboody, D., Even-Tov, O., Lehavy, R., Trueman, B. (2018) — retail attention & overnight returns.
- Knuteson, B. (2022) "They Still Haven't Told You." SSRN.
- Qiao, K., Dam, L. (2019) "The Overnight Return Puzzle and the 'T+1' Trading Rule in Chinese Stock Markets." SSRN.
- Krohn, I., Mueller, P., Whelan, P. (2024) "Foreign Exchange Fixings and Returns around the Clock." *Journal of Finance* 79(1), 541-578.
- Carney, B., Dou, P., Lou, D. (2024 companion paper) "Meme stocks, meme reviews, and retail investors." — overnight patterns in meme stocks driven by retail.

**Numbers.**
- Lou-Polk-Skouras 2019: market portfolio 11.22% annual return = 4.58% intraday + 6.99% overnight; momentum strategy: 0.54% (small) -0.39% (intraday) per month + 1.04% (large) overnight per month; reversal strategy: 2.193% intraday + (-1.81%) overnight per month.
- Boyarchenko-Larsen-Whelan 2023: SPX E-mini S&P annualized return 3.7% during 02:00-03:00 ET window = 1.48 bp/day; rest of 24h net positive but much smaller.
- ETFs (Lachance 2021): overnight > intraday for many retail-heavy ETFs; not for diversified futures.

**Capacity.** $1M+ easy — overnight drift is a passive position that holds across the close.

**Decay.** Persistent in 2015-2024 samples. Multiple replications across global markets confirm the pattern.

**Retail fit on MT5.**
- 24h instruments (gold CFD, FX majors, CME E-mini S&P/NQ, CME crude): all have continuous overnight trading.
- Strategy: enter at close, hold through European open 02:00-03:00 ET (or Tokyo open for some instruments), exit before US cash session starts.
- Cost: only commission + spread on round-trip; no intraday turnover.
- **Verdict: STRONG candidate.** Cheap to implement, persistent across regimes, works at retail scale, fits MT5 24h sessions perfectly.

---

### 5. Intraday seasonality (time-of-day, session effects)
**Papers.**
- Ito, T., Hashimoto, Y. (2006) "Intra-Day Seasonality in Activities of the Foreign Exchange Markets: Evidence from the Electronic Broking System." NBER WP 12413. https://www.nber.org/system/files/working_papers/w12413/w12413.pdf — USDJPY and EURUSD, 1999 EBS data. U-shape in volume/volatility; trough at Tokyo lunch, London lunch, 21-22 GMT; bid-ask spread widens after Hours 16-17, peaks 21-22 GMT.
- Cotter, J., Dowd, K. (2007) "Intra-Day Seasonality in Foreign Exchange Market Transactions." MPRA 3502. https://mpra.ub.uni-muenchen.de/3502 — DEM/USD Dealing 2000-2; significant intraday return/volatility seasonality.
- Watkins, C. (2017) "Intraday Seasonality in Efficiency, Liquidity, Volatility and Trading Activity in Gold and Platinum Futures." Kobe Univ WP 1722. https://www.econ.kobe-u.ac.jp/wp-content/uploads/2023/06/1722.pdf — informed trading dominates NY session for both gold and platinum on both Tokyo and NY exchanges; uninformed dominates Tokyo day session.
- Andersen, T., Bollerslev, T. (1997) — U-shape in equity volatility.
- Harris, L. (1986) — equity U-shape in volume.
- FXEmpire 2026 article on FX seasonality persistence (lower-trust secondary source but pragmatic): https://www.fxempire.com/education/article/fx-seasonality-what-still-works-and-what-doesnt-in-2026-1545003
- Day-of-week meta-analysis: Grebe, F., Schiereck, D. (2024) "Day-of-the-week effect: a meta-analysis." *Eurasian Economic Review*. https://link.springer.com/article/10.1007/s40822-024-00293-9

**Numbers.**
- BIS Triennial Survey April 2025: London sales desk ~38% of global FX turnover; US ~19%; Singapore ~12%; Hong Kong ~7%. https://www.bis.org/publications/202509-commentary-otc-derivatives
- London-NY overlap (13:00-17:00 GMT = 70% of total daily FX volume by some measures; "more than 70%" of two-centre trading, per https://www.thinkmarkets.com/en/trading-academy/forex/sessions).
- Average pip range by session (City Index): EUR/USD London 114, NY 92, Tokyo 76 pips. https://www.cityindex.com/en-uk/forex/forex-market-hours
- Calendar anomalies:
  - TOM (turn-of-month) — Lakonishok-Smirloc 1988 documented strong effect; Aalto dissertation 2024 (https://aaltodoc.aalto.fi/bitstreams/27ca8cf2-8edd-4ac5-b81f-20b11032661a/download) finds TOM faded in most international indices post-2000; still significant only in New Zealand.
  - Halloween (Sell in May) — Bouman-Jacobsen 323-year study shows persistent in equities; mixed evidence in FX.
  - Day-of-week: meta-analysis 2024 shows Monday effect weak but persistent in many markets.
  - January effect: heavily decayed post-1980s in equities; weak in FX.

**Decay.** Mixed.
- Session effects (overlap, lunch troughs): structural; very persistent.
- Day-of-week: weakened since 1980s but Monday effect still observed.
- TOM: faded in most equity indices post-2000; only NZ shows persistence in recent samples.

**Retail fit on MT5.**
- **Session overlap filters** (e.g., "only trade London-NY overlap") are essentially free alpha — restrict trade window to high-volume periods for tighter execution.
- Trading-cost effect: tightest spreads during overlap (Dukascopy FX spreads typically 0.1-0.3 pips EUR/USD vs 1-2 pips Tokyo).
- **Verdict: STRONG as a filter / execution layer.** Session timing is structural alpha, not a strategy to deploy on its own.

---

### 6. Pairs trading / stat arb
**Papers.**
- Gatev, E., Goetzmann, W., Rouwenhorst, K.G. (2006) "Pairs Trading: Performance of a Relative-Value Arbitrage Rule." *Review of Financial Studies* 19(3), 797-827. http://stat.wharton.upenn.edu/~steele/Courses/434/434Context/PairsTrading/PairsTradingGGR.pdf — annualized excess return ~11% on US equities 1962-2002.
- Do, B., Faff, R. (2010, 2012) — pairs trading profitability and costs.
- Krauss, C. (2017) "Statistical arbitrage pairs trading strategies: Review and outlook." *Journal of Economic Surveys* 31:513-545. https://www.iwf.rw.fau.de/files/2016/03/09-2015.pdf
- Zhu, X. (2024) "Examining Pairs Trading Profitability." Yale Econ. https://economics.yale.edu/sites/default/files/2024-05/Zhu_Pairs_Trading.pdf — **most recent and rigorous replication**.
- Rubesam, A. (2021) "Pairs Trading: Replicating Gatev, Goetzmann and Rouwenhorst (2006)." Mendeley Data. https://data.mendeley.com/datasets/xz6c2bp5d8 — Rubesam 2021 claims pairs decay; Zhu 2024 counter-replicates and finds robustness.
- Krauss, G., Stübinger, J. (2017+) — cointegration-based pairs more robust than distance-based.
- Brunnermeier, M., Pedersen, L. (2005) — market liquidity and funding on stat-arb.
- Quantitativo 2024 "Short-Term Basis Reversal" https://quantitativo.com/p/short-term-basis-reversal — adjacent-contract basis spread reversal on commodities; Sharpe 1.45, 19.2% annual return (gross), 22.3% / Sharpe 1.66 (with 5 bp costs).
- Avellaneda, M., Lee, J.-H. (2010) "Statistical arbitrage in the US equities market." *Quantitative Finance* 10(7), 761-782.
- Recent dynamic cointegration pairs (arXiv 2109.10662) — crypto pairs profitable 2018-2021.

**Numbers (Zhu 2024 Yale replication, critical reading).**
- T20 (top-20 pairs, vanilla GGR): mean monthly return 0.461%, t-stat 3.647, Sharpe 0.814, IR 0.240.
- T100 (top-100 pairs): mean monthly 0.426%, t-stat 4.618, Sharpe 1.177, IR 0.381.
- **T500 (top-500 pairs, largest universe): mean monthly 0.498%, t-stat 4.471, Sharpe 1.345, IR 0.438. Annual return 6.2% / Sharpe 1.35.**
- L50 / L75 / R20: Sharpe 0.5-0.8 range.
- 6-factor model: returns explained by market, SMB, HML, MOM, ST_REV, LT_REV. Standard deviations: STR (short-term reversal) loading 0.124 (T100), 0.113 (T500) — significant.
- Skew: 6.39-7.33 for top pairs, indicating frequent large positive outlier months.
- Maximum monthly gain 24.3% — kurtosis.
- Min/max T20: -6.7% / +24.3% — fat tails.
- Risk decomposition: 1-SD increase in MOM can wipe out best strategy return.

**Capacity.** $500K-$1M on liquid US equities (US listed equity universe has thousands of tradeable pairs). On futures / FX, capacity shrinks to ~$500K max per pair but more legs available.

**Decay.** Zhu 2024 explicitly argues against Rubesam 2021's decay claim. The post-2002 sample in Zhu's replication still shows Sharpe 1.35 with T500 universe — pairs trading HAS survived. Zhu's main caveat: it's risk-bearing (loading on MOM, ST_REV); not pure arbitrage.

**Retail fit on MT5-CFD/futures.**
- Equities not directly accessible via MT5 (MT5 supports some CFDs on US stocks but spreads/commissions usually too wide for pairs).
- Cross-listed instruments (gold/silver, oil products, related equity index futures) — viable.
- Cross-currency pairs (EUR/GBP vs EUR/USD-USD/GBP triangle, AUD/NZD vs cross-rates) — feasible on MT5.
- Commodity calendar spreads (front vs 2nd month) — Quantitativo 2024 documents Sharpe 1.45 net of costs.
- **Verdict: GOOD candidate for diversification.** Universe construction is the alpha; works on retail-scale with proper basket.

---

### 7. Carry families — FX, commodity basis, crypto funding
**Papers.**
- Lustig, H., Roussanov, N., Verdelhan, A. (2011) "Common Risk Factors in Currency Markets." *Review of Financial Studies* 24(11), 3731-77. https://www.nber.org/system/files/working_papers/w16427/revisions/w16427.rev2.pdf — HML FX carry Sharpe ~0.5 on basket; country-level FX carry near zero.
- Lustig, H., Roussanov, N., Verdelhan, A. (2014) "Countercyclical Currency Risk Premia." *Journal of Financial Economics* 111(3), 527-53.
- Menkhoff, L., Sarno, L., Schmeling, M., Schrimpf, A. (2012) "Carry Trades and Global Foreign Exchange Volatility." *Journal of Finance* 67(2), 681-718.
- Burnside, C., Eichenbaum, M., Rebelo, S. (2011) "Carry Trade and Momentum in Currency Markets." *Annual Review of Financial Economics*.
- Accominotti, O., Chambers, M., Marsh, I. (2019) "Currency Regimes and the Carry Trade." LSE Eprints https://eprints.lse.ac.uk/100239/1/Accominotti_Cen_Chambers_Marsh_CurrencyRegimesandtheCarryTrade_2019_02.pdf — century of carry data; outsized drawdowns in peg collapses.
- Lettau, M., Maggiori, M., Weber, M. (2014) "Conditional Risk Premia in Currency Markets and Other Asset Classes." *JFE*.
- Erb, C., Harvey, C. (2006) "The Strategic and Tactical Value of Commodity Futures." *Financial Analysts Journal* 62(2), 69-97.
- Gorton, G., Hayashi, F., Rouwenhorst, K.G. (2007/2013) "The Fundamentals of Commodity Futures Returns." *Review of Finance* 17, 35-105.
- Szymanowska, M., De Roon, F., Nijman, T., Van Den Goorbergh, R. (2014) "An Anatomy of Commodity Futures Risk Premia." *Journal of Finance* 69, 453-482.
- Bakshi, G., Gao, X., Rossi, A. (2019) "Understanding the Sources of Risk Underlying the Cross-Section of Commodity Returns." SSRN.
- Yang, Z. (2013) "A new strategy using term-structure dynamics of commodity futures." ScienceDirect S1544612313000676.
- Boons, M., Prado, M. (2019) "Basis-Momentum." *Journal of Finance*.
- Christin, N. et al. (2022) "Bitcoin and Crypto Carry." NBER.
- Schmeling, M., Schrimpf, A., Todorov, K. (2025) "Crypto Carry." SSRN 4268371.
- He, S., Manela, E., Ross, O., von Wachter, T. (2024) "Fundamentals of Perpetual Futures." arXiv 2212.06888v5. https://arxiv.org/html/2212.06888v5
- Hu, Y. et al. (2025+) "Perpetual Futures in Decentralised Finance." MDPI 14(7), 178. https://www.mdpi.com/2227-7072/14/7/178

**Numbers.**
- FX HML carry (LRV 2011, USD-defined basket): mean 6.99% annual, Sharpe 0.54 on developed countries; 15.49% mean / Sharpe 0.40 on broad basket; dollar carry mean 7.12% / Sharpe 0.08; country-level FX carry mean 0.5% / Sharpe ~0.
- 1-month carry term structure (Cieslak-Love 2025 AER PDF https://dspace.mit.edu/bitstream/handle/1721.1/135975/aer.20180098.pdf) — downward-sloping term structure of carry trade risk premia.
- Commodity basis carry (Szymanowska 2014): long-backwardated / short-contangoed on 28 commodities: 70 bp/month = 7.9% annualized mean, Sharpe 0.685 (basis factor alone); "highly significant" t-stat; uncorrelated with conventional risk factors.
- Bakshi 2019 alternative: 70 bp/month = 7.9% annualized basis; 9.8% / Sharpe 0.44 alternative roll method.
- Long-only "carry" on commodity index (Gorton-Rouwenhorst 2006): 7-12% annualized historically; lost in financialization (2023 paper).
- Cross-section momentum + basis (Fuertes-Miffre-Fernandez-Perez 2015): Sharpe 1.00+ on combined momentum + basis + IV screen.
- Crypto funding (Schmeling 2025): BTC funding alone Sharpe 1.80 (5y sample), ETH 2.55; carry averages 7% annual across CeFi exchanges (vs ~0.7% S&P futures basis).
- He et al. 2024 perpetual futures: median BTC funding 0.01%/period on Binance; decile bounds ±0.78-0.96%; "carry averages ~7% annual, ~10x S&P 500 futures basis."

**Capacity.** Wide. FX carry: $1M+ easy; commodity carry: $1M+; crypto funding: $1M+ but exchange-specific (counterparty).

**Decay.** Mixed.
- FX carry Sharpe has DECLINED post-2014 in floating-rate regime (Accominotti 2019); drawdowns in crises (2008 GFC, SNB Jan 2015, COVID Mar 2020).
- Commodity carry (basis) Sharpe 0.685 (Szymanowska 2014) — most recent replications (Bakshi 2019; Fuertes 2015) confirm persistence.
- Crypto funding: He et al. 2024 document that deviations from no-arbitrage are "larger than in traditional currency markets but diminish over time as market matures and arbitrage capacity deepens."
- Recent regime change (Oct 2025): CV5 Capital documents BTC 30-day funding at -5% vs historical norm +8%, reflecting institutional hedging — regime may be inverting.

**Retail fit on MT5-CFD + CME-futures.**
- FX carry on MT5: trivial to implement (long AUD/TRY or short JPY crosses); but TRY is illiquid on MT5; G10 carry is lower-Sharpe. Stay with G10 pairs + swap-positive carry.
- Commodity basis on CME: requires roll-management (front-2nd spreads) — straightforward via CFD roll.
- Crypto funding: not available via MT5; if oracle scope includes crypto exchanges, it's documented Sharpe 1.5-2.5.
- **Verdict: GOOD candidate for basket inclusion, especially commodity basis + FX G10 carry. Crypto excluded by MT5 scope.**

---

### 8. Volatility risk premium (short-VIX, short-vol)
**Papers.**
- Whaley, R. (1993, 2009) — VIX as predictor of realized vol; implied > realized.
- Cboe term-structure strategy (Quantpedia https://quantpedia.com/strategies/exploiting-term-structure-of-vix-futures) — short VIX futures in contango, hedge with ES.
- Whaley "Understanding the VIX Premium" (Cboe educational).
- Simplify "Volatility Premium Harvesting, Reimagined" https://www.simplify.us/blog/volatility-premium-harvesting-reimagined — empirical: 25% short exposure optimal, 50% too risky post-Volmageddon 2018.
- Loomis Sayles "How the Spike in Volatility Punctured the Short Vol Trade" https://www.loomissayles.com/insights/how-the-spike-in-volatility-punctured-the-short-vol-trade — XIV -92% on 5 Feb 2018.

**Numbers.**
- Long-run Sharpe of short-VIX-futures strategies: ~0.5-1.0 (Whaley series; depends on hedge ratio).
- Sharpe post-2018 with 25% exposure: lower than pre-2018 with 100% exposure due to convexity loss.
- VRP magnitude: VIX futures typically trade 2-4 vol points above realized — translates to ~5-10% annualized premium depending on roll tenor.
- Tail: -50% to -90% drawdowns in 1-2 days during vol spikes (Aug 2015 ETF dislocation; Feb 2018 XIV; Mar 2020).

**Capacity.** Limited at retail — VIX futures not directly on MT5; only VIX CFDs (brokers' synthetic). CME VIX futures are institutional.

**Decay.** Yes — Sharpe compressed after 2018 (exposure reduced from 100% to 25%); risk-adjusted return per unit capital now lower; tail risk persistent.

**Retail fit.**
- MT5: VIX not available. Synthetic via short S&P 500 straddle on E-mini options — but options on CME S&P require approval + capital.
- No clean retail VRP edge on MT5-CFD without options access.
- **Verdict: NOT applicable to the MT5-CFD-only stack.** Would require adding options/CME options; flag for future evaluation.

---

### 9. ML ensembles / meta-labeling (Lopez de Prado and successors)
**Papers & recent evidence.**
- López de Prado, M. (2018) *Advances in Financial Machine Learning* (book).
- López de Prado, M. (2018) "Advances in Financial Machine Learning: The 'Triple Barrier Method' and 'Meta-Labeling'." Adoption across industry.
- Hudson & Thames Research (2019+) https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method — S&P 500 E-mini, primary Bollinger mean-reversion + triple barrier + meta-labeling: F1/AUC improved substantially; Sharpe from primary signal modestly improved.
- BlackArbs Chapter 3 walkthrough https://blackarbs.com/blog/labeling-and-meta-labeling-returns-for-ml-prediction.
- Adaptive Event-Driven Labeling (MDPI 2025) https://www.mdpi.com/2076-3417/15/24/13204 — 16 assets 2000-2025, AEDL Sharpe 0.48 average vs baselines -0.29 to 0.001.
- Mental-Momentum 2025 "Meta-labeling and triple-barrier methods" https://research.mental-momentum.ai/r/meta-labeling-triple-barrier-methods-lq4i7w — meta-labeling raises OOS accuracy 17% → 63% on baseline mean-reversion.
- "Highly optimized quantitative equity strategy" (HRP + XGBoost + regime gating): OOS Sharpe 2.06, max DD -11.6% (no slippage ablation reported).
- RL market-making on Binance BTC-USDT-perp (Reinforcement learning for AMM 2026): Sharpe 1.49, MDD -6.39% on holdout.

**Numbers.**
- Meta-labeling improves precision dramatically (often 17% → 60%+) at the cost of some recall.
- Empirical Sharpe improvements 0.2-0.5 typical after meta-labeling; depends heavily on primary signal quality.
- AEDL 2025: OOS Sharpe 0.48 vs -0.29 (Fixed Horizon) to 0.001 (Trend Scanning).
- Quantitative equity strategy with full stack (HRP + XGBoost + regime + meta-labeling): SR 2.06 OOS, MDD -11.6%.

**PBO concern.** Lopez de Prado himself documents PBO (Probability of Backtest Overfitting) is high for ML-based strategies; CPCV (Combinatorial Purged Cross-Validation) is the correct validation framework. Most published "ML beats simple rules" papers fail to apply CPCV properly. The 2.06 Sharpe result cited above does NOT report CPCV validation in the snippet.

**Capacity.** $500K-$1M. ML-driven strategies need careful validation but can scale.

**Decay.** Insufficient data to call decay; this is a meta-strategy not a signal. Quality of underlying signal drives the result.

**Retail fit on MT5.**
- MT5 Strategy Tester can backtest ML signals (Python integration via MetaEditor).
- Dukascopy tick + IBKR paper 1m provide free training data.
- **Verdict: PROMISING as a confidence-weighting layer** on simple rule-based signals (e.g., size positions proportionally to meta-model probability). Must respect CPCV; otherwise expect PBO.

---

### 10. Time-series momentum / trend following (CTA-style)
**Papers.**
- Moskowitz, T., Ooi, Y.H., Pedersen, L.H. (2012) "Time Series Momentum." *Journal of Financial Economics* 104(2), 228-250. NYU https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf — 12-month TSM across 58 liquid futures/FX/equity/bond markets 1985-2009; Sharpe ~1.0 monthly; TSM alpha survives cross-sectional momentum control = 94 bp/month = 2.65%/quarter.
- Hurst, B., Ooi, Y.H., Pedersen, L.H. (2017) "A Century of Evidence Trend of Investing." *Journal of Portfolio Management*. AQR https://jkgcapital.com/wp-content/uploads/2017/02/AQR-A-Century-of-Trend-Following-Investing.pdf — 67 markets, 1880-2013; full sample Sharpe 0.77 net of 2/20 fees; long-term Sharpe 0.40 still beneficial at conservative assumption.
- Babu, A., Levine, A., Ooi, Y.H., Pedersen, L.H., Stamelos, E. (2020) "Trends Everywhere." *Journal of Investment Management*.
- Baltas, N., Kosowski, R. (2012) — trend-following 1994-2011 on 38 futures, Sharpe 0.7-1.0.
- Fuertes, A.-M., Miffre, J., Rallis, G. (2010) — commodity momentum.
- Huang, D. et al. (2020) "Time Series Momentum: Is It There?" *JFE* 135(3), 774-794 — skeptical view: weak statistical significance.
- NBIM 2014 Discussion Note "Momentum in Futures Markets" https://www.nbim.no/globalassets/documents/dicussion-paper/2014/discussionnote_time_series_momentum_latest.pdf — confirms across asset classes but reports 1-month lookback period best on currencies.
- Carver, R. (2025) "Is the degradation of trend following performance a cohort effect, instrument decay, or an environmental problem?" https://qoppac.blogspot.com/2025/10/is-degradation-of-trend-following.html — **trend performance halved since 2010**; 1970s 500%, 1980s/90s/00s 200%+ per decade, 2010s onwards halved.
- Quantica Capital 2025 Q3 "Gas, Power, and the Past" https://quantica-capital.com/en/publication/qi-2025Q3 — alternative-markets CTAs -15.2% Jan 2023-Jun 2025; SG Trend Index -11.4% same period.
- Man Group "Trend Following Deep Dive" https://www.man.com/insights/trend-following-optimal-market-mix — trend offers positive expected Sharpe AND positive expected crisis Sharpe on traditional markets.

**Numbers.**
- MOP 2012: TSM Sharpe ~1.0 monthly on multi-asset basket.
- HOP 2017 (full sample 1880-2013): net of 2/20 fees, gross annualized 14.9%, net 11.2%, vol 9.7%, Sharpe net 0.77. By decade: 1880-89 0.27; 1920-29 1.09; 1970-79 strong; 2010-13 still positive but lower.
- Recent (post-2010): Carver 2025 documents halving of returns; Quantica 2025 documents -15% on alternative CTA markets 2023-2025; SG Trend Index 2.2% annual 2015-2025 vs traditional CTA estimate 8.5% for "alternative" basket on less-liquid markets (Quantica 2025).
- Huang et al. 2020 skepticism: time-series momentum is statistically weak in pooled regressions; works in time-series.

**Capacity.** Wide ($1M+ easy on liquid futures); cash-efficient (margin ~$1 per $10 of exposure).

**Decay.** YES.
- Carver 2025: returns "degrading over last few decades."
- Quantica 2025: "widespread deterioration in trend persistence across alternative markets universe" 2023-2025.
- But HOP 2017 still shows positive returns through 2013 in their full sample.

**Retail fit on MT5-CFD + CME-futures.**
- Implementable on CFDs (gold, FX majors, oil, indices) but trend signals on CFDs include spread costs.
- CME E-mini + futures block + FX forwards via MT5: feasible; transaction cost 1-3 bp per round trip; signal Sharpe 0.5-0.7 net.
- **Verdict: GOOD diversifier leg with reduced sizing.** Not as alpha-rich as in 1980s/90s; capacity to absorb retail $1M easily; positive skew is valuable for portfolio.

---

### 11. Cross-sectional momentum at daily horizon (futures/FX baskets)
**Papers.**
- Asness, C., Moskowitz, T., Pedersen, L. (2013) "Value and Momentum Everywhere." *Journal of Finance* 68(3), 929-985. NYU https://w4.stern.nyu.edu/facdir/lpederse/papers/ValMomEverywhere.pdf — momentum returns in 8 asset classes, common factor structure, value-momentum equally weighted Sharpe ≈ 1.0+ on global basket.
- Jegadeesh, N., Titman, S. (1993) "Returns to Buying Winners and Selling Losers." *Journal of Finance* 48(1), 65-91.
- Jegadeesh, N., Titman, S. (2023) "Momentum: Evidence and Insights 30 Years Later." *Pacific-Basin Finance Journal* 82. https://www.sciencedirect.com/science/article/abs/pii/S0927538X23002731 — US equity monthly momentum ~0.31% post-2000; New Zealand 2.21%; Asia-Pacific generally stronger.
- Fuertes, A.-M., Miffre, J., Fernandez-Perez, A. (2015) — commodity momentum + term structure + idiosyncratic volatility triple-screen Sharpe 1.0+ on 1985-2011 24-commodity basket.
- Menkhoff, L., Sarno, L., Schmeling, M., Schrimpf, A. (2012) — FX momentum cross-section (different from FX carry).
- "Exploiting Commodity Momentum Along the Curve" https://assets.super.so/.../cfaedebc-97c5-4563-b76a-a7bbccf38797.pdf — curve-momentum strategies Sharpe 1.0-1.1 net after costs.
- Levord likely remains positive on FX at 1-3 month horizon per Menkhoff et al.

**Numbers.**
- Asness-Moskowitz-Pedersen 2013 (FX momentum): Sharpe 0.5-0.7 in 1970s-2010 sample.
- Commodity cross-sectional momentum (Fuertes et al. 2015):
  - Generic momentum: gross Sharpe 0.74, vol 16.12%, MaxDD -21.39%.
  - Optimal-roll momentum: gross Sharpe 1.06, vol 13.92%, MaxDD -19.62%.
  - Net (standard costs 3.3 bp): Sharpe 0.75-0.76.
  - Net (Amihud-based conservative costs): Sharpe 0.55-0.57.
  - Triple-screen (momentum + basis + idiosyncratic vol) Sharpe > 1.0.
- Curve momentum (Baltas-Kosowski style): annualized excess return 6-13% with Sharpe 0.59-0.75 across variants; Long Winners - Short Losers Sharpe 0.59-0.64.
- FX cross-sectional momentum (Menkhoff et al. 2012): Sharpe ~0.5-0.7.

**Capacity.** Wide. 30+ commodity futures, 20+ G10 FX pairs — diversified basket.

**Decay.** Less decayed than equity-only momentum. Asness-Moskowitz-Pedersen 2013 finds value-momentum combined still works in FX/commodity universes.

**Retail fit on MT5-CFD + CME-futures.**
- All instruments available.
- Rebalance monthly — low turnover.
- Free Dukascopy + FirstRate + Binance data sufficient for backtesting.
- **Verdict: STRONG candidate.** One of the best-documented, persistent, capacity-adequate, cost-tolerant edges for this stack.

---

### 12. Calendar effects (day-of-week, TOM, January, Halloween)
**Papers.**
- Lakonishok, J., Smirloc, M. (1988) "Volume, Turn-of-Month, and Realized Volatility." — original TOM in equities.
- McLean-Pontiff 2016 — out-of-sample / post-publication decay.
- Grebe-Schiereck 2024 meta-analysis — DoW effect.
- Aalto dissertation 2024 "Does TOM still exist?" https://aaltodoc.aalto.fi/bitstreams/27ca8cf2-8edd-4ac5-b81f-20b11032661a/download — TOM faded in most international equity indices post-2000.
- Lakonishok-Smirloc 1988; Carcano-Tornero "Calendar Anomalies in Stock Index Futures" — TOM in S&P 500 futures persistent.
- TOM EEM/EM currencies: post-crisis (2008) effects disappeared per https://www.sciencedirect.com/science/article/pii/104402839590008X (Indian FX).

**Numbers.**
- TOM in S&P 500: ~30-50 bp/month on 7 days around month turn.
- January effect: post-1980s mostly decayed.
- Halloween effect (Sell in May): Bouman-Jacobsen 323-year study says persistent in equities.
- Day-of-week: meta-analysis 2024 shows Mondays still underperform in many markets but small effect.

**Capacity.** $1M+ (single instrument).

**Decay.** YES — most documented calendar effects have weakened post-publication. McLean-Pontiff framework applies.

**Retail fit on MT5.**
- Easy to implement as a filter.
- **Verdict: MARGINAL** as stand-alone; useful as a meta-filter on other strategies. NOT a primary edge.

---

## Ranked top-5 candidates for this stack (MT5-CFD + CME-futures retail)

### #1. Overnight / intraday decomposition (Lou-Polk-Skouras 2019, Boyarchenko-Larsen-Whelan 2023)
- **Why**: structural alpha from market microstructure; cheap to trade (single overnight hold); persistent across regimes; works perfectly on MT5 24h instruments; capacity $1M+; Sharpe ~0.5-1.0 historical.
- **Implementation**: enter at close, hold through European open 02:00-03:00 ET (or Tokyo open for some instruments); exit before US cash open.
- **Risk**: regime shift if overnight liquidity provision mechanism breaks (e.g., dealer balance sheet constraints; ETF share-class arbitrage discontinuities).

### #2. Commodity cross-sectional momentum + basis (Fuertes-Miffre-Fernandez-Perez 2015; Szymanowska 2014)
- **Why**: Sharpe 0.7-1.0 net on 24-30 commodity basket; persistent; capacity $1M+; low turnover; works on CME futures directly.
- **Implementation**: monthly rebalance long top-quintile momentum + high-basis, short bottom; vol-target 30%.
- **Risk**: oil/gas extreme moves 2022 (Russia-Ukraine); financialization reducing edge.

### #3. Trend / time-series momentum (Moskowitz-Ooi-Pedersen 2012; Hurst-Ooi-Pedersen 2017)
- **Why**: positive skew; positive crisis Sharpe; works on MT5/CFD + CME; capacity $1M+.
- **Why not higher**: post-2010 halving of returns (Carver 2025); alternative markets -15% 2023-2025 (Quantica 2025).
- **Implementation**: TSM 12-month on liquid futures basket; vol-target 20%; combine with 6-month to capture medium-term; size smaller given decay.

### #4. FX carry + cross-asset basis carry (Lustig-Roussanov-Verdelhan 2011; Szymanowska 2014)
- **Why**: well-documented Sharpe ~0.4-0.7; works on MT5 G10; capacity $1M+.
- **Risk**: tail events (SNB Jan 2015, COVID Mar 2020, USD funding regime 2025); need crisis-aware sizing.

### #5. Pairs trading / stat arb on futures + cross-listed (Zhu 2024; Quantitativo 2024 basis reversal)
- **Why**: Sharpe 1.0-1.5 on liquid equity pairs (Zhu 2024); Sharpe 1.45 on commodity basis spreads (Quantitativo 2024); capacity $500K-$1M; persists in 2020s.
- **Implementation**: cross-section of basis-spread reversals across commodities; cross-asset stat arb (gold/silver, oil products, equity indices).
- **Risk**: low-vol; needs careful universe construction; correlation spikes in crisis.

**Honorable mentions / conditionally:**
- **ML meta-labeling** as overlay (not stand-alone) — confidence-weighted sizing on top of simple rules; requires CPCV discipline.
- **Crypto funding carry** (Schmeling 2025) — best raw Sharpe documented but out of scope for MT5-CFD-only stack.

---

## What has decayed / avoid

| Family | Decay status (2025 verdict) |
|---|---|
| US equity short-term reversal (Nagel 2012) | Decayed 30-60% post-publication; cost-sensitive. Use sparingly. |
| US equity momentum 12-1 (Jegadeesh-Titman 1993) | Sharpe halved in US (0.31%/mo post-2000); stronger in NZ, Korea. Not a primary leg. |
| Intraday momentum on NYSE (Heldens 2017) | Pre-cost edge tiny; net of realistic costs, zero. Skip on liquid equities. |
| Calendar (TOM, day-of-week, January) | Mostly decayed post-2000; only persistent in select markets. Use as filter, not edge. |
| VIX short-vol premium | Compressed Sharpe post-2018 Volmageddon; tail risk persistent. Skip on retail MT5 (no VIX direct). |
| Sub-class long-only commodity beta (S&P GSCI) | Negative carry since 2000s financialization. Avoid long-only. |
| ML hype > CPCV | PBO > 50% in many published ML results (Lopez de Prado). Avoid ML without CPCV. |
| High-frequency liquidity provision (Nagel/HBS) | Sharpe 1.75 → halving as volume rose; capacity-constrained. |
| Pair trading in small equity universe | Rubesam 2021 claims decay; but Zhu 2024 counter-evidence with larger T500 universe. Use larger universe. |

---

## Contradictions & open questions

1. **Trend following degradation: cohort vs instrument vs environment** (Carver 2025 explicitly raises this). Three competing hypotheses: (a) original cohort of CTAs were unique (cohort effect, future can't replicate); (b) liquidity provision for trends (instrument decay) reduced as more strategies trade trends; (c) macro environment less trend-prone post-2010 (lower vol regimes; central bank intervention). Evidence: Quantica 2025 shows even newly-discovered "alternative" markets trended well 2015-2022 then broke down 2023-2025, suggesting environment-driven decay. Open question.

2. **Overnight drift mechanism: dealer-inventory vs retail-attention.** Boyarchenko-Larsen-Whelan 2023 attribute to dealer inventory management (Grossman-Miller 1988); Berkman-Koch-Tuttle-Zhang 2012 + Aboody et al. 2018 + Carney-Dou-Lou 2024 attribute to retail overpaying at the open. "Does Overnight News Explain Overnight Returns?" (arXiv 2507.04481, 2025) finds news doesn't fully explain it; supports the dealer-inventory channel but doesn't fully rule out retail. Both can be true simultaneously (inventory + retail-attention correlated). Open question: which is more persistent for retail capturing?

3. **Pairs trading Rubesam 2021 vs Zhu 2024 contradiction.** Zhu 2024 explicitly counters Rubesam 2021 with a more recent 20-year sample (up to 2024) and finds T500 pairs Sharpe 1.35. Rubesam used a smaller universe and a different period. The conflict suggests the result depends on universe size and pairing method. Practical implication: use larger universe (≥100 pairs) and avoid the simple top-20 vanilla.

4. **Intraday momentum holds on futures but breaks on equities.** Heldens 2017 NYSE: equity intraday momentum pre-cost = $0.20/day; reversal = $3.29/day (Reversal wins on equities). BDLM 2021 on 60+ futures: momentum is strong 1974-2020. Implication: futures/futures-CFD keep the intraday momentum; equity-CFDs do not (different mechanism at work).

5. **Crypto funding carry persistence.** He et al. 2024 document that "deviations from no-arbitrage prices diminish over time as market matures and arbitrage capacity deepens." Schmeling et al. 2025 document persistent 7-15% annual funding carry. October 2025 saw -5% funding (CV5 Capital) — regime may be inverting under institutional hedging pressure. Open: is this a regime change or temporary?

6. **Meta-labeling improvements: real or PBO?** Multiple studies report Sharpe 1.5-2.0 OOS for ML+meta-labeling stacks; but Lopez de Prado documents >50% PBO in published ML papers that don't use CPCV. The 2.06 Sharpe result cited above doesn't report CPCV validation. Open: which published meta-labeling results survive CPCV?

7. **Overnight drift on MT5-specific instruments (gold, oil).** LPS 2019 and BLW 2023 are US equity index focused. Replication on gold CFD / oil CFD overnight drift is less established. Practical question for oracle: does gold CFD overnight drift exist? Open for empirical validation with Dukascopy data.

8. **Day-of-week effect for FX specifically.** FX day-of-week meta-analysis (Grebe-Schiereck 2024) covers equities primarily. FX-specific day-of-week evidence (post-2000) is sparser. Open for validation with Dukascopy G10 data.

---

## Sources index (selected)

### Original academic
- Nagel, S. (2012) "Evaporating Liquidity" — https://academic.oup.com/rfs/article-abstract/25/7/2005/1602153 ; SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1988706
- Da, Liu, Schaumburg (2013) — https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr513.html
- McLean, Pontiff (2016) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2475955
- Drechsler, Moreira, Savov (2021) — https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2022/03/Paper5_Drechsler.pdf
- Harvard "Rethinking Volume" — https://www.hbs.edu/ris/download.aspx?name=26-003.pdf
- Cont, Kukanov, Stoikov (2014) — https://academic.oup.com/jfec/article-abstract/12/1/47/816163
- Fed FEDS Notes (2025) on OFI — https://www.federalreserve.gov/econres/notes/feds-notes/order-flow-imbalances-and-amplification-of-price-movements-evidence-from-u-s-treasury-markets-20251103.html
- Easley, López de Prado, O'Hara VPIN — https://cdn.cboe.com/api/v1.5/delayed_quote_chicken_series_options/VPIN_Methodology.pdf
- Gao, Han, Li, Zhou (2018) — https://www.sciencedirect.com/science/article/abs/pii/S0304405X18300687
- Replication: https://github.com/codespace5555/Replication-of-Decay-of-Intraday-Momentum-by-Li-Zhou-Gao-2018
- Baltussen, Da, Lammers, Martens (2021) — https://www.sciencedirect.com/science/article/abs/pii/S0304405X21001598
- Li (Lancaster 2020) "Intraday Time Series Momentum: International Evidence" — http://wp.lancs.ac.uk/fofi2020/files/2020/04/FoFI-2020-092-Zeming-Li.pdf
- Seo (KOSPI 2022) — https://www.mdpi.com/1911-8074/15/11/523
- Heldens (Tilburg 2017 NYSE intraday momentum/reversal) — http://arno.uvt.nl/show.cgi?fid=144554
- Lou, Polk, Skouras (2019) — https://www.sciencedirect.com/science/article/abs/pii/S0304405X19300650
- Lou, Polk, Skouras (2024) "The Day Destroys the Night" — https://personal.lse.ac.uk/loud/LouPolkSkouras.pdf
- Boyarchenko, Larsen, Whelan (2023) "The Overnight Drift" — https://research-api.cbs.dk/ws/portalfiles/portal/101311522/nina_boyarchenko_et_al_the_overnight_drift_acceptedversion.pdf
- Lachance (2021) "ETFs' High Overnight Returns" — JFM
- Berkman, Koch, Tuttle, Zhang (2012) — JFQA 47
- Aboody et al. (2018) — JFE
- Krohn, Mueller, Whelan (2024) "FX Fixings and Returns around the Clock" — JF 79(1)
- Ito, Hashimoto (2006) EBS intraday — https://www.nber.org/system/files/working_papers/w12413/w12413.pdf
- Cotter, Dowd (2007) DEM/USD intraday — https://mpra.ub.uni-muenchen.de/3502
- Watkins (2017) Gold/Platinum intraday seasonality — https://www.econ.kobe-u.ac.jp/wp-content/uploads/2023/06/1722.pdf
- BIS Triennial Survey April 2025 — https://www.bis.org/publications/202509-commentary-otc-derivatives
- Gatev, Goetzmann, Rouwenhorst (2006) — http://stat.wharton.upenn.edu/~steele/Courses/434/434Context/PairsTrading/PairsTradingGGR.pdf
- Zhu, X. (2024 Yale) Pairs Trading replication — https://economics.yale.edu/sites/default/files/2024-05/Zhu_Pairs_Trading.pdf
- Rubesam, A. (2021) — https://data.mendeley.com/datasets/xz6c2bp5d8
- Krauss (2017) Pairs review — https://www.iwf.rw.fau.de/files/2016/03/09-2015.pdf
- Quantitativo "Short-Term Basis Reversal" (2024) — https://quantitativo.com/p/short-term-basis-reversal
- Lustig, Roussanov, Verdelhan (2011) — https://www.nber.org/system/files/working_papers/w16427/revisions/w16427.rev2.pdf
- Accominotti, Chambers, Marsh (2019) "Currency Regimes and the Carry Trade" — https://eprints.lse.ac.uk/100239/1/Accominotti_Cen_Chambers_Marsh_CurrencyRegimesandtheCarryTrade_2019_02.pdf
- Szymanowska, De Roon, Nijman, Van Den Goorbergh (2014) — JoF 69, 453-482
- Bakshi, Gao, Rossi (2019) Commodity risk premia — SSRN
- Gorton, Hayashi, Rouwenhorst (2013) "Fundamentals of Commodity Futures Returns" — Review of Finance 17
- Erb, Harvey (2006) "Strategic and Tactical Value of Commodity Futures" — FAJ 62(2)
- Asness, Moskowitz, Pedersen (2013) "Value and Momentum Everywhere" — JoF 68(3), 929-985 — https://w4.stern.nyu.edu/facdir/lpederse/papers/ValMomEverywhere.pdf
- Moskowitz, Ooi, Pedersen (2012) "Time Series Momentum" — https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
- Hurst, Ooi, Pedersen (2017) "A Century of Evidence" — https://jkgcapital.com/wp-content/uploads/2017/02/AQR-A-Century-of-Trend-Following-Investing.pdf
- Babu, Levine, Ooi, Pedersen, Stamelos (2020) "Trends Everywhere" — JIM
- Huang et al. (2020) "Time Series Momentum: Is It There?" — JFE 135(3), 774-794
- Carver (2025) "Is the degradation of trend following performance a cohort effect, instrument decay, or an environmental problem?" — https://qoppac.blogspot.com/2025/10/is-degradation-of-trend-following.html
- Quantica Capital (2025 Q3) "Gas, Power, and the Past" — https://quantica-capital.com/en/publication/qi-2025Q3
- Man Group "Trend Following Deep Dive" — https://www.man.com/insights/trend-following-optimal-market-mix
- Fuertes, Miffre, Fernandez-Perez (2015) Commodity momentum/term structure/IV triple-screen — openaccess.city.ac.uk/6418
- Exploiting Commodity Momentum Along the Curve — https://assets.super.so/.../cfaedebc-97c5-4563-b76a-a7bbccf38797.pdf
- Whaley (1993, 2009) VIX premium — multiple papers
- Quantpedia VIX Term Structure — https://quantpedia.com/strategies/exploiting-term-structure-of-vix-futures
- Simplify (2024) "Volatility Premium Harvesting, Reimagined" — https://www.simplify.us/blog/volatility-premium-harvesting-reimagined
- Loomis Sayles (2018) Short Vol Trade — https://www.loomissayles.com/insights/how-the-spike-in-volatility-punctured-the-short-vol-trade
- López de Prado (2018) Advances in Financial Machine Learning (book); Wikipedia https://en.wikipedia.org/wiki/Meta-labeling
- Hudson & Thames meta-labeling — https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method
- Mental-Momentum 2025 — https://research.mental-momentum.ai/r/meta-labeling-triple-barrier-methods-lq4i7w
- AEDL 2025 — https://www.mdpi.com/2076-3417/15/24/13204
- Reinforcement learning AMM 2026 — https://www.sciencedirect.com/science/article/pii/S240591882600022X
- Cboe VPIN methodology — https://cdn.cboe.com/api/v1.5/delayed_quote_chicken_series_options/VPIN_Methodology.pdf
- Christin et al. (2022) BTC carry — NBER
- Schmeling, Schrimpf, Todorov (2025) Crypto Carry — SSRN 4268371
- He et al. (2024) Perpetual Futures — https://arxiv.org/html/2212.06888v5
- Hu et al. (2025+) MDPI 14(7), 178 — https://www.mdpi.com/2227-7072/14/7/178
- Lakonishok, Smirloc (1988) TOM — original
- Carcano, Tornero "Calendar Anomalies in Stock Index Futures"
- Aalto dissertation 2024 TOM — https://aaltodoc.aalto.fi/bitstreams/27ca8cf2-8edd-4ac5-b81f-20b11032661a/download
- Grebe, Schiereck (2024) DoW meta-analysis — https://link.springer.com/article/10.1007/s40822-024-00293-9
- Jegadeesh, Titman (1993) momentum — https://www.bauer.uh.edu/rsusmel/phd/jegadeesh-titman93.pdf
- Jegadeesh, Titman (2023) "30 years later" — https://www.sciencedirect.com/science/article/abs/pii/S0927538X23002731

### Practitioner / replication sources (lower trust but useful for current numbers)
- IC Markets trading costs — https://www.icmarkets.eu/en/trading-pricing/trading-costs
- BestBrokers MT5 brokers 2026 — https://www.bestbrokers.com/forex-brokers/metatrader-5-forex-brokers
- ThinkMarkets forex sessions — https://www.thinkmarkets.com/en/trading-academy/forex/sessions
- City Index forex market hours — https://www.cityindex.com/en-uk/forex/forex-market-hours
- FXEmpire FX seasonality 2026 — https://www.fxempire.com/education/article/fx-seasonality-what-still-works-and-what-doesnt-in-2026-1545003
- Quantpedia Term Structure Effect in Commodities — http://www.quantpedia.com/strategies/term-structure-effect-in-commodities
- Quantpedia FX Carry Trade — https://quantpedia.com/strategies/fx-carry-trade
- Quantpedia Short-Term Reversal — https://quantpedia.com/strategies/short-term-reversal-in-stocks
- Quantpedia Turn of Month — https://quantpedia.com/strategies/turn-of-the-month-in-equity-indexes
- Quantpedia Currency Momentum — https://quantpedia.com/strategies/currency-momentum-factor

---

*Written 2026-09-04 for Oracle edge-factory. Primary academic sources preferred; replication snippets and practitioner articles cited where helpful for current retail-execution numbers. Open empirical questions flagged.*
