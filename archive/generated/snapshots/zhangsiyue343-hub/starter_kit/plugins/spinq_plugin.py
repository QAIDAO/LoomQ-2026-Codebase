#!/usr/bin/env python3
"""量旋 SpinQit plugin — OpenQASM 2.0 dialect.

Native path: spinqit Taurus simulator (big-endian counts).
Fallback: internal statevector engine.
"""

from __future__ import annotations

try:
    from ..native_support import (builtin_outcome, normalize_native,
                                  sdk_available, build_spinqit_circuit,
                                  resolve_execution_plan, run_spinq_cloud)
    from ..plugin_loader import BackendPlugin, ExecutionOutcome
    from ..targets import EMITTERS
except (ImportError, ValueError):
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.dirname(
        _os.path.dirname(_os.path.abspath(__file__))))
    from native_support import (builtin_outcome, normalize_native,
                                sdk_available, build_spinqit_circuit,
                                resolve_execution_plan, run_spinq_cloud)
    from plugin_loader import BackendPlugin, ExecutionOutcome
    from targets import EMITTERS


def _run(circuit, shots: int, config) -> ExecutionOutcome:
    backends = getattr(config, "backends", None)
    has_token = bool(getattr(backends, "spinq_token", ""))
    prefer_real = bool(getattr(backends, "prefer_real_machine", False))
    plan = resolve_execution_plan("spinq", "spinqit", has_token, prefer_real)
    if plan == "cloud":
        return run_spinq_cloud(circuit, shots, backends.spinq_token)
    if plan == "sdk-local":
        try:
            from spinqit.backend import check_backend_and_config
            from spinqit.compiler import get_compiler
            from spinqit.algorithm.loss.measurement import MeasureOp

            circ = build_spinqit_circuit(circuit)
            ir = get_compiler().compile(circ, level=0)
            backend, backend_config = check_backend_and_config("spinq")
            backend_config.configure_shots(shots)
            _, result = backend.evaluate(ir, backend_config, MeasureOp("count"))
            counts = normalize_native(dict(result.counts), True, circuit)
            return ExecutionOutcome("spinq_taurus_simulator", "native:spinqit", counts)
        except ImportError:
            pass
    return builtin_outcome(circuit, shots)


def register() -> BackendPlugin:
    return BackendPlugin(
        target="spinq",
        backend_id="spinq_taurus_simulator",
        dialect="qasm2",
        display_name="量旋 SpinQit Taurus 模拟器",
        capabilities={
            "kind": "simulator",
            "max_qubits": 24,
            "queue": "none",
            "cost": "free",
            "requires_account": False,
            "notes": "pip install spinqit 即用，无需联网；可接量旋云超导真机",
        },
        emit=EMITTERS["qasm2"],
        run=_run,
    )
