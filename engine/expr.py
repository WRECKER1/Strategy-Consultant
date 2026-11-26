"""Safe expression evaluator for rule conditions in config/*.yaml.

Only a whitelisted subset of Python expression syntax is allowed:
names, attribute access on `t` (thresholds), numbers, strings, comparisons,
and/or/not, + - * /, and the functions mean(), abs(), min(), max().
No other code runs. This keeps the theory in config, not code (principle 2),
and stops a config file from executing arbitrary code.
"""
from __future__ import annotations

import ast
from types import SimpleNamespace
from typing import Any, Mapping

ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.USub,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div,
    ast.Name, ast.Load, ast.Constant, ast.Attribute, ast.Call, ast.List, ast.Tuple,
)


class Missing:
    """Value of an indicator/construct that is Insufficient or not applicable.

    Any comparison with Missing is False, and arithmetic with it gives Missing,
    so a rule never fires on absent evidence (MT §5.2 R5). The diagnosis
    engine reports such rules as 'Cannot assess' separately.
    """

    def __repr__(self) -> str:  # pragma: no cover
        return "Missing"

    def _cmp(self, other):
        return False

    __lt__ = __le__ = __gt__ = __ge__ = _cmp

    def __eq__(self, other):
        return isinstance(other, Missing)

    def __ne__(self, other):
        return not isinstance(other, Missing)

    def __hash__(self):
        return 0

    def _arith(self, other):
        return self

    __add__ = __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __truediv__ = __rtruediv__ = _arith

    def __neg__(self):
        return self

    def __bool__(self):
        return False


MISSING = Missing()


def _mean(*xs):
    vals = [x for x in xs if not isinstance(x, Missing)]
    return sum(vals) / len(vals) if vals else MISSING


def _abs(x):
    return x if isinstance(x, Missing) else abs(x)


FUNCTIONS = {"mean": _mean, "abs": _abs, "min": min, "max": max}


def parse(expr: str) -> ast.Expression:
    """Parse and validate an expression; raises ValueError if it is not allowed."""
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError(f"Disallowed syntax {type(node).__name__} in: {expr}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
                raise ValueError(f"Disallowed function in: {expr}")
        if isinstance(node, ast.Attribute) and not (isinstance(node.value, ast.Name) and node.value.id == "t"):
            raise ValueError(f"Attribute access allowed only on thresholds 't.' in: {expr}")
    return tree


def names_in(expr: str) -> set[str]:
    """Return free variable names used (excluding function names and 't')."""
    tree = parse(expr)
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in FUNCTIONS and node.id != "t":
            out.add(node.id)
    return out


def threshold_refs(expr: str) -> set[str]:
    tree = parse(expr)
    return {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}


def evaluate(expr: str, variables: Mapping[str, Any], thresholds: Mapping[str, float] | None = None) -> Any:
    tree = parse(expr)
    env = dict(FUNCTIONS)
    env.update({k: (MISSING if v is None else v) for k, v in variables.items()})
    env["t"] = SimpleNamespace(**(thresholds or {}))
    for name in names_in(expr):
        env.setdefault(name, MISSING)
    code = compile(tree, "<rule>", "eval")
    return eval(code, {"__builtins__": {}}, env)  # safe: AST whitelisted above
