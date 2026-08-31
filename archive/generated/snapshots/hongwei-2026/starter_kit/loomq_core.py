#!/usr/bin/env python3
"""LoomQ unified intermediate layer: parse, emit, simulate, hybrid compile."""

from __future__ import annotations

import math
import random
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Angle / token helpers
# ---------------------------------------------------------------------------

_PI = math.pi


def eval_angle(expr: str) -> float:
    """Evaluate OpenQASM angle expressions built from numbers and pi."""
    text = expr.strip().lower().replace(" ", "")
    if not text:
        raise ValueError("empty angle expression")
    # Replace pi with a float literal before safe eval of arithmetic.
    text = re.sub(r"\bpi\b", repr(_PI), text)
    if not re.fullmatch(r"[0-9eE+\-*/().]+", text):
        raise ValueError("unsupported angle expression: %s" % expr)
    return float(eval(text, {"__builtins__": {}}, {}))  # noqa: S307 — restricted


def format_angle(theta: float) -> str:
    """Pretty-print common multiples of pi; otherwise use a float."""
    for n, d in (
        (0, 1),
        (1, 1),
        (-1, 1),
        (1, 2),
        (-1, 2),
        (1, 4),
        (-1, 4),
        (3, 4),
        (-3, 4),
        (1, 8),
        (-1, 8),
        (3, 8),
        (-3, 8),
        (1, 3),
        (-1, 3),
        (2, 3),
        (-2, 3),
    ):
        target = _PI * n / d if d else 0.0
        if abs(theta - target) < 1e-10:
            if n == 0:
                return "0"
            sign = "-" if n < 0 else ""
            n = abs(n)
            if d == 1:
                return "%spi" % sign if n == 1 else "%s%d*pi" % (sign, n)
            if n == 1:
                return "%spi/%d" % (sign, d)
            return "%s%d*pi/%d" % (sign, n, d)
    return "%.12g" % theta


# ---------------------------------------------------------------------------
# Circuit IR
# ---------------------------------------------------------------------------

@dataclass
class Gate:
    name: str
    qubits: Tuple[int, ...]
    params: Tuple[float, ...] = ()


@dataclass
class Measure:
    qubit: int
    cbit: int


@dataclass
class Circuit:
    n_qubits: int = 0
    n_clbits: int = 0
    gates: List[Gate] = field(default_factory=list)
    measures: List[Measure] = field(default_factory=list)


_GATE_LINE = re.compile(
    r"^\s*(?P<name>h|x|s|sdg|t|tdg|rz|ry|cx|cu1|swap|ccx)\s*"
    r"(?:\((?P<params>[^)]*)\))?\s*"
    r"(?P<args>[^;]+);",
    re.IGNORECASE,
)
_QREG = re.compile(r"^\s*qreg\s+(\w+)\s*\[\s*(\d+)\s*\]\s*;", re.IGNORECASE)
_CREG = re.compile(r"^\s*creg\s+(\w+)\s*\[\s*(\d+)\s*\]\s*;", re.IGNORECASE)
_MEASURE_ONE = re.compile(
    r"^\s*measure\s+(\w+)\s*\[\s*(\d+)\s*\]\s*->\s*(\w+)\s*\[\s*(\d+)\s*\]\s*;",
    re.IGNORECASE,
)
_MEASURE_ALL = re.compile(
    r"^\s*measure\s+(\w+)\s*->\s*(\w+)\s*;",
    re.IGNORECASE,
)
_QUBIT = re.compile(r"(\w+)\s*\[\s*(\d+)\s*\]")


def parse_qasm(qasm_str: str) -> Circuit:
    """Parse a whitelist OpenQASM 2.0 circuit into the LoomQ IR."""
    circuit = Circuit()
    qregs: Dict[str, Tuple[int, int]] = {}  # name -> (offset, size)
    cregs: Dict[str, Tuple[int, int]] = {}
    q_offset = 0
    c_offset = 0

    # Strip classical blocks for pure quantum parse (L3 uses a separate path).
    text = qasm_str
    while True:
        found = _find_classical_block(text)
        if not found:
            break
        start, end, _ = found
        text = text[:start] + text[end:]
    lines = []
    for raw in text.splitlines():
        line = raw.split("//")[0].strip()
        if line:
            lines.append(line)
    # Allow multiple statements per line.
    body = " ".join(lines)
    statements = [s.strip() + ";" for s in body.split(";") if s.strip()]

    for stmt in statements:
        m = _QREG.match(stmt)
        if m:
            name, size = m.group(1), int(m.group(2))
            qregs[name] = (q_offset, size)
            q_offset += size
            circuit.n_qubits = q_offset
            continue
        m = _CREG.match(stmt)
        if m:
            name, size = m.group(1), int(m.group(2))
            cregs[name] = (c_offset, size)
            c_offset += size
            circuit.n_clbits = c_offset
            continue
        m = _MEASURE_ONE.match(stmt)
        if m:
            qname, qi, cname, ci = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
            circuit.measures.append(
                Measure(qregs[qname][0] + qi, cregs[cname][0] + ci)
            )
            continue
        m = _MEASURE_ALL.match(stmt)
        if m:
            qname, cname = m.group(1), m.group(2)
            qoff, qsize = qregs[qname]
            coff, csize = cregs[cname]
            for i in range(min(qsize, csize)):
                circuit.measures.append(Measure(qoff + i, coff + i))
            continue
        if re.match(r"^\s*OPENQASM", stmt, re.IGNORECASE):
            continue
        if re.match(r"^\s*include\s+", stmt, re.IGNORECASE):
            continue
        m = _GATE_LINE.match(stmt)
        if not m:
            raise ValueError("unsupported statement: %s" % stmt)
        name = m.group("name").lower()
        params_raw = m.group("params")
        params: Tuple[float, ...] = ()
        if params_raw is not None:
            params = tuple(eval_angle(p) for p in params_raw.split(",") if p.strip())
        args = _QUBIT.findall(m.group("args"))
        if not args:
            raise ValueError("missing qubit args: %s" % stmt)
        qubits = []
        for reg, idx in args:
            qubits.append(qregs[reg][0] + int(idx))
        circuit.gates.append(Gate(name, tuple(qubits), params))

    if not circuit.measures and circuit.n_clbits and circuit.n_qubits:
        # Implicit full measure if none declared — keep empty; caller decides.
        pass
    return circuit


# ---------------------------------------------------------------------------
# Emitters
# ---------------------------------------------------------------------------

def emit_spinq(circuit: Circuit) -> str:
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[%d];" % circuit.n_qubits,
        "creg c[%d];" % max(circuit.n_clbits, 1),
    ]
    for gate in circuit.gates:
        lines.append(_emit_qasm2_gate(gate))
    if circuit.measures:
        for meas in circuit.measures:
            lines.append("measure q[%d] -> c[%d];" % (meas.qubit, meas.cbit))
    else:
        lines.append("measure q -> c;")
    return "\n".join(lines) + "\n"


def emit_braket(circuit: Circuit) -> str:
    nq = circuit.n_qubits
    nc = max(circuit.n_clbits, 1)
    lines = [
        "OPENQASM 3.0;",
        'include "stdgates.inc";',
        "qubit[%d] q;" % nq,
        "bit[%d] c;" % nc,
    ]
    for gate in circuit.gates:
        lines.append(_emit_qasm3_gate(gate))
    if circuit.measures:
        # Prefer whole-register measure when it covers all qubits in order.
        ordered = sorted(circuit.measures, key=lambda m: m.cbit)
        if (
            len(ordered) == nq == nc
            and all(m.qubit == m.cbit == i for i, m in enumerate(ordered))
        ):
            lines.append("c = measure q;")
        else:
            for meas in ordered:
                lines.append("c[%d] = measure q[%d];" % (meas.cbit, meas.qubit))
    else:
        lines.append("c = measure q;")
    return "\n".join(lines) + "\n"


def emit_originq(circuit: Circuit) -> str:
    lines = [
        "QINIT %d" % circuit.n_qubits,
        "CREG %d" % max(circuit.n_clbits, 1),
    ]
    for gate in circuit.gates:
        lines.append(_emit_origin_gate(gate))
    if circuit.measures:
        for meas in sorted(circuit.measures, key=lambda m: m.cbit):
            lines.append("MEASURE q[%d], c[%d]" % (meas.qubit, meas.cbit))
    else:
        for i in range(circuit.n_qubits):
            lines.append("MEASURE q[%d], c[%d]" % (i, i))
    return "\n".join(lines) + "\n"


def _emit_qasm2_gate(gate: Gate) -> str:
    name = gate.name
    qs = gate.qubits
    if name in ("h", "x", "s", "sdg", "t", "tdg"):
        return "%s q[%d];" % (name, qs[0])
    if name in ("rz", "ry"):
        return "%s(%s) q[%d];" % (name, format_angle(gate.params[0]), qs[0])
    if name == "cx":
        return "cx q[%d], q[%d];" % (qs[0], qs[1])
    if name == "cu1":
        return "cu1(%s) q[%d], q[%d];" % (format_angle(gate.params[0]), qs[0], qs[1])
    if name == "swap":
        return "swap q[%d], q[%d];" % (qs[0], qs[1])
    if name == "ccx":
        return "ccx q[%d], q[%d], q[%d];" % (qs[0], qs[1], qs[2])
    raise ValueError("unknown gate %s" % name)


def _emit_qasm3_gate(gate: Gate) -> str:
    name = gate.name
    qs = gate.qubits
    if name in ("h", "x", "s", "sdg", "t", "tdg"):
        return "%s q[%d];" % (name, qs[0])
    if name in ("rz", "ry"):
        return "%s(%s) q[%d];" % (name, format_angle(gate.params[0]), qs[0])
    if name == "cx":
        return "cnot q[%d], q[%d];" % (qs[0], qs[1])
    if name == "cu1":
        # stdgates.inc uses `cp` for controlled phase; cu1 is equivalent.
        return "cp(%s) q[%d], q[%d];" % (format_angle(gate.params[0]), qs[0], qs[1])
    if name == "swap":
        return "swap q[%d], q[%d];" % (qs[0], qs[1])
    if name == "ccx":
        return "ccx q[%d], q[%d], q[%d];" % (qs[0], qs[1], qs[2])
    raise ValueError("unknown gate %s" % name)


def _emit_origin_gate(gate: Gate) -> str:
    name = gate.name
    qs = gate.qubits
    mapping = {
        "h": "H",
        "x": "X",
        "s": "S",
        "sdg": "SDAG",
        "t": "T",
        "tdg": "TDAG",
        "cx": "CNOT",
        "swap": "SWAP",
        "ccx": "TOFFOLI",
    }
    if name in mapping and name not in ("rz", "ry", "cu1"):
        op = mapping[name]
        if len(qs) == 1:
            return "%s q[%d]" % (op, qs[0])
        if len(qs) == 2:
            return "%s q[%d], q[%d]" % (op, qs[0], qs[1])
        return "%s q[%d], q[%d], q[%d]" % (op, qs[0], qs[1], qs[2])
    if name == "ry":
        return "RY(%s) q[%d]" % (format_angle(gate.params[0]), qs[0])
    if name == "rz":
        return "RZ(%s) q[%d]" % (format_angle(gate.params[0]), qs[0])
    if name == "cu1":
        return "CU1(%s) q[%d], q[%d]" % (format_angle(gate.params[0]), qs[0], qs[1])
    raise ValueError("unknown gate %s" % name)


def transpile_circuit(circuit: Circuit, target: str) -> str:
    target = target.lower().strip()
    if target == "spinq":
        return emit_spinq(circuit)
    if target == "braket":
        return emit_braket(circuit)
    if target == "originq":
        return emit_originq(circuit)
    raise ValueError("unsupported target: %s" % target)


# ---------------------------------------------------------------------------
# Statevector simulator (stdlib only)
# ---------------------------------------------------------------------------

def _mat_mul(a: List[List[complex]], b: List[List[complex]]) -> List[List[complex]]:
    n = len(a)
    m = len(b[0])
    k = len(b)
    out = [[0j] * m for _ in range(n)]
    for i in range(n):
        for j in range(m):
            s = 0j
            for t in range(k):
                s += a[i][t] * b[t][j]
            out[i][j] = s
    return out


def _gate_matrix(name: str, params: Sequence[float]) -> List[List[complex]]:
    if name == "h":
        s = 1 / math.sqrt(2)
        return [[s, s], [s, -s]]
    if name == "x":
        return [[0, 1], [1, 0]]
    if name == "s":
        return [[1, 0], [0, 1j]]
    if name == "sdg":
        return [[1, 0], [0, -1j]]
    if name == "t":
        return [[1, 0], [0, complex(math.cos(_PI / 4), math.sin(_PI / 4))]]
    if name == "tdg":
        return [[1, 0], [0, complex(math.cos(-_PI / 4), math.sin(-_PI / 4))]]
    if name == "rz":
        th = params[0]
        return [
            [complex(math.cos(-th / 2), math.sin(-th / 2)), 0],
            [0, complex(math.cos(th / 2), math.sin(th / 2))],
        ]
    if name == "ry":
        th = params[0]
        c, s = math.cos(th / 2), math.sin(th / 2)
        return [[c, -s], [s, c]]
    raise ValueError(name)


def _apply_1q(state: List[complex], n: int, qubit: int, mat: List[List[complex]]) -> None:
    step = 1 << qubit
    for base in range(1 << n):
        if base & step:
            continue
        i0 = base
        i1 = base | step
        a0, a1 = state[i0], state[i1]
        state[i0] = mat[0][0] * a0 + mat[0][1] * a1
        state[i1] = mat[1][0] * a0 + mat[1][1] * a1


def _apply_cx(state: List[complex], n: int, control: int, target: int) -> None:
    cbit, tbit = 1 << control, 1 << target
    for i in range(1 << n):
        if (i & cbit) and not (i & tbit):
            j = i | tbit
            state[i], state[j] = state[j], state[i]


def _apply_cu1(state: List[complex], n: int, control: int, target: int, theta: float) -> None:
    phase = complex(math.cos(theta), math.sin(theta))
    mask = (1 << control) | (1 << target)
    for i in range(1 << n):
        if (i & mask) == mask:
            state[i] *= phase


def _apply_swap(state: List[complex], n: int, a: int, b: int) -> None:
    if a == b:
        return
    abit, bbit = 1 << a, 1 << b
    for i in range(1 << n):
        has_a = bool(i & abit)
        has_b = bool(i & bbit)
        if has_a == has_b:
            continue
        # Only swap each pair once: when a is set and b is clear.
        if has_a and not has_b:
            j = (i ^ abit) | bbit
            state[i], state[j] = state[j], state[i]


def _apply_ccx(state: List[complex], n: int, c0: int, c1: int, target: int) -> None:
    m0, m1, mt = 1 << c0, 1 << c1, 1 << target
    for i in range(1 << n):
        if (i & m0) and (i & m1) and not (i & mt):
            j = i | mt
            state[i], state[j] = state[j], state[i]


def simulate_counts(circuit: Circuit, shots: int, seed: Optional[int] = None) -> Dict[str, int]:
    n = circuit.n_qubits
    if n <= 0:
        raise ValueError("circuit has no qubits")
    if n > 20:
        raise ValueError("too many qubits for built-in simulator: %d" % n)
    state = [0j] * (1 << n)
    state[0] = 1 + 0j

    for gate in circuit.gates:
        name, qs, params = gate.name, gate.qubits, gate.params
        if name in ("h", "x", "s", "sdg", "t", "tdg", "rz", "ry"):
            _apply_1q(state, n, qs[0], _gate_matrix(name, params))
        elif name == "cx":
            _apply_cx(state, n, qs[0], qs[1])
        elif name == "cu1":
            _apply_cu1(state, n, qs[0], qs[1], params[0])
        elif name == "swap":
            _apply_swap(state, n, qs[0], qs[1])
        elif name == "ccx":
            _apply_ccx(state, n, qs[0], qs[1], qs[2])
        else:
            raise ValueError("unsupported gate in simulator: %s" % name)

    measures = circuit.measures
    if not measures:
        measures = [Measure(i, i) for i in range(min(n, circuit.n_clbits or n))]
    n_cl = max((m.cbit for m in measures), default=-1) + 1
    if n_cl <= 0:
        n_cl = n

    # Probability of each full computational basis state.
    probs = [abs(amp) ** 2 for amp in state]
    rng = random.Random(seed)

    counts: Dict[str, int] = {}
    for _ in range(shots):
        r = rng.random()
        acc = 0.0
        outcome = (1 << n) - 1
        for idx, p in enumerate(probs):
            acc += p
            if r <= acc:
                outcome = idx
                break
        bits = ["0"] * n_cl
        for meas in measures:
            qbit = (outcome >> meas.qubit) & 1
            bits[meas.cbit] = str(qbit)
        # little-endian key: rightmost char is c[0]
        key = "".join(reversed(bits))
        counts[key] = counts.get(key, 0) + 1
    return counts


def unified_result(
    backend: str,
    shots: int,
    counts: Dict[str, int],
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "backend": backend,
        "job_id": str(uuid.uuid4()),
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "meta": meta or {},
    }


BACKEND_NAMES = {
    "spinq": "spinq_taurus",
    "originq": "originq_local_simulator",
    "braket": "braket_local_simulator",
}


# ---------------------------------------------------------------------------
# Hybrid-QASM → (quantum ops, RISC-V)
# ---------------------------------------------------------------------------

def _find_classical_block(source: str) -> Optional[Tuple[int, int, str]]:
    """Return (start, end, body) for the first classical { ... } block with nested braces."""
    match = re.search(r"classical\s*\{", source, re.IGNORECASE)
    if not match:
        return None
    start = match.start()
    i = match.end() - 1  # at '{'
    depth = 0
    for j in range(i, len(source)):
        ch = source[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                body = source[i + 1 : j]
                return start, j + 1, body
    raise ValueError("unclosed classical block")


def extract_quantum_ops(hybrid_qasm: str) -> List[str]:
    """Return quantum/measure statements as normalized strings (no classical)."""
    found = _find_classical_block(hybrid_qasm)
    text = hybrid_qasm
    if found:
        start, end, _ = found
        text = hybrid_qasm[:start] + hybrid_qasm[end:]
    ops: List[str] = []
    body = " ".join(
        line.split("//")[0].strip()
        for line in text.splitlines()
        if line.split("//")[0].strip()
    )
    for stmt in [s.strip() for s in body.split(";") if s.strip()]:
        low = stmt.lower()
        if low.startswith("openqasm") or low.startswith("include"):
            continue
        if low.startswith("qreg") or low.startswith("creg"):
            continue
        ops.append(stmt)
    return ops


class _ClassicAST:
    pass


@dataclass
class _Assign(_ClassicAST):
    reg: int  # 1..9
    expr: Any  # int | ('reg', n) | ('bin', op, left, right)


@dataclass
class _IfElse(_ClassicAST):
    left: Any
    op: str  # == or !=
    right: Any
    then_body: List[_ClassicAST]
    else_body: List[_ClassicAST]


def _parse_classic_expr(tokens: List[str], i: int) -> Tuple[Any, int]:
    left, i = _parse_classic_atom(tokens, i)
    while i < len(tokens) and tokens[i] in ("+", "-"):
        op = tokens[i]
        right, i = _parse_classic_atom(tokens, i + 1)
        left = ("bin", op, left, right)
    return left, i


def _parse_classic_atom(tokens: List[str], i: int) -> Tuple[Any, int]:
    tok = tokens[i]
    m = re.fullmatch(r"r([1-9])", tok, re.IGNORECASE)
    if m:
        return ("reg", int(m.group(1))), i + 1
    m = re.fullmatch(r"c\[(\d+)\]", tok, re.IGNORECASE)
    if m:
        return ("cbit", int(m.group(1))), i + 1
    if re.fullmatch(r"-?\d+", tok):
        return ("imm", int(tok)), i + 1
    raise ValueError("bad classic atom: %s" % tok)


def _tokenize_classic(src: str) -> List[str]:
    src = src.replace("(", " ( ").replace(")", " ) ")
    src = src.replace("{", " { ").replace("}", " } ")
    src = src.replace(";", " ; ").replace(",", " , ")
    src = re.sub(r"==", " == ", src)
    src = re.sub(r"!=", " != ", src)
    src = re.sub(r"(?<![!<>=])=(?!=)", " = ", src)
    src = re.sub(r"\+", " + ", src)
    # Keep minus attached to numbers when possible; otherwise separate.
    src = re.sub(r"(?<![eE])-(?=\D)", " - ", src)
    return [t for t in src.split() if t]


def _parse_classic_block(tokens: List[str], i: int = 0) -> Tuple[List[_ClassicAST], int]:
    body: List[_ClassicAST] = []
    while i < len(tokens):
        if tokens[i] == "}":
            return body, i
        if tokens[i].lower() == "if":
            # if ( cond ) { ... } else { ... }
            i += 1
            if tokens[i] != "(":
                raise ValueError("expected ( after if")
            i += 1
            left, i = _parse_classic_expr(tokens, i)
            op = tokens[i]
            if op not in ("==", "!="):
                raise ValueError("expected == or !=")
            i += 1
            right, i = _parse_classic_expr(tokens, i)
            if tokens[i] != ")":
                raise ValueError("expected )")
            i += 1
            if tokens[i] != "{":
                raise ValueError("expected {")
            then_body, i = _parse_classic_block(tokens, i + 1)
            if tokens[i] != "}":
                raise ValueError("expected }")
            i += 1
            else_body: List[_ClassicAST] = []
            if i < len(tokens) and tokens[i].lower() == "else":
                i += 1
                if tokens[i] != "{":
                    raise ValueError("expected { after else")
                else_body, i = _parse_classic_block(tokens, i + 1)
                if tokens[i] != "}":
                    raise ValueError("expected }")
                i += 1
            body.append(_IfElse(left, op, right, then_body, else_body))
            continue
        # assignment: rN = expr ;
        m = re.fullmatch(r"r([1-9])", tokens[i], re.IGNORECASE)
        if not m:
            raise ValueError("unexpected token in classical block: %s" % tokens[i])
        reg = int(m.group(1))
        i += 1
        if tokens[i] != "=":
            raise ValueError("expected =")
        i += 1
        expr, i = _parse_classic_expr(tokens, i)
        if i >= len(tokens) or tokens[i] != ";":
            raise ValueError("expected ; after assignment")
        i += 1
        body.append(_Assign(reg, expr))
    return body, i


def _emit_expr_to_reg(
    expr: Any,
    dest: str,
    asm: List[str],
    tmp_counter: List[int],
) -> None:
    """Evaluate expr into dest register (xN string)."""
    if isinstance(expr, tuple) and expr[0] == "imm":
        asm.append("li %s, %d" % (dest, expr[1]))
        return
    if isinstance(expr, tuple) and expr[0] == "reg":
        asm.append("addi %s, x%d, 0" % (dest, expr[1]))
        return
    if isinstance(expr, tuple) and expr[0] == "cbit":
        asm.append("addi %s, x%d, 0" % (dest, 10 + expr[1]))
        return
    if isinstance(expr, tuple) and expr[0] == "bin":
        op, left, right = expr[1], expr[2], expr[3]
        tmp_counter[0] += 1
        # Use high temps x20+ to avoid clobbering r1..r9 / cbits.
        tleft = "x%d" % (20 + (tmp_counter[0] % 5))
        tmp_counter[0] += 1
        tright = "x%d" % (20 + (tmp_counter[0] % 5))
        _emit_expr_to_reg(left, tleft, asm, tmp_counter)
        _emit_expr_to_reg(right, tright, asm, tmp_counter)
        if op == "+":
            asm.append("add %s, %s, %s" % (dest, tleft, tright))
        elif op == "-":
            asm.append("sub %s, %s, %s" % (dest, tleft, tright))
        else:
            raise ValueError("unsupported binop %s" % op)
        return
    raise ValueError("bad expr %r" % (expr,))


def _compile_stmts(stmts: List[_ClassicAST], asm: List[str], label_id: List[int]) -> None:
    tmp_counter = [0]
    for stmt in stmts:
        if isinstance(stmt, _Assign):
            _emit_expr_to_reg(stmt.expr, "x%d" % stmt.reg, asm, tmp_counter)
        elif isinstance(stmt, _IfElse):
            label_id[0] += 1
            lid = label_id[0]
            then_l = "THEN_%d" % lid
            else_l = "ELSE_%d" % lid
            end_l = "END_%d" % lid
            # Evaluate both sides into temps.
            _emit_expr_to_reg(stmt.left, "x28", asm, tmp_counter)
            _emit_expr_to_reg(stmt.right, "x29", asm, tmp_counter)
            if stmt.op == "==":
                asm.append("beq x28, x29, %s" % then_l)
                asm.append("j %s" % else_l)
            else:  # !=
                asm.append("bne x28, x29, %s" % then_l)
                asm.append("j %s" % else_l)
            asm.append("%s:" % then_l)
            _compile_stmts(stmt.then_body, asm, label_id)
            asm.append("j %s" % end_l)
            asm.append("%s:" % else_l)
            _compile_stmts(stmt.else_body, asm, label_id)
            asm.append("%s:" % end_l)
        else:
            raise ValueError("unknown stmt")


def compile_hybrid_program(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    found = _find_classical_block(hybrid_qasm_str)
    classical_src = found[2] if found else ""
    quantum_ops = extract_quantum_ops(hybrid_qasm_str)
    tokens = _tokenize_classic(classical_src)
    stmts, _ = _parse_classic_block(tokens, 0) if tokens else ([], 0)
    asm: List[str] = []
    _compile_stmts(stmts, asm, [0])
    if not asm:
        asm.append("addi x0, x0, 0")
    return quantum_ops, "\n".join(asm) + "\n"
