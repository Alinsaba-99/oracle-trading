"""Expression-based alpha factors — AST, parser, and evaluator.

Allows expressing alpha factors as trees of operators:

    sma(close, 20) / ts_std(close, 20)
    rank(ts_mean(close, 5) - ts_mean(close, 20))
    correlation(close, volume, 20)

The GA can evolve these expressions using DEAP's GP module,
or they can be hand-crafted and optimised via parameter search.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl


# ---------------------------------------------------------------------------
# Expression Tree Nodes
# ---------------------------------------------------------------------------


class ExprNode:
    """Base class for expression tree nodes."""

    def __repr__(self) -> str:
        return self.__str__()


class OpNode(ExprNode):
    """Node representing an operator applied to arguments."""

    __slots__ = ("op", "args")

    def __init__(self, op: str, args: list[ExprNode]) -> None:
        self.op = op
        self.args = args

    def __str__(self) -> str:
        if self.op in ("+", "-", "*", "/") and len(self.args) == 2:
            return f"({self.args[0]} {self.op} {self.args[1]})"
        if self.op == "neg" and len(self.args) == 1:
            return f"-{self.args[0]}"
        return f"{self.op}({', '.join(str(a) for a in self.args)})"


class LeafNode(ExprNode):
    """Leaf node referencing a data column."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return self.name


class ConstNode(ExprNode):
    """Constant numeric value."""

    __slots__ = ("value",)

    def __init__(self, value: float) -> None:
        self.value = value

    def __str__(self) -> str:
        if self.value == int(self.value):
            return str(int(self.value))
        return f"{self.value:.10f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# Parser — converts string expressions into AST
# ---------------------------------------------------------------------------


class ParseError(ValueError):
    """Expression parse error."""


_LEAF_NAMES: set[str] = {
    "open", "high", "low", "close", "volume", "returns", "vwap",
}


def _tokenize(s: str) -> list[tuple[str, str]]:
    """Yield (type, value) tokens."""
    tokens: list[tuple[str, str]] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c in " \t\n\r":
            i += 1
        elif c in "(),":
            tokens.append(("DELIM", c))
            i += 1
        elif c in "+-*/":
            tokens.append(("OP", c))
            i += 1
        elif c.isdigit() or (c == "." and i + 1 < len(s) and s[i + 1].isdigit()):
            j = i
            while j < len(s) and (s[j].isdigit() or s[j] == "."):
                j += 1
            tokens.append(("NUM", s[i:j]))
            i = j
        elif c.isalpha() or c == "_":
            j = i
            while j < len(s) and (s[j].isalnum() or s[j] == "_"):
                j += 1
            tokens.append(("NAME", s[i:j]))
            i = j
        else:
            raise ParseError(f"Unexpected character {c!r} at position {i}")
    return tokens


class _Parser:
    """Recursive-descent parser."""

    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> tuple[str, str] | None:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _advance(self) -> tuple[str, str]:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, typ: str, val: str | None = None) -> tuple[str, str]:
        tok = self._peek()
        if tok is None:
            raise ParseError(f"Expected {val or typ}, got end of input")
        if tok[0] != typ or (val is not None and tok[1] != val):
            raise ParseError(f"Expected {val or typ}, got {tok[1]!r}")
        return self._advance()

    def parse(self) -> ExprNode:
        node = self._expr()
        if self._peek() is not None:
            tok = self._peek()
            assert tok is not None  # type narrowing
            raise ParseError(f"Unexpected token {tok!r} after expression")
        return node

    def _expr(self) -> ExprNode:
        left = self._term()
        while True:
            tok = self._peek()
            if tok is None or tok[0] != "OP" or tok[1] not in "+-":
                break
            op = self._advance()[1]
            right = self._term()
            left = OpNode(op, [left, right])
        return left

    def _term(self) -> ExprNode:
        left = self._factor()
        while True:
            tok = self._peek()
            if tok is None or tok[0] != "OP" or tok[1] not in "*/":
                break
            op = self._advance()[1]
            right = self._factor()
            left = OpNode(op, [left, right])
        return left

    def _factor(self) -> ExprNode:
        tok = self._peek()
        if tok is None:
            raise ParseError("Unexpected end of expression")
        if tok[1] == "-":
            self._advance()
            return OpNode("neg", [self._factor()])
        if tok[1] == "(":
            self._advance()
            node = self._expr()
            self._expect("DELIM", ")")
            return node
        if tok[0] == "NUM":
            self._advance()
            return ConstNode(float(tok[1]))
        if tok[0] == "NAME":
            name = tok[1]
            self._advance()
            next_tok = self._peek()
            if next_tok is not None and next_tok[1] == "(":
                self._advance()
                args: list[ExprNode] = []
                while True:
                    nt = self._peek()
                    if nt is None or nt[1] == ")":
                        break
                    args.append(self._expr())
                    peek_comma = self._peek()
                    if peek_comma is None or peek_comma[1] != ",":
                        break
                    self._advance()
                self._expect("DELIM", ")")
                return OpNode(name, args)
            return LeafNode(name)
        raise ParseError(f"Unexpected token {tok!r}")


def parse_expression(s: str) -> ExprNode:
    """Parse a string expression into an AST."""
    tokens = _tokenize(s)
    parser = _Parser(tokens)
    return parser.parse()


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


def _to_scalar(a: np.ndarray) -> float | int | np.ndarray:
    """Extract scalar from singleton constant array, else pass through."""
    if isinstance(a, np.ndarray) and a.ndim == 1 and len(a) == 1:
        val = float(a[0])
        return int(val) if val == int(val) else val
    return a


def _get_leaf_data(name: str, data: pl.DataFrame) -> np.ndarray:
    """Extract a column from the DataFrame as numpy array."""
    col = name.lower()
    if col == "returns":
        close = data["close"].to_numpy()
        ret = np.diff(close, prepend=close[0]) / (close + 1e-10)
        return ret
    if col == "vwap":
        high_arr = data["high"].to_numpy()
        low_arr = data["low"].to_numpy()
        close_arr = data["close"].to_numpy()
        return (high_arr + low_arr + close_arr) / 3.0
    if col in data.columns:
        return data[col].to_numpy()
    raise ValueError(f"Unknown leaf: {name!r}. Available columns: {list(data.columns)}")


def evaluate(
    node: ExprNode,
    data: pl.DataFrame,
    op_map: dict[str, Any],
) -> np.ndarray:
    """Evaluate an expression tree on market data.

    Args:
        node: Root of the expression AST.
        data: OHLCV DataFrame.
        op_map: Dictionary mapping operator names to callables.

    Returns:
        Signal array of dtype float64.
    """
    if isinstance(node, ConstNode):
        return np.array([node.value], dtype=np.float64)

    if isinstance(node, LeafNode):
        return _get_leaf_data(node.name, data).astype(np.float64)

    if isinstance(node, OpNode):
        arg_arrays = [evaluate(a, data, op_map) for a in node.args]

        # Arithmetic operators
        if node.op == "neg":
            return -arg_arrays[0]
        if node.op == "+":
            return _to_scalar(arg_arrays[0]) + _to_scalar(arg_arrays[1])  # type: ignore[return-value]
        if node.op == "-":
            return _to_scalar(arg_arrays[0]) - _to_scalar(arg_arrays[1])  # type: ignore[return-value]
        if node.op == "*":
            return _to_scalar(arg_arrays[0]) * _to_scalar(arg_arrays[1])  # type: ignore[return-value]
        if node.op == "/":
            a = _to_scalar(arg_arrays[0])
            b = _to_scalar(arg_arrays[1])
            if isinstance(b, float):
                return a / (abs(b) + 1e-10)  # type: ignore[return-value]
            return a / (np.abs(b) + 1e-10)  # type: ignore[return-value]

        # Named function: convert singleton constant arrays to scalars
        cleaned = [_to_scalar(a) for a in arg_arrays]

        if node.op in op_map:
            return op_map[node.op](*cleaned)
        if node.op in _LEAF_NAMES:
            return _get_leaf_data(node.op, data).astype(np.float64)
        raise ValueError(f"Unknown operator: {node.op!r}")

    raise TypeError(f"Unknown node type: {type(node)}")


def expression_depth(node: ExprNode) -> int:
    """Compute the depth of an expression tree."""
    if isinstance(node, (LeafNode, ConstNode)):
        return 1
    if isinstance(node, OpNode):
        return 1 + max((expression_depth(a) for a in node.args), default=0)
    return 1


def expression_to_string(node: ExprNode) -> str:
    """Render an expression tree back to its string representation."""
    return str(node)
