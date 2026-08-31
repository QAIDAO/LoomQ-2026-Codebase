"""Quantum extension of the official TinyRISCVEmulator."""

from __future__ import annotations

import random
from typing import Dict, Iterable, List, Optional, Tuple

try:
    from ..riscv_emulator import TinyRISCVEmulator
except ImportError:
    from riscv_emulator import TinyRISCVEmulator

from .decoder import decode_program
from .isa import SPECS_BY_MNEMONIC, units_to_angle
from .statevector import QuantumState


class QuantumRISCVEmulator(TinyRISCVEmulator):
    """Execute the official classical subset plus isolated quantum custom opcodes."""

    def __init__(self, seed: int = 0):
        super().__init__()
        self._rng = random.Random(seed)
        self._quantum_state: Optional[QuantumState] = None
        self._pending_angle: Optional[float] = None
        self.execution_log: List[Dict[str, object]] = []

    @property
    def quantum_state(self) -> Tuple[complex, ...]:
        if self._quantum_state is None:
            return ()
        return tuple(self._quantum_state.amplitudes)

    def load_program(self, asm_code: str):
        super().load_program(asm_code)
        self._reset_quantum_runtime()

    def load_quantum_words(
        self, words: Iterable[int], classical_assembly: str = ""
    ) -> None:
        """Load decoded custom words before an optional official-subset program."""
        decoded = decode_program(words)
        super().load_program(classical_assembly)
        quantum = []
        for instruction in decoded:
            operands = [str(value) for value in instruction.operands]
            quantum.append((instruction.mnemonic, operands))
        offset = len(quantum)
        self.instructions = quantum + self.instructions
        self.labels = {name: index + offset for name, index in self.labels.items()}
        self.pc = 0
        self._reset_quantum_runtime()

    def execute(self) -> Dict[str, int]:
        steps = 0
        while 0 <= self.pc < len(self.instructions):
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")
            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1
            if op == "qparam":
                self._set_parameter(args)
            elif op in SPECS_BY_MNEMONIC:
                self._execute_quantum(op, args)
            else:
                if self._pending_angle is not None:
                    raise ValueError("QPARAM must be immediately followed by a parameterized gate")
                next_pc = self._execute_classical(op, args, next_pc)
            self.pc = next_pc
        if self._pending_angle is not None:
            raise ValueError("Program ended with an unconsumed QPARAM")
        return {
            f"x{index}": value
            for index, value in enumerate(self.registers)
            if value != 0
        }

    def _reset_quantum_runtime(self) -> None:
        self._quantum_state = None
        self._pending_angle = None
        self.execution_log = []

    def _set_parameter(self, args: List[str]) -> None:
        if len(args) != 1:
            raise ValueError("QPARAM expects one signed fixed-point operand")
        if self._pending_angle is not None:
            raise ValueError("QPARAM cannot overwrite an unconsumed angle")
        self._pending_angle = units_to_angle(int(args[0]))
        self.execution_log.append({"instruction": "qparam", "units": int(args[0])})

    def _execute_quantum(self, op: str, args: List[str]) -> None:
        spec = SPECS_BY_MNEMONIC[op]
        if len(args) != len(spec.operands):
            raise ValueError(f"{op.upper()} expects {len(spec.operands)} operands")
        values = tuple(int(value[1:]) if value.lower().startswith("x") else int(value) for value in args)
        if spec.parameterized != (self._pending_angle is not None):
            if self._pending_angle is not None:
                raise ValueError("QPARAM must be immediately followed by a parameterized gate")
            raise ValueError(f"{op.upper()} requires a preceding QPARAM")

        if op == "qinit":
            self._quantum_state = QuantumState(values[0], self._rng)
            self.execution_log.append({"instruction": op, "qubits": values[0]})
            return
        if self._quantum_state is None:
            raise ValueError(f"{op.upper()} requires QINIT before quantum execution")
        if op == "qmeasure":
            qubit, register = values
            if not 1 <= register <= 31:
                raise ValueError("QMEASURE destination must be x1..x31")
            outcome = self._quantum_state.measure(qubit)
            self.set_register(f"x{register}", outcome)
            self.execution_log.append(
                {
                    "instruction": op,
                    "qubit": qubit,
                    "register": f"x{register}",
                    "outcome": outcome,
                }
            )
            return

        angle = self._pending_angle
        self._pending_angle = None
        self._quantum_state.apply(op, values, angle)
        item: Dict[str, object] = {"instruction": op, "qubits": values}
        if angle is not None:
            item["angle"] = angle
        self.execution_log.append(item)

    def _execute_classical(self, op: str, args: List[str], next_pc: int) -> int:
        if op == "li":
            rd, imm = args[0], int(args[1])
            self.set_register(rd, imm)
        elif op == "add":
            rd, rs1, rs2 = args[0], args[1], args[2]
            self.set_register(rd, self.get_register(rs1) + self.get_register(rs2))
        elif op == "sub":
            rd, rs1, rs2 = args[0], args[1], args[2]
            self.set_register(rd, self.get_register(rs1) - self.get_register(rs2))
        elif op == "addi":
            rd, rs1, imm = args[0], args[1], int(args[2])
            self.set_register(rd, self.get_register(rs1) + imm)
        elif op in {"beq", "bne"}:
            rs1, rs2, label = args[0], args[1], args[2]
            equal = self.get_register(rs1) == self.get_register(rs2)
            taken = equal if op == "beq" else not equal
            if taken:
                if label not in self.labels:
                    raise ValueError(f"未定义的跳转标签: {label}")
                next_pc = self.labels[label]
        elif op == "j":
            label = args[0]
            if label not in self.labels:
                raise ValueError(f"未定义的跳转标签: {label}")
            next_pc = self.labels[label]
        else:
            raise ValueError(f"不支持的指令操作: {op}")
        return next_pc
