"""面向 LoomQ 12 门白名单的最小化 OpenQASM 2.0 解析器。

不是通用的 QASM 前端：它只接受比赛保证会出现的子集（problem_statement.md
第三节）—— qreg/creg 声明、12 个白名单门、以及 measure 语句——其余一律
直接抛 ValueError，不做任何静默猜测。
"""

import math
import re
from typing import Dict, Iterator, List, Tuple

from .ir import Circuit, GateOp, MeasureOp, WHITELIST_GATES


class _ExprParser:
    """递归下降求值器，处理 '-pi/2' 这类角度表达式。"""

    def __init__(self, text: str):
        self.tokens = self._tokenize(text)
        self.pos = 0

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        tokens: List[str] = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch.isspace():
                i += 1
                continue
            m = re.match(r"\d+\.\d+(?:[eE][+-]?\d+)?|\d+\.?\d*(?:[eE][+-]?\d+)?", text[i:])
            if m and m.group(0):
                tokens.append(m.group(0))
                i += len(m.group(0))
                continue
            m = re.match(r"[A-Za-z_]\w*", text[i:])
            if m:
                tokens.append(m.group(0))
                i += len(m.group(0))
                continue
            if ch in "+-*/()":
                tokens.append(ch)
                i += 1
                continue
            raise ValueError(f"unexpected character in expression: {ch!r}")
        return tokens

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _advance(self):
        tok = self._peek()
        self.pos += 1
        return tok

    def parse(self) -> float:
        value = self._expr()
        if self.pos != len(self.tokens):
            raise ValueError(f"trailing tokens in expression: {self.tokens[self.pos:]}")
        return value

    def _expr(self) -> float:
        value = self._term()
        while self._peek() in ("+", "-"):
            op = self._advance()
            rhs = self._term()
            value = value + rhs if op == "+" else value - rhs
        return value

    def _term(self) -> float:
        value = self._unary()
        while self._peek() in ("*", "/"):
            op = self._advance()
            rhs = self._unary()
            value = value * rhs if op == "*" else value / rhs
        return value

    def _unary(self) -> float:
        if self._peek() == "-":
            self._advance()
            return -self._unary()
        if self._peek() == "+":
            self._advance()
            return self._unary()
        return self._atom()

    def _atom(self) -> float:
        tok = self._advance()
        if tok is None:
            raise ValueError("unexpected end of expression")
        if tok == "(":
            value = self._expr()
            if self._advance() != ")":
                raise ValueError("mismatched parentheses in expression")
            return value
        if tok.lower() == "pi":
            return math.pi
        try:
            return float(tok)
        except ValueError:
            raise ValueError(f"unknown identifier in expression: {tok!r}")


def eval_expr(text: str) -> float:
    return _ExprParser(text).parse()


_STATEMENT_RE = re.compile(
    r"^(?P<name>[A-Za-z_]\w*)\s*(?:\((?P<params>[^)]*)\))?\s*(?P<args>[^;]*)$"
)
_ARG_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*(?:\[\s*(\d+)\s*\])?\s*$")


def _iter_statements(source: str) -> Iterator[str]:
    """每次吐出一条以 `;` 结尾的语句，注释和首尾空白已经处理干净。

    对 `source` 做一次从左到右的单趟扫描，全程只维护"当前是否在
    // 注释里"这一个状态，以及正在攒的这一条语句的字符缓冲区——不会
    为整个源码生成一份去掉注释的完整拷贝，也不会一次性建好全部语句的
    列表，所以额外占用的内存只跟"最长的单条语句"成正比，跟输入总长度
    无关。`in_comment` 这个标记必须在"找 `;`"之前就跟踪好，而不是先按
    `;` 切完再处理注释：如果注释里恰好包含一个字面的 `;`（比如
    `h q[0]; // note: uses a CX; not a CCX` `\n x q[1];`），后者会把它
    误判成多出来的一个语句边界。
    """
    buf: List[str] = []
    in_comment = False
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if in_comment:
            if ch == "\n":
                in_comment = False
            i += 1
            continue
        if ch == "/" and source[i + 1 : i + 2] == "/":
            in_comment = True
            i += 2
            continue
        if ch == ";":
            stmt = "".join(buf).strip()
            buf.clear()
            if stmt:
                yield stmt
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        yield tail


def _parse_args(args_text: str, registers: Dict[str, Tuple[int, int]]) -> List[List[int]]:
    """把逗号分隔的参数字符串，解析成每个参数各自对应的全局下标列表。
    裸寄存器（不带 `[i]`）会展开成它声明的全部下标——用于
    `measure q -> c;` 这类整寄存器语句。"""
    args: List[List[int]] = []
    for raw in args_text.split(","):
        raw = raw.strip()
        if not raw:
            continue
        m = _ARG_RE.match(raw)
        if not m:
            raise ValueError(f"cannot parse register argument: {raw!r}")
        reg, idx = m.group(1), m.group(2)
        if reg not in registers:
            raise ValueError(f"undeclared register: {reg!r}")
        offset, size = registers[reg]
        if idx is None:
            args.append([offset + i for i in range(size)])
        else:
            i = int(idx)
            if not (0 <= i < size):
                raise ValueError(f"register index out of range: {reg}[{i}]")
            args.append([offset + i])
    return args


def parse_qasm2(source: str) -> Circuit:
    qregs: Dict[str, Tuple[int, int]] = {}
    cregs: Dict[str, Tuple[int, int]] = {}
    n_qubits = 0
    n_clbits = 0
    ops: List = []
    header_seen = False

    for stmt in _iter_statements(source):
        if stmt.upper().startswith("OPENQASM"):
            header_seen = True
            continue
        if stmt.startswith("include"):
            continue
        if stmt.startswith("barrier"):
            continue
        if stmt.startswith("qreg"):
            m = re.match(r"qreg\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]", stmt)
            if not m:
                raise ValueError(f"malformed qreg declaration: {stmt!r}")
            name, size = m.group(1), int(m.group(2))
            qregs[name] = (n_qubits, size)
            n_qubits += size
            continue
        if stmt.startswith("creg"):
            m = re.match(r"creg\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]", stmt)
            if not m:
                raise ValueError(f"malformed creg declaration: {stmt!r}")
            name, size = m.group(1), int(m.group(2))
            cregs[name] = (n_clbits, size)
            n_clbits += size
            continue
        if stmt.startswith("measure"):
            m = re.match(r"measure\s+(.+?)\s*->\s*(.+)$", stmt)
            if not m:
                raise ValueError(f"malformed measure statement: {stmt!r}")
            q_args = _parse_args(m.group(1), qregs)
            c_args = _parse_args(m.group(2), cregs)
            if len(q_args) != 1 or len(c_args) != 1:
                raise ValueError(f"measure expects one qubit arg and one clbit arg: {stmt!r}")
            qubits, clbits = q_args[0], c_args[0]
            if len(qubits) != len(clbits):
                raise ValueError(f"measure register size mismatch: {stmt!r}")
            for q, c in zip(qubits, clbits):
                ops.append(MeasureOp(qubit=q, clbit=c))
            continue

        m = _STATEMENT_RE.match(stmt)
        if not m:
            raise ValueError(f"unrecognized statement: {stmt!r}")
        name = m.group("name").lower()
        if name not in WHITELIST_GATES:
            raise ValueError(
                f"gate '{name}' is outside the LoomQ 12-gate whitelist: {stmt!r}"
            )
        params = tuple(
            eval_expr(p) for p in (m.group("params") or "").split(",") if p.strip()
        )
        arg_groups = _parse_args(m.group("args"), qregs)
        if not arg_groups:
            raise ValueError(f"gate statement has no qubit arguments: {stmt!r}")
        width = max(len(g) for g in arg_groups)
        for i in range(width):
            qubits = tuple(g[i] if len(g) > 1 else g[0] for g in arg_groups)
            ops.append(GateOp(name=name, qubits=qubits, params=params))

    if not header_seen:
        raise ValueError("missing 'OPENQASM 2.0;' header")
    if n_qubits == 0:
        raise ValueError("no qreg declared")

    return Circuit(n_qubits=n_qubits, n_clbits=n_clbits, ops=ops)
