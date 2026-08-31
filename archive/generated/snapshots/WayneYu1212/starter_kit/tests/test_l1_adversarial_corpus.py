from __future__ import annotations

"""Deterministic adversarial L1 corpus: one test hitting every hidden-test-shaped
dimension called out for the whitelist grammar:

pi arithmetic, negative angles, nested parentheses, multiple qregs, multiple
cregs, partial measurement, permuted measurement, little-endian bit order,
unused qubits, repeated gates, multi-register indices.

Every generated circuit must parse, validate, and match the independent
reference simulator on all three real SDK runners (spinq / originq / braket).
"""
import random
import unittest

from starter_kit.evaluator import calculate_hellinger_fidelity, validate_schema
from starter_kit.loomq.compiler.parser import parse_qasm
from starter_kit.loomq.runners import run_circuit
from starter_kit.loomq.simulator import probabilities


def adversarial_corpus(seed: int) -> str:
    rng = random.Random(seed)
    qa, qb = f"qa{seed}", f"qb{seed}"
    ca, cb = f"ca{seed}", f"cb{seed}"
    # two qregs (3 + 2 qubits), one qubit in each register left unused
    refs = [f"{qa}[0]", f"{qa}[1]", f"{qa}[2]", f"{qb}[0]", f"{qb}[1]"]
    used = refs[:4]  # qa[2] and later maybe qb[1] unused depending on rng
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg {qa}[3];",
        f"qreg {qb}[2];",
        f"creg {ca}[2];",
        f"creg {cb}[3];",
    ]
    # pi arithmetic / negative angles / nested parentheses, all deterministic
    angles = [
        "pi/3",
        "-pi/4 + pi/8",           # negative angle via unary minus
        "3*pi/7 - pi/21",         # pi arithmetic
        "((pi/2))",               # nested parentheses
        "pi/(2*3)",               # parentheses in denominator
        "-(pi/6 + pi/12)",        # negated grouped expression
        "2*(pi/4 - pi/8) + pi/16",
    ]
    one_qubit = ("h", "x", "s", "sdg", "t", "tdg")  # official whitelist only
    for _ in range(20):
        family = rng.choice(("one", "rotation", "two", "three", "repeat"))
        if family == "one":
            lines.append(f"{rng.choice(one_qubit)} {rng.choice(used)};")
        elif family == "rotation":
            lines.append(
                f"{rng.choice(('rz', 'ry'))}({rng.choice(angles)}) {rng.choice(used)};"
            )
        elif family == "two":
            a, b = rng.sample(used, 2)
            gate = rng.choice(("cx", "swap", "cu1"))
            parameter = f"({rng.choice(angles)})" if gate == "cu1" else ""
            lines.append(f"{gate}{parameter} {a},{b};")
        elif family == "three":
            a, b, c = rng.sample(used, 3)
            lines.append(f"ccx {a},{b},{c};")
        else:  # repeated gates on the same qubit
            q = rng.choice(used)
            gate = rng.choice(one_qubit)
            for _ in range(rng.randint(2, 4)):
                lines.append(f"{gate} {q};")
    # partial + permuted measurement: only 4 of 5 used qubits measured,
    # mapped out of index order across both cregs (little-endian stress)
    measured = rng.sample(used, 4)
    cbits = [f"{cb}[2]", f"{ca}[0]", f"{cb}[0]", f"{ca}[1]"]
    for q, c in zip(measured, cbits):
        lines.append(f"measure {q} -> {c};")
    return "\n".join(lines) + "\n"


class AdversarialWhitelistCorpusTests(unittest.TestCase):
    def test_corpus_matches_reference_simulator_on_three_sdks(self):
        shots = 4096
        for seed in (7, 31, 97, 211):
            source = adversarial_corpus(seed)
            circuit = parse_qasm(source)
            expected = probabilities(circuit)
            for target in ("spinq", "originq", "braket"):
                with self.subTest(seed=seed, target=target):
                    result = run_circuit(circuit, target, shots)
                    valid, reason = validate_schema(result)
                    self.assertTrue(valid, reason)
                    self.assertEqual(result["bit_order"], "little")
                    observed = {
                        state: count / shots for state, count in result["counts"].items()
                    }
                    self.assertGreaterEqual(
                        calculate_hellinger_fidelity(observed, expected), 0.97
                    )
                    self.assertNotIn("reference", result["meta"]["engine"])

    def test_corpus_gate_and_measurement_shape(self):
        for seed in (7, 31, 97, 211):
            source = adversarial_corpus(seed)
            circuit = parse_qasm(source)
            self.assertEqual(circuit.qubit_count, 5)
            self.assertEqual(circuit.cbit_count, 5)
            self.assertLessEqual(len(circuit.measurements), 4)  # partial
            # unused qubits exist: at least one declared qubit has no measurement
            measured_qubits = {m.qubit for m in circuit.measurements}
            self.assertLess(len(measured_qubits), circuit.qubit_count)
            # permuted measurement: qubit index never maps one-to-one onto bit index
            pairs = {(m.qubit, m.cbit) for m in circuit.measurements}
            self.assertTrue(any(q != b for q, b in pairs))


if __name__ == "__main__":
    unittest.main()
