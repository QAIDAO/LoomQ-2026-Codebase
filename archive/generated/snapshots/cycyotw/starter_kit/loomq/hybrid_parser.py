#!/usr/bin/env python3
"""Hybrid-QASM 经典控制块 · 语法分析器（编译器第二步）

干什么：把分词器给出的一串"词"，组装成一棵"语法树"——也就是把
"这段话的结构是什么"显式地表示出来。

    r1 = r1 + 5;

变成

    Assign(target=1, expr=BinOp(op='+', left=Reg(index=1), right=Num(value=5)))

为什么要有这一步：文本是平的，但语义是有层次的。`if` 里面套 `if`、
`a + b - c` 谁先算，这些关系只有变成树才说得清楚。有了树，
"翻译成汇编"和"直接算出答案"就都只是遍历这棵树而已。

支持的文法（赛题第三节给定，另加几处只放宽不收紧的容错）：

    program  := stmt*
    stmt     := if_stmt | assign
    assign   := REG '=' expr ';'          # 分号可省略（容错）
    if_stmt  := 'if' '(' cond ')' body [ 'else' (body | if_stmt) ]
    body     := '{' stmt* '}' | stmt      # 单条语句可不加花括号（容错）
    cond     := expr ('==' | '!=') expr | expr      # 裸表达式按"不等于 0"处理（容错）
    expr     := unary (('+' | '-') unary)*
    unary    := ('-' | '+') unary | primary
    primary  := NUM | REG | 'c' '[' NUM ']' | '(' expr ')'

    REG      := r1 .. r9
"""

from collections import namedtuple

try:
    from .hybrid_lexer import HybridSyntaxError, tokenize
except ImportError:  # 允许把 starter_kit 直接加进 sys.path 使用
    from hybrid_lexer import HybridSyntaxError, tokenize


# ---- 语法树节点（用 namedtuple，打印出来自带字段名，便于走查）----
Num = namedtuple("Num", "value")  # 整数字面量，例如 5
Reg = namedtuple("Reg", "index")  # 经典寄存器变量 r1..r9，index 取 1..9
Bit = namedtuple("Bit", "index")  # 测量位 c[k]，index 取 k
BinOp = namedtuple("BinOp", "op left right")  # 二元运算，op 是 '+' 或 '-'
Neg = namedtuple("Neg", "expr")  # 取负，例如 -3
Compare = namedtuple("Compare", "op left right")  # 比较，op 是 '==' 或 '!='
Assign = namedtuple("Assign", "target expr")  # 赋值，target 是 1..9
If = namedtuple("If", "cond then_body else_body")  # else_body 为 None 表示没有 else

MIN_REG = 1
MAX_REG = 9


def parse(text):
    """把经典块的源码文本解析成语句列表。

    text : str        `classical { ... }` 花括号里面的内容
    返回 : list[语句]  Assign / If 的列表
    """
    return _Parser(tokenize(text)).parse_program()


class _Parser:
    """递归下降解析器：每条文法规则对应一个方法，规则套规则就是方法调方法。

    这样写的好处是嵌套的 if/else 天然就支持了——不需要为"套了几层"写任何特判。
    """

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # ---------- 基础工具 ----------

    def peek(self, offset=0):
        index = min(self.pos + offset, len(self.tokens) - 1)
        return self.tokens[index]

    def next(self):
        token = self.peek()
        if token.kind != "eof":
            self.pos += 1
        return token

    def at(self, kind, text=None):
        token = self.peek()
        return token.kind == kind and (text is None or token.text == text)

    def accept(self, kind, text=None):
        if self.at(kind, text):
            return self.next()
        return None

    def expect(self, kind, text=None, what=None):
        token = self.accept(kind, text)
        if token is None:
            found = self.peek()
            shown = repr(found.text) if found.kind != "eof" else "文本结束"
            raise HybridSyntaxError(
                "第 %d 行第 %d 列：这里应该是 %s，实际读到 %s"
                % (found.line, found.col, what or (text or kind), shown)
            )
        return token

    # ---------- 文法规则 ----------

    def parse_program(self):
        statements = []
        while not self.at("eof"):
            statements.append(self.parse_statement())
        return statements

    def parse_statement(self):
        if self.at("name", "if"):
            return self.parse_if()
        return self.parse_assign()

    def parse_if(self):
        self.expect("name", "if")
        self.expect("punct", "(", what="if 后面的左括号 (")
        cond = self.parse_condition()
        self.expect("punct", ")", what="条件后面的右括号 )")
        then_body = self.parse_body()

        else_body = None
        if self.accept("name", "else"):
            # else 后面既可以再接一个 if（形成 else if 链），也可以是普通语句块
            if self.at("name", "if"):
                else_body = [self.parse_if()]
            else:
                else_body = self.parse_body()
        return If(cond, then_body, else_body)

    def parse_body(self):
        """语句块。标准写法是花括号包起来；只有一条语句时允许省略花括号。"""
        if self.accept("punct", "{"):
            statements = []
            while not self.at("punct", "}"):
                if self.at("eof"):
                    token = self.peek()
                    raise HybridSyntaxError("第 %d 行：语句块的花括号 { 没有闭合" % token.line)
                statements.append(self.parse_statement())
            self.expect("punct", "}")
            return statements
        return [self.parse_statement()]

    def parse_assign(self):
        token = self.peek()
        target = self._register_index(token)
        self.next()
        self.expect("op", "=", what="赋值号 =")
        expr = self.parse_expr()
        self.accept("punct", ";")  # 分号可有可无
        return Assign(target, expr)

    def parse_condition(self):
        left = self.parse_expr()
        for op in ("==", "!="):
            if self.accept("op", op):
                return Compare(op, left, self.parse_expr())
        # 没写比较运算符时，按"这个值不等于 0"理解
        return Compare("!=", left, Num(0))

    def parse_expr(self):
        node = self.parse_unary()
        while True:
            token = self.peek()
            if token.kind == "op" and token.text in ("+", "-"):
                self.next()
                node = BinOp(token.text, node, self.parse_unary())
            else:
                return node

    def parse_unary(self):
        token = self.peek()
        if token.kind == "op" and token.text == "-":
            self.next()
            return Neg(self.parse_unary())
        if token.kind == "op" and token.text == "+":
            self.next()
            return self.parse_unary()
        return self.parse_primary()

    def parse_primary(self):
        token = self.peek()

        if token.kind == "num":
            self.next()
            return Num(int(token.text))

        if token.kind == "punct" and token.text == "(":
            self.next()
            node = self.parse_expr()
            self.expect("punct", ")", what="右括号 )")
            return node

        if token.kind == "name":
            # 测量位 c[k]
            if token.text in ("c", "C") and self.peek(1).kind == "punct" and self.peek(1).text == "[":
                self.next()
                self.next()
                index_token = self.expect("num", what="测量位下标（例如 c[0] 里的 0）")
                self.expect("punct", "]", what="右方括号 ]")
                return Bit(int(index_token.text))
            # 经典寄存器 r1..r9
            index = self._register_index(token)
            self.next()
            return Reg(index)

        shown = repr(token.text) if token.kind != "eof" else "文本结束"
        raise HybridSyntaxError(
            "第 %d 行第 %d 列：这里应该是一个数值（整数、r1..r9 或 c[k]），实际读到 %s"
            % (token.line, token.col, shown)
        )

    # ---------- 小工具 ----------

    @staticmethod
    def _register_index(token):
        text = token.text
        if (
            token.kind == "name"
            and len(text) == 2
            and text[0] in ("r", "R")
            and text[1].isdigit()
            and MIN_REG <= int(text[1]) <= MAX_REG
        ):
            return int(text[1])
        shown = repr(text) if token.kind != "eof" else "文本结束"
        raise HybridSyntaxError(
            "第 %d 行第 %d 列：经典寄存器只能是 r1 到 r9，实际读到 %s"
            % (token.line, token.col, shown)
        )


def max_bit_index(statements):
    """扫一遍语法树，返回用到的最大测量位下标；一个都没用到时返回 -1。"""
    highest = -1

    def walk_expr(node):
        nonlocal highest
        if isinstance(node, Bit):
            highest = max(highest, node.index)
        elif isinstance(node, BinOp):
            walk_expr(node.left)
            walk_expr(node.right)
        elif isinstance(node, Compare):
            walk_expr(node.left)
            walk_expr(node.right)
        elif isinstance(node, Neg):
            walk_expr(node.expr)

    def walk_statements(items):
        for item in items:
            if isinstance(item, Assign):
                walk_expr(item.expr)
            elif isinstance(item, If):
                walk_expr(item.cond)
                walk_statements(item.then_body)
                if item.else_body:
                    walk_statements(item.else_body)

    walk_statements(statements)
    return highest
