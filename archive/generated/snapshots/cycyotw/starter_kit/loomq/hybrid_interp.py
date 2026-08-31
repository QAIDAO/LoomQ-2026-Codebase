#!/usr/bin/env python3
"""Hybrid-QASM 经典控制块 · 参考解释器（自测用，不参与提交路径）

干什么：不生成任何汇编，直接照着语法树把答案算出来。

为什么要写这么一个"重复"的东西：它是编译器的对照组。
同一段程序，一边编译成汇编丢进官方模拟器跑，一边用它直接算，
两边结果必须一模一样。不一致就说明编译器有 bug——
这正是 `tools/fuzz_l3.py` 用几万个随机程序自动做的事。
"""

try:
    from .hybrid_parser import Assign, Bit, BinOp, Compare, If, Neg, Num, Reg
except ImportError:  # 允许把 starter_kit 直接加进 sys.path 使用
    from hybrid_parser import Assign, Bit, BinOp, Compare, If, Neg, Num, Reg


class MeasurementBitMissing(KeyError):
    """程序读了一个没有被注入测量值的 c[k]。"""


def interpret(statements, bits=None):
    """执行语句列表，返回 r1..r9 的终态。

    statements : list        hybrid_parser.parse() 的结果
    bits       : dict[int,int]  测量位取值，例如 {0: 1, 1: 0}
    返回       : dict[int,int]  键是 1..9，值是对应寄存器的最终值
    """
    registers = {index: 0 for index in range(1, 10)}
    _run(statements, registers, bits or {})
    return registers


def _run(statements, registers, bits):
    for statement in statements:
        if isinstance(statement, Assign):
            registers[statement.target] = _eval(statement.expr, registers, bits)
        elif isinstance(statement, If):
            if _eval_condition(statement.cond, registers, bits):
                _run(statement.then_body, registers, bits)
            elif statement.else_body:
                _run(statement.else_body, registers, bits)
        else:
            raise TypeError("未知的语句类型：%r" % (statement,))


def _eval_condition(cond, registers, bits):
    left = _eval(cond.left, registers, bits)
    right = _eval(cond.right, registers, bits)
    if cond.op == "==":
        return left == right
    if cond.op == "!=":
        return left != right
    raise TypeError("未知的比较运算符：%r" % (cond.op,))


def _eval(node, registers, bits):
    if isinstance(node, Num):
        return node.value
    if isinstance(node, Reg):
        return registers[node.index]
    if isinstance(node, Bit):
        if node.index not in bits:
            raise MeasurementBitMissing("测量位 c[%d] 没有被注入取值" % node.index)
        return bits[node.index]
    if isinstance(node, Neg):
        return -_eval(node.expr, registers, bits)
    if isinstance(node, BinOp):
        left = _eval(node.left, registers, bits)
        right = _eval(node.right, registers, bits)
        if node.op == "+":
            return left + right
        if node.op == "-":
            return left - right
        raise TypeError("未知的运算符：%r" % (node.op,))
    if isinstance(node, Compare):
        return 1 if _eval_condition(node, registers, bits) else 0
    raise TypeError("未知的表达式类型：%r" % (node,))
