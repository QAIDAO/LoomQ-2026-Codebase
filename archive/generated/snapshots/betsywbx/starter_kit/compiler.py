"""
A compiler that separate a given hybrid-QASM into two sections: standard 
OpenQASM2.0 syntax and RISC-V assembly text that achieves classical control 
flow. It is designed in the following structure:
    1. Extract the classical block
    2.tokenise the classical block, then parse them into an AST
    3. Traverse the AST, translate it into RISC-V
"""

import re
from typing import List, Tuple, Optional, Union

# Extract classical{} block from the given Hybrid-QASM string by matching  
# curly brackets, {}
def _extract_classical_block(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    # remove comments
    lines = []
    for line in hybrid_qasm_str.splitlines():
        if "//" in line:
            line = line[:line.index("//")]
        lines.append(line)
    text = "\n".join(lines)

    start = text.find("classical")
    if start == -1:
        raise ValueError("No classical{} block found from input")

    brace_start = text.find("{", start)
    if brace_start == -1:
        raise ValueError("No '{' found after the key word 'classical'")

    depth = 0
    end = None
    for i in range(brace_start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        raise ValueError("Unmatched curly brakets in classical{}")

    classical_body = text[brace_start + 1:end]

    # OpenQASM2.0 = text before classical + text after classical
    before = text[:start]
    after = text[end + 1:]
    quantum_text = before + "\n" + after

    quantum_ops = []
    for stmt in quantum_text.split(";"):
        stmt = stmt.strip()
        if not stmt:
            continue
        if stmt.startswith(("OPENQASM", "include", "qreg", "creg")):
            continue
        quantum_ops.append(stmt + ";")

    return quantum_ops, classical_body


# Analyse classical block, then create a simple Abstract Syntax Tree
_TOKEN_RE = re.compile(r"""
    \s*(?:
        (?P<NUMBER>-?\d+)
      | (?P<CREG>c\[\d+\])
      | (?P<REG>r[1-9])
      | (?P<IF>\bif\b)
      | (?P<ELSE>\belse\b)
      | (?P<EQ>==)
      | (?P<NE>!=)
      | (?P<ASSIGN>=)
      | (?P<PLUS>\+)
      | (?P<MINUS>-)
      | (?P<LBRACE>\{)
      | (?P<RBRACE>\})
      | (?P<LPAREN>\()
      | (?P<RPAREN>\))
      | (?P<SEMI>;)
    )
""", re.VERBOSE)


# Tokenise all non-space characters
def _tokenise(text: str) -> List[Tuple[str, str]]:
    tokens = []
    pos = 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        m = _TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            raise ValueError(f"Undefined characters in classical block: {text[pos:pos+20]!r}")
        kind = m.lastgroup
        value = m.group(kind)
        tokens.append((kind, value))
        pos = m.end()
    return tokens


# AST nodes: represented by classes
class Assign:
    def __init__(self, reg_num: int, expr):
        self.reg_num = reg_num
        self.expr = expr


class IfElse:
    def __init__(self, cond, then_stmts, else_stmts):
        self.cond = cond
        self.then_stmts = then_stmts
        self.else_stmts = else_stmts


class Atom:
    """The smallest element in the expression: int, reg, creg"""
    def __init__(self, kind: str, value: int):
        self.kind = kind  # 'num' | 'reg' | 'creg'
        self.value = value  # number / reg index(1-9) / creg index(0,1,2..)


class BinExpr:
    def __init__(self, op: str, left: Atom, right: Atom):
        self.op = op  # '+' | '-' | '==' | '!='
        self.left = left
        self.right = right


class Parser:
    def __init__(self, tokens: List[Tuple[str, str]]):
        self.tokens = tokens
        self.pos = 0

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def _advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, kind: str):
        actual_kind, value = self._peek()
        if actual_kind != kind:
            raise ValueError(f"SyntaxError: expect {kind}, but received {actual_kind}({value}) at token {self.pos}")
        return self._advance()

    def parse_program(self) -> List:
        stmts = []
        while self.pos < len(self.tokens):
            stmts.append(self._parse_stmt())
        return stmts

    def _parse_stmt(self):
        kind, _ = self._peek()
        if kind == "IF":
            return self._parse_if()
        elif kind == "REG":
            return self._parse_assign()
        else:
            raise ValueError(f"SyntaxError: unknown starting token {kind}")

    def _parse_if(self):
        self._expect("IF")
        self._expect("LPAREN")
        cond = self._parse_cond()
        self._expect("RPAREN")
        self._expect("LBRACE")
        then_stmts = []
        while self._peek()[0] != "RBRACE":
            then_stmts.append(self._parse_stmt())
        self._expect("RBRACE")

        else_stmts = []
        if self._peek()[0] == "ELSE":
            self._advance()
            self._expect("LBRACE")
            while self._peek()[0] != "RBRACE":
                else_stmts.append(self._parse_stmt())
            self._expect("RBRACE")

        return IfElse(cond, then_stmts, else_stmts)

    def _parse_assign(self):
        _, reg_tok = self._expect("REG")
        reg_num = int(reg_tok[1:])
        self._expect("ASSIGN")
        expr = self._parse_expr()
        self._expect("SEMI")
        return Assign(reg_num, expr)

    def _parse_atom(self) -> Atom:
        kind, value = self._peek()
        if kind == "NUMBER":
            self._advance()
            return Atom("num", int(value))
        elif kind == "REG":
            self._advance()
            return Atom("reg", int(value[1:]))
        elif kind == "CREG":
            self._advance()
            idx = int(value[2:-1])  # "c[3]" -> 3
            return Atom("creg", idx)
        else:
            raise ValueError(f"SyntaxError: expect num/reg/creg, but received {kind}({value})")

    def _parse_expr(self):
        """expr := atom (('+' | '-') atom)? - mini grammar, no nested parentheses"""
        left = self._parse_atom()
        kind, _ = self._peek()
        if kind in ("PLUS", "MINUS"):
            op = "+" if kind == "PLUS" else "-"
            self._advance()
            right = self._parse_atom()
            return BinExpr(op, left, right)
        return left  # a single Atom

    def _parse_cond(self):
        """cond := atom ('==' | '!=') atom"""
        left = self._parse_atom()
        kind, _ = self._peek()
        if kind not in ("EQ", "NE"):
            raise ValueError(f"SyntaxError: expect '==' or '!=' in if condition, but received {kind}")
        op = "==" if kind == "EQ" else "!="
        self._advance()
        right = self._parse_atom()
        return BinExpr(op, left, right)


# Translate the AST to RISC-V assembly language using li/add/sub/addi/beq/bne/j 
def _atom_reg(atom: Atom) -> str:
    """Translate reg/creg to processor. Note that num Atom is not applicable"""
    if atom.kind == "reg":
        return f"x{atom.value}"
    elif atom.kind == "creg":
        return f"x{10 + atom.value}"
    else:
        raise ValueError("num Atom cannot be directly used as a processor")


class CodeGen:
    # x30, x31 are used as temp reg for constant comparision and load
    SCRATCH_REG = "x31"

    def __init__(self):
        self.lines: List[str] = []
        self._label_counter = 0

    def _new_label(self, hint: str) -> str:
        self._label_counter += 1
        return f"{hint}_{self._label_counter}"

    def _emit(self, line: str):
        self.lines.append(line)

    def gen_program(self, stmts: List) -> str:
        for stmt in stmts:
            self._gen_stmt(stmt)
        return "\n".join(self.lines)

    def _gen_stmt(self, stmt):
        if isinstance(stmt, Assign):
            self._gen_assign(stmt)
        elif isinstance(stmt, IfElse):
            self._gen_if(stmt)
        else:
            raise ValueError(f"Unknown syntex: {stmt}")

    def _gen_assign(self, stmt: Assign):
        rd = f"x{stmt.reg_num}"
        expr = stmt.expr

        if isinstance(expr, Atom):
            if expr.kind == "num":
                self._emit(f"li {rd}, {expr.value}")
            else:
                # e.g. r1 = r2, or r1 = c[0]
                self._emit(f"addi {rd}, {_atom_reg(expr)}, 0")
            return

        # expr is BinExpr: '+' or '-'
        left, right = expr.left, expr.right

        if left.kind == "num":
            # e.g. r1 = 5 + r1
            self._emit(f"li {rd}, {left.value}")
            left_reg = rd
        else:
            left_reg = _atom_reg(left)

        if right.kind == "num":
            imm = right.value if expr.op == "+" else -right.value
            self._emit(f"addi {rd}, {left_reg}, {imm}")
        else:
            # right is a reg
            right_reg = _atom_reg(right)
            if expr.op == "+":
                self._emit(f"add {rd}, {left_reg}, {right_reg}")
            else:
                self._emit(f"sub {rd}, {left_reg}, {right_reg}")

    def _gen_cond_branch(self, cond: BinExpr, true_label: str, false_label: str):
        """
        If condition is satisfied, jump to true_label, else jume to false_label. 
        If constant is met, use li and temp reg as beq/bne only applies to two
        registers. 
        """
        left, right = cond.left, cond.right

        if left.kind == "num" and right.kind == "num":
            # both are constant
            self._emit(f"li {self.SCRATCH_REG}, {left.value}")
            left_reg = self.SCRATCH_REG
            self._emit(f"li x30, {right.value}")
            right_reg = "x30"
        elif left.kind == "num":
            self._emit(f"li {self.SCRATCH_REG}, {left.value}")
            left_reg = self.SCRATCH_REG
            right_reg = _atom_reg(right)
        elif right.kind == "num":
            left_reg = _atom_reg(left)
            self._emit(f"li {self.SCRATCH_REG}, {right.value}")
            right_reg = self.SCRATCH_REG
        else:
            left_reg = _atom_reg(left)
            right_reg = _atom_reg(right)

        branch_op = "beq" if cond.op == "==" else "bne"
        self._emit(f"{branch_op} {left_reg}, {right_reg}, {true_label}")
        self._emit(f"j {false_label}")

    def _gen_if(self, stmt: IfElse):
        true_label = self._new_label("IF_TRUE")
        false_label = self._new_label("IF_FALSE")
        end_label = self._new_label("IF_END")

        self._gen_cond_branch(stmt.cond, true_label, false_label)

        self._emit(f"{true_label}:")
        for s in stmt.then_stmts:
            self._gen_stmt(s)
        self._emit(f"j {end_label}")

        self._emit(f"{false_label}:")
        for s in stmt.else_stmts:
            self._gen_stmt(s)

        self._emit(f"{end_label}:")


# combined compiler
def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    quantum_ops, classical_body = _extract_classical_block(hybrid_qasm_str)

    tokens = _tokenise(classical_body)
    parser = Parser(tokens)
    ast_stmts = parser.parse_program()

    codegen = CodeGen()
    asm_text = codegen.gen_program(ast_stmts)

    return quantum_ops, asm_text