"""Encoder for LoomQ 32-bit custom quantum instruction words."""

from __future__ import annotations

import re
from typing import Iterable, Sequence, Tuple

from .decoder import decode_word
from .isa import (
    ANGLE_UNITS_MAX,
    ANGLE_UNITS_MIN,
    CUSTOM_0_OPCODE,
    CUSTOM_1_OPCODE,
    MAX_ENCODED_QUBITS,
    QUANTUM_FUNCT3,
    SPECS_BY_MNEMONIC,
)


_REGISTER = re.compile(r"x(\d+)$", re.I)


def encode_instruction(mnemonic: str, operands: Sequence[int]) -> int:
    """Encode one QPARAM or custom-0 quantum instruction."""
    normalized = mnemonic.strip().lower()
    values = tuple(operands)
    if normalized == "qparam":
        if len(values) != 1:
            raise ValueError("QPARAM expects one fixed-point angle operand")
        units = _integer(values[0], "angle units")
        if not ANGLE_UNITS_MIN <= units <= ANGLE_UNITS_MAX:
            raise ValueError("QPARAM angle units are outside signed 12-bit range")
        word = ((units & 0xFFF) << 20) | CUSTOM_1_OPCODE
        decode_word(word)
        return word

    spec = SPECS_BY_MNEMONIC.get(normalized)
    if spec is None:
        raise ValueError(f"Unsupported quantum instruction: {mnemonic}")
    if len(values) != len(spec.operands):
        raise ValueError(f"{normalized.upper()} expects {len(spec.operands)} operands")
    checked = tuple(_field(value, name) for value, name in zip(values, spec.operands))

    rd = rs1 = rs2 = 0
    if normalized == "qinit":
        rd = checked[0]
        if rd == 0:
            raise ValueError("QINIT qubit count must be positive")
    elif normalized == "qccx":
        rs1, rs2, rd = checked
        if len({rd, rs1, rs2}) != 3:
            raise ValueError("QCCX requires three distinct qubits")
    elif normalized == "qmeasure":
        rs1, rd = checked
        if rd == 0:
            raise ValueError("QMEASURE destination cannot be x0")
    elif len(checked) == 2:
        rs1, rs2 = checked
        if rs1 == rs2:
            raise ValueError(f"{normalized.upper()} requires distinct qubits")
    else:
        rs1 = checked[0]

    word = (
        (spec.function << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (QUANTUM_FUNCT3 << 12)
        | (rd << 7)
        | CUSTOM_0_OPCODE
    )
    decode_word(word)
    return word


def encode_assembly(source: str) -> Tuple[int, ...]:
    """Encode newline-delimited quantum extension assembly."""
    words = []
    for raw_line in source.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        tokens = line.replace(",", " ").split()
        mnemonic = tokens[0]
        values = []
        for index, token in enumerate(tokens[1:]):
            match = _REGISTER.fullmatch(token)
            if match:
                values.append(int(match.group(1)))
            else:
                try:
                    values.append(int(token, 0))
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid operand {index + 1} for {mnemonic}: {token}"
                    ) from exc
        words.append(encode_instruction(mnemonic, values))
    return tuple(words)


def machine_hex(words: Iterable[int]) -> Tuple[str, ...]:
    """Render machine words in fixed-width hexadecimal notation."""
    return tuple(f"0x{word:08x}" for word in words)


def _integer(value: int, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Quantum {label} must be an integer")
    return value


def _field(value: int, label: str) -> int:
    checked = _integer(value, label)
    if not 0 <= checked <= MAX_ENCODED_QUBITS:
        raise ValueError(f"Quantum {label} is outside the 5-bit field")
    return checked
