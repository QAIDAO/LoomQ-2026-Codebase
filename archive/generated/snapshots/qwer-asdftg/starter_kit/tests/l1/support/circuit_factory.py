"""Deterministic hidden-style OpenQASM 2 circuit builders for L1 tests."""

import random


_RANDOM_SEED = 20260818
_ONE_QUBIT_GATES = ("h", "x", "s", "sdg", "t", "tdg")
_ROTATION_GATES = ("rz", "ry")
_MULTI_QUBIT_GATES = ("cx", "cu1", "swap", "ccx")
_ANGLES = ("pi/8", "-pi/8", "pi/6", "-pi/6", "pi/4", "-pi/4", "pi/3", "-pi/3", "pi/2", "-pi/2")


def _program(num_qubits, operations):
    return "\n".join(
        (
            "OPENQASM 2.0;",
            'include "qelib1.inc";',
            f"qreg q[{num_qubits}];",
            f"creg c[{num_qubits}];",
            *operations,
            "measure q -> c;",
            "",
        )
    )


def _ghz_5():
    return _program(5, ("h q[0];", "cx q[0],q[1];", "cx q[1],q[2];", "cx q[2],q[3];", "cx q[3],q[4];"))


def _qft_4():
    return _program(
        4,
        (
            "h q[0];",
            "cu1(pi/2) q[1],q[0];",
            "cu1(pi/4) q[2],q[0];",
            "cu1(pi/8) q[3],q[0];",
            "h q[1];",
            "cu1(pi/2) q[2],q[1];",
            "cu1(pi/4) q[3],q[1];",
            "h q[2];",
            "cu1(pi/2) q[3],q[2];",
            "h q[3];",
            "swap q[0],q[3];",
            "swap q[1],q[2];",
        ),
    )


def _grover_3():
    iteration = (
        "h q[2];", "ccx q[0],q[1],q[2];", "h q[2];",
        "h q[0];", "h q[1];", "h q[2];",
        "x q[0];", "x q[1];", "x q[2];",
        "h q[2];", "ccx q[0],q[1],q[2];", "h q[2];",
        "x q[0];", "x q[1];", "x q[2];",
        "h q[0];", "h q[1];", "h q[2];",
    )
    return _program(
        3,
        (
            "h q[0];", "h q[1];", "h q[2];",
        ) + iteration + iteration,
    )


def _random_operation(generator, num_qubits):
    gate = generator.choice(_ONE_QUBIT_GATES + _ROTATION_GATES + _MULTI_QUBIT_GATES)
    if gate in _ONE_QUBIT_GATES:
        return f"{gate} q[{generator.randrange(num_qubits)}];"
    if gate in _ROTATION_GATES:
        return f"{gate}({generator.choice(_ANGLES)}) q[{generator.randrange(num_qubits)}];"
    if gate == "ccx":
        first, second, target = generator.sample(range(num_qubits), 3)
        return f"ccx q[{first}],q[{second}],q[{target}];"
    first, second = generator.sample(range(num_qubits), 2)
    if gate == "cu1":
        return f"cu1({generator.choice(_ANGLES)}) q[{first}],q[{second}];"
    return f"{gate} q[{first}],q[{second}];"


def _random_5(generator):
    return _program(5, tuple(_random_operation(generator, 5) for _ in range(24)))


def hidden_style_circuits():
    """Return exact and seeded-random measured circuits in a stable order."""
    generator = random.Random(_RANDOM_SEED)
    return {
        "ghz-5": _ghz_5(),
        "qft-4": _qft_4(),
        "grover-3": _grover_3(),
        "random-5-1": _random_5(generator),
        "random-5-2": _random_5(generator),
        "random-5-3": _random_5(generator),
    }


__all__ = ["hidden_style_circuits"]
