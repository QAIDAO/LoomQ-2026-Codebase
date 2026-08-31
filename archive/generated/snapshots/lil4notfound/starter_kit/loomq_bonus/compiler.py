"""Isolated compiler path for the optional quantum RISC-V extension."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

try:
    from ..loomq_core.model import Circuit
    from ..loomq_core.qasm2 import parse_qasm2
    from ..loomq_hybrid import compile_hybrid_program
except ImportError:
    from loomq_core.model import Circuit
    from loomq_core.qasm2 import parse_qasm2
    from loomq_hybrid import compile_hybrid_program

from .encoder import encode_assembly, machine_hex
from .isa import angle_to_units


_DECLARATION = re.compile(
    r"\b(?:qreg|creg)\s+[A-Za-z_]\w*\s*\[\s*\d+\s*\]\s*;",
    re.IGNORECASE,
)
_COMMENTS = re.compile(r"/\*.*?\*/|//[^\r\n]*", re.DOTALL)
_GATE_MNEMONICS = {
    "h": "qh",
    "x": "qx",
    "s": "qs",
    "sdg": "qsdg",
    "t": "qt",
    "tdg": "qtdg",
    "ry": "qry",
    "rz": "qrz",
    "cx": "qcx",
    "cu1": "qcu1",
    "swap": "qswap",
    "ccx": "qccx",
}


@dataclass(frozen=True)
class QuantumBonusProgram:
    quantum_operations: Tuple[str, ...]
    classical_assembly: str
    quantum_assembly: str
    machine_words: Tuple[int, ...]

    @property
    def machine_hex(self) -> Tuple[str, ...]:
        return machine_hex(self.machine_words)

    @property
    def combined_assembly(self) -> str:
        return self.quantum_assembly + self.classical_assembly


def compile_quantum_qasm(source: str) -> QuantumBonusProgram:
    """Compile standard OpenQASM 2.0 into the optional quantum instruction stream."""
    circuit = parse_qasm2(source)
    assembly = _circuit_assembly(circuit)
    operations = _circuit_operations(circuit)
    return QuantumBonusProgram(operations, "", assembly, encode_assembly(assembly))


def compile_hybrid_bonus(source: str) -> QuantumBonusProgram:
    """Compile Hybrid-QASM without changing the base compile_hybrid contract."""
    quantum_operations, classical_assembly = compile_hybrid_program(source)
    circuit_source = _qasm_from_hybrid(source, quantum_operations)
    circuit = parse_qasm2(circuit_source)
    quantum_assembly = _circuit_assembly(circuit)
    return QuantumBonusProgram(
        tuple(quantum_operations),
        classical_assembly,
        quantum_assembly,
        encode_assembly(quantum_assembly),
    )


def _qasm_from_hybrid(source: str, operations: List[str]) -> str:
    uncommented = _COMMENTS.sub("", source)
    declarations = _DECLARATION.findall(uncommented)
    if not declarations:
        raise ValueError("Hybrid-QASM contains no register declarations")
    return "\n".join(
        ['OPENQASM 2.0;', 'include "qelib1.inc";']
        + [item.strip() for item in declarations]
        + list(operations)
    ) + "\n"


def _circuit_assembly(circuit: Circuit) -> str:
    lines = [f"qinit {circuit.qubit_count}"]
    for operation in circuit.operations:
        mnemonic = _GATE_MNEMONICS[operation.name]
        qubits = tuple(circuit.quantum_index(item) for item in operation.qubits)
        if operation.parameter is not None:
            lines.append(f"qparam {angle_to_units(operation.parameter)}")
        lines.append(f"{mnemonic} " + ", ".join(str(item) for item in qubits))
    for measurement in circuit.measurements:
        qubit = circuit.quantum_index(measurement.qubit)
        register = 10 + circuit.classical_index(measurement.classical)
        if register > 31:
            raise ValueError("Quantum measurement cannot be mapped beyond RISC-V x31")
        lines.append(f"qmeasure {qubit}, x{register}")
    return "\n".join(lines) + "\n"


def _circuit_operations(circuit: Circuit) -> Tuple[str, ...]:
    operations = []
    for operation in circuit.operations:
        parameter = ""
        if operation.parameter is not None:
            parameter = f"({format(operation.parameter, '.17g')})"
        qubits = ", ".join(
            f"{item.register}[{item.index}]" for item in operation.qubits
        )
        operations.append(f"{operation.name}{parameter} {qubits};")
    for measurement in circuit.measurements:
        operations.append(
            f"measure {measurement.qubit.register}[{measurement.qubit.index}] -> "
            f"{measurement.classical.register}[{measurement.classical.index}];"
        )
    return tuple(operations)
