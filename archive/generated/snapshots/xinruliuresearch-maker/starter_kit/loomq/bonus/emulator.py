"""Quantum extension of the organizer-provided :class:`TinyRISCVEmulator`.

The official file remains untouched.  This subclass retains its public API and
classical instruction behavior while accepting quantum mnemonics or encoded
``.word`` directives in the RISC-V ``custom-0`` opcode space.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from riscv_emulator import TinyRISCVEmulator

from .isa import (
    QuantumDecodingError,
    assemble_quantum_line,
    decode_instruction,
    fixed_to_radians,
)
from .statevector import BonusStatevector


_QUANTUM_MNEMONICS = {
    "qinit",
    "qh",
    "qx",
    "qs",
    "qt",
    "qry",
    "qrz",
    "qcx",
    "qswap",
    "qccx",
    "qmeasure",
}


class QuantumRISCVEmulator(TinyRISCVEmulator):
    """TinyRISCV-compatible classical/quantum instruction demonstrator.

    GPR operands contain *qubit indices*, rather than being qubits themselves.
    This makes ordinary ``li``/``add``/branches useful for computing operands.
    Quantum state is local, ideal and bounded; it is never represented as real
    hardware evidence.
    """

    def __init__(self, *, seed: int = 0, max_qubits: int = 12) -> None:
        super().__init__()
        self.seed = seed
        self.max_qubits = max_qubits
        self.quantum_state = BonusStatevector(seed=seed, max_qubits=max_qubits)
        self.quantum_log: List[Dict[str, Any]] = []
        self.measurement_results: List[Dict[str, int]] = []

    def load_program(self, asm_code: str) -> None:
        """Load mixed official assembly, quantum mnemonics and ``.word`` lines."""

        if not isinstance(asm_code, str):
            raise TypeError("asm_code must be text")
        rewritten: List[str] = []
        for original in asm_code.splitlines():
            code, marker, comment = original.partition("#")
            stripped = code.strip()
            if not stripped:
                rewritten.append(original)
                continue

            label_prefix = ""
            instruction_text = stripped
            if ":" in stripped:
                possible_label, remainder = stripped.split(":", 1)
                if possible_label.strip() and remainder.strip():
                    label_prefix = possible_label.strip() + ": "
                    instruction_text = remainder.strip()
                elif not remainder.strip():
                    rewritten.append(original)
                    continue

            mnemonic = instruction_text.replace(",", " ").split()[0].lower()
            if mnemonic in _QUANTUM_MNEMONICS:
                word = assemble_quantum_line(instruction_text)
                replacement = f"{label_prefix}.word 0x{word:08x}"
                if marker:
                    replacement += f"  # {comment}"
                rewritten.append(replacement)
            else:
                rewritten.append(original)

        super().load_program("\n".join(rewritten))
        self.quantum_state = BonusStatevector(seed=self.seed, max_qubits=self.max_qubits)
        self.quantum_log = []
        self.measurement_results = []

        for op, args in self.instructions:
            if op == ".word":
                if len(args) != 1:
                    raise ValueError(".word requires exactly one 32-bit value")
                try:
                    word = int(args[0], 0)
                except ValueError as exc:
                    raise ValueError(f"invalid .word value: {args[0]!r}") from exc
                decode_instruction(word)

    def _execute_quantum_word(self, word_text: str, *, pc: int) -> None:
        try:
            word = int(word_text, 0)
        except ValueError as exc:
            raise ValueError(f"invalid .word value: {word_text!r}") from exc
        instruction = decode_instruction(word)
        entry: Dict[str, Any] = {
            "pc": pc,
            "machine_word": f"0x{word:08x}",
            "mnemonic": instruction.mnemonic,
            "register_operands": instruction.to_assembly().split(maxsplit=1)[1],
        }
        first_value = self.get_register(f"x{instruction.rs1}")
        if instruction.operand_form == "init":
            self.quantum_state.initialize(first_value)
            entry["initialized_qubits"] = first_value
        elif instruction.operand_form == "single":
            entry["resolved_qubits"] = [first_value]
            self.quantum_state.apply_single(instruction.mnemonic, first_value)
        elif instruction.operand_form == "double":
            second_value = self.get_register(f"x{instruction.rs2}")
            entry["resolved_qubits"] = [first_value, second_value]
            self.quantum_state.apply_double(
                instruction.mnemonic, first_value, second_value
            )
        elif instruction.operand_form == "rotation":
            raw_angle = self.get_register(f"x{instruction.rs2}")
            angle = fixed_to_radians(raw_angle)
            entry["resolved_qubits"] = [first_value]
            entry["angle_q16_16"] = raw_angle
            entry["angle_radians"] = angle
            self.quantum_state.apply_rotation(instruction.mnemonic, first_value, angle)
        elif instruction.operand_form == "triple":
            second_value = self.get_register(f"x{instruction.rs2}")
            third_value = self.get_register(f"x{instruction.rd}")
            entry["resolved_qubits"] = [first_value, second_value, third_value]
            self.quantum_state.apply_triple(
                instruction.mnemonic, first_value, second_value, third_value
            )
        else:
            entry["resolved_qubits"] = [first_value]
            result = self.quantum_state.measure(first_value)
            self.set_register(f"x{instruction.rd}", result)
            measurement = {
                "qubit": first_value,
                "destination_register": instruction.rd,
                "value": result,
            }
            self.measurement_results.append(measurement)
            entry["measurement"] = measurement
        self.quantum_log.append(entry)

    def execute(self) -> Dict[str, int]:
        """Execute the mixed program and return official-style nonzero GPR state."""

        steps = 0
        num_instr = len(self.instructions)
        while 0 <= self.pc < num_instr:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")

            current_pc = self.pc
            op, args = self.instructions[current_pc]
            next_pc = current_pc + 1

            if op == ".word":
                if len(args) != 1:
                    raise ValueError(".word requires exactly one 32-bit value")
                self._execute_quantum_word(args[0], pc=current_pc)
            elif op == "li":
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
            elif op == "beq":
                rs1, rs2, label = args[0], args[1], args[2]
                if self.get_register(rs1) == self.get_register(rs2):
                    if label not in self.labels:
                        raise ValueError(f"未定义的跳转标签: {label}")
                    next_pc = self.labels[label]
            elif op == "bne":
                rs1, rs2, label = args[0], args[1], args[2]
                if self.get_register(rs1) != self.get_register(rs2):
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
            self.pc = next_pc

        return {
            f"x{index}": value
            for index, value in enumerate(self.registers)
            if value != 0
        }

    def execution_report(self) -> Dict[str, Any]:
        """Return a JSON-serializable local execution record for inspection."""

        return {
            "engine": "loomq_bonus_tinyriscv_statevector",
            "hardware_execution": False,
            "registers": {
                f"x{index}": value
                for index, value in enumerate(self.registers)
                if value != 0
            },
            "quantum_operations": deepcopy(self.quantum_log),
            "measurements": deepcopy(self.measurement_results),
            "basis_probabilities": self.quantum_state.probabilities(),
        }
