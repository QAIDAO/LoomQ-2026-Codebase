"""Serialize Circuit IR as SpinQ-compatible OpenQASM 2.0."""

from typing import List

from ..ir import (
    Circuit,
    ClassicalBitRef,
    GateOperation,
    MeasureOperation,
    QubitRef,
)


def _qubit(reference: QubitRef) -> str:
    return "%s[%d]" % (reference.register, reference.index)


def _classical_bit(reference: ClassicalBitRef) -> str:
    return "%s[%d]" % (reference.register, reference.index)


def serialize_spinq(circuit: Circuit) -> str:
    """Return a complete OpenQASM 2.0 program for SpinQ."""
    lines: List[str] = ['OPENQASM 2.0;', 'include "qelib1.inc";']
    lines.extend(
        "qreg %s[%d];" % (register.name, register.size)
        for register in circuit.quantum_registers
    )
    lines.extend(
        "creg %s[%d];" % (register.name, register.size)
        for register in circuit.classical_registers
    )

    for operation in circuit.operations:
        if isinstance(operation, GateOperation):
            parameters = ""
            if operation.parameters:
                parameters = "(%s)" % ", ".join(
                    format(value, ".17g") for value in operation.parameters
                )
            lines.append(
                "%s%s %s;"
                % (
                    operation.name,
                    parameters,
                    ", ".join(_qubit(qubit) for qubit in operation.qubits),
                )
            )
        elif isinstance(operation, MeasureOperation):
            if isinstance(operation.quantum, QubitRef) and isinstance(
                operation.classical, ClassicalBitRef
            ):
                lines.append(
                    "measure %s -> %s;"
                    % (_qubit(operation.quantum), _classical_bit(operation.classical))
                )
            elif not isinstance(operation.quantum, QubitRef) and not isinstance(
                operation.classical, ClassicalBitRef
            ):
                lines.append(
                    "measure %s -> %s;"
                    % (operation.quantum.register, operation.classical.register)
                )
            else:
                raise ValueError("invalid mixed-width measurement in Circuit IR")
        else:
            raise TypeError("unsupported operation in Circuit IR: %r" % (operation,))
    return "\n".join(lines) + "\n"
