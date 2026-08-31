"""Compile existing L3 output into the isolated quantum RISC-V extension."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from .encoding import (
    GATE_BY_QASM_NAME,
    MNEMONIC_BY_GATE,
    PARAMETER_GATES,
    GateCode,
    QuantumEncodingError,
    decode_word,
    encode_gate,
    encode_parameter,
    instruction_to_assembly,
)

try:
    from ..L3.quantum import parse_hybrid_program
    from ..L3.riscv_compiler import compile_riscv
    from ..qasm_L1.parser import parse_qasm
except ImportError:
    from L3.quantum import parse_hybrid_program
    from L3.riscv_compiler import compile_riscv
    from qasm_L1.parser import parse_qasm


_DECLARATION = re.compile(
    r"\b(?:qreg|creg)\s+[A-Za-z_]\w*\s*\[\s*\d+\s*\]\s*;",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class QuantumRISCVProgram:
    quantum_words: Tuple[int, ...]
    quantum_assembly: str
    classical_assembly: str
    qubit_count: int
    classical_bit_count: int

    @property
    def combined_assembly(self) -> str:
        return self.quantum_assembly + self.classical_assembly

    @property
    def machine_code_hex(self) -> Tuple[str, ...]:
        return tuple("0x%08x" % word for word in self.quantum_words)


def compile_quantum_riscv(hybrid_qasm_str: str) -> QuantumRISCVProgram:
    """Encode all L1 quantum gates and retain the existing L3 classical code."""
    hybrid = parse_hybrid_program(hybrid_qasm_str)
    classical_assembly = compile_riscv(
        hybrid.classical_statements, hybrid.classical_bit_count
    )

    declarations = _extract_declarations(hybrid_qasm_str)
    layout = parse_qasm(declarations)
    if layout.qubit_count < 1 or layout.qubit_count > 31:
        raise QuantumEncodingError("quantum RISC-V supports 1..31 encoded qubits")

    words: List[int] = []
    assembly: List[str] = []

    def emit(word: int) -> None:
        words.append(word)
        assembly.append(instruction_to_assembly(decode_word(word)))

    emit(encode_gate(GateCode.QINIT, q0=layout.qubit_count))
    for operation in hybrid.quantum_operations:
        parsed = parse_qasm(declarations + "\n" + operation)
        if len(parsed.gates) == 1 and not parsed.measurements:
            gate = parsed.gates[0]
            try:
                gate_code = GATE_BY_QASM_NAME[gate.name]
            except KeyError as exc:
                raise QuantumEncodingError(
                    "no custom encoding for gate: %s" % gate.name
                ) from exc
            if gate_code in PARAMETER_GATES:
                emit(encode_parameter(gate.params[0]))
            qubits = [qubit.global_index for qubit in gate.qubits]
            emit(_encode_gate_application(gate_code, qubits))
            continue

        if len(parsed.measurements) == 1 and not parsed.gates:
            measurement = parsed.measurements[0]
            for qubit, cbit in zip(measurement.qubits, measurement.cbits):
                emit(
                    encode_gate(
                        GateCode.MEASURE,
                        q0=qubit.global_index,
                        rd=10 + cbit.global_index,
                    )
                )
            continue

        raise QuantumEncodingError(
            "quantum operation must contain exactly one gate or measurement: %s"
            % operation
        )

    return QuantumRISCVProgram(
        quantum_words=tuple(words),
        quantum_assembly="\n".join(assembly) + "\n",
        classical_assembly=classical_assembly,
        qubit_count=layout.qubit_count,
        classical_bit_count=hybrid.classical_bit_count,
    )


def _extract_declarations(source: str) -> str:
    without_comments = re.sub(r"//[^\n]*", "", source)
    declarations = _DECLARATION.findall(without_comments)
    if not declarations:
        raise QuantumEncodingError("Hybrid-QASM contains no register declarations")
    return "\n".join(declarations) + "\n"


def _encode_gate_application(gate: GateCode, qubits: List[int]) -> int:
    if len(qubits) == 1:
        return encode_gate(gate, q0=qubits[0])
    if len(qubits) == 2:
        return encode_gate(gate, q0=qubits[0], q1=qubits[1])
    if len(qubits) == 3:
        return encode_gate(gate, q0=qubits[0], q1=qubits[1], rd=qubits[2])
    raise QuantumEncodingError(
        "%s has unsupported arity %d"
        % (MNEMONIC_BY_GATE[gate], len(qubits))
    )
