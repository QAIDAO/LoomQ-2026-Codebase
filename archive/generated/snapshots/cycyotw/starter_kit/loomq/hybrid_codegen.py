#!/usr/bin/env python3
"""Hybrid-QASM 经典控制块 · 代码生成器（编译器第三步）

干什么：把语法树翻译成 RISC-V 汇编文本，能直接丢进官方
`riscv_emulator.py` 执行。

官方模拟器只给了 7 条指令，整个翻译就是在这 7 条里凑：

    li   rd, imm          把一个常数装进寄存器
    add  rd, rs1, rs2     两个寄存器相加
    sub  rd, rs1, rs2     两个寄存器相减
    addi rd, rs1, imm     寄存器加一个常数
    beq  rs1, rs2, 标签    相等就跳
    bne  rs1, rs2, 标签    不等就跳
    j    标签              无条件跳

寄存器怎么分（赛题规定 + 我们自己的约定）：

    r1..r9   -> x1..x9      赛题规定：经典变量
    c[k]     -> x10, x11..  赛题规定：测量结果由评测系统注入
    临时值    -> x20 往上     我们自己的约定，见下方 TEMP_FLOOR

★ 两个容易踩的坑：

1. `beq / bne` 只能比较两个寄存器，不能拿寄存器跟常数比。
   所以 `if (c[0] == 1)` 必须先把常数 1 装进一个临时寄存器再比。

2. 临时寄存器必须避开 x10 起的测量位，否则会把评测系统注入的测量结果覆盖掉。
   我们从 x20 起用（并且会随测量位数量往上让），算完还会把用过的临时寄存器清零，
   保证最终寄存器状态里只剩 r1..r9 和测量位，不留垃圾。

if / else 翻译成什么样：

    if (条件) { A } else { B }

    ->   <算出条件两边的值>
         b<条件的反面>  左, 右, L_ELSE_1     # 条件不成立就跳去 else
         <A 的指令>
         j L_END_1
         L_ELSE_1:
         <B 的指令>
         L_END_1:
"""

try:
    from .hybrid_parser import Assign, Bit, BinOp, Compare, If, Neg, Num, Reg
except ImportError:  # 允许把 starter_kit 直接加进 sys.path 使用
    from hybrid_parser import Assign, Bit, BinOp, Compare, If, Neg, Num, Reg


ZERO = "x0"  # RISC-V 的 x0 恒为 0，读它总是拿到 0，写它无效
MEASURE_BASE = 10  # 赛题规定：c[0] 注入 x10，c[1] 注入 x11，依此类推
TEMP_FLOOR = 20  # 临时寄存器最低从 x20 开始，给测量位留足空间
LAST_REGISTER = 31  # 官方模拟器只有 x0..x31


class RegisterPressureError(RuntimeError):
    """表达式嵌套太深，32 个寄存器不够用了。正常用例不会触发。"""


def generate(statements, measure_bits=0):
    """把语句列表翻译成汇编文本。

    statements   : list  hybrid_parser.parse() 的结果
    measure_bits : int   这段程序里测量位的数量（决定临时寄存器从哪里开始）
    返回         : str   RISC-V 汇编文本
    """
    return _CodeGenerator(measure_bits).generate(statements)


class _CodeGenerator:
    def __init__(self, measure_bits=0):
        # 临时寄存器起点：既不低于 x20，也要躲开所有测量位
        self.temp_base = max(TEMP_FLOOR, MEASURE_BASE + max(0, measure_bits))
        self.next_temp = self.temp_base
        self.high_water = self.temp_base  # 历史上用到过的最大临时寄存器编号 + 1
        self.label_counter = 0
        self.lines = []

    # ---------- 汇编输出 ----------

    def emit(self, instruction, comment=None):
        if comment:
            self.lines.append("    %-24s # %s" % (instruction, comment))
        else:
            self.lines.append("    %s" % instruction)

    def emit_label(self, name):
        self.lines.append("%s:" % name)

    def emit_comment(self, text):
        self.lines.append("# %s" % text)

    def new_labels(self):
        self.label_counter += 1
        return "L_ELSE_%d" % self.label_counter, "L_END_%d" % self.label_counter

    # ---------- 临时寄存器：一个极简的栈式分配器 ----------

    def mark(self):
        return self.next_temp

    def release(self, mark):
        self.next_temp = mark

    def alloc(self):
        index = self.next_temp
        if index > LAST_REGISTER:
            raise RegisterPressureError(
                "表达式嵌套过深，临时寄存器已超出 x%d" % LAST_REGISTER
            )
        self.next_temp += 1
        self.high_water = max(self.high_water, self.next_temp)
        return "x%d" % index

    # ---------- 主流程 ----------

    def generate(self, statements):
        self.emit_comment("=" * 60)
        self.emit_comment("LoomQ L3 · 由 Hybrid-QASM 经典控制块自动编译生成")
        self.emit_comment(
            "寄存器约定：r1..r9 -> x1..x9   c[k] -> x%d+k   临时寄存器 -> x%d 起"
            % (MEASURE_BASE, self.temp_base)
        )
        self.emit_comment("=" * 60)

        body_start = len(self.lines)
        for order, statement in enumerate(statements, start=1):
            self.emit_comment("--- 第 %d 条语句 ---" % order)
            self.gen_statement(statement)

        self.emit_cleanup()

        if len(self.lines) == body_start:
            # 空的经典块也要给出一条真指令，保证产物是可执行的合法程序
            self.emit("add x0, x0, x0", "空操作（经典块里没有语句）")

        return "\n".join(self.lines) + "\n"

    def emit_cleanup(self):
        """把用过的临时寄存器清零。

        为什么必须做：官方模拟器的 execute() 会返回"所有非零寄存器"。
        临时寄存器里的中间结果如果留着，就会混进最终状态里，
        和参考解释器的结果对不上。
        """
        if self.high_water <= self.temp_base:
            return
        self.emit_comment("--- 清理临时寄存器，只留下 r1..r9 与测量位 ---")
        for index in range(self.temp_base, self.high_water):
            self.emit("li x%d, 0" % index)

    # ---------- 语句 ----------

    def gen_statement(self, node):
        if isinstance(node, Assign):
            self.gen_assign(node)
        elif isinstance(node, If):
            self.gen_if(node)
        else:
            raise TypeError("未知的语句类型：%r" % (node,))

    def gen_assign(self, node):
        target = "x%d" % node.target
        mark = self.mark()
        if isinstance(node.expr, Num):
            # 直接赋常数，一条指令就够
            self.emit("li %s, %d" % (target, node.expr.value), "r%d = %d" % (node.target, node.expr.value))
        else:
            source = self.gen_expr(node.expr)
            self.emit("add %s, %s, %s" % (target, source, ZERO), "r%d = 上面算出来的值" % node.target)
        self.release(mark)

    def gen_if(self, node):
        else_label, end_label = self.new_labels()
        has_else = bool(node.else_body)

        # 条件不成立就跳走：没有 else 时直接跳到结尾
        self.gen_branch_if_false(node.cond, else_label if has_else else end_label)

        for statement in node.then_body:
            self.gen_statement(statement)

        if has_else:
            self.emit("j %s" % end_label, "then 分支执行完，跳过 else")
            self.emit_label(else_label)
            for statement in node.else_body:
                self.gen_statement(statement)

        self.emit_label(end_label)

    def gen_branch_if_false(self, cond, target_label):
        """条件为假时跳到 target_label。

        注意这里用的是"反面指令"：`==` 用 bne 跳走，`!=` 用 beq 跳走。
        因为汇编里的分支表达的是"什么时候绕开这段代码"。
        """
        mark = self.mark()
        left = self.gen_expr(cond.left)
        right = self.gen_expr(cond.right)
        if cond.op == "==":
            self.emit("bne %s, %s, %s" % (left, right, target_label), "两边不相等就跳走")
        elif cond.op == "!=":
            self.emit("beq %s, %s, %s" % (left, right, target_label), "两边相等就跳走")
        else:
            raise TypeError("未知的比较运算符：%r" % (cond.op,))
        self.release(mark)

    # ---------- 表达式 ----------

    def gen_expr(self, node):
        """算出一个表达式的值，返回存放结果的寄存器名。

        约定：这个函数绝不写 x1..x9（那是用户变量），中间结果一律放临时寄存器。
        """
        if isinstance(node, Num):
            temp = self.alloc()
            self.emit("li %s, %d" % (temp, node.value), "常数 %d" % node.value)
            return temp

        if isinstance(node, Reg):
            return "x%d" % node.index  # 变量本来就在寄存器里，不用搬

        if isinstance(node, Bit):
            return "x%d" % (MEASURE_BASE + node.index)  # 测量位由评测系统注入

        if isinstance(node, Neg):
            mark = self.mark()
            value = self.gen_expr(node.expr)
            self.release(mark)
            temp = self.alloc()
            self.emit("sub %s, %s, %s" % (temp, ZERO, value), "取负")
            return temp

        if isinstance(node, BinOp):
            return self.gen_binop(node)

        raise TypeError("未知的表达式类型：%r" % (node,))

    def gen_binop(self, node):
        mark = self.mark()

        # 右边是常数时，用 addi 一条指令搞定，省掉"先把常数装进寄存器"
        if isinstance(node.right, Num):
            left = self.gen_expr(node.left)
            self.release(mark)
            temp = self.alloc()
            delta = node.right.value if node.op == "+" else -node.right.value
            self.emit("addi %s, %s, %d" % (temp, left, delta), "%s %d" % (node.op, node.right.value))
            return temp

        left = self.gen_expr(node.left)
        right = self.gen_expr(node.right)
        self.release(mark)
        temp = self.alloc()
        # 先释放再分配，temp 可能正好复用 left 的位置。
        # 这没问题：模拟器执行一条指令时先读两个源寄存器再写目标寄存器。
        opcode = "add" if node.op == "+" else "sub"
        self.emit("%s %s, %s, %s" % (opcode, temp, left, right), "两个值相%s" % ("加" if node.op == "+" else "减"))
        return temp
