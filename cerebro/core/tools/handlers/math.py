"""Deterministic numeric evaluator — stdlib-only, no Python eval()."""

from __future__ import annotations

import ast
import operator as op
from typing import Final

_ALLOWED_OPS: Final = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.FloorDiv: op.floordiv,
    ast.Mod: op.mod,
    ast.Pow: op.pow,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        left, right = _eval(node.left), _eval(node.right)
        return float(_ALLOWED_OPS[type(node.op)](left, right))  # type: ignore[operator]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return float(_ALLOWED_OPS[type(node.op)](_eval(node.operand)))  # type: ignore[operator]
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def _format_numeric(value: float) -> str:
    rounded = round(value, 10)
    if rounded.is_integer():
        return str(int(rounded))
    text = f"{rounded:.10f}".rstrip("0").rstrip(".")
    return text or "0"


def evaluate_math(expression: str) -> str:
    """Evaluate a pure-numeric expression and return the result as a string.

    Allowed: +, -, *, /, //, %, **, unary +/-, parentheses. Refuses anything
    else (variables, calls, attribute access, comparisons).
    """
    try:
        tree = ast.parse(expression, mode="eval")
        value = _eval(tree)
    except SyntaxError as exc:
        return f"Error: {exc}"
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        return f"Error: {exc}"
    return _format_numeric(value)
