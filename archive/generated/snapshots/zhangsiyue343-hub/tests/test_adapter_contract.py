"""Adapter-level contract: unified schema, transpile, hybrid semantics."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starter_kit.adapter import (SUPPORTED_TARGETS, compile_hybrid, run,
                                 run_all, transpile)
from starter_kit.evaluator import TinyRISCVEmulator, validate_schema

BELL = ('OPENQASM 2.0; include "qelib1.inc";\n'
        "qreg q[2]; creg c[2];\n"
        "h q[0]; cx q[0],q[1];\nmeasure q -> c;\n")

HYBRID = ("OPENQASM 2.0;\n"
          "include \"stdlib.inc\";\n"
          "qreg q[4];\n"
          "creg c[4];\n"
          "h q[0];\n"
          "cx q[0], q[1];\n"
          "cx q[1], q[2];\n"
          "cx q[2], q[3];\n"
          "measure q[0] -> c[0];\n"
          "measure q[1] -> c[1];\n"
          "measure q[2] -> c[2];\n"
          "measure q[3] -> c[3];\n"
          "classical {\n"
          "    if (c[0] == 1) {\n"
          "        r1 = r1 + 10;\n"
          "    } else {\n"
          "        r1 = 42;\n"
          "    }\n"
          "}\n")


class TestUnifiedSchema(unittest.TestCase):
    def test_schema_valid_for_every_target(self):
        for target in SUPPORTED_TARGETS:
            result = run(BELL, target, 128)
            ok, reason = validate_schema(result)
            self.assertTrue(ok, "%s: %s" % (target, reason))
            self.assertEqual(result["bit_order"], "little")
            self.assertEqual(result["shots"], 128)
            self.assertTrue(result["backend"])
            self.assertTrue(result["job_id"])
            self.assertLessEqual(len(set(result["counts"])), 4)

    def test_job_ids_are_unique_per_call(self):
        a = run(BELL, "spinq", 32)["job_id"]
        b = run(BELL, "spinq", 32)["job_id"]
        self.assertNotEqual(a, b)

    def test_native_ir_stripped_from_public_result(self):
        self.assertNotIn("native_ir", run(BELL, "originq", 16))


class TestTranspileContract(unittest.TestCase):
    def test_all_targets_transpile(self):
        for target in SUPPORTED_TARGETS:
            text = transpile(BELL, target)
            self.assertIsInstance(text, str)
            self.assertTrue(text.strip())

    def test_invalid_qasm_raises_value_error(self):
        with self.assertRaises(ValueError):
            transpile("qreg q[1]; frobnicate q[0];", "spinq")


class TestRunAll(unittest.TestCase):
    def test_concurrent_fanout_aggregates(self):
        reports = run_all(BELL, 64)
        self.assertEqual({r["target"] for r in reports}, set(SUPPORTED_TARGETS))
        self.assertTrue(all(r["ok"] for r in reports), reports)
        totals = [sum(r["result"]["counts"].values()) for r in reports]
        self.assertEqual(totals, [64, 64, 64])
        ids = {r["result"]["job_id"] for r in reports}
        self.assertEqual(len(ids), len(SUPPORTED_TARGETS))

    def test_failure_isolation(self):
        # one bad target among good ones must not sink the batch
        reports = run_all(BELL, 32,
                          targets=("spinq", "nope", "originq"))
        by_target = {r["target"]: r for r in reports}
        self.assertTrue(by_target["spinq"]["ok"])
        self.assertFalse(by_target["nope"]["ok"])
        self.assertIn("error", by_target["nope"])
        self.assertIsNone(by_target["nope"]["result"])


class TestCompileHybridContract(unittest.TestCase):
    def test_returns_quantum_ops_and_assembly(self):
        quantum_ops, assembly = compile_hybrid(HYBRID)
        self.assertIsInstance(quantum_ops, list)
        self.assertTrue(all(isinstance(op, str) for op in quantum_ops))
        self.assertEqual(len(quantum_ops), 8)      # 4 gates + 4 measures
        self.assertIn("x10", assembly)             # measurement lands in x10
        self.assertIn("x1", assembly)              # r1 result register touched

    def test_branch_semantics_on_official_emulator(self):
        """c[0]==1 -> r1 += 10 ; else -> r1 = 42 (spec mini-grammar)."""
        _ops, assembly = compile_hybrid(HYBRID)
        for injected, expected in ((1, 10), (0, 42)):
            emu = TinyRISCVEmulator()
            emu.load_program(assembly)
            emu.set_register("x10", injected)      # grader protocol
            result = emu.execute()
            self.assertEqual(result.get("x1", 0), expected,
                             "injected=%r" % injected)

    def test_malformed_input_raises(self):
        with self.assertRaises(Exception):
            compile_hybrid("not even qasm")


if __name__ == "__main__":
    unittest.main()
