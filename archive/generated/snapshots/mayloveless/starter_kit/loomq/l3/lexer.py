"""Hybrid-QASM lexer，保留足够位置信息用于确定性报错。"""

import re
from dataclasses import dataclass
from typing import List


class HybridQASMError(ValueError):
    """输入不符合 Hybrid-QASM 文法或目标机器约束。"""


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int


_NUMBER_RE = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def tokenize(source: str) -> List[Token]:
    """将源代码切分为 token，并忽略行注释及块注释。"""
    if not isinstance(source, str):
        raise TypeError("Hybrid-QASM source must be a string")

    tokens: List[Token] = []
    index = 0
    line = 1
    column = 1
    length = len(source)

    def advance(text: str) -> None:
        nonlocal line, column
        newline_count = text.count("\n")
        if newline_count:
            line += newline_count
            column = len(text.rsplit("\n", 1)[-1]) + 1
        else:
            column += len(text)

    while index < length:
        char = source[index]
        if char.isspace():
            advance(char)
            index += 1
            continue

        if source.startswith("//", index):
            end = source.find("\n", index)
            end = length if end < 0 else end
            advance(source[index:end])
            index = end
            continue

        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            if end < 0:
                raise HybridQASMError(
                    "line %d, column %d: unterminated block comment" % (line, column)
                )
            text = source[index : end + 2]
            advance(text)
            index = end + 2
            continue

        token_line, token_column = line, column
        if char.isalpha() or char == "_":
            end = index + 1
            while end < length and (source[end].isalnum() or source[end] == "_"):
                end += 1
            value = source[index:end]
            tokens.append(Token("IDENT", value, token_line, token_column))
            advance(value)
            index = end
            continue

        if char.isdigit() or (
            char == "." and index + 1 < length and source[index + 1].isdigit()
        ):
            # 量子门参数允许小数和科学计数法；经典文法仍只接受 INTEGER。
            match = _NUMBER_RE.match(source, index)
            assert match is not None
            end = match.end()
            value = source[index:end]
            kind = "INTEGER" if value.isdigit() else "NUMBER"
            tokens.append(Token(kind, value, token_line, token_column))
            advance(value)
            index = end
            continue

        if char == '"':
            end = index + 1
            escaped = False
            terminated = False
            while end < length:
                current = source[end]
                if current == "\n":
                    break
                if current == '"' and not escaped:
                    end += 1
                    terminated = True
                    break
                escaped = current == "\\" and not escaped
                if current != "\\":
                    escaped = False
                end += 1
            if not terminated:
                raise HybridQASMError(
                    "line %d, column %d: unterminated string literal"
                    % (token_line, token_column)
                )
            value = source[index:end]
            tokens.append(Token("STRING", value, token_line, token_column))
            advance(value)
            index = end
            continue

        pair = source[index : index + 2]
        if pair in ("==", "!=", "->"):
            tokens.append(Token("SYMBOL", pair, token_line, token_column))
            advance(pair)
            index += 2
            continue

        # 量子门参数可能包含经典子语言之外的标点，先作为普通符号保留。
        tokens.append(Token("SYMBOL", char, token_line, token_column))
        advance(char)
        index += 1

    tokens.append(Token("EOF", "", line, column))
    return tokens
