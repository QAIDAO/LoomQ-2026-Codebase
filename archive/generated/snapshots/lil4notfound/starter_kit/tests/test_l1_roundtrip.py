import random
import unittest

try:
    from starter_kit import adapter
    from starter_kit.loomq_core.qasm2 import parse_qasm2
    from starter_kit.loomq_core.simulator import simulate_counts
    from starter_kit.loomq_core.target_ir import (
        parse_braket_ir,
        parse_origin_ir,
        parse_target_ir,
    )
    from starter_kit.loomq_core.verification import (
        circuit_difference,
        verify_target_roundtrip,
    )
except ModuleNotFoundError:
    import adapter
    from loomq_core.qasm2 import parse_qasm2
    from loomq_core.simulator import simulate_counts
    from loomq_core.target_ir import parse_braket_ir, parse_origin_ir, parse_target_ir
    from loomq_core.verification import circuit_difference, verify_target_roundtrip


GATES = {
    "h": (1, None),
    "x": (1, None),
    "s": (1, None),
    "sdg": (1, None),
    "t": (1, None),
    "tdg": (1, None),
    "rz": (1, True),
    "ry": (1, True),
    "cx": (2, None),
    "cu1": (2, True),
    "swap": (2, None),
    "ccx": (3, None),
}

ANGLE_EXPRESSIONS = (
    "pi/3",
    "-pi/5",
    "2*pi/7",
    "0.125",
    "-(pi/8)",
    "3.141592653589793",
)


class TargetIRRoundTripTests(unittest.TestCase):
    def test_braket_register_measurement_form_is_read(self):
        source = """OPENQASM 3.0;
        include "stdgates.inc";
        qubit[2] q;
        bit[2] c;
        h q[0];
        cnot q[0], q[1];
        c = measure q;
        """
        circuit = parse_braket_ir(source)
        self.assertEqual(circuit.qubit_count, 2)
        self.assertEqual(len(circuit.measurements), 2)
        self.assertEqual([item.name for item in circuit.operations], ["h", "cx"])

    def test_origin_aliases_and_trailing_angle_form_are_read(self):
        source = """QINIT 3
        CREG 3
        RY q[0],(pi/3)
        CR q[0], q[1],(pi/7)
        CCX q[0], q[1], q[2]
        MEASURE q[0], c[0]
        MEASURE q[1], c[1]
        MEASURE q[2], c[2]
        """
        circuit = parse_origin_ir(source)
        self.assertEqual(
            [item.name for item in circuit.operations], ["ry", "cu1", "ccx"]
        )

    def test_target_readers_reject_invalid_or_incomplete_ir(self):
        with self.assertRaisesRegex(ValueError, "measurement"):
            parse_braket_ir(
                'OPENQASM 3.0; include "stdgates.inc"; qubit[1] q; bit[1] c; h q[0];'
            )
        with self.assertRaisesRegex(ValueError, "Index outside"):
            parse_origin_ir("QINIT 1\nCREG 1\nX q[2]\nMEASURE q[0], c[0]")
        with self.assertRaisesRegex(ValueError, "Unsupported target"):
            parse_target_ir("irrelevant", "unknown")

    def test_roundtrip_verifier_detects_semantic_mutation_for_every_target(self):
        source = """OPENQASM 2.0;
        include "qelib1.inc";
        qreg q[2]; creg c[2];
        h q[0]; cx q[0], q[1]; measure q -> c;
        """
        expected = parse_qasm2(source)
        replacements = {
            "spinq": ("cx q[0], q[1]", "cx q[1], q[0]"),
            "originq": ("CNOT q[0], q[1]", "CNOT q[1], q[0]"),
            "braket": ("cnot q[0], q[1]", "cnot q[1], q[0]"),
        }
        for target, (before, after) in replacements.items():
            with self.subTest(target=target):
                rendered = adapter.transpile(source, target)
                mutated = rendered.replace(before, after)
                with self.assertRaisesRegex(ValueError, "qubits differ"):
                    verify_target_roundtrip(expected, target, mutated)

    def test_seeded_random_circuits_roundtrip_and_simulate_equally(self):
        master = random.Random(20260825)
        seen_gates = set()
        for case_index in range(72):
            case_seed = master.randrange(1 << 63)
            source, generated_gates = _random_qasm(random.Random(case_seed))
            seen_gates.update(generated_gates)
            expected = parse_qasm2(source)
            expected_counts = simulate_counts(expected, 4096)
            for target in adapter.SUPPORTED_TARGETS:
                with self.subTest(
                    case=case_index, case_seed=case_seed, target=target
                ):
                    rendered = adapter.transpile(source, target)
                    actual = verify_target_roundtrip(expected, target, rendered)
                    self.assertIsNone(circuit_difference(expected, actual))
                    self.assertEqual(
                        simulate_counts(actual, 4096), expected_counts
                    )
        self.assertEqual(seen_gates, set(GATES))


def _random_qasm(rng):
    qubit_count = rng.randint(1, 5)
    quantum_sizes = _partition(qubit_count, rng)
    classical_sizes = _partition(qubit_count, rng)
    quantum_names = [f"q{index}" for index in range(len(quantum_sizes))]
    classical_names = [f"c{index}" for index in range(len(classical_sizes))]
    quantum_bits = _bit_refs(quantum_names, quantum_sizes)
    classical_bits = _bit_refs(classical_names, classical_sizes)

    lines = ['OPENQASM 2.0;', 'include "qelib1.inc";']
    lines.extend(
        f"qreg {name}[{size}];"
        for name, size in zip(quantum_names, quantum_sizes)
    )
    lines.extend(
        f"creg {name}[{size}];"
        for name, size in zip(classical_names, classical_sizes)
    )
    lines.append("// Seeded differential circuit.")

    available = [name for name, (arity, _) in GATES.items() if arity <= qubit_count]
    generated = []
    for _ in range(rng.randint(6, 20)):
        name = rng.choice(available)
        arity, parameterized = GATES[name]
        operands = rng.sample(quantum_bits, arity)
        parameter = f"({rng.choice(ANGLE_EXPRESSIONS)})" if parameterized else ""
        separator = "," if rng.random() < 0.5 else ", "
        lines.append(f"{name}{parameter} {separator.join(operands)};")
        generated.append(name)

    rng.shuffle(classical_bits)
    lines.extend(
        f"measure {qubit} -> {classical};"
        for qubit, classical in zip(quantum_bits, classical_bits)
    )
    return "\n".join(lines) + "\n", generated


def _partition(total, rng):
    part_count = rng.randint(1, min(3, total))
    cuts = sorted(rng.sample(range(1, total), part_count - 1))
    boundaries = [0, *cuts, total]
    return [right - left for left, right in zip(boundaries, boundaries[1:])]


def _bit_refs(names, sizes):
    return [
        f"{name}[{index}]"
        for name, size in zip(names, sizes)
        for index in range(size)
    ]


if __name__ == "__main__":
    unittest.main()
