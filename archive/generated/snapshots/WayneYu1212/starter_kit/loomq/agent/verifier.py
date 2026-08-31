"""Program-owned verification between model output and user-visible QASM."""

from __future__ import annotations

from dataclasses import dataclass

from ..compiler.ir import Circuit
from ..compiler.parser import parse_qasm
from ..simulator import probabilities


@dataclass(frozen=True, slots=True)
class VerificationReport:
    qasm: str
    circuit: Circuit
    distribution: dict[str, float]
    checks: tuple[str, ...]
    summary: str


def verify_qasm(qasm: str) -> VerificationReport:
    """Parse, validate, and independently simulate a model-produced program."""

    circuit = parse_qasm(qasm)
    distribution = probabilities(circuit)
    dominant = sorted(distribution.items(), key=lambda item: (-item[1], item[0]))[:4]
    summary = "、".join(f"{state}≈{probability:.1%}" for state, probability in dominant)
    return VerificationReport(
        qasm=qasm.strip() + "\n",
        circuit=circuit,
        distribution=distribution,
        checks=("OpenQASM 2.0 语法", "官方 12 门边界", "本地无噪声模拟"),
        summary=summary,
    )
