"""Amazon Braket LocalSimulator runner for LoomQ L1."""

import math
from typing import Any, Dict, Mapping, Optional, Tuple

try:
    from .loomq_l1 import Circuit
except ImportError:
    from loomq_l1 import Circuit


def _load_sdk():
    try:
        from braket.devices import LocalSimulator
        from braket.ir.openqasm import Program
    except ImportError as exc:
        raise RuntimeError(
            "Braket runner requires the pinned amazon-braket-sdk dependency"
        ) from exc
    return LocalSimulator, Program


def _angle(value: float) -> str:
    text = format(value, ".17g")
    return "0" if text == "-0" else text


def emit_braket_executable(circuit: Circuit) -> str:
    """Emit include-free OpenQASM 3 accepted by Braket runtimes.

    Braket cloud devices expose their supported operations directly and do not
    need ``stdgates.inc``.  Keeping this source shared with LocalSimulator also
    gives paid hardware workflows an offline syntax and bit-order preflight.
    """

    qoffsets: Dict[str, int] = {}
    coffsets: Dict[str, int] = {}
    qtotal = ctotal = 0
    for name, size in circuit.qregs:
        qoffsets[name], qtotal = qtotal, qtotal + size
    for name, size in circuit.cregs:
        coffsets[name], ctotal = ctotal, ctotal + size
    q = lambda bit: "q[%d]" % (qoffsets[bit.register] + bit.index)
    c = lambda bit: "c[%d]" % (coffsets[bit.register] + bit.index)
    lines = ["OPENQASM 3.0;", "qubit[%d] q;" % qtotal, "bit[%d] c;" % ctotal]

    def append(name: str, operands, parameter: Optional[float] = None) -> None:
        suffix = "(%s)" % _angle(parameter) if parameter is not None else ""
        lines.append("%s%s %s;" % (name, suffix, ", ".join(operands)))

    for gate in circuit.gates:
        operands = [q(bit) for bit in gate.qubits]
        if gate.name in {"sdg", "tdg"}:
            append("rz", operands, -math.pi / (2 if gate.name == "sdg" else 4))
        elif gate.name == "cu1":
            angle = gate.params[0]
            append("rz", [operands[0]], angle / 2)
            append("rz", [operands[1]], angle / 2)
            append("cnot", operands)
            append("rz", [operands[1]], -angle / 2)
            append("cnot", operands)
        elif gate.name == "ccx":
            first, second, target = operands
            append("h", [target])
            append("cnot", [second, target])
            append("rz", [target], -math.pi / 4)
            append("cnot", [first, target])
            append("t", [target])
            append("cnot", [second, target])
            append("rz", [target], -math.pi / 4)
            append("cnot", [first, target])
            append("t", [second])
            append("t", [target])
            append("h", [target])
            append("cnot", [first, second])
            append("t", [first])
            append("rz", [second], -math.pi / 4)
            append("cnot", [first, second])
        else:
            name = "cnot" if gate.name == "cx" else gate.name
            append(name, operands, gate.params[0] if gate.params else None)
    lines += ["%s = measure %s;" % (c(item.classical), q(item.qubit)) for item in circuit.measurements]
    return "\n".join(lines) + "\n"


# Backwards-compatible private name retained for existing callers and tests.
_local_source = emit_braket_executable


def _map_counts_to_classical(
    counts: Mapping[Any, Any], circuit: Circuit
) -> Dict[str, Any]:
    coffsets: Dict[str, int] = {}
    offset = 0
    for name, size in circuit.cregs:
        coffsets[name] = offset
        offset += size
    mapped: Dict[str, Any] = {}
    for raw_key, value in counts.items():
        key = str(raw_key).replace(" ", "")
        if len(key) != len(circuit.measurements) or set(key) - {"0", "1"}:
            raise RuntimeError("Braket LocalSimulator returned an invalid counts key")
        classical = ["0"] * circuit.classical_count
        for bit, measurement in zip(key, circuit.measurements):
            index = coffsets[measurement.classical.register] + measurement.classical.index
            classical[index] = bit
        normalized_key = "".join(reversed(classical))
        mapped[normalized_key] = mapped.get(normalized_key, 0) + value
    return mapped


def run_braket(
    circuit: Circuit, shots: int
) -> Tuple[Mapping[Any, Any], str, str, Optional[Dict[str, Any]]]:
    LocalSimulator, Program = _load_sdk()
    task = LocalSimulator().run(
        Program(source=emit_braket_executable(circuit)), shots=shots
    )
    result = task.result()
    counts = result.measurement_counts
    if not isinstance(counts, Mapping):
        raise RuntimeError("Braket LocalSimulator returned invalid counts")

    normalized_order = _map_counts_to_classical(counts, circuit)
    metadata = getattr(result, "task_metadata", None)
    device_id = getattr(metadata, "deviceId", None)
    return (
        normalized_order,
        "braket-local-simulator",
        str(task.id),
        {
            "qubits": circuit.qubit_count,
            "engine": "Amazon Braket LocalSimulator",
            "device_id": device_id or "braket_sv",
        },
    )
