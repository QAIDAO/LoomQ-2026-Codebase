"""Independent target-IR readers used for translation validation and tests.

These readers intentionally consume the emitted text again instead of reusing the
source AST.  That catches dropped operands, wrong gate names, index flattening,
and measurement/bit-order mistakes at the serialization boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass

from .ir import Circuit, QASMError, parse_qasm2, strip_comments
from .simulator import exact_probabilities, statevector


@dataclass(frozen=True)
class TranslationCertificate:
    """Machine-checkable receipt for one source-to-target translation."""

    target: str
    source_ir_sha256: str
    target_ir_sha256: str
    operation_trace_equal: bool
    measurement_map_equal: bool
    statevector_distance: float
    probability_delta: float
    tolerance: float
    certificate_sha256: str

    @property
    def verified(self) -> bool:
        return (
            self.operation_trace_equal
            and self.measurement_map_equal
            and self.statevector_distance <= self.tolerance
            and self.probability_delta <= self.tolerance
        )

    def as_dict(self) -> dict[str, object]:
        return {**asdict(self), "verified": self.verified, "equivalence": "global-phase"}


def parse_spinq(text: str) -> Circuit:
    return parse_qasm2(text)


def parse_braket(text: str) -> Circuit:
    statements = [item.strip() for item in strip_comments(text).split(";") if item.strip()]
    if not statements or not re.fullmatch(r"OPENQASM\s+3\.0", statements[0], re.IGNORECASE):
        raise QASMError("Braket IR must begin with OPENQASM 3.0;")
    qasm2 = ['OPENQASM 2.0;', 'include "qelib1.inc";']
    for statement in statements[1:]:
        if re.fullmatch(r'include\s+["\']stdgates\.inc["\']', statement, re.IGNORECASE):
            continue
        declaration = re.fullmatch(
            r"(qubit|bit)\s*\[\s*(\d+)\s*\]\s*([A-Za-z_]\w*)",
            statement,
            re.IGNORECASE,
        )
        if declaration:
            kind, size, name = declaration.groups()
            qasm2.append(f"{'qreg' if kind.lower() == 'qubit' else 'creg'} {name}[{size}];")
            continue
        measurement = re.fullmatch(r"(.+?)\s*=\s*measure\s+(.+)", statement, re.IGNORECASE)
        if measurement:
            cbit, qubit = measurement.groups()
            qasm2.append(f"measure {qubit.strip()} -> {cbit.strip()};")
            continue
        gate = re.match(r"([A-Za-z_]\w*)", statement)
        if not gate:
            raise QASMError(f"malformed Braket statement: {statement!r}")
        name = gate.group(1).lower()
        replacement = {"cnot": "cx", "cp": "cu1"}.get(name, name)
        qasm2.append(replacement + statement[len(gate.group(1)) :] + ";")
    return parse_qasm2("\n".join(qasm2))


def parse_originq(text: str) -> Circuit:
    lines = [line.strip() for line in strip_comments(text).splitlines() if line.strip()]
    if len(lines) < 2:
        raise QASMError("OriginIR requires QINIT and CREG headers")
    qinit = re.fullmatch(r"QINIT\s+(\d+)", lines[0], re.IGNORECASE)
    creg = re.fullmatch(r"CREG\s+(\d+)", lines[1], re.IGNORECASE)
    if not qinit or not creg:
        raise QASMError("OriginIR requires QINIT then CREG")
    qasm2 = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{qinit.group(1)}];",
        f"creg c[{creg.group(1)}];",
    ]
    reverse_names = {
        "H": "h",
        "X": "x",
        "S": "s",
        "SDAG": "sdg",
        "T": "t",
        "TDAG": "tdg",
        "RY": "ry",
        "RZ": "rz",
        "CNOT": "cx",
        "CU1": "cu1",
        "CR": "cu1",
        "SWAP": "swap",
        "TOFFOLI": "ccx",
        "CCX": "ccx",
    }
    for line in lines[2:]:
        measurement = re.fullmatch(r"MEASURE\s+(q\[\d+\])\s*,\s*(c\[\d+\])", line, re.IGNORECASE)
        if measurement:
            qasm2.append(f"measure {measurement.group(1)} -> {measurement.group(2)};")
            continue
        gate = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*)\s*(?:\((.*?)\))?\s+(.+)", line)
        if not gate:
            raise QASMError(f"malformed OriginIR statement: {line!r}")
        raw_name, parameter, operands = gate.groups()
        name = reverse_names.get(raw_name.upper())
        if not name:
            raise QASMError(f"unsupported OriginIR gate: {raw_name}")
        suffix = f"({parameter})" if parameter is not None else ""
        qasm2.append(f"{name}{suffix} {operands};")
    return parse_qasm2("\n".join(qasm2))


def parse_target(text: str, target: str) -> Circuit:
    if target == "spinq":
        return parse_spinq(text)
    if target == "braket":
        return parse_braket(text)
    if target == "originq":
        return parse_originq(text)
    raise ValueError(f"unknown target: {target}")


def distribution_delta(left: Circuit, right: Circuit) -> float:
    first, second = exact_probabilities(left), exact_probabilities(right)
    return max((abs(first.get(key, 0.0) - second.get(key, 0.0)) for key in set(first) | set(second)), default=0.0)


def _measurement_map(circuit: Circuit) -> tuple[tuple[int, int], ...]:
    from .ir import Measure

    return tuple(
        (circuit.qubit_index(operation.qubit), circuit.cbit_index(operation.cbit))
        for operation in circuit.operations
        if isinstance(operation, Measure)
    )


def _operation_trace(circuit: Circuit) -> tuple[tuple[object, ...], ...]:
    """Register-name-independent exact trace for the non-optimizing emitters."""
    from .ir import Gate, Measure

    trace: list[tuple[object, ...]] = []
    for operation in circuit.operations:
        if isinstance(operation, Gate):
            trace.append(
                (
                    "gate",
                    operation.name,
                    tuple(circuit.qubit_index(ref) for ref in operation.qubits),
                    tuple(value.hex() for value in operation.parameters),
                )
            )
        elif isinstance(operation, Measure):
            trace.append(
                (
                    "measure",
                    circuit.qubit_index(operation.qubit),
                    circuit.cbit_index(operation.cbit),
                )
            )
    return tuple(trace)


def statevector_distance(left: Circuit, right: Circuit) -> float:
    """Return pure-state Euclidean distance minimized over global phase."""
    first, second = statevector(left), statevector(right)
    if len(first) != len(second):
        return 2.0
    overlap = sum(a.conjugate() * b for a, b in zip(first, second))
    if abs(overlap) <= 1e-300:
        return math.sqrt(2.0)
    # Direct phase alignment avoids catastrophic cancellation in sqrt(2-2|overlap|).
    phase = overlap.conjugate() / abs(overlap)
    return math.sqrt(sum(abs(a - phase * b) ** 2 for a, b in zip(first, second)))


def _circuit_digest(circuit: Circuit) -> str:
    payload = {
        "qregs": list(circuit.qregs.items()),
        "cregs": list(circuit.cregs.items()),
        "operations": [repr(operation) for operation in circuit.operations],
    }
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def certify_translation(
    source: Circuit,
    artifact: str,
    target: str,
    tolerance: float = 1e-11,
) -> tuple[Circuit, TranslationCertificate]:
    """Reparse target text independently and issue a fail-closed equivalence receipt."""
    translated = parse_target(artifact, target)
    trace_equal = (
        source.total_qubits == translated.total_qubits
        and source.total_cbits == translated.total_cbits
        and _operation_trace(source) == _operation_trace(translated)
    )
    map_equal = _measurement_map(source) == _measurement_map(translated)
    vector_delta = statevector_distance(source, translated)
    probability_delta = distribution_delta(source, translated)
    fields: dict[str, object] = {
        "target": target,
        "source_ir_sha256": _circuit_digest(source),
        "target_ir_sha256": hashlib.sha256(artifact.encode("utf-8")).hexdigest(),
        "operation_trace_equal": trace_equal,
        "measurement_map_equal": map_equal,
        "statevector_distance": vector_delta,
        "probability_delta": probability_delta,
        "tolerance": tolerance,
    }
    receipt = json.dumps(fields, separators=(",", ":"), sort_keys=True, allow_nan=False)
    certificate = TranslationCertificate(
        **fields,
        certificate_sha256=hashlib.sha256(receipt.encode("utf-8")).hexdigest(),
    )
    if not certificate.verified:
        raise ValueError(
            f"{target} translation certificate failed "
            f"(operation trace={trace_equal}, measurement map={map_equal}, state distance={vector_delta:g}, "
            f"probability delta={probability_delta:g})"
        )
    return translated, certificate


def verify_translation(source: Circuit, artifact: str, target: str, tolerance: float = 1e-11) -> float:
    """Compatibility wrapper returning the strongest numeric certificate error."""
    _, certificate = certify_translation(source, artifact, target, tolerance)
    return max(certificate.statevector_distance, certificate.probability_delta)
