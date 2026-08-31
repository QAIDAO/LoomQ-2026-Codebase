import math
import os
import sys
import types
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STARTER = ROOT
sys.path.insert(0, STARTER)

import l1_reference
import l1_regression
import loomq_l1


class ReferenceSimulatorTests(unittest.TestCase):
    def test_known_distributions_and_classical_bit_order(self):
        cases = {case.case_id: case for case in l1_regression.regression_cases()}
        self.assertEqual(
            {"00": 0.5, "11": 0.5},
            l1_reference.distribution(cases["public/bell.qasm"].source),
        )
        self.assertEqual(
            {"01001": 1.0},
            l1_reference.distribution(
                cases["extended/hidden/bit_order_asymmetric.qasm"].source
            ),
        )
        self.assertEqual(
            {"1011": 1.0},
            l1_reference.distribution(
                cases["extended/hidden/noncontiguous_measurement.qasm"].source
            ),
        )

    def test_all_gate_and_angle_cases_are_normalized(self):
        gate_cases = [
            case for case in l1_regression.regression_cases() if case.group == "gate"
        ]
        seen = set()
        parameter_angles = {"rz": set(), "ry": set(), "cu1": set()}
        for case in gate_cases:
            circuit = loomq_l1.parse_qasm(case.source)
            seen.update(gate.name for gate in circuit.gates)
            for gate in circuit.gates:
                if gate.name in parameter_angles:
                    parameter_angles[gate.name].update(gate.params)
            probabilities = l1_reference.distribution(circuit)
            self.assertAlmostEqual(1.0, sum(probabilities.values()), places=12)
        self.assertEqual(set(loomq_l1.GATE_SIGNATURES), seen)
        required = {0.0, math.pi / 2.0, -math.pi / 3.0, math.pi / 7.0}
        for name, angles in parameter_angles.items():
            with self.subTest(gate=name):
                self.assertTrue(required <= angles)

    def test_qft_grover_and_seeded_cases_are_nontrivial(self):
        first = l1_regression.regression_cases()
        second = l1_regression.regression_cases()
        self.assertEqual(first, second)
        by_id = {case.case_id: case for case in first}
        qft = l1_reference.distribution(by_id["extended/hidden/qft4.qasm"].source)
        grover = l1_reference.distribution(by_id["extended/hidden/grover3.qasm"].source)
        random_cases = [case for case in first if case.case_id.startswith("extended/random-")]
        self.assertEqual(16, len(qft))
        self.assertGreater(grover["111"], 0.75)
        self.assertEqual(3, len(random_cases))
        self.assertEqual(3, len({case.source for case in random_cases}))

    def test_native_gate_decompositions_match_statevectors(self):
        l1_regression.validate_decompositions()

    def test_global_phase_comparison(self):
        base = (1 / math.sqrt(2), 1j / math.sqrt(2))
        phase = complex(math.cos(0.37), math.sin(0.37))
        shifted = tuple(value * phase for value in base)
        self.assertTrue(l1_reference.equivalent_up_to_global_phase(base, shifted))
        self.assertFalse(
            l1_reference.equivalent_up_to_global_phase(base, (base[0], -base[1]))
        )


class RegressionHarnessTests(unittest.TestCase):
    def test_every_case_parses_and_emits_deterministically(self):
        for case in l1_regression.regression_cases():
            loomq_l1.parse_qasm(case.source)
            for target in l1_regression.DEFAULT_TARGETS:
                with self.subTest(case=case.case_id, target=target):
                    artifact = loomq_l1.transpile(case.source, target)
                    self.assertTrue(artifact.strip())
                    self.assertEqual(artifact, loomq_l1.transpile(case.source, target))

    def test_result_validation_rejects_schema_and_width_errors(self):
        valid = {
            "backend": "test",
            "job_id": "job",
            "shots": 4,
            "counts": {"00": 4},
            "bit_order": "little",
            "timestamp": "2026-08-03T00:00:00+00:00",
        }
        self.assertEqual(
            {"00": 1.0}, l1_regression._validate_result(valid, 4, 2)
        )
        mutations = (
            {**valid, "counts": {"0": 4}},
            {**valid, "counts": {"00": 3}},
            {**valid, "bit_order": "big"},
            {**valid, "meta": {"is_mock": True}},
        )
        for payload in mutations:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                l1_regression._validate_result(payload, 4, 2)

    def test_full_entrypoint_flow_with_in_memory_runner(self):
        def exact_counts(source, shots):
            probabilities = l1_reference.distribution(source)
            items = list(probabilities.items())
            counts = {key: int(value * shots) for key, value in items}
            remainder = shots - sum(counts.values())
            counts[max(items, key=lambda item: item[1])[0]] += remainder
            return counts

        fake = types.SimpleNamespace(
            transpile=loomq_l1.transpile,
            run=lambda source, target, shots: {
                "backend": "in-memory-" + target,
                "job_id": "job-" + target,
                "shots": shots,
                "counts": exact_counts(source, shots),
                "bit_order": "little",
                "timestamp": "2026-08-03T00:00:00+00:00",
            },
        )
        with mock.patch.dict(sys.modules, {"adapter": fake}):
            records = l1_regression.run_regression(
                l1_regression.DEFAULT_TARGETS, reporter=lambda _message: None
            )
        self.assertEqual(
            len(l1_regression.regression_cases()) * 3,
            len(records),
        )
        self.assertTrue(all(record["status"] == "PASS" for record in records))

    def test_production_path_has_no_reference_or_case_hardcoding(self):
        filenames = ("adapter.py", "l1_spinq.py", "l1_originq.py", "l1_braket.py")
        for filename in filenames:
            with open(os.path.join(STARTER, filename), encoding="utf-8") as handle:
                source = handle.read().lower()
            with self.subTest(filename=filename):
                self.assertNotIn("l1_reference", source)
                self.assertNotIn("l1_regression", source)
                self.assertNotIn("bell.qasm", source)
                self.assertNotIn("ghz3.qasm", source)


if __name__ == "__main__":
    unittest.main()
