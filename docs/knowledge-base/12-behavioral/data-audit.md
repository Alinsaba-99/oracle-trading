# 12 Behavioral — Data Audit (free $0 verified 2026-08-17)

> Regola hard: $0/mo per dati. Vedi ADR-020.

## Fonti behavioral free verificate

| Fonte | Coverage | Format | API Key | Note |
|---|---|---|---|---|
| **Shiller CAPE data** | 1871-2026 monthly | CSV | nessuna | http://www.econ.yale.edu/~shiller/data.htm. CAPE + interest rates + CPI |
| **AAII sentiment survey** | 1987-2026 weekly | HTML + CSV | nessuna (basic) | https://www.aaii.com/sentimentsurvey. Free weekly summary |
| **Baker-Wurgler sentiment index** | 1960-2025 monthly | Excel | nessuna | https://sites.google.com/a/nyu.edu/jeffreywurgler/data. NYU Stern public |
| **Investor Intelligence (II)** | 1963-2026 weekly | HTML | paid | Weekly summary in Barron's magazine free, full historical $50/mo |
| **VIX (FRED)** | 1990-2026 daily | JSON via FRED | `FRED_API_KEY` free | Series VIXCLS. Proxy of risk aversion |
| **OptionMetrics / CBOE OVX** | 2007+ | CSV | nessuna (limited) | https://cdn.cboe.com/data/option-analytics/. Free delayed |
| **yfinance SPY options chain** | current + some history | JSON | nessuna | `yf.Ticker("SPY").option_chain()`. OTM puts for tail risk |
| **SEC 13-F institutional holdings** | quarterly 45-day delay | JSON via EDGAR | nessuna | https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=13F |
| **Greenwood-Shleifer survey data** | 1963-2026 quarterly | CSV | nessuna | Harvard Kennedy School public |

## Capabilities Oracle esistenti

- ✅ Lane B backtester (fundamental equity)
- ✅ FRED VIX loader
- ✅ `analytics/ai_analysts/lateral.py` + `synthesizer.py` (LLM via vsllm/OmniRoute)

## Gap dichiarati

1. **Shiller CAPE adapter** NON implementato. TODO BL-KB-86.
2. **De Bondt-Thaler reversal signal** NON implementato. TODO BL-KB-87.
3. **Taleb barbell tail-risk overlay** NON implementato. TODO BL-KB-88.
4. **Loss aversion position sizing (Kahneman-Tversky)** NON implementato. TODO BL-KB-89.
5. **Bubble detector (Greenwood-Shleifer extrapolation)** NON implementato. TODO BL-KB-90.

## Cap da NON usare (paywalled)

| Fonte | Perché esclusa | Alternativa free |
|---|---|---|
| Bloomberg behavioral analytics | $24k/yr | AAII + II weekly + CAPE |
| Refinitiv sentiment + flows | $1.8k/mo | yfinance + SEC 13-F |
| Investor's Intelligence historical | $50/mo | AAII free + II weekly in Barron's |
| Dataminr social sentiment | enterprise | Reddit PRAW + StockTwits (dominio 07) |
| Glassnode + Santiment crypto behavioral | paid | Etherscan + CoinGecko (dominio 11) |

## Reference implementations free

- **Shiller CAPE monthly**: http://www.econ.yale.edu/~shiller/data/ie_data.xls (updated monthly)
- **Baker-Wurgler sentiment data**: https://sites.google.com/a/nyu.edu/jeffreywurgler/data
- **Greenwood-Shleifer paper**: https://www.hks.harvard.edu/sites/default/files/HKSEE/HKSEE%20Files/BF_Extrapolation_Greenwood.pdf
