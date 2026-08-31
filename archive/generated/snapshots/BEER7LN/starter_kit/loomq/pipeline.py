"""Auditable L1 compilation stages without changing the public adapter API."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Any

from .gate_policy import lower_to_public_basis
from .qasm import (
    GateOperation,
    MeasureOperation,
    Program,
    parse_openqasm2,
    serialize_openqasm2,
)


@dataclass(frozen=True)
class StageTrace:
    name: str
    artifact: str
    sha256: str
    details: dict[str, Any]


@dataclass(frozen=True)
class PipelineTrace:
    target: str
    canonical_qasm: str
    public_ir: str
    runtime_ir: str
    stages: tuple[StageTrace, ...]

    @property
    def native_ir(self) -> str:
        """Backward-compatible alias for the public transpile artifact."""

        return self.public_ir

    def to_meta(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "artifacts": {
                "canonical_sha256": _digest(self.canonical_qasm),
                "public_sha256": _digest(self.public_ir),
                "runtime_sha256": _digest(self.runtime_ir),
            },
            "stages": [asdict(stage) for stage in self.stages],
        }


def trace_transpilation(source: str, target: str) -> PipelineTrace:
    """Run parse, basis validation, canonicalization, and target emission."""

    received = StageTrace(
        name="receive",
        artifact="openqasm2-source",
        sha256=_digest(source),
        details={"characters": len(source)},
    )
    parsed = parse_openqasm2(source)
    parse_stage = StageTrace(
        name="parse",
        artifact="loomq-program",
        sha256=_digest(repr(parsed)),
        details={
            "qubits": parsed.quantum_register.size,
            "classical_bits": parsed.classical_register.size,
            "operations": len(parsed.operations),
        },
    )
    lowered, lowering = lower_to_public_basis(parsed)
    basis_stage = StageTrace(
        name="public-basis",
        artifact="loomq-program",
        sha256=_digest(repr(lowered)),
        details=asdict(lowering),
    )
    canonical = serialize_openqasm2(lowered)
    canonical_stage = StageTrace(
        name="canonicalize",
        artifact="openqasm2-canonical",
        sha256=_digest(canonical),
        details={"signature": program_signature(lowered)},
    )
    public_ir = _emit_public(canonical, target)
    public_emit_stage = StageTrace(
        name="emit-public",
        artifact={
            "spinq": "openqasm2",
            "originq": "originir",
            "braket": "openqasm3",
        }[target],
        sha256=_digest(public_ir),
        details={"characters": len(public_ir), "contract": "target-ir-v1"},
    )
    runtime_ir = _emit_runtime(canonical, target)
    runtime_emit_stage = StageTrace(
        name="emit-runtime",
        artifact={
            "spinq": "spinq-qasm2-runtime",
            "originq": "pyqpanda-originir-runtime",
            "braket": "braket-openqasm3-runtime",
        }[target],
        sha256=_digest(runtime_ir),
        details={"characters": len(runtime_ir), "consumer": "vendor-sdk"},
    )
    return PipelineTrace(
        target=target,
        canonical_qasm=canonical,
        public_ir=public_ir,
        runtime_ir=runtime_ir,
        stages=(
            received,
            parse_stage,
            basis_stage,
            canonical_stage,
            public_emit_stage,
            runtime_emit_stage,
        ),
    )


def program_signature(program: Program) -> list[dict[str, Any]]:
    """Return a stable semantic signature used by independent round-trip checks."""

    signature: list[dict[str, Any]] = []
    for operation in program.operations:
        if isinstance(operation, GateOperation):
            signature.append(
                {
                    "kind": "gate",
                    "name": operation.name,
                    "parameter": operation.parameter,
                    "operands": list(operation.operands),
                }
            )
        elif isinstance(operation, MeasureOperation):
            signature.append(
                {
                    "kind": "measure",
                    "source": operation.source,
                    "destination": operation.destination,
                }
            )
    return signature


def _emit_public(canonical_qasm: str, target: str) -> str:
    if target == "spinq":
        from .transpilers.spinq import transpile
    elif target == "originq":
        from .transpilers.originq import transpile
    elif target == "braket":
        from .transpilers.braket import transpile
    else:
        raise ValueError(f"Unsupported target: {target}")
    return transpile(canonical_qasm)


def _emit_runtime(canonical_qasm: str, target: str) -> str:
    if target == "spinq":
        from .transpilers.spinq import transpile_runtime
    elif target == "originq":
        from .transpilers.originq import transpile_runtime
    elif target == "braket":
        from .transpilers.braket import transpile_runtime
    else:
        raise ValueError(f"Unsupported target: {target}")
    return transpile_runtime(canonical_qasm)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
