"""Execution runtime for the LoomQ universal transpiler.

transpile(): OpenQASM 2.0 -> a target backend's native circuit text.
run():       execute on the target's local simulator -> unified result schema.

Bit-order note: the result schema requires little-endian count keys (rightmost
character = c[0], the Qiskit convention). Backends disagree on this, so every
run path normalizes here. That normalization IS part of being a "universal"
middle layer, not an afterthought.
"""

import hashlib
import os
import tempfile
from datetime import datetime, timezone

from parser import parse_qasm
from emitters import emit_originir, emit_spinq

SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile(qasm_str, target):
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    ir = parse_qasm(qasm_str)
    if target == "spinq":
        return emit_spinq(ir)
    if target == "originq":
        return emit_originir(ir)
    raise ValueError(f"unsupported target: {target!r} (supported: {SUPPORTED_TARGETS})")


def _normalize_counts(counts, reverse_keys):
    """Return counts as {str: int}, keys reversed to little-endian if needed.

    Reversing can map two backend keys onto the same normalized key, so values
    are summed rather than overwritten.
    """
    merged = {}
    for key, value in counts.items():
        k = str(key)[::-1] if reverse_keys else str(key)
        merged[k] = merged.get(k, 0) + int(value)
    return merged


def _run_spinq(native_qasm, shots):
    """Execute SpinQ-native QASM on the basic (Taurus) local simulator."""
    from spinqit import BasicSimulatorConfig, get_basic_simulator, get_compiler

    # spinqit's QASM compiler reads from a file path. Write to a private temp
    # directory with a fully-closed handle: NamedTemporaryFile can stay locked
    # between close() and a second open on Windows, which breaks the compiler.
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, "circuit.qasm")
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(native_qasm)
        compiled = get_compiler("qasm").compile(path, 0)
    finally:
        try:
            os.remove(path)
            os.rmdir(tmpdir)
        except OSError:
            pass

    engine = get_basic_simulator()
    config = BasicSimulatorConfig()
    config.configure_shots(shots)
    result = engine.execute(compiled, config)
    # SpinQ reports keys big-endian (c[0] leftmost); reverse to little-endian.
    counts = _normalize_counts(result.counts, reverse_keys=True)
    return counts, compiled.qnum


def _run_originq(native_originir, shots):
    """Execute OriginIR on the pyqpanda CPU simulator (CPUQVM)."""
    import pyqpanda as pq

    machine = pq.CPUQVM()
    machine.init_qvm()
    try:
        prog, _qubits, cbits = pq.convert_originir_str_to_qprog(native_originir, machine)
        result = machine.run_with_configuration(prog, cbits, shots)
        # OriginQ already reports little-endian keys, so no reversal is needed.
        counts = _normalize_counts(result, reverse_keys=False)
        return counts, len(cbits)
    finally:
        machine.finalize()


def run(qasm_str, target, shots):
    """Run a circuit and return the unified result schema (little-endian counts)."""
    native = transpile(qasm_str, target)
    if target == "spinq":
        counts, qubits = _run_spinq(native, shots)
        backend = "spinq_taurus_simulator"
    elif target == "originq":
        counts, qubits = _run_originq(native, shots)
        backend = "originq_local_simulator"
    else:
        raise ValueError(f"unsupported target: {target!r} (supported: {SUPPORTED_TARGETS})")

    job_id = f"local-{target}-{hashlib.sha1(native.encode()).hexdigest()[:8]}"
    return {
        "backend": backend,
        "job_id": job_id,
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "meta": {"qubits": qubits},
    }
