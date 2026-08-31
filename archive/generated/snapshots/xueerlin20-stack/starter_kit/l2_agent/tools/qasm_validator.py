"""QASM validation by actually running circuits through the L1 pipeline."""

from __future__ import annotations

import math
from typing import Any, Callable, Dict

try:
    from ...qasm_L1.parser import parse_qasm
except ImportError:
    from qasm_L1.parser import parse_qasm

from ..models import AgentIntent, ValidationResult


class QASMValidator:
    """Execute QASM on a selected L1 local backend and inspect real counts."""

    def __init__(
        self,
        target: str = "spinq",
        shots: int = 4096,
        fidelity_threshold: float = 0.97,
        executor: Callable[[str, str, int], Dict[str, Any]] | None = None,
    ) -> None:
        if target not in {"spinq", "originq", "braket"}:
            raise ValueError("unsupported L1 validation target: %s" % target)
        if shots <= 0:
            raise ValueError("validation shots must be positive")
        self.target = target
        self.shots = shots
        self.fidelity_threshold = fidelity_threshold
        self._executor = executor

    def validate(self, qasm: str, intent: AgentIntent) -> ValidationResult:
        english = intent.response_language == "en"
        try:
            execution = self._execute(qasm)
        except (SyntaxError, TypeError, ValueError) as exc:
            return ValidationResult(
                False,
                "execution_failed",
                (
                    "L1 %s could not execute the candidate circuit: %s: %s"
                    if english
                    else "L1 %s 无法执行候选电路：%s: %s"
                )
                % (self.target, type(exc).__name__, exc),
                qasm,
            )
        except Exception as exc:
            return ValidationResult(
                False,
                "execution_failed",
                (
                    "L1 %s local simulation failed: %s: %s"
                    if english
                    else "L1 %s 本地模拟执行失败：%s: %s"
                )
                % (self.target, type(exc).__name__, exc),
                qasm,
                details={"target": self.target, "shots": self.shots},
                repairable=False,
            )

        # L1 run() has already parsed and transpiled the program.  Reuse the
        # same IR only to interpret the user's qubit and measurement intent.
        try:
            circuit = parse_qasm(qasm)
        except (SyntaxError, TypeError, ValueError) as exc:
            return ValidationResult(
                False,
                "execution_failed",
                (
                    "L1 %s could not execute the candidate circuit: %s: %s"
                    if english
                    else "L1 %s 无法执行候选电路：%s: %s"
                )
                % (self.target, type(exc).__name__, exc),
                qasm,
            )

        qubits = circuit.qubit_count
        declared_qubits = intent.circuit.get("qubits")
        if isinstance(declared_qubits, int) and not isinstance(declared_qubits, bool):
            if declared_qubits != qubits:
                return ValidationResult(
                    False,
                    "intent_mismatch",
                    (
                        "The request declares %d qubits, but the candidate circuit declares %d."
                        if english
                        else "用户意图声明 %d 比特，但候选电路声明 %d 比特。"
                    )
                    % (declared_qubits, qubits),
                    qasm,
                )

        if intent.circuit.get("measure_all") is True:
            measured_qubits = {
                qubit.global_index
                for measurement in circuit.measurements
                for qubit in measurement.qubits
            }
            missing = sorted(set(range(qubits)) - measured_qubits)
            if missing:
                return ValidationResult(
                    False,
                    "intent_mismatch",
                    (
                        "The request requires full measurement, but qubits %s are not measured."
                        if english
                        else "用户要求全测量，但量子比特 %s 没有测量。"
                    )
                    % ", ".join(str(index) for index in missing),
                    qasm,
                    details={"missing_measurement_qubits": missing},
                )

        try:
            counts = execution["counts"]
            shots = execution["shots"]
            backend = execution["backend"]
            job_id = execution["job_id"]
        except (KeyError, TypeError) as exc:
            return ValidationResult(
                False,
                "execution_failed",
                (
                    "The L1 result is missing required fields."
                    if english
                    else "L1 返回结果缺少必要字段。"
                ),
                qasm,
                repairable=False,
            )
        if not isinstance(counts, dict) or not counts or sum(counts.values()) != shots:
            return ValidationResult(
                False,
                "execution_failed",
                "L1 returned invalid counts."
                if english
                else "L1 返回了无效的 counts。",
                qasm,
                repairable=False,
            )

        details = {
            "target": self.target,
            "backend": backend,
            "job_id": job_id,
            "shots": shots,
            "counts": counts,
        }
        target_state = self._canonical_target(intent.circuit.get("target_state"))
        if target_state in {"ghz", "bell"}:
            if target_state == "bell" and qubits != 2:
                return ValidationResult(
                    False,
                    "intent_mismatch",
                    (
                        "A Bell state requires 2 qubits; the candidate circuit uses %d."
                        if english
                        else "Bell 态必须使用 2 个量子比特，候选电路使用了 %d 个。"
                    )
                    % qubits,
                    qasm,
                    details=details,
                )
            width = circuit.cbit_count or qubits
            expected = {"0" * width: 0.5, "1" * width: 0.5}
            fidelity = self._distribution_fidelity(counts, shots, expected)
            ok = fidelity >= self.fidelity_threshold
            name = "Bell" if target_state == "bell" else "GHZ"
            return ValidationResult(
                ok,
                "verified" if ok else "fidelity_failed",
                (
                    "Executed %d shots on the L1 %s local simulator; %s distribution fidelity is %.6f."
                    % (shots, self.target, name, fidelity)
                    if english
                    else "已在 L1 %s 本地模拟器实际执行 %d shots；%s 分布 Fidelity 为 %.6f。"
                    % (self.target, shots, name, fidelity)
                ),
                qasm,
                fidelity=fidelity,
                details=details,
            )

        return ValidationResult(
            True,
            "executed_unverified",
            (
                "Executed %d shots on the L1 %s local simulator; this target has no independent reference distribution, so intent correctness cannot be proven automatically."
                % (shots, self.target)
                if english
                else "已在 L1 %s 本地模拟器实际执行 %d shots；该目标没有独立参考分布，不能自动证明符合用户意图。"
                % (self.target, shots)
            ),
            qasm,
            details=details,
        )

    def _execute(self, qasm: str) -> Dict[str, Any]:
        if self._executor is not None:
            return self._executor(qasm, self.target, self.shots)
        # Lazy import avoids an adapter/factory import cycle during startup.
        try:
            from ...adapter import run
        except ImportError:
            from adapter import run
        return run(qasm, self.target, self.shots)

    @staticmethod
    def _canonical_target(value) -> str:
        if not isinstance(value, str):
            return "unknown"
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        return {
            "ghz_state": "ghz",
            "bell_state": "bell",
            "bell_pair": "bell",
        }.get(normalized, normalized)

    @staticmethod
    def _distribution_fidelity(
        counts: Dict[str, int], shots: int, expected: Dict[str, float]
    ) -> float:
        observed = {key: value / shots for key, value in counts.items()}
        states = set(observed) | set(expected)
        distance = math.sqrt(
            sum(
                (
                    math.sqrt(observed.get(state, 0.0))
                    - math.sqrt(expected.get(state, 0.0))
                )
                ** 2
                for state in states
            )
        ) / math.sqrt(2.0)
        return max(0.0, min(1.0, 1.0 - distance))
