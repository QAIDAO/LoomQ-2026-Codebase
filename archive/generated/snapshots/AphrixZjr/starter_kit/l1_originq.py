"""pyQPanda CPUQVM runner for LoomQ L1."""

import uuid
from typing import Any, Dict, Mapping, Optional, Tuple

try:
    from .loomq_l1 import Circuit, emit_originq
except ImportError:
    from loomq_l1 import Circuit, emit_originq


def _load_sdk():
    try:
        import pyqpanda
    except ImportError as exc:
        raise RuntimeError(
            "OriginQ runner requires the pinned pyqpanda dependency"
        ) from exc
    return pyqpanda


def run_originq(
    circuit: Circuit, shots: int
) -> Tuple[Mapping[Any, Any], str, str, Optional[Dict[str, Any]]]:
    sdk = _load_sdk()
    machine = sdk.CPUQVM()
    initialized = False
    try:
        machine.init_qvm()
        initialized = True
        prog, _qubits, cbits = sdk.convert_originir_str_to_qprog(
            emit_originq(circuit), machine
        )
        counts = machine.run_with_configuration(prog, cbits, shots)
        if not isinstance(counts, Mapping):
            raise RuntimeError("pyQPanda CPUQVM returned invalid counts")
        return (
            counts,
            "originq-cpuqvm",
            "originq-local-" + uuid.uuid4().hex,
            {"qubits": circuit.qubit_count, "engine": "pyQPanda CPUQVM"},
        )
    finally:
        if initialized:
            machine.finalize()
