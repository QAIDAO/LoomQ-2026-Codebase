"""Deterministic L2 synthesis and capability-matrix normalization tests."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

from loomq.capabilities import (  # noqa: E402
    compatible_backends,
    load_capability_matrix,
    normalize_constraint_spec,
)
from loomq.gate_policy import PUBLIC_GATE_WHITELIST  # noqa: E402
from loomq.qasm import GateOperation, parse_openqasm2  # noqa: E402
from loomq.simulator import ideal_distribution  # noqa: E402
from loomq.synthesis import (  # noqa: E402
    CircuitSpec,
    normalize_circuit_spec,
    normalize_task_type,
    synthesize,
)


class DeterministicSynthesisTests(unittest.TestCase):
    def test_model_schema_aliases_normalize_to_one_internal_spec(self) -> None:
        self.assertEqual(normalize_task_type("generate-circuit"), "generate_qasm")
        spec = normalize_circuit_spec(
            {
                "spec": {
                    "target_state": "cat state",
                    "n_qubits": "5",
                }
            },
            "Please prepare the requested state.",
        )
        self.assertEqual(spec, CircuitSpec("ghz", 5))

    def test_known_families_emit_only_public_gates_and_match_targets(self) -> None:
        cases = (
            CircuitSpec("bell", 2),
            CircuitSpec("ghz", 5),
            CircuitSpec("uniform", 3),
            CircuitSpec("basis", 4, "1010"),
            CircuitSpec("phase_interference", 1),
            CircuitSpec("w", 3),
            CircuitSpec("qft", 4, "0101"),
            CircuitSpec("grover", 3, "101"),
        )
        for spec in cases:
            with self.subTest(spec=spec):
                result = synthesize(spec)
                program = parse_openqasm2(result.qasm)
                names = {
                    operation.name
                    for operation in program.operations
                    if isinstance(operation, GateOperation)
                }
                self.assertTrue(names <= PUBLIC_GATE_WHITELIST)
                distribution = ideal_distribution(result.qasm)
                expected_mass = sum(
                    distribution.get(state, 0.0)
                    for state in result.expected_dominant_states
                )
                self.assertGreaterEqual(expected_mass, 0.60)

    def test_w_state_has_three_equal_single_excitation_outcomes(self) -> None:
        result = synthesize(CircuitSpec("w", 3))
        distribution = ideal_distribution(result.qasm)
        self.assertEqual(set(distribution), {"001", "010", "100"})
        for probability in distribution.values():
            self.assertAlmostEqual(probability, 1 / 3, places=10)


class CapabilityMatrixTests(unittest.TestCase):
    def test_matrix_rows_are_typed_unique_and_validated(self) -> None:
        rows = load_capability_matrix()
        self.assertEqual(len({row.id for row in rows}), len(rows))
        self.assertTrue(all(row.max_qubits > 0 for row in rows))

    def test_constraint_aliases_are_normalized_before_selection(self) -> None:
        normalized = normalize_constraint_spec(
            {
                "minimum_qubits": "15",
                "backend_kind": "local",
                "zero_queue": "yes",
                "free_only": 1,
                "no_account": True,
                "platform": "originq",
            }
        )
        self.assertEqual(normalized["required_kind"], "simulator")
        self.assertEqual(normalized["allowed_platforms"], ("originq",))
        matches = compatible_backends(normalized)
        self.assertEqual([item.id for item in matches], ["originq_local_simulator"])


if __name__ == "__main__":
    unittest.main()
