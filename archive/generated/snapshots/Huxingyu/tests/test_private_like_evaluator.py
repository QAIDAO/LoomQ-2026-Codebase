"""Deterministic private-test-shaped stress suite for LoomQ L1-L3."""

import cmath
import itertools
import math
import random
import unittest

from starter_kit.adapter import compile_hybrid, run
from starter_kit.agent_engine import compatible_backends
from starter_kit.evaluator import calculate_hellinger_fidelity
from starter_kit.riscv_emulator import TinyRISCVEmulator


TARGETS = ("spinq", "originq", "braket")
SINGLE_GATES = ("h", "x", "s", "sdg", "t", "tdg", "rz", "ry")
ALL_GATES = SINGLE_GATES + ("cx", "cu1", "swap", "ccx")


def single_matrix(name, angle=0.0):
    if name == "h":
        scale = 1 / math.sqrt(2)
        return ((scale, scale), (scale, -scale))
    if name == "x":
        return ((0, 1), (1, 0))
    phases = {
        "s": math.pi / 2,
        "sdg": -math.pi / 2,
        "t": math.pi / 4,
        "tdg": -math.pi / 4,
    }
    if name in phases:
        return ((1, 0), (0, cmath.exp(1j * phases[name])))
    if name == "rz":
        return ((cmath.exp(-0.5j * angle), 0), (0, cmath.exp(0.5j * angle)))
    if name == "ry":
        cosine, sine = math.cos(angle / 2), math.sin(angle / 2)
        return ((cosine, -sine), (sine, cosine))
    raise AssertionError(name)


def independent_distribution(qubits, operations):
    state = [0j] * (1 << qubits)
    state[0] = 1 + 0j
    for name, operands, angle in operations:
        if name in SINGLE_GATES:
            target = operands[0]
            mask = 1 << target
            matrix = single_matrix(name, angle)
            for index in range(len(state)):
                if index & mask:
                    continue
                other = index | mask
                zero, one = state[index], state[other]
                state[index] = matrix[0][0] * zero + matrix[0][1] * one
                state[other] = matrix[1][0] * zero + matrix[1][1] * one
        elif name == "cx":
            control, target = operands
            for index in range(len(state)):
                if index & (1 << control) and not index & (1 << target):
                    other = index | (1 << target)
                    state[index], state[other] = state[other], state[index]
        elif name == "cu1":
            control, target = operands
            both = (1 << control) | (1 << target)
            for index in range(len(state)):
                if index & both == both:
                    state[index] *= cmath.exp(1j * angle)
        elif name == "swap":
            first, second = operands
            masks = (1 << first, 1 << second)
            for index in range(len(state)):
                if bool(index & masks[0]) != bool(index & masks[1]):
                    other = index ^ masks[0] ^ masks[1]
                    if index < other:
                        state[index], state[other] = state[other], state[index]
        elif name == "ccx":
            first, second, target = operands
            controls = (1 << first) | (1 << second)
            for index in range(len(state)):
                if index & controls == controls and not index & (1 << target):
                    other = index | (1 << target)
                    state[index], state[other] = state[other], state[index]
        else:
            raise AssertionError(name)
    return {
        format(index, f"0{qubits}b"): abs(amplitude) ** 2
        for index, amplitude in enumerate(state)
        if abs(amplitude) ** 2 > 1e-15
    }


def random_circuit(seed):
    rng = random.Random(seed)
    qubits = rng.randint(3, 5)
    operations = []
    lines = [
        "OPENQASM 2.0;", 'include "qelib1.inc";',
        f"qreg q[{qubits}];", f"creg c[{qubits}];",
    ]
    for _ in range(rng.randint(12, 32)):
        name = rng.choice(ALL_GATES)
        arity = 3 if name == "ccx" else (2 if name in {"cx", "cu1", "swap"} else 1)
        operands = tuple(rng.sample(range(qubits), arity))
        angle = rng.uniform(-4 * math.pi, 4 * math.pi) if name in {"rz", "ry", "cu1"} else 0.0
        parameter = f"({angle:.15g})" if name in {"rz", "ry", "cu1"} else ""
        lines.append(f"{name}{parameter} " + ", ".join(f"q[{item}]" for item in operands) + ";")
        operations.append((name, operands, angle))
    lines.append("measure q -> c;")
    return "\n".join(lines) + "\n", qubits, operations


def render_expression(expression):
    kind = expression[0]
    if kind == "int":
        return str(expression[1])
    if kind == "reg":
        return f"r{expression[1]}"
    if kind == "cbit":
        return f"c[{expression[1]}]"
    return f"({render_expression(expression[2])} {expression[1]} {render_expression(expression[3])})"


def evaluate_expression(expression, registers, measured):
    kind = expression[0]
    if kind == "int":
        return expression[1]
    if kind == "reg":
        return registers[expression[1]]
    if kind == "cbit":
        return measured[expression[1]]
    left = evaluate_expression(expression[2], registers, measured)
    right = evaluate_expression(expression[3], registers, measured)
    return left + right if expression[1] == "+" else left - right


def random_expression(rng, depth):
    if depth <= 0 or rng.random() < 0.55:
        kind = rng.choice(("int", "reg", "cbit"))
        value = rng.randint(-30, 30) if kind == "int" else rng.randint(1, 5) if kind == "reg" else rng.randint(0, 3)
        return kind, value
    return "binary", rng.choice(("+", "-")), random_expression(rng, depth - 1), random_expression(rng, depth - 1)


def random_statements(rng, depth):
    result = []
    for _ in range(rng.randint(1, 4)):
        if depth > 0 and rng.random() < 0.4:
            result.append((
                "if", rng.choice(("==", "!=")), random_expression(rng, 2), random_expression(rng, 2),
                random_statements(rng, depth - 1), random_statements(rng, depth - 1),
            ))
        else:
            result.append(("set", rng.randint(1, 5), random_expression(rng, 3)))
    return result


def render_statements(statements, indent="  "):
    lines = []
    for statement in statements:
        if statement[0] == "set":
            lines.append(f"{indent}r{statement[1]} = {render_expression(statement[2])};")
            continue
        _, operator, left, right, then_body, else_body = statement
        lines.append(f"{indent}if ({render_expression(left)} {operator} {render_expression(right)}) {{")
        lines.extend(render_statements(then_body, indent + "  "))
        lines.append(indent + "} else {")
        lines.extend(render_statements(else_body, indent + "  "))
        lines.append(indent + "}")
    return lines


def interpret_statements(statements, registers, measured):
    for statement in statements:
        if statement[0] == "set":
            registers[statement[1]] = evaluate_expression(statement[2], registers, measured)
            continue
        _, operator, left, right, then_body, else_body = statement
        lhs = evaluate_expression(left, registers, measured)
        rhs = evaluate_expression(right, registers, measured)
        condition = lhs == rhs if operator == "==" else lhs != rhs
        interpret_statements(then_body if condition else else_body, registers, measured)


class PrivateLikeL1Tests(unittest.TestCase):
    def test_one_hundred_random_circuits_meet_private_fidelity_threshold(self):
        for seed in range(100):
            qasm, qubits, operations = random_circuit(seed)
            expected = independent_distribution(qubits, operations)
            for target in TARGETS:
                result = run(qasm, target, 8192)
                observed = {state: count / 8192 for state, count in result["counts"].items()}
                self.assertGreaterEqual(
                    calculate_hellinger_fidelity(observed, expected), 0.97, (seed, target)
                )


class PrivateLikeL2Tests(unittest.TestCase):
    def test_twelve_backend_constraint_paraphrases(self):
        cases = (
            ("15 比特线路要求等待时间为零", {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"}),
            ("5 比特真实量子硬件，而且不想花钱", {"spinq_cloud_qpu", "originq_wukong"}),
            ("25 qubits, local, free, no account, no wait", {"originq_local_simulator", "braket_local_simulator"}),
            ("30 个量子比特，只使用本地模拟器", {"originq_local_simulator"}),
            ("AWS cloud backend for 30 qubits", {"braket_cloud"}),
            ("8 比特真机但不愿注册账号", set()),
            ("50 qubits，选择一个后端", {"originq_wukong"}),
            ("73 qubits，选择一个后端", set()),
            ("5 比特真机且不能付费", {"spinq_cloud_qpu", "originq_wukong"}),
            ("24 qubit simulator without waiting", {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"}),
            ("OriginQ 平台、30 比特、零排队", {"originq_local_simulator"}),
            ("SpinQ local simulator for 24 qubits", {"spinq_taurus_simulator"}),
        )
        for prompt, expected in cases:
            self.assertEqual(set(compatible_backends(prompt)), expected, prompt)


class PrivateLikeL3Tests(unittest.TestCase):
    def test_recursive_random_programs_match_reference_interpreter(self):
        for seed in range(120):
            rng = random.Random(seed)
            statements = random_statements(rng, depth=2)
            classical = "\n".join(render_statements(statements))
            source = f'''OPENQASM 2.0;
include "qelib1.inc";
qreg q[4];
creg c[4];
measure q -> c;
classical {{
{classical}
}}
'''
            _, assembly = compile_hybrid(source)
            for measured in itertools.product((0, 1), repeat=4):
                expected = {index: 0 for index in range(1, 6)}
                interpret_statements(statements, expected, measured)
                emulator = TinyRISCVEmulator()
                emulator.load_program(assembly)
                for index, value in enumerate(measured):
                    emulator.set_register(f"x{10 + index}", value)
                observed = emulator.execute()
                for register in range(1, 6):
                    self.assertEqual(observed.get(f"x{register}", 0), expected[register], (seed, measured, register))


if __name__ == "__main__":
    unittest.main()
