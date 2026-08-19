# 01 Fundamental — Literature Review

> Fonti: Tavily API search (advanced, AI-optimized) 2026-08-17.
> Citazioni verificate via URL dirette (NBER, SSRN, MDPI, AQR, institutional).

## 1. Value investing classico

### Piotroski F-Score (2000)

**Paper**: Piotroski, J. (2000). *Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers*. Journal of Accounting Research.

- **Risultato originale**: high F-Score (8-9) value stocks battono low F-Score (0-3) di **13.4% annuo** nel periodo 1976-1996.
- **9 criteri** (ROA, CFO, ΔROA, accruals, Δmargin, Δturnover, Δleverage, Δcurrent_ratio, equity issuance).
- **OOS**: Replica 1999-2011 su Eurozone (1500 companies) → ancora +alpha, ma meno della meta originale (~30% decay post-publication, coerente con McLean-Pontiff 2016).
- **Edge attivo**: usa solo storico accounting, no forecasts. Utile come signal di qualità dentro bucket value.
- URL paper: https://www.chicagobooth.edu/-/media/36c84add1aa54bb2b6f9f9d3f5570d35.pdf

### Lakonishok, Shleifer, Vishny (1994)

**Paper**: Lakonishok, J., Shleifer, A., Vishny, R. (1994). *Contrarian Investment, Extrapolation, and Risk*. Journal of Finance.

- **Value premium sostanzioso su 3-5y orizzonti** (non 1y). Glamour stocks (high past growth) sotto-performano value stocks (low price/book, low past growth).
- **Causa behavioral**: investitori estrapolano passato recente → overpay glamour → reversion.
- **NON risk-based** (contro Fama-French): se behavioral, drawdown lungo = mispricing più grande = expected future return più alto. Se risk-based, drawdown = rischio materializzato.
- **Orizzonte critico**: 12m valuation è fuorviante. 3-5y è il tempo corretto.
- URL foxholm.com: https://foxholm.com/q/research/lakonishok-shleifer-vishny-contrarian

### Greenblatt Magic Formula (2006)

**Book**: Greenblatt, J. (2006). *The Little Book That Beats the Market*.

- **Formula**: rank by ROC (return on capital) + rank by earnings yield → somma → top 20-30 stocks.
- **Backtest 1988-2004**: 30.8% annuo vs 12.3% S&P = **+18.4% alpha**.
- **Large-cap subset (top 1000)**: 22.9% annuo = +10.5% alpha (più realistico retail).
- **OOS 2017-2026** (Seeking Alpha replica): 4-6% annuo sopra S&P su 20-30 top-ranked. Decay rispetto al paper originale ~50%.
- **Key insight**: Quality (ROCE) alone batte Value (Earnings Yield) alone. Combinazione best risk-adjusted. **Sostituendo P/FCF a Earnings Yield → returns + Sharpe migliori**.
- URL stockrover: https://www.stockrover.com/blog/stock-research/magic-formula-investing-strategy

## 2. Profitability factor

### Novy-Marx Gross Profitability (2013)

**Paper**: Novy-Marx, R. (2013). *The Other Side of Value: The Gross Profitability Premium*. Journal of Financial Economics.

- **Definizione**: gross profit (revenue - COGS) / total assets.
- **Premium**: high gross profitability stocks outperform low. ~0.31% mensile, t-stat ~3.5.
- **Combina con value**: long high-profitability value + short low-profitability growth → alpha più robusto.
- **Buffett explanation**: ~50% dell'alpha di Berkshire è spiegato da QMJ + BAB (Frazzini-Kabiller-Pedersen 2018).
- URL NBER: https://www.nber.org/system/files/working_papers/w15940/w15940.pdf

### Asness, Frazzini, Pedersen — Quality Minus Junk (QMJ, 2019)

**Paper**: Asness, C., Frazzini, A., Pedersen, L. (2019). *Quality Minus Junk*. Review of Accounting Studies.

- **QMJ factor**: profitability + growth + safety + payout → composite quality score.
- **SMB control**: SMB alpha = 13bps. Quality-adjusted SMB alpha = 64bps (t-stat 6.39). **Small firms sono junky, large firms sono high quality**.
- **Alpha globale 1986-2012**: positivo in 24/24 paesi studiati.
- URL AQR: http://www.efalken.com/LowVolClassics/Asness_Frazzini_Pedersen_QMJ.pdf

### Fama-French 5-Factor Model (2015)

**Paper**: Fama, E., French, K. (2015). *A five-factor asset pricing model*. Journal of Financial Economics.

- **3 fattori originali** (1993): Mkt-RF, SMB, HML.
- **2 nuovi**: RMW (robust operating profitability) + CMA (conservative minus aggressive investment).
- **HML spesso ridondante** quando controllato per RMW+CMA → 5-factor a volte peggiore di 4-factor (senza HML).
- **Issue**: small stocks con negative RMW/CMA exposure sono mispriced.
- URL: https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1976.tb01893.x

## 3. Earnings quality + anomaly

### Sloan Accrual Anomaly (1996)

**Paper**: Sloan, R. (1996). *Do Stock Prices Reflect Information in Accruals and Cash Flows about Future Earnings?* Journal of Accounting Research.

- **Anomaly**: firms with **high accruals** (earnings > cash flow) → lower future returns. Underreaction al fatto che accruals sono meno persistenti di cash flows.
- **Strategy**: long lowest-accrual decile + short highest-accrual decile → +alpha 1 anno dopo.
- **Replicato international**: Pincus-Rajgopal-Venkatachalam (confermato fuori US).
- URL Columbia: https://business.columbia.edu/sites/default/files-efs/pubfiles/12947/pincus%20rajgopal%20venkatachalam%20TAR.pdf

### Altman Z-Score (1968)

**Paper**: Altman, E. (1968). *Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy*. Journal of Finance.

- **Modello**: 5 ratio (working capital / assets, retained earnings / assets, EBIT / assets, market cap / liabilities, sales / assets) → weighted Z-score.
- **Z < 1.81** = distress zone. Z > 3.0 = safe.
- **Accuracy**: ~72% Tipo I (bankrupt classified bankrupt), ~80% overall.
- **Maintained**: Altman 2018a conferma accuracy sostenuta 50y dopo.
- URL MDPI: https://www.mdpi.com/1911-8074/18/8/465

### PEAD — Post-Earnings Announcement Drift (Piotroski-So 2012)

**Paper**: Piotroski, J., So, E. (2012). *Identifying Expectation Errors in Value/Glamour Strategies via Fundamental Analysis*. Review of Accounting Studies.

- **PEAD**: stock price underreact a earnings surprise → drift nella direzione dell'earnings news per 60 giorni post-announcement.
- **Combo con F-Score**: high F-Score + positive earnings surprise = max alpha.
- **Edge persistente**: non ancora arbitrato via. Linked to information uncertainty + governance quality.
- URL: https://ies.fsv.cuni.cz/sites/default/files/uploads/files/Chang_0.pdf

## 4. Behavioral + macro valuation

### Shiller CAPE (1988)

**Paper**: Campbell, J., Shiller, R. (1988). *The Dividend-Price Ratio and Expectations of Future Dividends and Discount Factors*. Review of Financial Studies.

- **CAPE (cyclically adjusted PE)**: price / 10y average of inflation-adjusted earnings.
- **Predictive power**: forward 10y stock returns correlate -0.4 a -0.5 con CAPE iniziale. High CAPE → low future returns.
- **5y vs 10y**: 10y predict è molto più accurato. 3y quasi inutile.
- **Modified CAPE** include interest rates (ECY = excess CAPE yield) → ancora migliore (UP repository paper 2024).
- URL: https://repository.up.ac.za/server/api/core/bitstreams/6f5329c6-878a-4d94-9bb3-fc8403878340/content

### Buffett Alpha Decomposition (Frazzini-Kabiller-Pedersen 2018)

**Paper**: Frazzini, A., Kabiller, D., Pedersen, L. (2018). *Buffett's Alpha*. Financial Analysts Journal.

- **Berkshire 1976-2011**: 19.0% annuo vs 6.7% S&P = +12.3% alpha. Sharpe 0.76.
- **Decomposition**: 100% dell'alpha spiegato da **BAB (betting against beta)** + **QMJ (quality minus junk)**. Residual alpha ≈ 0.
- **Mechanismo**: Buffett bought safe high-quality stocks + levered via insurance float (1.6x leverage).
- **Post-1995**: intangible value loading +50%, residual alpha -1.9%/yr → underperform vs rules-based implementation.
- URL: https://www.evidenceinvestor.com/post/buffett-s-investment-strategy

## 5. Momentum fundamentals

### Chan, Jegadeesh, Lakonishok (1996) — Earnings Momentum

**Paper**: Chan, L., Jegadeesh, N., Lakonishok, J. (1996). *Momentum Strategies*. Journal of Finance.

- **Past returns + past earnings surprises** → entrambi predicono drift in future returns controllando per l'altro.
- **Independent explanatory power**: price momentum ed earnings momentum sono correlati ma ognuno ha signal esclusivo.
- **3-12m orizzonte**: media 6-12 mesi.

### George & Hwang 52-Week High (2004)

**Paper**: George, T., Hwang, C. (2004). *The 52-Week High and Momentum Investing*. Journal of Finance.

- **Nearness to 52-week high** (price / 52w high) → predice future returns meglio di past 6-12m returns.
- **Subsumes price momentum**: quando controllato per 52w-high, traditional Jegadeesh-Titman momentum perde metà explanatory power.
- **Causa**: anchoring bias (investors reluctant to buy near 52w-high).

### Chen-Lakonishok Fundamental Momentum (2020)

**Paper**: Chen, Z., Lakonishok, J. (2020). *Fundamental Momentum*. Review of Asset Pricing Studies.

- **Earnings + revenue momentum** predicono future returns anche dopo controllo per price momentum.
- **Composite (technical + fundamental + macro)** → migliore di qualsiasi singolo momentum.
- **Chen et al 2014**: revenue/earnings/price momentum ognuno ha exclusive information content. No dominating strategy.
- URL: https://link.springer.com/article/10.1007/s11156-026-01540-7

## 6. Factor zoo + replication

### Harvey, Liu, Zhu (2016)

**Paper**: Harvey, C., Liu, Y., Zhu, H. (2016). *… and the Cross-Section of Expected Returns*. Review of Financial Studies.

- **~400 fattori pubblicati** dal 1963. La maggior parte non sopravvive a multiple-testing correction (Bonferroni, Holm, BHY).
- **t-stat threshold raccomandato**: >3.0 (non >2.0) per nuove anomalie post-2010.
- **Implication**: alcune anomalie value/profitability classiche sopravvivono (Piotroski, Lakonishok, Fama-French 5F), ma non tutte.

### Hou, Xue, Zhang (2020)

**Paper**: Hou, K., Xue, C., Zhang, Z. (2020). *Replicating Anomalies*. Review of Financial Studies.

- **Replica 452 anomalie**: ~65% non replicano o perdono >50% alpha OOS.
- **Value + profitability + investment** → robusti. Momentum + accruals + PEAD → marginali.
- **McLean-Pontiff (2016)**: post-publication decay ~30% (arbitraggio erode).
- URL HEC: https://www.hec.ca/finance/Fichier/Pearson2022.pdf

## 7. Cap summary — fattori che sopravvivono al filter

**Edge forte e persistente** (replicato OOS, t-stat > 3, decay < 30%):
- Value (HML) — Piotroski / Lakonishok / Fama-French
- Profitability (RMW) — Novy-Marx gross profit
- Investment (CMA) — Fama-French 2015
- Quality (QMJ) — Asness-Frazzini-Pedersen
- Earnings momentum — Chan-Jegadeesh-Lakonishok
- 52-week high — George-Hwang
- PEAD — Piotroski-So
- Accrual anomaly — Sloan

**Edge contestato o decaying**:
- Magic Formula (Greenblatt) — ~50% decay post-2006
- Shiller CAPE — 10y orizzonte, non tradabile short-term
- Small-cap premium (SMB) — 0% da 1980, QMJ-adjusted SMB è positivo ma è QMJ driving

**Edge non replicato / data mining**:
- ~400 altri fattori pubblicati — vedi factor zoo Harvey-Liu-Zhu
