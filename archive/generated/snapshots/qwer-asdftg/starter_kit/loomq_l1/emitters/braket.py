"""AWS Braket OpenQASM 3.0 emitter."""

from ..model import Circuit
from . import _VALIDATION_TOKEN, _format_parameter, _validate_circuit


_GATE_NAMES = {
    "cx": "cnot",
    "cu1": "cp",
}


def _render_braket(circuit: Circuit) -> str:
    lines = [
        "OPENQASM 3.0;",
        'include "stdgates.inc";',
        f"bit[{circuit.num_clbits}] c;",
        f"qubit[{circuit.num_qubits}] q;",
    ]
    for operation in circuit.operations:
        operands = ", ".join(f"q[{index}]" for index in operation.qubits)
        gate = _GATE_NAMES.get(operation.name, operation.name)
        if operation.parameter is None:
            lines.append(f"{gate} {operands};")
        else:
            lines.append(f"{gate}({_format_parameter(operation.parameter)}) {operands};")
    lines.extend(
        f"c[{measurement.cbit}] = measure q[{measurement.qubit}];"
        for measurement in circuit.measurements
    )
    return "\n".join(lines) + "\n"


def emit_braket(circuit: Circuit, *, _validation_token: object = None) -> str:
    """Emit *circuit* as AWS Braket OpenQASM 3.0."""
    if _validation_token is not _VALIDATION_TOKEN:
        circuit = _validate_circuit(circuit)
    return _render_braket(circuit)


__all__ = ["emit_braket"]
