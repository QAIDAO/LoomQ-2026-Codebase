import math
import random
import re
import unittest

from starter_kit.adapter import run, transpile
from starter_kit.qasm_core import parse_qasm


GATES = ("h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx")


def signature(circuit):
    return [
        (operation.name, operation.qubits, operation.cbits, operation.params)
        for operation in circuit.operations
    ]


def assert_operations_equal(testcase, expected, actual):
    testcase.assertEqual(len(expected), len(actual))
    for wanted, observed in zip(expected, actual):
        testcase.assertEqual(wanted[:3], observed[:3])
        testcase.assertEqual(len(wanted[3]), len(observed[3]))
        for left, right in zip(wanted[3], observed[3]):
            testcase.assertTrue(math.isclose(left, right, rel_tol=0, abs_tol=1e-10))


def parse_braket_contract(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines[:2] != ["OPENQASM 3.0;", 'include "stdgates.inc";']:
        raise ValueError("invalid Braket header")
    qdecl = re.fullmatch(r"qubit\[(\d+)] q;", lines[2])
    cdecl = re.fullmatch(r"bit\[(\d+)] c;", lines[3])
    if not qdecl or not cdecl:
        raise ValueError("invalid Braket declarations")
    operations = []
    aliases = {"cnot": "cx", "cp": "cu1"}
    for line in lines[4:]:
        measurement = re.fullmatch(r"c\[(\d+)] = measure q\[(\d+)];", line)
        if measurement:
            operations.append(("measure", (int(measurement.group(2)),),
                               (int(measurement.group(1)),), ()))
            continue
        gate = re.fullmatch(r"([a-z]+)(?:\(([^)]+)\))? (.+);", line)
        if not gate:
            raise ValueError("invalid Braket operation: " + line)
        name = aliases.get(gate.group(1), gate.group(1))
        qubits = tuple(int(item) for item in re.findall(r"q\[(\d+)]", gate.group(3)))
        params = (float(gate.group(2)),) if gate.group(2) is not None else ()
        operations.append((name, qubits, (), params))
    return int(qdecl.group(1)), int(cdecl.group(1)), operations


def parse_origin_contract(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    qdecl = re.fullmatch(r"QINIT (\d+)", lines[0])
    cdecl = re.fullmatch(r"CREG (\d+)", lines[1])
    if not qdecl or not cdecl:
        raise ValueError("invalid OriginIR declarations")
    allowed = {
        "H": "h", "X": "x", "S": "s", "SDAG": "sdg", "T": "t",
        "TDAG": "tdg", "RY": "ry", "RZ": "rz", "CNOT": "cx",
        "CU1": "cu1", "CR": "cu1", "SWAP": "swap", "TOFFOLI": "ccx",
        "CCX": "ccx",
    }
    operations = []
    for line in lines[2:]:
        measurement = re.fullmatch(r"MEASURE q\[(\d+)], c\[(\d+)]", line)
        if measurement:
            operations.append(("measure", (int(measurement.group(1)),),
                               (int(measurement.group(2)),), ()))
            continue
        gate = re.fullmatch(r"([A-Z][A-Z0-9]*)(?:\(([^)]+)\))? (.+)", line)
        if not gate or gate.group(1) not in allowed:
            raise ValueError("invalid OriginIR operation: " + line)
        qubits = tuple(int(item) for item in re.findall(r"q\[(\d+)]", gate.group(3)))
        params = (float(gate.group(2)),) if gate.group(2) is not None else ()
        operations.append((allowed[gate.group(1)], qubits, (), params))
    return int(qdecl.group(1)), int(cdecl.group(1)), operations


def random_qasm(seed):
    rng = random.Random(seed)
    qubit_count = rng.randint(3, 6)
    lines = [
        "OPENQASM 2.0;", 'include "qelib1.inc";',
        f"qreg qa[{qubit_count - 1}];", "qreg qb[1];",
        f"creg ca[{qubit_count - 1}];", "creg cb[1];",
    ]

    def ref(index):
        return f"qa[{index}]" if index < qubit_count - 1 else "qb[0]"

    for _ in range(30):
        name = rng.choice(GATES)
        arity = 3 if name == "ccx" else (2 if name in {"cx", "cu1", "swap"} else 1)
        operands = rng.sample(range(qubit_count), arity)
        parameter = f"({rng.uniform(-2 * math.pi, 2 * math.pi):.12g})" if name in {"rz", "ry", "cu1"} else ""
        lines.append(f"{name}{parameter} " + ", ".join(ref(index) for index in operands) + ";")
    for index in range(qubit_count - 1):
        lines.append(f"measure qa[{index}] -> ca[{index}];")
    lines.append("measure qb[0] -> cb[0];")
    return "\n".join(lines) + "\n"


class TargetIRSemanticsTests(unittest.TestCase):
    def test_random_circuits_round_trip_through_all_target_contracts(self):
        for seed in range(40):
            source = random_qasm(seed)
            original = parse_qasm(source)
            spinq = parse_qasm(transpile(source, "spinq"))
            self.assertEqual((original.qubits, original.cbits), (spinq.qubits, spinq.cbits))
            assert_operations_equal(self, signature(original), signature(spinq))

            bq, bc, braket_operations = parse_braket_contract(transpile(source, "braket"))
            self.assertEqual((original.qubits, original.cbits), (bq, bc))
            assert_operations_equal(self, signature(original), braket_operations)

            oq, oc, origin_operations = parse_origin_contract(transpile(source, "originq"))
            self.assertEqual((original.qubits, original.cbits), (oq, oc))
            assert_operations_equal(self, signature(original), origin_operations)

    def test_little_endian_order_with_asymmetric_state(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
x q[0];
measure q -> c;
"""
        for target in ("spinq", "originq", "braket"):
            self.assertEqual(run(source, target, 256)["counts"], {"01": 256})

    def test_partial_measurement_keeps_unwritten_classical_bits_zero(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg qa[1];
qreg qb[1];
creg ca[1];
creg cb[1];
x qb[0];
measure qb[0] -> ca[0];
"""
        for target in ("spinq", "originq", "braket"):
            self.assertEqual(run(source, target, 64)["counts"], {"01": 64})

    def test_repeated_measurement_of_one_qubit_stays_correlated(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[2];
h q[0];
measure q[0] -> c[0];
measure q[0] -> c[1];
"""
        for target in ("spinq", "originq", "braket"):
            counts = run(source, target, 1024)["counts"]
            self.assertTrue(set(counts).issubset({"00", "11"}), (target, counts))
            self.assertEqual(sum(counts.values()), 1024)

    def test_parameter_expression_boundaries_are_normalized(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
ry(-pi + pi/7) q[0];
rz(2*pi-0.000000001) q[1];
cu1(-3*pi/2) q[0], q[1];
measure q -> c;
"""
        original = signature(parse_qasm(source))
        assert_operations_equal(self, original, signature(parse_qasm(transpile(source, "spinq"))))
        assert_operations_equal(self, original, parse_braket_contract(transpile(source, "braket"))[2])
        assert_operations_equal(self, original, parse_origin_contract(transpile(source, "originq"))[2])


if __name__ == "__main__":
    unittest.main()
