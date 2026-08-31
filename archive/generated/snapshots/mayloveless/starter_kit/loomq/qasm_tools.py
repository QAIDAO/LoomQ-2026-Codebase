"""Utilities for extracting and validating generated OpenQASM 2.0."""

from __future__ import annotations

import re

from .ir import MeasureOperation
from .parser import parse_qasm


_QASM_HEADER = "OPENQASM 2.0;"
_FENCED_BLOCK_RE = re.compile(
    r"```(?P<language>[^`\n]*)\n(?P<body>.*?)```",
    re.DOTALL,
)
_ABSOLUTE_PATH_RE = re.compile(r"(?:[A-Za-z]:\\|/)[^\s\"')]+")
_ENVIRONMENT_NAME_RE = re.compile(r"\bLOOMQ_[A-Z0-9_]+\b")
_MAX_DIAGNOSTIC_LENGTH = 400


class QASMValidationError(RuntimeError):
    """Stable L2 validation failure carrying a safe repair diagnostic."""

    def __init__(self, diagnostic: str) -> None:
        super().__init__("generated QASM failed OpenQASM 2.0 validation")
        self.diagnostic = diagnostic


def _clean_parser_error(error: Exception) -> str:
    """Keep only bounded parser details that are safe to send back to the model."""
    message = str(error).split(" (statement:", 1)[0]
    message = " ".join(message.split())
    message = _ABSOLUTE_PATH_RE.sub("<path>", message)
    message = _ENVIRONMENT_NAME_RE.sub("<environment-variable>", message)
    message = re.sub(r"(?i)authorization\s*:\s*bearer\s+\S+", "<credential>", message)
    diagnostic = "%s: %s" % (type(error).__name__, message)
    return diagnostic[:_MAX_DIAGNOSTIC_LENGTH]


def extract_qasm(text: str) -> str | None:
    """Extract one unambiguous plain or fenced OpenQASM 2.0 program."""
    if not isinstance(text, str):
        return None

    fenced_candidates = []
    fenced_header_count = 0
    for match in _FENCED_BLOCK_RE.finditer(text):
        language = match.group("language").strip().lower()
        if language not in ("", "qasm", "openqasm"):
            continue
        body = match.group("body")
        header_count = body.count(_QASM_HEADER)
        if header_count:
            fenced_header_count += header_count
            candidate = body[body.index(_QASM_HEADER) :].strip()
            fenced_candidates.append(candidate)

    total_header_count = text.count(_QASM_HEADER)
    if fenced_candidates:
        # 多个相同代码块可归一为一个；互相冲突或块内多程序均拒绝。
        unique_candidates = set(fenced_candidates)
        if (
            len(unique_candidates) != 1
            or fenced_header_count != total_header_count
            or next(iter(unique_candidates)).count(_QASM_HEADER) != 1
        ):
            return None
        return next(iter(unique_candidates))

    if total_header_count != 1:
        return None
    # 纯文本允许头部之前有简短说明；Parser 负责判断后续是否为完整程序。
    return text[text.index(_QASM_HEADER) :].strip()


def validate_qasm(qasm: str, *, require_measurement: bool = False) -> None:
    """Validate QASM and optionally enforce the L2 measurement contract."""
    try:
        circuit = parse_qasm(qasm)
    except (TypeError, ValueError) as exc:
        # 不把完整模型输出带入异常，防止响应内容意外泄露。
        raise QASMValidationError(_clean_parser_error(exc)) from None

    if not circuit.quantum_registers:
        raise QASMValidationError("QASMValidationError: missing quantum register")
    if require_measurement:
        if not circuit.classical_registers:
            raise QASMValidationError(
                "QASMValidationError: measurement requires a classical register"
            )
        if not any(
            isinstance(operation, MeasureOperation) for operation in circuit.operations
        ):
            raise QASMValidationError("QASMValidationError: circuit has no measurement")


__all__ = ["QASMValidationError", "extract_qasm", "validate_qasm"]
