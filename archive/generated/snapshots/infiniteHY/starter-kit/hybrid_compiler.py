#!/usr/bin/env python3
"""LoomQ L3 — Hybrid-QASM 解析 + RISC-V 汇编生成器。"""
from __future__ import annotations
import re
from typing import List, Tuple

# ---- 量子部分提取 ----

def _strip_classical_blocks(text: str) -> str:
    result = []
    i = 0
    while i < len(text):
        m = re.search(r'\bclassical\s*\{', text[i:])
        if not m:
            result.append(text[i:]); break
        result.append(text[i: i + m.start()])
        start_brace = i + m.end() - 1
        depth, j = 1, start_brace + 1
        while j < len(text) and depth > 0:
            if text[j] == '{': depth += 1
            elif text[j] == '}': depth -= 1
            j += 1
        i = j
    return "".join(result)

def extract_quantum_ops(hybrid_qasm: str) -> List[str]:
    text = re.sub(r"//.*", "", hybrid_qasm)
    text = _strip_classical_blocks(text)
    ops = []
    skip = {"openqasm", "include", "qreg", "creg"}
    for statement in text.split(";"):
        line = statement.strip()
        if not line: continue
        if line.split()[0].lower().rstrip("(") in skip: continue
        ops.append(line + ";")
    return ops

# ---- AST 节点 ----

class ASTNode: pass
class AssignNode(ASTNode):
    def __init__(self, var, expr): self.var = var; self.expr = expr
class IfNode(ASTNode):
    def __init__(self, cond, then_body, else_body): self.cond = cond; self.then_body = then_body; self.else_body = else_body
class BinOp(ASTNode):
    def __init__(self, op, left, right): self.op = op; self.left = left; self.right = right
class VarNode(ASTNode):
    def __init__(self, name): self.name = name
class LiteralNode(ASTNode):
    def __init__(self, value): self.value = value
class MeasBitNode(ASTNode):
    def __init__(self, idx): self.idx = idx

# ---- Tokenizer ----

_TOKEN_RE = re.compile(
    r'\b(if|else|int)\b'
    r'|([cr]\d*\[\d+\])'
    r'|(\d+)'
    r'|(r[1-9])'
    r'|([=!]=|[+\-]|(?<![=!])=(?!=))'
    r'|([{}();,])'
)

def _tokenize(text: str) -> List[str]:
    return [m.group(0) for m in _TOKEN_RE.finditer(text)]

# ---- Parser ----

class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens; self.pos = 0
    def peek(self): return self.tokens[self.pos] if self.pos < len(self.tokens) else None
    def consume(self, expected=None):
        tok = self.tokens[self.pos]
        if expected is not None and tok != expected:
            raise SyntaxError(f"Expected {expected!r}, got {tok!r}")
        self.pos += 1; return tok
    def parse_body(self):
        stmts = []
        while self.peek() and self.peek() != "}":
            stmts.append(self.parse_stmt())
        return stmts
    def parse_stmt(self):
        if self.peek() == "if": return self.parse_if()
        var = self.consume(); self.consume("=")
        expr = self.parse_expr()
        if self.peek() == ";": self.consume(";")
        return AssignNode(var, expr)
    def parse_if(self):
        self.consume("if"); self.consume("(")
        cond = self.parse_cmp(); self.consume(")")
        self.consume("{"); then_body = self.parse_body(); self.consume("}")
        else_body = []
        if self.peek() == "else":
            self.consume("else"); self.consume("{")
            else_body = self.parse_body(); self.consume("}")
        return IfNode(cond, then_body, else_body)
    def parse_cmp(self):
        left = self.parse_expr()
        if self.peek() in ("==", "!="):
            op = self.consume(); right = self.parse_expr()
            return BinOp(op, left, right)
        return left
    def parse_expr(self):
        node = self.parse_atom()
        while self.peek() in ("+", "-"):
            op = self.consume(); right = self.parse_atom()
            node = BinOp(op, node, right)
        return node
    def parse_atom(self):
        tok = self.peek()
        if tok is None: raise SyntaxError("Unexpected end of input")
        if tok == "-":
            self.consume("-")
            value = self.consume()
            if not re.match(r'^\d+$', value):
                raise SyntaxError("Unary minus is only supported for integer literals")
            return LiteralNode(-int(value))
        m = re.match(r'c\[(\d+)\]', tok)
        if m: self.consume(); return MeasBitNode(int(m.group(1)))
        if re.match(r'^\d+$', tok): self.consume(); return LiteralNode(int(tok))
        if re.match(r'^r[1-9]$', tok): self.consume(); return VarNode(tok)
        raise SyntaxError(f"Unexpected token: {tok!r}")

def parse_classical_block(hybrid_qasm: str) -> List[ASTNode]:
    hybrid_qasm = re.sub(r"//.*", "", hybrid_qasm)
    m = re.search(r'\bclassical\s*\{', hybrid_qasm)
    if not m: return []
    start, depth, j = m.end() - 1, 1, m.end()
    while j < len(hybrid_qasm) and depth > 0:
        if hybrid_qasm[j] == '{': depth += 1
        elif hybrid_qasm[j] == '}': depth -= 1
        j += 1
    tokens = _tokenize(hybrid_qasm[start+1:j-1])
    return _Parser(tokens).parse_body()

# ---- RISC-V 代码生成 ----

_LABEL_COUNT = 0

def _new_label(prefix: str) -> str:
    global _LABEL_COUNT
    _LABEL_COUNT += 1
    return f"{prefix}_{_LABEL_COUNT}"

def _reg(var_name: str) -> str:
    m = re.match(r'^r([1-9])$', var_name)
    if m: return f"x{m.group(1)}"
    raise ValueError(f"Unknown variable: {var_name}")

class RISCVGen:
    def __init__(self): self.lines: List[str] = []
    def emit(self, instr): self.lines.append(instr)
    def gen_atom_into(self, node, dest):
        if isinstance(node, LiteralNode):
            self.emit(f"li {dest}, {node.value}")
        elif isinstance(node, VarNode):
            src = _reg(node.name)
            if src != dest: self.emit(f"addi {dest}, {src}, 0")
        elif isinstance(node, MeasBitNode):
            src = f"x{10 + node.idx}"
            if src != dest: self.emit(f"addi {dest}, {src}, 0")
        else:
            raise TypeError(f"Unsupported expression atom: {type(node).__name__}")
    def flatten_expr(self, node):
        if isinstance(node, BinOp) and node.op in ("+", "-"):
            return self.flatten_expr(node.left) + [(node.op, node.right)]
        return [(None, node)]
    def gen_expr_into(self, node, dest):
        terms = self.flatten_expr(node)
        self.gen_atom_into(terms[0][1], "x30")
        for op, term in terms[1:]:
            self.gen_atom_into(term, "x31")
            instr = "add" if op == "+" else "sub"
            self.emit(f"{instr} x30, x30, x31")
        if dest != "x30":
            self.emit(f"addi {dest}, x30, 0")
    def gen_cond_into(self, cond, true_label, false_label):
        if isinstance(cond, BinOp) and cond.op in ("==", "!="):
            self.gen_expr_into(cond.left, "x28")
            self.gen_expr_into(cond.right, "x29")
            if cond.op == "==":
                self.emit(f"beq x28, x29, {true_label}"); self.emit(f"j {false_label}")
            else:
                self.emit(f"bne x28, x29, {true_label}"); self.emit(f"j {false_label}")
        else:
            self.gen_expr_into(cond, "x28")
            self.emit(f"bne x28, x0, {true_label}"); self.emit(f"j {false_label}")
    def gen_stmts(self, stmts):
        for s in stmts: self.gen_stmt(s)
    def gen_stmt(self, stmt):
        if isinstance(stmt, AssignNode):
            self.gen_expr_into(stmt.expr, _reg(stmt.var))
        elif isinstance(stmt, IfNode):
            then_l = _new_label("THEN"); else_l = _new_label("ELSE"); end_l = _new_label("ENDIF")
            self.gen_cond_into(stmt.cond, then_l, else_l if stmt.else_body else end_l)
            self.emit(f"{then_l}:"); self.gen_stmts(stmt.then_body); self.emit(f"j {end_l}")
            if stmt.else_body:
                self.emit(f"{else_l}:"); self.gen_stmts(stmt.else_body)
            self.emit(f"{end_l}:")
    def get_asm(self): return "\n".join(self.lines)

def compile_hybrid_qasm(hybrid_qasm: str) -> Tuple[List[str], str]:
    global _LABEL_COUNT
    _LABEL_COUNT = 0
    quantum_ops = extract_quantum_ops(hybrid_qasm)
    ast = parse_classical_block(hybrid_qasm)
    gen = RISCVGen()
    gen.gen_stmts(ast)
    return quantum_ops, gen.get_asm()
