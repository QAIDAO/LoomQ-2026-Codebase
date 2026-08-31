"""OriginQ OriginIR emitter."""

from ..model import Circuit
from . import _VALIDATION_TOKEN, _format_parameter, _validate_circuit


_GATE_NAMES = {
    "h": "H",
    "x": "X",
    "s": "S",
    "sdg": "SDAG",
    "t": "T",
    "tdg": "TDAG",
    "rz": "RZ",
    "ry": "RY",
    "cx": "CNOT",
    "cu1": "CU1",
    "swap": "SWAP",
    "ccx": "TOFFOLI",
}


def _render_originq(circuit: Circuit) -> str:
    lines = [f"QINIT {circuit.num_qubits}", f"CREG {circuit.num_clbits}"]
    for operation in circuit.operations:
        operands = ", ".join(f"q[{index}]" for index in operation.qubits)
        gate = _GATE_NAMES[operation.name]
        if operation.parameter is None:
            lines.append(f"{gate} {operands}")
        else:
            lines.append(f"{gate} {operands}, ({_format_parameter(operation.parameter)})")
    lines.extend(
        f"MEASURE q[{measurement.qubit}], c[{measurement.cbit}]"
        for measurement in circuit.measurements
    )
    return "\n".join(lines) + "\n"


def emit_originq(circuit: Circuit, *, _validation_token: object = None) -> str:
    """Emit *circuit* as OriginQ OriginIR."""
    if _validation_token is not _VALIDATION_TOKEN:
        circuit = _validate_circuit(circuit)
    return _render_originq(circuit)


__all__ = ["emit_originq"]
