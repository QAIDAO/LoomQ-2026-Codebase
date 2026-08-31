"""OriginQ contract emitter for the documented OriginIR subset."""

from typing import Any

from .base import format_angle, format_operands, gate_fields, is_measurement, measurement_fields


GATE_NAMES = {
    "h": "H",
    "x": "X",
    "s": "S",
    "sdg": "SDAG",
    "t": "T",
    "tdg": "TDAG",
    "ry": "RY",
    "rz": "RZ",
    "cx": "CNOT",
    "cu1": "CU1",
    "swap": "SWAP",
    "ccx": "TOFFOLI",
}


def emit(circuit: Any) -> str:
    lines = ["QINIT %d" % circuit.qubit_count, "CREG %d" % circuit.classical_count]
    for operation in circuit.operations:
        if is_measurement(operation):
            qubit, cbit = measurement_fields(operation)
            lines.append("MEASURE q[%d], c[%d]" % (qubit, cbit))
            continue
        name, params, qubits = gate_fields(operation)
        native_name = GATE_NAMES[name]
        parameter = "(%s)" % format_angle(params[0]) if params else ""
        lines.append("%s%s %s" % (native_name, parameter, format_operands(qubits)))
    return "\n".join(lines) + "\n"
