"""Deterministic last-resort circuit construction from a declared target.

This never inspects the user's prompt. It consumes only the structured target the
model itself declared, so a transient model or network failure after a successful
call does not force an empty answer.
"""

from __future__ import annotations

import math

import numpy as np
from qiskit import QuantumCircuit, qasm2, transpile

try:
    from .normalize import BASIS
    from .reference import reference_distribution
    from .simulate import simulate
    from .verify import fidelity
    from ..parser import parse_qasm
except ImportError:  # pragma: no cover - flat-layout fallback
    from l2.normalize import BASIS
    from l2.reference import reference_distribution
    from l2.simulate import simulate
    from l2.verify import fidelity
    from parser import parse_qasm


MAX_QUBITS = 12


def _program(n: int, body: list[str]) -> str:
    header = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{n}];",
        f"creg c[{n}];",
    ]
    measures = [f"measure q[{i}] -> c[{i}];" for i in range(n)]
    return "\n".join(header + body + measures)


def _w_body(n: int) -> list[str]:
    """Textbook W_n cascade: excite q[0], then hand one excitation down the line.

    Step k splits the remaining weight so exactly 1/n stays on q[k]; the leftover
    branch moves to q[k+1] and clears q[k]. Only ry/cx are used, so the program
    stays inside the LoomQ gate subset and reads like the standard construction.
    """
    body = ["x q[0];"]
    for step in range(n - 1):
        theta = 2.0 * math.acos(math.sqrt(1.0 / (n - step)))
        half = theta / 2.0
        body.extend([
            f"ry({half!r}) q[{step + 1}];",
            f"cx q[{step}],q[{step + 1}];",
            f"ry({-half!r}) q[{step + 1}];",
            f"cx q[{step}],q[{step + 1}];",
            f"cx q[{step + 1}],q[{step}];",
        ])
    return body


def _product_program(distribution: dict[str, float], n: int) -> str | None:
    """Independent qubits, each either fixed or in an even superposition.

    Covers "q[1] stays |1> while the others are superposed", which the generic
    state-preparation path would otherwise answer with a wall of rotations. The
    caller still simulates the result, so a correlated target that happens to
    share these marginals is rejected rather than silently accepted.
    """
    body: list[str] = []
    for qubit in range(n):
        index = n - 1 - qubit  # distribution keys are c[n-1]...c[0]
        weight = sum(
            probability
            for state, probability in distribution.items()
            if state[index] == "1"
        )
        if abs(weight) <= 1e-9:
            continue
        if abs(weight - 1.0) <= 1e-9:
            body.append(f"x q[{qubit}];")
        elif abs(weight - 0.5) <= 1e-9:
            body.append(f"h q[{qubit}];")
        else:
            return None
    return _program(n, body)


def _canonical_program(target: dict, n: int) -> str | None:
    """Textbook constructions, so the fallback stays readable for reviewers."""
    kind = str(target.get("kind", "")).lower()
    if kind in {"bell", "epr"} or (kind == "ghz" and n >= 2):
        return _program(n, ["h q[0];"] + [f"cx q[{i}],q[{i + 1}];" for i in range(n - 1)])
    if kind in {"plus", "uniform", "superposition"}:
        return _program(n, [f"h q[{i}];" for i in range(n)])
    if kind == "w" and n >= 2:
        return _program(n, _w_body(n))
    if kind == "basis":
        state = str(target.get("state", "")).replace("|", "").replace(">", "")
        if len(state) == n and not set(state) - {"0", "1"}:
            # state[0] is c[n-1]; classical bit i maps to qubit i.
            return _program(
                n, [f"x q[{n - 1 - i}];" for i, bit in enumerate(state) if bit == "1"]
            )
    return None


def synthesize(target: dict) -> tuple[str, float] | None:
    """Build a circuit whose measurement distribution matches the declared target.

    Returns (qasm, fidelity) or None when the target is not constructible.
    """
    if not isinstance(target, dict):
        return None

    distribution = reference_distribution(target)
    if not distribution:
        return None

    widths = {len(state) for state in distribution}
    if len(widths) != 1:
        return None
    n = widths.pop()
    if not 1 <= n <= MAX_QUBITS:
        return None

    amplitudes = np.zeros(1 << n, dtype=np.complex128)
    for state, probability in distribution.items():
        if set(state) - {"0", "1"} or probability < 0:
            return None
        # Distribution keys are c[n-1]...c[0], matching little-endian indices.
        amplitudes[int(state, 2)] = math.sqrt(float(probability))

    norm = float(np.linalg.norm(amplitudes))
    if norm <= 0:
        return None
    amplitudes /= norm

    # Readable constructions first; each is simulated before it is trusted, so a
    # mismatched guess falls through to generic state preparation.
    for build in (
        lambda: _canonical_program(target, n),
        lambda: _product_program(distribution, n),
    ):
        try:
            program = build()
        except Exception:
            continue
        if program is None:
            continue
        try:
            score = fidelity(simulate(parse_qasm(program)), distribution)
        except Exception:
            continue
        if score >= 0.999:
            return program.strip(), score

    try:
        circuit = QuantumCircuit(n, n)
        circuit.prepare_state(amplitudes, range(n))
        circuit.measure(range(n), range(n))
        compiled = transpile(circuit, basis_gates=BASIS, optimization_level=1)
        program = qasm2.dumps(compiled)
        score = fidelity(simulate(parse_qasm(program)), distribution)
    except Exception:
        return None

    if score < 0.999:
        return None
    return program.strip(), score
