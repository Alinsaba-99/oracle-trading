"""Lane B value catalog — Piotroski F-Score, Lakonishok value, Greenblatt (BL-505).

Implements three academic value-investing factors for the Lane B turnaround
universe (per deep-research 2026-08-15 §2.5):

1. **Piotroski F-Score** (Piotroski 2000, J. Accounting Research):
   9-point binary score across profitability, leverage/liquidity, operating
   efficiency. Long-only high-B/M + high F-Score portfolio earned 7.5%
   annual beat over 1991-2008 in original paper.

2. **Lakonishok Value-Momentum** (Lakonishok, Shleifer, Vishny 1994, J. Finance):
   Value strategies yield higher returns because they exploit mistakes of
   the typical investor, NOT because they are fundamentally riskier. Buy
   low P/B + low P/E + positive momentum.

3. **Greenblatt Magic Formula** (Greenblatt 2005, "The Little Book That
   Beats the Market"): rank by earnings yield (EBIT/EV) + return on capital.
   Not guaranteed (magicformulainvesting.com disclaimer: "nothing magical").

References
----------
- Piotroski, J. (2000). "Value Investing: The Use of Historical Financial
  Statement Information to Separate Winners from Losers." *Journal of
  Accounting Research* 38(Suppl):1-41. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2434586
- Lakonishok, J., Shleifer, A., Vishny, R. (1994). "Contrarian Investment,
  Extrapolation, and Risk." *Journal of Finance* 49(5):1541-1578.
  https://www.nber.org/papers/w4360
- Greenblatt, J. (2005). "The Little Book That Beats the Market."
  https://www.magicformulainvesting.com/
- Deep-research synthesis 2026-08-15 §2.5.

Lane B scope
------------
Lane B is **portafoglio personale operatore**, NOT prop-firm (per ADR-018).
The5ers/Lucid/MFF offer futures/CFD, not single stocks. The operators's
INTC/Xiaomi turnaround intuition is formalised here as a systematic screen
on a paniere of 20-30 depressed-multiples stocks with identifiable catalyst.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

# =========================================================================
# Piotroski F-Score (9-point)
# =========================================================================


@dataclass(frozen=True)
class PiotroskiFScore:
    """Piotroski 9-point binary accounting score.

    Categories (Piotroski 2000 §3):
    - Profitability (4 points): ROA, Operating CF, ΔROA, Accruals
    - Leverage/Liquidity/Source of Funds (3 points): ΔLeverage, ΔCurrentRatio, Equity Issuance
    - Operating Efficiency (2 points): ΔGrossMargin, ΔAssetTurnover

    Each component is binary (0 or 1). Total score in [0, 9].
    Long high F-Score (>=7) stocks in a high-B/M universe per the original paper.
    """

    @staticmethod
    def compute(
        roa: float | None,
        cfo: float | None,
        roa_prev: float | None,
        accruals: float | None,
        leverage_prev: float | None,
        leverage_curr: float | None,
        current_ratio_prev: float | None,
        current_ratio_curr: float | None,
        equity_issued: bool | None,
        gross_margin_prev: float | None,
        gross_margin_curr: float | None,
        asset_turnover_prev: float | None,
        asset_turnover_curr: float | None,
    ) -> int:
        """Return the 9-point F-Score (0 if data missing for a component)."""
        score = 0

        # Profitability
        if roa is not None and roa > 0:
            score += 1
        if cfo is not None and cfo > 0:
            score += 1
        if roa is not None and roa_prev is not None and roa > roa_prev:
            score += 1
        # Accruals: CFO > ROA (positive cash accrual, i.e., earnings quality)
        if cfo is not None and roa is not None and cfo > roa:
            score += 1

        # Leverage/Liquidity/Source of Funds
        if (
            leverage_curr is not None
            and leverage_prev is not None
            and leverage_curr < leverage_prev
        ):
            score += 1
        if (
            current_ratio_curr is not None
            and current_ratio_prev is not None
            and current_ratio_curr > current_ratio_prev
        ):
            score += 1
        # No equity issuance (clean capital structure; Binary 1 if no new shares issued)
        if equity_issued is not None and not equity_issued:
            score += 1

        # Operating Efficiency
        if (
            gross_margin_curr is not None
            and gross_margin_prev is not None
            and gross_margin_curr > gross_margin_prev
        ):
            score += 1
        if (
            asset_turnover_curr is not None
            and asset_turnover_prev is not None
            and asset_turnover_curr > asset_turnover_prev
        ):
            score += 1

        return score

    @staticmethod
    def compute_from_row(row: dict[str, object]) -> int:
        """Compute F-Score from a named row mapping (e.g. ``iter_rows(named=True)``).

        Expected columns (all optional, None if missing):
            roa, cfo, roa_prev, accruals, leverage_prev, leverage_curr,
            current_ratio_prev, current_ratio_curr, equity_issued,
            gross_margin_prev, gross_margin_curr, asset_turnover_prev,
            asset_turnover_curr
        """

        def get(name: str) -> float | bool | None:
            try:
                v = row[name]
            except Exception:
                return None
            if v is None:
                return None
            try:
                return float(v)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None

        def get_bool(name: str) -> bool | None:
            try:
                v = row[name]
            except Exception:
                return None
            if v is None:
                return None
            return bool(v)

        return PiotroskiFScore.compute(
            roa=get("roa"),
            cfo=get("cfo"),
            roa_prev=get("roa_prev"),
            accruals=get("accruals"),
            leverage_prev=get("leverage_prev"),
            leverage_curr=get("leverage_curr"),
            current_ratio_prev=get("current_ratio_prev"),
            current_ratio_curr=get("current_ratio_curr"),
            equity_issued=get_bool("equity_issued"),
            gross_margin_prev=get("gross_margin_prev"),
            gross_margin_curr=get("gross_margin_curr"),
            asset_turnover_prev=get("asset_turnover_prev"),
            asset_turnover_curr=get("asset_turnover_curr"),
        )


# =========================================================================
# Lakonishok Value-Momentum
# =========================================================================


@dataclass(frozen=True)
class LakonishokValueMomentum:
    """Lakonishok-Shleifer-Vishny value-momentum composite.

    Long low-P/B + low-P/E + positive-past-return stocks. The "value" signal
    is a composite rank (lower multiples = higher rank). The "momentum" filter
    requires positive 12-month past return (avoid "value traps").

    References
    ----------
    Lakonishok, Shleifer, Vishny (1994) show value strategies yield higher
    returns because they exploit mistakes of the typical investor, NOT
    because they are fundamentally riskier. Original universe: high-B/M
    decile of CRSP, 1963-1990, 7.5% annual beat vs low-B/M decile.
    """

    pb_rank_threshold: int = 30  # bottom 30% by P/B (cheapest)
    pe_rank_threshold: int = 30  # bottom 30% by P/E (cheapest)
    past_return_min: float = 0.0  # require non-negative 12-mo past return

    def filter(
        self,
        df: pl.DataFrame,
        *,
        pb_col: str = "pb",
        pe_col: str = "pe",
        past_return_col: str = "return_12m",
    ) -> pl.DataFrame:
        """Filter to the value-momentum long universe.

        Parameters
        ----------
        df : pl.DataFrame
            Universe with columns pb, pe, return_12m. NaN values are filtered
            out before rank computation.

        Returns
        -------
        pl.DataFrame
            Subset of stocks that pass both value (cheap multiples) and
            momentum (positive past return) filters.
        """
        if df.height == 0:
            return df

        cols = df.columns
        if pb_col not in cols and pe_col not in cols and past_return_col not in cols:
            return pl.DataFrame(schema=df.schema)

        # Drop rows with missing critical data
        df_clean = df
        for c in [pb_col, pe_col, past_return_col]:
            if c in df_clean.columns:
                df_clean = df_clean.filter(pl.col(c).is_not_null())

        if df_clean.height == 0:
            return pl.DataFrame(schema=df.schema)

        # Compute percentile rank within cleaned universe (1 = cheapest)
        ranked = df_clean
        if pb_col in cols:
            ranked = ranked.with_columns(pl.col(pb_col).rank(method="ordinal").alias("pb_rank"))
            n = ranked.height
            ranked = ranked.with_columns(
                (pl.col("pb_rank") <= max(1, int(0.30 * n))).alias("pb_cheap")
            )
        if pe_col in cols:
            ranked = ranked.with_columns(pl.col(pe_col).rank(method="ordinal").alias("pe_rank"))
            n = ranked.height
            ranked = ranked.with_columns(
                (pl.col("pe_rank") <= max(1, int(0.30 * n))).alias("pe_cheap")
            )
        if past_return_col in cols:
            ranked = ranked.with_columns(
                (pl.col(past_return_col) >= self.past_return_min).alias("mom_positive")
            )

        # Composite: require cheap on BOTH multiples AND positive momentum
        conds: list[pl.Expr] = []
        if pb_col in cols:
            conds.append(pl.col("pb_cheap"))
        if pe_col in cols:
            conds.append(pl.col("pe_cheap"))
        if past_return_col in cols:
            conds.append(pl.col("mom_positive"))

        if not conds:
            return pl.DataFrame(schema=df.schema)

        # AND all conditions
        mask: pl.Expr = conds[0]
        for cond in conds[1:]:
            mask = mask & cond
        return ranked.filter(mask)


# =========================================================================
# Greenblatt Magic Formula
# =========================================================================


@dataclass(frozen=True)
class GreenblattMagicFormula:
    """Greenblatt Magic Formula ranking.

    Rank stocks by:
    1. **Earnings yield** = EBIT / Enterprise Value (high = cheap)
    2. **Return on capital** = EBIT / (Net Working Capital + Net Fixed Assets)

    Composite rank = rank_earnings_yield + rank_return_on_capital (lower = better).

    Disclaimer
    ----------
    Per magicformulainvesting.com: "There is nothing 'magical' about the
    formula, and the use of the formula does not guarantee performance or
    investment success."
    """

    top_n: int = 30  # how many stocks to hold after ranking

    def rank(
        self,
        df: pl.DataFrame,
        *,
        ebit_col: str = "ebit",
        ev_col: str = "ev",
        nwc_col: str = "nwc",
        nfa_col: str = "nfa",
    ) -> pl.DataFrame:
        """Return df with magic_formula_rank column (lower = better).

        Top-N are the recommended long holdings.
        """
        cols = df.columns
        if ebit_col not in cols or ev_col not in cols:
            return pl.DataFrame(schema=df.schema)

        ranked = df.filter(
            pl.col(ebit_col).is_not_null() & pl.col(ev_col).is_not_null() & (pl.col(ev_col) > 0)
        )
        if ranked.height == 0:
            return pl.DataFrame(schema=df.schema)

        # Earnings yield = EBIT / EV (higher = cheaper)
        ranked = ranked.with_columns((pl.col(ebit_col) / pl.col(ev_col)).alias("earnings_yield"))
        ranked = ranked.with_columns(
            pl.col("earnings_yield").rank(method="ordinal", descending=True).alias("ey_rank")
        )

        # Return on capital = EBIT / (NWC + NFA)
        if nwc_col in cols and nfa_col in cols:
            ranked = ranked.filter(pl.col(nwc_col).is_not_null() & pl.col(nfa_col).is_not_null())
            ranked = ranked.with_columns(
                (pl.col(ebit_col) / (pl.col(nwc_col) + pl.col(nfa_col))).alias("roc")
            )
            ranked = ranked.with_columns(
                pl.col("roc").rank(method="ordinal", descending=True).alias("roc_rank")
            )
            ranked = ranked.with_columns(
                (pl.col("ey_rank") + pl.col("roc_rank")).alias("magic_formula_rank")
            )
        else:
            # Without NWC/NFA, just use earnings yield rank
            ranked = ranked.with_columns(pl.col("ey_rank").alias("magic_formula_rank"))
        return ranked.sort("magic_formula_rank").head(self.top_n)


# =========================================================================
# Composite Lane B filter (turnaround screen)
# =========================================================================


@dataclass(frozen=True)
class TurnaroundScreen:
    """Composite Lane B turnaround screen (the operator's INTC/Xiaomi intuition).

    Combines Piotroski F-Score (quality), Lakonishok value-momentum (cheap + recovering),
    and Greenblatt Magic Formula (cheap + high ROC) into a pre-registered tesi screen.

    Per ADR-018 (Lane B is for portafoglio personale operatore, NOT prop-firm):
    - universe: 20-30 depressed-multiples stocks with identifiable catalyst
    - sizing: ≤2-3% of capital per idea
    - invalidation: when thesis fails (target/stop/time), exit
    - no HARKing: pre-register in trial ledger S0.3 (BL-506)
    """

    min_f_score: int = 7  # Piotroski threshold (high quality)
    max_magic_formula_rank: int = 50  # Greenblatt: top-50 magic formula
    min_past_return_12m: float = -0.20  # depressed but recovering
    max_past_return_12m: float = 0.50  # avoid hyped/momentum stocks

    def screen(
        self,
        df: pl.DataFrame,
        *,
        f_score_col: str = "f_score",
        magic_rank_col: str = "magic_formula_rank",
        past_return_col: str = "return_12m",
    ) -> pl.DataFrame:
        """Filter to the turnaround universe.

        Pre-registered per BL-506 (trial ledger S0.3, no HARKing).
        """
        cols = df.columns
        if f_score_col not in cols or magic_rank_col not in cols or past_return_col not in cols:
            return pl.DataFrame(schema=df.schema)

        return df.filter(
            (pl.col(f_score_col) >= self.min_f_score)
            & (pl.col(magic_rank_col) <= self.max_magic_formula_rank)
            & (pl.col(past_return_col) >= self.min_past_return_12m)
            & (pl.col(past_return_col) <= self.max_past_return_12m)
        )


# =========================================================================
# Composite Lane B score (weighted blend, replaces hard-AND filters)
# =========================================================================
#
# Step 1 Opzione C (2026-08-16): instead of three AND filters that exclude
# each other (F-Score 7 AND magic_rank<=50 AND return_12m in [-20%,+50%]),
# we normalise each signal to [0,1] and combine into a single composite
# score. A name with F-Score 6 + magic_rank 5 + return_12m 0.20 now
# qualifies (it was filtered out by the AND screen); a name with
# F-Score 9 but magic_rank 80 now doesn't (the AND screen let it in).
#
# Composite formula (deep-research synthesis 2026-08-15 §2.5):
#     composite = w_f * (f_score / 9)
#               + w_m * (1 - rank / total_ranked)
#               + w_r * normalized_return_in_band
#
# where normalized_return_in_band maps [-20%, +50%] → [0, 1] linearly
# (so -20% → 0.0, +15% → 0.5, +50% → 1.0). Outside the band the signal
# is clamped to 0 or 1 — keeps the Lakonishok intuition (depressed but
# recovering is good; falling knives or hyped names are bad).
#
# Default weights (40% Piotroski, 40% Greenblatt, 20% Lakonishok):
# - Piotroski 40%: quality matters most (operator's INTC thesis)
# - Greenblatt 40%: cheap + high-ROC second pillar
# - Lakonishok 20%: value-momentum tilt, weaker weight because past
#   return is noisy on turnaround names
# Threshold >= 0.65 (vs 0.50 random) qualifies the name as a turnaround.


@dataclass(frozen=True)
class CompositeLaneBScore:
    """Weighted composite of Piotroski + Greenblatt + Lakonishok signals.

    Each signal is normalised to [0, 1] and combined into a single
    ``composite_score`` column. A higher score is better. The
    ``composite_rank`` column ranks names within each cross-section
    (publish_date), lower = better (matches ``magic_formula_rank``
    convention so downstream code can use either).
    """

    w_f_score: float = 0.40
    w_magic_rank: float = 0.40
    w_return_12m: float = 0.20
    return_band_min: float = -0.20
    return_band_max: float = 0.50
    min_composite_threshold: float = 0.65

    def __post_init__(self) -> None:
        total = self.w_f_score + self.w_magic_rank + self.w_return_12m
        if not abs(total - 1.0) < 1e-6:
            raise ValueError(f"CompositeLaneBScore weights must sum to 1.0 (got {total:.4f})")

    def score(
        self,
        df: pl.DataFrame,
        *,
        f_score_col: str = "f_score",
        magic_rank_col: str = "magic_formula_rank",
        past_return_col: str = "return_12m",
        composite_col: str = "composite_score",
        rank_col: str = "composite_rank",
        group_col: str | None = "publish_date",
    ) -> pl.DataFrame:
        """Add ``composite_score`` and ``composite_rank`` columns to df.

        Returns the input DataFrame with two new columns. Names that
        fail a signal's preconditions (e.g. null f_score) get a 0 for
        that component — they won't make it past the threshold.
        """
        cols = df.columns
        if f_score_col not in cols or magic_rank_col not in cols or past_return_col not in cols:
            return df.with_columns(
                [
                    pl.lit(None, dtype=pl.Float64).alias(composite_col),
                    pl.lit(None, dtype=pl.Int64).alias(rank_col),
                ]
            )

        # Component 1: Piotroski F-Score normalised to [0, 1] (9-point scale)
        f_norm_expr = (
            pl.when(pl.col(f_score_col).is_not_null())
            .then(pl.col(f_score_col) / 9.0)
            .otherwise(0.0)
        )

        # Component 2: Greenblatt rank normalised to [0, 1].
        # Lower rank = better, so we invert: best = 1.0, worst = 0.0.
        # ``magic_formula_rank`` is already a cross-sectional ordinal rank
        # per publish_date (see ``LaneBBacktester._compute_greenblatt_signals``),
        # so we use the raw value directly — re-ranking would collapse
        # the cross-section to [1, N] and destroy the signal.
        max_rank_expr = (
            pl.col(magic_rank_col).max().over(group_col)
            if group_col is not None and group_col in cols
            else pl.col(magic_rank_col).max()
        )
        m_norm_expr = (
            pl.when(pl.col(magic_rank_col).is_not_null())
            .then(1.0 - pl.col(magic_rank_col) / max_rank_expr)
            .otherwise(0.0)
        )

        # Component 3: Lakonishok value-momentum.
        # return_12m in [band_min, band_max] → linear [0, 1].
        # Outside the band → clamp to 0 (falling knife or hyped).
        band_range = self.return_band_max - self.return_band_min
        r_norm_expr = (
            pl.when(pl.col(past_return_col).is_not_null())
            .then((pl.col(past_return_col) - self.return_band_min) / band_range)
            .otherwise(0.0)
        ).clip(0.0, 1.0)

        composite_expr = (
            self.w_f_score * f_norm_expr
            + self.w_magic_rank * m_norm_expr
            + self.w_return_12m * r_norm_expr
        )

        result = df.with_columns([composite_expr.alias(composite_col)])

        # Rank within cross-section (lower = better), like magic_formula_rank.
        rank_within = (
            pl.col(composite_col).rank(method="ordinal", descending=True)
            if group_col is None or group_col not in cols
            else pl.col(composite_col).rank(method="ordinal", descending=True).over(group_col)
        )
        result = result.with_columns(rank_within.alias(rank_col))
        return result

    def screen(self, df: pl.DataFrame, *, composite_col: str = "composite_score") -> pl.DataFrame:
        """Filter to composite_score >= threshold."""
        if composite_col not in df.columns:
            df = self.score(df)
        return df.filter(pl.col(composite_col) >= self.min_composite_threshold)


__all__: list[str] = [
    "CompositeLaneBScore",
    "GreenblattMagicFormula",
    "LakonishokValueMomentum",
    "PiotroskiFScore",
    "TurnaroundScreen",
]
