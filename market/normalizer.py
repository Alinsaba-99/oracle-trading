"""Market data normalizer — tick validation and OHLCV bar aggregation.

The :class:`Normalizer` validates raw tick data from any source,
enriches it with a standardized timestamp, and aggregates ticks into
fixed-interval OHLCV bars.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class Normalizer:
    """Validate and aggregate market data ticks.

    Usage::

        normalizer = Normalizer()
        tick = normalizer.normalize_tick(raw)
        bar = normalizer.aggregate_bars([tick, ...], "1m")
        normalizer.validate_bar(bar)
    """

    # ------------------------------------------------------------------
    # Tick normalization
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_tick(raw: dict[str, Any]) -> dict[str, Any]:
        """Validate a raw tick dict and add a UTC timestamp.

        Expected keys: ``instrument_id``, ``price`` or ``close``, and
        ``volume``.  A missing ``price`` falls back to ``close``.

        Parameters
        ----------
        raw:
            Raw tick data from a source (Binance, yfinance, etc.).

        Returns
        -------
        dict
            Normalized tick with ``timestamp`` added if absent.

        Raises
        ------
        ValueError
            When required fields are missing or contain invalid values.
        """
        if not isinstance(raw, dict):
            msg = "Tick data must be a dict"
            raise ValueError(msg)

        instrument_id = raw.get("instrument_id") or raw.get("symbol")
        if not instrument_id:
            msg = "Missing instrument_id in tick data"
            raise ValueError(msg)

        price = raw.get("price") or raw.get("close")
        if price is None:
            msg = "Missing price/close in tick data"
            raise ValueError(msg)

        volume = raw.get("volume", 0)
        try:
            price_f = float(price)
            volume_f = float(volume)
        except (TypeError, ValueError) as exc:
            msg = f"Non-numeric price or volume: {exc}"
            raise ValueError(msg) from exc

        import math

        if (
            math.isnan(price_f)
            or math.isinf(price_f)
            or math.isnan(volume_f)
            or math.isinf(volume_f)
        ):
            msg = f"Invalid price ({price_f}) or volume ({volume_f}) — NaN/Inf rejected"
            raise ValueError(msg)

        if price_f < 0 or volume_f < 0:
            msg = "Negative price or volume not allowed"
            raise ValueError(msg)

        normalized = dict(raw)
        if "timestamp" not in normalized or not normalized["timestamp"]:
            normalized["timestamp"] = datetime.now(UTC).isoformat()

        normalized["price"] = price_f
        normalized["volume"] = volume_f
        normalized["instrument_id"] = str(instrument_id)
        return normalized

    # ------------------------------------------------------------------
    # Bar aggregation
    # ------------------------------------------------------------------

    @staticmethod
    def aggregate_bars(ticks: list[dict[str, Any]], timeframe: str) -> dict[str, Any]:
        """Aggregate a list of normalized ticks into a single OHLCV bar.

        Parameters
        ----------
        ticks:
            List of normalized tick dicts.  Each must have ``price`` and
            ``volume`` keys.
        timeframe:
            Bar interval label, e.g. ``"1m"``, ``"5m"``, ``"1h"``.
            Stored verbatim on the output.

        Returns
        -------
        dict
            OHLCV bar with keys ``open``, ``high``, ``low``, ``close``,
            ``volume``, ``trades``, ``timeframe``, ``instrument_id``,
            ``timestamp``.

        Raises
        ------
        ValueError
            When the tick list is empty.
        """
        if not ticks:
            msg = "Cannot aggregate empty tick list"
            raise ValueError(msg)

        instrument_id = ticks[0].get("instrument_id", "")
        prices = [t["price"] for t in ticks]
        volumes = [t["volume"] for t in ticks]

        bar = {
            "instrument_id": instrument_id,
            "timeframe": timeframe,
            "open": prices[0],
            "high": max(prices),
            "low": min(prices),
            "close": prices[-1],
            "volume": sum(volumes),
            "trades": len(ticks),
            "timestamp": ticks[0].get("timestamp", ""),
        }
        return bar

    # ------------------------------------------------------------------
    # Bar validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_bar(bar: dict[str, Any]) -> None:
        """Validate OHLCV consistency and reject NaN/inf values.

        Checks:
        - ``high >= max(open, close)``
        - ``low <= min(open, close)``
        - No NaN or Inf in numeric fields
        - ``volume >= 0``

        Parameters
        ----------
        bar:
            OHLCV bar dict to validate.

        Raises
        ------
        ValueError
            When any validation check fails.
        """
        required = ("open", "high", "low", "close", "volume")
        for key in required:
            value = bar.get(key)
            if value is None:
                msg = f"Missing required bar field: {key}"
                raise ValueError(msg)

        open_, high_, low_, close_, volume_ = (
            float(bar["open"]),
            float(bar["high"]),
            float(bar["low"]),
            float(bar["close"]),
            float(bar["volume"]),
        )

        # NaN / Inf checks
        import math

        for name, val in (
            ("open", open_),
            ("high", high_),
            ("low", low_),
            ("close", close_),
            ("volume", volume_),
        ):
            if math.isnan(val) or math.isinf(val):
                msg = f"Invalid numeric value for {name}: {val}"
                raise ValueError(msg)

        # OHLC consistency
        if high_ < max(open_, close_):
            msg = f"High ({high_}) < max(open={open_}, close={close_})"
            raise ValueError(msg)

        if low_ > min(open_, close_):
            msg = f"Low ({low_}) > min(open={open_}, close={close_})"
            raise ValueError(msg)

        if volume_ < 0:
            msg = f"Negative volume: {volume_}"
            raise ValueError(msg)
