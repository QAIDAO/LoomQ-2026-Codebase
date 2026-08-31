"""Optional custom-0 quantum RISC-V extension for LoomQ L3 Bonus."""
from __future__ import annotations
from dataclasses import dataclass
import math
import random
import re
try:
    from ..riscv_emulator import TinyRISCVEmulator
except ImportError:
    from riscv_emulator import TinyRISCVEmulator
try:
    from .gate_policy import PUBLIC_GATE_ARITY
    from .qasm import GateOperation, MeasureOperation, _parse_operation
    from .simulator import _apply_gate, _parameter_value
except ImportError:  # Allows direct execution from starter_kit/loomq.
    from gate_policy import PUBLIC_GATE_ARITY
    from qasm import GateOperation, MeasureOperation, _parse_operation
    from simulator import _apply_gate, _parameter_value

CUSTOM0_OPCODE = 0x0B
_GATE_ARITY = PUBLIC_GATE_ARITY
_GATE_IDS = {gate: index for index, gate in enumerate(_GATE_ARITY)}
_ID_TO_GATE = {index: gate for gate, index in _GATE_IDS.items()}
_GATE_FUNCT3, _MEASURE_FUNCT3, _PARAM_FUNCT3 = 0, 1, 2
_PARAM_SCALE = 1 << 15
_PARAM_MASK = (1 << 22) - 1

class QuantumOpcodeError(ValueError):
    pass

@dataclass(frozen=True)
class QuantumInstruction:
    gate: str
    qubits: tuple[int, ...] = ()
    cbit: int | None = None
    parameter: float | None = None

    @property
    def qubit(self) -> int:
        if len(self.qubits) != 1:
            raise QuantumOpcodeError(f"{self.gate} does not have one qubit")
        return self.qubits[0]

def _field(name: str, value: int) -> int:
    if not isinstance(value, int) or not 0 <= value < 32:
        raise QuantumOpcodeError(f"{name} field must be 0..31")
    return value

def encode_qop(gate: str, *qubits: int, cbit: int | None = None) -> int:
    """Encode a gate or measurement into one 32-bit custom-0 word."""
    gate = gate.lower()
    if gate == "measure":
        if cbit is None and len(qubits) == 2:
            qubits, cbit = (qubits[0],), qubits[1]
        if len(qubits) != 1 or cbit is None:
            raise QuantumOpcodeError("measure requires one qubit and one cbit")
        qubit, cbit = _field("qubit", qubits[0]), _field("cbit", cbit)
        if cbit > 21:
            raise QuantumOpcodeError("measurement cbit must map to x10 through x31")
        return CUSTOM0_OPCODE | (qubit << 7) | (_MEASURE_FUNCT3 << 12) | (cbit << 15)
    if gate not in _GATE_ARITY:
        raise QuantumOpcodeError(f"unsupported quantum gate: {gate}")
    if len(qubits) != _GATE_ARITY[gate]:
        raise QuantumOpcodeError(f"{gate} requires {_GATE_ARITY[gate]} qubits")
    operands = tuple(_field("qubit", value) for value in qubits)
    q0, q1, q2 = operands[0], operands[1] if len(operands) > 1 else 0, operands[2] if len(operands) > 2 else 0
    return CUSTOM0_OPCODE | (q0 << 7) | (_GATE_FUNCT3 << 12) | (q1 << 15) | (q2 << 20) | (_GATE_IDS[gate] << 25)

def encode_qparam(angle: float) -> int:
    """Encode a signed Q7.15 radian parameter-load custom instruction."""
    if not isinstance(angle, (int, float)) or not math.isfinite(angle):
        raise QuantumOpcodeError("quantum parameter must be finite")
    scaled = round(float(angle) * _PARAM_SCALE)
    if not -(1 << 21) <= scaled < (1 << 21):
        raise QuantumOpcodeError("parameter is outside signed Q7.15 range")
    payload = scaled & _PARAM_MASK
    return CUSTOM0_OPCODE | ((payload & 0x1F) << 7) | (_PARAM_FUNCT3 << 12) | ((payload >> 5) << 15)

def decode_qop(word: int) -> QuantumInstruction:
    if not isinstance(word, int) or word < 0 or word > 0xFFFFFFFF or (word & 0x7F) != CUSTOM0_OPCODE:
        raise QuantumOpcodeError("word is not a LoomQ custom-0 instruction")
    funct3 = (word >> 12) & 0x7
    if funct3 == _PARAM_FUNCT3:
        payload = ((word >> 15) << 5) | ((word >> 7) & 0x1F)
        if payload & (1 << 21): payload -= 1 << 22
        return QuantumInstruction("param", parameter=payload / _PARAM_SCALE)
    q0, q1, q2 = (word >> 7) & 0x1F, (word >> 15) & 0x1F, (word >> 20) & 0x1F
    if funct3 == _MEASURE_FUNCT3:
        if word >> 20 or q1 > 21:
            raise QuantumOpcodeError("invalid measurement encoding")
        return QuantumInstruction("measure", (q0,), q1)
    if funct3 != _GATE_FUNCT3:
        raise QuantumOpcodeError("unknown LoomQ quantum funct3")
    gate = _ID_TO_GATE.get((word >> 25) & 0x7F)
    if gate is None:
        raise QuantumOpcodeError("unknown LoomQ quantum gate id")
    arity = _GATE_ARITY[gate]
    if (arity < 3 and q2) or (arity < 2 and q1):
        raise QuantumOpcodeError("unused quantum operand field must be zero")
    return QuantumInstruction(gate, (q0,) if arity == 1 else (q0, q1) if arity == 2 else (q0, q1, q2))

class ExtendedTinyRISCVEmulator(TinyRISCVEmulator):
    """Compatible fork with custom qop execution and deterministic measurement."""
    def __init__(self, *, seed: int = 0, max_qubits: int = 12):
        super().__init__()
        if max_qubits < 1:
            raise ValueError("max_qubits must be positive")
        self.seed, self.max_qubits = seed, max_qubits
        self.quantum_trace: list[QuantumInstruction] = []
        self.statevector: list[complex] = [1 + 0j]
        self._random = random.Random(seed)
        self._pending_angle: float | None = None

    def load_program(self, asm_code: str) -> None:
        super().load_program(asm_code)
        self.quantum_trace = []
        self.statevector = [1 + 0j]
        self._random = random.Random(self.seed)
        self._pending_angle = None

    def _ensure_qubits(self, qubits: tuple[int, ...]) -> None:
        required = max(qubits, default=0) + 1
        if required > self.max_qubits:
            raise QuantumOpcodeError(f"execution supports at most {self.max_qubits} qubits")
        while len(self.statevector) < (1 << required):
            self.statevector.extend([0j] * len(self.statevector))

    def _measure(self, instruction: QuantumInstruction) -> None:
        qubit, cbit = instruction.qubit, instruction.cbit
        assert cbit is not None
        self._ensure_qubits((qubit,))
        mask = 1 << qubit
        probability_one = sum(abs(value) ** 2 for index, value in enumerate(self.statevector) if index & mask)
        result = int(self._random.random() < probability_one)
        probability = probability_one if result else 1.0 - probability_one
        if probability <= 0:
            raise QuantumOpcodeError("measurement selected a zero-probability state")
        scale = 1 / math.sqrt(probability)
        for index, value in enumerate(self.statevector):
            self.statevector[index] = value * scale if bool(index & mask) == bool(result) else 0j
        self.set_register(f"x{10 + cbit}", result)

    def _execute_quantum(self, instruction: QuantumInstruction) -> None:
        self.quantum_trace.append(instruction)
        if instruction.gate == "param":
            self._pending_angle = instruction.parameter
            return
        if instruction.gate == "measure":
            if self._pending_angle is not None:
                raise QuantumOpcodeError("parameter load must be followed by rz, ry or cu1")
            self._measure(instruction)
            return
        self._ensure_qubits(instruction.qubits)
        if instruction.gate in {"rz", "ry", "cu1"}:
            if self._pending_angle is None:
                raise QuantumOpcodeError(f"{instruction.gate} requires a preceding parameter word")
            parameter = self._pending_angle
            self._pending_angle = None
        else:
            if self._pending_angle is not None:
                raise QuantumOpcodeError("parameter load must be followed by rz, ry or cu1")
            parameter = None
        operation = GateOperation(
            instruction.gate,
            tuple(f"q[{qubit}]" for qubit in instruction.qubits),
            repr(parameter) if parameter is not None else None,
        )
        _apply_gate(self.statevector, operation)

    def execute(self) -> dict[str, int]:
        steps, total = 0, len(self.instructions)
        while 0 <= self.pc < total:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("program exceeded max_steps")
            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1
            if op == "qop":
                if len(args) != 1:
                    raise QuantumOpcodeError("qop requires exactly one encoded word")
                self._execute_quantum(decode_qop(int(args[0], 0)))
            elif op == "li": self.set_register(args[0], int(args[1]))
            elif op == "add": self.set_register(args[0], self.get_register(args[1]) + self.get_register(args[2]))
            elif op == "sub": self.set_register(args[0], self.get_register(args[1]) - self.get_register(args[2]))
            elif op == "addi": self.set_register(args[0], self.get_register(args[1]) + int(args[2]))
            elif op in {"beq", "bne"}:
                equal = self.get_register(args[0]) == self.get_register(args[1])
                if (equal if op == "beq" else not equal):
                    if args[2] not in self.labels: raise ValueError(f"undefined label: {args[2]}")
                    next_pc = self.labels[args[2]]
            elif op == "j":
                if args[0] not in self.labels: raise ValueError(f"undefined label: {args[0]}")
                next_pc = self.labels[args[0]]
            else:
                raise ValueError(f"unsupported instruction: {op}")
            self.pc = next_pc
        return {f"x{i}": value for i, value in enumerate(self.registers) if value}

_INDEXED = re.compile(r"^[A-Za-z_]\w*\[(\d+)\]$")

def _index(value: str, kind: str) -> int:
    match = _INDEXED.fullmatch(value)
    if match is None:
        raise QuantumOpcodeError(f"extension requires indexed {kind}: {value}")
    return int(match.group(1))

def compile_quantum_operations(operations: list[str]) -> str:
    """Bridge the L3 quantum sequence to executable custom-0 instructions."""
    lines: list[str] = []
    for raw in operations:
        try:
            operation = _parse_operation(raw.strip().rstrip(";"))
        except ValueError as exc:
            raise QuantumOpcodeError(f"invalid quantum operation: {raw}") from exc
        if isinstance(operation, MeasureOperation):
            word = encode_qop("measure", _index(operation.source, "measurement source"), cbit=_index(operation.destination, "measurement destination"))
            lines.append(f"qop 0x{word:08x}")
        else:
            qubits = tuple(_index(operand, "gate operand") for operand in operation.operands)
            if operation.parameter is not None:
                lines.append(f"qop 0x{encode_qparam(_parameter_value(operation.parameter)):08x}")
            lines.append(f"qop 0x{encode_qop(operation.name, *qubits):08x}")
    return "\n".join(lines) + ("\n" if lines else "")