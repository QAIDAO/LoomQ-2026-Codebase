"""OpenQASM 门参数的安全角度表达式求值。"""

import ast
import math
import operator
import re
from typing import Callable, Dict, Union


Number = Union[int, float]


class ParameterExpressionError(ValueError):
    """参数表达式包含非法语法、运算或结果。"""


_BINARY_OPERATORS: Dict[type, Callable[[Number, Number], Number]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARY_OPERATORS: Dict[type, Callable[[Number], Number]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_DECIMAL_LITERAL_RE = re.compile(
    r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
)


def _validate_number_literals(parsed: ast.AST, source: str) -> None:
    for node in ast.walk(parsed):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            literal = ast.get_source_segment(source, node)
            if literal is None or _DECIMAL_LITERAL_RE.fullmatch(literal) is None:
                raise ParameterExpressionError(
                    "only decimal and scientific notation numbers are allowed"
                )


def _evaluate(node: ast.AST) -> Number:
    # 只递归处理白名单节点；调用、属性、下标和幂运算都会落入拒绝分支。
    if isinstance(node, ast.Constant):
        if type(node.value) not in (int, float):
            raise ParameterExpressionError("only decimal numbers are allowed")
        return node.value
    if isinstance(node, ast.Name):
        if node.id != "pi":
            raise ParameterExpressionError("unknown name %r" % node.id)
        return math.pi
    if isinstance(node, ast.UnaryOp):
        operation = _UNARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise ParameterExpressionError("unsupported unary operator")
        return operation(_evaluate(node.operand))
    if isinstance(node, ast.BinOp):
        operation = _BINARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise ParameterExpressionError("unsupported binary operator")
        return operation(_evaluate(node.left), _evaluate(node.right))
    raise ParameterExpressionError("unsupported expression syntax")


def parse_angle_expression(expression: str) -> float:
    """安全计算一个有限的 OpenQASM 角度表达式。"""
    if not isinstance(expression, str) or not expression.strip():
        raise ParameterExpressionError("parameter expression must not be empty")
    try:
        source = expression.strip()
        parsed = ast.parse(source, mode="eval")
        _validate_number_literals(parsed, source)
        value = float(_evaluate(parsed.body))
    except ParameterExpressionError:
        raise
    except (SyntaxError, ZeroDivisionError, OverflowError, RecursionError) as exc:
        raise ParameterExpressionError("invalid arithmetic expression") from exc
    if not math.isfinite(value):
        raise ParameterExpressionError("parameter result must be finite")
    return value
