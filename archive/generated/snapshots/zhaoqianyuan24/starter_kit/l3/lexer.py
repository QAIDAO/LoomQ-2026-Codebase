from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int


class LexerError(ValueError):
    pass


class Lexer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1

    def _peek(self, offset: int = 0) -> str:
        index = self.pos + offset

        if index >= len(self.text):
            return ""

        return self.text[index]

    def _advance(self) -> str:
        ch = self._peek()

        if not ch:
            return ""

        self.pos += 1

        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1

        return ch

    def _error(self, message: str):
        raise LexerError(
            f"{message} at line {self.line}, "
            f"column {self.column}"
        )

    def tokenize(self) -> List[Token]:
        tokens = []

        while self.pos < len(self.text):

            ch = self._peek()

            # ------------------------------------------------
            # Whitespace
            # ------------------------------------------------

            if ch.isspace():
                self._advance()
                continue

            # ------------------------------------------------
            # // comment
            # ------------------------------------------------

            if ch == "/" and self._peek(1) == "/":

                while self._peek() not in {
                    "",
                    "\n",
                }:
                    self._advance()

                continue

            line = self.line
            column = self.column

            # ------------------------------------------------
            # Two-character operators
            # ------------------------------------------------

            if (
                ch == "="
                and self._peek(1) == "="
            ):
                self._advance()
                self._advance()

                tokens.append(
                    Token(
                        "EQ",
                        "==",
                        line,
                        column,
                    )
                )
                continue

            if (
                ch == "!"
                and self._peek(1) == "="
            ):
                self._advance()
                self._advance()

                tokens.append(
                    Token(
                        "NE",
                        "!=",
                        line,
                        column,
                    )
                )
                continue

            # ------------------------------------------------
            # Single-character tokens
            # ------------------------------------------------

            single = {
                "=": "ASSIGN",
                "+": "PLUS",
                "-": "MINUS",
                "(": "LPAREN",
                ")": "RPAREN",
                "{": "LBRACE",
                "}": "RBRACE",
                ";": "SEMI",
            }

            if ch in single:
                self._advance()

                tokens.append(
                    Token(
                        single[ch],
                        ch,
                        line,
                        column,
                    )
                )
                continue

            # ------------------------------------------------
            # Integer literal
            # ------------------------------------------------

            if ch.isdigit():

                start = self.pos

                while self._peek().isdigit():
                    self._advance()

                value = self.text[
                    start:self.pos
                ]

                tokens.append(
                    Token(
                        "INT",
                        value,
                        line,
                        column,
                    )
                )
                continue

            # ------------------------------------------------
            # c[k] measurement reference
            # ------------------------------------------------

            if (
                ch == "c"
                and self._peek(1) == "["
            ):
                self._advance()
                self._advance()

                start = self.pos

                while self._peek().isdigit():
                    self._advance()

                if start == self.pos:
                    self._error(
                        "Expected measurement index"
                    )

                index = self.text[
                    start:self.pos
                ]

                if self._peek() != "]":
                    self._error(
                        "Expected ']' after "
                        "measurement index"
                    )

                self._advance()

                tokens.append(
                    Token(
                        "CREF",
                        index,
                        line,
                        column,
                    )
                )
                continue

            # ------------------------------------------------
            # Identifier / r1..r9
            # ------------------------------------------------

            if (
                ch.isalpha()
                or ch == "_"
            ):

                start = self.pos

                while (
                    self._peek().isalnum()
                    or self._peek() == "_"
                ):
                    self._advance()

                value = self.text[
                    start:self.pos
                ]

                keyword_map = {
                    "classical": "CLASSICAL",
                    "if": "IF",
                    "else": "ELSE",
                }

                if value in keyword_map:
                    kind = keyword_map[value]

                elif (
                    len(value) == 2
                    and value[0] == "r"
                    and value[1] in "123456789"
                ):
                    kind = "REG"

                else:
                    self._error(
                        f"Unknown identifier '{value}'"
                    )

                tokens.append(
                    Token(
                        kind,
                        value,
                        line,
                        column,
                    )
                )
                continue

            self._error(
                f"Unexpected character '{ch}'"
            )

        tokens.append(
            Token(
                "EOF",
                "",
                self.line,
                self.column,
            )
        )

        return tokens
