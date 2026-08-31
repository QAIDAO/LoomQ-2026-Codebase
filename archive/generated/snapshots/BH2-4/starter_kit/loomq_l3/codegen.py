"""AST → 官方 7 指令 RISC-V 汇编（li add sub addi beq bne j）。

约定：r1..r9 → x1..x9；c[k] → x(10+k)（评测注入）；临时寄存器按表达式
深度从 _TEMPS 取用（嵌套表达式互不冲突），程序结尾统一清零，保证
"全部寄存器终态"与参考解释器一致。只生成前向跳转，总步数 ≤ 指令条数。
"""

from __future__ import annotations

from typing import List, Set

from .classic import Assign, Bin, CBit, Cond, If, Num, RReg

# 深度 d 的表达式可用临时寄存器；嵌套求值逐层取不同的寄存器
_TEMPS = ["x28", "x29", "x27", "x26", "x25", "x24", "x23", "x22",
          "x21", "x20", "x19", "x30", "x31"]


class _Emitter:
    def __init__(self):
        self.lines: List[str] = []
        self.label_seq = 0
        self.used_temps: Set[str] = set()
        self._free: List[str] = list(_TEMPS)

    def emit(self, text: str) -> None:
        self.lines.append(text)

    def reset_pool(self) -> None:
        self._free = list(_TEMPS)

    def alloc_temp(self) -> str:
        """分配临时寄存器；用完必须 free_temp 归还（活性极短）。"""
        if not self._free:
            raise ValueError("临时寄存器耗尽：活跃嵌套超过 %d 层" % len(_TEMPS))
        reg = self._free.pop()
        self.used_temps.add(reg)
        return reg

    def free_temp(self, reg: str) -> None:
        self._free.append(reg)

    def label(self, prefix: str) -> str:
        self.label_seq += 1
        return "%s_%d" % (prefix, self.label_seq)


def _gen_expr(node, dst: str, em: _Emitter) -> None:
    if isinstance(node, Num):
        em.emit("li %s, %d" % (dst, node.value))
        return
    if isinstance(node, RReg):
        em.emit("add %s, x%d, x0" % (dst, node.n))
        return
    if isinstance(node, CBit):
        em.emit("add %s, x%d, x0" % (dst, 10 + node.k))
        return
    if isinstance(node, Bin):
        lhs, rhs = node.lhs, node.rhs
        if node.op == "+":
            if isinstance(rhs, Num):
                _gen_expr(lhs, dst, em)
                em.emit("addi %s, %s, %d" % (dst, dst, rhs.value))
                return
            if isinstance(lhs, Num):
                _gen_expr(rhs, dst, em)
                em.emit("addi %s, %s, %d" % (dst, dst, lhs.value))
                return
            temp = em.alloc_temp()
            _gen_expr(lhs, dst, em)
            _gen_expr(rhs, temp, em)
            em.emit("add %s, %s, %s" % (dst, dst, temp))
            em.free_temp(temp)
            return
        if isinstance(rhs, Num):
            _gen_expr(lhs, dst, em)
            em.emit("addi %s, %s, %d" % (dst, dst, -rhs.value))
            return
        if isinstance(lhs, Num):
            temp = em.alloc_temp()
            _gen_expr(rhs, temp, em)
            em.emit("li %s, %d" % (dst, lhs.value))
            em.emit("sub %s, %s, %s" % (dst, dst, temp))
            em.free_temp(temp)
            return
        temp = em.alloc_temp()
        _gen_expr(lhs, dst, em)
        _gen_expr(rhs, temp, em)
        em.emit("sub %s, %s, %s" % (dst, dst, temp))
        em.free_temp(temp)
        return
    raise TypeError("不支持的表达式节点 %r" % (node,))


def _references(node, reg_num: int) -> bool:
    """表达式是否引用了 r 寄存器 reg_num（目标寄存器冲突检测）。"""
    if isinstance(node, RReg):
        return node.n == reg_num
    if isinstance(node, Bin):
        return _references(node.lhs, reg_num) or _references(node.rhs, reg_num)
    return False


def _gen_stmts(stmts: List[object], em: _Emitter) -> None:
    for stmt in stmts:
        em.reset_pool()
        if isinstance(stmt, Assign):
            dst = "x%d" % stmt.target
            if _references(stmt.expr, stmt.target):
                # 目标寄存器参与表达式：先整体算入临时寄存器再提交，避免自覆盖
                temp = em.alloc_temp()
                _gen_expr(stmt.expr, temp, em)
                em.emit("add %s, %s, x0" % (dst, temp))
                em.free_temp(temp)
            else:
                _gen_expr(stmt.expr, dst, em)
        elif isinstance(stmt, If):
            cond = stmt.cond
            lhs_reg = em.alloc_temp()
            rhs_reg = em.alloc_temp()
            _gen_expr(cond.lhs, lhs_reg, em)
            _gen_expr(cond.rhs, rhs_reg, em)
            then_label = em.label("THEN")
            else_label = em.label("ELSE")
            end_label = em.label("ENDIF")
            branch = "beq" if cond.op == "==" else "bne"
            em.emit("%s %s, %s, %s" % (branch, lhs_reg, rhs_reg, then_label))
            em.free_temp(lhs_reg)
            em.free_temp(rhs_reg)
            em.emit("j %s" % else_label)
            em.emit("%s:" % then_label)
            _gen_stmts(stmt.then_body, em)
            em.emit("j %s" % end_label)
            em.emit("%s:" % else_label)
            _gen_stmts(stmt.else_body, em)
            em.emit("%s:" % end_label)
        else:
            raise TypeError("不支持的语句节点 %r" % (stmt,))


def compile_classical(stmts: List[object]) -> str:
    """语句列表 → 汇编文本（末尾清零所有用过的临时寄存器）。"""
    em = _Emitter()
    em.emit("# loomq l3 classical code")
    _gen_stmts(stmts, em)
    for reg in sorted(em.used_temps, key=lambda r: int(r[1:]), reverse=True):
        em.emit("li %s, 0" % reg)
    return "\n".join(em.lines) + "\n"
