"""Safe angle-expression evaluation shared by supported circuit parsers."""

import ast
import math


def evaluate_angle(expression: str) -> float:
    """Evaluate the arithmetic subset accepted for rotation angles."""
    try:
        node = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        raise ValueError(f"Invalid gate parameter: {expression}") from error

    def evaluate(item: ast.AST) -> float:
        if isinstance(item, ast.Expression):
            return evaluate(item.body)
        if isinstance(item, ast.Constant) and isinstance(item.value, (int, float)):
            return float(item.value)
        if isinstance(item, ast.Name) and item.id.lower() == "pi":
            return math.pi
        if isinstance(item, ast.UnaryOp) and isinstance(item.op, (ast.UAdd, ast.USub)):
            value = evaluate(item.operand)
            return value if isinstance(item.op, ast.UAdd) else -value
        if isinstance(item, ast.BinOp) and isinstance(
            item.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
        ):
            left, right = evaluate(item.left), evaluate(item.right)
            if isinstance(item.op, ast.Add):
                return left + right
            if isinstance(item.op, ast.Sub):
                return left - right
            if isinstance(item.op, ast.Mult):
                return left * right
            return left / right
        raise ValueError(f"Unsupported gate parameter: {expression}")

    value = evaluate(node)
    if not math.isfinite(value):
        raise ValueError("Gate parameters must be finite")
    return value
