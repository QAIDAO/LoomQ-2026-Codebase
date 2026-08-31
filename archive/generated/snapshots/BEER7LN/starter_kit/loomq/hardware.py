"""Shared helpers for local-only real-hardware preparation and evidence checks."""

from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
import re
from typing import Mapping, Sequence

from .qasm import MeasureOperation, parse_openqasm2
from .transpilers.spinq import serialize_runtime


_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_env_file(path: Path) -> dict[str, str]:
    """Load a simple KEY=VALUE file without expanding variables or logging values."""

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"invalid environment entry on line {line_number}")
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not _ENV_NAME.fullmatch(name):
            raise ValueError(f"invalid environment name on line {line_number}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[name] = value
    return values


def require_config(config: Mapping[str, str], names: Sequence[str]) -> None:
    missing = [name for name in names if not config.get(name, "").strip()]
    if missing:
        raise ValueError("missing required configuration: " + ", ".join(missing))


def positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def prepare_spinq_cloud_qasm(qasm: str) -> str:
    """Remove explicit measurements because SpinQ Cloud measures automatically."""

    program = parse_openqasm2(qasm)
    operations = tuple(
        operation
        for operation in program.operations
        if not isinstance(operation, MeasureOperation)
    )
    if not operations:
        raise ValueError("SpinQ Cloud circuit must contain at least one gate")
    return serialize_runtime(replace(program, operations=operations))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def redact_text(text: str, config: Mapping[str, str], secret_names: Sequence[str]) -> str:
    redacted = text
    for name in secret_names:
        value = config.get(name, "")
        if len(value) >= 4:
            redacted = redacted.replace(value, "<redacted>")
    return redacted


def assert_no_secret_values(
    text: str, config: Mapping[str, str], secret_names: Sequence[str]
) -> None:
    leaked = [
        name
        for name in secret_names
        if len(config.get(name, "")) >= 4 and config[name] in text
    ]
    if leaked:
        raise ValueError("generated artifact contains sensitive configuration")


def extract_spinq_counts(payload: Mapping[str, object], shots: int, width: int) -> dict[str, int]:
    """Extract counts from a SpinQ raw result, deriving them from probabilities if needed."""

    run = payload.get("run")
    if not isinstance(run, Mapping):
        raise ValueError("SpinQ result is missing the run object")
    raw_counts = run.get("count")
    if isinstance(raw_counts, Mapping) and raw_counts:
        counts = {
            str(key).replace(" ", "").zfill(width): int(round(float(value)))
            for key, value in raw_counts.items()
        }
    else:
        probabilities = run.get("module")
        if not isinstance(probabilities, Mapping) or not probabilities:
            raise ValueError("SpinQ result contains neither counts nor probabilities")
        counts = {
            str(key).replace(" ", "").zfill(width): int(round(float(value) * shots))
            for key, value in probabilities.items()
        }
        difference = shots - sum(counts.values())
        if difference:
            dominant = max(counts, key=counts.get)
            counts[dominant] += difference
    if any(set(key) - {"0", "1"} or len(key) != width for key in counts):
        raise ValueError("SpinQ result contains an invalid bitstring")
    if sum(counts.values()) != shots:
        raise ValueError("SpinQ counts do not sum to shots")
    return dict(sorted(counts.items()))


def extract_originq_counts(
    probabilities: Mapping[str, object], shots: int, width: int
) -> dict[str, int]:
    """Convert OriginQ probability output into integer counts totaling ``shots``."""

    if not probabilities:
        raise ValueError("OriginQ result contains no probabilities")
    counts: dict[str, int] = {}
    for raw_state, raw_probability in probabilities.items():
        state = str(raw_state).replace(" ", "")
        if state.lower().startswith("0x"):
            state = format(int(state, 16), f"0{width}b")
        else:
            state = state.zfill(width)
        if set(state) - {"0", "1"} or len(state) != width:
            raise ValueError("OriginQ result contains an invalid bitstring")
        probability = float(raw_probability)
        if probability < 0:
            raise ValueError("OriginQ result contains a negative probability")
        counts[state] = counts.get(state, 0) + int(round(probability * shots))

    difference = shots - sum(counts.values())
    if difference:
        dominant = max(counts, key=counts.get)
        counts[dominant] += difference
    if any(value < 0 for value in counts.values()) or sum(counts.values()) != shots:
        raise ValueError("OriginQ counts do not sum to shots")
    return dict(sorted(counts.items()))


def top_k_states(counts: Mapping[str, int], k: int) -> list[str]:
    if k <= 0:
        raise ValueError("k must be positive")
    return [
        state
        for state, _count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )[:k]
    ]
