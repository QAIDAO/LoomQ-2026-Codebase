#!/usr/bin/env python3
"""AWS Braket plugin — OpenQASM 3 dialect.

Native path: braket-sdk LocalSimulator (big-endian counts, qubit i at
position i of the raw key).
Fallback: internal statevector engine.
"""

from __future__ import annotations

try:
    from ..native_support import (builtin_outcome, normalize_native,
                                  sdk_available, build_braket_circuit)
    from ..plugin_loader import BackendPlugin, ExecutionOutcome
    from ..targets import EMITTERS
except (ImportError, ValueError):
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.dirname(
        _os.path.dirname(_os.path.abspath(__file__))))
    from native_support import (builtin_outcome, normalize_native,
                                sdk_available, build_braket_circuit)
    from plugin_loader import BackendPlugin, ExecutionOutcome
    from targets import EMITTERS


def _run(circuit, shots: int, config) -> ExecutionOutcome:
    if sdk_available("braket"):
        try:
            from braket.devices import LocalSimulator

            circ = build_braket_circuit(circuit)
            result = LocalSimulator().run(circ, shots=shots).result()
            counts = normalize_native(dict(result.measurement_counts), True, circuit)
            return ExecutionOutcome("braket_local_simulator", "native:braket", counts)
        except ImportError:
            pass
    return builtin_outcome(circuit, shots)


def register() -> BackendPlugin:
    return BackendPlugin(
        target="braket",
        backend_id="braket_local_simulator",
        dialect="qasm3",
        display_name="AWS Braket LocalSimulator",
        capabilities={
            "kind": "simulator",
            "max_qubits": 25,
            "queue": "none",
            "cost": "free",
            "requires_account": False,
            "notes": "随 amazon-braket-sdk 本地运行，无需 AWS 账号",
        },
        emit=EMITTERS["qasm3"],
        run=_run,
    )
