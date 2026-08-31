"""Task 12B tests for independent statevector semantic verification."""

import importlib.util
import math
import unittest

from loomq.parser import parse_qasm
from loomq.semantic_verifier import (
    TargetSpecificationError,
    parse_target_specification,
    pure_state_fidelity,
    verify_semantics,
)


BRAKET_INSTALLED = importlib.util.find_spec("braket") is not None
SQRT_HALF = 1.0 / math.sqrt(2.0)


def target(qubit_count, amplitudes):
    return parse_target_specification(
        {
            "verification_mode": "statevector",
            "pure_state_requested": True,
            "qubit_count": qubit_count,
            "amplitudes": [
                {
                    "basis": basis,
                    "real": complex(value).real,
                    "imag": complex(value).imag,
                }
                for basis, value in amplitudes.items()
            ],
            "explanation": "test target",
        }
    )


def qasm(qubits, operations):
    return """OPENQASM 2.0;
include "qelib1.inc";
qreg q[%d];
%s
""" % (qubits, operations)


class TargetSpecificationTests(unittest.TestCase):
    def test_unlisted_amplitudes_are_zero_and_global_phase_is_ignored(self):
        bell = target(2, {"00": SQRT_HALF, "11": SQRT_HALF})
        actual = [-1.0 * SQRT_HALF, 0j, 0j, -1.0 * SQRT_HALF]
        self.assertAlmostEqual(pure_state_fidelity(actual, bell), 1.0)

    def test_relative_phase_error_is_detected(self):
        bell_plus = target(2, {"00": SQRT_HALF, "11": SQRT_HALF})
        bell_minus = [SQRT_HALF, 0j, 0j, -SQRT_HALF]
        self.assertAlmostEqual(pure_state_fidelity(bell_minus, bell_plus), 0.0)

    def test_target_must_be_finite_and_normalized(self):
        with self.assertRaisesRegex(TargetSpecificationError, "normalized"):
            target(2, {"00": 1.0, "11": 1.0})
        with self.assertRaisesRegex(TargetSpecificationError, "finite"):
            target(1, {"0": float("inf")})

    def test_target_judge_cannot_return_qasm(self):
        with self.assertRaisesRegex(TargetSpecificationError, "must not return QASM"):
            parse_target_specification(
                {
                    "verification_mode": "unsupported",
                    "pure_state_requested": False,
                    "unsupported_reason": "no_unique_target",
                    "qasm": "OPENQASM 2.0;",
                }
            )

    def test_explicit_pure_state_cannot_downgrade_to_unsupported(self):
        with self.assertRaisesRegex(
            TargetSpecificationError, "must use statevector"
        ):
            parse_target_specification(
                {
                    "verification_mode": "unsupported",
                    "pure_state_requested": True,
                    "unsupported_reason": "insufficient_spec",
                    "explanation": "judge failed to express the requested state",
                }
            )

    def test_unsupported_reason_is_required_and_enumerated(self):
        for reason in (
            "no_unique_target",
            "mixed_state",
            "distribution_only",
            "insufficient_spec",
        ):
            specification = parse_target_specification(
                {
                    "verification_mode": "unsupported",
                    "pure_state_requested": False,
                    "unsupported_reason": reason,
                    "explanation": "test",
                }
            )
            self.assertEqual(specification.unsupported_reason, reason)

        for reason in (None, "unknown"):
            with self.assertRaisesRegex(TargetSpecificationError, "unsupported_reason"):
                parse_target_specification(
                    {
                        "verification_mode": "unsupported",
                        "pure_state_requested": False,
                        "unsupported_reason": reason,
                        "explanation": "test",
                    }
                )


@unittest.skipUnless(BRAKET_INSTALLED, "amazon-braket-sdk is not installed")
class BraketSemanticVerifierTests(unittest.TestCase):
    def test_correct_bell_state_passes(self):
        circuit = parse_qasm(qasm(2, "h q[0];\ncx q[0],q[1];"))
        result = verify_semantics(
            circuit,
            target(2, {"00": SQRT_HALF, "11": SQRT_HALF}),
        )
        self.assertTrue(result.passed)
        self.assertAlmostEqual(result.fidelity, 1.0)

    def test_basis_order_matches_q0_to_qn_and_braket_statevector(self):
        q0_one = parse_qasm(qasm(2, "x q[0];"))
        q1_one = parse_qasm(qasm(2, "x q[1];"))
        self.assertTrue(verify_semantics(q0_one, target(2, {"10": 1.0})).passed)
        self.assertTrue(verify_semantics(q1_one, target(2, {"01": 1.0})).passed)

    def test_parser_valid_four_state_superposition_is_rejected_as_bell(self):
        circuit = parse_qasm(qasm(2, "h q[0];\nh q[1];"))
        result = verify_semantics(
            circuit,
            target(2, {"00": SQRT_HALF, "11": SQRT_HALF}),
        )
        self.assertFalse(result.passed)
        self.assertAlmostEqual(result.fidelity, 0.5)

    def test_correct_and_wrong_ghz_states(self):
        ghz_target = target(3, {"000": SQRT_HALF, "111": SQRT_HALF})
        correct = parse_qasm(qasm(3, "h q[0];\ncx q[0],q[1];\ncx q[1],q[2];"))
        wrong = parse_qasm(qasm(3, "h q[0];\nh q[1];\nh q[2];"))
        self.assertTrue(verify_semantics(correct, ghz_target).passed)
        wrong_result = verify_semantics(wrong, ghz_target)
        self.assertFalse(wrong_result.passed)
        self.assertAlmostEqual(wrong_result.fidelity, 0.25)

    def test_relative_phase_fails_but_global_phase_passes(self):
        bell_target = target(2, {"00": SQRT_HALF, "11": SQRT_HALF})
        relative_phase = parse_qasm(
            qasm(2, "h q[0];\ncx q[0],q[1];\ns q[0];\ns q[0];")
        )
        global_phase = parse_qasm(
            qasm(
                2,
                "x q[0];\ns q[0];\ns q[0];\nx q[0];\nh q[0];\ncx q[0],q[1];",
            )
        )
        self.assertFalse(verify_semantics(relative_phase, bell_target).passed)
        global_result = verify_semantics(global_phase, bell_target)
        self.assertTrue(global_result.passed)
        self.assertAlmostEqual(global_result.fidelity, 1.0)

    def test_measurements_are_removed_before_statevector_simulation(self):
        measured = parse_qasm(
            """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;
"""
        )
        result = verify_semantics(
            measured,
            target(2, {"00": SQRT_HALF, "11": SQRT_HALF}),
        )
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
