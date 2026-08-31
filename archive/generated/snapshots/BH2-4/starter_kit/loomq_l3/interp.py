"""classical AST 参考解释器：与官方 TinyRISCVEmulator 语义对齐。

对齐点：寄存器初值 0；无位宽回绕（Python 大整数）；x0 恒 0（r0 不存在）。
"""

from __future__ import annotations

from typing import Dict, List

from .classic import Assign, Bin, CBit, Cond, If, Num, RReg


def eval_expr(node, cvals: Dict[int, int], regs: List[int]) -> int:
    if isinstance(node, Num):
        return node.value
    if isinstance(node, RReg):
        return regs[node.n]
    if isinstance(node, CBit):
        return cvals.get(node.k, 0)
    if isinstance(node, Bin):
        lhs = eval_expr(node.lhs, cvals, regs)
        rhs = eval_expr(node.rhs, cvals, regs)
        return lhs + rhs if node.op == "+" else lhs - rhs
    raise TypeError("不支持的表达式节点 %r" % (node,))


def run_program(stmts: List[object], cvals: Dict[int, int]) -> List[int]:
    """执行语句列表，返回 r1..r9 终值列表（下标 0 对应 r1）。"""
    regs = [0] * 10  # regs[1..9]
    _exec(stmts, cvals, regs)
    return regs[1:]


def _exec(stmts: List[object], cvals: Dict[int, int], regs: List[int]) -> None:
    for stmt in stmts:
        if isinstance(stmt, Assign):
            regs[stmt.target] = eval_expr(stmt.expr, cvals, regs)
        elif isinstance(stmt, If):
            cond = stmt.cond
            lhs = eval_expr(cond.lhs, cvals, regs)
            rhs = eval_expr(cond.rhs, cvals, regs)
            taken = (lhs == rhs) if cond.op == "==" else (lhs != rhs)
            if taken:
                _exec(stmt.then_body, cvals, regs)
            else:
                _exec(stmt.else_body, cvals, regs)
        else:
            raise TypeError("不支持的语句节点 %r" % (stmt,))
