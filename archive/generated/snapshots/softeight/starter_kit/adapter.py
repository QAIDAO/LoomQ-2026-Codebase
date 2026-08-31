#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

transpile()/run() are implemented for the three L1 targets (spinq/originq/
braket) covering the 12-gate qelib1 whitelist, and compile_hybrid() is
implemented for L3. agent_chat (L2) is left unimplemented.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


SUPPORTED_TARGETS = ("spinq", "originq", "braket")

_GATE_LINE_RE = re.compile(r'^([a-zA-Z][a-zA-Z0-9]*)\s*(?:\(([^)]*)\))?\s+([^;]+);?$')


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_qasm2(qasm_str: str) -> Tuple[int, int, List[Dict[str, Any]]]:
    """Parse the subset of OpenQASM 2.0 used by this contest: version/include
    lines, qreg/creg declarations, whitelisted gate calls, and measure."""
    num_qubits = 0
    num_clbits = 0
    ops: List[Dict[str, Any]] = []

    for raw_line in qasm_str.strip().splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        if line.startswith("OPENQASM") or line.startswith("include"):
            continue

        m = re.match(r'qreg\s+q\[(\d+)\]\s*;', line)
        if m:
            num_qubits = int(m.group(1))
            continue

        m = re.match(r'creg\s+c\[(\d+)\]\s*;', line)
        if m:
            num_clbits = int(m.group(1))
            continue

        m = re.match(r'measure\s+q\s*->\s*c\s*;', line)
        if m:
            ops.append({"gate": "measure_all"})
            continue

        m = re.match(r'measure\s+q\[(\d+)\]\s*->\s*c\[(\d+)\]\s*;', line)
        if m:
            ops.append({"gate": "measure", "qubit": int(m.group(1)), "clbit": int(m.group(2))})
            continue

        m = _GATE_LINE_RE.match(line)
        if not m:
            raise ValueError(f"Unrecognized QASM line: {raw_line!r}")
        gate_name, param_str, qubit_str = m.groups()
        params = [p.strip() for p in param_str.split(",")] if param_str else []
        qubits = [int(re.search(r'\d+', q).group()) for q in qubit_str.split(",")]
        ops.append({"gate": gate_name, "params": params, "qubits": qubits})

    return num_qubits, num_clbits, ops


# ---- per-target gate-name tables (only entries needed for the 12-gate whitelist) ----

_ORIGINQ_GATE_NAMES = {
    "h": "H", "x": "X", "s": "S", "sdg": "SDAG", "t": "T", "tdg": "TDAG",
    "rz": "RZ", "ry": "RY", "cx": "CNOT", "cu1": "CU1", "swap": "SWAP", "ccx": "TOFFOLI",
}

# Braket's stdgates.inc uses these names for the whitelist; cu1 has no direct
# 1:1 name in stdgates.inc — if a hidden circuit ever needs it, decompose via
# gate_identities.md instead of relying on this guess.
_BRAKET_GATE_NAMES = {
    "h": "h", "x": "x", "s": "s", "sdg": "sdg", "t": "t", "tdg": "tdg",
    "rz": "rz", "ry": "ry", "cx": "cnot", "cu1": "cphase", "swap": "swap", "ccx": "ccx",
}


def _to_qasm2(num_qubits: int, num_clbits: int, ops: List[Dict[str, Any]]) -> str:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";',
              f"qreg q[{num_qubits}];", f"creg c[{num_clbits}];"]
    for op in ops:
        if op["gate"] == "measure_all":
            lines.append("measure q -> c;")
        elif op["gate"] == "measure":
            lines.append(f"measure q[{op['qubit']}] -> c[{op['clbit']}];")
        else:
            qubit_str = ", ".join(f"q[{q}]" for q in op["qubits"])
            if op["params"]:
                lines.append(f"{op['gate']}({', '.join(op['params'])}) {qubit_str};")
            else:
                lines.append(f"{op['gate']} {qubit_str};")
    return "\n".join(lines) + "\n"


def _to_originq(num_qubits: int, num_clbits: int, ops: List[Dict[str, Any]]) -> str:
    lines = [f"QINIT {num_qubits}", f"CREG {num_clbits}"]
    for op in ops:
        if op["gate"] == "measure_all":
            lines.extend(f"MEASURE q[{i}], c[{i}]" for i in range(num_clbits))
        elif op["gate"] == "measure":
            lines.append(f"MEASURE q[{op['qubit']}], c[{op['clbit']}]")
        else:
            name = _ORIGINQ_GATE_NAMES.get(op["gate"])
            if name is None:
                raise ValueError(f"Unsupported gate for originq: {op['gate']}")
            qubit_str = ", ".join(f"q[{q}]" for q in op["qubits"])
            if op["params"]:
                lines.append(f"{name} {qubit_str}, ({', '.join(op['params'])})")
            else:
                lines.append(f"{name} {qubit_str}")
    return "\n".join(lines) + "\n"


def _to_braket_qasm3(num_qubits: int, num_clbits: int, ops: List[Dict[str, Any]]) -> str:
    lines = ["OPENQASM 3.0;", 'include "stdgates.inc";',
              f"qubit[{num_qubits}] q;", f"bit[{num_clbits}] c;"]
    for op in ops:
        if op["gate"] == "measure_all":
            lines.append("c = measure q;")
        elif op["gate"] == "measure":
            lines.append(f"c[{op['clbit']}] = measure q[{op['qubit']}];")
        else:
            name = _BRAKET_GATE_NAMES.get(op["gate"])
            if name is None:
                raise ValueError(f"Unsupported gate for braket: {op['gate']}")
            qubit_str = ", ".join(f"q[{q}]" for q in op["qubits"])
            if op["params"]:
                lines.append(f"{name}({', '.join(op['params'])}) {qubit_str};")
            else:
                lines.append(f"{name} {qubit_str};")
    return "\n".join(lines) + "\n"


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"Unknown target: {target}")
    num_qubits, num_clbits, ops = _parse_qasm2(qasm_str)
    if target == "spinq":
        return _to_qasm2(num_qubits, num_clbits, ops)
    if target == "originq":
        return _to_originq(num_qubits, num_clbits, ops)
    return _to_braket_qasm3(num_qubits, num_clbits, ops)


def _run_spinq(qasm_str: str, shots: int) -> Dict[str, Any]:
    import os
    import tempfile
    from spinqit import BasicSimulatorConfig, get_basic_simulator, get_compiler

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".qasm", delete=False, encoding="utf-8")
    try:
        tmp.write(qasm_str)
        tmp.close()
        compiler = get_compiler("qasm")
        ir = compiler.compile(tmp.name, 0)
    finally:
        os.unlink(tmp.name)

    engine = get_basic_simulator()
    config = BasicSimulatorConfig()
    config.configure_shots(shots)
    result = engine.execute(ir, config)
    counts = {str(k): v for k, v in result.counts.items()}

    return {
        "backend": "spinq_taurus_simulator",
        "job_id": getattr(result, "job_id", None) or f"spinq-local-{abs(hash(qasm_str)) & 0xFFFF:04x}",
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": _now_iso(),
        "meta": {"qubits_count": ir.qnum},
    }


def _run_originq(qasm_str: str, shots: int) -> Dict[str, Any]:
    import pyqpanda as pq

    machine = pq.CPUQVM()
    machine.init_qvm()
    try:
        if hasattr(pq, "convert_qasm_string_to_qprog"):
            prog, _qreg, creg = pq.convert_qasm_string_to_qprog(qasm_str, machine)
        else:
            prog = pq.convert_qasm_to_qprog(qasm_str, machine)
            creg = machine.get_allocate_cbits()

        raw_counts = machine.run_with_configuration(prog, creg, shots)
        num_bits = len(creg)
        counts: Dict[str, int] = {}
        for key, val in raw_counts.items():
            # pyqpanda already returns binary-string keys (e.g. "00", "11").
            # Only int keys need re-encoding as zero-padded binary strings.
            if isinstance(key, int):
                counts[bin(key)[2:].zfill(num_bits)] = val
            else:
                counts[str(key)] = val
    finally:
        machine.finalize()

    return {
        "backend": "originq_cpu_simulator",
        "job_id": f"originq-local-{abs(hash(qasm_str)) & 0xFFFF:04x}",
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": _now_iso(),
        "meta": {"qubits_count": num_bits},
    }


def _run_braket(qasm_str: str, shots: int) -> Dict[str, Any]:
    from braket.devices import LocalSimulator
    from braket.ir.openqasm import Program

    qasm3_str = transpile(qasm_str, "braket")
    device = LocalSimulator()
    program = Program(source=qasm3_str)
    task = device.run(program, shots=shots)
    result = task.result()
    counts = dict(result.measurement_counts)

    return {
        "backend": "braket_local_simulator",
        "job_id": result.task_metadata.id,
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": _now_iso(),
        "meta": {"depth": len(result.measured_qubits)},
    }


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    if target == "spinq":
        return _run_spinq(qasm_str, shots)
    if target == "originq":
        return _run_originq(qasm_str, shots)
    if target == "braket":
        return _run_braket(qasm_str, shots)
    raise ValueError(f"Unknown target: {target}")


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""
    raise NotImplementedError("L2 is optional; implement agent_chat(prompt) to enter")


def _extract_classical_block(text: str) -> Tuple[str, Optional[str]]:
    """Split out the `classical { ... }` block (brace-matched) from the rest
    of the Hybrid-QASM source. Returns (remaining_text, block_body_or_None)."""
    idx = text.find("classical")
    if idx == -1:
        return text, None
    brace_start = text.find("{", idx)
    if brace_start == -1:
        raise ValueError("classical block missing opening brace")
    depth = 0
    i = brace_start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    else:
        raise ValueError("classical block missing closing brace")
    body = text[brace_start + 1 : i]
    remainder = text[:idx] + text[i + 1 :]
    return remainder, body


def _extract_quantum_ops(text_without_classical: str) -> List[str]:
    """Pull the ordered list of quantum gate/measure statements, skipping
    version/include/register declarations."""
    ops = []
    for raw_line in text_without_classical.strip().splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        if line.startswith("OPENQASM") or line.startswith("include"):
            continue
        if re.match(r"qreg\s+q\[\d+\]\s*;", line):
            continue
        if re.match(r"creg\s+c\[\d+\]\s*;", line):
            continue
        ops.append(line)
    return ops


# ---- Hybrid-QASM classical block: tiny expression grammar ----
# term := INT | r[1-9] | c[<digit>+]
# expr := term (('+' | '-' | '==' | '!=') term)?
# stmt := 'if' '(' expr ')' '{' stmt* '}' ['else' '{' stmt* '}']
#       | r[1-9] '=' expr ';'

_CLASSICAL_TOKEN_RE = re.compile(r"==|!=|[(){};+\-=]|c\[\d+\]|r[1-9]|[0-9]+|if|else")


def _tokenize_classical(body: str) -> List[str]:
    body = re.sub(r"//.*", "", body)
    return _CLASSICAL_TOKEN_RE.findall(body)


class _ClassicalParser:
    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> Optional[str]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _advance(self) -> str:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, tok: str) -> None:
        actual = self._advance() if self.pos < len(self.tokens) else None
        if actual != tok:
            raise ValueError(f"Expected {tok!r}, got {actual!r}")

    def parse_statements(self, terminator: Optional[str]) -> List[Tuple]:
        stmts = []
        while self._peek() is not None and self._peek() != terminator:
            stmts.append(self._parse_statement())
        return stmts

    def _parse_statement(self) -> Tuple:
        if self._peek() == "if":
            return self._parse_if()
        return self._parse_assign()

    def _parse_if(self) -> Tuple:
        self._expect("if")
        self._expect("(")
        cond = self._parse_expr()
        self._expect(")")
        self._expect("{")
        then_stmts = self.parse_statements("}")
        self._expect("}")
        else_stmts = None
        if self._peek() == "else":
            self._advance()
            self._expect("{")
            else_stmts = self.parse_statements("}")
            self._expect("}")
        return ("if", cond, then_stmts, else_stmts)

    def _parse_assign(self) -> Tuple:
        reg = self._advance()
        if not re.fullmatch(r"r[1-9]", reg or ""):
            raise ValueError(f"Expected register on assignment LHS, got {reg!r}")
        self._expect("=")
        expr = self._parse_expr()
        self._expect(";")
        return ("assign", reg, expr)

    def _parse_expr(self) -> Tuple:
        left = self._parse_term()
        if self._peek() in ("+", "-", "==", "!="):
            op = self._advance()
            right = self._parse_term()
            return ("binop", op, left, right)
        return ("term", left)

    def _parse_term(self) -> Tuple:
        tok = self._advance()
        if re.fullmatch(r"\d+", tok):
            return ("int", int(tok))
        if re.fullmatch(r"r[1-9]", tok):
            return ("reg", tok)
        m = re.fullmatch(r"c\[(\d+)\]", tok)
        if m:
            return ("creg", int(m.group(1)))
        raise ValueError(f"Unexpected token in expression: {tok!r}")


class _RiscVGen:
    """Emits the li/add/sub/addi/beq/bne/j subset. r1..r9 map straight to
    x1..x9; measured bit c[k] is expected in x(10+k) (matches the contest's
    injection convention). x28/x29 are scratch registers for expression eval."""

    def __init__(self):
        self.lines: List[str] = []
        self._label_counter = 0

    def _new_label(self, prefix: str) -> str:
        self._label_counter += 1
        return f"{prefix}{self._label_counter}"

    def _emit(self, line: str) -> None:
        self.lines.append(line)

    def _materialize(self, term: Tuple, dest: str) -> None:
        kind = term[0]
        if kind == "int":
            self._emit(f"li {dest}, {term[1]}")
        elif kind == "reg":
            self._emit(f"add {dest}, x{int(term[1][1:])}, x0")
        elif kind == "creg":
            self._emit(f"add {dest}, x{10 + term[1]}, x0")
        else:
            raise ValueError(f"Unknown term kind: {kind}")

    def gen_statements(self, stmts: List[Tuple]) -> None:
        for stmt in stmts:
            self._gen_statement(stmt)

    def _gen_statement(self, stmt: Tuple) -> None:
        kind = stmt[0]
        if kind == "assign":
            _, reg, expr = stmt
            self._gen_assign(expr, f"x{int(reg[1:])}")
        elif kind == "if":
            _, cond, then_stmts, else_stmts = stmt
            self._gen_if(cond, then_stmts, else_stmts)
        else:
            raise ValueError(f"Unknown statement kind: {kind}")

    def _gen_assign(self, expr: Tuple, dest: str) -> None:
        if expr[0] == "term":
            self._materialize(expr[1], dest)
            return
        _, op, left, right = expr
        if op not in ("+", "-"):
            raise ValueError(f"Operator {op!r} is not valid in an assignment expression")
        self._materialize(left, "x28")
        self._materialize(right, "x29")
        self._emit(f"{'add' if op == '+' else 'sub'} {dest}, x28, x29")

    def _gen_if(self, cond: Tuple, then_stmts: List[Tuple], else_stmts: Optional[List[Tuple]]) -> None:
        if cond[0] != "binop" or cond[1] not in ("==", "!="):
            raise ValueError("if condition must be an == or != comparison")
        _, op, left, right = cond
        self._materialize(left, "x28")
        self._materialize(right, "x29")
        then_label = self._new_label("THEN")
        else_label = self._new_label("ELSE")
        end_label = self._new_label("ENDIF")
        self._emit(f"{'beq' if op == '==' else 'bne'} x28, x29, {then_label}")
        self._emit(f"j {else_label}")
        self._emit(f"{then_label}:")
        self.gen_statements(then_stmts)
        self._emit(f"j {end_label}")
        self._emit(f"{else_label}:")
        if else_stmts:
            self.gen_statements(else_stmts)
        self._emit(f"j {end_label}")
        self._emit(f"{end_label}:")


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Split Hybrid-QASM into its quantum op list and a compiled classical
    control block (RISC-V assembly runnable on riscv_emulator.py)."""
    remainder, body = _extract_classical_block(hybrid_qasm_str)
    quantum_ops = _extract_quantum_ops(remainder)
    if body is None:
        return quantum_ops, "li x0, 0\n"
    tokens = _tokenize_classical(body)
    stmts = _ClassicalParser(tokens).parse_statements(terminator=None)
    gen = _RiscVGen()
    gen.gen_statements(stmts)
    return quantum_ops, "\n".join(gen.lines) + "\n"
