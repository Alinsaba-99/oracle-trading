"""Domain enumerations."""

from enum import StrEnum


class AssetClass(StrEnum):
    equity = "equity"
    crypto = "crypto"
    fx = "fx"
    option = "option"
    future = "future"


class TimeFrame(StrEnum):
    tick = "tick"
    m1 = "1m"
    m5 = "5m"
    m15 = "15m"
    m30 = "30m"
    h1 = "1h"
    h4 = "4h"
    d1 = "1d"
    w1 = "1w"
    M1 = "1M"


class OrderSide(StrEnum):
    buy = "buy"
    sell = "sell"


class OrderType(StrEnum):
    market = "market"
    limit = "limit"
    stop = "stop"


class TimeInForce(StrEnum):
    day = "day"
    gtc = "gtc"
    ioc = "ioc"
    fok = "fok"


class OrderStatus(StrEnum):
    pending = "pending"
    submitted = "submitted"
    partially_filled = "partially_filled"
    filled = "filled"
    cancelled = "cancelled"
    rejected = "rejected"


class TradeDirection(StrEnum):
    long = "long"
    short = "short"


class TradeStatus(StrEnum):
    open = "open"
    closed = "closed"


class PortfolioType(StrEnum):
    live = "live"
    paper = "paper"
    shadow = "shadow"
    backtest = "backtest"


class StrategyStatus(StrEnum):
    developing = "developing"
    backtesting = "backtesting"
    paper = "paper"
    shadow = "shadow"
    live = "live"
    paused = "paused"


class RegimeVolatility(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    panic = "panic"


class RegimeTrend(StrEnum):
    bull = "bull"
    bear = "bear"
    sideways = "sideways"
    choppy = "choppy"


class RegimeLiquidity(StrEnum):
    normal = "normal"
    tight = "tight"
    crisis = "crisis"


class RegimeCorrelation(StrEnum):
    risk_on = "risk_on"
    risk_off = "risk_off"
    mixed = "mixed"


class MarketPhase(StrEnum):
    accumulation = "accumulation"
    markup = "markup"
    distribution = "distribution"
    markdown = "markdown"


class PolicyType(StrEnum):
    hard_limit = "hard_limit"
    soft_limit = "soft_limit"
    compliance = "compliance"
    market_condition = "market_condition"
    governance = "governance"


class PolicyDecision(StrEnum):
    approved = "approved"
    rejected = "rejected"
    warning = "warning"


class ExperimentType(StrEnum):
    backtest = "backtest"
    ga_run = "ga_run"
    ga_evolution = "ga_evolution"
    training = "training"
    paper_trade = "paper_trade"


class ExperimentStatus(StrEnum):
    running = "running"
    completed = "completed"
    failed = "failed"


class PluginLifecycle(StrEnum):
    registered = "registered"
    validated = "validated"
    initialized = "initialized"
    started = "started"
    stopped = "stopped"
    disposed = "disposed"
