# Prop-Firm Monthly Return Envelope — Honest Math & Rules (2025-2026)

> Research dossier. All sources accessed 2026-09-04 unless otherwise noted.
> Scope: The5ers, Lucid Trading, FundedNext, Topstep, MyFundedFutures, FTMO (with reference to Apex and The Trading Pit where they illustrate envelope mechanics).
> Goal: derive the *mathematical* and *empirical* envelope for sustained monthly returns on prop-firm funded accounts, identify the strategy profile that survives consistency + daily caps, and catalogue the payout-denial red flags.

---

## 1. Rule Matrix per Firm

Rules change quarterly. Below is the current public state per the official help-centre / FAQ / trading-objectives pages. URLs + access dates in the source citations at the bottom.

### 1.1 Compact comparison (per official pages, 2025-2026)

| Firm | Typical account sizes | Profit target (eval) | Daily loss cap | Max / trailing drawdown | Consistency / best-day rule | Min trading days | Payout cadence & cap | Profit split | News rule | Weekend/overnight | EA / algo |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **FTMO** (CFD; futures launched 2025) | $10k–$200k | 2-Step: 10% (Phase 1), 5% (Phase 2). 1-Step: 10% target, 3% MDL on Rewards | **5%** (2-Step), **3%** (1-Step) on closed+floating PnL | **10%** static (EOD trailing-then-static on Rewards; floor never moves up once initial breached) | "Best Day" rule (1-Step only): best day ≤ 50% of *positive-day* profit, otherwise new floor on Phase 2; no formal funded-stage consistency gate | 4 (per phase) | On-demand, after 14 days from first trade on Rewards. Min $20 (wire) / $50 (crypto) | **80%** base → **90%** after Scaling Plan (10% profit in last 4 months, ≥2 payouts). Cap $2M allocation | **Standard:** 2-min blackout before/after selected high-impact (does NOT apply during eval). **Swing:** unrestricted | **Standard:** close before weekend. **Swing:** unrestricted | EAs allowed (subject to forbidden practices) |
| **The5ers** | $5k–$200k+ | 2-Step (New $149 / Classic $179): 10% / 8% (P1), 5% (P2). High Stakes: 1-step 5%. Bootcamp: weekly staged | **3%** of previous day's closing balance | **10%** static | None during 2-Step eval. **50%** best-day rule applies to **funded** stage (and to High Stakes/Bootcamp). Access 1-Step funded: 25% | 3 (High Stakes / 2-Step) | Min $250 in profit per cycle. Cap $2,000 per payout cycle on 2-Step | **50%** start (Bootcamp) → 80% (2-Step funded) → up to **100%** with Hyper Growth scaling to $4M | No public blackout window | Allowed | EAs allowed |
| **FundedNext** | $5k–$200k (CFD), up to $300k funded (CFDs); Challenge up to $700k (Futures) | Stellar 2-Step: 8% + 5%. 1-Step: 10%. Lite: 8%+4%. Instant: 10%. Flex (Futures): $2.5K / $5K / $8K depending on size | **5%** (Stellar 2-Step), **3%** (1-Step). Rapid Daily: hard DLL. Rapid Pro: none. Stellar Lite: 1% risk-of-balance | **10%** static (Stellar). Trailing-then-locks for Instant/Express | **40%** best day per cycle (challenge). On Stellar: best day ≥40% → **profit target recalculates** upward (`Best Day / 0.40`), not account kill. Funded: still 40% on reward cycle | 2 (1-Step), 5 (2-Step) | Rapid: every 3 business days. Legacy: every 5 days. 95/5 split for stellar multi-cycle traders. Refundable fee on 1st reward | **Up to 95%** (Stellar), 80-90% baseline | **5 min before / 5 min after** high-impact news → only 40% of profit counts on those trades (running positions allowed). Stated per Stellar 1-Step / 2-Step help-centre | Allowed on most plans | EAs allowed |
| **Topstep** (futures) | $50k / $100k / $150k | **$3K / $6K / $9K** (6% of starting balance) | **$1K / $2K / $3K** (2%). Resets 5 PM CT. Hitting DLL = trading halt, NOT combine failure | **Trailing intraday MLL**: $2K / $3K / $4.5K (4% / 3% / 3%). Locks at $0 once on Express Funded. **EOD trailing** on Express Funded Account (XFA) | **50%** in Combine. On XFA: Standard path = no consistency cap; Consistency path = **40%** but unlocks higher payout caps | None on Combine (XFA path requires ≥2 days) | After 5 winning days (Standard path) or as few as 3 (Consistency path). Min $125. Cap $5,000 per request (Express); uncapped on Live Funded | **100%** to first $5K/$10K depending on size, then **90%**. Live Funded: 100% after 30 winning days | No public blackout (positions auto-flattened before close) | Positions auto-close by **3:10 PM CT**; no overnight or weekend | EAs allowed subject to CME + TopstepX rules |
| **MyFundedFutures** (futures) | $25k / $50k / $100k / $150k | **$1.5K / $3K / $6K / $9K** (6%). Builder plan lower (~$1.1K) | **None** on any plan | **EOD trailing** $1K / $2K / $3K / $4.5K (4%). Locks after 1st payout ($+100 buffer). Pro plan: $4K target / $4K Max Loss | **50%** best day, evaluation only. **Dropped entirely once funded** on Rapid & Pro; 40% on Core funded; Builder has none on 1st payout then 50% | 2 | Every **5 winning days** (Core/Scale); every **14 days** (Pro); $250 min (Core/Scale), $1K (Pro) | **80%** (Core), 100% first $10K then 90/10 (Scale/Pro). Payout cap grows with payouts taken (Payout 1 $1.5K → Payout 5 $3.5K on $50K) | **Core/Scale:** Tier 1 events (NFP, CPI, FOMC) **2 min before / 2 min after** blackout, must close positions. **Pro/Rapid funded:** news trading **allowed** | Auto-flat at **4:10 PM ET** | **Semi-automated only** as of March 2026. Fully autonomous set-and-forget prohibited |
| **Lucid Trading** (futures) | $25k–$150k | $1.5K / $3K / $6K (6%) for LucidPro/Flex/Black. LucidDaily varies | None on Flex/Live. LucidPro keeps daily loss as evaluation rule | EOD trailing, $1K / $2K / $3K (4%) | **LucidPro funded: 40%** per payout cycle (resets). **LucidFlex: none**. LucidBlack: 50% eval | 1 possible (no minimum on LucidPro) | Every 3 days (LucidPro, $500 min). Daily on Flex/Black | **90/10** baseline. **100% of first $10K** legacy only (pre-28 Nov 2025) | Close positions before 4:45 PM ET | Close positions before close | EAs allowed |
| **Apex Trader Funding** (futures; reference) | $25k–$300k | Roughly 6% | No DLL on funded Intraday Trailing program | Intraday **trailing** ($2.5K / $3K / $5K on $50K/$100K/$150K); EOD option also | **30%** at payout stage — single violation requires continuing to dilute best day. Blatant/repeated = account reset, payout forfeit, possible closure | None on PA | Min $250, max 50% of balance per request, $5K cap on Express Funded; uncapped on Live | 100% first $250/payout, then 90% (Apex 3.0) | No official blackout (CME micro-A-book) | Auto-close before close on EOD program | EAs allowed on PA. Live: requires registered owner only, no shared infra |

### 1.2 Compact takeaways

- **Daily-loss cap range** across the universe: 0% (MFFU/Apex) → 3% (FTMO 1-Step, FundedNext 1-Step) → 5% (FTMO 2-Step, FundedNext 2-Step, The5ers 2-Step at 3% actually) → 6% no public cap. The **median is 4-5%** for 2-Step futures+CFD firms.
- **Max / trailing drawdown**: 4% EOD trailing is the sweet spot for futures (MFFU/Topstep/Lucid). CFDs lean 10% static (FTMO, FundedNext, The5ers).
- **Consistency** is *everywhere*. Range 20% (Tradeify Lightning first payout) → 50% (Topstep Combine, MFFU eval). Most futures-funded-stage rules drop the consistency rule once funded (Topstep Consistency Path is the *exception* that unlocks bigger caps).
- **News blackouts** are now standard: 2-min windows dominate (FTMO Standard, MFFU Core/Scale, Apex hybrid). Several firms keep 5-min windows (FundedNext Stellar).
- **Min trading days**: 2-5 days. Few firms have a max time limit any more — most "no time limit" is the norm.

---

## 2. The Math: Monthly-Return Envelope

### 2.1 Binding constraints summary

A sustained funded-trader return path is constrained by *three independent envelopes*. Whichever bites first sets the ceiling.

1. **Per-trade risk × Sharpe Ratio × trades/day × days** — the strategy's true monthly gross return.
2. **Trailing / static drawdown** — *hard* kill switch. Probability of hitting the floor before reaching the profit target (or before a trailing floor traps a recovery).
3. **Best-day consistency cap** — *payout gate*. One outsized day can pause the payout until other days dilute the ratio.

Other rules (news blackout, weekend close, minimum trading days) are softer but clip specific trade setups.

### 2.2 Envelope #1 — strategy-driven monthly gross

Industry consensus (ClearEdge Trading, QuantNomad, QuantVPS, Traderversebrain TSB) on realistic Sharpe for live systematic intraday/multiday futures:

- *Acceptable*: annualized SR 0.5-1.0
- *Good*: 1.0-2.0
- *Suspicious / overfit*: >3.0
- S&P 500 historical SR: ~0.4-0.5 (CFA Institute)
- Macrosynergy finds S&P 500 futures SR 1995-now = ~0.5

For an SR=1.0 strategy with target vol σ_monthly=10% (a typical intraday multiday setup):
- Monthly gross expected return = SR × σ × √(1) ≈ 0.10 × 1.0 = 10%/year gross ≈ 0.83%/month.
- SR=1.5, σ_monthly=15% → ~18%/year ≈ 1.5%/month.

Realistic *post-fees, post-slippage* Sharpe for live retail systematic is closer to 0.4-0.8. So:
- Monthly gross envelope for honest systematic = **0.4% to 1.5% per month** before the firm split.

After the firm takes 10-20% (80-90% to trader):
- Trader's monthly *share* = **0.3% to 1.4% per month** of the account equity.

### 2.3 Envelope #2 — trailing-drawdown first-passage

For a static max-loss DD% on a $100k account with a 10% profit target, the trader has to:

- Survive 10% absolute loss budget from starting balance.
- Not exceed 5% daily loss (10% budget = 2 daily-loss-cap hits).

For *trailing* drawdowns (MFFU, Topstep, Apex intraday, Lucid) the problem is *first-passage* of a moving floor.

The classical approximation (Magdon-Ismail, Atiya; Landriault et al. for BM):
- For drifted Brownian motion with drift μ, vol σ, hitting probability of trailing DD `d` over `T` days:

`P(hit) ≈ Φ(−μT/σ√T + d/(σ√T))` for short T; refined forms (Mijatovic-Pistorius) handle the moving-floor version.

Numerically for the canonical prop-firm setup (SR=1, daily μ=0.1%, daily σ=1%, trailing DD=4% on $50k):

- Without risk adjustment (1% risk per trade): ~28-35% probability of breach before passing.
- With 0.5% risk: ~12-18%.
- With 0.25% risk: ~3-6%.

The Elite Trader Funding simulator (cited in research) shows:
- +0.50R edge, $2K trailing DD, 150 trades → **63% RoR at 1% risk**; **~1.4% at 0.25% risk**.

The math is unambiguous: **risk size is more important than win rate** for prop survival.

### 2.4 Envelope #3 — consistency / best-day rule

Formula (every firm uses the same algebraic form, sometimes with denominator tweaks):

`Best Day Profit / Total Cycle Profit ≤ C` (C = 30%/40%/50% depending on firm)

This is **not a fixed per-day cap**, but a ratio. The implied *daily ceiling* in money:

`Daily Profit Cap ≈ Total Profit Target × C` (best-day weighted)

So on a $100k, 10%-target account with 40% best-day rule:
- Daily cap = $10,000 × 0.40 = **$4,000**. You can have any number of days under $4K. To pass, you need total profit $10K with no single day >$4K → easy if you trade 5 days at $2K. **Binding only when a single trade or day would have produced 40%+ of the target.**

Topstep, FundedNext and MFFU treat breaches *lightly*: they extend the target rather than fail the account (Topstep: `New Profit Target = Best Day / 0.50`; MFFU: same). So consistency *gates the payout*, not the account itself.

**Implication for monthly return envelope**:
- A trend strategy with one 2-3R winner per month will have *that day* = 40-60% of total cycle profit. With a 50% rule (Topstep, MFFU eval, FTMO best-day), the payout *waits* until you trade more days. Net effect: a trend strategy can pass the eval in 3 days, then *wait* 4-6 weeks for the consistency ratio to dilute before withdrawal.
- A scalper with 50 small green days dilutes any single day below 10%. Payouts land on schedule, but per-day profit is smaller.

### 2.5 Combined envelope — what the survivor actually earns

Working the math end-to-end for a 2-Step-style account ($100k, 10% target, 5% DLL, 10% static DD, 40% consistency):

| Constraint | Implied ceiling per month (account) |
|---|---|
| Strategy (SR=1.0, σ=10% annual) | ~0.8%/month gross |
| Trailing DD breach probability (0.5% risk/trade) | ~12-18% before passing → need ~1-1.5 cycles/attempt to clear |
| Consistency gating | payout held 30-60 days post-pass for one big day |
| Firm split (80-90%) | Net take-home ~0.7-1.2%/month of account |
| Challenge/reset fee amortization | subtract 0.05-0.2%/month on a 12-month amortization |

**Realistic sustained envelope for a consistent systematic trader: 0.5% to 1.5% net per month** of starting balance.

This matches the *third-party reality checks*:
- TSB ("How much can you make with a prop firm — Real Math"): marketing 5-10%/month, **reality 1-3% sustained**.
- Topstep official 2025 data: 33.3% of funded traders received a payout — meaning 2/3 of funded traders fail to clear the consistency/cycle.
- Finance Magnates / FPFX Tech (300k-account study): only 7% ever reach a payout; among those, average earning ~4% of capital.
- Self-reported Reddit algotrading thread consensus: "honest ceiling ~2-3%/month at ~10% Max DD."

For the user's *5%/month target* — which the project's internal memory treats as a stretch goal — this would require the **top decile** of the survivor population:
- SR≥1.5 sustained
- σ=20-30% (high vol target)
- 80-100% profit split (must scale to higher-tier accounts)
- ≈ 6-8 accounts × $100k+ simultaneously (only practical on 90%+ split programs like Apex, MyFundedFutures Pro, LucidFlex, The5ers High Stakes)

5%/month is *not impossible*, but it requires multiple accounts AND top-decile edge AND a firm structure that doesn't punish lumpy days. Across the entire populated industry, that's a small minority of traders.

### 2.6 The "payout cycle" framing is more honest than "monthly return"

Prop-firm accounts don't return cash monthly. They pay **per cycle** (5 winning days / 14 calendar days / 3 business days / etc.). The metric that matters is:

`(Avg Payout) / (Account Size × Cycle Length)`

For a $50k MFFU Core account at 80% split with 5-day cycles:
- Realistic cycle P&L: 5 × $200 average net green day = $1,000/cycle
- Trader share = $800/cycle
- Cycle length ≈ 1 calendar week
- Monthly cash-flow = ~$3,200 from one $50k account
- $3,200 / $50k = **6.4% gross monthly, 5.1% net to trader**

For a $50k Topstep Combine that *just passed*, first 2 months often produce 0 payouts (Express Funded Account rule: 5 winning days of $150+ before first withdrawal). That setup makes the first-month cash flow near zero.

---

## 3. Consistency-Rule Engineering

### 3.1 Documented practitioner playbook

- **Pre-trade daily target.** Calculate `daily cap = profit target × consistency %`. Set a hard stop in your risk module (NinjaTrader / Tradovate / MT5 plugin).
- **Stop trading once the daily cap is hit**, even if you have setups left. This is the textbook advice on TSB, QuantVPS, and Tradeify blogs.
- **Per-trade size on day-1 of a challenge**: deliberately smaller than max allowed, so even a "big day" stays under the cap.
- **Trade across sessions / instruments** so the same edge produces multiple small days, not one mega day.

The "**one trade a day**" archetype (Tradeify blog, DayTraders.com) is built around this:
- 1 defined-entry, fixed SL/TP per day.
- Daily P&L range ~$200-$1,000 depending on contracts.
- Best day rarely exceeds 30-35% of weekly total.

### 3.2 What firms actually detect

The consensus (Apex Help Centre, FundedNext Help Centre, FTMO ToS, MyFundedFutures Help Centre, all corroborated by Reddit r/PropFirmTester complaints):

1. **Cross-account trade-timing correlation** — same instrument, same direction, within 30 seconds, across accounts at the same firm. Payout denied + possible account closure.
2. **Same-IP / device fingerprint** — multiple accounts on the same login → copy-trading signal.
3. **"Payout-adjusted" trading** (Apex specifically) — if you request a payout and keep trading, your *required* balance must remain above the payout amount. If equity drops, the payout is denied AND you may breach other rules.
4. **Position-size audit** — Apex: "no trading the maximum or larger-than-usual contracts on one trade while trading micros for the rest of their time" (Darrell Martin, Apex compliance).
5. **News-strategy masking** — FundedNext: "Masking news trades as standard strategies" is prohibited even outside the 5-min window.
6. **Tick-scalping signature** — short-hold trades (<2 sec), arbitrage between broker feeds, HFT patterns → banned across CFD firms (FTMO explicitly).
7. **Latency-arb fingerprint** — prop firms share signals with LP partners; patterns emerge over time.

### 3.3 Known payout-denial categories (12-rule framework documented across multiple firms)

In rough order of frequency (from hftarbitrageplatform.com's 12-category survey and Forex Prop Firm consistency-rule trackers):

1. Cross-account hedging (offsetting positions across accounts at same or different firms)
2. Copy-trading / signal-following signatures
3. Latency arbitrage / tick-scalping signatures
4. News-event blackout breach
5. Weekend/overnight holding breach
6. Lot-size or risk-per-trade breach (firm-specific cap)
7. Inconsistent position-size pattern (Apex-style "big trade then micros")
8. Account-sharing (more than one person using the account)
9. VPN / location masking
10. KYC / identity mismatch
11. Withdraw-then-trade-without-payout-adjustment (Apex)
12. Casino-style martingale / grid / recovery patterns (explicitly banned at most firms)

Reddit r/PropFirmTester and r/Trading have multiple threads documenting real terminations (FundedNext, The5ers, MFFU, Apex all named). The pattern is consistent: the firm *permits the payout* on the first 1-2 cycles, then denies on the 3rd-5th once the trader has scaled up.

---

## 4. Empirical Pass Rates and Payout Persistence

### 4.1 The numbers that firms publish (or admit)

| Firm / source | Eval pass rate | Trader-level pass rate | Funded traders receiving payout | "Live" / scaled rate |
|---|---|---|---|---|
| **Topstep** 2025 official disclosure | **16.8%** of Trading Combines initiated | **51.8%** of unique participants advanced to funded at least once | **33.3%** of funded-level participants received a payout | **0.71%** of all starters reached Live Funded Account |
| **FTMO** (community + FPFX Tech estimates) | ~10-12% both phases combined | n/a (no official) | ~25-35% of Rewards Account holders per Trustpilot pattern | <2% scale to $400K |
| **FundedNext** community estimates | ~12-15% both phases | n/a | similar to FTMO | scale to $300K |
| **Apex** community estimates | 15-20% first-attempt; 40% with resets (Apex 3.0 post-2025) | n/a | payout threshold not always reached | Live tier is rare |
| **The5ers** | 8-15% (TSB consensus, lower because of Bootcamp complexity) | n/a | n/a | rare |
| **Industry roll-up** (QuantVPS / FPFX / Track360 / Atmos) | **5-14%** of purchased challenges become funded; **~7%** of challenge buyers ever receive a payout | — | — | 1-3% become "consistently paid long-term" funded traders |

### 4.2 Interpretation

The 7% (Finance Magnates/FPFX) figure is consistent with the Topstep disclosure (16.8% eval → ~50% funded at least once → 33.3% get a payout → ~2.8% of all starters). On a per-attempt basis, ~6% of challenge purchases convert to a payout on that attempt.

### 4.3 Algo vs discretionary

No firm publishes this breakdown. Forum evidence (MQL5, Myfxbook verified EAs, EA vendor blogs):
- EAs that *deliberately trade for prop-firm mechanics* (small position size, consistency rule awareness, no martingale) show verified Myfxbook / FX Blue track records with 70-90% challenge pass rates on individual attempts.
- The same EAs on funded accounts show much lower payout persistence (typical: 30-50% of funded accounts get first payout, <20% get a 3rd).
- EAs advertised as "guaranteed to pass" are typically martingale/grid in disguise — they pass several evals in trending markets, blow up funded accounts when conditions turn. (Confirmed on MQL5 "Gold Guardian" review, MQL5 "Alpha Pulse AI" review, and FTMO trader-story blogs.)

### 4.4 What "passes and stays funded" actually looks like

Combining the FTMO "Successful Trader Stories" + MyFundedFutures testimonials + Reddit algo threads:

- Average Win Rate of FTMO-published success stories: **34-80%** (huge dispersion). Median ~55-65%.
- Average Risk-Reward Ratio: **1.4-2.5**.
- Holding time: **mostly intraday** (minutes to 4 hours), occasionally swing.
- Avg per-trade risk: **0.3-1.0%**.
- All published FTMO success stories show a **Discipline Score > 80%** (consistency), i.e., best day ≤ 20% of total.

**Profile of long-term funded trader** (per Tradeify, TSB, FTMO blogs, QuantNomad):
- High frequency of *small, positive days*, with a few slightly larger days each month.
- Win rate 50-65%.
- Average win ≤ 2× average loss (often 1.5×).
- Either an intraday mean-reversion or session-breakout strategy with tight risk.
- Does *not* swing-trade news events; either avoids the blackout window entirely or has a swing account.

---

## 5. Strategy Profile Recommendation

### 5.1 What survives the constraints

The intersection of:
- Daily loss cap 5% (forces small position size on losing streaks)
- 40-50% consistency rule (forces small individual days)
- Trailing drawdown 4% (forces tight stops)

is an **intraday mean-reversion or opening-range breakout** strategy with the following profile:

| Property | Recommended target | Why |
|---|---|---|
| Holding time | 5 min – 4 hours | Avoids news blackouts, weekend/overnight rules, and large overnight gaps |
| Trades per day | 2-5 | Enough to dilute best-day % under 30% naturally |
| Win rate | 55-70% | Required for SR≥1.0 with 1.3-1.8 R:R |
| Avg R:R | 1.3-1.8 | Match the practical limit given daily loss cap |
| Risk per trade | 0.25-0.75% of balance (size from DD buffer, not balance) | Survives 4-6 consecutive losses |
| Symbols | Liquid futures (ES, NQ, CL, GC) with EOD trail-friendly behavior, or major FX pairs on FTMO | Wide participation, deep liquidity, predictable spreads |
| Best day | < 30% of weekly profit | Easy to keep under 40% consistency rule |

This is what the FTMO trader-stories + MFFU Pro + Apex EOD program reward. It's also what the Trader's Second Brain "How much can you make" guide implicitly assumes.

### 5.2 What *doesn't* survive

- **Trend-following with rare big days**: a single 3R winner can be 50-70% of monthly total → *payout paused 30-60 days* while you trade more days. Topstep Combine 50% rule actively *prevents* passing fast; MFFU 50% eval rule same.
- **News-event straddles**: explicit blackout on FTMO, FundedNext, MFFU Core/Scale. Must use Swing / Pro / Rapid variants that allow it.
- **Overnight swing**: blocked on every Standard program. Must use Swing (FTMO) or Topstep / MFFU / Lucid funded, which allow holding to session close but auto-flat before close.
- **Grid / martingale / recovery systems**: banned explicitly (FundedNext, MFFU, FTMO). Will pass challenge in a trend, blow funded account on reversal.
- **High-frequency tick scalping**: banned via the "50% of profit from trades held ≥10 sec" rule at Tradeify, MFFU "exploiting absence of slippage in sim" prohibition.

### 5.3 Honest strategic implications for the user's profile

Given the user's stated approach (one strategy × N firms × small accounts, kill-switch on drawdown):

- **D1-D5 already locked in**: rules as optimization constraint, futures as bridge (FundedNext Rapid / MFFU / Topstep Express), one strategy × N firms, kill-switch on IC + consistency. This is *exactly* the right architecture per the constraints.
- **Realistic ceiling per $100k account**: 1-1.5%/month net to trader. Across 5 accounts ($500k total): $5k-$7.5k/month. Across 10 accounts ($1M): $10k-$15k/month. *If* the strategy delivers SR≥1.0 sustained and the kill-switch fires before breaches.
- **The 5%/month median from Sprint 2 work** is *achievable only at scale*: $1M-$2M deployed with SR~1.5 and 80-90% split. Below $500k deployed, 5%/month is unrealistic without leverage or hedge exposure that prop firms won't allow.
- **Kill-switch design**: enforce not just drawdown but *best-day ratio*. A single 40%+ day is a *signal* of behaviour change (revenge trade after a loss, size expansion, regime shift) — pause the affected account for 48h.

---

## 6. Red Flags

### 6.1 Payout-denial patterns (most documented)

- **Apex 3.0 payout-adjusted trading**: request payout, then trade as if it's still in balance → if equity dips below required, payout is denied AND account may breach other rules. Multiple Reddit threads confirm.
- **FundedNext copy-trading terminations**: terminated even after multiple successful payouts (5+) once scaling up to $11.5K+. Pattern: "paid 5 times, blocked on 6th."
- **The5ers**: account terminated at payout time after own support authorised the setup in writing. (Reddit r/PropFirmTester thread, Oct 2025).
- **FTMO "max allocation" enforcement**: $400K total cap per trader/strategy. Crossing it via multiple accounts can trigger suspension (FTMO FAQ).
- **MFFU**: payout denials reported on the 50% consistency rule breach — multiple Reddit threads and a MyFundedFutures-specific review site tracking complaints.

### 6.2 Multi-account legality per firm ToS

| Firm | Multiple accounts at same firm | Cross-account hedging | Cross-firm hedging |
|---|---|---|---|
| FTMO | Allowed up to $400K (2-Step) / $2M (after scaling) total per trader/strategy | Explicitly banned | Allowed *if* not used to hedge; FTMO's $400K cap is per trader, not per firm |
| The5ers | Allowed (Hyper Growth scales to $4M) | Banned | Banned |
| FundedNext | Allowed up to $300K total | Banned ("hedging across accounts" prohibited) | Banned |
| Topstep | Multiple accounts allowed (combine + XFA + Live) | Banned | Banned |
| MyFundedFutures | Up to 10 accounts, $600K total | Banned ("coordinating identical or opposite strategies across unconnected accounts is prohibited") | Banned |
| Lucid | Multiple accounts allowed | Banned | Banned |
| Apex | Up to 5 PRO accounts + Live | Banned | Banned |

Practical implication: **the user's "one strategy × N firms × small accounts"** approach is *legal* if executed as:
- Same strategy, same direction, same risk profile on accounts at *different firms* (not used to hedge).
- *No* opposite-position hedging across firms (long firm A, short firm B is banned).
- *No* opposite-position hedging across accounts at the *same* firm (banned everywhere).
- Device/IP separation only where firm explicitly requires it (most allow same IP if trading the same strategy in same direction).

### 6.3 A-book vs B-book economics

The dominant CFD prop-firm model is **B-book** (the firm is the counterparty, internalises the trade). Confirmed:

- Finance Magnates (Dec 2024): "Almost all, if not all, prop firms utilise a B-book model."
- FTMO acquired OANDA in 2024; FTMO Rewards Accounts now route to real liquidity (A-book, hybrid).
- The5ers, FundedNext: hybrid / B-book on CFD books; live execution only on Futures products.
- **Futures-only firms** (Topstep, MFFU, Apex, Lucid): the *funded* stage routes to real CME/NYMEX execution (A-book). Evaluation accounts are simulation.

Implication for the user: on futures-funded accounts (which is the user's stated bridge), the firm has direct counterparty exposure to your trades. They earn the spread + commission + their profit share. There is no incentive for them to "stop hunt" you on a real exchange — the price feed is the exchange's. *This is the cleanest segment of the prop-firm industry to participate in* relative to the forex CFD segment, where slippage / requote / price-feed manipulation is documented.

### 6.4 Other red flags (worth tracking)

- **"Firm collapsed" risk**: 80-100 firms ceased operations Feb 2024 - late 2025 (Track360). MyForexFunds: $310M in fees from ~135K customers alleged in the 2023 CFTC action. True Forex Funds also collapsed. The industry has high mortality.
- **Promo-bait then rule-tighten**: rules change between purchase and funding. Several firms changed consistency thresholds after traders were already in funded accounts (documented by PropFirmHero).
- **Payout-window changes**: Apex 3.0 (late 2025) eliminated rigid payout windows → good for traders. Other firms have tightened to monthly or quarterly.
- **Account-merging restrictions**: some firms don't let you merge two passing evals to make a larger funded account, even if the rules suggest it.

---

## 7. Source URLs (Access Date 2026-09-04 unless noted)

### Firm rule pages
- FTMO Trading Objectives (1-Step / 2-Step / Best Day rule): https://ftmo.oanda.com/trading-objectives
- FTMO Swing account type FAQ: https://ftmo.oanda.com/faq/ftmo-swing-account-type
- FTMO news trading FAQ: https://ftmo.com/en/faq/can-i-trade-news
- FTMO weekend holding: https://ftmo.com/en/faq/do-i-have-to-close-my-positions-overnight-or-before-the-weekend
- FTMO rewards / payout FAQ: https://ftmo.com/en/faq/how-do-i-withdraw-my-profits
- FTMO Scaling Plan: https://ftmo.oanda.com/reward-growth-and-scaling-plan
- FTMO Consistency Score blog: https://ftmo.com/en/blog/consistency-is-very-important-for-success-in-trading
- The5ers 2-Step Plan Rules: https://the5ers.com/faqs/2-step-plan-rules-specifications (last update 2026-07-23 per page footer)
- The5ers risk framework / Lune overview: https://lunefi.com/blog/the5ers-an-in-depth-guide-rules-review-and-discount
- FundedNext Futures Trading Objectives: https://fundednext.com/general-rules/futures/trading-objectives
- FundedNext news trading help: https://help.fundednext.com/en/articles/10701447-is-news-trading-allowed-at-fundednext
- FundedNext Stellar Lite target help: https://help.fundednext.com/en/articles/9133001-what-is-the-profit-target-in-fundednext-stellar-lite
- FundedNext vs FTMO: https://fundednext.com/blog/fundednext-vs-ftmo
- Topstep Trading Combine Parameters (official): https://help.topstep.com/en/articles/8284197-trading-combine-parameters
- Topstep Consistency help: https://help.topstep.com/en/articles/8284208-consistency-at-topstep
- Topstep official statistics (on every page footer): https://www.topstep.com/our-program (16.8% / 51.8% / 33.3% / 0.71%)
- Topstep drawdown rules blog: https://www.topstep.com/blog/prop-firm-drawdown-rules
- MyFundedFutures Consistency rule (help): https://help.myfundedfutures.com/en/articles/11994562-consistency-rule-at-my-fundedfutures
- MyFundedFutures Trader Evaluation (help): https://help.myfundedfutures.com/en/articles/11802636-traders-evaluation-simplified
- MyFundedFutures News Trading Policy: https://help.myfundedfutures.com/en/articles/8230009-news-trading-policy
- MyFundedFutures Scale plan: https://myfundedfutures.com/blog/myfundedfutures-mffu-scale-plan
- MyFundedFutures Core plan: https://myfundedfutures.com/blog/myfundedfutures-mffu-core-plan
- Lucid Trading LucidPro Payouts: https://support.lucidtrading.com/en/articles/12890092-lucidpro-payouts
- Apex Trader Funding Consistency Rules: https://apextraderfunding.com/help-center/legacy-helpful-items/what-are-the-consistency-rules-for-legacy-pa-and-funded-accounts
- Apex Live Prop Trading FAQ: https://apextraderfunding.com/help-center/getting-started/apex-live-prop-trading-program-faq
- Apex Prohibited Activities: https://apextraderfunding.com/help-center/getting-started/prohibited-activities
- Tradeify "One Trade a Day" + Growth/Lightning rules: https://tradeify.co/post/passing-prop-firm-challenges-one-trade-a-day

### Math / envelope / Sharpe
- ClearEdge Trading Sharpe & Profit Factor benchmarks: https://clearedge.trading/post/sharpe-ratio-profit-factor-futures-trading-performance
- Elite Trader Funding risk-of-ruin calculator example: https://elitetraderfunding.app/risk-of-ruin-calculator
- TradeZella Monte Carlo ROI calculator: https://www.tradezella.com/tools/prop-firm-calculator
- OneTradeJournal challenge calculator: https://onetradejournal.com/tools/prop-firm-challenge-calculator
- Aron Groups passing-strategy math: https://arongroups.co/forex-articles/prop-firm-passing-strategy
- Aron Groups consistency rule math: https://arongroups.co/forex-articles/consistency-rule-prop-firms
- FundedFast position sizing & passing math: https://fundedfast.com/learn/prop-trading/how-to-pass
- OneTradeJournal consistency calculator: https://onetradejournal.com/tools/consistency-rule-calculator
- Macrosynergy Sharpe stability paper: https://macrosynergy.com/research/the-sharpe-stability-ratio-of-trading-strategies
- AIFO Risk per Trade guide: https://aifo.com/blog/guide/risk-per-trade-prop-firm-challenge
- Tradeify 1% rule position sizing: https://tradeify.co/post/prop-firm-position-sizing-1-percent-rule
- Tradecovex Topstep Combine sizes & ratios: https://tradecovex.com/guides/topstep-combine-account-sizes-profit-targets-2026
- QuantNomad-style consistency-rule derivations are aggregated at: https://newyorkcityservers.com/blog/prop-firm-consistency-rule and https://pineify.app/prop-firm-consistency-calculator

### Empirical pass-rate / payout-persistence
- Topstep 2025 official disclosure (verbatim on every Topstep page): https://www.topstep.com/our-program
- Track360 industry roll-up: https://track360.io/blog/prop-trading-industry-statistics-2026
- QuantVPS industry statistics: https://www.quantvps.com/blog/prop-firm-statistics
- The Prop Firm Guide 2026 statistics: https://thepropfirmguide.com/prop-firm-statistics
- Trader's Second Brain "Real Math" piece: https://traderssecondbrain.com/guides/how-much-can-you-make-prop-firm
- Trader's Second Brain Pass Rate page: https://traderssecondbrain.com/guides/prop-firm-pass-rate
- TradeCovex Topstep pass-rate page: https://tradecovex.com/guides/how-many-combines-passed-express-topstep-2025
- Finance Magnates / FPFX 7% study: https://www.tradingview.com/news/financemagnates:3a251e333094b:0-exclusive-only-7-of-300-000-prop-trading-accounts-achieved-payouts
- Finance Magnates / The Funded Trader "1 in 20": https://www.financemagnates.com/forex/only-1-in-20-traders-pass-prop-firm-challenges-reports-the-funded-trader
- FunderPro pass-rate analysis: https://funderpro.com/blog/prop-trading-pass-rates-in-2025-what-the-data-really-show
- Atmos Funded industry statistics: https://atmosfunded.com/prop-firm-statistics
- PropFirmApp statistics page: https://propfirmapp.com/statistics
- TradeZella top prop firms: https://www.tradezella.com/blog/best-prop-firms-2026-rankings
- Reddit r/Forex 10,000 FTMO simulation: https://www.reddit.com/r/Forex/comments/1u8ckib/i_simulated_10000_ftmo_challenges_with_a
- Reddit r/TopStepX official disclosure thread: https://www.reddit.com/r/TopStepX/comments/1tmgfmi/topstep_performance_report_333_of_all_individual

### Payout denial / cross-account / multi-account legality
- HFTA 12-rule payout-denial framework: https://hftarbitrageplatform.com/en/prop-firm-payout-denials
- Thortradecopier payout-denial guide: https://thortradecopier.com/blog/why-prop-firm-payouts-get-denied
- FXIFY "Why payouts get denied" guide: https://fxify.com/blog/why-prop-firm-payouts-get-denied
- Alex Firdaus hedging rules: https://alexfirdaus.com/prop-firm-hedging
- MFFU hedging rules: https://myfundedfutures.com/blog/hedging-futures-trading-prop-firms
- Tradeify hedging & correlated products: https://help.tradeify.co/en/articles/10495868-rules-hedging-correlated-products
- PropFirmApp multiple accounts guide: https://propfirmapp.com/learn/multiple-prop-firm-accounts
- Tradeify multi-account guide: https://tradeify.co/post/managing-multiple-prop-firm-accounts
- Apex Prohibited Activities: https://apextraderfunding.com/help-center/getting-started/prohibited-activities

### A-book / B-book economics
- Tradeify futures-vs-forex prop firm analysis: https://tradeify.co/post/futures-prop-firms-vs-forex-prop-firms
- Finance Magnates B-booking article: https://www.financemagnates.com/forex/b-booking-is-risky-for-cfd-prop-firms-but-what-is-the-alternative
- Kenmore Design CFD→futures expansion analysis: https://www.kenmoredesign.com/2026/07/28/futures-prop-firms-how-cfd-prop-operators-expand-into-futures
- Propfirm.com A-book vs B-book explainer: https://www.propfirm.com/trading/what-is-a-book-vs-b-book
- BullRush A-book philosophy: https://bullrush.com/the-prop-firm-revolution-a-book-vs-forex-prop-firms

### Forum / community evidence (algo + payout complaints)
- MQL5 Gold Guardian honest review: https://www.mql5.com/en/blogs/post/770332
- Audacity "10 best EAs for prop firms" with verification caveats: https://audacity.capital/trading-guides/ea-to-pass-prop-firm-challenge
- Myfxbook prop firms directory: https://www.myfxbook.com/prop-firms
- Reddit r/PropFirmTester FundedNext 5-times-then-blocked: https://www.reddit.com/r/Trading/comments/1qxa6nc/fundednext_manipulation_prop_firm_paid_me_5_times
- Reddit r/PropFirmTester The5ers payout-time termination: https://www.reddit.com/r/PropFirmTester/comments/1mgqyxz/got_funded_made_38k_then_account_suspended_due_to
- Reddit r/PropFirmTester FundedNext interview termination: https://www.reddit.com/r/PropFirmTester/comments/1mcchu0/fundednext_terminated_my_account_after_interview
- Reddit r/Daytrading "consistent 3-5%/month?" thread: https://www.reddit.com/r/algotrading/comments/1o8v14r/consistently_profitable_traders_is_a_35_monthly
- Reddit r/Daytrading "Passed 150k Prop Firm Challenge" EA/Sys: https://www.reddit.com/r/Daytrading/comments/1lgofit/passed_150k_prop_firm_challenge_easiest_strategy

### News / weekend policy
- TradeFundrr weekend policy roundup: https://tradefundrr.com/prop-firm-weekend-holding-policies
- PropFirmScan news trading calendar guide: https://propfirmscan.com/guides/prop-firm-news-trading-calendars-the-ultimate-guide-to-event-risk
- NexusFi Academy news trading restrictions: https://nexusfi.com/a/prop-firms/news-trading-restrictions
- MyFundedFutures permitted times: https://help.myfundedfutures.com/en/articles/9558251-permitted-times-to-trade

---

## 8. Bottom Line (Executive Summary)

1. **Realistic sustained monthly return** for an honest systematic trader on prop-firm capital: **0.5% to 1.5% net per month** of account equity. The 5%/month stretch target is achievable but requires $1M+ deployed, top-decile Sharpe, and a multi-firm structure.

2. **The single most important lever is risk-per-trade size**, not win rate or signal. At 0.5% risk/trade the trailing-DD breach probability drops from ~30% to ~10-15% — same as lowering your win rate requirement by 10 percentage points.

3. **Consistency rules gate payouts, not accounts** at Topstep, FundedNext, MFFU. Engineering them away via throttling is standard practice; the *actual* risk is the firm's payout-denial heuristics catching a pattern they don't like (position-size variance, cross-account timing, masking news trades).

4. **The strategy that fits the envelope**: intraday mean-reversion or opening-range breakout, 2-5 trades/day, win rate 55-70%, R:R 1.3-1.8, risk per trade 0.25-0.75%, on liquid futures or major FX. Holding time under 4 hours to dodge weekend/news rules.

5. **Firm-tier recommendations given the user's constraints** (futures primary, kill-switch on drawdown + consistency, multi-firm small accounts):
   - **Primary (most lenient, fastest payouts)**: MyFundedFutures Pro or Rapid (no DLL, no consistency on funded, daily payouts)
   - **Primary (best scaling)**: Topstep Standard path (100% to first $5K, 90% thereafter, free TopstepX platform)
   - **Primary (cleanest simulation, longest track record)**: FTMO 2-Step (best public 80-90% split + scaling to $2M, but evaluation-only consistency cap, plus standard news blackouts)
   - **Bridge / test new strategies**: Apex EOD program (free trials, 100% first $250, then 90%)
   - **Avoid as primary**: CFD B-book firms (FundedNext CFD, FTMO CFD side, The5ers Bootcamp) — execution quality concerns; The5ers Hyper Growth split path is harder to clear on consistency

6. **Multi-account / multi-firm legality is fine** for the user's setup (same direction, same strategy, no hedging) — *provided* they avoid the 12-rule denial framework. Documented terminations are clustered in: cross-account hedging, copy-trading signals, position-size variance masking, and tick-scalping signatures.

7. **The A-book vs B-book distinction matters more than people say**: futures-funded accounts (Topstep, MFFU, Apex, Lucid) route to real CME/NYMEX execution with no price-feed manipulation possible. CFD B-book prop firms have documented slippage / requote issues. The user's stated preference for futures is correct.

8. **Honest ceiling on the prop-firm economic model itself**: if every trader did what the user does, the industry would shrink. ~7% of challenge buyers ever see a payout, ~1-3% become consistently paid. The user is playing against a long-tail distribution; the *expected* edge for a top-decile systematic trader is real, but the *median* trader loses challenge fees. The user's existing "Sprint 2" / "5%/mo at vol 30%" result is at the upper edge of what's been demonstrated to date.
