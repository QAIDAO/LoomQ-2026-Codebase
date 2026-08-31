"""Minimal OpenQASM 2.0 parser for the LoomQ gate whitelist."""

from __future__ import annotations

import math
import re
from typing import List, Tuple

from .circuit import Circuit, GateOp, MeasureOp, QubitRef  # noqa: F401

WHITELIST = frozenset(
    {"h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx"}
)

_PARAM_GATE_ARITY = {
    "h": 1,
    "x": 1,
    "s": 1,
    "sdg": 1,
    "t": 1,
    "tdg": 1,
    "rz": 1,
    "ry": 1,
    "cx": 2,
    "cu1": 2,
    "swap": 2,
    "ccx": 3,
}

_LINE_COMMENT = re.compile(r"//.*?$", re.MULTILINE)
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_PI = re.compile(r"\bpi\b")


def _strip_comments(source: str) -> str:
    source = _BLOCK_COMMENT.sub("", source)
    source = _LINE_COMMENT.sub("", source)
    return source


def _eval_param(expr: str) -> float:
    text = expr.strip()
    if not text:
        raise ValueError("empty parameter expression")
    # Safe subset: numbers, pi, + - * / ( )
    normalized = _PI.sub(str(math.pi), text)
    if not re.fullmatch(r"[0-9eE+\-*/().\s]+", normalized):
        raise ValueError(f"unsupported parameter expression: {expr}")
    try:
        # eval is intentional: builtins stripped + charset pre-filtered above,
        # so this only evaluates arithmetic over floats/pi (no name lookup).
        value = eval(normalized, {"__builtins__": {}}, {})  # noqa: S307
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"cannot evaluate parameter '{expr}': {exc}") from exc
    if not isinstance(value, (int, float)):
        raise ValueError(f"parameter did not evaluate to a number: {expr}")
    return float(value)


def _parse_ref(token: str) -> Tuple[str, int]:
    match = re.fullmatch(r"([A-Za-z_][\w]*)\[(\d+)\]", token.strip())
    if not match:
        raise ValueError(f"expected register[index], got '{token}'")
    return match.group(1), int(match.group(2))


def _split_args(arg_text: str) -> List[str]:
    parts: List[str] = []
    depth = 0
    current: List[str] = []
    for ch in arg_text:
        if ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        current.append(ch)
    if current or parts:
        parts.append("".join(current).strip())
    return [part for part in parts if part]


def parse_qasm(qasm_str: str) -> Circuit:
    if not isinstance(qasm_str, str) or not qasm_str.strip():
        raise ValueError("qasm_str must be a non-empty string")

    cleaned = _strip_comments(qasm_str)
    # Keep statements separated by ';'
    raw_stmts = [stmt.strip() for stmt in cleaned.split(";") if stmt.strip()]
    circuit = Circuit()

    for stmt in raw_stmts:
        # Collapse internal whitespace for regex friendliness, but keep params.
        compact = re.sub(r"\s+", " ", stmt).strip()
        lower = compact.lower()

        if lower.startswith("openqasm"):
            continue
        if lower.startswith("include "):
            continue
        if lower.startswith("qreg "):
            match = re.fullmatch(r"qreg ([A-Za-z_][\w]*)\[(\d+)\]", compact, re.IGNORECASE)
            if not match:
                raise ValueError(f"invalid qreg statement: {stmt}")
            name, size = match.group(1), int(match.group(2))
            if name in circuit.qregs:
                raise ValueError(f"duplicate qreg: {name}")
            circuit.qregs[name] = size
            continue
        if lower.startswith("creg "):
            match = re.fullmatch(r"creg ([A-Za-z_][\w]*)\[(\d+)\]", compact, re.IGNORECASE)
            if not match:
                raise ValueError(f"invalid creg statement: {stmt}")
            name, size = match.group(1), int(match.group(2))
            if name in circuit.cregs:
                raise ValueError(f"duplicate creg: {name}")
            circuit.cregs[name] = size
            continue
        if lower.startswith("measure "):
            # measure q -> c;  OR  measure q[i] -> c[j];
            body = compact[len("measure ") :].strip()
            if "->" not in body:
                raise ValueError(f"invalid measure statement: {stmt}")
            left, right = [part.strip() for part in body.split("->", 1)]
            if "[" not in left and "[" not in right:
                # whole-register measure
                qname, cname = left, right
                if qname not in circuit.qregs or cname not in circuit.cregs:
                    raise ValueError(f"unknown register in measure: {stmt}")
                qsize = circuit.qregs[qname]
                csize = circuit.cregs[cname]
                size = min(qsize, csize)
                for i in range(size):
                    circuit.ops.append(
                        MeasureOp(qubit=(qname, i), cbit=(cname, i))
                    )
            else:
                circuit.ops.append(
                    MeasureOp(qubit=_parse_ref(left), cbit=_parse_ref(right))
                )
            continue

        # Gate: name(params?) args
        gate_match = re.fullmatch(
            r"([A-Za-z_][\w]*)(?:\(([^)]*)\))?\s+(.+)",
            compact,
        )
        if not gate_match:
            raise ValueError(f"unrecognized statement: {stmt}")

        name = gate_match.group(1).lower()
        param_text = gate_match.group(2)
        arg_text = gate_match.group(3)
        if name not in WHITELIST:
            raise ValueError(f"gate '{name}' is outside the LoomQ whitelist")

        params: Tuple[float, ...]
        if param_text is None or param_text.strip() == "":
            params = ()
        else:
            params = tuple(_eval_param(part) for part in _split_args(param_text))

        qubits: Tuple[QubitRef, ...] = tuple(
            _parse_ref(part) for part in _split_args(arg_text)
        )
        expected = _PARAM_GATE_ARITY[name]
        if len(qubits) != expected:
            raise ValueError(
                f"gate '{name}' expects {expected} qubit(s), got {len(qubits)}"
            )
        if name in {"rz", "ry", "cu1"} and len(params) != 1:
            raise ValueError(f"gate '{name}' expects exactly one parameter")
        if name not in {"rz", "ry", "cu1"} and params:
            raise ValueError(f"gate '{name}' does not take parameters")

        # Validate indices exist
        for qref in qubits:
            circuit.qubit_index(qref)

        circuit.ops.append(GateOp(name=name, qubits=qubits, params=params))

    if not circuit.qregs:
        raise ValueError("circuit has no qreg declaration")
    return circuit
