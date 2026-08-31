"""Local, deterministic semantic probes for candidate L2 chat models."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Callable, Iterable

from starter_kit.l2_errors import L2Error
from starter_kit.l2_semantics import validate_prompt_reply


@dataclass(frozen=True)
class ProbeCase:
    name: str
    prompt: str
    category: str


@dataclass(frozen=True)
class TaskResult:
    case: str
    passed: bool
    elapsed_seconds: float
    error: str | None = None


@dataclass(frozen=True)
class ModelResult:
    model: str
    tasks: tuple[TaskResult, ...]

    @property
    def passed(self) -> int:
        return sum(task.passed for task in self.tasks)


@dataclass(frozen=True)
class ProbeReport:
    models: tuple[ModelResult, ...]

    def as_dict(self) -> dict[str, object]:
        return {"models": [asdict(model) for model in self.models]}


def probe_cases() -> tuple[ProbeCase, ...]:
    return (
        ProbeCase(
            "ghz_3",
            "生成一个三量子比特 GHZ OpenQASM 2.0 电路，必须完整测量所有量子比特。",
            "qasm_ghz_3",
        ),
        ProbeCase(
            "repair_bell",
            "修复这段损坏的 Bell 电路并仅返回完整 OpenQASM 2.0："
            " OPENQASM 2.0; include \"qelib1.inc\"; qreg q[2]; creg c[2]; h q[0]; cx q[0] q[1]; measure q -> c;",
            "qasm_bell_2",
        ),
        ProbeCase(
            "backend_free_15",
            "从给定 LoomQ 后端能力表选择一个至少 15 比特、free、queue=none 的规范后端 ID。",
            "backend_free_15",
        ),
    )


def validate_reply(case: ProbeCase, reply: str) -> str | None:
    """Return a precise local failure reason, or ``None`` for a semantic pass."""
    if case.category not in {"qasm_ghz_3", "qasm_bell_2", "backend_free_15"}:
        return "unknown probe category: " + case.category
    return validate_prompt_reply(case.prompt, reply)


def probe_models(
    models: Iterable[str],
    invoke: Callable[[str, str], str],
) -> ProbeReport:
    """Run each local sample independently and continue after safe failures."""
    model_results: list[ModelResult] = []
    for model in models:
        task_results: list[TaskResult] = []
        for case in probe_cases():
            started = time.monotonic()
            try:
                error = validate_reply(case, invoke(model, case.prompt))
            except L2Error as exc:
                error = str(exc)
            except Exception:
                error = "model invocation failed"
            task_results.append(
                TaskResult(
                    case=case.name,
                    passed=error is None,
                    elapsed_seconds=time.monotonic() - started,
                    error=error,
                )
            )
        model_results.append(ModelResult(model=model, tasks=tuple(task_results)))
    return ProbeReport(models=tuple(model_results))
