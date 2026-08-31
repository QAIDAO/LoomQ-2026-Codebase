#!/usr/bin/env python3
"""Official lightweight RISC-V emulator and LoomQ quantum extension.

``TinyRISCVEmulator`` remains the text-instruction compatibility target used
by L3.  The same official module also carries the LoomQ-QISA-v1 assembler,
decoder, and machine-word executor required by the quantum RISC-V Bonus.
The two execution paths intentionally keep their original arithmetic models:
L3 uses Python integers, while the machine-word path uses RV32 wrapping.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, DecimalException, ROUND_HALF_EVEN
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


__all__ = [
    "TinyRISCVEmulator",
    "MASK32",
    "OP_R",
    "OP_I",
    "OP_B",
    "OP_U",
    "OP_J",
    "OP_QGATE",
    "OP_QCTRL",
    "GATES",
    "GATE_NAMES",
    "GATE_ARITY",
    "QISAError",
    "Decoded",
    "QuantumBackend",
    "QuantumRISCVEmulator",
    "assemble",
    "decode",
    "reference_backend",
]


class TinyRISCVEmulator:
    def __init__(self):
        # 32个通用寄存器 x0 - x31，x0 恒为 0
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[str]]] = []
        self.max_steps = 1000  # 防止死循环

    def set_register(self, reg: str, value: int):
        idx = self._parse_reg_idx(reg)
        if idx != 0:
            self.registers[idx] = value

    def get_register(self, reg: str) -> int:
        idx = self._parse_reg_idx(reg)
        return self.registers[idx]

    def _parse_reg_idx(self, reg: str) -> int:
        reg = reg.strip().replace(",", "")
        if not reg.startswith("x") and not reg.startswith("X"):
            raise ValueError(f"无效的寄存器名称: {reg}")
        idx = int(reg[1:])
        if idx < 0 or idx > 31:
            raise ValueError(f"寄存器索引超出范围 (x0-x31): {reg}")
        return idx

    def load_program(self, asm_code: str):
        """
        解析汇编代码并建立标签索引
        """
        self.instructions = []
        self.labels = {}
        self.pc = 0
        self.registers = [0] * 32
        
        lines = asm_code.split("\n")
        temp_instructions = []
        
        # 第一次解析：过滤注释、空行并建立指令列表与 Label 映射
        for line in lines:
            line = line.strip()
            # 过滤注释和空行
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            
            # 分割行内注释
            if "#" in line:
                line = line.split("#")[0].strip()
            
            # 提取标签，例如 "LABEL_A:"
            if line.endswith(":"):
                label_name = line[:-1].strip()
                self.labels[label_name] = len(temp_instructions)
                continue
            elif ":" in line:
                # 处理同行的标签，例如 "LOOP: li x1, 10"
                parts = line.split(":", 1)
                label_name = parts[0].strip()
                self.labels[label_name] = len(temp_instructions)
                line = parts[1].strip()
            
            # 解析指令和参数
            tokens = line.replace(",", " ").split()
            op = tokens[0].lower()
            args = tokens[1:]
            temp_instructions.append((op, args))
            
        self.instructions = temp_instructions

    def execute(self) -> Dict[str, int]:
        """
        执行已载入的指令直到程序结束，返回所有寄存器状态字典
        """
        steps = 0
        num_instr = len(self.instructions)
        
        while 0 <= self.pc < num_instr:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")
                
            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1
            
            # 模拟执行各指令
            if op == "li":
                # li rd, imm
                rd, imm = args[0], int(args[1])
                self.set_register(rd, imm)
                
            elif op == "add":
                # add rd, rs1, rs2
                rd, rs1, rs2 = args[0], args[1], args[2]
                self.set_register(rd, self.get_register(rs1) + self.get_register(rs2))
                
            elif op == "sub":
                # sub rd, rs1, rs2
                rd, rs1, rs2 = args[0], args[1], args[2]
                self.set_register(rd, self.get_register(rs1) - self.get_register(rs2))
                
            elif op == "addi":
                # addi rd, rs1, imm
                rd, rs1, imm = args[0], args[1], int(args[2])
                self.set_register(rd, self.get_register(rs1) + imm)
                
            elif op == "beq":
                # beq rs1, rs2, label
                rs1, rs2, label = args[0], args[1], args[2]
                if self.get_register(rs1) == self.get_register(rs2):
                    if label not in self.labels:
                        raise ValueError(f"未定义的跳转标签: {label}")
                    next_pc = self.labels[label]
                    
            elif op == "bne":
                # bne rs1, rs2, label
                rs1, rs2, label = args[0], args[1], args[2]
                if self.get_register(rs1) != self.get_register(rs2):
                    if label not in self.labels:
                        raise ValueError(f"未定义的跳转标签: {label}")
                    next_pc = self.labels[label]
                    
            elif op == "j":
                # j label
                label = args[0]
                if label not in self.labels:
                    raise ValueError(f"未定义的跳转标签: {label}")
                next_pc = self.labels[label]
                
            else:
                raise ValueError(f"不支持的指令操作: {op}")
                
            self.pc = next_pc
            
        # 返回非零寄存器的状态汇总
        result = {}
        for idx, val in enumerate(self.registers):
            if val != 0:
                result[f"x{idx}"] = val
        return result

# ---------------------------------------------------------------------------
# LoomQ-QISA-v1 machine-word extension
# ---------------------------------------------------------------------------

MASK32 = 0xFFFFFFFF
OP_R, OP_I, OP_B, OP_U, OP_J = 0x33, 0x13, 0x63, 0x37, 0x6F
OP_QGATE, OP_QCTRL = 0x0B, 0x2B
GATES = {
    "h": 1,
    "x": 2,
    "s": 3,
    "sdg": 4,
    "t": 5,
    "tdg": 6,
    "rz": 7,
    "ry": 8,
    "cx": 9,
    "cu1": 10,
    "swap": 11,
    "ccx": 12,
}
GATE_NAMES = {value: key for key, value in GATES.items()}
GATE_ARITY = {
    **{name: 1 for name in ("h", "x", "s", "sdg", "t", "tdg", "rz", "ry")},
    **{name: 2 for name in ("cx", "cu1", "swap")},
    "ccx": 3,
}
PARAMETER_GATES = frozenset(("rz", "ry", "cu1"))


class QISAError(ValueError):
    """Raised for malformed or invalid LoomQ-QISA-v1 programs."""


@dataclass(frozen=True)
class Decoded:
    """Normalized representation returned by :func:`decode`."""

    op: str
    rd: int = 0
    rs1: int = 0
    rs2: int = 0
    immediate: int = 0
    q0: int = 0
    q1: int = 0
    aux: int = 0


def _signed(value: int, bits: int) -> int:
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def _reg(token: str) -> int:
    match = re.fullmatch(r"[xX](\d+)", token.strip())
    if not match or int(match.group(1)) > 31:
        raise QISAError("invalid register %r" % token)
    return int(match.group(1))


def _range(value: int, low: int, high: int, name: str) -> int:
    if value < low or value > high:
        raise QISAError("%s out of range: %d" % (name, value))
    return value


def _bad(detail: str) -> None:
    raise QISAError("non-zero reserved %s" % detail)


def decode(word: int, pc: int = 0) -> Decoded:
    """Decode one RV32/LoomQ-QISA-v1 machine word.

    Unknown instructions and every reserved custom-instruction encoding fail
    closed with :class:`QISAError`.
    """

    if type(word) is not int or not 0 <= word <= MASK32:
        raise QISAError("instruction word must be uint32")
    if type(pc) is not int or pc < 0 or pc % 4:
        raise QISAError("unaligned PC: %r" % pc)

    opcode = word & 0x7F
    rd = (word >> 7) & 31
    funct3 = (word >> 12) & 7
    rs1 = (word >> 15) & 31
    rs2 = (word >> 20) & 31
    funct7 = (word >> 25) & 127

    if opcode == OP_R and funct3 == 0 and funct7 in (0, 0x20):
        return Decoded("add" if funct7 == 0 else "sub", rd, rs1, rs2)
    if opcode == OP_I and funct3 == 0:
        return Decoded("addi", rd, rs1, immediate=_signed(word >> 20, 12))
    if opcode == OP_U:
        return Decoded("lui", rd, immediate=word & 0xFFFFF000)
    if opcode == OP_B and funct3 in (0, 1):
        immediate = (
            ((word >> 31) << 12)
            | (((word >> 7) & 1) << 11)
            | (((word >> 25) & 0x3F) << 5)
            | (((word >> 8) & 0xF) << 1)
        )
        return Decoded(
            "beq" if funct3 == 0 else "bne",
            rs1=rs1,
            rs2=rs2,
            immediate=_signed(immediate, 13),
        )
    if opcode == OP_J and rd == 0:
        immediate = (
            ((word >> 31) << 20)
            | (((word >> 12) & 0xFF) << 12)
            | (((word >> 20) & 1) << 11)
            | (((word >> 21) & 0x3FF) << 1)
        )
        return Decoded("jal", immediate=_signed(immediate, 21))

    if opcode == OP_QGATE:
        if funct3 != 0 or funct7 not in GATE_NAMES:
            raise QISAError("reserved QGATE encoding")
        name = GATE_NAMES[funct7]
        arity = GATE_ARITY[name]
        if arity == 1 and rs1:
            _bad("QGATE q1 field")
        if arity < 3 and rs2 and name not in PARAMETER_GATES:
            _bad("QGATE aux field")
        if name in PARAMETER_GATES and rs2 == 0:
            raise QISAError("parameter gate requires a non-zero parameter register")
        return Decoded(name, q0=rd, q1=rs1, aux=rs2)

    if opcode == OP_QCTRL:
        operation, slot, qubit, reserved = funct3, rs2, rs1, funct7
        if reserved or operation > 3:
            raise QISAError("reserved QCTRL encoding")
        if operation == 0 and (rd or qubit or slot):
            _bad("qreset fields")
        if operation == 1 and rd:
            _bad("qmeasure rd")
        if operation == 2 and (rd or qubit or slot):
            _bad("qsubmit fields")
        if operation == 3 and qubit:
            _bad("qread q")
        return Decoded(
            ("qreset", "qmeasure", "qsubmit", "qread")[operation],
            rd=rd,
            q0=qubit,
            aux=slot,
        )

    raise QISAError("unsupported instruction 0x%08x" % word)


def _r(op: str, rd: int, rs1: int, rs2: int) -> int:
    return (
        ((0x20 if op == "sub" else 0) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (rd << 7)
        | OP_R
    )


def _i(rd: int, rs1: int, immediate: int) -> int:
    _range(immediate, -2048, 2047, "I immediate")
    return ((immediate & 0xFFF) << 20) | (rs1 << 15) | (rd << 7) | OP_I


def _b(op: str, rs1: int, rs2: int, immediate: int) -> int:
    _range(immediate, -4096, 4094, "B offset")
    if immediate % 2:
        raise QISAError("unaligned B offset")
    value = immediate & 0x1FFF
    return (
        (((value >> 12) & 1) << 31)
        | (((value >> 5) & 0x3F) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | ((1 if op == "bne" else 0) << 12)
        | (((value >> 1) & 0xF) << 8)
        | (((value >> 11) & 1) << 7)
        | OP_B
    )


def _j(immediate: int) -> int:
    _range(immediate, -(1 << 20), (1 << 20) - 2, "J offset")
    if immediate % 2:
        raise QISAError("unaligned J offset")
    value = immediate & 0x1FFFFF
    return (
        (((value >> 20) & 1) << 31)
        | (((value >> 1) & 0x3FF) << 21)
        | (((value >> 11) & 1) << 20)
        | (((value >> 12) & 0xFF) << 12)
        | OP_J
    )


def _li(rd: int, value: int) -> List[int]:
    _range(value, -(1 << 31), (1 << 32) - 1, "li immediate")
    value &= MASK32
    signed_value = _signed(value, 32)
    if -2048 <= signed_value <= 2047:
        return [_i(rd, 0, signed_value)]
    upper = (value + 0x800) & 0xFFFFF000
    low = _signed((value - upper) & 0xFFF, 12)
    return [upper | (rd << 7) | OP_U] + ([] if low == 0 else [_i(rd, rd, low)])


def _clean(source: str) -> List[Tuple[Optional[str], Optional[str], List[str]]]:
    if not isinstance(source, str):
        raise QISAError("assembly source must be text")
    rows: List[Tuple[Optional[str], Optional[str], List[str]]] = []
    for raw in source.splitlines():
        line = raw.split("#", 1)[0].split(";", 1)[0].strip()
        if not line:
            continue
        label = None
        if ":" in line:
            label, line = (part.strip() for part in line.split(":", 1))
            if not re.fullmatch(r"[A-Za-z_]\w*", label):
                raise QISAError("invalid label")
        if line:
            parts = line.replace(",", " ").split()
            rows.append((label, parts[0].lower(), parts[1:]))
        else:
            rows.append((label, None, []))
    return rows


def _integer(token: str, name: str) -> int:
    try:
        return int(token, 0)
    except (TypeError, ValueError) as exc:
        raise QISAError("invalid %s %r" % (name, token)) from exc


def _gate_operands(args: Sequence[str]) -> Tuple[str, int, List[int], int, Optional[int]]:
    if not args:
        raise QISAError("qgate requires a gate name")
    name = args[0].lower()
    arity = GATE_ARITY.get(name)
    if arity is None:
        raise QISAError("unknown quantum gate")
    expected = arity + (3 if name in PARAMETER_GATES else 1)
    if len(args) != expected:
        raise QISAError("wrong qgate operand count")
    qubits = [_range(_integer(token, "qubit"), 0, 31, "qubit") for token in args[1:1 + arity]]
    parameter_register = 0
    fixed_parameter: Optional[int] = None
    if name in PARAMETER_GATES:
        parameter_register = _reg(args[1 + arity])
        if parameter_register == 0:
            raise QISAError("parameter register must not be x0")
        try:
            angle = Decimal(args[2 + arity])
        except (DecimalException, ValueError) as exc:
            raise QISAError("invalid gate angle %r" % args[2 + arity]) from exc
        if not angle.is_finite():
            raise QISAError("gate angle must be finite")
        try:
            fixed_parameter = int(
                (angle * Decimal(65536)).to_integral_value(rounding=ROUND_HALF_EVEN)
            )
        except (DecimalException, OverflowError, ValueError) as exc:
            raise QISAError("gate angle is outside Q16.16 range") from exc
        _range(fixed_parameter, -(1 << 31), (1 << 31) - 1, "Q16.16 parameter")
    return name, arity, qubits, parameter_register, fixed_parameter


def _word_count(op: str, args: Sequence[str]) -> int:
    if op == "li":
        if len(args) != 2:
            raise QISAError("invalid instruction li %s" % " ".join(args))
        return len(_li(_reg(args[0]), _integer(args[1], "li immediate")))
    if op == "qgate":
        _, _, _, parameter_register, fixed_parameter = _gate_operands(args)
        if fixed_parameter is not None:
            return len(_li(parameter_register, fixed_parameter)) + 1
    return 1


def _label_address(labels: Dict[str, int], label: str) -> int:
    try:
        return labels[label]
    except KeyError as exc:
        raise QISAError("undefined label %s" % label) from exc


def assemble(source: str) -> List[int]:
    """Assemble the supported RV32 subset and quantum custom instructions."""

    rows = _clean(source)
    labels: Dict[str, int] = {}
    pc = 0
    for label, op, args in rows:
        if label:
            if label in labels:
                raise QISAError("duplicate label %s" % label)
            labels[label] = pc
        if op:
            pc += 4 * _word_count(op, args)

    words: List[int] = []
    pc = 0
    for _, op, args in rows:
        if not op:
            continue
        encoded: List[int]
        if op in ("add", "sub") and len(args) == 3:
            encoded = [_r(op, _reg(args[0]), _reg(args[1]), _reg(args[2]))]
        elif op == "addi" and len(args) == 3:
            encoded = [_i(_reg(args[0]), _reg(args[1]), _integer(args[2], "I immediate"))]
        elif op == "lui" and len(args) == 2:
            immediate = _range(_integer(args[1], "U immediate"), 0, 0xFFFFF, "U immediate")
            encoded = [(immediate << 12) | (_reg(args[0]) << 7) | OP_U]
        elif op == "li" and len(args) == 2:
            encoded = _li(_reg(args[0]), _integer(args[1], "li immediate"))
        elif op in ("beq", "bne") and len(args) == 3:
            encoded = [
                _b(
                    op,
                    _reg(args[0]),
                    _reg(args[1]),
                    _label_address(labels, args[2]) - pc,
                )
            ]
        elif op == "j" and len(args) == 1:
            encoded = [_j(_label_address(labels, args[0]) - pc)]
        elif op == "jal" and len(args) == 2 and _reg(args[0]) == 0:
            encoded = [_j(_label_address(labels, args[1]) - pc)]
        elif op == "qgate":
            name, arity, qubits, parameter_register, fixed_parameter = _gate_operands(args)
            encoded = []
            aux = qubits[2] if arity == 3 else 0
            if fixed_parameter is not None:
                encoded.extend(_li(parameter_register, fixed_parameter))
                aux = parameter_register
            encoded.append(
                (GATES[name] << 25)
                | (aux << 20)
                | ((qubits[1] if arity >= 2 else 0) << 15)
                | (qubits[0] << 7)
                | OP_QGATE
            )
        elif op == "qreset" and not args:
            encoded = [OP_QCTRL]
        elif op == "qmeasure" and len(args) == 2:
            qubit = _range(_integer(args[0], "qubit"), 0, 31, "qubit")
            slot = _range(_integer(args[1], "slot"), 0, 31, "slot")
            encoded = [(slot << 20) | (qubit << 15) | (1 << 12) | OP_QCTRL]
        elif op == "qsubmit" and not args:
            encoded = [(2 << 12) | OP_QCTRL]
        elif op == "qread" and len(args) == 2:
            slot = _range(_integer(args[1], "slot"), 0, 31, "slot")
            encoded = [(slot << 20) | (3 << 12) | (_reg(args[0]) << 7) | OP_QCTRL]
        else:
            raise QISAError("invalid instruction %s %s" % (op, " ".join(args)))
        words.extend(encoded)
        pc += 4 * len(encoded)
    return words


QuantumGate = Tuple[str, Tuple[int, ...], Optional[float]]
QuantumBackend = Callable[[Sequence[QuantumGate], Dict[int, int]], Dict[int, int]]


class QuantumRISCVEmulator:
    """Execute RV32 and LoomQ quantum custom-opcode machine words."""

    def __init__(self, backend: QuantumBackend, max_steps: int = 1000):
        if not callable(backend):
            raise TypeError("backend must be callable")
        if type(max_steps) is not int or max_steps <= 0:
            raise ValueError("max_steps must be a positive integer")
        self.backend = backend
        self.max_steps = max_steps
        self.registers = [0] * 32
        self.pc = 0
        self.pending: List[QuantumGate] = []
        self.measurements: Dict[int, int] = {}
        self.result: Optional[Dict[int, int]] = None
        self.submitted = False

    def execute(self, words: Sequence[int]) -> Dict[str, int]:
        """Execute an immutable snapshot of machine words to completion."""

        memory = tuple(words)
        if any(type(word) is not int or not 0 <= word <= MASK32 for word in memory):
            raise QISAError("invalid instruction memory")
        steps = 0
        while 0 <= self.pc < len(memory) * 4:
            if self.pc % 4:
                raise QISAError("unaligned fetch")
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("maximum instruction count exceeded")

            instruction = decode(memory[self.pc // 4], self.pc)
            next_pc = self.pc + 4
            left = self.registers[instruction.rs1]
            right = self.registers[instruction.rs2]

            if instruction.op == "add":
                self._set(instruction.rd, left + right)
            elif instruction.op == "sub":
                self._set(instruction.rd, left - right)
            elif instruction.op == "addi":
                self._set(instruction.rd, left + instruction.immediate)
            elif instruction.op == "lui":
                self._set(instruction.rd, instruction.immediate)
            elif instruction.op in ("beq", "bne"):
                taken = (left == right) == (instruction.op == "beq")
                if taken:
                    next_pc = self.pc + instruction.immediate
            elif instruction.op == "jal":
                next_pc = self.pc + instruction.immediate
            elif instruction.op in GATES:
                if self.submitted:
                    raise QISAError("qreset required before appending another circuit")
                arity = GATE_ARITY[instruction.op]
                qubits = (instruction.q0,)
                if arity >= 2:
                    qubits += (instruction.q1,)
                if arity == 3:
                    qubits += (instruction.aux,)
                angle = None
                if instruction.op in PARAMETER_GATES:
                    angle = _signed(self.registers[instruction.aux], 32) / 65536.0
                self.pending.append((instruction.op, qubits, angle))
            elif instruction.op == "qreset":
                self.pending.clear()
                self.measurements.clear()
                self.result = None
                self.submitted = False
            elif instruction.op == "qmeasure":
                if self.submitted:
                    raise QISAError("qreset required before appending another circuit")
                if instruction.aux in self.measurements:
                    raise QISAError("duplicate measurement slot")
                self.measurements[instruction.aux] = instruction.q0
            elif instruction.op == "qsubmit":
                if not self.pending or not self.measurements:
                    raise QISAError("empty quantum submission")
                if self.submitted:
                    raise QISAError("circuit already submitted")
                result = dict(self.backend(tuple(self.pending), dict(self.measurements)))
                if set(result) != set(self.measurements) or any(
                    type(value) is not int or value not in (0, 1)
                    for value in result.values()
                ):
                    raise QISAError("backend returned an invalid single-shot result")
                self.result = result
                self.submitted = True
            elif instruction.op == "qread":
                if self.result is None or instruction.aux not in self.result:
                    raise QISAError("unavailable quantum result")
                self._set(instruction.rd, self.result[instruction.aux])

            self.pc = next_pc
            self.registers[0] = 0

        return {
            "x%d" % index: value
            for index, value in enumerate(self.registers)
            if value
        }

    def _set(self, register: int, value: int) -> None:
        if register:
            self.registers[register] = value & MASK32


def reference_backend(
    gates: Sequence[QuantumGate], measurements: Dict[int, int]
) -> Dict[int, int]:
    """Run one deterministic local shot using the existing L1 reference model."""

    from l1_reference import distribution

    width = max(
        [0]
        + [qubit for _, qubits, _ in gates for qubit in qubits]
        + list(measurements.values())
    ) + 1
    slots = max(measurements) + 1
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[%d];" % width,
        "creg c[%d];" % slots,
    ]
    for name, qubits, angle in gates:
        parameter = "(%s)" % format(angle, ".17g") if angle is not None else ""
        operands = ",".join("q[%d]" % qubit for qubit in qubits)
        lines.append("%s%s %s;" % (name, parameter, operands))
    for slot, qubit in sorted(measurements.items()):
        lines.append("measure q[%d] -> c[%d];" % (qubit, slot))
    probabilities = distribution("\n".join(lines))
    bits = max(probabilities, key=lambda key: (probabilities[key], key))
    return {slot: int(bits[-1 - slot]) for slot in measurements}


# 简易功能测试
if __name__ == "__main__":
    code = """
    li x1, 5
    li x2, 10
    beq x1, x2, EQUAL
    add x3, x1, x2       # x3 = 15
    j END
    EQUAL:
    sub x3, x2, x1
    END:
    addi x3, x3, 1       # x3 = 16
    """
    emu = TinyRISCVEmulator()
    emu.load_program(code)
    state = emu.execute()
    print("寄存器执行最终状态:", state)
    assert state.get("x3") == 16, "测试失败！"
    print("Tiny RISC-V 模拟器核心测试通过！")
