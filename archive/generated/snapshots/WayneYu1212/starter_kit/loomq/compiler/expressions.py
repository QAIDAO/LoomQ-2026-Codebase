"""Safe arithmetic for the angle expressions allowed by LoomQ."""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Callable


_BINARY_OPERATORS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_MAX_AST_NODES = 64
_MAX_POWER = 32.0


def _finite(value: float) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("parameter expression must be finite")
    return result


def _evaluate(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("parameter expression contains a non-numeric literal")
        return _finite(node.value)

    if isinstance(node, ast.Name):
        if node.id != "pi":
            raise ValueError("parameter expression may only name pi")
        return math.pi

    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _finite(_UNARY_OPERATORS[type(node.op)](_evaluate(node.operand)))

    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        if isinstance(node.op, ast.Pow):
            if abs(right) > _MAX_POWER:
                raise ValueError("parameter exponent is too large")
            try:
                return _finite(left**right)
            except (OverflowError, ValueError) as exc:
                raise ValueError("invalid parameter exponentiation") from exc
        function = _BINARY_OPERATORS.get(type(node.op))
        if function is not None:
            try:
                return _finite(function(left, right))
            except (OverflowError, ZeroDivisionError) as exc:
                raise ValueError("invalid parameter arithmetic") from exc

    raise ValueError("unsupported parameter expression")


def parse_parameter(expression: str) -> float:
    """Evaluate a QASM angle expression without executing arbitrary Python."""

    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("parameter expression must be a non-empty string")
    normalized = expression.strip().replace("^", "**")
    try:
        parsed = ast.parse(normalized, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise ValueError("invalid parameter expression syntax") from exc
    if sum(1 for _ in ast.walk(parsed)) > _MAX_AST_NODES:
        raise ValueError("parameter expression is too complex")
    return _evaluate(parsed.body)
