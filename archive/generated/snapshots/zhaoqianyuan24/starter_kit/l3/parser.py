import re
from typing import List

from .ast import (
    Assign,
    BinaryOp,
    ClassicalBlock,
    Expr,
    IfStmt,
    IntLiteral,
    MeasurementRef,
    RegisterRef,
    Stmt,
    UnaryOp,
)

from .lexer import (
    Lexer,
    Token,
)


class ParserError(ValueError):
    pass


# ============================================================
# Classical-block extraction
# ============================================================


def extract_classical_source(
    hybrid_qasm: str,
) -> str:

    if not isinstance(hybrid_qasm, str):
        raise TypeError(
            "hybrid_qasm must be a string"
        )

    match = re.search(
        r"\bclassical\s*\{",
        hybrid_qasm,
    )

    if match is None:
        raise ParserError(
            "Hybrid-QASM contains no "
            "classical block."
        )

    start = match.start()

    brace_start = hybrid_qasm.find(
        "{",
        match.start(),
        match.end(),
    )

    depth = 0
    i = brace_start

    in_string = False

    while i < len(hybrid_qasm):

        ch = hybrid_qasm[i]

        # --------------------------------------------
        # Quoted strings
        # --------------------------------------------

        if ch == '"':
            in_string = not in_string
            i += 1
            continue

        if in_string:
            i += 1
            continue

        # --------------------------------------------
        # // comments
        # --------------------------------------------

        if (
            ch == "/"
            and i + 1 < len(hybrid_qasm)
            and hybrid_qasm[i + 1] == "/"
        ):
            newline = hybrid_qasm.find(
                "\n",
                i + 2,
            )

            if newline == -1:
                i = len(hybrid_qasm)
            else:
                i = newline + 1

            continue

        # --------------------------------------------
        # Brace matching
        # --------------------------------------------

        if ch == "{":
            depth += 1

        elif ch == "}":
            depth -= 1

            if depth == 0:
                return hybrid_qasm[
                    start:i + 1
                ]

        i += 1

    raise ParserError(
        "Unterminated classical block."
    )


# ============================================================
# Recursive-descent parser
# ============================================================


class Parser:
    def __init__(
        self,
        tokens: List[Token],
    ):
        self.tokens = tokens
        self.pos = 0

    def _current(self) -> Token:
        return self.tokens[self.pos]

    def _match(
        self,
        *kinds: str,
    ):
        token = self._current()

        if token.kind in kinds:
            self.pos += 1
            return token

        return None

    def _expect(
        self,
        kind: str,
    ) -> Token:

        token = self._current()

        if token.kind != kind:
            raise ParserError(
                f"Expected {kind}, "
                f"got {token.kind} "
                f"('{token.value}') "
                f"at line {token.line}, "
                f"column {token.column}"
            )

        self.pos += 1

        return token

    # ========================================================
    # Entry point
    # ========================================================

    def parse(self) -> ClassicalBlock:

        self._expect(
            "CLASSICAL"
        )

        statements = (
            self._parse_block()
        )

        self._expect(
            "EOF"
        )

        return ClassicalBlock(
            statements=statements
        )

    # ========================================================
    # block := "{" statement* "}"
    # ========================================================

    def _parse_block(
        self,
    ) -> List[Stmt]:

        self._expect(
            "LBRACE"
        )

        statements = []

        while (
            self._current().kind
            != "RBRACE"
        ):

            if (
                self._current().kind
                == "EOF"
            ):
                token = self._current()

                raise ParserError(
                    "Unexpected end of input "
                    f"at line {token.line}, "
                    f"column {token.column}"
                )

            statements.append(
                self._parse_statement()
            )

        self._expect(
            "RBRACE"
        )

        return statements

    # ========================================================
    # statement := assignment | if-statement
    # ========================================================

    def _parse_statement(
        self,
    ) -> Stmt:

        kind = self._current().kind

        if kind == "REG":
            return (
                self._parse_assignment()
            )

        if kind == "IF":
            return (
                self._parse_if()
            )

        token = self._current()

        raise ParserError(
            f"Unexpected token "
            f"{token.kind} "
            f"('{token.value}') "
            f"at line {token.line}, "
            f"column {token.column}"
        )

    # ========================================================
    # assignment :=
    #     REG "=" expr ";"
    # ========================================================

    def _parse_assignment(
        self,
    ) -> Assign:

        target = self._expect(
            "REG"
        )

        self._expect(
            "ASSIGN"
        )

        value = self._parse_expr()

        self._expect(
            "SEMI"
        )

        return Assign(
            target=int(
                target.value[1:]
            ),
            value=value,
        )

    # ========================================================
    # if :=
    #     "if" "(" condition ")" block
    #     ("else" block)?
    # ========================================================

    def _parse_if(
        self,
    ) -> IfStmt:

        self._expect(
            "IF"
        )

        self._expect(
            "LPAREN"
        )

        condition = (
            self._parse_condition()
        )

        self._expect(
            "RPAREN"
        )

        then_body = (
            self._parse_block()
        )

        else_body = None

        if self._match(
            "ELSE"
        ):
            else_body = (
                self._parse_block()
            )

        return IfStmt(
            condition=condition,
            then_body=then_body,
            else_body=else_body,
        )

    # ========================================================
    # condition :=
    #     expr ("==" | "!=") expr
    # ========================================================

    def _parse_condition(
        self,
    ) -> BinaryOp:

        left = self._parse_expr()

        operator = self._current()

        if operator.kind not in {
            "EQ",
            "NE",
        }:
            raise ParserError(
                "Condition requires "
                "'==' or '!=' "
                f"at line {operator.line}, "
                f"column {operator.column}"
            )

        self.pos += 1

        right = self._parse_expr()

        return BinaryOp(
            left=left,
            op=operator.value,
            right=right,
        )

    # ========================================================
    # expr :=
    #     unary (("+" | "-") unary)*
    # ========================================================

    def _parse_expr(
        self,
    ) -> Expr:

        expr = self._parse_unary()

        while (
            self._current().kind
            in {
                "PLUS",
                "MINUS",
            }
        ):

            operator = self._current()
            self.pos += 1

            right = (
                self._parse_unary()
            )

            expr = BinaryOp(
                left=expr,
                op=operator.value,
                right=right,
            )

        return expr

    # ========================================================
    # unary := "-" unary | primary
    # ========================================================

    def _parse_unary(
        self,
    ) -> Expr:

        if self._match(
            "MINUS"
        ):
            return UnaryOp(
                op="-",
                operand=(
                    self._parse_unary()
                ),
            )

        return self._parse_primary()

    # ========================================================
    # primary :=
    #     INT
    #     | REG
    #     | CREF
    #     | "(" expr ")"
    # ========================================================

    def _parse_primary(
        self,
    ) -> Expr:

        token = self._current()

        if token.kind == "INT":
            self.pos += 1

            return IntLiteral(
                int(token.value)
            )

        if token.kind == "REG":
            self.pos += 1

            return RegisterRef(
                int(token.value[1:])
            )

        if token.kind == "CREF":
            self.pos += 1

            return MeasurementRef(
                int(token.value)
            )

        if token.kind == "LPAREN":

            self.pos += 1

            expr = self._parse_expr()

            self._expect(
                "RPAREN"
            )

            return expr

        raise ParserError(
            f"Expected expression, "
            f"got {token.kind} "
            f"('{token.value}') "
            f"at line {token.line}, "
            f"column {token.column}"
        )


def parse_classical_block(
    hybrid_qasm: str,
) -> ClassicalBlock:

    classical_source = (
        extract_classical_source(
            hybrid_qasm
        )
    )

    tokens = Lexer(
        classical_source
    ).tokenize()

    return Parser(
        tokens
    ).parse()
