"""SpinQit BasicSimulator runner for LoomQ L1."""

import os
import tempfile
import uuid
from typing import Any, Dict, Mapping, Optional, Tuple

try:
    from .loomq_l1 import Circuit, emit_spinq
except ImportError:
    from loomq_l1 import Circuit, emit_spinq


def _load_sdk():
    try:
        from spinqit import BasicSimulatorConfig, get_basic_simulator, get_compiler
    except ImportError as exc:
        raise RuntimeError(
            "SpinQ runner requires the pinned spinqit dependency"
        ) from exc
    return BasicSimulatorConfig, get_basic_simulator, get_compiler


def _map_counts_to_classical(
    counts: Mapping[Any, Any], circuit: Circuit
) -> Dict[str, Any]:
    """Project SpinQ's q[0]...q[n-1] keys through QASM measurements."""

    qoffsets: Dict[str, int] = {}
    coffsets: Dict[str, int] = {}
    offset = 0
    for name, size in circuit.qregs:
        qoffsets[name] = offset
        offset += size
    offset = 0
    for name, size in circuit.cregs:
        coffsets[name] = offset
        offset += size

    projected: Dict[str, Any] = {}
    for raw_key, value in counts.items():
        key = str(raw_key).replace(" ", "")
        if key.startswith("0b"):
            key = key[2:]
        if len(key) != circuit.qubit_count or set(key) - {"0", "1"}:
            raise RuntimeError("SpinQ BasicSimulator returned an invalid counts key")
        classical = ["0"] * circuit.classical_count
        for measurement in circuit.measurements:
            qindex = qoffsets[measurement.qubit.register] + measurement.qubit.index
            cindex = coffsets[measurement.classical.register] + measurement.classical.index
            classical[cindex] = key[qindex]
        normalized_key = "".join(reversed(classical))
        projected[normalized_key] = projected.get(normalized_key, 0) + value
    return projected


def run_spinq(
    circuit: Circuit, shots: int
) -> Tuple[Mapping[Any, Any], str, str, Optional[Dict[str, Any]]]:
    BasicSimulatorConfig, get_basic_simulator, get_compiler = _load_sdk()
    path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".qasm", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(emit_spinq(circuit))
            path = handle.name
        ir = get_compiler("qasm").compile(path, 0)
        config = BasicSimulatorConfig()
        config.configure_shots(shots)
        result = get_basic_simulator().execute(ir, config)
        counts = result.counts
        if not isinstance(counts, Mapping):
            raise RuntimeError("SpinQ BasicSimulator returned invalid counts")
        return (
            _map_counts_to_classical(counts, circuit),
            "spinq-basic-simulator",
            "spinq-local-" + uuid.uuid4().hex,
            {"qubits": circuit.qubit_count, "engine": "SpinQit BasicSimulator"},
        )
    finally:
        if path is not None:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
