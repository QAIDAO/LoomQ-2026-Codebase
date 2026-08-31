#!/usr/bin/env python3
"""OpenQASM 2.0 解析器：文本 -> Circuit

整个 L1 只有这一个解析器。三个后端拿到的都是它的产物，
所以"统一"是在这里发生的，不是在三个后端里各自发生的。

它认识的东西（赛题第三节划死的边界）：

    OPENQASM 2.0;              文件头，跳过
    include "qelib1.inc";      跳过
    qreg q[2];                 声明 2 个量子比特
    creg c[2];                 声明 2 个经典比特
    h q[0];                    施加一个门
    rz(pi/2) q[0];             带参数的门，参数是个算式
    cx q[0], q[1];             多比特门
    measure q[0] -> c[0];      逐位测量
    measure q -> c;            整寄存器测量（等价于逐位写一遍）
    barrier q;                 忽略（不影响任何测量分布）

参数为什么在这里就算成数字：源码里写的是 `pi/2` 这种算式，
而三个后端的写法各不相同。与其让三个后端各自去理解算式，
不如在解析阶段一次性算成 1.5707963267948966，后面谁都不用再操心。
"""

import math
import re

try:
    from .circuit import Circuit, Gate, Measure
    from .gates import IGNORED_STATEMENTS, check
except ImportError:  # 允许把 starter_kit 直接加进 sys.path 使用
    from circuit import Circuit, Gate, Measure
    from gates import IGNORED_STATEMENTS, check


class QasmSyntaxError(ValueError):
    """QASM 源码有问题。消息尽量说清是哪一句、缺了什么。"""


_REGISTER_PATTERN = re.compile(r"^(qreg|creg)\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]$")
_INDEXED_PATTERN = re.compile(r"^([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]$")
_NAME_PATTERN = re.compile(r"^[A-Za-z_]\w*$")
_FUNCTIONS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "exp": math.exp,
    "ln": math.log,
    "sqrt": math.sqrt,
}


def parse(qasm_str):
    """把 OpenQASM 2.0 文本解析成 Circuit。"""
    if not isinstance(qasm_str, str):
        raise TypeError("parse 需要一个字符串，实际收到 %r" % type(qasm_str))

    circuit = Circuit()
    qregs = {}  # 名字 -> (起始下标, 长度)
    cregs = {}

    for statement in _split_statements(qasm_str):
        head = statement.split("(")[0].split()[0].lower()

        if head in ("openqasm", "include"):
            continue
        if head in IGNORED_STATEMENTS:
            continue
        if head == "gate":
            raise QasmSyntaxError("暂不支持自定义门声明（gate ...）：%r" % statement)
        if head == "if":
            raise QasmSyntaxError(
                "暂不支持 QASM 内联条件（if (...) ...）：%r。"
                "经典控制请用 L3 的 classical 块。" % statement
            )

        match = _REGISTER_PATTERN.match(statement)
        if match:
            kind, name, size = match.group(1), match.group(2), int(match.group(3))
            if size <= 0:
                raise QasmSyntaxError("寄存器 %s 的长度必须大于 0" % name)
            if kind == "qreg":
                qregs[name] = (circuit.num_qubits, size)
                circuit.num_qubits += size
            else:
                cregs[name] = (circuit.num_clbits, size)
                circuit.num_clbits += size
            continue

        if head == "measure":
            _parse_measure(statement, circuit, qregs, cregs)
            continue

        _parse_gate(statement, circuit, qregs)

    return circuit


# --------------------------------------------------------------------------
# 拆语句
# --------------------------------------------------------------------------


def _split_statements(text):
    """去掉注释，按分号切成一条条语句，丢掉空句。"""
    cleaned = _strip_comments(text)
    return [" ".join(chunk.split()) for chunk in cleaned.split(";") if chunk.strip()]


def _strip_comments(text):
    output = []
    index = 0
    length = len(text)
    while index < length:
        if text.startswith("//", index):
            newline = text.find("\n", index)
            if newline < 0:
                break
            index = newline
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            index = length if end < 0 else end + 2
            continue
        if text[index] == '"':
            end = text.find('"', index + 1)
            if end < 0:
                break
            output.append(text[index : end + 1])
            index = end + 1
            continue
        output.append(text[index])
        index += 1
    return "".join(output)


# --------------------------------------------------------------------------
# 测量
# --------------------------------------------------------------------------


def _parse_measure(statement, circuit, qregs, cregs):
    body = statement[len("measure") :]
    if "->" not in body:
        raise QasmSyntaxError("测量语句缺少箭头 -> ：%r" % statement)
    left, right = body.split("->", 1)
    qubits = _resolve(left.strip(), qregs, "量子", statement)
    clbits = _resolve(right.strip(), cregs, "经典", statement)
    if len(qubits) != len(clbits):
        raise QasmSyntaxError(
            "测量两边长度不一致（%d 个量子比特 vs %d 个经典比特）：%r"
            % (len(qubits), len(clbits), statement)
        )
    for qubit, clbit in zip(qubits, clbits):
        circuit.add(Measure(qubit, clbit))


# --------------------------------------------------------------------------
# 门
# --------------------------------------------------------------------------


def _parse_gate(statement, circuit, qregs):
    name, params_text, args_text = _split_gate(statement)
    params = tuple(_eval_expression(chunk, statement) for chunk in _split_commas(params_text))

    operands = [_resolve(chunk, qregs, "量子", statement) for chunk in _split_commas(args_text)]
    if not operands:
        raise QasmSyntaxError("门 %s 没有作用对象：%r" % (name, statement))

    # 允许整寄存器写法（h q; 等价于对 q 里每个比特各来一次）。
    # 多个操作数时要求长度一致，逐位对应。
    width = max(len(item) for item in operands)
    for item in operands:
        if len(item) not in (1, width):
            raise QasmSyntaxError(
                "门 %s 的各个作用对象长度对不上（%s）：%r"
                % (name, [len(x) for x in operands], statement)
            )

    for slot in range(width):
        qubits = [item[slot if len(item) > 1 else 0] for item in operands]
        check(name, params, qubits)
        circuit.add(Gate(name, params, tuple(qubits)))


def _split_gate(statement):
    """把 `rz(pi/2) q[0], q[1]` 拆成 ('rz', 'pi/2', 'q[0], q[1]')。"""
    open_paren = statement.find("(")
    if open_paren < 0:
        parts = statement.split(None, 1)
        if len(parts) != 2:
            raise QasmSyntaxError("看不懂的语句：%r" % statement)
        return parts[0].lower(), "", parts[1]

    depth = 0
    for index in range(open_paren, len(statement)):
        if statement[index] == "(":
            depth += 1
        elif statement[index] == ")":
            depth -= 1
            if depth == 0:
                name = statement[:open_paren].strip().lower()
                params = statement[open_paren + 1 : index]
                args = statement[index + 1 :].strip()
                if not name:
                    raise QasmSyntaxError("门名为空：%r" % statement)
                if not args:
                    raise QasmSyntaxError("门 %s 没有作用对象：%r" % (name, statement))
                return name, params, args
    raise QasmSyntaxError("括号没有闭合：%r" % statement)


def _split_commas(text):
    """按顶层逗号切分，括号里的逗号不算。"""
    if not text.strip():
        return []
    chunks = []
    depth = 0
    current = []
    for char in text:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        if char == "," and depth == 0:
            chunks.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    chunks.append("".join(current).strip())
    return [chunk for chunk in chunks if chunk]


def _resolve(text, registers, kind, statement):
    """把 `q[0]` 解析成 [全局下标]，把 `q` 解析成整个寄存器的下标列表。"""
    match = _INDEXED_PATTERN.match(text)
    if match:
        name, index = match.group(1), int(match.group(2))
        if name not in registers:
            raise QasmSyntaxError("未声明的%s寄存器 %r：%r" % (kind, name, statement))
        base, size = registers[name]
        if not 0 <= index < size:
            raise QasmSyntaxError(
                "%s[%d] 越界，%s 只有 %d 位：%r" % (name, index, name, size, statement)
            )
        return [base + index]

    if _NAME_PATTERN.match(text):
        if text not in registers:
            raise QasmSyntaxError("未声明的%s寄存器 %r：%r" % (kind, text, statement))
        base, size = registers[text]
        return [base + offset for offset in range(size)]

    raise QasmSyntaxError("看不懂的%s比特写法 %r：%r" % (kind, text, statement))


# --------------------------------------------------------------------------
# 参数算式：pi/2、-pi/4、2*pi/8 这种
# --------------------------------------------------------------------------


def _eval_expression(text, statement):
    tokens = _tokenize_expression(text, statement)
    parser = _ExpressionParser(tokens, statement)
    value = parser.parse_expr()
    parser.expect_end()
    return value


def _tokenize_expression(text, statement):
    tokens = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char.isdigit() or char == ".":
            match = re.match(r"\d*\.?\d+([eE][+-]?\d+)?", text[index:])
            if not match:
                raise QasmSyntaxError("看不懂的数字：%r（在 %r 中）" % (text[index:], statement))
            tokens.append(("num", float(match.group(0))))
            index += match.end()
            continue
        if char.isalpha() or char == "_":
            match = re.match(r"[A-Za-z_]\w*", text[index:])
            tokens.append(("name", match.group(0)))
            index += match.end()
            continue
        if char in "+-*/^()":
            tokens.append(("op", char))
            index += 1
            continue
        raise QasmSyntaxError("参数里出现无法识别的字符 %r：%r" % (char, statement))
    tokens.append(("end", None))
    return tokens


class _ExpressionParser:
    """和 L3 用的是同一种写法（递归下降），一条文法规则一个方法。"""

    def __init__(self, tokens, statement):
        self.tokens = tokens
        self.pos = 0
        self.statement = statement

    def peek(self):
        return self.tokens[self.pos]

    def next(self):
        token = self.tokens[self.pos]
        if token[0] != "end":
            self.pos += 1
        return token

    def accept_op(self, *symbols):
        kind, value = self.peek()
        if kind == "op" and value in symbols:
            self.next()
            return value
        return None

    def expect_end(self):
        if self.peek()[0] != "end":
            raise QasmSyntaxError("参数算式没读完，剩下 %r：%r" % (self.peek()[1], self.statement))

    def parse_expr(self):
        value = self.parse_term()
        while True:
            operator = self.accept_op("+", "-")
            if operator is None:
                return value
            right = self.parse_term()
            value = value + right if operator == "+" else value - right

    def parse_term(self):
        value = self.parse_power()
        while True:
            operator = self.accept_op("*", "/")
            if operator is None:
                return value
            right = self.parse_power()
            if operator == "/" and right == 0:
                raise QasmSyntaxError("参数算式里出现除以 0：%r" % self.statement)
            value = value * right if operator == "*" else value / right

    def parse_power(self):
        base = self.parse_unary()
        if self.accept_op("^"):
            return base ** self.parse_power()  # 右结合
        return base

    def parse_unary(self):
        operator = self.accept_op("-", "+")
        if operator == "-":
            return -self.parse_unary()
        if operator == "+":
            return self.parse_unary()
        return self.parse_primary()

    def parse_primary(self):
        kind, value = self.next()

        if kind == "num":
            return value

        if kind == "op" and value == "(":
            inner = self.parse_expr()
            if self.accept_op(")") is None:
                raise QasmSyntaxError("参数算式缺右括号：%r" % self.statement)
            return inner

        if kind == "name":
            lowered = value.lower()
            if lowered == "pi":
                return math.pi
            if lowered in _FUNCTIONS:
                if self.accept_op("(") is None:
                    raise QasmSyntaxError("函数 %s 后面缺左括号：%r" % (value, self.statement))
                inner = self.parse_expr()
                if self.accept_op(")") is None:
                    raise QasmSyntaxError("函数 %s 缺右括号：%r" % (value, self.statement))
                return _FUNCTIONS[lowered](inner)
            raise QasmSyntaxError("参数里不认识的名字 %r：%r" % (value, self.statement))

        raise QasmSyntaxError("参数算式不完整：%r" % self.statement)
