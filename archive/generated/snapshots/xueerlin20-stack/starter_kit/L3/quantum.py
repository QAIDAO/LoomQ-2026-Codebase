"""Hybrid-QASM container parsing and ordered quantum-operation extraction."""

from __future__ import annotations

import re
from typing import List, Tuple

from .errors import HybridCompileError, HybridSyntaxError
from .nodes import HybridProgram
from .parser import parse_classical_block


_CREG_C = re.compile(r"^creg\s+c\[(\d+)\]$", re.IGNORECASE)


def parse_hybrid_program(source: str) -> HybridProgram:
    if not isinstance(source, str) or not source.strip():
        raise HybridCompileError("Hybrid-QASM source must be a non-empty string")

    without_comments = _mask_line_comments(source)
    keywords = _find_keywords(without_comments, "classical")
    if len(keywords) != 1:
        raise HybridSyntaxError(
            "Hybrid-QASM must contain exactly one classical block; found %d"
            % len(keywords)
        )

    keyword_start, keyword_end = keywords[0]
    opening = keyword_end
    while opening < len(without_comments) and without_comments[opening].isspace():
        opening += 1
    if opening >= len(without_comments) or without_comments[opening] != "{":
        raise HybridSyntaxError("classical must be followed by a braced block")
    closing = _matching_brace(without_comments, opening)

    classical_source = source[opening + 1 : closing]
    replacement = "".join(
        "\n" if char == "\n" else " " for char in source[keyword_start : closing + 1]
    )
    quantum_source = source[:keyword_start] + replacement + source[closing + 1 :]
    statements = _split_semicolon_statements(_mask_line_comments(quantum_source))

    metadata: List[str] = []
    operations: List[str] = []
    classical_bit_counts: List[int] = []
    has_version = False
    for statement in statements:
        normalized = _normalize_statement(statement)
        lowered = normalized.lower()
        if lowered.startswith("openqasm "):
            has_version = lowered == "openqasm 2.0"
            metadata.append(normalized + ";")
        elif lowered.startswith("include ") or lowered.startswith("qreg "):
            metadata.append(normalized + ";")
        elif lowered.startswith("creg "):
            metadata.append(normalized + ";")
            match = _CREG_C.fullmatch(normalized)
            if match:
                classical_bit_counts.append(int(match.group(1)))
        else:
            operations.append(normalized + ";")

    if not has_version:
        raise HybridSyntaxError("Hybrid-QASM must declare OPENQASM 2.0")
    if len(classical_bit_counts) != 1 or classical_bit_counts[0] <= 0:
        raise HybridSyntaxError("Hybrid-QASM must declare exactly one positive creg c[N]")
    if not operations:
        raise HybridSyntaxError("Hybrid-QASM contains no quantum operations")

    _validate_quantum_program(metadata, operations)
    classical_bit_count = classical_bit_counts[0]
    classical_statements = parse_classical_block(
        classical_source, classical_bit_count
    )
    return HybridProgram(
        tuple(operations), classical_statements, classical_bit_count
    )


def _mask_line_comments(source: str) -> str:
    output = list(source)
    index = 0
    quote: str | None = None
    while index < len(source):
        char = source[index]
        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
            index += 1
            continue
        if source.startswith("//", index):
            while index < len(source) and source[index] != "\n":
                output[index] = " "
                index += 1
            continue
        index += 1
    return "".join(output)


def _find_keywords(source: str, keyword: str) -> List[Tuple[int, int]]:
    matches: List[Tuple[int, int]] = []
    index = 0
    quote: str | None = None
    while index < len(source):
        char = source[index]
        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
            index += 1
            continue
        if char.isalpha() or char == "_":
            end = index + 1
            while end < len(source) and (
                source[end].isalnum() or source[end] == "_"
            ):
                end += 1
            if source[index:end] == keyword:
                matches.append((index, end))
            index = end
            continue
        index += 1
    return matches


def _matching_brace(source: str, opening: int) -> int:
    depth = 0
    quote: str | None = None
    for index in range(opening, len(source)):
        char = source[index]
        if quote is not None:
            if char == quote and (index == 0 or source[index - 1] != "\\"):
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    raise HybridSyntaxError("unterminated classical block")


def _split_semicolon_statements(source: str) -> List[str]:
    statements: List[str] = []
    start = 0
    quote: str | None = None
    for index, char in enumerate(source):
        if quote is not None:
            if char == quote and (index == 0 or source[index - 1] != "\\"):
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == ";":
            statement = source[start:index].strip()
            if statement:
                statements.append(statement)
            start = index + 1
    remainder = source[start:].strip()
    if remainder:
        raise HybridSyntaxError("quantum statement is missing a terminating semicolon")
    return statements


def _normalize_statement(statement: str) -> str:
    return re.sub(r"\s+", " ", statement).strip()


def _validate_quantum_program(metadata: List[str], operations: List[str]) -> None:
    validation_source = "\n".join(metadata + operations) + "\n"
    try:
        try:
            from ..qasm_L1.parser import parse_qasm
        except ImportError:
            from qasm_L1.parser import parse_qasm
        parse_qasm(validation_source)
    except (SyntaxError, TypeError, ValueError) as exc:
        raise HybridSyntaxError("invalid quantum portion: %s" % exc) from exc

