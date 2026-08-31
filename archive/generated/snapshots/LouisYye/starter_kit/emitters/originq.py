try:
    from ..ir import Circuit, Gate
except ImportError:
    from ir import Circuit, Gate


ORIGINQ_GATE_NAMES = {
    "h": "H",
    "x": "X",
    "s": "S",
    "sdg": "SDAG",
    "t": "T",
    "tdg": "TDAG",
    "ry": "RY",
    "rz": "RZ",
    "cx": "CNOT",
    "cu1": "CR",
    "swap": "SWAP",
    "ccx": "TOFFOLI",
}


def _format_param(value: float) -> str:
    return repr(float(value))


def _require_params(gate: Gate, expected: int) -> None:
    if len(gate.params) != expected:
        raise ValueError(
            f"OriginQ gate {gate.name} requires {expected} parameter(s), "
            f"got {len(gate.params)}"
        )


def _emit_execution_gate(gate: Gate) -> list[str]:
    """Emit OriginIR accepted by pyqpanda 3.8.5."""

    qubits = [f"q[{index}]" for index in gate.qubits]

    if gate.name == "sdg":
        return ["DAGGER", f"S {qubits[0]}", "ENDDAGGER"]

    if gate.name == "tdg":
        return ["DAGGER", f"T {qubits[0]}", "ENDDAGGER"]

    if gate.name == "cu1":
        _require_params(gate, 1)
        theta = float(gate.params[0])
        control, target = qubits
        return [
            f"U1 {control},({_format_param(theta / 2.0)})",
            f"CNOT {control}, {target}",
            f"U1 {target},({_format_param(-theta / 2.0)})",
            f"CNOT {control}, {target}",
            f"U1 {target},({_format_param(theta / 2.0)})",
        ]

    target_name = ORIGINQ_GATE_NAMES.get(gate.name)
    if target_name is None:
        raise ValueError(f"Unsupported OriginQ gate: {gate.name}")

    if gate.name in {"ry", "rz"}:
        _require_params(gate, 1)
        return [
            f"{target_name} {qubits[0]},"
            f"({_format_param(gate.params[0])})"
        ]

    _require_params(gate, 0)
    return [f"{target_name} {', '.join(qubits)}"]


def _emit_contract_gate(gate: Gate) -> str:
    """Emit the canonical OriginIR subset required by LoomQ."""

    target_name = ORIGINQ_GATE_NAMES.get(gate.name)
    if target_name is None:
        raise ValueError(f"Unsupported OriginQ gate: {gate.name}")

    qubits = ", ".join(f"q[{index}]" for index in gate.qubits)

    if gate.name in {"ry", "rz", "cu1"}:
        _require_params(gate, 1)
        return (
            f"{target_name} {qubits},"
            f"({_format_param(gate.params[0])})"
        )

    _require_params(gate, 0)
    return f"{target_name} {qubits}"


def emit_originq(
    circuit: Circuit,
    execution_compatible: bool = False,
) -> str:
    """Convert the shared Circuit IR into OriginIR."""

    lines = [
        f"QINIT {circuit.num_qubits}",
        f"CREG {circuit.num_bits}",
    ]

    for gate in circuit.gates:
        if execution_compatible:
            lines.extend(_emit_execution_gate(gate))
        else:
            lines.append(_emit_contract_gate(gate))

    for measurement in circuit.measurements:
        lines.append(
            f"MEASURE q[{measurement.qubit}], c[{measurement.bit}]"
        )

    return "\n".join(lines)
