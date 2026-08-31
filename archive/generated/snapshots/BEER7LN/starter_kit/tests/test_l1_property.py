"""Deterministic property and differential tests for LoomQ L1."""

from __future__ import annotations

import cmath
import math
import random
import re
import sys
import unittest
from unittest import mock
from pathlib import Path


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

import adapter  # noqa: E402
from loomq.qasm import GateOperation, MeasureOperation, Program, parse_openqasm2  # noqa: E402


GATES = ("h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx")
PARAMETERS = ("pi/7", "-pi/3", "0.25", "3*pi/8", "-0.6")
ORIGIN_GATE_MAP = {
    "H": "h", "X": "x", "S": "s", "SDAG": "sdg", "T": "t", "TDAG": "tdg",
    "RZ": "rz", "RY": "ry", "CNOT": "cx", "CU1": "cu1", "CR": "cu1",
    "SWAP": "swap", "TOFFOLI": "ccx", "CCX": "ccx",
}
BRAKET_GATE_MAP = {
    "si": "sdg",
    "ti": "tdg",
    "cnot": "cx",
    "cx": "cx",
    "cp": "cu1",
    "cphaseshift": "cu1",
    "ccnot": "ccx",
}


class L1PropertyTests(unittest.TestCase):
    def test_all_whitelisted_gates_survive_each_target_ir(self) -> None:
        qasm = _all_gates_qasm()
        expected = _normalize_program(parse_openqasm2(qasm))
        self.assertEqual(_normalize_program(parse_openqasm2(adapter.transpile(qasm, "spinq"))), expected)
        self.assertEqual(_parse_originir(adapter.transpile(qasm, "originq")), expected)
        self.assertEqual(_parse_qasm3(adapter.transpile(qasm, "braket")), expected)

    def test_random_circuits_match_independent_reference_distribution(self) -> None:
        seen: set[str] = set()
        with mock.patch.dict("os.environ", {"LOOMQ_FORCE_REFERENCE_SIMULATOR": "1"}):
            for seed in range(32):
                qasm, gates = _random_qasm(seed)
                seen.update(gates)
                program = parse_openqasm2(qasm)
                expected = _reference_distribution(program)
                expected_operations = _normalize_program(program)
                self.assertEqual(
                    _normalize_program(parse_openqasm2(adapter.transpile(qasm, "spinq"))),
                    expected_operations,
                )
                self.assertEqual(_parse_originir(adapter.transpile(qasm, "originq")), expected_operations)
                self.assertEqual(_parse_qasm3(adapter.transpile(qasm, "braket")), expected_operations)
                for target in adapter.SUPPORTED_TARGETS:
                    with self.subTest(seed=seed, target=target):
                        payload = adapter.run(qasm, target, 8192)
                        observed = {state: count / 8192 for state, count in payload["counts"].items()}
                        self.assertGreaterEqual(_fidelity(observed, expected), 0.97)
        self.assertEqual(seen, set(GATES))

    def test_bit_order_and_partial_measurement_mapping(self) -> None:
        qasm = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg data[3];
creg out[3];
x data[0];
x data[2];
measure data[0] -> out[2];
measure data[1] -> out[1];
measure data[2] -> out[0];
"""
        with mock.patch.dict("os.environ", {"LOOMQ_FORCE_REFERENCE_SIMULATOR": "1"}):
            for target in adapter.SUPPORTED_TARGETS:
                payload = adapter.run(qasm, target, 128)
                self.assertEqual(payload["counts"], {"101": 128})
        origin = adapter.transpile(qasm, "originq")
        self.assertIn("X q[0]", origin)
        self.assertIn("MEASURE q[0], c[2]", origin)


def _all_gates_qasm() -> str:
    return """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[3];
creg c[3];
h q[0];
x q[1];
s q[2];
sdg q[2];
t q[1];
tdg q[1];
rz(pi/7) q[0];
ry(-pi/3) q[1];
cx q[0], q[1];
cu1(3*pi/8) q[0], q[2];
swap q[1], q[2];
ccx q[0], q[1], q[2];
measure q -> c;
"""


def _random_qasm(seed: int) -> tuple[str, set[str]]:
    rng = random.Random(20260801 + seed)
    qubits = rng.randint(3, 5)
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{qubits}];", f"creg c[{qubits}];"]
    selected: set[str] = set()
    for _ in range(rng.randint(10, 22)):
        gate = rng.choice(GATES)
        selected.add(gate)
        if gate in {"h", "x", "s", "sdg", "t", "tdg"}:
            lines.append(f"{gate} q[{rng.randrange(qubits)}];")
        elif gate in {"rz", "ry"}:
            lines.append(f"{gate}({rng.choice(PARAMETERS)}) q[{rng.randrange(qubits)}];")
        elif gate in {"cx", "swap"}:
            first, second = rng.sample(range(qubits), 2)
            lines.append(f"{gate} q[{first}], q[{second}];")
        elif gate == "cu1":
            first, second = rng.sample(range(qubits), 2)
            lines.append(f"cu1({rng.choice(PARAMETERS)}) q[{first}], q[{second}];")
        else:
            first, second, third = rng.sample(range(qubits), 3)
            lines.append(f"ccx q[{first}], q[{second}], q[{third}];")
    if seed % 2:
        for index in range(qubits):
            lines.append(f"measure q[{index}] -> c[{qubits - index - 1}];")
    else:
        lines.append("measure q -> c;")
    return "\n".join(lines) + "\n", selected


def _normalize_program(program: Program) -> list[tuple[object, ...]]:
    normalized: list[tuple[object, ...]] = []
    for operation in program.operations:
        if isinstance(operation, GateOperation):
            normalized.append((operation.name, _angle(operation.parameter), tuple(_index(item) for item in operation.operands)))
        elif operation.source == program.quantum_register.name:
            normalized.extend(("measure", None, (index, index)) for index in range(program.quantum_register.size))
        else:
            normalized.append(("measure", None, (_index(operation.source), _index(operation.destination))))
    return normalized


def _parse_originir(source: str) -> list[tuple[object, ...]]:
    operations: list[tuple[object, ...]] = []
    dagger = False
    for line in (item.strip() for item in source.splitlines()):
        if not line or line.startswith(("QINIT ", "CREG ")):
            continue
        if line == "DAGGER":
            dagger = True
            continue
        if line == "ENDDAGGER":
            dagger = False
            continue
        if line.startswith("MEASURE "):
            source_operand, destination = [item.strip() for item in line[8:].split(",")]
            operations.append(("measure", None, (_index(source_operand), _index(destination))))
            continue
        parameterized = re.fullmatch(r"([A-Z0-9]+)\s+(.+),\((.*)\)", line)
        if parameterized is not None and parameterized.group(1) in ORIGIN_GATE_MAP:
            operands = tuple(
                _index(item.strip()) for item in parameterized.group(2).split(",")
            )
            operations.append(
                (
                    _origin_gate_name(parameterized.group(1), dagger),
                    _angle(parameterized.group(3)),
                    operands,
                )
            )
            continue
        match = re.fullmatch(r"([A-Z0-9]+)(?:\((.+)\))?\s+(.+)", line)
        if match is None or match.group(1) not in ORIGIN_GATE_MAP:
            raise AssertionError(f"Unparseable OriginIR: {line}")
        operands = tuple(_index(item.strip()) for item in match.group(3).split(","))
        operations.append((_origin_gate_name(match.group(1), dagger), _angle(match.group(2)), operands))
    return operations


def _origin_gate_name(native_name: str, dagger: bool) -> str:
    name = ORIGIN_GATE_MAP[native_name]
    return {"s": "sdg", "t": "tdg"}.get(name, name) if dagger else name


def _parse_qasm3(source: str) -> list[tuple[object, ...]]:
    operations: list[tuple[object, ...]] = []
    statements = [item.strip() for item in source.split(";") if item.strip()]
    size_match = re.search(r"qubit\[(\d+)\]", source)
    if size_match is None:
        raise AssertionError("QASM 3 output has no qubit declaration")
    size = int(size_match.group(1))
    for statement in statements:
        if statement.startswith(("OPENQASM ", "include ", "qubit[", "bit[")):
            continue
        whole_measurement = re.fullmatch(r"\w+\s*=\s*measure\s+\w+", statement)
        if whole_measurement:
            operations.extend(("measure", None, (index, index)) for index in range(size))
            continue
        partial_measurement = re.fullmatch(r"\w+\[(\d+)\]\s*=\s*measure\s+\w+\[(\d+)\]", statement)
        if partial_measurement:
            operations.append(("measure", None, (int(partial_measurement.group(2)), int(partial_measurement.group(1)))))
            continue
        match = re.fullmatch(r"([a-z]+)(?:\((.+)\))?\s+(.+)", statement)
        if match is None:
            raise AssertionError(f"Unparseable OpenQASM 3: {statement}")
        name = BRAKET_GATE_MAP.get(match.group(1), match.group(1))
        operands = tuple(_index(item.strip()) for item in match.group(3).split(","))
        operations.append((name, _angle(match.group(2)), operands))
    return operations


def _reference_distribution(program: Program) -> dict[str, float]:
    state = [0j] * (1 << program.quantum_register.size)
    state[0] = 1 + 0j
    for operation in program.operations:
        if not isinstance(operation, GateOperation):
            continue
        operands = tuple(_index(item) for item in operation.operands)
        angle = _angle(operation.parameter)
        if operation.name == "h":
            scale = 1 / math.sqrt(2)
            state = _reference_single(state, operands[0], ((scale, scale), (scale, -scale)))
        elif operation.name == "x":
            state = _reference_single(state, operands[0], ((0, 1), (1, 0)))
        elif operation.name == "s":
            state = _reference_single(state, operands[0], ((1, 0), (0, 1j)))
        elif operation.name == "sdg":
            state = _reference_single(state, operands[0], ((1, 0), (0, -1j)))
        elif operation.name == "t":
            state = _reference_single(state, operands[0], ((1, 0), (0, cmath.exp(1j * math.pi / 4))))
        elif operation.name == "tdg":
            state = _reference_single(state, operands[0], ((1, 0), (0, cmath.exp(-1j * math.pi / 4))))
        elif operation.name == "rz":
            assert angle is not None
            state = _reference_single(state, operands[0], ((cmath.exp(-0.5j * angle), 0), (0, cmath.exp(0.5j * angle))))
        elif operation.name == "ry":
            assert angle is not None
            cosine, sine = math.cos(angle / 2), math.sin(angle / 2)
            state = _reference_single(state, operands[0], ((cosine, -sine), (sine, cosine)))
        else:
            state = _reference_multi(state, operation.name, operands, angle)
    distribution: dict[str, float] = {}
    for basis, amplitude in enumerate(state):
        bitstring = _measured_bitstring(basis, program)
        distribution[bitstring] = distribution.get(bitstring, 0.0) + abs(amplitude) ** 2
    return {key: value for key, value in distribution.items() if value > 1e-12}


def _reference_single(state: list[complex], qubit: int, matrix: tuple[tuple[complex, complex], tuple[complex, complex]]) -> list[complex]:
    output = [0j] * len(state)
    mask = 1 << qubit
    for basis, amplitude in enumerate(state):
        input_bit = 1 if basis & mask else 0
        for output_bit in (0, 1):
            target = (basis & ~mask) | (output_bit << qubit)
            output[target] += matrix[output_bit][input_bit] * amplitude
    return output


def _reference_multi(state: list[complex], name: str, operands: tuple[int, ...], angle: float | None) -> list[complex]:
    output = [0j] * len(state)
    for basis, amplitude in enumerate(state):
        target, phase = basis, 1 + 0j
        if name == "cx" and basis & (1 << operands[0]):
            target ^= 1 << operands[1]
        elif name == "cu1" and basis & (1 << operands[0]) and basis & (1 << operands[1]):
            assert angle is not None
            phase = cmath.exp(1j * angle)
        elif name == "swap" and bool(basis & (1 << operands[0])) != bool(basis & (1 << operands[1])):
            target ^= (1 << operands[0]) | (1 << operands[1])
        elif name == "ccx" and basis & (1 << operands[0]) and basis & (1 << operands[1]):
            target ^= 1 << operands[2]
        output[target] += phase * amplitude
    return output


def _measured_bitstring(basis: int, program: Program) -> str:
    classical = [0] * program.classical_register.size
    for operation in program.operations:
        if not isinstance(operation, MeasureOperation):
            continue
        if operation.source == program.quantum_register.name:
            for index in range(program.quantum_register.size):
                classical[index] = (basis >> index) & 1
        else:
            classical[_index(operation.destination)] = (basis >> _index(operation.source)) & 1
    return "".join(str(classical[index]) for index in reversed(range(len(classical))))


def _angle(expression: str | None) -> float | None:
    if expression is None:
        return None
    value = expression.lower().replace("pi", f"({math.pi!r})")
    if re.search(r"[^0-9eE.+*/() -]", value):
        raise AssertionError(f"Unsafe angle expression: {expression}")
    return round(float(eval(value, {"__builtins__": {}}, {})), 12)


def _index(operand: str) -> int:
    match = re.search(r"\[(\d+)\]", operand)
    if match is None:
        raise AssertionError(f"Missing indexed operand: {operand}")
    return int(match.group(1))


def _fidelity(observed: dict[str, float], expected: dict[str, float]) -> float:
    states = set(observed) | set(expected)
    distance = math.sqrt(sum((math.sqrt(observed.get(state, 0.0)) - math.sqrt(expected.get(state, 0.0))) ** 2 for state in states)) / math.sqrt(2)
    return 1 - distance


if __name__ == "__main__":
    unittest.main()
