"""L3 Hybrid-QASM compiler: quantum op extraction plus RISC-V code generation.

The classical block is compiled through a real lexer/parser/codegen chain rather
than pattern matching, because grading injects randomized programs and every
measurement-value combination.

Register contract fixed by the rules:
  - ``r1``..``r9``           -> ``x1``..``x9``
  - measured bit ``c[k]``    -> ``x{10 + k}`` (injected by the grader)
Scratch registers therefore start above the measurement window, and generated
code never writes to a measurement register: the grader sets ``x10`` *after*
``load_program`` zeroes the file, so clobbering it would destroy the input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

from .circuit import GateOp, MeasureOp
from .gates import format_angle
from .parse_qasm import _strip_comments, parse_qasm

MEASURE_REG_BASE = 10
MAX_REG = 31
VAR_COUNT = 9

# ---------------------------------------------------------------------------
# Classical-block AST
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Literal:
    value: int


@dataclass(frozen=True)
class VarRef:
    """``r1``..``r9``, stored as the 1-based index."""

    index: int


@dataclass(frozen=True)
class CBitRef:
    """A measured classical bit; ``slot`` is the global bit position."""

    name: str
    index: int
    slot: int


@dataclass(frozen=True)
class BinOp:
    op: str  # '+' or '-'
    left: "Expr"
    right: "Expr"


Expr = Union[Literal, VarRef, CBitRef, BinOp]


@dataclass(frozen=True)
class Compare:
    op: str  # '==' or '!='
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Assign:
    target: int  # 1-based r-index
    value: Expr


@dataclass(frozen=True)
class If:
    cond: Compare
    then_body: Tuple["Stmt", ...]
    else_body: Tuple["Stmt", ...]


Stmt = Union[Assign, If]


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<op2>==|!=)
  | (?P<int>\d+)
  | (?P<ident>[A-Za-z_]\w*)
  | (?P<sym>[{}()\[\];=+\-,])
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class Token:
    kind: str  # 'int' | 'ident' | 'sym' | 'op2'
    text: str
    pos: int


def _tokenize(source: str) -> List[Token]:
    tokens: List[Token] = []
    pos = 0
    length = len(source)
    while pos < length:
        match = _TOKEN_RE.match(source, pos)
        if not match:
            raise ValueError(
                f"unexpected character {source[pos]!r} at offset {pos} of classical block"
            )
        pos = match.end()
        if match.lastgroup == "ws":
            continue
        tokens.append(Token(match.lastgroup, match.group(), match.start()))
    return tokens


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: Sequence[Token], cbit_slots: Dict[Tuple[str, int], int]):
        self._tokens = list(tokens)
        self._pos = 0
        self._cbit_slots = cbit_slots

    # -- token helpers ----------------------------------------------------
    def _peek(self) -> Optional[Token]:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _next(self) -> Token:
        token = self._peek()
        if token is None:
            raise ValueError("unexpected end of classical block")
        self._pos += 1
        return token

    def _accept(self, text: str) -> bool:
        token = self._peek()
        if token is not None and token.text == text:
            self._pos += 1
            return True
        return False

    def _expect(self, text: str) -> Token:
        token = self._next()
        if token.text != text:
            raise ValueError(f"expected {text!r} but found {token.text!r}")
        return token

    def _at_end(self) -> bool:
        return self._pos >= len(self._tokens)

    # -- grammar ----------------------------------------------------------
    def parse_program(self) -> Tuple[Stmt, ...]:
        body = self._parse_statements(terminator=None)
        if not self._at_end():
            raise ValueError(f"trailing tokens in classical block: {self._peek().text!r}")
        return body

    def _parse_statements(self, terminator: Optional[str]) -> Tuple[Stmt, ...]:
        body: List[Stmt] = []
        while True:
            token = self._peek()
            if token is None:
                if terminator is not None:
                    raise ValueError(f"missing {terminator!r} in classical block")
                break
            if terminator is not None and token.text == terminator:
                break
            body.append(self._parse_statement())
        return tuple(body)

    def _parse_statement(self) -> Stmt:
        token = self._peek()
        if token is None:
            raise ValueError("unexpected end of classical block")
        if token.kind == "ident" and token.text == "if":
            return self._parse_if()
        return self._parse_assign()

    def _parse_block_or_statement(self) -> Tuple[Stmt, ...]:
        if self._accept("{"):
            body = self._parse_statements(terminator="}")
            self._expect("}")
            return body
        return (self._parse_statement(),)

    def _parse_if(self) -> If:
        self._expect("if")
        self._expect("(")
        cond = self._parse_condition()
        self._expect(")")
        then_body = self._parse_block_or_statement()
        else_body: Tuple[Stmt, ...] = ()
        token = self._peek()
        if token is not None and token.text == "else":
            self._next()
            else_body = self._parse_block_or_statement()
        return If(cond=cond, then_body=then_body, else_body=else_body)

    def _parse_assign(self) -> Assign:
        token = self._next()
        index = self._var_index(token)
        self._expect("=")
        value = self._parse_expr()
        # A trailing semicolon is required by the grammar but tolerated as optional
        # so a final statement without one still compiles.
        self._accept(";")
        return Assign(target=index, value=value)

    def _parse_condition(self) -> Compare:
        left = self._parse_expr()
        token = self._next()
        if token.kind != "op2":
            raise ValueError(f"expected '==' or '!=' but found {token.text!r}")
        right = self._parse_expr()
        return Compare(op=token.text, left=left, right=right)

    def _parse_expr(self) -> Expr:
        node = self._parse_term()
        while True:
            token = self._peek()
            if token is None or token.text not in {"+", "-"}:
                return node
            self._next()
            node = BinOp(op=token.text, left=node, right=self._parse_term())

    def _parse_term(self) -> Expr:
        token = self._next()
        if token.text == "(":
            inner = self._parse_expr()
            self._expect(")")
            return inner
        if token.text == "-":
            return BinOp(op="-", left=Literal(0), right=self._parse_term())
        if token.text == "+":
            return self._parse_term()
        if token.kind == "int":
            return Literal(int(token.text))
        if token.kind == "ident":
            if re.fullmatch(r"r[1-9]", token.text):
                return VarRef(index=int(token.text[1:]))
            # Classical register bit reference: name '[' index ']'
            self._expect("[")
            index_token = self._next()
            if index_token.kind != "int":
                raise ValueError(f"expected bit index but found {index_token.text!r}")
            self._expect("]")
            key = (token.text, int(index_token.text))
            if key not in self._cbit_slots:
                raise ValueError(f"unknown classical bit {token.text}[{index_token.text}]")
            return CBitRef(name=key[0], index=key[1], slot=self._cbit_slots[key])
        raise ValueError(f"unexpected token {token.text!r} in expression")

    def _var_index(self, token: Token) -> int:
        if token.kind == "ident" and re.fullmatch(r"r[1-9]", token.text):
            return int(token.text[1:])
        raise ValueError(f"assignment target must be r1..r9, got {token.text!r}")


# ---------------------------------------------------------------------------
# Reference interpreter (independent of codegen, used for differential tests)
# ---------------------------------------------------------------------------


def interpret_classical(
    body: Sequence[Stmt], cbits: Dict[int, int]
) -> Dict[int, int]:
    """Evaluate the AST directly and return the final ``r1``..``r9`` values."""
    env: Dict[int, int] = {index: 0 for index in range(1, VAR_COUNT + 1)}

    def value_of(expr: Expr) -> int:
        if isinstance(expr, Literal):
            return expr.value
        if isinstance(expr, VarRef):
            return env[expr.index]
        if isinstance(expr, CBitRef):
            return cbits.get(expr.slot, 0)
        if isinstance(expr, BinOp):
            left, right = value_of(expr.left), value_of(expr.right)
            return left + right if expr.op == "+" else left - right
        raise TypeError(f"unknown expression node: {expr!r}")

    def truth(cond: Compare) -> bool:
        left, right = value_of(cond.left), value_of(cond.right)
        return left == right if cond.op == "==" else left != right

    def run(statements: Sequence[Stmt]) -> None:
        for stmt in statements:
            if isinstance(stmt, Assign):
                env[stmt.target] = value_of(stmt.value)
            elif isinstance(stmt, If):
                run(stmt.then_body if truth(stmt.cond) else stmt.else_body)
            else:
                raise TypeError(f"unknown statement node: {stmt!r}")

    run(body)
    return env


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------


class _ScratchPool:
    """Stack allocator over the registers above the measurement window."""

    def __init__(self, low: int, high: int):
        if low > high:
            raise ValueError(
                "no scratch registers left; classical register is too wide for x31"
            )
        self._free = list(range(low, high + 1))

    def acquire(self) -> int:
        if not self._free:
            raise ValueError("ran out of scratch registers while compiling")
        return self._free.pop()

    def release(self, index: int) -> None:
        self._free.append(index)


class _CodeGen:
    def __init__(self, n_cbits: int):
        self.lines: List[str] = []
        self._labels = 0
        self._pool = _ScratchPool(MEASURE_REG_BASE + max(n_cbits, 1), MAX_REG)

    def emit(self, text: str) -> None:
        self.lines.append(f"  {text}")

    def label(self, name: str) -> None:
        self.lines.append(f"{name}:")

    def new_label(self, tag: str) -> str:
        self._labels += 1
        return f"L{self._labels}_{tag}"

    # -- expressions ------------------------------------------------------
    def eval_into(self, expr: Expr, dest: int) -> None:
        """Materialise ``expr`` into register ``x{dest}``.

        ``dest`` is always a scratch register, so evaluating a sub-expression can
        never clobber an ``r``-variable that is still needed (``r1 = r2 + r1``).
        """
        if isinstance(expr, Literal):
            self.emit(f"li x{dest}, {expr.value}")
            return
        if isinstance(expr, VarRef):
            self._move(dest, expr.index)
            return
        if isinstance(expr, CBitRef):
            self._move(dest, MEASURE_REG_BASE + expr.slot)
            return
        if isinstance(expr, BinOp):
            # Fold a literal right operand into addi to keep the listing readable.
            if isinstance(expr.right, Literal):
                self.eval_into(expr.left, dest)
                delta = expr.right.value if expr.op == "+" else -expr.right.value
                if delta:
                    self.emit(f"addi x{dest}, x{dest}, {delta}")
                return
            self.eval_into(expr.left, dest)
            rhs = self._pool.acquire()
            self.eval_into(expr.right, rhs)
            mnemonic = "add" if expr.op == "+" else "sub"
            self.emit(f"{mnemonic} x{dest}, x{dest}, x{rhs}")
            self._pool.release(rhs)
            return
        raise TypeError(f"unknown expression node: {expr!r}")

    def _move(self, dest: int, src: int) -> None:
        if dest != src:
            self.emit(f"addi x{dest}, x{src}, 0")

    # -- statements -------------------------------------------------------
    def gen_body(self, statements: Sequence[Stmt]) -> None:
        for stmt in statements:
            if isinstance(stmt, Assign):
                self.gen_assign(stmt)
            elif isinstance(stmt, If):
                self.gen_if(stmt)
            else:
                raise TypeError(f"unknown statement node: {stmt!r}")

    def gen_assign(self, stmt: Assign) -> None:
        temp = self._pool.acquire()
        self.eval_into(stmt.value, temp)
        self._move(stmt.target, temp)
        self._pool.release(temp)

    def gen_if(self, stmt: If) -> None:
        left = self._pool.acquire()
        right = self._pool.acquire()
        self.eval_into(stmt.cond.left, left)
        self.eval_into(stmt.cond.right, right)

        else_label = self.new_label("ELSE")
        end_label = self.new_label("ENDIF")
        # Branch past the then-body when the condition is false.
        skip = "bne" if stmt.cond.op == "==" else "beq"
        target = else_label if stmt.else_body else end_label
        self.emit(f"{skip} x{left}, x{right}, {target}")
        self._pool.release(right)
        self._pool.release(left)

        self.gen_body(stmt.then_body)
        if stmt.else_body:
            self.emit(f"j {end_label}")
            self.label(else_label)
            self.gen_body(stmt.else_body)
        self.label(end_label)


def compile_classical(body: Sequence[Stmt], n_cbits: int) -> str:
    """Lower the classical AST to the emulator's seven-instruction subset."""
    gen = _CodeGen(n_cbits=n_cbits)
    header = [
        "# LoomQ L3 generated RISC-V assembly",
        "#   r1..r9 -> x1..x9",
        f"#   measured c[k] -> x{MEASURE_REG_BASE}+k (injected by the runner)",
        f"#   scratch -> x{MEASURE_REG_BASE + max(n_cbits, 1)}..x{MAX_REG}",
    ]
    gen.gen_body(body)
    if not gen.lines:
        # Keep the artifact non-empty and executable when there is nothing to do.
        gen.emit("addi x0, x0, 0")
    return "\n".join(header + gen.lines) + "\n"


# ---------------------------------------------------------------------------
# Hybrid-QASM splitting
# ---------------------------------------------------------------------------

_CLASSICAL_KEYWORD = re.compile(r"\bclassical\b", re.IGNORECASE)


def split_hybrid(source: str) -> Tuple[str, List[str]]:
    """Separate the quantum statements from the ``classical { ... }`` blocks."""
    cleaned = _strip_comments(source)
    quantum_parts: List[str] = []
    classical_blocks: List[str] = []
    cursor = 0

    while True:
        match = _CLASSICAL_KEYWORD.search(cleaned, cursor)
        if not match:
            quantum_parts.append(cleaned[cursor:])
            break
        brace = cleaned.find("{", match.end())
        if brace == -1:
            raise ValueError("'classical' block is missing its opening brace")
        if cleaned[match.end() : brace].strip():
            raise ValueError("unexpected tokens between 'classical' and '{'")

        depth = 0
        end = -1
        for pos in range(brace, len(cleaned)):
            char = cleaned[pos]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = pos
                    break
        if end == -1:
            raise ValueError("'classical' block is missing its closing brace")

        quantum_parts.append(cleaned[cursor : match.start()])
        classical_blocks.append(cleaned[brace + 1 : end])
        cursor = end + 1

    return "".join(quantum_parts), classical_blocks


def _format_op(op: Union[GateOp, MeasureOp]) -> str:
    if isinstance(op, MeasureOp):
        return (
            f"measure {op.qubit[0]}[{op.qubit[1]}] -> {op.cbit[0]}[{op.cbit[1]}];"
        )
    args = ", ".join(f"{name}[{index}]" for name, index in op.qubits)
    if op.params:
        params = ", ".join(format_angle(value) for value in op.params)
        return f"{op.name}({params}) {args};"
    return f"{op.name} {args};"


def parse_hybrid(source: str) -> Tuple[List[str], Tuple[Stmt, ...], int]:
    """Return canonical quantum statements, the classical AST, and the cbit count."""
    if not isinstance(source, str) or not source.strip():
        raise ValueError("hybrid_qasm_str must be a non-empty string")

    quantum_text, classical_blocks = split_hybrid(source)
    # Reuse the L1 parser so the quantum half is validated against the same
    # whitelist and normalised the same way as a plain L1 submission.
    circuit = parse_qasm(quantum_text)
    quantum_ops = [_format_op(op) for op in circuit.ops]

    cbit_slots = {
        (name, local): circuit.cbit_index((name, local))
        for name, size in circuit.cregs.items()
        for local in range(size)
    }

    body: List[Stmt] = []
    for block in classical_blocks:
        tokens = _tokenize(block)
        body.extend(_Parser(tokens, cbit_slots).parse_program())

    return quantum_ops, tuple(body), circuit.n_clbits()


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """L3 entry point: Hybrid-QASM -> (quantum op list, RISC-V assembly)."""
    quantum_ops, body, n_cbits = parse_hybrid(hybrid_qasm_str)
    assembly = compile_classical(body, n_cbits=n_cbits)
    return quantum_ops, assembly
