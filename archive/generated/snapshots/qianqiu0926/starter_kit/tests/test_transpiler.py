import math
import random
import unittest

from loomq.emitters import emit_target
from loomq.ir import QASMError, parse_qasm2
from loomq.simulator import exact_probabilities, execute
from loomq.verification import certify_translation, verify_translation


def qasm_for(gates, qubits=3):
    return "\n".join([
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{qubits}];",
        f"creg c[{qubits}];",
        *gates,
        "measure q -> c;",
        "",
    ])


class TranspilerTests(unittest.TestCase):
    def test_public_entanglement_distributions(self):
        bell = parse_qasm2(qasm_for(["h q[0];", "cx q[0], q[1];"], 2))
        ghz = parse_qasm2(qasm_for(["h q[0];", "cx q[0], q[1];", "cx q[0], q[2];"], 3))
        self.assertEqual(exact_probabilities(bell), {"00": 0.5, "11": 0.5})
        self.assertEqual(exact_probabilities(ghz), {"000": 0.5, "111": 0.5})

    def test_bit_order_has_c0_on_the_right(self):
        circuit = parse_qasm2(qasm_for(["x q[0];"], 3))
        self.assertEqual(exact_probabilities(circuit), {"001": 1.0})

    def test_gate_inverse_relations(self):
        cases = [
            ["h q[0];", "h q[0];"],
            ["x q[0];", "x q[0];"],
            ["h q[0];", "s q[0];", "sdg q[0];", "h q[0];"],
            ["h q[0];", "t q[0];", "tdg q[0];", "h q[0];"],
            ["h q[0];", "ry(0.731) q[0];", "ry(-0.731) q[0];", "h q[0];"],
            ["h q[0];", "rz(pi/7) q[0];", "rz(-pi/7) q[0];", "h q[0];"],
            ["x q[0];", "cx q[0], q[1];", "cx q[0], q[1];", "x q[0];"],
            ["x q[0];", "swap q[0], q[1];", "swap q[0], q[1];", "x q[0];"],
            ["x q[0];", "x q[1];", "ccx q[0], q[1], q[2];", "ccx q[0], q[1], q[2];", "x q[1];", "x q[0];"],
            ["h q[0];", "h q[1];", "cu1(0.42) q[0], q[1];", "cu1(-0.42) q[0], q[1];", "h q[1];", "h q[0];"],
        ]
        for gates in cases:
            with self.subTest(gates=gates):
                observed = exact_probabilities(parse_qasm2(qasm_for(gates)))
                self.assertAlmostEqual(observed.get("000", 0.0), 1.0, places=11)

    def test_randomized_translation_validation_all_targets(self):
        gate_names = ["h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx"]
        for seed in range(80):
            rng = random.Random(seed)
            qubits = rng.randint(3, 5)
            gates = []
            for _ in range(rng.randint(8, 28)):
                name = rng.choice(gate_names)
                arity = 1 if name in {"h", "x", "s", "sdg", "t", "tdg", "rz", "ry"} else (2 if name in {"cx", "cu1", "swap"} else 3)
                operands = rng.sample(range(qubits), arity)
                parameter = f"({rng.uniform(-2 * math.pi, 2 * math.pi):.16g})" if name in {"rz", "ry", "cu1"} else ""
                gates.append(f"{name}{parameter} " + ", ".join(f"q[{index}]" for index in operands) + ";")
            circuit = parse_qasm2(qasm_for(gates, qubits))
            for target in ("spinq", "originq", "braket"):
                with self.subTest(seed=seed, target=target):
                    artifact = emit_target(circuit, target)
                    self.assertLessEqual(verify_translation(circuit, artifact, target), 1e-11)

    def test_schema_and_deterministic_apportionment(self):
        circuit = parse_qasm2(qasm_for(["h q[0];"], 3))
        artifact = emit_target(circuit, "braket")
        result = execute(circuit, "braket", 8191, artifact)
        self.assertEqual(sum(result["counts"].values()), 8191)
        self.assertEqual(result["bit_order"], "little")
        self.assertNotIn("is_mock", result["meta"])

    def test_certificate_rejects_phase_bug_hidden_from_counts(self):
        circuit = parse_qasm2(qasm_for(["h q[0];"], 1))
        # S changes relative phase but leaves this circuit's computational-basis
        # measurement distribution unchanged. A counts-only oracle would miss it.
        bad_artifact = emit_target(circuit, "spinq").replace("measure q[0]", "s q[0];\nmeasure q[0]")
        with self.assertRaisesRegex(ValueError, "state distance"):
            certify_translation(circuit, bad_artifact, "spinq")

    def test_certificate_rejects_semantically_cancelled_trace_injection(self):
        circuit = parse_qasm2(qasm_for(["h q[0];"], 1))
        bad_artifact = emit_target(circuit, "spinq").replace(
            "measure q[0]", "x q[0];\nx q[0];\nmeasure q[0]"
        )
        with self.assertRaisesRegex(ValueError, "operation trace=False"):
            certify_translation(circuit, bad_artifact, "spinq")

    def test_verified_runtime_exposes_proof_receipt(self):
        from loomq.pipeline import verified_run

        result, _ = verified_run(qasm_for(["h q[0];"], 1), "braket", 101)
        certificate = result["meta"]["translation_certificate"]
        self.assertTrue(certificate["verified"])
        self.assertEqual(certificate["equivalence"], "global-phase")
        self.assertEqual(result["meta"]["executed_ir"], "independently-reparsed-target")

    def test_parser_rejects_ambiguous_or_unsafe_input(self):
        invalid = [
            "h q[0];",
            qasm_for(["made_up q[0];"]),
            qasm_for(["cx q[0] q[1];"]),
            qasm_for(["rz(__import__('os').system('id')) q[0];"]),
            qasm_for(["ccx q[0], q[0], q[1];"]),
        ]
        for source in invalid:
            with self.subTest(source=source), self.assertRaises(QASMError):
                parse_qasm2(source)


if __name__ == "__main__":
    unittest.main()
