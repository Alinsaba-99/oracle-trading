"""Structured strategy spec — the space the LLM researcher proposes within.

Modo A is "LLM in the research loop": the LLM never executes code or
orders.  It fills a :class:`StrategySpec` (a small, validated DSL); the
machine builds the signal, backtests, and Monte-Carlo evaluates it.  This
is the Inalpha/stratevo "machine-approval, LLM-no-direct-order-path"
pattern — sophisticated search, deterministic validation, hard risk gate.

The spec space maps onto the existing signal library + instruments, so any
valid spec is immediately evaluable by the harness already built in Fase 6.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from analytics.backtest.protocol import BacktestSignal
from analytics.strategy.composite_signal import CompositeMTFSignal
from analytics.strategy.signals import (
    BbandReversion,
    DonchianBreakout,
    EmaTrend,
    KeltnerReversion,
    RocMomentum,
    RsiReversion,
    TrendFilteredBreakout,
    ZscoreReversion,
)
from analytics.strategy.signals_r1 import AdxTrend, MacdTrend, Pullback, VolumeBreakout
from analytics.strategy.signals_r2 import R2_SIGNALS
from analytics.strategy.timeframe import is_higher_tf

#: Instruments the search may sample. Every entry is backed by 1h/4h/1d in the
#: data lake (see ``scripts/lake_status.py``); the value is the yfinance
#: ticker used only when falling back to a live fetch.
INSTRUMENTS: dict[str, str] = {
    # metals — lake-backed from 2003
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    # FX majors — lake-backed from 2003
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "NZDUSD": "NZDUSD=X",
    # FX crosses — lake-backed from 2004-2006; different vol/carry character
    # from the majors, which widens the regime coverage of the search.
    "EURJPY": "EURJPY=X",
    "EURGBP": "EURGBP=X",
    "EURCHF": "EURCHF=X",
    "EURCAD": "EURCAD=X",
    "EURAUD": "EURAUD=X",
    "EURNZD": "EURNZD=X",
    "GBPJPY": "GBPJPY=X",
    "GBPCHF": "GBPCHF=X",
    "GBPCAD": "GBPCAD=X",
    "GBPAUD": "GBPAUD=X",
    # crypto (24/7, high vol) — lake-backed from 2017
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
}

#: Supported bar timeframes — must exist in the data lake (1m available but
#: too slow for search; 15m not in lake). Use 1h/4h/1d for search loops.
TIMEFRAMES: list[str] = ["1h", "4h", "1d"]

#: Entry-rule name -> signal builder.  The LLM picks a name + params; the
#: machine constructs the signal deterministically.
ENTRY_TYPES: dict[str, type[BacktestSignal]] = {
    "donchian_breakout": DonchianBreakout,
    "ema_trend": EmaTrend,
    "rsi_reversion": RsiReversion,
    "bband_reversion": BbandReversion,
    "trend_filtered_breakout": TrendFilteredBreakout,
    "roc_momentum": RocMomentum,
    "zscore_reversion": ZscoreReversion,
    "keltner_reversion": KeltnerReversion,
    # R1 additions usable as filter legs (trend / momentum):
    "adx_trend": AdxTrend,
    "macd_trend": MacdTrend,
    "pullback": Pullback,
    "volume_breakout": VolumeBreakout,
    # R2 long/short families (see analytics.strategy.signals_r2). These emit
    # the full -1/0/+1 domain, so the search can find short-side edges too.
    **R2_SIGNALS,
}

#: Composite multi-TF combination rules (see CompositeMTFSignal).
FILTER_MODES: list[str] = ["gate", "confirm", "size"]

#: Backtest regimes. "fixed" = full notional (higher return, more DD);
#: "sized" = volatility-scaled (lower DD, lower return).
REGIMES: list[str] = ["fixed", "sized"]

#: Spec key → DataRegistry instrument ID (for lake-backed evaluation).
#: Falls back to uppercased key when not listed (FX pairs use same id).
LAKE_INSTRUMENTS: dict[str, str] = {
    "GOLD": "XAUUSD",
    "SILVER": "XAGUSD",
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
}


class StrategySpec(BaseModel):
    """One LLM-proposed strategy, machine-validated before any execution."""

    name: str = Field(description="Short label, e.g. 'gold_trend_filtered'")
    instrument: str = Field(description="One of INSTRUMENTS keys, e.g. 'GOLD'")
    entry: str = Field(description="One of ENTRY_TYPES keys")
    entry_params: dict[str, int | float] = Field(
        default_factory=dict, description="Signal params, e.g. {'period': 20, 'ma_period': 200}"
    )
    timeframe: str = Field(default="1d", description="Primary bar timeframe (15m/1h/4h/1d)")
    regime: str = Field(
        default="sized",
        description="Backtest regime: 'fixed' (full notional) or 'sized' (vol-scaled)",
    )
    risk_pct: float = Field(default=0.01, description="Per-trade risk fraction (sized regime)")
    stop_atr_mult: float = Field(
        default=2.0, description="Stop distance in ATR multiples (sized regime)"
    )
    rationale: str = Field(default="", description="Why the LLM expects this to work")

    # R2: multi-TF composition (optional). When filter_tf is None the spec
    # is single-TF and behaves exactly as pre-R2.
    filter_tf: str | None = Field(
        default=None,
        description="Higher timeframe for the filter leg (must be > timeframe). None = single-TF.",
    )
    filter_entry: str | None = Field(
        default=None, description="ENTRY_TYPES key for the filter signal"
    )
    filter_entry_params: dict[str, int | float] = Field(
        default_factory=dict, description="Filter signal params"
    )
    filter_mode: str = Field(default="gate", description="Combination rule: gate / confirm / size")
    filter_sign: int = Field(
        default=1, description="+1 = filter allows long bias; -1 = short (gate mode only)"
    )

    def ticker(self) -> str:
        """Resolve to the yfinance ticker."""
        return INSTRUMENTS.get(self.instrument.upper(), self.instrument)

    def lake_instrument_id(self) -> str:
        """Resolve to the DataRegistry / lake instrument ID."""
        key = self.instrument.upper()
        return LAKE_INSTRUMENTS.get(key, key)

    @property
    def is_multi_tf(self) -> bool:
        """True when this spec composes a filter signal on a higher TF."""
        return self.filter_tf is not None

    def build_signal(self) -> BacktestSignal:
        """Construct the signal deterministically from the entry spec.

        Single-TF spec → returns the entry signal directly.
        Multi-TF spec  → returns a :class:`CompositeMTFSignal` wrapping the
        primary entry + filter entry. Validation happens here, not at
        compute time.
        """
        cls = ENTRY_TYPES.get(self.entry)
        if cls is None:
            raise ValueError(f"Unknown entry type {self.entry!r}; choose from {list(ENTRY_TYPES)}")
        try:
            primary_signal = cls(**self.entry_params)
        except TypeError as exc:
            raise ValueError(f"Invalid entry_params for {self.entry}: {exc}") from exc

        if not self.is_multi_tf:
            return primary_signal

        # Multi-TF: validate pair + filter leg.
        assert self.filter_tf is not None  # for type-narrowing
        if not is_higher_tf(self.timeframe, self.filter_tf):
            raise ValueError(
                f"filter_tf must be strictly higher than timeframe "
                f"(got primary={self.timeframe!r}, filter={self.filter_tf!r})"
            )
        if self.filter_entry is None:
            raise ValueError("multi-TF spec requires filter_entry")
        filter_cls = ENTRY_TYPES.get(self.filter_entry)
        if filter_cls is None:
            raise ValueError(
                f"Unknown filter_entry {self.filter_entry!r}; choose from {list(ENTRY_TYPES)}"
            )
        try:
            filter_signal = filter_cls(**self.filter_entry_params)
        except TypeError as exc:
            raise ValueError(f"Invalid filter_entry_params for {self.filter_entry}: {exc}") from exc

        return CompositeMTFSignal(
            primary_signal,
            filter_signal,
            primary_tf=self.timeframe,
            filter_tf=self.filter_tf,
            mode=self.filter_mode,
            filter_sign=self.filter_sign,
        )


def spec_summary(spec: StrategySpec, result: dict[str, Any] | None = None) -> str:
    """Compact one-line summary of a spec (+ optional eval result) for the LLM."""
    base = (
        f"{spec.name}: {spec.entry}({spec.entry_params}) on {spec.instrument}, "
        f"risk={spec.risk_pct} atr={spec.stop_atr_mult}"
    )
    if result:
        base += (
            f" -> pass={result.get('pass_rate', 0) * 100:.0f}% "
            f"sharpe={result.get('sharpe', 0):.2f} "
            f"ret={result.get('return_pct', 0):.0f}% "
            f"fail_d={result.get('fail_d', 0) * 100:.0f}% "
            f"fail_o={result.get('fail_o', 0) * 100:.0f}%"
        )
    return base
