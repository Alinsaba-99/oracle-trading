"""Tests for expression-based alpha — parser and evaluator."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from genetics.alpha.expression import (
    ConstNode,
    LeafNode,
    OpNode,
    ParseError,
    evaluate,
    expression_depth,
    parse_expression,
)

# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


def test_parse_leaf():
    node = parse_expression("close")
    assert isinstance(node, LeafNode)
    assert node.name == "close"


def test_parse_simple_op():
    node = parse_expression("ts_mean(close, 20)")
    assert isinstance(node, OpNode)
    assert node.op == "ts_mean"
    assert len(node.args) == 2
    assert isinstance(node.args[0], LeafNode)
    assert node.args[0].name == "close"
    assert isinstance(node.args[1], ConstNode)
    assert node.args[1].value == 20.0


def test_parse_binary():
    node = parse_expression("a + b")
    assert isinstance(node, OpNode)
    assert node.op == "+"


def test_parse_nested():
    node = parse_expression("ts_mean(close, 20) / ts_std(close, 20)")
    assert isinstance(node, OpNode)
    assert node.op == "/"
    assert node.args[0].op == "ts_mean"
    assert node.args[1].op == "ts_std"


def test_parse_complex():
    node = parse_expression("rank(ts_mean(close, 5) - ts_mean(close, 20))")
    assert isinstance(node, OpNode)
    assert node.op == "rank"
    assert node.args[0].op == "-"


def test_parse_with_parentheses():
    node = parse_expression("(a + b) * c")
    assert node.op == "*"


def test_parse_constant():
    node = parse_expression("42")
    assert isinstance(node, ConstNode)
    assert node.value == 42.0


def test_parse_float():
    node = parse_expression("3.14")
    assert isinstance(node, ConstNode)
    assert abs(node.value - 3.14) < 1e-10


def test_parse_unary_minus():
    node = parse_expression("-close")
    assert isinstance(node, OpNode)
    assert node.op == "neg"


def test_parse_invalid_raises():
    with pytest.raises(ParseError):
        parse_expression("foo(")  # unclosed paren
    with pytest.raises(ParseError):
        parse_expression("foo bar")  # two exprs
    with pytest.raises(ParseError):
        parse_expression("close + ")  # trailing op


def test_string_roundtrip():
    s = "ts_mean(close, 20) / ts_std(close, 20)"
    node = parse_expression(s)
    # Top-level division is wrapped in parens by infix notation
    assert str(node) == f"({s})"


# ---------------------------------------------------------------------------
# Evaluator tests
# ---------------------------------------------------------------------------


def _sample_data(n: int = 100) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    close = 100.0 + np.arange(n) * 0.05 + rng.normal(0, 0.5, n)
    return pl.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": np.abs(rng.normal(1e6, 1e5, n)),
        }
    )


@pytest.fixture
def sample_data() -> pl.DataFrame:
    return _sample_data()


def _make_op_map():
    """Minimal operator map for testing."""

    def ts_mean(x, d):
        d = int(d)
        n = len(x)
        result = np.zeros(n)
        for i in range(n):
            start = max(0, i - d + 1)
            result[i] = np.nanmean(x[start : i + 1])
        return result

    def ts_std(x, d):
        d = int(d)
        n = len(x)
        result = np.ones(n)
        for i in range(1, n):
            start = max(0, i - d + 1)
            s = np.nanstd(x[start : i + 1])
            result[i] = s if s > 1e-10 else 1.0
        return result

    return {
        "ts_mean": ts_mean,
        "ts_std": ts_std,
        "rank": lambda x: (x - np.nanmin(x)) / (np.nanmax(x) - np.nanmin(x) + 1e-10),
    }


def test_evaluate_leaf(sample_data):
    node = parse_expression("close")
    result = evaluate(node, sample_data, _make_op_map())
    assert isinstance(result, np.ndarray)
    assert len(result) == len(sample_data)
    assert np.allclose(result, sample_data["close"].to_numpy())


def test_evaluate_simple_op(sample_data):
    node = parse_expression("ts_mean(close, 5)")
    result = evaluate(node, sample_data, _make_op_map())
    assert len(result) == len(sample_data)
    assert not np.any(np.isnan(result))


def test_evaluate_binary(sample_data):
    node = parse_expression("close + 0.0")
    result = evaluate(node, sample_data, _make_op_map())
    assert np.allclose(result, sample_data["close"].to_numpy())


def test_evaluate_nested(sample_data):
    node = parse_expression("ts_mean(close, 5) / ts_std(close, 5)")
    result = evaluate(node, sample_data, _make_op_map())
    assert len(result) == len(sample_data)
    assert np.all(np.isfinite(result))


def test_evaluate_returns(sample_data):
    node = parse_expression("returns")
    result = evaluate(node, sample_data, {})
    assert len(result) == len(sample_data)
    assert np.all(np.isfinite(result))


def test_depth():
    assert expression_depth(ConstNode(1.0)) == 1
    assert expression_depth(LeafNode("close")) == 1
    n = OpNode("+", [ConstNode(1.0), ConstNode(2.0)])
    assert expression_depth(n) == 2
    n2 = OpNode("*", [n, ConstNode(3.0)])
    assert expression_depth(n2) == 3


def test_parse_multi_arg():
    node = parse_expression("correlation(close, volume, 20)")
    assert isinstance(node, OpNode)
    assert node.op == "correlation"
    assert len(node.args) == 3
