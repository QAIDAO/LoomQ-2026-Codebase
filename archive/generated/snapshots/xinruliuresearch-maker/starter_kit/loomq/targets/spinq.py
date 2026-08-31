"""SpinQ contract emitter: complete normalized OpenQASM 2.0."""

from typing import Any

from .base import format_angle, format_operands, gate_fields, is_measurement, measurement_fields


def emit(circuit: Any) -> str:
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[%d];" % circuit.qubit_count,
        "creg c[%d];" % circuit.classical_count,
    ]
    for operation in circuit.operations:
        if is_measurement(operation):
            qubit, cbit = measurement_fields(operation)
            lines.append("measure q[%d] -> c[%d];" % (qubit, cbit))
            continue
        name, params, qubits = gate_fields(operation)
        parameter = "(%s)" % format_angle(params[0]) if params else ""
        lines.append("%s%s %s;" % (name, parameter, format_operands(qubits)))
    return "\n".join(lines) + "\n"
