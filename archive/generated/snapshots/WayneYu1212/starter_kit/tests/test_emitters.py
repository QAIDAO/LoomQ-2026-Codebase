import unittest

import pyqpanda as pq

from starter_kit.loomq.compiler.parser import parse_qasm
from starter_kit.tests.test_parser_validator import ALL_GATES_QASM, BELL_QASM


try:
    from starter_kit.loomq.compiler.metrics import circuit_metrics
    from starter_kit.loomq.emitters import SUPPORTED_TARGETS, emit
except ImportError:
    circuit_metrics = None
    emit = None
    SUPPORTED_TARGETS = None


class TargetEmitterTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(emit, "target emitters are missing")

    def test_bell_artifacts_are_complete_native_programs(self):
        parsed = parse_qasm(BELL_QASM)

        self.assertEqual(
            emit(parsed, "spinq"),
            """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
""",
        )
        self.assertEqual(
            emit(parsed, "originq"),
            """QINIT 2
CREG 2
H q[0]
CNOT q[0], q[1]
MEASURE q[0], c[0]
MEASURE q[1], c[1]
""",
        )
        self.assertEqual(
            emit(parsed, "braket"),
            """OPENQASM 3.0;
include "stdgates.inc";
qubit[2] q;
bit[2] c;
h q[0];
cnot q[0], q[1];
c[0] = measure q[0];
c[1] = measure q[1];
""",
        )

    def test_all_official_gates_map_to_each_target_contract(self):
        parsed = parse_qasm(ALL_GATES_QASM)
        spinq = emit(parsed, "spinq")
        originq = emit(parsed, "originq")
        braket = emit(parsed, "braket")

        for statement in (
            "sdg q[0];",
            "tdg q[1];",
            "rz(1.5707963267948966) q[0];",
            "cu1(0.78539816339744828) q[1], q[2];",
            "ccx q[0], q[1], q[2];",
        ):
            with self.subTest(target="spinq", statement=statement):
                self.assertIn(statement, spinq)
        for statement in (
            "RZ q[0],(1.5707963267948966)",
            "CR q[1], q[2],(0.78539816339744828)",
            "TOFFOLI q[0], q[1], q[2]",
        ):
            with self.subTest(target="originq", statement=statement):
                self.assertIn(statement, originq)
        self.assertNotIn("SDAG", originq)
        self.assertNotIn("TDAG", originq)
        self.assertEqual(originq.splitlines().count("S q[0]"), 4)
        self.assertEqual(originq.splitlines().count("T q[1]"), 8)
        for statement in (
            "si q[0];",
            "ti q[1];",
            "rz(1.5707963267948966) q[0];",
            "cphaseshift(0.78539816339744828) q[1], q[2];",
            "ccnot q[0], q[1], q[2];",
        ):
            with self.subTest(target="braket", statement=statement):
                self.assertIn(statement, braket)

    def test_originq_artifact_is_accepted_by_pyqpanda_parser(self):
        machine = pq.CPUQVM()
        machine.init_qvm()
        try:
            program, qubits, cbits = pq.convert_originir_str_to_qprog(
                emit(parse_qasm(ALL_GATES_QASM), "originq"), machine
            )
        finally:
            machine.finalize()

        self.assertIsNotNone(program)
        self.assertEqual((len(qubits), len(cbits)), (3, 3))

    def test_dispatch_rejects_unknown_target(self):
        self.assertEqual(SUPPORTED_TARGETS, ("spinq", "originq", "braket"))
        with self.assertRaisesRegex(ValueError, "unsupported target"):
            emit(parse_qasm(BELL_QASM), "not-a-platform")

    def test_metrics_count_gates_and_parallel_depth(self):
        source = BELL_QASM.replace(
            "h q[0];",
            "h q[0]; x q[1];",
        )
        metrics = circuit_metrics(parse_qasm(source))

        self.assertEqual(metrics, {"transpiled_gates": 3, "depth": 2})


if __name__ == "__main__":
    unittest.main()
