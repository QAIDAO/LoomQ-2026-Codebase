#!/usr/bin/env python3
"""本源 OriginQ plugin — OriginIR dialect.

Native path: pyqpanda CPUQVM (little-endian counts; sdg/tdg lowered to RZ).
Fallback: internal statevector engine.
"""

from __future__ import annotations

try:
    from ..native_support import (builtin_outcome, normalize_native,
                                  sdk_available, build_pyqpanda_program,
                                  resolve_execution_plan, run_originq_cloud)
    from ..plugin_loader import BackendPlugin, ExecutionOutcome
    from ..targets import EMITTERS
except (ImportError, ValueError):
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.dirname(
        _os.path.dirname(_os.path.abspath(__file__))))
    from native_support import (builtin_outcome, normalize_native,
                                sdk_available, build_pyqpanda_program,
                                resolve_execution_plan, run_originq_cloud)
    from plugin_loader import BackendPlugin, ExecutionOutcome
    from targets import EMITTERS


def _run(circuit, shots: int, config) -> ExecutionOutcome:
    backends = getattr(config, "backends", None)
    has_token = bool(getattr(backends, "originq_token", ""))
    prefer_real = bool(getattr(backends, "prefer_real_machine", False))
    plan = resolve_execution_plan("originq", "pyqpanda",
                                  has_token, prefer_real)
    if plan == "cloud":
        return run_originq_cloud(circuit, shots, backends.originq_token)
    if plan == "sdk-local":
        try:
            from pyqpanda import init_quantum_machine, QMachineType

            machine = init_quantum_machine(QMachineType.CPU_SINGLE_THREAD)
            try:
                qubits = machine.qAlloc_many(circuit.n_qubits)
                clbits = machine.cAlloc_many(circuit.n_clbits)
                program = build_pyqpanda_program(circuit, qubits, clbits)
                raw = dict(machine.run_with_configuration(program, shots))
            finally:
                machine.qFree_all()
            counts = normalize_native(raw, False, circuit)
            return ExecutionOutcome("originq_local_simulator", "native:pyqpanda", counts)
        except ImportError:
            pass
    return builtin_outcome(circuit, shots)


def register() -> BackendPlugin:
    return BackendPlugin(
        target="originq",
        backend_id="originq_local_simulator",
        dialect="originir",
        display_name="本源 pyqpanda 本地模拟器（CPUQVM）",
        capabilities={
            "kind": "simulator",
            "max_qubits": 30,
            "queue": "none",
            "cost": "free",
            "requires_account": False,
            "notes": "上限受本机内存约束，30 为评测基准值；可接悟空真机 72 比特",
        },
        emit=EMITTERS["originir"],
        run=_run,
    )
