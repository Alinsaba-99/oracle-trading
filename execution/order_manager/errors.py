"""Order manager exception hierarchy."""


class OrderError(Exception):
    """Base exception for order-related errors."""


class OrderRejectedError(OrderError):
    """Order was rejected by the broker or risk gate."""


class OrderNotFoundError(OrderError):
    """Order was not found in local state."""


class BrokerTimeoutError(OrderError):
    """Broker did not respond within the timeout window."""


class InvalidOrderError(OrderError):
    """Order request failed validation."""
