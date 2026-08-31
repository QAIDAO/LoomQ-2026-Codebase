#!/usr/bin/env python3
"""LoomQ L1 — QASM 2.0 解析与多后端转译核心。

支持白名单 12 门：h x s sdg t tdg rz ry cx cu1 swap ccx
门分解参考 gate_identities.md（全局相位不影响测量分布）。
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Tuple
import math

@dataclass
class Gate:
    name: str
    params: List[float]
    qubits: List[Tuple[str, int]]
    raw_params: List[str]

@dataclass
class Circuit:
    qregs: dict
    cregs: dict
    gates: List[Gate] = field(default_factory=list)
    measurements: List[Tuple[Tuple[str,int], Tuple[str,int]]] = field(default_factory=list)

_CONSTANTS = {"pi": math.pi, "Pi": math.pi, "PI": math.pi}

def _eval_expr(expr: str) -> float:
    expr = expr.strip()
    for k, v in _CONSTANTS.items():
        expr = re.sub(r'\b' + k + r'\b', str(v), expr)
    if re.search(r'[^0-9.+\-*/() eE]', expr):
        raise ValueError(f"Unsafe expression: {expr}")
    return float(eval(expr, {"__builtins__": {}}, {}))

_QREG_RE = re.compile(r'qreg\s+(\w+)\s*\[(\d+)\]$')
_CREG_RE = re.compile(r'creg\s+(\w+)\s*\[(\d+)\]$')
_MEASURE_SINGLE_RE = re.compile(r'measure\s+(\w+)\[(\d+)\]\s*->\s*(\w+)\[(\d+)\]$')
_MEASURE_ALL_RE    = re.compile(r'measure\s+(\w+)\s*->\s*(\w+)\s*$')

_GATE_ARITY = {
    "h": 1, "x": 1, "s": 1, "sdg": 1, "t": 1, "tdg": 1,
    "rz": 1, "ry": 1, "cx": 2, "cu1": 2, "swap": 2, "ccx": 3,
}
_PARAM_COUNTS = {"rz": 1, "ry": 1, "cu1": 1}

def parse_qasm(qasm: str) -> Circuit:
    circ = Circuit(qregs={}, cregs={})
    qasm = re.sub(r"//.*", "", qasm)
    for raw_stmt in qasm.split(";"):
        line = raw_stmt.strip()
        if not line or line.startswith("OPENQASM") or line.startswith("include"):
            continue
        m = _QREG_RE.match(line)
        if m:
            circ.qregs[m.group(1)] = int(m.group(2)); continue
        m = _CREG_RE.match(line)
        if m:
            circ.cregs[m.group(1)] = int(m.group(2)); continue
        m = _MEASURE_SINGLE_RE.match(line)
        if m:
            qname, qidx = m.group(1), int(m.group(2))
            cname, cidx = m.group(3), int(m.group(4))
            if qname not in circ.qregs or qidx >= circ.qregs[qname]:
                raise ValueError(f"Invalid qubit reference: {qname}[{qidx}]")
            if cname not in circ.cregs or cidx >= circ.cregs[cname]:
                raise ValueError(f"Invalid cbit reference: {cname}[{cidx}]")
            circ.measurements.append(((qname, qidx), (cname, cidx))); continue
        m = _MEASURE_ALL_RE.match(line)
        if m:
            qname, cname = m.group(1), m.group(2)
            if qname not in circ.qregs or cname not in circ.cregs:
                raise ValueError(f"Unknown register in measurement: {qname} -> {cname}")
            if circ.qregs[qname] != circ.cregs[cname]:
                raise ValueError(f"Register size mismatch in measurement: {qname} -> {cname}")
            for i in range(circ.qregs[qname]):
                circ.measurements.append(((qname, i), (cname, i)))
            continue
        _parse_gate_line(line, circ)
    return circ

def _parse_gate_line(line: str, circ: Circuit):
    m = re.match(r'(\w+)\s*(.*)', line)
    if not m: return
    name = m.group(1).lower()
    if name not in _GATE_ARITY:
        raise ValueError(f"Unsupported gate: {name}")
    rest = m.group(2).strip()
    params_raw: List[str] = []
    params: List[float] = []
    if rest.startswith("("):
        depth = 0
        close = None
        for pos, char in enumerate(rest):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    close = pos
                    break
        if close is None:
            raise ValueError(f"Unclosed gate parameter list: {line}")
        params_str = rest[1:close].strip()
        rest = rest[close+1:].strip()
        if params_str:
            params_raw = [p.strip() for p in params_str.split(",")]
            params = [_eval_expr(p) for p in params_raw]
    expected_params = _PARAM_COUNTS.get(name, 0)
    if len(params) != expected_params:
        raise ValueError(f"Gate {name} expects {expected_params} parameter(s), got {len(params)}")
    operands: List[List[Tuple[str, int]]] = []
    for tok in re.split(r'\s*,\s*', rest):
        tok = tok.strip()
        if not tok: continue
        qm = re.fullmatch(r'(\w+)\[(\d+)\]', tok)
        if qm:
            qreg, idx = qm.group(1), int(qm.group(2))
            if qreg not in circ.qregs or idx >= circ.qregs[qreg]:
                raise ValueError(f"Invalid qubit reference: {tok}")
            operands.append([(qreg, idx)])
        elif tok in circ.qregs:
            operands.append([(tok, i) for i in range(circ.qregs[tok])])
        else:
            raise ValueError(f"Invalid qubit operand: {tok}")
    if len(operands) != _GATE_ARITY[name]:
        raise ValueError(f"Gate {name} expects {_GATE_ARITY[name]} qubit operand(s), got {len(operands)}")
    widths = {len(operand) for operand in operands}
    width = max(widths)
    if any(size not in (1, width) for size in widths):
        raise ValueError(f"Register size mismatch for gate {name}")
    for i in range(width):
        qubits = [operand[0] if len(operand) == 1 else operand[i] for operand in operands]
        circ.gates.append(Gate(name=name, params=params, qubits=qubits, raw_params=params_raw))

def qubit_index(circ: Circuit, qreg: str, idx: int) -> int:
    offset = 0
    for rname, size in circ.qregs.items():
        if rname == qreg:
            if idx < 0 or idx >= size:
                raise ValueError(f"qubit index out of range: {qreg}[{idx}]")
            return offset + idx
        offset += size
    raise ValueError(f"qreg {qreg} not found")

def total_qubits(circ: Circuit) -> int: return sum(circ.qregs.values())
def total_cbits(circ: Circuit) -> int: return sum(circ.cregs.values())

def cbit_index(circ: Circuit, creg: str, idx: int) -> int:
    offset = 0
    for rname, size in circ.cregs.items():
        if rname == creg:
            if idx < 0 or idx >= size:
                raise ValueError(f"cbit index out of range: {creg}[{idx}]")
            return offset + idx
        offset += size
    raise ValueError(f"creg {creg} not found")

# ---- OriginIR ----

def _gate_to_originir(gate: Gate, circ: Circuit) -> List[str]:
    name = gate.name
    q = [qubit_index(circ, r, i) for r, i in gate.qubits]
    def qi(n): return f"q[{q[n]}]"
    if name == "h":   return [f"H {qi(0)}"]
    if name == "x":   return [f"X {qi(0)}"]
    if name == "s":   return [f"S {qi(0)}"]
    if name == "sdg": return [f"SDAG {qi(0)}"]
    if name == "t":   return [f"T {qi(0)}"]
    if name == "tdg": return [f"TDAG {qi(0)}"]
    if name == "rz":  return [f"RZ({gate.params[0]}) {qi(0)}"]
    if name == "ry":  return [f"RY({gate.params[0]}) {qi(0)}"]
    if name == "cx":  return [f"CNOT {qi(0)},{qi(1)}"]
    if name == "swap":
        return [f"CNOT {qi(0)},{qi(1)}", f"CNOT {qi(1)},{qi(0)}", f"CNOT {qi(0)},{qi(1)}"]
    if name == "cu1":
        t = gate.params[0]
        return [f"RZ({t/2}) {qi(0)}", f"CNOT {qi(0)},{qi(1)}", f"RZ({-t/2}) {qi(1)}", f"CNOT {qi(0)},{qi(1)}", f"RZ({t/2}) {qi(1)}"]
    if name == "ccx":
        return [f"H {qi(2)}", f"CNOT {qi(1)},{qi(2)}", f"TDAG {qi(2)}", f"CNOT {qi(0)},{qi(2)}", f"T {qi(2)}", f"CNOT {qi(1)},{qi(2)}", f"TDAG {qi(2)}", f"CNOT {qi(0)},{qi(2)}", f"T {qi(1)}", f"T {qi(2)}", f"H {qi(2)}", f"CNOT {qi(0)},{qi(1)}", f"T {qi(0)}", f"TDAG {qi(1)}", f"CNOT {qi(0)},{qi(1)}"]
    return [f"# unknown gate: {name}"]

def to_originir(circ: Circuit) -> str:
    lines = ["QINIT %d" % total_qubits(circ), "CREG %d" % total_cbits(circ)]
    for gate in circ.gates:
        lines.extend(_gate_to_originir(gate, circ))
    for (qreg, qi_), (creg, ci_) in circ.measurements:
        lines.append(f"MEASURE q[{qubit_index(circ,qreg,qi_)}],c[{cbit_index(circ,creg,ci_)}]")
    return "\n".join(lines)

# ---- Braket OpenQASM 3.0 ----

_BRAKET_SINGLE = {"h":"h","x":"x","s":"s","sdg":"si","t":"t","tdg":"ti","rz":"rz","ry":"ry"}

def _gate_to_braket3(gate: Gate, circ: Circuit) -> List[str]:
    name = gate.name
    q = [qubit_index(circ, r, i) for r, i in gate.qubits]
    def qi(n): return f"q[{q[n]}]"
    if name == "cx": return [f"cnot {qi(0)}, {qi(1)};"]
    if name in _BRAKET_SINGLE:
        bname = _BRAKET_SINGLE[name]
        if gate.params:
            return [f"{bname}({', '.join(str(p) for p in gate.params)}) {qi(0)};"]
        return [f"{bname} {qi(0)};"]
    if name == "swap":
        return [f"cnot {qi(0)}, {qi(1)};", f"cnot {qi(1)}, {qi(0)};", f"cnot {qi(0)}, {qi(1)};"]
    if name == "cu1":
        t = gate.params[0]
        return [f"rz({t/2}) {qi(0)};", f"cnot {qi(0)}, {qi(1)};", f"rz({-t/2}) {qi(1)};", f"cnot {qi(0)}, {qi(1)};", f"rz({t/2}) {qi(1)};"]
    if name == "ccx":
        return [f"h {qi(2)};", f"cnot {qi(1)}, {qi(2)};", f"ti {qi(2)};", f"cnot {qi(0)}, {qi(2)};", f"t {qi(2)};", f"cnot {qi(1)}, {qi(2)};", f"ti {qi(2)};", f"cnot {qi(0)}, {qi(2)};", f"t {qi(1)};", f"t {qi(2)};", f"h {qi(2)};", f"cnot {qi(0)}, {qi(1)};", f"t {qi(0)};", f"ti {qi(1)};", f"cnot {qi(0)}, {qi(1)};"]
    return [f"// unknown gate: {name}"]

def to_braket_openqasm3(circ: Circuit) -> str:
    lines = ["OPENQASM 3.0;", f"qubit[{total_qubits(circ)}] q;", f"bit[{total_cbits(circ)}] c;"]
    for gate in circ.gates:
        lines.extend(_gate_to_braket3(gate, circ))
    for (qreg, qi_), (creg, ci_) in circ.measurements:
        lines.append(f"c[{cbit_index(circ,creg,ci_)}] = measure q[{qubit_index(circ,qreg,qi_)}];")
    return "\n".join(lines)

# ---- SpinQ QASM 2.0 ----

_SPINQ_DECOMPOSE = {"sdg", "tdg", "cu1", "swap", "ccx"}

def _gate_to_spinq_qasm(gate: Gate, circ: Circuit) -> List[str]:
    name = gate.name
    qubits_str = ", ".join(f"{r}[{i}]" for r, i in gate.qubits)
    if name not in _SPINQ_DECOMPOSE:
        if gate.raw_params:
            return [f"{name}({','.join(gate.raw_params)}) {qubits_str};"]
        return [f"{name} {qubits_str};"]
    q = gate.qubits
    def qstr(n): return f"{q[n][0]}[{q[n][1]}]"
    if name == "sdg": return [f"rz(-pi/2) {qstr(0)};"]
    if name == "tdg": return [f"rz(-pi/4) {qstr(0)};"]
    if name == "swap":
        return [f"cx {qstr(0)},{qstr(1)};", f"cx {qstr(1)},{qstr(0)};", f"cx {qstr(0)},{qstr(1)};"]
    if name == "cu1":
        t = gate.params[0]
        return [f"rz({t/2}) {qstr(0)};", f"cx {qstr(0)},{qstr(1)};", f"rz({-t/2}) {qstr(1)};", f"cx {qstr(0)},{qstr(1)};", f"rz({t/2}) {qstr(1)};"]
    if name == "ccx":
        return [f"h {qstr(2)};", f"cx {qstr(1)},{qstr(2)};", f"rz(-pi/4) {qstr(2)};", f"cx {qstr(0)},{qstr(2)};", f"rz(pi/4) {qstr(2)};", f"cx {qstr(1)},{qstr(2)};", f"rz(-pi/4) {qstr(2)};", f"cx {qstr(0)},{qstr(2)};", f"rz(pi/4) {qstr(1)};", f"rz(pi/4) {qstr(2)};", f"h {qstr(2)};", f"cx {qstr(0)},{qstr(1)};", f"rz(pi/4) {qstr(0)};", f"rz(-pi/4) {qstr(1)};", f"cx {qstr(0)},{qstr(1)};"]
    return [f"{name} {qubits_str};"]

def to_spinq_qasm2(circ: Circuit) -> str:
    lines = ['OPENQASM 2.0;', 'include "qelib1.inc";']
    for rname, size in circ.qregs.items():
        lines.append(f"qreg {rname}[{size}];")
    for rname, size in circ.cregs.items():
        lines.append(f"creg {rname}[{size}];")
    for gate in circ.gates:
        lines.extend(_gate_to_spinq_qasm(gate, circ))
    for (qreg, qi_), (creg, ci_) in circ.measurements:
        lines.append(f"measure {qreg}[{qi_}] -> {creg}[{ci_}];")
    return "\n".join(lines)
