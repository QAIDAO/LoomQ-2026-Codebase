"""Opt-in real-model surrogate scorer for LoomQ L2.

This is a local 24-case surrogate suite. It is not the organizer's private
12-case set and its result is not an official competition score.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Mapping


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) in sys.path:
    sys.path.remove(str(STARTER_KIT))
sys.path.insert(0, str(STARTER_KIT))
CAPABILITIES_FILE = STARTER_KIT / "backend_capabilities.json"
DEFAULT_REPORT = STARTER_KIT / "tests" / "generated" / "l2-live-deepseek-report.json"
SURROGATE_SEEDS = (2026081201, 2026081202)
REQUIRED_ENV = ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")
SHOTS = 8192
FIDELITY_THRESHOLD = 0.97


@dataclass(frozen=True)
class SurrogateCase:
    case_id: str
    seed: int
    category: str
    prompt: str
    oracle_name: str
    expected_distribution: dict[str, float] | None = None
    selection_constraints: dict[str, Any] | None = None


def _distribution(*states: str) -> dict[str, float]:
    probability = 1.0 / len(states)
    return {state: probability for state in states}


def _uniform(width: int) -> dict[str, float]:
    return _distribution(*(format(value, f"0{width}b") for value in range(1 << width)))


def _selection_oracles() -> tuple[tuple[str, dict[str, Any]], ...]:
    return (
        (
            "15q-free-zero-queue-no-account",
            {
                "min_qubits": 15,
                "required_kind": None,
                "require_real_hardware": False,
                "require_zero_queue": True,
                "avoid_paid": True,
                "require_no_account": True,
                "allowed_platforms": [],
            },
        ),
        (
            "5q-real-hardware-no-paid",
            {
                "min_qubits": 5,
                "required_kind": None,
                "require_real_hardware": True,
                "require_zero_queue": False,
                "avoid_paid": True,
                "require_no_account": False,
                "allowed_platforms": [],
            },
        ),
        (
            "30q-free-zero-queue",
            {
                "min_qubits": 30,
                "required_kind": None,
                "require_real_hardware": False,
                "require_zero_queue": True,
                "avoid_paid": True,
                "require_no_account": False,
                "allowed_platforms": [],
            },
        ),
        (
            "200q-real-free-zero-queue",
            {
                "min_qubits": 200,
                "required_kind": None,
                "require_real_hardware": True,
                "require_zero_queue": True,
                "avoid_paid": True,
                "require_no_account": False,
                "allowed_platforms": [],
            },
        ),
    )


def build_cases() -> list[SurrogateCase]:
    """Return two balanced, fixed, locally authored surrogate seeds."""
    seed_a, seed_b = SURROGATE_SEEDS
    cases = [
        SurrogateCase(
            "s1-generate-ghz3", seed_a, "generate",
            "请生成一个 3 量子比特 GHZ 最大纠缠态，并把三个量子比特全部测量。返回可执行的 OpenQASM 2.0。",
            "ghz-3", _distribution("000", "111"),
        ),
        SurrogateCase(
            "s1-generate-bell", seed_a, "generate",
            "Create and fully measure a two-qubit Bell pair whose ideal outcomes are equally split between 00 and 11. Use OpenQASM 2.0.",
            "bell", _distribution("00", "11"),
        ),
        SurrogateCase(
            "s1-generate-uniform2", seed_a, "generate",
            "制作一个 2 比特电路，使测量时 00、01、10、11 四种结果等概率出现，并进行全测量。",
            "uniform-2", _uniform(2),
        ),
        SurrogateCase(
            "s1-generate-101", seed_a, "generate",
            "Generate a measured three-qubit OpenQASM 2.0 circuit that deterministically returns classical bit string 101.",
            "deterministic-101", _distribution("101"),
        ),
        SurrogateCase(
            "s1-repair-bell", seed_a, "repair",
            "我想制备并测量 Bell 态，理想结果应为 00/11 各一半。请修复这段错误代码并返回完整 OpenQASM 2.0： H q[0]; CX q[0] q[1]",
            "bell", _distribution("00", "11"),
        ),
        SurrogateCase(
            "s1-repair-ghz3", seed_a, "repair",
            "Repair this program so it prepares a fully measured 3-qubit GHZ state (000 and 111): OPENQASM 2.0; qreg q[3]; H q[0]; CX q[0] q[1]; CX q[1] q[2];",
            "ghz-3", _distribution("000", "111"),
        ),
        SurrogateCase(
            "s1-repair-uniform2", seed_a, "repair",
            "目标是让两个比特的 00、01、10、11 等概率并全部测量。以下代码缺少必要声明且门名错误，请保持目标修好： H q[0]; H q[1]; measure q -> c;",
            "uniform-2", _uniform(2),
        ),
        SurrogateCase(
            "s1-repair-0101", seed_a, "repair",
            "Fix the incomplete QASM while preserving this intent: a four-qubit circuit must deterministically measure 0101. Broken snippet: X q[0]; X q[2]; measure q -> c;",
            "deterministic-0101", _distribution("0101"),
        ),
        SurrogateCase(
            "s2-generate-ghz4", seed_b, "generate",
            "写出完整 OpenQASM 2.0：制备 4 比特最大纠缠 GHZ 态，最终测量所有比特。",
            "ghz-4", _distribution("0000", "1111"),
        ),
        SurrogateCase(
            "s2-generate-ghz5", seed_b, "generate",
            "Produce a five-qubit cat/GHZ state and measure every qubit; ideal shots must concentrate equally on 00000 and 11111.",
            "ghz-5", _distribution("00000", "11111"),
        ),
        SurrogateCase(
            "s2-generate-uniform3", seed_b, "generate",
            "请生成一个全测量的 3 量子比特均匀叠加电路，使八个三位结果理想概率相同。",
            "uniform-3", _uniform(3),
        ),
        SurrogateCase(
            "s2-generate-110", seed_b, "generate",
            "Return executable OpenQASM 2.0 for a measured 3-qubit state that always yields 110.",
            "deterministic-110", _distribution("110"),
        ),
        SurrogateCase(
            "s2-repair-ghz4", seed_b, "repair",
            "修复以下 4 比特 GHZ 意图，结果应只有 0000 和 1111，并补齐完整声明和测量： h q[0]; CX q[0] q[1]; CX q[1] q[2]; CX q[2] q[3]",
            "ghz-4", _distribution("0000", "1111"),
        ),
        SurrogateCase(
            "s2-repair-ghz5", seed_b, "repair",
            "The target is a fully measured 5-qubit GHZ state. Repair this malformed fragment without changing that target: H q[0]; CX q[0] q[1]; CX q[1] q[2]; CX q[2] q[3]; CX q[3] q[4];",
            "ghz-5", _distribution("00000", "11111"),
        ),
        SurrogateCase(
            "s2-repair-uniform3", seed_b, "repair",
            "我要三个比特八种结果等概率。修复并补全这段程序： qreg q[3] H q[0]; H q[1]; H q[2]; MEASURE q -> c;",
            "uniform-3", _uniform(3),
        ),
        SurrogateCase(
            "s2-repair-110", seed_b, "repair",
            "Repair the syntax and declarations so the measured three-bit result is deterministically 110: X q[1] X q[2] measure q -> c",
            "deterministic-110", _distribution("110"),
        ),
    ]

    selection_prompts = {
        seed_a: (
            "我需要运行 15 比特电路：免费、零排队、不注册账号。请从官方能力表推荐一个规范后端标识。",
            "Choose a backend for a 5-qubit experiment on real quantum hardware. Paid-only options are not acceptable, but a free quota and an account are fine.",
            "需要正好能支持至少 30 比特、免费且零排队的运行环境，请给出规范后端 ID。",
            "Select real hardware for 200 qubits with zero queue and no paid use. If none satisfies all constraints, say so honestly and do not invent an ID.",
        ),
        seed_b: (
            "Recommend a canonical backend ID for 15 qubits with no queue, no fee, and no account requirement.",
            "我要做 5 比特真机实验；不能是纯模拟器，也不要只能付费使用，允许账号和免费额度。选哪个后端？",
            "Which published backend can run 30 qubits locally or otherwise with zero waiting and without paid cost? Return its canonical identifier.",
            "我要 200 比特真实量子硬件，同时免费并立即运行。若能力表没有满足全部条件的后端，请明确无解，不能编造平台。",
        ),
    }
    for seed in SURROGATE_SEEDS:
        for index, ((oracle_name, constraints), prompt) in enumerate(
            zip(_selection_oracles(), selection_prompts[seed]), start=1
        ):
            cases.append(
                SurrogateCase(
                    f"s{1 if seed == seed_a else 2}-select-{index}",
                    seed,
                    "select",
                    prompt,
                    oracle_name,
                    None,
                    dict(constraints),
                )
            )
    return cases


def build_execution_cases(suite: str) -> list[Any]:
    """Select the fixed baseline, stratified live sample, or full extended corpus."""
    if suite == "baseline24":
        return list(build_cases())
    if __package__:
        from .l2_surrogate_corpus import build_extended_cases, stratified_live_sample
    else:
        from tests.l2_surrogate_corpus import build_extended_cases, stratified_live_sample
    if suite == "extended60":
        return list(stratified_live_sample(size=60, seed=2026081203))
    if suite == "extended192":
        return list(build_extended_cases())
    raise ValueError(f"unknown suite: {suite}")


def _case_metadata(case: Any) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "seed": getattr(case, "seed", 2026081203),
        "category": case.category,
        "oracle_name": getattr(case, "oracle_name", getattr(case, "family", "unknown")),
        "prompt_sha256": _sha256_text(case.prompt),
    }

def _capabilities() -> list[dict[str, Any]]:
    payload = json.loads(CAPABILITIES_FILE.read_text(encoding="utf-8"))
    return [dict(item) for item in payload["backends"]]


def expected_backend_ids(constraints: Mapping[str, Any] | None) -> set[str]:
    """Independently filter the published backend capability table."""
    if constraints is None:
        return set()
    required_kind = "qpu" if constraints.get("require_real_hardware") else constraints.get("required_kind")
    allowed = {str(item).lower() for item in constraints.get("allowed_platforms", [])}
    matches: set[str] = set()
    for backend in _capabilities():
        if int(backend["max_qubits"]) < int(constraints.get("min_qubits", 1)):
            continue
        if required_kind and backend["kind"] != required_kind:
            continue
        if constraints.get("require_zero_queue") and backend["queue"] != "none":
            continue
        if constraints.get("avoid_paid") and backend["cost"] == "paid":
            continue
        if constraints.get("require_no_account") and backend["requires_account"]:
            continue
        if allowed and str(backend["platform"]).lower() not in allowed:
            continue
        matches.add(str(backend["id"]))
    return matches


def redact_report(value: Any, secrets: list[str]) -> Any:
    """Recursively remove configured credentials and credential-like strings."""
    active = [secret for secret in secrets if secret]

    def redact_text(text: str) -> str:
        for secret in active:
            text = text.replace(secret, "[REDACTED]")
        token_prefix = "s" + "k-"
        return re.sub(re.escape(token_prefix) + r"[A-Za-z0-9_-]{8,}", "[REDACTED]", text)

    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_report(item, active) for item in value]
    if isinstance(value, tuple):
        return [redact_report(item, active) for item in value]
    if isinstance(value, Mapping):
        return {str(key): redact_report(item, active) for key, item in value.items()}
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _git_provenance() -> dict[str, Any]:
    def git(*arguments: str) -> str:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=STARTER_KIT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return completed.stdout.strip() if completed.returncode == 0 else ""

    return {
        "commit": git("rev-parse", "HEAD"),
        "working_tree_dirty": bool(git("status", "--porcelain")),
        "harness_sha256": _sha256_text(
            Path(__file__).read_text(encoding="utf-8")
        ),
        "capabilities_sha256": _sha256_text(
            CAPABILITIES_FILE.read_text(encoding="utf-8")
        ),
    }


def _report_integrity_sha256(report: Mapping[str, Any]) -> str:
    unsigned = dict(report)
    unsigned.pop("integrity_sha256", None)
    serialized = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return _sha256_text(serialized)


def verify_campaign_report(
    path: Path, *, minimum_cases: int = 24
) -> list[str]:
    """Return integrity and semantic-evidence errors for a saved live report."""

    if not path.is_file():
        return [f"campaign report does not exist: {path}"]
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"campaign report is invalid JSON: {exc}"]
    if not isinstance(report, Mapping):
        return ["campaign report root must be an object"]

    errors: list[str] = []
    if report.get("schema_version") != "1.1":
        errors.append("campaign report schema_version must be 1.1")
    if report.get("integrity_sha256") != _report_integrity_sha256(report):
        errors.append("campaign report integrity hash mismatch")
    provenance = report.get("provenance", {})
    current = _git_provenance()
    if not isinstance(provenance, Mapping):
        errors.append("campaign report provenance is missing")
    else:
        for field in ("harness_sha256", "capabilities_sha256"):
            if provenance.get(field) != current[field]:
                errors.append(f"campaign provenance mismatch: {field}")

    cases = report.get("cases", [])
    definitions = report.get("case_definitions", [])
    if not isinstance(cases, list) or not isinstance(definitions, list):
        return errors + ["campaign cases and definitions must be arrays"]
    if len(cases) < minimum_cases:
        errors.append(
            f"campaign must contain at least {minimum_cases} cases; found {len(cases)}"
        )
    if report.get("selected_case_count") != len(cases) or len(definitions) != len(cases):
        errors.append("campaign case counts are inconsistent")
    if report.get("failed") != 0 or report.get("passed") != len(cases):
        errors.append("campaign contains failed semantic cases")

    definitions_by_id = {
        item.get("case_id"): item
        for item in definitions
        if isinstance(item, Mapping)
    }
    if len(definitions_by_id) != len(definitions):
        errors.append("campaign case definitions contain duplicate or invalid IDs")
    seen: set[str] = set()
    for item in cases:
        if not isinstance(item, Mapping):
            errors.append("campaign contains a non-object case result")
            continue
        case_id = str(item.get("case_id", ""))
        if not case_id or case_id in seen:
            errors.append(f"campaign result has duplicate or empty case ID: {case_id!r}")
            continue
        seen.add(case_id)
        definition = definitions_by_id.get(case_id)
        if not isinstance(definition, Mapping):
            errors.append(f"{case_id}: matching case definition is missing")
            continue
        if item.get("prompt_sha256") != _sha256_text(str(definition.get("prompt", ""))):
            errors.append(f"{case_id}: prompt hash mismatch")
        reply = str(item.get("reply", ""))
        if item.get("reply_sha256") != _sha256_text(reply):
            errors.append(f"{case_id}: reply hash mismatch")
        if int(item.get("model_calls", 0)) < 1:
            errors.append(f"{case_id}: no observed model call")
        if not item.get("passed"):
            errors.append(f"{case_id}: semantic score did not pass")
        if item.get("category") in {"generate", "repair"}:
            try:
                qasm = _extract_qasm(reply)
            except ValueError as exc:
                errors.append(f"{case_id}: extractor validation failed: {exc}")
                continue
            if item.get("qasm") != qasm or item.get("qasm_sha256") != _sha256_text(qasm):
                errors.append(f"{case_id}: QASM artifact hash mismatch")
    return errors


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"environment file does not exist: {path}")
    for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            raise RuntimeError(f"invalid environment assignment at line {line_number}")
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if value[:1] == value[-1:] and value[:1] in {"'", '"'}:
            value = value[1:-1]
        if name in REQUIRED_ENV or name.startswith("LOOMQ_LLM_"):
            os.environ[name] = value


def _extract_qasm(reply: str) -> str:
    headers = list(re.finditer(r"OPENQASM\s+2\.0;", reply, re.IGNORECASE))
    if len(headers) != 1:
        raise ValueError(
            f"agent reply must contain exactly one OpenQASM header; found {len(headers)}"
        )
    official = re.search(
        r"OPENQASM\s+2\.0;.*?(?=^\s*```|\Z)",
        reply,
        re.DOTALL | re.MULTILINE | re.IGNORECASE,
    )
    if official is None:
        raise ValueError("agent reply contains no OpenQASM 2.0 program")
    fenced = re.search(
        r"```(?:qasm|openqasm)?\s*(OPENQASM\s+2\.0;.*?)```",
        reply,
        re.IGNORECASE | re.DOTALL,
    )
    if fenced is None or fenced.group(1).strip() != official.group(0).strip():
        raise ValueError("official extractor output differs from the fenced QASM artifact")
    return official.group(0).strip()


def _hellinger_fidelity(counts: Mapping[str, int], expected: Mapping[str, float]) -> float:
    shots = sum(int(value) for value in counts.values())
    if shots <= 0:
        return 0.0
    states = set(counts) | set(expected)
    coefficient = sum(
        ((int(counts.get(state, 0)) / shots) * float(expected.get(state, 0.0))) ** 0.5
        for state in states
    )
    return min(1.0, coefficient * coefficient)


def _score_case(case: Any, worker: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = dict(worker)
    result.update(_case_metadata(case))
    result["reply_sha256"] = _sha256_text(str(worker.get("reply", "")))
    result["passed"] = False
    if worker.get("error"):
        result["score_reason"] = "agent execution failed"
        return result
    if int(worker.get("model_calls", 0)) < 1:
        result["score_reason"] = "no valid model-service call was observed"
        return result
    reply = str(worker.get("reply", ""))
    if case.category in {"generate", "repair"}:
        try:
            if str(STARTER_KIT) not in sys.path:
                sys.path.insert(0, str(STARTER_KIT))
            from loomq.simulator import run_local

            qasm = _extract_qasm(reply)
            simulation = run_local(qasm, "originq", SHOTS)
            counts = simulation["counts"]
            production_fidelity = _hellinger_fidelity(counts, case.expected_distribution or {})
            if __package__:
                from .l2_surrogate_corpus import independent_distribution, hellinger_fidelity
            else:
                from tests.l2_surrogate_corpus import independent_distribution, hellinger_fidelity
            independent_observed = independent_distribution(qasm)
            independent_fidelity = hellinger_fidelity(
                independent_observed, case.expected_distribution or {}
            )
            result.update({
                "qasm": qasm,
                "qasm_sha256": _sha256_text(qasm),
                "counts": counts,
                "shots": SHOTS,
                "production_fidelity": production_fidelity,
                "independent_distribution": independent_observed,
                "independent_fidelity": independent_fidelity,
                "fidelity": min(production_fidelity, independent_fidelity),
                "threshold": FIDELITY_THRESHOLD,
            })
            result["passed"] = (
                production_fidelity >= FIDELITY_THRESHOLD
                and independent_fidelity >= FIDELITY_THRESHOLD
            )
            result["score_reason"] = (
                "both production and independent fidelity thresholds met"
                if result["passed"] else "production or independent fidelity below threshold"
            )
        except Exception as exc:  # A malformed reply is a scored failure.
            result["score_reason"] = f"QASM validation failed: {type(exc).__name__}: {exc}"
    else:
        expected = expected_backend_ids(case.selection_constraints)
        canonical_ids = {str(item["id"]) for item in _capabilities()}
        observed = {backend_id for backend_id in canonical_ids if backend_id in reply}
        if expected:
            passed = len(observed) == 1 and observed <= expected
        else:
            passed = not observed
        result.update({"expected_backend_ids": sorted(expected), "observed_backend_ids": sorted(observed), "passed": passed})
        result["score_reason"] = "backend oracle matched" if passed else "backend oracle mismatch"
    return result


def serialize_worker_payload(payload: Mapping[str, Any]) -> str:
    """Serialize the worker protocol using ASCII escapes for Windows consoles."""
    return json.dumps(payload, ensure_ascii=True)

def _worker(case_id: str, suite: str) -> int:
    if str(STARTER_KIT) not in sys.path:
        sys.path.insert(0, str(STARTER_KIT))
    case = next((item for item in build_execution_cases(suite) if item.case_id == case_id), None)
    if case is None:
        print(json.dumps({"error": "unknown case id"}))
        return 2

    import adapter
    import loomq.l2 as l2_module

    original = l2_module.chat_completion
    telemetry: dict[str, Any] = {"model_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def observed_chat_completion(*args: Any, **kwargs: Any) -> dict[str, Any]:
        response = original(*args, **kwargs)
        telemetry["model_calls"] += 1
        usage = response.get("usage", {}) if isinstance(response, Mapping) else {}
        if isinstance(usage, Mapping):
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                value = usage.get(key, 0)
                if isinstance(value, int) and not isinstance(value, bool):
                    telemetry[key] += value
        return response

    l2_module.chat_completion = observed_chat_completion
    started = time.monotonic()
    payload: dict[str, Any]
    try:
        payload = {"reply": adapter.agent_chat(case.prompt), "error": None}
    except Exception as exc:
        payload = {"reply": "", "error": f"{type(exc).__name__}: {exc}"}
    payload.update(telemetry)
    payload["elapsed_seconds"] = time.monotonic() - started
    print(serialize_worker_payload(payload))
    return 0


def _run_worker(case: Any, timeout_seconds: float, suite: str) -> dict[str, Any]:
    command = [sys.executable, str(Path(__file__).resolve()), "--worker", case.case_id, "--worker-suite", suite]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=STARTER_KIT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {"reply": "", "error": f"case exceeded {timeout_seconds:g} seconds", "model_calls": 0, "elapsed_seconds": time.monotonic() - started}
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        return {"reply": "", "error": "worker returned no JSON result", "model_calls": 0, "elapsed_seconds": time.monotonic() - started, "worker_stderr": completed.stderr[-2000:]}
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError:
        payload = {"reply": "", "error": "worker returned invalid JSON", "model_calls": 0, "worker_stdout": completed.stdout[-2000:], "worker_stderr": completed.stderr[-2000:]}
    payload["worker_returncode"] = completed.returncode
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an opt-in real DeepSeek L2 surrogate score.")
    parser.add_argument("--env-file", type=Path, default=STARTER_KIT / ".env.l2.local")
    parser.add_argument("--suite", choices=("baseline24", "extended60", "extended192"), default="baseline24")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--case", action="append", dest="case_ids", help="Run only this case ID; repeat to select more cases.")
    parser.add_argument("--timeout-seconds", type=float, default=125.0, help="Outer subprocess timeout; agent requests remain governed by LOOMQ_LLM_TIMEOUT_SECONDS.")
    parser.add_argument("--live", action="store_true", help="Required acknowledgement that this command makes billable network calls.")
    parser.add_argument("--worker", metavar="CASE_ID", help=argparse.SUPPRESS)
    parser.add_argument("--worker-suite", choices=("baseline24", "extended60", "extended192"), default="baseline24", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.worker:
        return _worker(args.worker, args.worker_suite)
    if not args.live:
        print("Refusing to call the model without --live. This protects normal tests from API usage.", file=sys.stderr)
        return 2
    _load_env_file(args.env_file.resolve())
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        print("Missing required environment variable(s): " + ", ".join(missing), file=sys.stderr)
        return 2
    if args.timeout_seconds <= 0:
        print("--timeout-seconds must be positive", file=sys.stderr)
        return 2

    selected = build_execution_cases(args.suite)
    if args.case_ids:
        requested = set(args.case_ids)
        selected = [case for case in selected if case.case_id in requested]
        unknown = requested - {case.case_id for case in selected}
        if unknown:
            print("Unknown case ID(s): " + ", ".join(sorted(unknown)), file=sys.stderr)
            return 2

    results: list[dict[str, Any]] = []
    for index, case in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] {case.case_id} ...", flush=True)
        scored = _score_case(case, _run_worker(case, args.timeout_seconds, args.suite))
        results.append(scored)
        status = "PASS" if scored["passed"] else "FAIL"
        print(f"  {status}: {scored['score_reason']}", flush=True)

    passed = sum(bool(item["passed"]) for item in results)
    report: dict[str, Any] = {
        "schema_version": "1.1",
        "suite": f"loomq-l2-live-deepseek-{args.suite}",
        "disclaimer": "Locally authored same-family surrogate cases; not organizer private seeds and not an official score.",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "model": os.environ.get("LOOMQ_LLM_MODEL", ""),
        "surrogate_seeds": list(SURROGATE_SEEDS),
        "selected_case_count": len(selected),
        "passed": passed,
        "failed": len(selected) - passed,
        "pass_rate": passed / len(selected) if selected else 0.0,
        "fidelity_threshold": FIDELITY_THRESHOLD,
        "shots": SHOTS,
        "provenance": _git_provenance(),
        "cases": results,
        "case_definitions": [asdict(case) for case in selected],
    }
    secrets = [os.environ.get("LOOMQ_LLM_API_KEY", "")]
    safe_report = redact_report(report, secrets)
    safe_report["integrity_sha256"] = _report_integrity_sha256(safe_report)
    report_path = args.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(safe_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    serialized = report_path.read_text(encoding="utf-8")
    if any(secret and secret in serialized for secret in secrets):
        report_path.unlink(missing_ok=True)
        print("Credential redaction self-check failed; report was removed.", file=sys.stderr)
        return 3
    print(f"Surrogate result: {passed}/{len(selected)} passed. Report: {report_path}")
    return 0 if passed == len(selected) else 1


if __name__ == "__main__":
    raise SystemExit(main())
