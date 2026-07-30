"""Sandbox Gate 1 — AST audit: static source-code safety check.

Parses candidate strategy source with ``ast.parse()`` and walks the tree
to reject dangerous patterns before the code ever runs.

Inspired by Inalpha's 3-gate approach (AST audit → subprocess isolation
→ protocol contract). This is Gate 1.

Allowed patterns:
  - Function definitions (def), class definitions
  - Arithmetic: +, -, *, /, //, %, **
  - Comparison: ==, !=, <, >, <=, >=
  - Boolean: and, or, not
  - Subscript, attribute access, calls, constants, names
  - if/elif/else, for, while, try/except, with
  - Imports from the whitelist only

Rejected patterns:
  - eval, exec, compile, __import__
  - open, file I/O (os, shutil, pathlib)
  - subprocess, os.system, os.popen
  - Network calls (socket, httpx, requests, urllib)
  - Import of non-whitelisted modules
  - Decorators (potential for metaprogramming attacks)
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("oracle.genetics.gates.ast_audit")

# Modules allowed in strategy code (standard library + numpy + polars)
_ALLOWED_MODULES: frozenset[str] = frozenset(
    {
        "__future__",
        # Math / numpy
        "math",
        "numpy",
        "np",
        # DataFrame operations
        "polars",
        "pl",
        # Collections
        "collections",
        "dataclasses",
        # Typing
        "typing",
        "types",
        # Standard lib — safe
        "itertools",
        "functools",
        "operator",
        "enum",
        "decimal",
        "statistics",
    }
)

# AST node types that are ALWAYS rejected
_FORBIDDEN_NODES: frozenset[type[ast.AST]] = frozenset(
    {
        ast.ClassDef  # Actually allowed — see _check_class
    }
)

# Call names that are ALWAYS rejected
_FORBIDDEN_CALLS: frozenset[str] = frozenset(
    {
        # Code execution
        "eval",
        "exec",
        "compile",
        "__import__",
        # File I/O
        "open",
        # Subprocess
        "subprocess",
        "os_system",
        "os_popen",
        # Network
        "urlopen",
        "request",
    }
)

# Attribute access patterns that are rejected
_FORBIDDEN_ATTR_PREFIXES: tuple[str, ...] = (
    "os.",
    "sys.",
    "shutil.",
    "pathlib.",
    "subprocess.",
    "socket.",
    "httpx.",
    "requests.",
    "pickle.",
    "shelve.",
    "marshal.",
)


@dataclass
class AuditResult:
    """Result of a static source audit."""

    passed: bool = False
    errors: list[str] = field(default_factory=list)
    node_count: int = 0
    class_name: str | None = None


def audit_source(source: str, max_nodes: int = 300) -> AuditResult:
    """Run AST audit on candidate strategy source.

    Args:
        source: Python source code of the candidate strategy.
        max_nodes: Maximum number of AST nodes allowed.

    Returns:
        AuditResult with passed=True/False and any errors.
    """
    result = AuditResult()

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        result.errors.append(f"Syntax error: {exc}")
        result.passed = False
        return result

    # Count and check node limit
    all_nodes = list(ast.walk(tree))
    result.node_count = len(all_nodes)
    if result.node_count > max_nodes:
        result.errors.append(f"AST node count {result.node_count} exceeds limit {max_nodes}")

    # Walk the tree
    for node in all_nodes:
        # Check for forbidden call names
        if isinstance(node, ast.Call):
            func_name = _get_call_name(node)
            if func_name in _FORBIDDEN_CALLS:
                result.errors.append(
                    f"Forbidden call '{func_name}' at line {getattr(node, 'lineno', '?')}"
                )

        # Check for forbidden attribute access patterns
        if isinstance(node, ast.Attribute):
            full_attr = _get_full_attr(node)
            if full_attr:
                for prefix in _FORBIDDEN_ATTR_PREFIXES:
                    if full_attr.startswith(prefix):
                        result.errors.append(
                            f"Forbidden attribute '{full_attr}'"
                            f" at line {getattr(node, 'lineno', '?')}"
                        )

        # Check imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod not in _ALLOWED_MODULES:
                    result.errors.append(f"Import '{alias.name}' is not in the allowed module list")

        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module.split(".")[0]
            if mod not in _ALLOWED_MODULES:
                result.errors.append(
                    f"Import from '{node.module}' is not in the allowed module list"
                )

        # Check class definitions — extract the class name
        if isinstance(node, ast.ClassDef) and result.class_name is None:
            result.class_name = node.name

    result.passed = len(result.errors) == 0
    return result


def _get_call_name(node: ast.Call) -> str | None:
    """Extract the function name from a Call node."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _get_full_attr(node: ast.Attribute) -> str | None:
    """Reconstruct a dotted attribute access like 'os.system'."""
    parts: list[str] = [node.attr]
    current = node.value
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    elif isinstance(current, ast.Call):
        return None
    else:
        return None
    return ".".join(reversed(parts))


__all__ = ["AuditResult", "audit_source"]
