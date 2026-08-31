"""Round-trip equivalence checking for emitted target IR.

Formal L1 scoring parses and simulates whatever `transpile()` returns, so the
emitted OpenQASM 3 / OriginIR must be semantically identical to the input
OpenQASM 2. These readers parse our own emitted artifacts back into the unified
IR so the two distributions can be compared offline.
"""

from __future__ import annotations

import math
import re
from typing import Dict, List, Tuple

from .circuit import Circuit, GateOp, MeasureOp
from .emit import emit, emit_braket_native_qasm3
from .parse_qasm import parse_qasm
from .reference_sim import hellinger_fidelity, ideal_distribution, simulate

_ORIGIN_TO_CANON = {
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

_QASM3_TO_CANON = {
    "h": "h",
    "x": "x",
    "s": "s",
    "sdg": "sdg",
    "si": "sdg",
    "t": "t",
    "tdg": "tdg",
    "ti": "tdg",
    "rz": "rz",
    "ry": "ry",
    "cx": "cx",
    "cnot": "cx",
    "swap": "swap",
    "ccx": "ccx",
    "ccnot": "ccx",
    "cphaseshift": "cu1",
    "cu1": "cu1",
}

_PI = re.compile(r"\bpi\b")


def _eval_angle(text: str) -> float:
    normalized = _PI.sub(str(math.pi), text.strip())
    if not re.fullmatch(r"[0-9eE+\-*/().\s]+", normalized):
        raise ValueError(f"unsupported angle expression: {text}")
    return float(eval(normalized, {"__builtins__": {}}, {}))  # noqa: S307


def parse_originir(text: str) -> Circuit:
    circuit = Circuit()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("QINIT"):
            circuit.qregs["q"] = int(line.split()[1])
            continue
        if upper.startswith("CREG"):
            circuit.cregs["c"] = int(line.split()[1])
            continue
        if upper.startswith("MEASURE"):
            refs = re.findall(r"([qc])\[(\d+)\]", line)
            if len(refs) != 2:
                raise ValueError(f"invalid OriginIR measure: {line}")
            circuit.ops.append(
                MeasureOp(qubit=("q", int(refs[0][1])), cbit=("c", int(refs[1][1])))
            )
            continue

        match = re.match(r"([A-Za-z_]\w*)\s*(?:\(([^)]*)\))?\s*(.*)", line)
        if not match:
            raise ValueError(f"unrecognized OriginIR line: {line}")
        raw_name = match.group(1).upper()
        param_text = match.group(2)
        rest = match.group(3)

        # Accept the alternative `RY q[0],(theta)` spelling.
        if param_text is None:
            tail = re.search(r"\(([^)]*)\)\s*$", rest)
            if tail:
                param_text = tail.group(1)
                rest = rest[: tail.start()]

        name = _ORIGIN_TO_CANON.get(raw_name)
        if name is None:
            raise ValueError(f"unknown OriginIR gate: {raw_name}")
        qubits = tuple(("q", int(idx)) for idx in re.findall(r"q\[(\d+)\]", rest))
        params = () if not param_text or not param_text.strip() else (_eval_angle(param_text),)
        circuit.ops.append(GateOp(name=name, qubits=qubits, params=params))

    if not circuit.qregs:
        raise ValueError("OriginIR text has no QINIT")
    return circuit


def parse_qasm3(text: str) -> Circuit:
    circuit = Circuit()
    body = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    for raw in body.split(";"):
        stmt = re.sub(r"\s+", " ", raw).strip()
        if not stmt:
            continue
        lower = stmt.lower()
        if lower.startswith("openqasm") or lower.startswith("include"):
            continue

        decl = re.fullmatch(r"(qubit|bit)\[(\d+)\] ([A-Za-z_]\w*)", stmt, re.IGNORECASE)
        if decl:
            kind, size, name = decl.group(1).lower(), int(decl.group(2)), decl.group(3)
            if kind == "qubit":
                circuit.qregs[name] = size
            else:
                circuit.cregs[name] = size
            continue

        assign = re.fullmatch(
            r"([A-Za-z_]\w*)(?:\[(\d+)\])? = measure ([A-Za-z_]\w*)(?:\[(\d+)\])?",
            stmt,
            re.IGNORECASE,
        )
        if assign:
            cname, cidx, qname, qidx = assign.groups()
            if cidx is None and qidx is None:
                size = min(circuit.qregs[qname], circuit.cregs[cname])
                for i in range(size):
                    circuit.ops.append(
                        MeasureOp(qubit=(qname, i), cbit=(cname, i))
                    )
            else:
                circuit.ops.append(
                    MeasureOp(qubit=(qname, int(qidx)), cbit=(cname, int(cidx)))
                )
            continue

        gate = re.fullmatch(r"([A-Za-z_]\w*)(?:\(([^)]*)\))? (.+)", stmt)
        if not gate:
            raise ValueError(f"unrecognized OpenQASM 3 statement: {stmt}")
        raw_name = gate.group(1).lower()
        name = _QASM3_TO_CANON.get(raw_name)
        if name is None:
            raise ValueError(f"unknown OpenQASM 3 gate: {raw_name}")
        param_text = gate.group(2)
        params = () if not param_text or not param_text.strip() else (_eval_angle(param_text),)
        qubits = tuple(
            (m.group(1), int(m.group(2)))
            for m in re.finditer(r"([A-Za-z_]\w*)\[(\d+)\]", gate.group(3))
        )
        circuit.ops.append(GateOp(name=name, qubits=qubits, params=params))

    if not circuit.qregs:
        raise ValueError("OpenQASM 3 text has no qubit declaration")
    return circuit


READERS = {
    "spinq": parse_qasm,
    "braket": parse_qasm3,
    "originq": parse_originir,
    # The dialect actually handed to Braket's LocalSimulator; verified separately
    # because it uses Braket's own gate names instead of stdgates.
    "braket_native": parse_qasm3,
}

_EXTRA_EMITTERS = {"braket_native": emit_braket_native_qasm3}


def _emit_for(circuit: Circuit, target: str) -> str:
    if target in _EXTRA_EMITTERS:
        return _EXTRA_EMITTERS[target](circuit)
    return emit(circuit, target)


def _distribution_of(circuit: Circuit) -> Dict[str, float]:
    probs, measured = simulate(circuit)
    n_bits = circuit.n_clbits() or circuit.n_qubits()
    if not measured:
        measured = [(i, i) for i in range(circuit.n_qubits())]
    dist: Dict[str, float] = {}
    for state_index, prob in enumerate(probs):
        if prob <= 1e-15:
            continue
        bits = ["0"] * n_bits
        for qubit_index, cbit_index in measured:
            bits[n_bits - 1 - cbit_index] = str((state_index >> qubit_index) & 1)
        key = "".join(bits)
        dist[key] = dist.get(key, 0.0) + prob
    return dist


def check_transpile_equivalence(qasm_str: str, target: str) -> Tuple[float, Dict[str, float], Dict[str, float]]:
    """Emit target IR, read it back, and compare against the source distribution."""
    expected = ideal_distribution(qasm_str)
    native = _emit_for(parse_qasm(qasm_str), target)
    reader = READERS.get(target)
    if reader is None:
        raise ValueError(f"no reader for target '{target}'")
    observed = _distribution_of(reader(native))
    return hellinger_fidelity(observed, expected), observed, expected


def check_all_targets(qasm_str: str, targets: List[str] | None = None) -> Dict[str, float]:
    targets = targets or ["spinq", "braket", "originq", "braket_native"]
    return {
        target: check_transpile_equivalence(qasm_str, target)[0] for target in targets
    }
