"""Versioned L2 curriculum backed by the real L1 parser and simulator."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any


STARTER_KIT = Path(__file__).resolve().parent
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

from loomq.qasm import parse_openqasm2  # noqa: E402
from loomq.simulator import _simulate, run_local  # noqa: E402


CURRICULUM_PATH = STARTER_KIT / "curriculum" / "lessons.json"
MAX_SHOTS = 8192
MAX_NONCE_LENGTH = 128


def load_curriculum() -> dict[str, Any]:
    """Load and defensively copy the local, versioned curriculum definition."""

    with CURRICULUM_PATH.open(encoding="utf-8") as handle:
        curriculum = json.load(handle)
    if curriculum.get("schema_version") != "1.0":
        raise ValueError("unsupported curriculum schema_version")
    if not isinstance(curriculum.get("lessons"), list):
        raise ValueError("curriculum lessons must be a list")
    return curriculum


def lesson_catalog() -> dict[str, Any]:
    """Return learner-facing metadata without exposing executable QASM."""

    curriculum = load_curriculum()
    catalog = deepcopy(curriculum)
    for lesson in catalog["lessons"]:
        for experiment in lesson.get("experiments", []):
            experiment.pop("qasm", None)
    return catalog


def simulate_lesson_experiment(
    lesson_id: str,
    experiment_id: str,
    shots: int,
    nonce: str = "",
) -> dict[str, Any]:
    """Execute a curriculum experiment through the L1 parser and simulator."""

    _validate_request(shots, nonce)
    lesson = _find_lesson(lesson_id)
    experiment = _find_experiment(lesson, experiment_id)
    if experiment.get("engine") != "l1_statevector":
        raise ValueError("experiment is not backed by the L1 statevector engine")

    qasm = experiment["qasm"]
    program = parse_openqasm2(qasm)
    state = _simulate(program)
    execution_qasm = _qasm_with_nonce(qasm, nonce)
    result = run_local(execution_qasm, "braket", shots)

    return {
        "lesson": {"id": lesson["id"], "title": lesson["title"]},
        "experiment": {
            key: deepcopy(value)
            for key, value in experiment.items()
            if key != "qasm"
        },
        "engine": "loomq.l1.statevector",
        "statevector": _serialize_statevector(state, program.quantum_register.size),
        "result": result,
    }


def _validate_request(shots: int, nonce: str) -> None:
    if not isinstance(shots, int) or isinstance(shots, bool) or not 1 <= shots <= MAX_SHOTS:
        raise ValueError(f"shots must be an integer between 1 and {MAX_SHOTS}")
    if not isinstance(nonce, str):
        raise ValueError("nonce must be a string")
    if len(nonce) > MAX_NONCE_LENGTH:
        raise ValueError(f"nonce must not exceed {MAX_NONCE_LENGTH} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in nonce):
        raise ValueError("nonce must not contain control characters")


def _find_lesson(lesson_id: str) -> dict[str, Any]:
    if not isinstance(lesson_id, str):
        raise KeyError("unknown lesson")
    for lesson in load_curriculum()["lessons"]:
        if lesson.get("id") == lesson_id:
            return lesson
    raise KeyError(f"unknown lesson: {lesson_id}")


def _find_experiment(lesson: dict[str, Any], experiment_id: str) -> dict[str, Any]:
    if not isinstance(experiment_id, str):
        raise KeyError("unknown experiment")
    for experiment in lesson.get("experiments", []):
        if experiment.get("id") == experiment_id:
            return experiment
    raise KeyError(f"unknown experiment: {experiment_id}")


def _qasm_with_nonce(qasm: str, nonce: str) -> str:
    if not nonce:
        return qasm
    digest = hashlib.sha256(nonce.encode("utf-8")).hexdigest()[:24]
    return f"// loomq-run:{digest}\n{qasm}"


def _serialize_statevector(state: list[complex], qubit_count: int) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for index, amplitude in enumerate(state):
        probability = abs(amplitude) ** 2
        phase = 0.0 if probability < 1e-30 else math.atan2(amplitude.imag, amplitude.real)
        serialized.append(
            {
                "basis": format(index, f"0{qubit_count}b"),
                "amplitude": {
                    "real": _clean_float(amplitude.real),
                    "imag": _clean_float(amplitude.imag),
                },
                "probability": _clean_float(probability),
                "phase_radians": _clean_float(phase),
            }
        )
    return serialized


def _clean_float(value: float) -> float:
    return 0.0 if abs(value) < 1e-15 else float(value)
