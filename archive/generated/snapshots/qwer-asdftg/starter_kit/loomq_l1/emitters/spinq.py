"""SpinQ OpenQASM 2.0 emitter."""

from ..model import Circuit
from . import _VALIDATION_TOKEN, _format_parameter, _validate_circuit


def _render_spinq(circuit: Circuit) -> str:
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{circuit.num_qubits}];",
        f"creg c[{circuit.num_clbits}];",
    ]
    for operation in circuit.operations:
        operands = ", ".join(f"q[{index}]" for index in operation.qubits)
        if operation.parameter is None:
            lines.append(f"{operation.name} {operands};")
        else:
            lines.append(
                f"{operation.name}({_format_parameter(operation.parameter)}) {operands};"
            )
    lines.extend(
        f"measure q[{measurement.qubit}] -> c[{measurement.cbit}];"
        for measurement in circuit.measurements
    )
    return "\n".join(lines) + "\n"


def emit_spinq(circuit: Circuit, *, _validation_token: object = None) -> str:
    """Emit *circuit* as the SpinQ OpenQASM 2.0 subset."""
    if _validation_token is not _VALIDATION_TOKEN:
        circuit = _validate_circuit(circuit)
    return _render_spinq(circuit)


__all__ = ["emit_spinq"]
