"""Hybrid-QASM parsing: split quantum ops from the classical control block.

The classical block grammar (from the problem statement) is:

    stmt    := 'if' '(' cond ')' '{' stmt* '}' [ 'else' '{' stmt* '}' ]
             | reg '=' expr ';'
    cond    := operand ( '==' | '!=' ) operand
    operand := integer | 'r' [1-9] | 'c' '[' integer ']'
    expr    := operand ( ( '+' | '-' ) operand )*

The parser is hand-written and produces a small AST; the RISC-V code
generator consumes it. Measurement bits c[k] map to x10+k, registers
r1..r9 map to x1..x9.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union

# --- AST nodes -----------------------------------------------------------

Imm = int
RegRef = int  # r-index, 1..9
CbitRef = int  # c-index

Operand = Tuple[str, int]  # ("imm", v) | ("reg", i) | ("cbit", k)


@dataclass
class Assign:
    target: RegRef
    expr: List[Tuple[str, Operand]]  # (op, operand), first op is "="


@dataclass
class Cond:
    left: Operand
    op: str  # "==" or "!="
    right: Operand


@dataclass
class If:
    cond: Cond
    then_body: List[object]
    else_body: Optional[List[object]] = None


@dataclass
class HybridSplit:
    quantum_ops: List[str]
    classic_text: str


# --- Classical block tokenizer/parser -------------------------------------

_TOKEN_RE = re.compile(
    r"""
    (?P<num>\d+)
  | (?P<reg>r[1-9])
  | (?P<cbit>c\[\d+\])
  | (?P<kw>if|else)
  | (?P<op>==|!=|[=+\-])
  | (?P<lbrace>\{)
  | (?P<rbrace>\})
  | (?P<lparen>\()
  | (?P<rparen>\))
  | (?P<semi>;)
  | (?P<ws>\s+)
  """,
    re.VERBOSE,
)


class ClassicParseError(ValueError):
    pass


class _Tokenizer:
    def __init__(self, text: str) -> None:
        self.tokens: List[Tuple[str, str]] = []
        pos = 0
        while pos < len(text):
            match = _TOKEN_RE.match(text, pos)
            if not match:
                raise ClassicParseError("unexpected character %r" % text[pos])
            kind = match.lastgroup
            value = match.group()
            if kind != "ws":
                self.tokens.append((kind, value))
            pos = match.end()
        self.pos = 0

    def peek(self) -> Optional[Tuple[str, str]]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def next(self) -> Tuple[str, str]:
        token = self.peek()
        if token is None:
            raise ClassicParseError("unexpected end of classical block")
        self.pos += 1
        return token

    def expect(self, kind: str) -> Tuple[str, str]:
        token = self.next()
        if token[0] != kind:
            raise ClassicParseError("expected %r, got %r" % (kind, token))
        return token


def _parse_operand(tok: Tuple[str, str], tokens: Optional["_Tokenizer"] = None) -> Operand:
    kind, value = tok
    if kind == "num":
        return ("imm", int(value))
    if kind == "reg":
        return ("reg", int(value[1:]))
    if kind == "cbit":
        return ("cbit", int(value[2:-1]))
    if kind == "op" and value == "-" and tokens is not None:
        # unary minus: '-' immediately followed by a number literal
        nxt = tokens.peek()
        if nxt is not None and nxt[0] == "num":
            tokens.next()
            return ("imm", -int(nxt[1]))
        raise ClassicParseError("expected operand after '-', got %r" % (nxt,))
    raise ClassicParseError("expected operand, got %r" % (value,))


class _Parser:
    def __init__(self, text: str) -> None:
        self.tokens = _Tokenizer(text)

    def parse_block(self) -> List[object]:
        stmts: List[object] = []
        while True:
            token = self.tokens.peek()
            if token is None:
                break
            if token[0] == "rbrace":
                break
            stmts.append(self._parse_stmt())
        return stmts

    def _parse_stmt(self) -> object:
        token = self.tokens.peek()
        if token[0] == "reg":
            target = int(self.tokens.next()[1][1:])
            self.tokens.expect("op")  # '='
            expr = self._parse_expr()
            self.tokens.expect("semi")
            return Assign(target=target, expr=expr)
        if token[0] == "kw" and token[1] == "if":
            return self._parse_if()
        raise ClassicParseError("unexpected statement %r" % (token,))

    def _parse_if(self) -> If:
        self.tokens.expect("kw")  # 'if'
        self.tokens.expect("lparen")
        cond = self._parse_cond()
        self.tokens.expect("rparen")
        self.tokens.expect("lbrace")
        then_body = self.parse_block()
        self.tokens.expect("rbrace")
        else_body: Optional[List[object]] = None
        peek = self.tokens.peek()
        if peek is not None and peek[0] == "kw" and peek[1] == "else":
            self.tokens.next()
            self.tokens.expect("lbrace")
            else_body = self.parse_block()
            self.tokens.expect("rbrace")
        return If(cond=cond, then_body=then_body, else_body=else_body)

    def _parse_cond(self) -> Cond:
        left = _parse_operand(self.tokens.next(), self.tokens)
        op_token = self.tokens.expect("op")
        if op_token[1] not in ("==", "!="):
            raise ClassicParseError("expected == or != in condition")
        right = _parse_operand(self.tokens.next(), self.tokens)
        return Cond(left=left, op=op_token[1], right=right)

    def _parse_expr(self) -> List[Tuple[str, Operand]]:
        first = _parse_operand(self.tokens.next(), self.tokens)
        expr: List[Tuple[str, Operand]] = [("=", first)]
        while True:
            peek = self.tokens.peek()
            if peek is None or peek[0] != "op" or peek[1] not in ("+", "-"):
                break
            op = self.tokens.next()[1]
            expr.append((op, _parse_operand(self.tokens.next(), self.tokens)))
        return expr


# --- Hybrid-QASM splitting -------------------------------------------------

def split_hybrid(hybrid_qasm_str: str) -> HybridSplit:
    """Separate the quantum statements from the classical control block."""
    quantum_ops: List[str] = []
    classic_lines: List[str] = []
    brace_depth = 0
    in_classical = False
    for raw_line in hybrid_qasm_str.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        if in_classical:
            classic_lines.append(line)
            brace_depth += line.count("{") - line.count("}")
            if brace_depth <= 0:
                in_classical = False
            continue
        lower = line.lower()
        if lower.startswith("classical"):
            in_classical = True
            content = line[len("classical"):].strip()
            brace_depth = content.count("{") - content.count("}")
            if content.startswith("{"):
                content = content[1:].strip()  # drop the outer block brace
            if content:
                classic_lines.append(content)
            if brace_depth <= 0:
                in_classical = False
            continue
        if (
            lower.startswith("openqasm")
            or lower.startswith("include")
            or lower.startswith("qreg")
            or lower.startswith("creg")
            or lower.startswith("barrier")
        ):
            continue
        quantum_ops.append(line)
    if in_classical:
        raise ClassicParseError("unterminated classical block")
    return HybridSplit(quantum_ops=quantum_ops, classic_text="\n".join(classic_lines))


def parse_classic(text: str) -> List[object]:
    """Parse the classical block text into a statement AST."""
    return _Parser(text).parse_block()
