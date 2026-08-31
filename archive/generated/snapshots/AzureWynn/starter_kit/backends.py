#!/usr/bin/env python3
"""L1 backends as Strategy classes behind a small Factory registry.

Each backend implements two capabilities:
  transpile(pc)      -> target-native IR text (per target_ir_contract.md)
  run_raw(pc, shots) -> raw counts keyed by qubit index order (backend native)

The dispatcher in adapter.py then normalizes raw counts into the unified
little-endian clbit schema, so bit-order handling is a single point per backend
and never leaks into callers.

Verified 2026-08-17 against local simulators:
  spinq   -> spinqit Taurus simulator (counts big-endian)
  originq -> pyqpanda CPUQVM          (counts little-endian)
  braket  -> AWS LocalSimulator       (counts big-endian)
"""

import math
from abc import ABC, abstractmethod
from typing import Dict

try:
    from .qasm_parser import ParsedCircuit, fmt_decimal, fmt_param
except ImportError:
    from qasm_parser import ParsedCircuit, fmt_decimal, fmt_param

_QASM2_GATES = {
    "h": "h", "x": "x", "s": "s", "sdg": "sdg", "t": "t", "tdg": "tdg",
    "rz": "rz", "ry": "ry", "cx": "cx", "cu1": "cu1",
    "swap": "swap", "ccx": "ccx",
}
_QASM3_GATES = {
    "h": "h", "x": "x", "s": "s", "sdg": "sdg", "t": "t", "tdg": "tdg",
    "rz": "rz", "ry": "ry", "cx": "cnot", "cu1": "cphase",
    "swap": "swap", "ccx": "ccx",
}
_ORIGINIR_GATES = {
    "h": "H", "x": "X", "s": "S", "sdg": "SDAG", "t": "T", "tdg": "TDAG",
    "rz": "RZ", "ry": "RY", "cx": "CNOT", "cu1": "CU1",
    "swap": "SWAP", "ccx": "TOFFOLI",
}


def _render_gate(gate: str, params, qubits, fmt) -> str:
    head = gate
    if params:
        head += "(" + ",".join(fmt(p) for p in params) + ")"
    args = ", ".join("q[%d]" % qi for qi in qubits)
    return "%s %s" % (head, args)


class BackendStrategy(ABC):
    """Strategy: uniform interface over one quantum backend (target IR + run)."""

    target: str = ""
    backend_id: str = ""
    raw_is_big_endian: bool = True

    @abstractmethod
    def transpile(self, pc: ParsedCircuit) -> str:
        """Render the parsed circuit as this backend's native IR text."""

    @abstractmethod
    def run_raw(self, pc: ParsedCircuit, shots: int) -> Dict[str, int]:
        """Execute on the local simulator; return counts in backend key order."""


class SpinQBackend(BackendStrategy):
    """量旋 SpinQit Taurus simulator. Target IR: OpenQASM 2.0 (pass-through)."""

    target = "spinq"
    backend_id = "spinq_taurus_simulator"
    raw_is_big_endian = True

    def transpile(self, pc: ParsedCircuit) -> str:
        lines = ["OPENQASM 2.0;", 'include "qelib1.inc";',
                 "qreg q[%d];" % pc.nq, "creg c[%d];" % pc.nc]
        lines.extend(_render_gate(_QASM2_GATES[g], p, qs, fmt_param) + ";"
                     for g, p, qs in pc.ops)
        lines.extend("measure q[%d] -> c[%d];" % (qi, ci) for qi, ci in pc.measures)
        return "\n".join(lines) + "\n"

    def run_raw(self, pc: ParsedCircuit, shots: int) -> Dict[str, int]:
        from spinqit import (Circuit, H, X, S, Sd, T, Td, Rz, Ry,
                             CX, SWAP, CCX, CP, MEASURE)
        from spinqit.backend import check_backend_and_config
        from spinqit.compiler import get_compiler
        from spinqit.algorithm.loss.measurement import MeasureOp

        gates = {"h": H, "x": X, "s": S, "sdg": Sd, "t": T, "tdg": Td,
                 "rz": Rz, "ry": Ry, "cx": CX, "cu1": CP,
                 "swap": SWAP, "ccx": CCX}
        circ = Circuit()
        circ.allocateQubits(pc.nq)
        circ.allocateClbits(pc.nq)
        for g, params, qubits in pc.ops:
            circ.append(gates[g], list(qubits), [], *params)
        for i in range(pc.nq):
            circ.append(MEASURE, [i], [i])
        ir = get_compiler().compile(circ, level=0)
        backend, config = check_backend_and_config("spinq")
        config.configure_shots(shots)
        _, res = backend.evaluate(ir, config, MeasureOp("count"))
        return dict(res.counts)


class OriginQBackend(BackendStrategy):
    """本源 pyqpanda CPUQVM. Target IR: OriginIR.

    pyqpanda has no S-dagger / T-dagger gates, so sdg/tdg are decomposed as
    RZ(-pi/2) / RZ(-pi/4) (equal up to global phase -> same measurement law).
    """

    target = "originq"
    backend_id = "originq_local_simulator"
    raw_is_big_endian = False

    def transpile(self, pc: ParsedCircuit) -> str:
        lines = ["QINIT %d" % pc.nq, "CREG %d" % pc.nc]
        lines.extend(_render_gate(_ORIGINIR_GATES[g], p, qs, fmt_decimal)
                     for g, p, qs in pc.ops)
        lines.extend("MEASURE q[%d], c[%d]" % (qi, ci) for qi, ci in pc.measures)
        return "\n".join(lines) + "\n"

    def run_raw(self, pc: ParsedCircuit, shots: int) -> Dict[str, int]:
        from pyqpanda import (init_quantum_machine, QMachineType, QProg,
                              H, X, S, T, RZ, RY, CNOT, SWAP, Toffoli, CR, measure_all)

        machine = init_quantum_machine(QMachineType.CPU_SINGLE_THREAD)
        q = machine.qAlloc_many(pc.nq)
        c = machine.cAlloc_many(pc.nq)
        prog = QProg()
        for g, params, qubits in pc.ops:
            q0 = qubits[0]
            q1 = qubits[1] if len(qubits) > 1 else None
            if g == "h":
                prog << H(q[q0])
            elif g == "x":
                prog << X(q[q0])
            elif g == "s":
                prog << S(q[q0])
            elif g == "sdg":
                prog << RZ(q[q0], -math.pi / 2)
            elif g == "t":
                prog << T(q[q0])
            elif g == "tdg":
                prog << RZ(q[q0], -math.pi / 4)
            elif g == "rz":
                prog << RZ(q[q0], params[0])
            elif g == "ry":
                prog << RY(q[q0], params[0])
            elif g == "cx":
                prog << CNOT(q[q0], q[q1])
            elif g == "cu1":
                prog << CR(q[q0], q[q1], params[0])
            elif g == "swap":
                prog << SWAP(q[q0], q[q1])
            elif g == "ccx":
                prog << Toffoli(q[q0], q[q1], q[qubits[2]])
        prog << measure_all(q, c)
        return dict(machine.run_with_configuration(prog, shots))


class BraketBackend(BackendStrategy):
    """AWS Braket LocalSimulator. Target IR: OpenQASM 3 (stdgates.inc)."""

    target = "braket"
    backend_id = "braket_local_simulator"
    raw_is_big_endian = True

    def transpile(self, pc: ParsedCircuit) -> str:
        lines = ["OPENQASM 3.0;", 'include "stdgates.inc";',
                 "qubit[%d] q;" % pc.nq, "bit[%d] c;" % pc.nc]
        lines.extend(_render_gate(_QASM3_GATES[g], p, qs, fmt_param) + ";"
                     for g, p, qs in pc.ops)
        if len(pc.measures) == pc.nq and all(qi == ci for qi, ci in pc.measures):
            lines.append("c = measure q;")
        else:
            lines.extend("c[%d] = measure q[%d];" % (ci, qi) for qi, ci in pc.measures)
        return "\n".join(lines) + "\n"

    def run_raw(self, pc: ParsedCircuit, shots: int) -> Dict[str, int]:
        from braket.circuits import Circuit
        from braket.devices import LocalSimulator

        c = Circuit()
        for g, params, qubits in pc.ops:
            q0 = qubits[0]
            q1 = qubits[1] if len(qubits) > 1 else None
            if g == "h":
                c.h(q0)
            elif g == "x":
                c.x(q0)
            elif g == "s":
                c.s(q0)
            elif g == "sdg":
                c.si(q0)
            elif g == "t":
                c.t(q0)
            elif g == "tdg":
                c.ti(q0)
            elif g == "rz":
                c.rz(q0, params[0])
            elif g == "ry":
                c.ry(q0, params[0])
            elif g == "cx":
                c.cnot(q0, q1)
            elif g == "cu1":
                c.cphaseshift(q0, q1, params[0])
            elif g == "swap":
                c.swap(q0, q1)
            elif g == "ccx":
                c.ccnot(q0, q1, qubits[2])
        for i in range(pc.nq):
            c.measure(i)
        res = LocalSimulator().run(c, shots=shots).result()
        return dict(res.measurement_counts)


# --- Factory: target -> Strategy ---------------------------------------------

_BACKENDS = {backend.target: backend for backend in (
    SpinQBackend(), OriginQBackend(), BraketBackend(),
)}


def get_backend(target: str) -> BackendStrategy:
    """Factory entry point: resolve a backend strategy by target name."""
    try:
        return _BACKENDS[target]
    except KeyError:
        raise ValueError("unknown target: %r" % target)


def supported_targets():
    return tuple(_BACKENDS)