"""Quantum RISC-V 32-bit custom instruction 的编码与解码。"""

from dataclasses import dataclass
from typing import Optional


CUSTOM_0_OPCODE = 0x0B
_MAX_FIELD_VALUE = 31
_WORD_MASK = 0xFFFFFFFF

_QH_FUNCT3 = 0
_QX_FUNCT3 = 1
_QCX_FUNCT3 = 2
_QMEAS_FUNCT3 = 3


class QuantumInstructionError(ValueError):
    """Quantum RISC-V 指令编码、字段或语义非法。"""


@dataclass(frozen=True)
class QuantumInstruction:
    """解码后的稳定命令；未使用的操作数以 None 表示。"""

    operation: str
    q0: int
    q1: Optional[int] = None
    rd: Optional[int] = None


def _validate_field(name: str, value: int, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("%s must be an integer" % name)
    if value < minimum or value > _MAX_FIELD_VALUE:
        raise QuantumInstructionError(
            "%s out of range (%d-%d): %d"
            % (name, minimum, _MAX_FIELD_VALUE, value)
        )


def _encode(funct3: int, q0: int, q1: int = 0, rd: int = 0) -> int:
    _validate_field("q0", q0)
    _validate_field("q1", q1)
    _validate_field("rd", rd)
    # funct7 固定为零，确保当前版本所有未分配高位都可被严格校验。
    return (
        ((q1 & 0x1F) << 20)
        | ((q0 & 0x1F) << 15)
        | ((funct3 & 0x07) << 12)
        | ((rd & 0x1F) << 7)
        | CUSTOM_0_OPCODE
    ) & _WORD_MASK


def encode_qh(qubit: int) -> int:
    """编码 QH q[qubit]。"""
    return _encode(_QH_FUNCT3, qubit)


def encode_qx(qubit: int) -> int:
    """编码 QX q[qubit]。"""
    return _encode(_QX_FUNCT3, qubit)


def encode_qcx(control: int, target: int) -> int:
    """编码 QCX q[control], q[target]。"""
    if control == target:
        raise QuantumInstructionError("QCX control and target must differ")
    return _encode(_QCX_FUNCT3, control, q1=target)


def encode_qmeas(qubit: int, classical_reg: int) -> int:
    """编码 QMEAS q[qubit] -> x[classical_reg]。"""
    _validate_field("classical_reg", classical_reg, minimum=1)
    return _encode(_QMEAS_FUNCT3, qubit, rd=classical_reg)


def decode_quantum_instruction(word: int) -> QuantumInstruction:
    """严格解码一个 32-bit custom word，拒绝保留字段和非法组合。"""
    if isinstance(word, bool) or not isinstance(word, int):
        raise TypeError("word must be an integer")
    if word < 0 or word > _WORD_MASK:
        raise QuantumInstructionError("word must be an unsigned 32-bit integer")

    opcode = word & 0x7F
    rd = (word >> 7) & 0x1F
    funct3 = (word >> 12) & 0x07
    q0 = (word >> 15) & 0x1F
    q1 = (word >> 20) & 0x1F
    funct7 = (word >> 25) & 0x7F

    if opcode != CUSTOM_0_OPCODE:
        raise QuantumInstructionError(
            "not a Quantum RISC-V custom-0 instruction: opcode 0x%02x" % opcode
        )
    if funct7 != 0:
        raise QuantumInstructionError("reserved funct7 bits must be zero")

    if funct3 == _QH_FUNCT3:
        if q1 != 0 or rd != 0:
            raise QuantumInstructionError("QH reserved q1 and rd fields must be zero")
        return QuantumInstruction("QH", q0)
    if funct3 == _QX_FUNCT3:
        if q1 != 0 or rd != 0:
            raise QuantumInstructionError("QX reserved q1 and rd fields must be zero")
        return QuantumInstruction("QX", q0)
    if funct3 == _QCX_FUNCT3:
        if rd != 0:
            raise QuantumInstructionError("QCX reserved rd field must be zero")
        if q0 == q1:
            raise QuantumInstructionError("QCX control and target must differ")
        return QuantumInstruction("QCX", q0, q1=q1)
    if funct3 == _QMEAS_FUNCT3:
        if q1 != 0:
            raise QuantumInstructionError("QMEAS reserved q1 field must be zero")
        if rd == 0:
            raise QuantumInstructionError("QMEAS rd must be x1-x31")
        return QuantumInstruction("QMEAS", q0, rd=rd)

    raise QuantumInstructionError(
        "unsupported quantum funct3: 0b{0:03b}".format(funct3)
    )


def format_instruction(instruction: QuantumInstruction) -> str:
    """生成仅用于诊断的可读形式；binary word 仍是执行依据。"""
    if instruction.operation in ("QH", "QX"):
        return "%s q[%d]" % (instruction.operation, instruction.q0)
    if instruction.operation == "QCX":
        return "QCX q[%d], q[%d]" % (instruction.q0, instruction.q1)
    if instruction.operation == "QMEAS":
        return "QMEAS q[%d] -> x%d" % (instruction.q0, instruction.rd)
    raise QuantumInstructionError("unknown decoded operation: %s" % instruction.operation)
