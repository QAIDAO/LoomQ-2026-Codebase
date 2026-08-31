"""classical 块文法 → AST。

文法：stmt := assign | if ；assign := rN '=' expr ';' ；
if := 'if' '(' expr ('=='|'!=') expr ')' block ('else' (block|if))?；
expr := term (('+'|'-') term)* ；term := NUM | rN | c[k]；
支持一元负号（折叠进常量）。寄存器 r1..r9，测量位 c[0..]。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Union

_TOKEN = re.compile(r"\s*(==|!=|[-+={}()\[\];]|[A-Za-z_][A-Za-z0-9_]*|\d+)")


def tokenize(text: str) -> List[str]:
    tokens, pos = [], 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        if text.startswith("//", pos) or text[pos] == "#":  # 行注释
            nl = text.find("\n", pos)
            pos = len(text) if nl < 0 else nl + 1
            continue
        match = _TOKEN.match(text, pos)
        if not match:
            raise SyntaxError("classical 无法识别的字符 %r（偏移 %d）" % (text[pos], pos))
        tokens.append(match.group(1))
        pos = match.end()
    return tokens


@dataclass(frozen=True)
class Num:
    value: int


@dataclass(frozen=True)
class RReg:
    n: int  # 1..9


@dataclass(frozen=True)
class CBit:
    k: int  # 测量位下标


@dataclass(frozen=True)
class Bin:
    op: str  # '+' | '-'
    lhs: object
    rhs: object


@dataclass(frozen=True)
class Cond:
    op: str  # '==' | '!='
    lhs: object
    rhs: object


@dataclass(frozen=True)
class Assign:
    target: int  # r 寄存器号
    expr: object


@dataclass(frozen=True)
class If:
    cond: Cond
    then_body: List[object] = field(default_factory=list)
    else_body: List[object] = field(default_factory=list)


class _Parser:
    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Optional[str]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next(self) -> str:
        token = self.peek()
        if token is None:
            raise SyntaxError("classical 语句意外结束")
        self.pos += 1
        return token

    def expect(self, token: str) -> None:
        got = self.next()
        if got != token:
            raise SyntaxError("期望 %r，得到 %r" % (token, got))

    def program(self) -> List[object]:
        stmts = []
        while self.peek() is not None:
            stmts.append(self.statement())
        return stmts

    def statement(self) -> object:
        token = self.peek()
        if token == "if":
            return self.if_statement()
        if token is not None and re.fullmatch(r"r[1-9]", token):
            self.pos += 1
            self.expect("=")
            expr = self.expr()
            self.expect(";")
            return Assign(int(token[1]), expr)
        raise SyntaxError("期望语句（rN=... 或 if），得到 %r" % token)

    def if_statement(self) -> If:
        self.expect("if")
        self.expect("(")
        lhs = self.expr()
        op = self.next()
        if op not in ("==", "!="):
            raise SyntaxError("条件只支持 == / !=，得到 %r" % op)
        rhs = self.expr()
        self.expect(")")
        then_body = self.block()
        else_body: List[object] = []
        if self.peek() == "else":
            self.next()
            if self.peek() == "if":
                else_body = [self.if_statement()]
            else:
                else_body = self.block()
        return If(Cond(op, lhs, rhs), then_body, else_body)

    def block(self) -> List[object]:
        self.expect("{")
        stmts = []
        while self.peek() is not None and self.peek() != "}":
            stmts.append(self.statement())
        self.expect("}")
        return stmts

    def expr(self) -> object:
        value = self.term()
        while self.peek() in ("+", "-"):
            op = self.next()
            rhs = self.term()
            value = Bin(op, value, rhs)
        return value

    def term(self) -> object:
        token = self.peek()
        if token == "-":
            self.next()
            inner = self.term()
            if isinstance(inner, Num):
                return Num(-inner.value)
            return Bin("-", Num(0), inner)
        if token is not None and token.isdigit():
            self.next()
            return Num(int(token))
        if token is not None and re.fullmatch(r"r[1-9]", token):
            self.next()
            return RReg(int(token[1]))
        if token == "(":
            self.next()
            value = self.expr()
            self.expect(")")
            return value
        if token == "c":
            self.next()
            self.expect("[")
            index = self.next()
            if not index.isdigit():
                raise SyntaxError("c[k] 下标应为整数")
            self.expect("]")
            return CBit(int(index))
        raise SyntaxError("期望数字/rN/c[k]，得到 %r" % token)


def parse_classical(text: str) -> List[object]:
    """classical 块文本 → 语句列表（AST）。"""
    return _Parser(tokenize(text)).program()
