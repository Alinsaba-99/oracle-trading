"""GP genome encoding — bridges DEAP gp.PrimitiveTree with ExprNode AST."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

import numpy as np
from deap import gp as deap_gp

from genetics.alpha.expression import ConstNode, ExprNode, LeafNode, OpNode, expression_to_string
from genetics.alpha.operators import OPERATORS_MAP

# Map between symbolic infix operators (ExprNode uses "+", "-", etc.)
# and named functions registered in the primitive set.
_ARITHMETIC_TO_NAMED: dict[str, str] = {"+": "add", "-": "sub", "*": "mul", "/": "div"}
_NAMED_TO_ARITHMETIC: dict[str, str] = {v: k for k, v in _ARITHMETIC_TO_NAMED.items()}

# ---------------------------------------------------------------------------
# Primitive set
# ---------------------------------------------------------------------------

# Data leaves available as terminals (LeafNode equivalents)
_DATA_LEAVES: list[str] = ["close", "open", "high", "low", "volume", "returns", "vwap"]

# Numeric constants registered as named terminals
_NUMERIC_CONSTANTS: list[int] = [2, 3, 5, 7, 10, 14, 20, 30, 50, 60, 100, 200]


def _infer_arg_count(fn: Callable[..., Any]) -> int | None:
    """Infer argument count from function signature."""
    try:
        sig = inspect.signature(fn)
        count = sum(
            1
            for p in sig.parameters.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) and p.default is p.empty
        )
        return count
    except (ValueError, TypeError):
        return None


def _wrap_primitive(fn: Callable[..., Any], name: str) -> Callable[..., Any]:
    """Wrap an operator so it broadcasts scalar arguments to arrays.

    DEAP passes each argument as a separate positional argument.
    Our operators expect np.ndarray arguments.  If a window-size
    argument (int) arrives as a scalar, broadcast it to the length
    of the first array argument.
    """
    sig_len = _infer_arg_count(fn)
    if sig_len is None:
        return fn

    def wrapper(*args: Any, _fn: Callable[..., Any] = fn) -> np.ndarray:
        # Broadcast any scalar int argument to the length of the first array
        # This handles operators like ts_mean(x, d) where d is a constant
        expanded: list[Any] = []
        first_arr: np.ndarray | None = None
        for a in args:
            if isinstance(a, (int, float)) and first_arr is not None:
                expanded.append(np.full_like(first_arr, a))
            else:
                if isinstance(a, np.ndarray) and first_arr is None:
                    first_arr = a
                expanded.append(a)
        return np.asarray(_fn(*expanded))

    wrapper.__name__ = name
    wrapper.__qualname__ = name
    return wrapper


def create_primitive_set() -> deap_gp.PrimitiveSetTyped:
    """Create DEAP primitive set with all operators.

    Returns a PrimitiveSetTyped where:
    - PSET.terminals[object] = list of terminal names (close, volume, ...)
    - PSET.primitives[object] = list of operator wrappers

    All operators accept/return np.ndarray (object type) to avoid
    strict type constraints in the GP system.
    """
    pset = deap_gp.PrimitiveSetTyped("ALPHA", [], object)

    # Register terminals (data leaves)
    for name in _DATA_LEAVES:
        pset.addTerminal(name, object, name=name)

    # Register numeric constants
    for val in _NUMERIC_CONSTANTS:
        pset.addTerminal(val, object, name=f"_{val}")

    # Register operators from OPERATORS_MAP
    # Skip leaf extractors — data access is via LeafNode
    for name, fn in sorted(OPERATORS_MAP.items()):
        if name.startswith("leaf_"):
            continue
        sig_len = _infer_arg_count(fn)
        if sig_len is None or sig_len == 0:
            continue
        wrapped = _wrap_primitive(fn, name)
        pset.addPrimitive(wrapped, [object] * sig_len, object, name=name)

    return pset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_prim(pset: deap_gp.PrimitiveSetTyped, name: str) -> deap_gp.Primitive:
    """Look up a Primitive by name in the primitive set."""
    for p in pset.primitives[object]:
        if p.name == name:
            return p
    raise ValueError(f"Operator {name!r} not in primitive set")


def _find_terminal(pset: deap_gp.PrimitiveSetTyped, name: str) -> deap_gp.Terminal:
    """Look up a Terminal by name in the terminal set."""
    for t in pset.terminals[object]:
        if t.name == name:
            return t
    raise ValueError(f"Terminal {name!r} not in terminal set")


# ---------------------------------------------------------------------------
# AST -> DEAP tree
# ---------------------------------------------------------------------------


def expr_to_gp_tree(node: ExprNode, pset: deap_gp.PrimitiveSetTyped) -> deap_gp.PrimitiveTree:
    """Convert an ExprNode AST into a DEAP PrimitiveTree (for seeding)."""

    def _build(n: ExprNode) -> list[deap_gp.Primitive | deap_gp.Terminal]:
        if isinstance(n, ConstNode):
            if n.value in _NUMERIC_CONSTANTS and n.value == int(n.value):
                return [_find_terminal(pset, f"_{int(n.value)}")]
            return [deap_gp.Terminal(n.value, False, object)]
        if isinstance(n, LeafNode):
            return [_find_terminal(pset, n.name)]
        if isinstance(n, OpNode):
            gp_name = _ARITHMETIC_TO_NAMED.get(n.op, n.op)
            prim = _find_prim(pset, gp_name)
            result: list[deap_gp.Primitive | deap_gp.Terminal] = [prim]
            for arg in n.args:
                result.extend(_build(arg))
            return result
        raise TypeError(f"Unknown node type: {type(n)}")

    return deap_gp.PrimitiveTree(_build(node))
    raise TypeError(f"Unknown node type: {type(node)}")


# ---------------------------------------------------------------------------
# DEAP tree -> AST
# ---------------------------------------------------------------------------


def gp_tree_to_expr(tree: deap_gp.PrimitiveTree) -> ExprNode:
    """Convert a DEAP PrimitiveTree back into an ExprNode AST.

    DEAP stores the tree in prefix order:
        [primitive, arg1_node, arg2_node, ...]
    """
    stack: list[ExprNode] = []
    for node in reversed(tree):
        if isinstance(node, deap_gp.Terminal):
            val = node.value
            if isinstance(val, str):
                # Named constants use _N prefix; everything else is a data leaf
                if val.startswith("_") and val[1:].lstrip("-").isdigit():
                    stack.append(ConstNode(float(val[1:])))
                else:
                    stack.append(LeafNode(val))
            else:
                stack.append(ConstNode(float(val)))
        elif isinstance(node, deap_gp.Primitive):
            n_args = node.arity
            args = [stack.pop() for _ in range(n_args)]
            # Map named functions back to symbolic infix operators
            op_name = _NAMED_TO_ARITHMETIC.get(node.name, node.name)
            stack.append(OpNode(op_name, args))
    if not stack:
        return ConstNode(0.0)
    return stack[0]


# ---------------------------------------------------------------------------
# Random generation
# ---------------------------------------------------------------------------


def random_expression(
    pset: deap_gp.PrimitiveSetTyped, min_depth: int = 1, max_depth: int = 5
) -> deap_gp.PrimitiveTree:
    """Generate a random GP tree (full or grow method)."""
    expr = deap_gp.genHalfAndHalf(pset, min_depth, max_depth)
    return deap_gp.PrimitiveTree(expr)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def tree_to_string(tree: deap_gp.PrimitiveTree) -> str:
    """Convert DEAP PrimitiveTree back to expression string."""
    expr = gp_tree_to_expr(tree)
    return expression_to_string(expr)
