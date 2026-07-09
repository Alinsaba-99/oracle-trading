"""Event models for NATS communication."""

from core.events.agent import (
    AgentAnalysisCompletedEvent,
    AgentDebateCompletedEvent,
    AgentDecisionProposedEvent,
)
from core.events.client import EventBusClient
from core.events.envelope import build_envelope
from core.events.experiment import ExperimentCompletedEvent
from core.events.feature import FeatureUpdatedEvent
from core.events.market import (
    MarketBarEvent,
    MarketOrderBookEvent,
    MarketTickEvent,
    MarketTradeEvent,
)
from core.events.order import OrderFilledEvent, OrderSubmittedEvent
from core.events.policy import PolicyApprovedEvent, PolicyRejectedEvent, PolicyWarningEvent
from core.events.portfolio import PortfolioUpdatedEvent
from core.events.regime import RegimeUpdatedEvent
from core.events.signal import SignalFilteredEvent, SignalGeneratedEvent
from core.events.subscription import SubscriptionManager
from core.events.system import (
    SYSTEM_HEALTH,
    SYSTEM_PLUGIN_REGISTERED,
    HealthEventPayload,
    PluginRegisteredPayload,
    SystemEventPayload,
)
from core.events.trade import TradeClosedEvent, TradeOpenedEvent

__all__ = [
    "SYSTEM_HEALTH",
    "SYSTEM_PLUGIN_REGISTERED",
    "AgentAnalysisCompletedEvent",
    "AgentDebateCompletedEvent",
    "AgentDecisionProposedEvent",
    "EventBusClient",
    "ExperimentCompletedEvent",
    "FeatureUpdatedEvent",
    "HealthEventPayload",
    "MarketBarEvent",
    "MarketOrderBookEvent",
    "MarketTickEvent",
    "MarketTradeEvent",
    "OrderFilledEvent",
    "OrderSubmittedEvent",
    "PluginRegisteredPayload",
    "PolicyApprovedEvent",
    "PolicyRejectedEvent",
    "PolicyWarningEvent",
    "PortfolioUpdatedEvent",
    "RegimeUpdatedEvent",
    "SignalFilteredEvent",
    "SignalGeneratedEvent",
    "SubscriptionManager",
    "SystemEventPayload",
    "TradeClosedEvent",
    "TradeOpenedEvent",
    "build_envelope",
]
