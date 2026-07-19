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

#: yfinance tickers.  All validated to serve daily; 1h/15m serve shorter history.
INSTRUMENTS: dict[str, str] = {
    # metals & commodities
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "COPPER": "HG=F",
    "CRUDE": "CL=F",
    "NATGAS": "NG=F",
    # equity indices
    "SP500": "^GSPC",
    "NASDAQ": "^NDX",
    "DOW": "^DJI",
    "RUSSELL": "^RUT",
    "DAX": "^GDAXI",
    "FTSE": "^FTSE",
    "NIKKEI": "^N225",
    # FX majors + crosses
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    # crypto (24/7, high vol)
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
}

#: Supported bar timeframes (yfinance). 1d/1h give the longest history.
TIMEFRAMES: list[str] = ["1d", "1h", "15m"]

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
}

#: Backtest regimes. "fixed" = full notional (higher return, more DD);
#: "sized" = volatility-scaled (lower DD, lower return).
REGIMES: list[str] = ["fixed", "sized"]


class StrategySpec(BaseModel):
    """One LLM-proposed strategy, machine-validated before any execution."""

    name: str = Field(description="Short label, e.g. 'gold_trend_filtered'")
    instrument: str = Field(description="One of INSTRUMENTS keys, e.g. 'GOLD'")
    entry: str = Field(description="One of ENTRY_TYPES keys")
    entry_params: dict[str, int | float] = Field(
        default_factory=dict, description="Signal params, e.g. {'period': 20, 'ma_period': 200}"
    )
    timeframe: str = Field(default="1d", description="Bar timeframe: 1d, 1h, or 15m")
    regime: str = Field(
        default="sized",
        description="Backtest regime: 'fixed' (full notional) or 'sized' (vol-scaled)",
    )
    risk_pct: float = Field(default=0.01, description="Per-trade risk fraction (sized regime)")
    stop_atr_mult: float = Field(
        default=2.0, description="Stop distance in ATR multiples (sized regime)"
    )
    rationale: str = Field(default="", description="Why the LLM expects this to work")

    def ticker(self) -> str:
        """Resolve to the yfinance ticker."""
        return INSTRUMENTS.get(self.instrument.upper(), self.instrument)

    def build_signal(self) -> BacktestSignal:
        """Construct the signal deterministically from the entry spec."""
        cls = ENTRY_TYPES.get(self.entry)
        if cls is None:
            raise ValueError(f"Unknown entry type {self.entry!r}; choose from {list(ENTRY_TYPES)}")
        try:
            return cls(**self.entry_params)
        except TypeError as exc:
            raise ValueError(f"Invalid entry_params for {self.entry}: {exc}") from exc


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
