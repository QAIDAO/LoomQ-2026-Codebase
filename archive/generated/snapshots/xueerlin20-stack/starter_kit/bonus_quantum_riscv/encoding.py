"""32-bit instruction encoding for the LoomQ quantum RISC-V extension."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


CUSTOM_0_OPCODE = 0x0B
CUSTOM_1_OPCODE = 0x2B
ANGLE_SCALE = 1_000_000
WORD_MASK = 0xFFFFFFFF
_SIGNED_PARAMETER_BITS = 25
_SIGNED_PARAMETER_LIMIT = 1 << (_SIGNED_PARAMETER_BITS - 1)


class QuantumEncodingError(ValueError):
    """Raised when a custom instruction cannot be encoded or decoded."""


class GateCode(IntEnum):
    QINIT = 0
    X = 1
    H = 2
    S = 3
    SDG = 4
    T = 5
    TDG = 6
    RZ = 7
    RY = 8
    CX = 9
    CU1 = 10
    SWAP = 11
    CCX = 12
    MEASURE = 13


GATE_BY_QASM_NAME = {
    "x": GateCode.X,
    "h": GateCode.H,
    "s": GateCode.S,
    "sdg": GateCode.SDG,
    "t": GateCode.T,
    "tdg": GateCode.TDG,
    "rz": GateCode.RZ,
    "ry": GateCode.RY,
    "cx": GateCode.CX,
    "cu1": GateCode.CU1,
    "swap": GateCode.SWAP,
    "ccx": GateCode.CCX,
}

MNEMONIC_BY_GATE = {
    GateCode.QINIT: "qinit",
    GateCode.X: "qx",
    GateCode.H: "qh",
    GateCode.S: "qs",
    GateCode.SDG: "qsdg",
    GateCode.T: "qt",
    GateCode.TDG: "qtdg",
    GateCode.RZ: "qrz",
    GateCode.RY: "qry",
    GateCode.CX: "qcx",
    GateCode.CU1: "qcu1",
    GateCode.SWAP: "qswap",
    GateCode.CCX: "qccx",
    GateCode.MEASURE: "qmeasure",
}

GATE_BY_MNEMONIC = {value: key for key, value in MNEMONIC_BY_GATE.items()}

_SINGLE_QUBIT_GATES = {
    GateCode.X,
    GateCode.H,
    GateCode.S,
    GateCode.SDG,
    GateCode.T,
    GateCode.TDG,
    GateCode.RZ,
    GateCode.RY,
}
_TWO_QUBIT_GATES = {GateCode.CX, GateCode.CU1, GateCode.SWAP}
PARAMETER_GATES = {GateCode.RZ, GateCode.RY, GateCode.CU1}


@dataclass(frozen=True)
class DecodedInstruction:
    kind: str
    gate: Optional[GateCode] = None
    q0: int = 0
    q1: int = 0
    rd: int = 0
    angle: Optional[float] = None

    @property
    def mnemonic(self) -> str:
        if self.kind == "parameter":
            return "qparam"
        if self.gate is None:
            raise QuantumEncodingError("decoded gate instruction has no gate code")
        return MNEMONIC_BY_GATE[self.gate]


def encode_gate(
    gate: GateCode, q0: int = 0, q1: int = 0, rd: int = 0
) -> int:
    """Encode one Q-type instruction using the RISC-V custom-0 opcode."""
    try:
        gate = GateCode(gate)
    except ValueError as exc:
        raise QuantumEncodingError("unknown quantum gate code: %r" % gate) from exc

    _check_field("q0", q0)
    _check_field("q1", q1)
    _check_field("rd", rd)
    _validate_gate_operands(gate, q0, q1, rd)

    return (
        (int(gate) << 25)
        | (q1 << 20)
        | (q0 << 15)
        | (rd << 7)
        | CUSTOM_0_OPCODE
    ) & WORD_MASK


def encode_parameter(angle: float) -> int:
    """Encode a normalized radian angle as signed fixed-point custom-1."""
    try:
        angle = float(angle)
    except (TypeError, ValueError) as exc:
        raise QuantumEncodingError("quantum angle must be numeric") from exc
    if not math.isfinite(angle):
        raise QuantumEncodingError("quantum angle must be finite")

    normalized = math.remainder(angle, 2.0 * math.pi)
    fixed = int(round(normalized * ANGLE_SCALE))
    if fixed < -_SIGNED_PARAMETER_LIMIT or fixed >= _SIGNED_PARAMETER_LIMIT:
        raise QuantumEncodingError("normalized quantum angle is out of range")
    payload = fixed & ((1 << _SIGNED_PARAMETER_BITS) - 1)
    return ((payload << 7) | CUSTOM_1_OPCODE) & WORD_MASK


def decode_word(word: int) -> DecodedInstruction:
    """Decode one custom 32-bit word and validate its reserved fields."""
    if not isinstance(word, int) or word < 0 or word > WORD_MASK:
        raise QuantumEncodingError("instruction word must be an unsigned 32-bit integer")

    opcode = word & 0x7F
    if opcode == CUSTOM_1_OPCODE:
        payload = word >> 7
        if payload & _SIGNED_PARAMETER_LIMIT:
            payload -= 1 << _SIGNED_PARAMETER_BITS
        return DecodedInstruction(
            kind="parameter", angle=payload / float(ANGLE_SCALE)
        )

    if opcode != CUSTOM_0_OPCODE:
        raise QuantumEncodingError("unsupported custom opcode: 0x%02x" % opcode)
    if ((word >> 12) & 0x7) != 0:
        raise QuantumEncodingError("Q-type funct3 must be zero")

    gate_value = (word >> 25) & 0x7F
    try:
        gate = GateCode(gate_value)
    except ValueError as exc:
        raise QuantumEncodingError("unknown quantum gate id: %d" % gate_value) from exc

    rd = (word >> 7) & 0x1F
    q0 = (word >> 15) & 0x1F
    q1 = (word >> 20) & 0x1F
    _validate_gate_operands(gate, q0, q1, rd)
    return DecodedInstruction(kind="gate", gate=gate, q0=q0, q1=q1, rd=rd)


def instruction_to_assembly(instruction: DecodedInstruction) -> str:
    """Render a decoded machine word as the extension's readable assembly."""
    if instruction.kind == "parameter":
        if instruction.angle is None:
            raise QuantumEncodingError("parameter instruction has no angle")
        return "qparam %s" % _format_angle(instruction.angle)

    gate = instruction.gate
    if gate is None:
        raise QuantumEncodingError("gate instruction has no gate code")
    mnemonic = MNEMONIC_BY_GATE[gate]
    if gate == GateCode.QINIT:
        return "%s %d" % (mnemonic, instruction.q0)
    if gate in _SINGLE_QUBIT_GATES:
        return "%s q%d" % (mnemonic, instruction.q0)
    if gate in _TWO_QUBIT_GATES:
        return "%s q%d, q%d" % (mnemonic, instruction.q0, instruction.q1)
    if gate == GateCode.CCX:
        return "%s q%d, q%d, q%d" % (
            mnemonic,
            instruction.q0,
            instruction.q1,
            instruction.rd,
        )
    if gate == GateCode.MEASURE:
        return "%s q%d, x%d" % (mnemonic, instruction.q0, instruction.rd)
    raise QuantumEncodingError("cannot render gate: %s" % gate)


def _validate_gate_operands(gate: GateCode, q0: int, q1: int, rd: int) -> None:
    if gate == GateCode.QINIT:
        if q0 < 1 or q1 != 0 or rd != 0:
            raise QuantumEncodingError("qinit requires a qubit count from 1 to 31")
        return
    if gate in _SINGLE_QUBIT_GATES:
        if q1 != 0 or rd != 0:
            raise QuantumEncodingError("single-qubit gates reserve q1 and rd as zero")
        return
    if gate in _TWO_QUBIT_GATES:
        if rd != 0 or q0 == q1:
            raise QuantumEncodingError("two-qubit gates require distinct qubits and rd=0")
        return
    if gate == GateCode.CCX:
        if len({q0, q1, rd}) != 3:
            raise QuantumEncodingError("qccx requires three distinct qubits")
        return
    if gate == GateCode.MEASURE:
        if q1 != 0 or rd < 10:
            raise QuantumEncodingError("qmeasure requires destination x10..x31")
        return
    raise QuantumEncodingError("unsupported gate code: %s" % gate)


def _check_field(name: str, value: int) -> None:
    if not isinstance(value, int) or value < 0 or value > 31:
        raise QuantumEncodingError("%s must fit an unsigned 5-bit field" % name)


def _format_angle(value: float) -> str:
    text = format(value, ".6f").rstrip("0").rstrip(".")
    return text if text not in {"", "-0"} else "0"
