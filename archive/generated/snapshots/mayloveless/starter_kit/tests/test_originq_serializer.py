"""OriginIR Serializer 与 adapter 路由测试。"""

import math
import unittest
from unittest import mock

import adapter
from loomq.ir import Circuit, GateOperation, QubitRef
from loomq.parser import parse_qasm
from loomq.serializers import serialize_originq


HEADER = 'OPENQASM 2.0; include "qelib1.inc"; '


class OriginQSerializerTests(unittest.TestCase):
    def test_bell_is_complete_exact_originir(self) -> None:
        source = HEADER + "qreg q[2]; creg c[2]; h q[0]; cx q[0], q[1]; measure q -> c;"
        self.assertEqual(
            "QINIT 2\nCREG 2\nH q[0]\nCNOT q[0], q[1]\n"
            "MEASURE q[0], c[0]\nMEASURE q[1], c[1]\n",
            serialize_originq(parse_qasm(source)),
        )

    def test_all_twelve_gates_and_stable_parameters(self) -> None:
        source = HEADER + (
            "qreg q[3]; creg c[3]; h q[0]; x q[0]; s q[0]; sdg q[0]; "
            "t q[0]; tdg q[0]; ry(pi/2) q[0]; rz(-pi/4) q[1]; "
            "cx q[0], q[1]; cu1(3*pi/8) q[0], q[1]; swap q[0], q[1]; "
            "ccx q[0], q[1], q[2]; measure q -> c;"
        )
        lines = serialize_originq(parse_qasm(source)).splitlines()
        self.assertEqual(
            [
                "H q[0]", "X q[0]", "S q[0]",
                "RZ q[0],(%s)" % format(-math.pi / 2, ".17g"), "T q[0]",
                "RZ q[0],(%s)" % format(-math.pi / 4, ".17g"),
                "RY q[0],(%s)" % format(math.pi / 2, ".17g"),
                "RZ q[1],(%s)" % format(-math.pi / 4, ".17g"), "CNOT q[0], q[1]",
                "CR q[0], q[1],(%s)" % format(3 * math.pi / 8, ".17g"),
                "SWAP q[0], q[1]", "TOFFOLI q[0], q[1], q[2]",
            ],
            lines[2:14],
        )

    def test_public_and_execution_modes_use_contract_sdk_compatible_syntax(self) -> None:
        source = HEADER + (
            "qreg q[2]; creg c[2]; sdg q[0]; tdg q[1]; "
            "ry(pi/2) q[0]; rz(-pi/4) q[1]; cu1(pi/8) q[0], q[1]; "
            "measure q -> c;"
        )

        public = serialize_originq(parse_qasm(source))
        execution = serialize_originq(parse_qasm(source), execution_mode=True)

        self.assertEqual(public, execution)
        self.assertNotIn("SDAG", public)
        self.assertNotIn("TDAG", public)
        self.assertIn("RZ q[0],(%s)" % format(-math.pi / 2, ".17g"), public)
        self.assertIn("RZ q[1],(%s)" % format(-math.pi / 4, ".17g"), public)
        self.assertIn("RY q[0],(%s)" % format(math.pi / 2, ".17g"), public)
        self.assertIn("CR q[0], q[1],(%s)" % format(math.pi / 8, ".17g"), public)

    def test_multiple_registers_and_crossed_measurements_are_flattened(self) -> None:
        source = HEADER + (
            "qreg qa[2]; qreg qb[1]; creg ca[1]; creg cb[2]; x qb[0]; "
            "measure qb[0] -> ca[0]; measure qa[1] -> cb[1];"
        )
        self.assertEqual(
            "QINIT 3\nCREG 3\nX q[2]\nMEASURE q[2], c[0]\nMEASURE q[1], c[2]\n",
            serialize_originq(parse_qasm(source)),
        )

    def test_register_measurement_expands_and_preserves_operation_order(self) -> None:
        source = HEADER + (
            "qreg left[2]; qreg right[1]; creg low[2]; creg high[1]; "
            "h left[0]; measure right -> high; x left[1]; measure left -> low;"
        )
        self.assertEqual(
            ["QINIT 3", "CREG 3", "H q[0]", "MEASURE q[2], c[2]", "X q[1]",
             "MEASURE q[0], c[0]", "MEASURE q[1], c[1]"],
            serialize_originq(parse_qasm(source)).splitlines(),
        )

    def test_unmeasured_classical_bits_remain_in_creg(self) -> None:
        source = HEADER + "qreg q[1]; creg c[3]; measure q[0] -> c[1];"
        self.assertEqual(
            "QINIT 1\nCREG 3\nMEASURE q[0], c[1]\n",
            serialize_originq(parse_qasm(source)),
        )

    def test_rejects_unsupported_gate_and_wrong_arity(self) -> None:
        circuit = Circuit("2.0", (), (), (GateOperation("z", (), ()),))
        with self.assertRaisesRegex(ValueError, "unsupported OriginIR gate"):
            serialize_originq(circuit)
        circuit = Circuit(
            "2.0", (), (), (GateOperation("h", (QubitRef("q", 0),), (1.0,)),)
        )
        with self.assertRaisesRegex(ValueError, "expects 0 parameters"):
            serialize_originq(circuit)

    def test_adapter_transpile_routes_originq_and_run_routes_parsed_ir(self) -> None:
        source = HEADER + "qreg q[1]; creg c[1]; x q[0]; measure q -> c;"
        self.assertEqual("QINIT 1\nCREG 1\nX q[0]\nMEASURE q[0], c[0]\n", adapter.transpile(source, "originq"))
        expected = {"backend": "sentinel"}
        with mock.patch("adapter.run_originq", return_value=expected) as runner:
            self.assertIs(expected, adapter.run(source, "originq", 1))
        self.assertIsInstance(runner.call_args.args[0], Circuit)
        self.assertEqual(1, runner.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
