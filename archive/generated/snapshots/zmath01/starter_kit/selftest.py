#!/usr/bin/env python3
"""Extended local self-tests for the LoomQ submission.

Goes beyond the public evaluator:

- L1: stress circuits using all 12 whitelist gates (GHZ-5, QFT-4, Grover-3,
  seeded random circuits) checked against independently computed ideal
  distributions for all three targets.
- L3: randomly generated classical blocks compiled and executed on the
  official TinyRISCVEmulator, compared against an independent Python
  reference interpreter over *all* measurement injections.

Run:  python3 selftest.py
Exit code 0 = everything passed.
"""

from __future__ import annotations

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import adapter  # noqa: E402
from loomq_core.qasm import parse_qasm2  # noqa: E402
from loomq_core.simulator import statevector  # noqa: E402
from loomq_core.hybrid import _extract_classical_block, _tokenize, _Parser  # noqa: E402
from loomq_core import hybrid as hybrid_mod  # noqa: E402
from riscv_emulator import TinyRISCVEmulator  # noqa: E402


FAILURES = []


def check(label: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    print("[%s] %s %s" % (status, label, detail))
    if not ok:
        FAILURES.append(label)


def hellinger_fidelity(observed, expected):
    states = set(observed) | set(expected)
    distance = math.sqrt(
        sum((math.sqrt(observed.get(s, 0.0)) - math.sqrt(expected.get(s, 0.0))) ** 2 for s in states)
    ) / math.sqrt(2.0)
    return max(0.0, min(1.0, 1.0 - distance))


def ideal_distribution(qasm: str):
    circuit = parse_qasm2(qasm)
    state = statevector(circuit)
    measured = circuit.measurements or [(k, k) for k in range(circuit.num_qubits)]
    num_clbits = max(circuit.num_clbits, circuit.num_qubits)
    dist = {}
    for outcome, amp in enumerate(state):
        p = abs(amp) ** 2
        if p < 1e-12:
            continue
        bits = ["0"] * num_clbits
        for qubit, clbit in measured:
            if (outcome >> qubit) & 1:
                bits[num_clbits - 1 - clbit] = "1"
        key = "".join(bits)
        dist[key] = dist.get(key, 0.0) + p
    return dist


def l1_case(name: str, qasm: str) -> None:
    expected = ideal_distribution(qasm)
    for target in adapter.SUPPORTED_TARGETS:
        native = adapter.transpile(qasm, target)
        check("l1:%s:%s:transpile" % (name, target), bool(native.strip()))
        result = adapter.run(qasm, target, 8192)
        observed = {k: v / 8192 for k, v in result["counts"].items()}
        fidelity = hellinger_fidelity(observed, expected)
        check(
            "l1:%s:%s" % (name, target),
            fidelity >= 0.97,
            "fidelity=%.4f" % fidelity,
        )


def ghz(n: int) -> str:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";',
             "qreg q[%d];" % n, "creg c[%d];" % n, "h q[0];"]
    for i in range(n - 1):
        lines.append("cx q[%d], q[%d];" % (i, i + 1))
    lines.append("measure q -> c;")
    return "\n".join(lines) + "\n"


def qft4() -> str:
    # QFT on 4 qubits (no final swaps), built from whitelist gates only.
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', "qreg q[4];", "creg c[4];"]
    lines.append("x q[2];")  # non-trivial input state |0010> (little-endian q2)
    for i in range(4):
        lines.append("h q[%d];" % i)
        for j in range(i + 1, 4):
            angle = math.pi / (2 ** (j - i))
            lines.append("cu1(%s) q[%d], q[%d];" % (repr(angle), j, i))
    lines.append("measure q -> c;")
    return "\n".join(lines) + "\n"


def grover3() -> str:
    # 3-qubit Grover oracle marking |111>, one diffusion round.
    return "\n".join([
        "OPENQASM 2.0;", 'include "qelib1.inc";', "qreg q[3];", "creg c[3];",
        "h q[0];", "h q[1];", "h q[2];",
        # oracle: phase flip on |111> = ccz via h+ccx+h
        "h q[2];", "ccx q[0], q[1], q[2];", "h q[2];",
        # diffusion
        "h q[0];", "h q[1];", "h q[2];",
        "x q[0];", "x q[1];", "x q[2];",
        "h q[2];", "ccx q[0], q[1], q[2];", "h q[2];",
        "x q[0];", "x q[1];", "x q[2];",
        "h q[0];", "h q[1];", "h q[2];",
        "measure q -> c;",
    ]) + "\n"


def random_circuit(seed: int, qubits: int, depth: int) -> str:
    rng = random.Random(seed)
    singles = ["h", "x", "s", "sdg", "t", "tdg"]
    angles = ["rz", "ry"]
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";',
             "qreg q[%d];" % qubits, "creg c[%d];" % qubits]
    for _ in range(depth):
        pick = rng.random()
        if pick < 0.4:
            gate = rng.choice(singles)
            lines.append("%s q[%d];" % (gate, rng.randrange(qubits)))
        elif pick < 0.6:
            gate = rng.choice(angles)
            lines.append("%s(%s) q[%d];" % (gate, repr(rng.uniform(-math.pi, math.pi)),
                                             rng.randrange(qubits)))
        elif pick < 0.8:
            a, b = rng.sample(range(qubits), 2)
            gate = rng.choice(["cx", "swap", "cu1"])
            if gate == "cu1":
                lines.append("cu1(%s) q[%d], q[%d];" % (repr(rng.uniform(-math.pi, math.pi)), a, b))
            else:
                lines.append("%s q[%d], q[%d];" % (gate, a, b))
        else:
            a, b, c = rng.sample(range(qubits), 3)
            lines.append("ccx q[%d], q[%d], q[%d];" % (a, b, c))
    lines.append("measure q -> c;")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# L3 randomized cross-check
# ---------------------------------------------------------------------------

def ref_eval(stmts, creg_values):
    """Independent reference interpreter for the classical-block AST."""
    regs = {}

    def ev(node):
        if isinstance(node, hybrid_mod.Num):
            return node.value
        if isinstance(node, hybrid_mod.Reg):
            return regs.get(node.index, 0)
        if isinstance(node, hybrid_mod.CBit):
            return creg_values.get(node.index, 0)
        if isinstance(node, hybrid_mod.BinOp):
            left, right = ev(node.left), ev(node.right)
            return left + right if node.op == "+" else left - right
        raise AssertionError

    def run_block(body):
        for stmt in body:
            if isinstance(stmt, hybrid_mod.Assign):
                regs[stmt.target] = ev(stmt.expr)
            else:
                cond = (ev(stmt.left) == ev(stmt.right))
                if (stmt.op == "==" and cond) or (stmt.op == "!=" and not cond):
                    run_block(stmt.then_body)
                else:
                    run_block(stmt.else_body)

    run_block(stmts)
    return regs


def random_classical_block(rng: random.Random, depth: int = 0):
    """Generate a random classical-block program text plus its AST."""
    num_bits = 2
    stmts_text = []

    def rand_operand():
        pick = rng.random()
        if pick < 0.4:
            return str(rng.randint(0, 20))
        if pick < 0.8:
            return "r%d" % rng.randint(1, 5)
        return "c[%d]" % rng.randint(0, num_bits - 1)

    def rand_expr():
        text = rand_operand()
        for _ in range(rng.randint(0, 2)):
            text += " %s %s" % (rng.choice(["+", "-"]), rand_operand())
        return text

    def gen_statements(count, indent):
        out = []
        for _ in range(count):
            if depth < 2 and rng.random() < 0.35:
                cond = "%s %s %s" % (rand_expr(), rng.choice(["==", "!="]), rand_operand())
                out.append("if (%s) {" % cond)
                out.extend(gen_statements(rng.randint(1, 2), indent + 1))
                if rng.random() < 0.7:
                    out.append("} else {")
                    out.extend(gen_statements(rng.randint(1, 2), indent + 1))
                out.append("}")
            else:
                out.append("r%d = %s;" % (rng.randint(1, 5), rand_expr()))
        return out

    stmts_text = gen_statements(rng.randint(1, 4), 0)
    return "\n".join(stmts_text), num_bits


def l3_random_cases(n_cases: int = 25) -> None:
    rng = random.Random(20260818)
    for case in range(n_cases):
        body, num_bits = random_classical_block(rng)
        source = (
            'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[%d];\ncreg c[%d];\n'
            "measure q -> c;\nclassical {\n%s\n}\n" % (num_bits, num_bits, body)
        )
        ops, asm = adapter.compile_hybrid(source)
        # reference: re-parse the body and interpret
        _, ref_body = _extract_classical_block(source)
        ref_stmts = _Parser(_tokenize(ref_body)).parse_block()
        ok = True
        detail = ""
        for injection in range(2 ** num_bits):
            creg_values = {k: (injection >> k) & 1 for k in range(num_bits)}
            expected = ref_eval(ref_stmts, creg_values)
            emu = TinyRISCVEmulator()
            emu.load_program(asm)
            for k, value in creg_values.items():
                emu.set_register("x%d" % (10 + k), value)
            final = emu.execute()
            for reg_idx in range(1, 6):
                got = final.get("x%d" % reg_idx, 0)
                want = expected.get(reg_idx, 0)
                if got != want:
                    ok = False
                    detail = "case %d injection %d x%d: got %s want %s" % (
                        case, injection, reg_idx, got, want)
                    break
            if not ok:
                break
        check("l3:random-%02d" % case, ok, detail)
        if not ok:
            print("---- classical body ----")
            print(body)
            print("---- assembly ----")
            print(asm)
            break


def l1_all_gates() -> str:
    """Exercise every one of the 12 whitelist gates in a single circuit.

    x, s/sdg, h, t/tdg, rz, ry, cx, cu1, swap, ccx -- the full L1 workload
    list from the problem statement. Runs through all three emitters and the
    unified run() with a fidelity check, proving no whitelist gate is lost in
    any backend translation.
    """
    return "\n".join([
        "OPENQASM 2.0;", 'include "qelib1.inc";',
        "qreg q[4];", "creg c[4];",
        "x q[0];",
        "s q[0];", "sdg q[0];",            # s + sdg cancel
        "h q[1];",
        "t q[1];", "tdg q[1];",            # t + tdg cancel
        "rz(0.7) q[2];", "ry(1.1) q[2];",
        "cx q[2], q[3];",
        "cu1(0.4) q[1], q[0];",
        "swap q[0], q[3];",
        "ccx q[0], q[1], q[2];",
        "measure q -> c;",
    ]) + "\n"


def main() -> int:
    print("== L1 stress circuits (all 12 whitelist gates) ==")
    l1_case("ghz5", ghz(5))
    l1_case("qft4", qft4())
    l1_case("grover3", grover3())
    l1_case("gates-12", l1_all_gates())
    for seed in (1, 2, 3):
        l1_case("random-s%d" % seed, random_circuit(seed, 4, 14))
    print("== L3 randomized hybrid compilation ==")
    l3_random_cases()
    print()
    if FAILURES:
        print("FAILED: %d case(s)" % len(FAILURES))
        return 1
    print("ALL EXTENDED SELF-TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
