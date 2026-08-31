import math
import unittest

from starter_kit.loomq_l1.emitters import (
    emit,
    emit_braket,
    emit_originq,
    emit_spinq,
)
from starter_kit.loomq_l1.errors import QASMSemanticError, UnsupportedTargetError
from starter_kit.loomq_l1.model import Circuit, Measurement, Operation, Register
from starter_kit.loomq_l1.parser import parse_qasm


class EmitterTests(unittest.TestCase):
    _SOURCE = '''
        OPENQASM 2.0;
        include "qelib1.inc";
        qreg left[1]; qreg right[2]; creg low[1]; creg high[2];
        h left[0]; x right[0]; s right[1]; sdg left[0]; t right[0]; tdg right[1];
        rz(pi/2) left[0]; ry(-pi/4) right[0];
        cx left[0],right[0]; cu1(pi/2) left[0],right[0]; swap left[0],right[1];
        ccx left[0],right[0],right[1];
        measure left[0] -> low[0]; measure right[0] -> high[1]; measure right[1] -> high[0];
    '''

    def setUp(self):
        self.circuit = parse_qasm(self._SOURCE)

    def test_emits_exact_spinq_qasm_with_flattened_registers(self):
        self.assertEqual(
            emit(self.circuit, "spinq"),
            '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
x q[1];
s q[2];
sdg q[0];
t q[1];
tdg q[2];
rz(1.5707963267948966) q[0];
ry(-0.78539816339744828) q[1];
cx q[0], q[1];
cu1(1.5707963267948966) q[0], q[1];
swap q[0], q[2];
ccx q[0], q[1], q[2];
measure q[0] -> c[0];
measure q[1] -> c[2];
measure q[2] -> c[1];
''',
        )

    def test_emits_exact_originq_ir_with_flattened_registers(self):
        self.assertEqual(
            emit(self.circuit, "originq"),
            '''QINIT 3
CREG 3
H q[0]
X q[1]
S q[2]
SDAG q[0]
T q[1]
TDAG q[2]
RZ q[0], (1.5707963267948966)
RY q[1], (-0.78539816339744828)
CNOT q[0], q[1]
CU1 q[0], q[1], (1.5707963267948966)
SWAP q[0], q[2]
TOFFOLI q[0], q[1], q[2]
MEASURE q[0], c[0]
MEASURE q[1], c[2]
MEASURE q[2], c[1]
''',
        )

    def test_emits_exact_braket_qasm_with_flattened_registers(self):
        self.assertEqual(
            emit(self.circuit, "braket"),
            '''OPENQASM 3.0;
include "stdgates.inc";
bit[3] c;
qubit[3] q;
h q[0];
x q[1];
s q[2];
sdg q[0];
t q[1];
tdg q[2];
rz(1.5707963267948966) q[0];
ry(-0.78539816339744828) q[1];
cnot q[0], q[1];
cp(1.5707963267948966) q[0], q[1];
swap q[0], q[2];
ccx q[0], q[1], q[2];
c[0] = measure q[0];
c[2] = measure q[1];
c[1] = measure q[2];
''',
        )

    def test_required_provider_specific_output_substrings(self):
        spinq = emit(self.circuit, "spinq")
        originq = emit(self.circuit, "originq")
        braket = emit(self.circuit, "braket")

        self.assertIn("OPENQASM 2.0;", spinq)
        self.assertIn("qreg q[3];", spinq)
        self.assertIn("cu1(1.5707963267948966) q[0], q[1];", spinq)
        self.assertTrue(originq.startswith("QINIT 3\nCREG 3\n"))
        self.assertIn("SDAG q[0]", originq)
        self.assertIn("TDAG q[2]", originq)
        self.assertIn("CU1 q[0], q[1], (1.5707963267948966)", originq)
        self.assertIn("TOFFOLI q[0], q[1], q[2]", originq)
        self.assertIn("OPENQASM 3.0;", braket)
        self.assertIn('include "stdgates.inc";', braket)
        self.assertIn("cp(1.5707963267948966) q[0], q[1];", braket)
        self.assertIn("cnot q[0], q[1];", braket)
        self.assertIn("c[0] = measure q[0];", braket)

    def test_unknown_target_raises_existing_error(self):
        with self.assertRaises(UnsupportedTargetError):
            emit(self.circuit, "unknown")

    def test_rejects_duplicate_classical_measurement_destinations(self):
        circuit = Circuit(
            qregs=(Register("q", 1, 0),),
            cregs=(Register("c", 1, 0),),
            operations=(),
            measurements=(Measurement(0, 0), Measurement(0, 0)),
        )

        for target in ("spinq", "originq", "braket"):
            with self.subTest(target=target):
                with self.assertRaisesRegex(QASMSemanticError, "duplicate classical"):
                    emit(circuit, target)

    def test_rejects_invalid_register_structures_with_semantic_error(self):
        non_positive = Register("q", 1, 0)
        object.__setattr__(non_positive, "size", 0)
        cases = (
            Circuit((), (Register("c", 1, 0),), (), ()),
            Circuit((Register("q", 1, 0),), (), (), ()),
            Circuit([Register("q", 1, 0)], (Register("c", 1, 0),), (), ()),
            Circuit((object(),), (Register("c", 1, 0),), (), ()),
            Circuit(
                (Register("q", 1, 0), Register("q", 1, 1)),
                (Register("c", 1, 0),),
                (),
                (),
            ),
            Circuit((Register("q", 1, 0),), (Register("q", 1, 0),), (), ()),
            Circuit((Register("", 1, 0),), (Register("c", 1, 0),), (), ()),
            Circuit((Register(1, 1, 0),), (Register("c", 1, 0),), (), ()),
            Circuit((non_positive,), (Register("c", 1, 0),), (), ()),
        )

        for circuit in cases:
            with self.subTest(circuit=circuit):
                for target in ("spinq", "originq", "braket"):
                    with self.subTest(target=target):
                        with self.assertRaises(QASMSemanticError):
                            emit(circuit, target)

    def test_rejects_repeated_multi_qubit_operation_indices(self):
        cases = (
            Operation("cx", (0, 0)),
            Operation("swap", (1, 1)),
            Operation("ccx", (0, 1, 1)),
        )

        for operation in cases:
            circuit = Circuit(
                qregs=(Register("q", 3, 0),),
                cregs=(Register("c", 1, 0),),
                operations=(operation,),
                measurements=(),
            )
            with self.subTest(operation=operation):
                for target in ("spinq", "originq", "braket"):
                    with self.subTest(target=target):
                        with self.assertRaisesRegex(QASMSemanticError, "distinct qubit"):
                            emit(circuit, target)

    def test_public_provider_emitters_validate_before_rendering(self):
        circuit = Circuit(
            qregs=(Register("q", 1, 0),),
            cregs=(Register("c", 1, 0),),
            operations=(Operation("nope", (0,)),),
            measurements=(),
        )

        for emitter in (emit_spinq, emit_originq, emit_braket):
            with self.subTest(emitter=emitter.__name__):
                with self.assertRaisesRegex(QASMSemanticError, "unsupported operation"):
                    emitter(circuit)

    def test_rejects_nonreal_nonfinite_and_unrepresentable_parameters(self):
        parameters = ("not a number", math.inf, 10**400)
        providers = (emit_spinq, emit_originq, emit_braket)

        for parameter in parameters:
            circuit = Circuit(
                qregs=(Register("q", 1, 0),),
                cregs=(Register("c", 1, 0),),
                operations=(Operation("rz", (0,), parameter),),
                measurements=(),
            )
            with self.subTest(parameter=repr(parameter)):
                for target in ("spinq", "originq", "braket"):
                    with self.subTest(target=target):
                        with self.assertRaises(QASMSemanticError):
                            emit(circuit, target)
                for provider in providers:
                    with self.subTest(provider=provider.__name__):
                        with self.assertRaises(QASMSemanticError):
                            provider(circuit)

    def test_emission_is_deterministic_and_does_not_mutate_circuit(self):
        before = self.circuit
        first = emit(self.circuit, "spinq")
        second = emit(self.circuit, "spinq")

        self.assertEqual(first, second)
        self.assertEqual(self.circuit, before)
        self.assertTrue(first.endswith("\n"))
        self.assertFalse(first.endswith("\n\n"))

    def test_rejects_impossible_ir_with_existing_loomq_error(self):
        cases = (
            Circuit((), (), (Operation("nope", (0,)),), ()),
            Circuit((Register("q", 1, 0),), (), (Operation("cx", (0,)),), ()),
            Circuit((Register("q", 1, 0),), (), (Operation("h", (0,), 0.0),), ()),
            Circuit((Register("q", 1, 0),), (), (Operation("rz", (0,), None),), ()),
            Circuit((Register("q", 1, 0),), (), (Operation("rz", (0,), math.inf),), ()),
            Circuit((Register("q", 1, 0),), (), (Operation("h", (1,)),), ()),
            Circuit((), (Register("c", 1, 0),), (), (Measurement(0, 0),)),
        )

        for circuit in cases:
            with self.subTest(circuit=circuit):
                for target in ("spinq", "originq", "braket"):
                    with self.subTest(target=target):
                        with self.assertRaises(QASMSemanticError):
                            emit(circuit, target)


if __name__ == "__main__":
    unittest.main()
