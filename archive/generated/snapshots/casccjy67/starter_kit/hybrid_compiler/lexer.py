"""Lexer for Hybrid-QASM classical blocks."""
from enum import Enum, auto
from dataclasses import dataclass


class TokenType(Enum):
    NUMBER = auto()
    REGISTER = auto()      # r1..r9
    CLBIT = auto()         # c[0], c[1]...
    PLUS = auto()
    MINUS = auto()
    DIVIDE = auto()        # /
    EQ = auto()            # ==
    NEQ = auto()           # !=
    ASSIGN = auto()        # =
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    IF = auto()
    ELSE = auto()
    CLASSICAL = auto()
    QASM_HEADER = auto()
    INCLUDE = auto()
    QREG = auto()
    CREG = auto()
    GATE = auto()
    MEASURE = auto()
    COMMA = auto()
    SEMICOLON = auto()
    ARROW = auto()         # ->
    IDENT = auto()
    EOF = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type.name}, '{self.value}')"


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens = []

    def tokenize(self) -> list:
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch in " \t\r":
                self._advance()
                continue
            if ch == "\n":
                self.line += 1
                self.col = 1
                self.pos += 1
                continue
            if ch == "/" and self._peek(1) == "/":
                self._skip_comment()
                continue
            if ch.isalpha() or ch == "_":
                self._read_identifier()
                continue
            if ch.isdigit():
                self._read_number()
                continue
            if ch == '"':
                self._read_string()
                continue
            if ch == "-" and self._peek(1) == ">":
                self._add_token(TokenType.ARROW, "->")
                continue
            self._read_symbol(ch)
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.col))
        return self.tokens

    def _advance(self, n=1):
        self.pos += n
        self.col += n

    def _peek(self, offset=0):
        idx = self.pos + offset
        return self.source[idx] if idx < len(self.source) else "\0"

    def _skip_comment(self):
        while self.pos < len(self.source) and self.source[self.pos] != "\n":
            self._advance()

    def _read_string(self):
        self._advance()  # skip opening quote
        start = self.pos
        while self.pos < len(self.source) and self.source[self.pos] != '"':
            self._advance()
        value = self.source[start:self.pos]
        self.tokens.append(Token(TokenType.IDENT, value, self.line, self.col))
        if self.pos < len(self.source):
            self._advance()  # skip closing quote

    def _add_token(self, ttype, value):
        self.tokens.append(Token(ttype, value, self.line, self.col))
        self._advance(len(value))

    def _read_identifier(self):
        start = self.pos
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == "_"):
            self._advance()
        word = self.source[start:self.pos]
        lower = word.lower()
        keywords = {
            "openqasm": TokenType.QASM_HEADER,
            "include": TokenType.INCLUDE,
            "qreg": TokenType.QREG,
            "creg": TokenType.CREG,
            "measure": TokenType.MEASURE,
            "classical": TokenType.CLASSICAL,
            "if": TokenType.IF,
            "else": TokenType.ELSE,
        }
        if lower in keywords:
            self.tokens.append(Token(keywords[lower], word, self.line, self.col - len(word)))
        elif len(word) >= 2 and word[0] in "rR" and word[1:].isdigit():
            reg_num = int(word[1:])
            if 1 <= reg_num <= 9:
                self.tokens.append(Token(TokenType.REGISTER, word, self.line, self.col - len(word)))
            else:
                self.tokens.append(Token(TokenType.IDENT, word, self.line, self.col - len(word)))
        else:
            self.tokens.append(Token(TokenType.IDENT, word, self.line, self.col - len(word)))

    def _read_number(self):
        start = self.pos
        while self.pos < len(self.source) and (self.source[self.pos].isdigit() or self.source[self.pos] == "."):
            self._advance()
        self.tokens.append(Token(TokenType.NUMBER, self.source[start:self.pos], self.line, self.col - (self.pos - start)))

    def _read_symbol(self, ch):
        two = ch + self._peek(1)
        two_char = {
            "==": TokenType.EQ, "!=": TokenType.NEQ, "->": TokenType.ARROW,
        }
        one_char = {
            "+": TokenType.PLUS, "-": TokenType.MINUS, "=": TokenType.ASSIGN,
            "(": TokenType.LPAREN, ")": TokenType.RPAREN,
            "{": TokenType.LBRACE, "}": TokenType.RBRACE,
            "[": TokenType.LBRACKET, "]": TokenType.RBRACKET,
            ",": TokenType.COMMA, ";": TokenType.SEMICOLON,
            "/": TokenType.DIVIDE,
        }
        if two in two_char:
            self._add_token(two_char[two], two)
        elif ch in one_char:
            self._add_token(one_char[ch], ch)
        else:
            raise SyntaxError(f"Unexpected character '{ch}' at line {self.line}, col {self.col}")
