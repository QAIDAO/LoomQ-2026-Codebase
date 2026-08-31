"""Deterministic generated corpus for Hybrid-QASM differential verification."""

from __future__ import annotations

from dataclasses import dataclass
import random

from .gate_policy import PUBLIC_GATE_WHITELIST


@dataclass(frozen=True)
class HybridStressCase:
    case_id: str
    source: str
    width: int


def build_stress_corpus(
    *, seed: int = 0x4C_33_2026, cases: int = 48
) -> tuple[HybridStressCase, ...]:
    """Generate reproducible grammar, branch, arithmetic, and gate variations."""

    if cases <= 0:
        raise ValueError("cases must be positive")
    rng = random.Random(seed)
    output: list[HybridStressCase] = []
    for case_index in range(cases):
        width = 1 + case_index % 6
        quantum = _quantum_operations(rng, width, case_index)
        split = rng.randrange(len(quantum) + 1)
        classical = _classical_program(rng, width, case_index)
        lines = [
            "OPENQASM 2.0;",
            'include "qelib1.inc";',
            f"qreg q[{width}];",
            f"creg c[{width}];",
            *quantum[:split],
            "classical {",
            classical,
            "}",
            *quantum[split:],
            "",
        ]
        output.append(
            HybridStressCase(
                case_id=f"generated-{seed:08x}-{case_index:03d}",
                source="\n".join(lines),
                width=width,
            )
        )
    return tuple(output)


def _quantum_operations(
    rng: random.Random, width: int, case_index: int
) -> list[str]:
    one_qubit = ("h", "x", "s", "sdg", "t", "tdg")
    operations: list[str] = []
    for offset in range(3 + case_index % 4):
        gate = rng.choice(one_qubit)
        operations.append(f"{gate} q[{rng.randrange(width)}];")
        rotation = ("rz", "ry")[offset % 2]
        numerator = rng.choice((-7, -3, -1, 1, 2, 5, 9))
        denominator = rng.choice((2, 3, 5, 7))
        operations.append(
            f"{rotation}({numerator}*pi/{denominator}) q[{rng.randrange(width)}];"
        )
    if width >= 2:
        first, second = rng.sample(range(width), 2)
        operations.extend(
            [
                f"cx q[{first}], q[{second}];",
                f"cu1(pi/{2 + case_index % 5}) q[{second}], q[{first}];",
                f"swap q[{first}], q[{second}];",
            ]
        )
    if width >= 3:
        first, second, target = rng.sample(range(width), 3)
        operations.append(f"ccx q[{first}], q[{second}], q[{target}];")
    operations.append("measure q -> c;")
    names = {
        operation.split("(", 1)[0].split(" ", 1)[0]
        for operation in operations
        if not operation.startswith("measure")
    }
    if names - PUBLIC_GATE_WHITELIST:
        raise AssertionError("stress generator emitted a non-whitelisted gate")
    return operations


def _classical_program(
    rng: random.Random, width: int, case_index: int
) -> str:
    first = rng.randrange(width)
    second = rng.randrange(width)
    third = rng.randrange(width)
    base = rng.randint(-40, 40)
    outer = "==" if case_index % 2 else "!="
    inner = "!=" if case_index % 3 else "=="
    return "\n".join(
        [
            f"  // generated case {case_index}; comment braces are inert: }} {{",
            f"  r1 = {base};",
            f"  r2 = r1 + c[{first}] - {case_index % 7};",
            f"  if ((r2 - c[{second}]) {outer} ({base - case_index % 7})) {{",
            f"    r3 = r2 + c[{third}] + {case_index % 5};",
            f"    if (c[{first}] {inner} c[{second}]) {{ r4 = r3 - r1; }}",
            "    else { r4 = r3 + r1; }",
            "  } else {",
            f"    r3 = r2 - c[{third}] - {case_index % 4};",
            "    r4 = r3 - r2;",
            "  }",
            "  r5 = r4 + r3 - r2;",
            "  r6 = r5 + r1;",
        ]
    )
