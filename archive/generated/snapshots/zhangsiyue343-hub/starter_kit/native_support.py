#!/usr/bin/env python3
"""Shared helpers for native-SDK backend plugins.

Each plugin prefers its platform SDK when importable in the running
interpreter and transparently falls back to the built-in statevector engine
otherwise — callers never care which path produced the counts. Gate names
come from gates.py's sdk column, so per-plugin code only encodes each SDK's
call shapes.
"""

from __future__ import annotations

import importlib.util
from typing import Optional

try:
    from .gates import GATES
    from .ir import Circuit
    from .normalize import normalize_counts
    from .simulator import run_circuit as _simulate
except ImportError:
    from gates import GATES
    from ir import Circuit
    from normalize import normalize_counts
    from simulator import run_circuit as _simulate


def sdk_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


def builtin_outcome(circuit: Circuit, shots: int, seed: Optional[int] = None):
    """Execute on the internal engine and package an honest outcome."""
    from plugin_loader import ExecutionOutcome
    rng = None
    if seed is not None:
        from random import Random
        rng = Random(seed)
    counts = _simulate(circuit, shots, rng=rng)
    return ExecutionOutcome("loomq_statevector", "builtin:statevector", dict(counts))


# --------------------------------------------------------------------------
# Real-machine support: credentials always arrive via LoomqConfig.backends
# (environment variables only — see config.BackendsConfig). When the user
# explicitly asks for a real device we attempt the platform SDK and report
# failures honestly; we never silently substitute simulation for a requested
# hardware run.
# --------------------------------------------------------------------------

def resolve_execution_plan(backend_id: str, sdk_module: str,
                           has_credential: bool, prefer_real: bool) -> str:
    """Pure decision helper -> one of "cloud" | "sdk-local" | "builtin"."""
    if prefer_real and has_credential:
        return "cloud"
    if sdk_available(sdk_module):
        return "sdk-local"
    return "builtin"


def _require(module_name: str, backend_id: str, purpose: str):
    if not sdk_available(module_name):
        raise RuntimeError(
            "%s 需要 %s 包（当前解释器未安装）。请改用 Python 3.10 环境，"
            "例如：uv pip install --python 3.10 %s"
            % (purpose, module_name, module_name))


def run_spinq_cloud(circuit: Circuit, shots: int, token: str):
    """Submit to SpinQ cloud (Taurus superconducting QPU). Best-effort adapter
    against the spinqit cloud API; raises instead of ever faking results."""
    _require("spinqit", "spinq", "SpinQ 真机提交")
    try:
        from spinqit import CloudClient  # type: ignore[attr-defined]
    except ImportError as exc:
        raise RuntimeError(
            "当前 spinqit 版本未提供 CloudClient；请查阅量旋云文档确认 SDK 版本，"
            "或使用平台控制台手动生成真机证据。") from exc
    client = CloudClient(token=token)
    circ = build_spinqit_circuit(circuit)
    compiler = __import__("spinqit").compiler.Compiler(client=client)
    exe = compiler.compile(circ, 0)
    result = exe.run(shots=shots)
    raw = getattr(result, "counts", None) or dict(result)
    job_id = str(getattr(result, "task_id", getattr(result, "job_id", "")) or "")
    from plugin_loader import ExecutionOutcome
    normalized = normalize_native({str(k): int(v) for k, v in raw.items()},
                                  big_endian=True, circuit=circuit)
    return ExecutionOutcome(job_id or "spinq-cloud-unknown",
                            "native:spinq-cloud", normalized)


def run_originq_cloud(circuit: Circuit, shots: int, token: str):
    """Submit to OriginQ cloud (Wukong 72-qubit QPU) via pyqpanda QCloud."""
    _require("pyqpanda", "originq", "本源悟空真机提交")
    pyqpanda = _pyqpanda()
    qcloud_url = "https://qcloud.originqc.com"
    machine = pyqpanda.QCloud()
    machine.init_qcloud(token, qcloud_url)
    try:
        qubits = machine.get_allocate_qubits(circuit.n_qubits)[0]
        clbits = machine.allocate_cbits(circuit.n_clbits) \
            if hasattr(machine, "allocate_cbits") else \
            [machine.cAlloc() for _ in range(circuit.n_clbits)]
        program = build_pyqpanda_program(circuit, qubits, clbits)
        result = machine.run_with_configuration(program, clbits, shots)
        job_id = str(getattr(machine, "get_task_id", lambda: "")() or "")
    finally:
        try:
            machine.finalize()
        except Exception:
            pass
    from plugin_loader import ExecutionOutcome
    normalized = normalize_native({str(k): int(v) for k, v in result.items()},
                                  big_endian=False, circuit=circuit)
    return ExecutionOutcome(job_id or "originq-cloud-unknown",
                            "native:wukong-cloud", normalized)


def normalize_native(raw_counts: dict, big_endian: bool,
                     circuit: Circuit) -> dict[str, int]:
    measures = circuit.measures or [(i, i) for i in range(circuit.n_qubits)]
    return normalize_counts(
        {str(k): int(v) for k, v in raw_counts.items()},
        big_endian=big_endian,
        measures=measures,
        n_clbits=circuit.n_clbits,
        n_qubits=circuit.n_qubits,
    )


# sdg/tdg have no pyqpanda primitive; canonical RZ lowerings (global phase only).
PYQPANDA_DECOMPOSE = {
    "sdg": (("rz", (-__import__("math").pi / 2,), (0,)),),
    "tdg": (("rz", (-__import__("math").pi / 4,), (0,)),),
}


def build_pyqpanda_program(circuit: Circuit, qubits, clbits):
    import math as _math
    from pyqpanda import QProg

    program = QProg()
    constructors = {name: getattr(_pyqpanda(), defn.sdk["pyqpanda"])
                    for name, defn in GATES.items() if defn.sdk.get("pyqpanda")}
    measure = _pyqpanda().measure

    def emit(gate: str, params, targets):
        if gate == "sdg" or gate == "tdg":
            sub_gate, sub_params, sub_targets = PYQPANDA_DECOMPOSE[gate][0]
            program << constructors[sub_gate](qubits[targets[sub_targets[0]]],
                                              sub_params[0])
            return
        constructor = constructors[gate]
        if len(params) == 1 and len(targets) == 1:
            program << constructor(qubits[targets[0]], params[0])
        elif len(params) == 1:
            program << constructor(qubits[targets[0]], qubits[targets[1]],
                                   params[0])
        else:
            program << constructor(*(qubits[t] for t in targets))

    for gate, params, targets in circuit.ops:
        emit(gate, params, targets)

    if circuit.measures:
        for qi, ci in circuit.measures:
            program << measure(qubits[qi], clbits[ci])
    else:
        program << _pyqpanda().measure_all(qubits, clbits)
    return program


_PYQPANDA_MODULE = None


def _pyqpanda():
    global _PYQPANDA_MODULE
    if _PYQPANDA_MODULE is None:
        import pyqpanda
        _PYQPANDA_MODULE = pyqpanda
    return _PYQPANDA_MODULE


def build_spinqit_circuit(circuit: Circuit):
    spinqit = _spinqit()
    symbols = {}
    for name, defn in GATES.items():
        attr = defn.sdk["spinqit"]
        root = attr.split(".")[0]
        holder = spinqit
        try:
            symbols[name] = getattr(holder, attr)
        except AttributeError:
            continue
    circ = spinqit.Circuit()
    circ.allocateQubits(circuit.n_qubits)
    circ.allocateClbits(circuit.n_clbits)
    for gate, params, targets in circuit.ops:
        if gate not in symbols:
            raise ValueError("spinqit cannot execute gate %r" % gate)
        circ.append(symbols[gate], list(targets), [], *params)
    measures = circuit.measures or [(i, i) for i in range(circuit.n_qubits)]
    for qi, ci in measures:
        circ.append(spinqit.MEASURE, [qi], [ci])
    return circ


_SPINQIT_MODULE = None


def _spinqit():
    global _SPINQIT_MODULE
    if _SPINQIT_MODULE is None:
        import spinqit
        _SPINQIT_MODULE = spinqit
    return _SPINQIT_MODULE


def build_braket_circuit(circuit: Circuit):
    from braket.circuits import Circuit

    circ = Circuit()
    for gate, params, targets in circuit.ops:
        name = GATES[gate].sdk["braket"]
        method = getattr(circ, name)
        if params:
            method(*targets, *params)
        else:
            method(*targets)
    measured = sorted({qi for qi, _ci in
                       (circuit.measures or [(i, i) for i in range(circuit.n_qubits)])})
    for qi in measured:
        circ.measure(qi)
    return circ
