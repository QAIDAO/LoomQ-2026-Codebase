"""First executable acceptance tests for the public L1 adapter contract."""

from __future__ import annotations

import sys
import unittest
from unittest import mock
from pathlib import Path


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

import adapter  # noqa: E402


BELL_QASM = (STARTER_KIT / "circuits" / "bell.qasm").read_text(encoding="utf-8")


class L1ContractTests(unittest.TestCase):
    """Verify output shape before adding semantic and randomized testing."""

    def test_spinq_transpile_contract(self) -> None:
        native = adapter.transpile(BELL_QASM, "spinq")
        upper = native.upper()
        self.assertIsInstance(native, str)
        self.assertIn("OPENQASM 2.0;", upper)
        self.assertIn('INCLUDE "QELIB1.INC";', upper)
        self.assertIn("QREG Q[2];", upper)
        self.assertIn("CREG C[2];", upper)
        self.assertIn("MEASURE", upper)

    def test_originq_transpile_contract(self) -> None:
        native = adapter.transpile(BELL_QASM, "originq")
        upper = native.upper()
        self.assertIsInstance(native, str)
        self.assertIn("QINIT 2", upper)
        self.assertIn("CREG 2", upper)
        self.assertIn("H Q[0]", upper)
        self.assertIn("CNOT Q[0], Q[1]", upper)
        self.assertIn("MEASURE Q[0], C[0]", upper)
        self.assertIn("MEASURE Q[1], C[1]", upper)

    def test_braket_transpile_contract(self) -> None:
        native = adapter.transpile(BELL_QASM, "braket")
        upper = native.upper()
        self.assertIsInstance(native, str)
        self.assertIn("OPENQASM 3.0;", upper)
        self.assertIn('INCLUDE "STDGATES.INC";', upper)
        self.assertIn("QUBIT[2] Q;", upper)
        self.assertIn("BIT[2] C;", upper)
        self.assertTrue("CX Q[0], Q[1];" in upper or "CNOT Q[0], Q[1];" in upper)
        self.assertIn("MEASURE", upper)

    def test_run_schema_for_all_targets(self) -> None:
        with mock.patch.dict("os.environ", {"LOOMQ_FORCE_REFERENCE_SIMULATOR": "1"}):
            for target in adapter.SUPPORTED_TARGETS:
                with self.subTest(target=target):
                    payload = adapter.run(BELL_QASM, target, shots=128)
                    self._assert_result_schema(payload)

    def _assert_result_schema(self, payload: object) -> None:
        self.assertIsInstance(payload, dict)
        for field in ("backend", "job_id", "shots", "counts", "bit_order", "timestamp"):
            self.assertIn(field, payload)
        self.assertIsInstance(payload["backend"], str)
        self.assertTrue(payload["backend"])
        self.assertIsInstance(payload["job_id"], str)
        self.assertTrue(payload["job_id"])
        self.assertEqual(payload["shots"], 128)
        self.assertEqual(payload["bit_order"], "little")
        self.assertIsInstance(payload["counts"], dict)
        self.assertTrue(payload["counts"])
        self.assertEqual(sum(payload["counts"].values()), 128)
        for bitstring, count in payload["counts"].items():
            self.assertTrue(bitstring)
            self.assertTrue(set(bitstring) <= {"0", "1"})
            self.assertIsInstance(count, int)
            self.assertGreaterEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
