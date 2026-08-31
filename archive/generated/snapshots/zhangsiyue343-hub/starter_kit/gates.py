#!/usr/bin/env python3
"""Single source of truth for the 12-gate whitelist.

Every consumer — parser validation, dialect emitters, the statevector
simulator, native SDK executors and the agent prompt — reads its facts from
this table instead of keeping private copies. Each GateDef carries:

  * arity / parameter count
  * a dense unitary matrix builder (little-endian bit convention: qubit k of
    a basis index i is `(i >> k) & 1`)
  * spellings in every textual dialect we emit
  * SDK constructor names for the native executors
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, Mapping

Complex = complex
Matrix = tuple[tuple[Complex, ...], ...]


def cmath_rect(real: float, imag: float) -> Complex:
    return complex(real, imag)


def _mat(rows: list[list[Complex]]) -> Matrix:
    return tuple(tuple(row) for row in rows)


def _h() -> Matrix:
    r = 1.0 / math.sqrt(2.0)
    return _mat([[r, r], [r, -r]])


def _x() -> Matrix:
    return _mat([[0, 1], [1, 0]])


def _s() -> Matrix:
    return _mat([[1, 0], [0, 1j]])


def _sdg() -> Matrix:
    return _mat([[1, 0], [0, -1j]])


def _t() -> Matrix:
    return _mat([[1, 0], [0, cmath_rect(math.cos(math.pi / 4), math.sin(math.pi / 4))]])


def _tdg() -> Matrix:
    return _mat([[1, 0], [0, cmath_rect(math.cos(math.pi / 4), -math.sin(math.pi / 4))]])


def _rz(theta: float) -> Matrix:
    return _mat([
        [cmath_rect(math.cos(theta / 2), -math.sin(theta / 2)), 0],
        [0, cmath_rect(math.cos(theta / 2), math.sin(theta / 2))],
    ])


def _ry(theta: float) -> Matrix:
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return _mat([[c, -s], [s, c]])


def _cx() -> Matrix:
    return _mat([
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 0, 1],
        [0, 0, 1, 0],
    ])  # basis |q0 q1> with q0 = control


def _cu1(theta: float) -> Matrix:
    phase = cmath_rect(math.cos(theta), math.sin(theta))
    return _mat([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, phase]])


def _swap() -> Matrix:
    return _mat([
        [1, 0, 0, 0],
        [0, 0, 1, 0],
        [0, 1, 0, 0],
        [0, 0, 0, 1],
    ])


def _ccx() -> Matrix:
    size = 8
    rows = [[0.0] * size for _ in range(size)]
    for i in range(size):
        rows[i][i] = 1
    rows[0b110][0b110] = 0
    rows[0b110][0b111] = 1
    rows[0b111][0b111] = 0
    rows[0b111][0b110] = 1   # controls are q0,q1; target q2
    return _mat(rows)


@dataclass(frozen=True)
class GateDef:
    name: str
    n_qubits: int
    n_params: int
    matrix: Callable[..., Matrix]
    dialect: Mapping[str, str] = field(default_factory=dict)   # target -> spelling
    sdk: Mapping[str, str] = field(default_factory=dict)       # sdk package -> callable/attr name
    note_up_to_phase: str = ""

    def build(self, params: tuple[float, ...]) -> Matrix:
        return self.matrix(*params)


GATES: dict[str, GateDef] = {
    g.name: g
    for g in (
        GateDef("h", 1, 0, _h,
                {"qasm2": "h", "qasm3": "h", "originir": "H"},
                {"spinqit": "H", "pyqpanda": "H", "braket": "h"}),
        GateDef("x", 1, 0, _x,
                {"qasm2": "x", "qasm3": "x", "originir": "X"},
                {"spinqit": "X", "pyqpanda": "X", "braket": "x"}),
        GateDef("s", 1, 0, _s,
                {"qasm2": "s", "qasm3": "s", "originir": "S"},
                {"spinqit": "S", "pyqpanda": "S", "braket": "s"}),
        GateDef("sdg", 1, 0, _sdg,
                {"qasm2": "sdg", "qasm3": "sdg", "originir": "SDAG"},
                {"spinqit": "Sd", "pyqpanda": None, "braket": "si"},
                note_up_to_phase="pyqpanda lacks SDAG; lower to RZ(-pi/2)"),
        GateDef("t", 1, 0, _t,
                {"qasm2": "t", "qasm3": "t", "originir": "T"},
                {"spinqit": "T", "pyqpanda": "T", "braket": "t"}),
        GateDef("tdg", 1, 0, _tdg,
                {"qasm2": "tdg", "qasm3": "tdg", "originir": "TDAG"},
                {"spinqit": "Td", "pyqpanda": None, "braket": "ti"},
                note_up_to_phase="pyqpanda lacks TDAG; lower to RZ(-pi/4)"),
        GateDef("rz", 1, 1, _rz,
                {"qasm2": "rz", "qasm3": "rz", "originir": "RZ"},
                {"spinqit": "Rz", "pyqpanda": "RZ", "braket": "rz"}),
        GateDef("ry", 1, 1, _ry,
                {"qasm2": "ry", "qasm3": "ry", "originir": "RY"},
                {"spinqit": "Ry", "pyqpanda": "RY", "braket": "ry"}),
        GateDef("cx", 2, 0, _cx,
                {"qasm2": "cx", "qasm3": "cnot", "originir": "CNOT"},
                {"spinqit": "CX", "pyqpanda": "CNOT", "braket": "cnot"}),
        GateDef("cu1", 2, 1, _cu1,
                {"qasm2": "cu1", "qasm3": "cphase", "originir": "CU1"},
                {"spinqit": "CP", "pyqpanda": "CR", "braket": "cphaseshift"}),
        GateDef("swap", 2, 0, _swap,
                {"qasm2": "swap", "qasm3": "swap", "originir": "SWAP"},
                {"spinqit": "SWAP", "pyqpanda": "SWAP", "braket": "swap"}),
        GateDef("ccx", 3, 0, _ccx,
                {"qasm2": "ccx", "qasm3": "ccx", "originir": "TOFFOLI"},
                {"spinqit": "CCX", "pyqpanda": "Toffoli", "braket": "ccnot"}),
    )
}

# Lowering rules: gates absent from a backend's primitive set expand into
# these canonical forms (up to global phase, which never affects sampling).
DECOMPOSITIONS: dict[str, tuple[tuple[str, tuple[float, ...], tuple[int, ...]], ...]] = {
    "sdg": (("rz", (-math.pi / 2,), (0,)),),
    "tdg": (("rz", (-math.pi / 4,), (0,)),),
}


def get(name: str) -> GateDef:
    try:
        return GATES[name]
    except KeyError:
        raise ValueError("unknown gate %r" % name) from None


def whitelist_names() -> tuple[str, ...]:
    return tuple(sorted(GATES))


def prompt_whitelist() -> str:
    """Human-readable whitelist used verbatim inside LLM system prompts."""
    return ("h, x, s, sdg, t, tdg (no parameter); rz(theta), ry(theta) "
            "(one parameter); cx, cu1(theta), swap (two qubits); ccx (three qubits)")
