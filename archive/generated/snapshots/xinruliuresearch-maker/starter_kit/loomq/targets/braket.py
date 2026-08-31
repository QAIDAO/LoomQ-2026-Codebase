"""Amazon Braket contract emitter: complete OpenQASM 3.0."""

from typing import Any

from .base import format_angle, format_operands, gate_fields, is_measurement, measurement_fields


GATE_NAMES = {"cx": "cnot", "cu1": "cp"}


def emit(circuit: Any) -> str:
    lines = [
        "OPENQASM 3.0;",
        'include "stdgates.inc";',
        "qubit[%d] q;" % circuit.qubit_count,
        "bit[%d] c;" % circuit.classical_count,
    ]
    for operation in circuit.operations:
        if is_measurement(operation):
            qubit, cbit = measurement_fields(operation)
            lines.append("c[%d] = measure q[%d];" % (cbit, qubit))
            continue
        name, params, qubits = gate_fields(operation)
        native_name = GATE_NAMES.get(name, name)
        parameter = "(%s)" % format_angle(params[0]) if params else ""
        lines.append("%s%s %s;" % (native_name, parameter, format_operands(qubits)))
    return "\n".join(lines) + "\n"
