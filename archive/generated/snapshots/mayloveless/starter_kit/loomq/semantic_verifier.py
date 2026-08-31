"""Independent target-state validation with Braket's local statevector simulator."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import math
from typing import Any, Mapping, Sequence

from .ir import Circuit, MeasureOperation
from .serializers.braket import serialize_braket


DEFAULT_FIDELITY_THRESHOLD = 0.97
_NORMALIZATION_TOLERANCE = 1e-6
_UNSUPPORTED_REASONS = {
    "no_unique_target",
    "mixed_state",
    "distribution_only",
    "insufficient_spec",
}


class TargetSpecificationError(RuntimeError):
    """Raised when the independent judge returns an invalid target specification."""


class SemanticVerificationError(RuntimeError):
    """Raised when deterministic local statevector verification cannot run."""


@dataclass(frozen=True)
class TargetAmplitude:
    basis: str
    real: float
    imag: float


@dataclass(frozen=True)
class TargetSpecification:
    verification_mode: str
    pure_state_requested: bool
    qubit_count: int | None
    amplitudes: tuple[TargetAmplitude, ...]
    explanation: str
    unsupported_reason: str | None = None

    def as_prompt_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "verification_mode": self.verification_mode,
            "pure_state_requested": self.pure_state_requested,
            "explanation": self.explanation,
        }
        if self.verification_mode == "statevector":
            payload["qubit_count"] = self.qubit_count
            payload["amplitudes"] = [
                {
                    "basis": amplitude.basis,
                    "real": amplitude.real,
                    "imag": amplitude.imag,
                }
                for amplitude in self.amplitudes
            ]
        elif self.unsupported_reason is not None:
            payload["unsupported_reason"] = self.unsupported_reason
        return payload


@dataclass(frozen=True)
class SemanticVerificationResult:
    fidelity: float | None
    passed: bool
    mode: str


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TargetSpecificationError("target amplitude %s must be numeric" % field)
    number = float(value)
    if not math.isfinite(number):
        raise TargetSpecificationError("target amplitude %s must be finite" % field)
    return number


def parse_target_specification(payload: Any) -> TargetSpecification:
    """Validate a target-judge JSON object independently of candidate QASM."""
    if not isinstance(payload, Mapping):
        raise TargetSpecificationError("target specification must be an object")
    if "qasm" in payload:
        raise TargetSpecificationError("target judge must not return QASM")
    mode = payload.get("verification_mode")
    pure_state_requested = payload.get("pure_state_requested")
    if not isinstance(pure_state_requested, bool):
        raise TargetSpecificationError(
            "target pure_state_requested must be a boolean"
        )
    explanation = payload.get("explanation", "")
    if not isinstance(explanation, str):
        raise TargetSpecificationError("target explanation must be a string")

    if mode == "unsupported":
        if pure_state_requested:
            # 明确纯态请求不能以 unsupported 静默绕过语义校验。
            raise TargetSpecificationError(
                "explicit pure-state target must use statevector verification"
            )
        unsupported_reason = payload.get("unsupported_reason")
        if unsupported_reason not in _UNSUPPORTED_REASONS:
            raise TargetSpecificationError(
                "unsupported target must provide a valid unsupported_reason"
            )
        return TargetSpecification(
            verification_mode="unsupported",
            pure_state_requested=False,
            qubit_count=None,
            amplitudes=(),
            explanation=explanation.strip(),
            unsupported_reason=unsupported_reason,
        )
    if mode != "statevector":
        raise TargetSpecificationError("unsupported target verification_mode")
    if not pure_state_requested:
        raise TargetSpecificationError(
            "statevector target must identify an explicit pure-state request"
        )

    qubit_count = payload.get("qubit_count")
    if (
        isinstance(qubit_count, bool)
        or not isinstance(qubit_count, int)
        or qubit_count <= 0
    ):
        raise TargetSpecificationError("target qubit_count must be a positive integer")
    raw_amplitudes = payload.get("amplitudes")
    if not isinstance(raw_amplitudes, list) or not raw_amplitudes:
        raise TargetSpecificationError("target amplitudes must be a non-empty array")

    amplitudes = []
    seen_basis = set()
    norm = 0.0
    for index, raw_amplitude in enumerate(raw_amplitudes):
        if not isinstance(raw_amplitude, Mapping):
            raise TargetSpecificationError(
                "target amplitude entry %d must be an object" % index
            )
        basis = raw_amplitude.get("basis")
        if (
            not isinstance(basis, str)
            or len(basis) != qubit_count
            or any(bit not in "01" for bit in basis)
        ):
            raise TargetSpecificationError(
                "target amplitude basis must be a binary string of qubit_count length"
            )
        if basis in seen_basis:
            raise TargetSpecificationError("target amplitude basis must be unique")
        seen_basis.add(basis)
        real = _finite_number(raw_amplitude.get("real"), "real")
        imag = _finite_number(raw_amplitude.get("imag"), "imag")
        norm += real * real + imag * imag
        amplitudes.append(TargetAmplitude(basis=basis, real=real, imag=imag))

    if abs(norm - 1.0) > _NORMALIZATION_TOLERANCE:
        raise TargetSpecificationError("target amplitudes must be normalized")
    return TargetSpecification(
        verification_mode="statevector",
        pure_state_requested=True,
        qubit_count=qubit_count,
        amplitudes=tuple(amplitudes),
        explanation=explanation.strip(),
    )


def pure_state_fidelity(
    actual_statevector: Sequence[complex], target: TargetSpecification
) -> float:
    """Calculate |<target|actual>|^2, naturally ignoring global phase."""
    if target.verification_mode != "statevector" or target.qubit_count is None:
        raise ValueError("statevector target is required")
    dimension = 1 << target.qubit_count
    if len(actual_statevector) != dimension:
        raise SemanticVerificationError(
            "candidate statevector dimension does not match target qubit count"
        )
    target_values = [0j] * dimension
    for amplitude in target.amplitudes:
        target_values[int(amplitude.basis, 2)] = complex(
            amplitude.real, amplitude.imag
        )
    inner_product = sum(
        target_value.conjugate() * complex(actual_value)
        for target_value, actual_value in zip(target_values, actual_statevector)
    )
    fidelity = abs(inner_product) ** 2
    return min(1.0, max(0.0, float(fidelity)))


def _statevector_circuit(circuit: Circuit) -> Circuit:
    return Circuit(
        openqasm_version=circuit.openqasm_version,
        quantum_registers=circuit.quantum_registers,
        classical_registers=circuit.classical_registers,
        operations=tuple(
            operation
            for operation in circuit.operations
            if not isinstance(operation, MeasureOperation)
        ),
    )


def simulate_statevector(circuit: Circuit) -> tuple[complex, ...]:
    """Run the pre-measurement circuit on local Braket braket_sv with shots=0."""
    try:
        devices = importlib.import_module("braket.devices")
        openqasm = importlib.import_module("braket.ir.openqasm")
    except (ImportError, ModuleNotFoundError):
        raise SemanticVerificationError(
            "Braket SDK is required for L2 semantic verification"
        ) from None

    verification_circuit = _statevector_circuit(circuit)
    source = serialize_braket(
        verification_circuit,
        include_stdgates=False,
        execution_mode=True,
    )
    # Braket 会裁掉从未被引用的 idle qubit；零角度旋转只用于保留声明宽度。
    for register in verification_circuit.quantum_registers:
        for index in range(register.size):
            source += "rz(0) %s[%d];\n" % (register.name, index)
    source += "#pragma braket result state_vector\n"
    try:
        device = devices.LocalSimulator("braket_sv")
        program = openqasm.Program(source=source)
        result = device.run(program, shots=0).result()
        values = getattr(result, "values", None)
        if not isinstance(values, list) or len(values) != 1:
            raise SemanticVerificationError(
                "Braket statevector result has an unexpected shape"
            )
        return tuple(complex(value) for value in values[0])
    except SemanticVerificationError:
        raise
    except Exception:
        # SDK 内部异常不携带到修复 Prompt，避免路径或内部栈泄露。
        raise SemanticVerificationError("local Braket statevector simulation failed") from None


def verify_semantics(
    circuit: Circuit,
    target: TargetSpecification,
    *,
    threshold: float = DEFAULT_FIDELITY_THRESHOLD,
) -> SemanticVerificationResult:
    """Verify candidate semantics, or explicitly downgrade unsupported targets."""
    if target.verification_mode == "unsupported":
        return SemanticVerificationResult(fidelity=None, passed=True, mode="unsupported")
    if target.qubit_count != sum(
        register.size for register in circuit.quantum_registers
    ):
        return SemanticVerificationResult(
            fidelity=0.0,
            passed=False,
            mode="statevector",
        )
    fidelity = pure_state_fidelity(simulate_statevector(circuit), target)
    return SemanticVerificationResult(
        fidelity=fidelity,
        passed=fidelity >= threshold,
        mode="statevector",
    )


__all__ = [
    "DEFAULT_FIDELITY_THRESHOLD",
    "SemanticVerificationError",
    "SemanticVerificationResult",
    "TargetAmplitude",
    "TargetSpecification",
    "TargetSpecificationError",
    "parse_target_specification",
    "pure_state_fidelity",
    "simulate_statevector",
    "verify_semantics",
]
