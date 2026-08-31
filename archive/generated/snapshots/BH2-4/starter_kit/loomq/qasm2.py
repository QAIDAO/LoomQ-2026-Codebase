"""OpenQASM 2.0 子集解析器：文本 → Circuit IR。

支持：qreg/creg（含 qubit[n] q; / bit[n] c; 变体）、整寄存器与逐位 measure、
barrier（忽略）、自定义 gate 定义与递归展开、qelib1 常用内置门、
内置门整寄存器广播（如 `x q;`）、参数表达式（数字、pi、+ - * /、括号）。
if 条件门 / reset 不在 L1 评测电路范围，遇到即显式报错。
"""

from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Tuple

from .ir import Circuit, Op

# name -> (参数个数, 量子比特个数)
BUILTIN_GATES: Dict[str, Tuple[int, int]] = {
    "h": (0, 1), "x": (0, 1), "y": (0, 1), "z": (0, 1),
    "s": (0, 1), "sdg": (0, 1), "t": (0, 1), "tdg": (0, 1),
    "id": (0, 1), "sx": (0, 1),
    "rx": (1, 1), "ry": (1, 1), "rz": (1, 1),
    "p": (1, 1), "u1": (1, 1), "u2": (2, 1), "u3": (3, 1), "u": (3, 1),
    "cx": (0, 2), "cy": (0, 2), "cz": (0, 2), "ch": (0, 2), "swap": (0, 2),
    "ccx": (0, 3), "cswap": (0, 3),
    "cu1": (1, 2), "cp": (1, 2), "cphase": (1, 2), "crz": (1, 2),
    "cu3": (3, 2), "cu": (4, 2),
}

_TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<comment>//[^\n]*)
  | (?P<num>(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?)
  | (?P<id>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<str>"[^"]*")
  | (?P<arrow>->)
  | (?P<punct>[{}()\[\],;=<>!+\-*/^:])
""",
    re.VERBOSE,
)


def _tokenize(text: str) -> List[Tuple[str, str]]:
    tokens: List[Tuple[str, str]] = []
    pos = 0
    while pos < len(text):
        match = _TOKEN_RE.match(text, pos)
        if match is None:
            raise SyntaxError("无法识别的字符 %r（偏移 %d）" % (text[pos], pos))
        pos = match.end()
        kind = match.lastgroup
        if kind in ("ws", "comment"):
            continue
        tokens.append((kind, match.group()))
    return tokens


class _GateDef:
    """自定义 gate 定义：gate name(p1,..) a, b { body }"""

    def __init__(self, name: str, params: List[str], args: List[str], body: List):
        self.name = name
        self.params = params
        self.args = args
        # body 每项: (门名, [参数 token 列表], [(形参名, None)])
        self.body = body


class _Parser:
    def __init__(self, tokens: List[Tuple[str, str]]):
        self.tokens = tokens
        self.pos = 0
        self.qregs: Dict[str, int] = {}
        self.qsizes: Dict[str, int] = {}
        self.cregs: Dict[str, int] = {}
        self.csizes: Dict[str, int] = {}
        self.n_qubits = 0
        self.n_clbits = 0
        self.gate_defs: Dict[str, _GateDef] = {}
        self.circuit = Circuit()
        # 参数表达式求值状态
        self._etokens: List[Tuple[str, str]] = []
        self._epos = 0
        self._eenv: Dict[str, float] = {}

    # ---- token 游标 ----
    def peek(self) -> Optional[Tuple[str, str]]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next(self) -> Tuple[str, str]:
        if self.pos >= len(self.tokens):
            raise SyntaxError("意外的输入结尾")
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def expect_punct(self, text: str) -> None:
        kind, value = self.next()
        if kind != "punct" or value != text:
            raise SyntaxError("期望 %r，得到 %r" % (text, value))

    def expect_id(self) -> str:
        kind, value = self.next()
        if kind != "id":
            raise SyntaxError("期望标识符，得到 %r" % (value,))
        return value

    def skip_to_semicolon(self) -> None:
        while self.peek() is not None and self.peek()[1] != ";":
            self.next()
        self.expect_punct(";")

    def _bracket_int(self) -> int:
        self.expect_punct("[")
        digits = ""
        while True:
            kind, value = self.next()
            if kind == "num":
                digits += value
            elif kind == "punct" and value == "]":
                break
            elif kind == "punct" and value == "_":
                continue
            else:
                raise SyntaxError("寄存器下标/长度应为非负整数")
        if not digits:
            raise SyntaxError("寄存器下标/长度为空")
        return int(digits)

    def _parse_ref(self) -> Tuple[str, Optional[int]]:
        """解析 name 或 name[idx]，返回 (名字, 下标或 None)。"""
        name = self.expect_id()
        if self.peek() is not None and self.peek() == ("punct", "["):
            return name, self._bracket_int()
        return name, None

    # ---- 程序结构 ----
    def parse(self) -> Circuit:
        if self.peek() is not None and self.peek() == ("id", "OPENQASM"):
            self.next()
            self.next()  # 版本号
            self.expect_punct(";")
        while self.peek() is not None:
            self._statement()
        self.circuit.n_qubits = self.n_qubits
        self.circuit.n_clbits = self.n_clbits
        return self.circuit

    def _statement(self) -> None:
        kind, value = self.peek()
        if kind != "id":
            raise SyntaxError("期望语句，得到 %r" % (value,))
        if value == "include":
            self.next()
            self.next()  # 文件名
            self.expect_punct(";")
        elif value == "opaque":
            self.next()
            self.skip_to_semicolon()
        elif value in ("qreg", "creg", "qubit", "bit"):
            self._declaration()
        elif value == "gate":
            self._gate_def()
        elif value == "measure":
            self._measure()
        elif value == "barrier":
            self.next()
            self.skip_to_semicolon()
        elif value in ("if", "reset"):
            raise SyntaxError("暂不支持 %s（L1 评测电路不使用）" % value)
        else:
            self._gate_call()

    def _declaration(self) -> None:
        kw = self.next()[1]
        if kw in ("qreg", "creg"):
            name = self.expect_id()
            size = self._bracket_int()
        else:  # qubit[n] name; / bit[n] name;
            size = self._bracket_int()
            name = self.expect_id()
        self.expect_punct(";")
        if kw in ("qreg", "qubit"):
            if name in self.qregs:
                raise SyntaxError("重复的量子寄存器声明 %r" % name)
            self.qregs[name] = self.n_qubits
            self.qsizes[name] = size
            self.n_qubits += size
        else:
            if name in self.cregs:
                raise SyntaxError("重复的经典寄存器声明 %r" % name)
            self.cregs[name] = self.n_clbits
            self.csizes[name] = size
            self.n_clbits += size

    def _gate_def(self) -> None:
        self.next()  # gate
        name = self.expect_id()
        params: List[str] = []
        if self.peek() is not None and self.peek()[1] == "(":
            self.next()
            while True:
                params.append(self.expect_id())
                kind, value = self.next()
                if value == ")":
                    break
                if value != ",":
                    raise SyntaxError("gate 形参列表格式错误")
        args: List[Tuple[str, Optional[int]]] = []
        while self.peek() is not None and self.peek()[1] != "{":
            if self.peek() == ("punct", ","):
                self.next()
                continue
            args.append(self._parse_ref())
        self.expect_punct("{")
        body = []
        while True:
            peeked = self.peek()
            if peeked is None:
                raise SyntaxError("gate 定义缺少 }")
            if peeked == ("punct", "}"):
                self.next()
                break
            if peeked[0] != "id":
                raise SyntaxError("gate 体内只允许门调用，得到 %r" % (peeked[1],))
            if peeked[1] == "barrier":
                self.next()
                self.skip_to_semicolon()
                continue
            body.append(self._parse_call_head())
        formal_args = [name for name, _ in args]
        if len(set(formal_args)) != len(formal_args):
            raise SyntaxError("gate 形参重名")
        for _, _, refs in body:
            for ref_name, ref_idx in refs:
                if ref_idx is not None or ref_name not in formal_args:
                    raise SyntaxError("gate 体内引用 %r 不是形参" % ((ref_name, ref_idx),))
        self.gate_defs[name] = _GateDef(name, params, formal_args, body)

    def _parse_call_head(self) -> Tuple[str, List[List[Tuple[str, str]]],
                                       List[Tuple[str, Optional[int]]]]:
        """解析一条门调用头：name(params...) refs...;"""
        name = self.expect_id()
        raw_params: List[List[Tuple[str, str]]] = []
        if self.peek() is not None and self.peek()[1] == "(":
            self.next()
            current: List[Tuple[str, str]] = []
            depth = 1
            while True:
                kind, value = self.next()
                if kind == "punct" and value == "(":
                    depth += 1
                elif kind == "punct" and value == ")":
                    depth -= 1
                    if depth == 0:
                        raw_params.append(current)
                        break
                elif kind == "punct" and value == "," and depth == 1:
                    raw_params.append(current)
                    current = []
                    continue
                current.append((kind, value))
        refs: List[Tuple[str, Optional[int]]] = []
        while self.peek() is not None and self.peek()[1] != ";":
            if self.peek() == ("punct", ","):
                self.next()
                continue
            refs.append(self._parse_ref())
        self.expect_punct(";")
        return name, raw_params, refs

    def _measure(self) -> None:
        self.next()  # measure
        qreg, qidx = self._parse_ref()
        kind, value = self.next()
        if kind != "arrow" and value != "->":
            raise SyntaxError("期望 ->，得到 %r" % (value,))
        creg, cidx = self._parse_ref()
        self.expect_punct(";")
        if qreg not in self.qregs or creg not in self.cregs:
            raise SyntaxError("measure 引用了未声明的寄存器")
        pairs: List[Tuple[int, int]] = []
        if qidx is None and cidx is None:
            size = self.qsizes[qreg]
            if size != self.csizes[creg]:
                raise SyntaxError("整寄存器测量要求两寄存器等长")
            base_q, base_c = self.qregs[qreg], self.cregs[creg]
            pairs = [(base_q + i, base_c + i) for i in range(size)]
        elif qidx is not None and cidx is not None:
            pairs = [(qidx, cidx)]
        else:
            raise SyntaxError("measure 两端必须同时为寄存器或同时为位")
        self.circuit.measures.extend(pairs)

    # ---- 门调用与展开 ----
    def _gate_call(self) -> None:
        name, raw_params, refs = self._parse_call_head()
        if name in self.gate_defs:
            gate = self.gate_defs[name]
            values = [self._eval(tokens, {}) for tokens in raw_params]
            if len(values) != len(gate.params):
                raise SyntaxError("gate %s 需要 %d 个参数" % (name, len(gate.params)))
            arg_map: Dict[str, int] = {}
            if len(refs) != len(gate.args):
                raise SyntaxError("gate %s 需要 %d 个比特" % (name, len(gate.args)))
            for (rname, ridx), formal in zip(refs, gate.args):
                if ridx is None:
                    raise SyntaxError("gate 调用实参 %r 必须带下标" % rname)
                arg_map[formal] = self.qregs[rname] + ridx
            self._expand(name, values, arg_map, depth=0)
            return
        if name not in BUILTIN_GATES:
            raise SyntaxError("未知门 %r" % name)
        n_params, n_qubits = BUILTIN_GATES[name]
        if len(raw_params) != n_params:
            raise SyntaxError("门 %s 需要 %d 个参数，得到 %d"
                              % (name, n_params, len(raw_params)))
        params = tuple(self._eval(tokens, {}) for tokens in raw_params)
        for qubits in self._resolve_builtin_refs(name, refs, n_qubits):
            self.circuit.ops.append(Op(name, params, tuple(qubits)))

    def _resolve_builtin_refs(self, name: str, refs, n_qubits: int) -> List[List[int]]:
        """解析门实参，支持整寄存器广播，返回"每次施加的比特列表"。

        - n_qubits == 1 且实参为寄存器：逐位展开为多次施加（如 `x q;`）
        - n_qubits > 1 且全部实参为等长寄存器：按位配对（如 `cx q, r;`）
        - 显式下标：常规单次施加
        """
        broadcast = [idx is None for _, idx in refs]
        if any(broadcast):
            if any(idx is not None for _, idx in refs):
                raise SyntaxError("门 %s 的广播实参不能与位下标混用" % name)
            if n_qubits == 1:
                rname = refs[0][0]
                if rname not in self.qregs:
                    raise SyntaxError("未知量子寄存器 %r" % rname)
                return [[self.qregs[rname] + i]
                        for i in range(self.qsizes[rname])]
            if len(refs) != n_qubits:
                raise SyntaxError("门 %s 广播需要 %d 个等长寄存器，得到 %d"
                                  % (name, n_qubits, len(refs)))
            for rname, _ in refs:
                if rname not in self.qregs:
                    raise SyntaxError("未知量子寄存器 %r" % rname)
            size = self.qsizes[refs[0][0]]
            if any(self.qsizes[r] != size for r, _ in refs):
                raise SyntaxError("门 %s 广播要求各寄存器等长" % name)
            return [[self.qregs[r] + k for r, _ in refs] for k in range(size)]
        resolved: List[int] = []
        for rname, ridx in refs:
            if rname not in self.qregs:
                raise SyntaxError("未知量子寄存器 %r" % rname)
            resolved.append(self.qregs[rname] + ridx)
        if len(resolved) != n_qubits:
            raise SyntaxError("门 %s 需要 %d 个量子比特，得到 %d"
                              % (name, n_qubits, len(resolved)))
        return [resolved]

    def _expand(self, name: str, param_values: List[float],
                arg_map: Dict[str, int], depth: int) -> None:
        if depth > 32:
            raise SyntaxError("gate 展开过深，疑似递归定义")
        gate = self.gate_defs[name]
        env = dict(zip(gate.params, param_values))
        for sub_name, sub_raw, sub_refs in gate.body:
            sub_values = [self._eval(tokens, env) for tokens in sub_raw]
            sub_args: List[int] = [arg_map[rname] for rname, _ in sub_refs]
            if sub_name in self.gate_defs:
                sub_gate = self.gate_defs[sub_name]
                sub_map = dict(zip(sub_gate.args, sub_args))
                self._expand(sub_name, sub_values, sub_map, depth + 1)
                continue
            if sub_name not in BUILTIN_GATES:
                raise SyntaxError("gate 体内未知门 %r" % sub_name)
            n_params, n_qubits = BUILTIN_GATES[sub_name]
            if len(sub_values) != n_params or len(sub_args) != n_qubits:
                raise SyntaxError("gate %s 参数/比特个数不匹配" % sub_name)
            self.circuit.ops.append(Op(sub_name, tuple(sub_values), tuple(sub_args)))

    # ---- 参数表达式求值：add := mul ((+|-) mul)* ----
    def _eval(self, tokens: List[Tuple[str, str]], env: Dict[str, float]) -> float:
        if not tokens:
            raise SyntaxError("空参数表达式")
        self._etokens = tokens
        self._epos = 0
        self._eenv = env
        value = self._expr_add()
        if self._epos != len(self._etokens):
            raise SyntaxError("参数表达式存在多余符号")
        return value

    def _epeek(self) -> Tuple[str, str]:
        return self._etokens[self._epos]

    def _expr_add(self) -> float:
        value = self._expr_mul()
        while self._epos < len(self._etokens):
            kind, text = self._epeek()
            if kind == "punct" and text in ("+", "-"):
                self._epos += 1
                rhs = self._expr_mul()
                value = value + rhs if text == "+" else value - rhs
            else:
                break
        return value

    def _expr_mul(self) -> float:
        value = self._expr_unary()
        while self._epos < len(self._etokens):
            kind, text = self._epeek()
            if kind == "punct" and text in ("*", "/"):
                self._epos += 1
                rhs = self._expr_unary()
                value = value * rhs if text == "*" else value / rhs
            else:
                break
        return value

    def _expr_unary(self) -> float:
        kind, text = self._epeek()
        if kind == "punct" and text == "-":
            self._epos += 1
            return -self._expr_unary()
        if kind == "punct" and text == "+":
            self._epos += 1
            return self._expr_unary()
        return self._expr_atom()

    def _expr_atom(self) -> float:
        kind, text = self._epeek()
        self._epos += 1
        if kind == "num":
            return float(text)
        if kind == "id":
            if text == "pi":
                return math.pi
            if text in self._eenv:
                return self._eenv[text]
            raise SyntaxError("未知符号 %r" % text)
        if kind == "punct" and text == "(":
            value = self._expr_add()
            kind, text = self._epeek()
            if kind != "punct" or text != ")":
                raise SyntaxError("括号不匹配")
            self._epos += 1
            return value
        raise SyntaxError("参数表达式存在非法符号 %r" % text)


def parse_qasm(text: str) -> Circuit:
    """把 OpenQASM 2.0 文本解析为 Circuit。"""
    return _Parser(_tokenize(text)).parse()
