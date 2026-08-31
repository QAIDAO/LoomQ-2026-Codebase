import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loomq.facade import run, transpile
from loomq.qasm import parse_and_normalize
from loomq.targets.roundtrip import parse_target_artifact


BELL = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""


class TargetEmitterTests(unittest.TestCase):
    def test_all_target_headers_and_measurements(self):
        spinq = transpile(BELL, "spinq")
        originq = transpile(BELL, "originq")
        braket = transpile(BELL, "braket")
        self.assertTrue(spinq.startswith("OPENQASM 2.0;"))
        self.assertIn("measure q[1] -> c[1];", spinq)
        self.assertTrue(originq.startswith("QINIT 2\nCREG 2"))
        self.assertIn("CNOT q[0], q[1]", originq)
        self.assertIn("MEASURE q[1], c[1]", originq)
        self.assertTrue(braket.startswith("OPENQASM 3.0;"))
        self.assertIn("cnot q[0], q[1];", braket)
        self.assertIn("c[1] = measure q[1];", braket)
        source = parse_and_normalize(BELL)
        self.assertEqual(parse_target_artifact(spinq, "spinq"), source)
        self.assertEqual(parse_target_artifact(originq, "originq"), source)
        self.assertEqual(parse_target_artifact(braket, "braket"), source)

    def test_controlled_phase_uses_braket_cp(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2]; creg c[2];
cu1(pi/3) q[0], q[1];
measure q -> c;
"""
        self.assertIn("cp(", transpile(source, "braket"))
        self.assertIn("CU1(", transpile(source, "originq"))

    def test_tiny_nonzero_angles_survive_all_target_round_trips(self):
        source = (
            'OPENQASM 2.0; include "qelib1.inc"; qreg q[1]; creg c[1]; '
            "ry(1e-20) q[0]; measure q -> c;"
        )
        for target in ("spinq", "originq", "braket"):
            with self.subTest(target=target):
                artifact = transpile(source, target)
                self.assertNotIn("ry(0)", artifact.lower())
                self.assertIn("e-21", artifact.lower())


class ReferenceRuntimeTests(unittest.TestCase):
    def test_bell_distribution_and_schema(self):
        payload = run(BELL, "spinq", 4096)
        self.assertEqual(payload["shots"], 4096)
        self.assertEqual(sum(payload["counts"].values()), 4096)
        self.assertEqual(set(payload["counts"]), {"00", "11"})
        self.assertEqual(payload["bit_order"], "little")
        self.assertEqual(payload["backend"], "loomq_reference_statevector_spinq")
        self.assertFalse(payload["meta"]["native_sdk_used"])
        self.assertEqual(payload["meta"]["execution_engine"], "loomq_reference_statevector")

    def test_rightmost_bit_is_c_zero(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2]; creg c[2];
x q[0];
measure q -> c;
"""
        payload = run(source, "originq", 32)
        self.assertEqual(payload["counts"], {"01": 32})

    def test_shots_boolean_is_rejected(self):
        with self.assertRaises(ValueError):
            run(BELL, "braket", True)


if __name__ == "__main__":
    unittest.main()
