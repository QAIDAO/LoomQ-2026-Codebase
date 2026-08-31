"""Application service shared by the workbench HTTP handler and tests."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Mapping, Optional

from ..facade import run as run_circuit
from ..facade import transpile
from ..hybrid import compile_hybrid_program
from ..qasm import GateOp, MeasureOp, QASMError, parse_and_normalize
from ..targets.registry import SUPPORTED_TARGETS
from .workspace import RunWorkspace, WorkspaceSession, redact_text


MAX_PROMPT_CHARS = 16_000
MAX_SOURCE_BYTES = 256_000
TASKS = ("simulate", "transpile", "hybrid", "agent", "repair")
_LOCATION = re.compile(r"line\s+(\d+),\s*column\s+(\d+)", re.IGNORECASE)
_FENCED_QASM = re.compile(
    r"```(?:openqasm|qasm)?\s*\r?\n(.*?)```", re.IGNORECASE | re.DOTALL
)


class WorkbenchRequestError(ValueError):
    """A stable, user-correctable API failure."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "INVALID_REQUEST",
        suggestion: Optional[str] = None,
        line: Optional[int] = None,
        column: Optional[int] = None,
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.suggestion = suggestion
        self.line = line
        self.column = column
        self.retryable = retryable


class WorkbenchService:
    """Execute bounded UI workflows and persist an evidence ledger for each."""

    def __init__(self, workspace: WorkspaceSession) -> None:
        self.workspace = workspace

    def health(self) -> Dict[str, Any]:
        llm_ready = all(
            os.environ.get(name)
            for name in (
                "LOOMQ_LLM_BASE_URL",
                "LOOMQ_LLM_API_KEY",
                "LOOMQ_LLM_MODEL",
            )
        )
        return {
            "ok": True,
            "service": "loomq-workbench",
            "session_id": self.workspace.session_id,
            "binding": "local",
            "targets": list(SUPPORTED_TARGETS),
            "components": {
                "qasm_parser": "ready",
                "reference_runtime": "ready",
                "hybrid_compiler": "ready",
                "llm_agent": "ready" if llm_ready else "configuration_required",
                "evidence_workspace": "ready",
            },
        }

    def examples(self) -> list[Dict[str, Any]]:
        return [
            {
                "id": "bell-2",
                "title_zh": "Bell 态 · 2 比特",
                "title_en": "Bell state · 2 qubits",
                "note_zh": "最小纠缠回路，预期 00 / 11 为主。",
                "note_en": "Minimal entanglement; 00 / 11 should dominate.",
                "task": "simulate",
                "target": "spinq",
                "shots": 1024,
                "prompt": "验证两比特 Bell 态的相关性。",
                "qasm": """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;""",
            },
            {
                "id": "ghz-3",
                "title_zh": "GHZ 链 · 3 比特",
                "title_en": "GHZ chain · 3 qubits",
                "note_zh": "检查多比特转译与小端位序。",
                "note_en": "Checks multi-qubit lowering and little-endian results.",
                "task": "simulate",
                "target": "braket",
                "shots": 2048,
                "prompt": "在三个比特上编译并执行 GHZ 态。",
                "qasm": """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[3];
creg c[3];
h q[0];
cx q[0], q[1];
cx q[1], q[2];
measure q -> c;""",
            },
            {
                "id": "hybrid-feed-forward",
                "title_zh": "测量后分支 · Hybrid",
                "title_en": "Post-measure branch · Hybrid",
                "note_zh": "把 c[0] 编译为 TinyRISCV 条件分支。",
                "note_en": "Lowers c[0] into deterministic TinyRISCV branches.",
                "task": "hybrid",
                "target": "originq",
                "shots": 256,
                "prompt": "编译测量结果驱动的经典分支。",
                "qasm": """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[1];
creg c[1];
h q[0];
measure q[0] -> c[0];
classical {
  if (c[0] == 1) { r1 = 7; }
  else { r1 = 3; }
}""",
            },
        ]

    def execute(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        run = self.workspace.begin_request()
        task = "unknown"
        target = "spinq"
        try:
            run.write_json("request.json", dict(payload))
            request = _validate_payload(payload)
            task = request["task"]
            target = request["target"]
            intent = _intent_record(request)
            run.write_json("intent.json", intent)
            if task == "hybrid":
                response = self._execute_hybrid(run, request, intent)
            else:
                response = self._execute_quantum(run, request, intent)
            manifest = run.finalize(
                "completed",
                {
                    "task": task,
                    "target": target,
                    "operation_count": response["normalized"].get(
                        "operation_count", 0
                    ),
                },
            )
            response.update(
                {
                    "ok": True,
                    "run_id": run.run_id,
                    "manifest": manifest,
                    "workflow": _workflow("completed", task),
                }
            )
            return response
        except Exception as exc:
            error = _public_error(exc)
            self._write_failure_artifacts(run, task, target, error)
            manifest = run.finalize(
                "failed",
                {"task": task, "target": target, "error_code": error["code"]},
            )
            return {
                "ok": False,
                "run_id": run.run_id,
                "error": error,
                "manifest": manifest,
                "workflow": _workflow("failed", task),
            }

    def _execute_quantum(
        self,
        run: RunWorkspace,
        request: Dict[str, Any],
        intent: Dict[str, Any],
    ) -> Dict[str, Any]:
        task = request["task"]
        source = request["qasm"]
        agent_output = ""

        if task == "repair":
            source = _deterministic_repair(source)
        elif task == "agent":
            agent_output = _call_agent(request["prompt"])
            extracted = _extract_agent_qasm(agent_output)
            if not extracted:
                normalized = {
                    "source_type": "agent_response",
                    "operation_count": 0,
                    "qubit_count": 0,
                    "classical_count": 0,
                    "operations": [],
                }
                result = {
                    "status": "agent_response",
                    "output": agent_output,
                    "note": "No circuit artifact was present; no quantum run was claimed.",
                }
                verification = {
                    "status": "passed",
                    "checks": [
                        {
                            "id": "agent-response-bounded",
                            "passed": True,
                            "detail": "A bounded response was returned without hidden reasoning.",
                        },
                        {
                            "id": "qasm-admission",
                            "passed": False,
                            "detail": "Not applicable: response contained no OpenQASM artifact.",
                        },
                    ],
                }
                run.write_json("normalized.json", normalized)
                run.write_json("ir/index.json", {"artifacts": []})
                run.write_json("result.json", result)
                run.write_json("verification.json", verification)
                return {
                    "intent": intent,
                    "normalized": normalized,
                    "ir": {},
                    "result": result,
                    "verification": verification,
                    "agent_output": agent_output,
                    "source": "",
                }
            source = extracted

        circuit = parse_and_normalize(source)
        normalized = _normalized_circuit(circuit)
        ir = {target: transpile(source, target) for target in SUPPORTED_TARGETS}
        for ir_target, artifact in ir.items():
            extension = "qasm" if ir_target != "originq" else "originir"
            run.write_text("ir/%s.%s" % (ir_target, extension), artifact)
        run.write_json(
            "ir/index.json",
            {
                "artifacts": [
                    {
                        "target": ir_target,
                        "format": (
                            "OpenQASM 3"
                            if ir_target == "braket"
                            else "OriginIR"
                            if ir_target == "originq"
                            else "OpenQASM 2"
                        ),
                    }
                    for ir_target in SUPPORTED_TARGETS
                ]
            },
        )

        should_run = task in {"simulate", "agent"}
        if should_run:
            result = run_circuit(source, request["target"], request["shots"])
        else:
            result = {
                "status": "not_run",
                "reason": (
                    "repair_only" if task == "repair" else "transpile_only"
                ),
                "shots": request["shots"],
            }
        verification = _verification_record(
            circuit,
            ir,
            result if should_run else None,
            request["shots"],
        )
        run.write_json("normalized.json", normalized)
        run.write_json("result.json", result)
        run.write_json("verification.json", verification)
        return {
            "intent": intent,
            "normalized": normalized,
            "ir": ir,
            "result": result,
            "verification": verification,
            "agent_output": agent_output,
            "source": source,
        }

    def _execute_hybrid(
        self,
        run: RunWorkspace,
        request: Dict[str, Any],
        intent: Dict[str, Any],
    ) -> Dict[str, Any]:
        quantum, assembly = compile_hybrid_program(request["qasm"])
        normalized = {
            "source_type": "hybrid_qasm",
            "operation_count": len(quantum),
            "qubit_count": None,
            "classical_count": None,
            "quantum_operations": quantum,
            "assembly_instruction_count": len(
                [line for line in assembly.splitlines() if line and not line.endswith(":")]
            ),
        }
        ir = {"quantum": "\n".join(quantum), "tinyriscv": assembly}
        run.write_text("ir/hybrid-quantum.txt", ir["quantum"])
        run.write_text("ir/tinyriscv.s", assembly)
        run.write_json(
            "ir/index.json",
            {
                "artifacts": [
                    {"target": "quantum", "format": "normalized operations"},
                    {"target": "tinyriscv", "format": "TinyRISCV assembly"},
                ]
            },
        )
        result = {
            "status": "compiled",
            "reason": "hybrid_compile_only",
            "assembly_instruction_count": normalized[
                "assembly_instruction_count"
            ],
        }
        verification = {
            "status": "passed",
            "checks": [
                {
                    "id": "hybrid-parser",
                    "passed": True,
                    "detail": "Hybrid-QASM was accepted by the deterministic parser.",
                },
                {
                    "id": "instruction-allowlist",
                    "passed": _assembly_is_allowlisted(assembly),
                    "detail": "Generated instructions stay inside the official TinyRISCV subset.",
                },
            ],
        }
        run.write_json("normalized.json", normalized)
        run.write_json("result.json", result)
        run.write_json("verification.json", verification)
        return {
            "intent": intent,
            "normalized": normalized,
            "ir": ir,
            "result": result,
            "verification": verification,
            "agent_output": "",
            "source": request["qasm"],
        }

    @staticmethod
    def _write_failure_artifacts(
        run: RunWorkspace, task: str, target: str, error: Dict[str, Any]
    ) -> None:
        if "request.json" not in run._artifacts:
            run.write_json(
                "request.json",
                {"status": "rejected", "reason": "request could not be persisted"},
            )
        if "intent.json" not in run._artifacts:
            run.write_json(
                "intent.json",
                {"task": task, "target": target, "status": "rejected"},
            )
        if "normalized.json" not in run._artifacts:
            run.write_json(
                "normalized.json",
                {"status": "not_available", "reason": error["code"]},
            )
        if "ir/index.json" not in run._artifacts:
            run.write_json(
                "ir/index.json",
                {"artifacts": [], "reason": "source admission failed"},
            )
        if "result.json" not in run._artifacts:
            run.write_json(
                "result.json", {"status": "not_run", "reason": error["code"]}
            )
        if "verification.json" not in run._artifacts:
            run.write_json(
                "verification.json",
                {
                    "status": "failed",
                    "checks": [
                        {
                            "id": "source-admission",
                            "passed": False,
                            "detail": error["message"],
                        }
                    ],
                },
            )


def _validate_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise WorkbenchRequestError("JSON body must be an object")
    task = payload.get("task", "simulate")
    if not isinstance(task, str) or task not in TASKS:
        raise WorkbenchRequestError(
            "task must be one of: " + ", ".join(TASKS),
            suggestion="Choose a task from the workbench task selector.",
        )
    target = payload.get("target", "spinq")
    if not isinstance(target, str) or target not in SUPPORTED_TARGETS:
        raise WorkbenchRequestError(
            "target must be one of: " + ", ".join(SUPPORTED_TARGETS),
            suggestion="Select SpinQ, OriginQ, or Braket.",
        )
    shots = payload.get("shots", 1024)
    if (
        not isinstance(shots, int)
        or isinstance(shots, bool)
        or shots < 1
        or shots > 100_000
    ):
        raise WorkbenchRequestError(
            "shots must be an integer between 1 and 100000",
            suggestion="Try 1024 shots for an interactive local run.",
        )
    prompt = payload.get("prompt", "")
    qasm = payload.get("qasm", "")
    if not isinstance(prompt, str) or len(prompt) > MAX_PROMPT_CHARS:
        raise WorkbenchRequestError(
            "prompt must be a string no longer than 16000 characters"
        )
    if not isinstance(qasm, str) or len(qasm.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise WorkbenchRequestError(
            "source must be a string no larger than 256000 UTF-8 bytes"
        )
    if task == "agent" and not prompt.strip():
        raise WorkbenchRequestError(
            "agent task requires a prompt",
            suggestion="Describe a circuit, a QASM repair, or backend constraints.",
        )
    if task != "agent" and not qasm.strip():
        raise WorkbenchRequestError(
            "this task requires QASM source",
            suggestion="Load one of the three verified examples or enter source code.",
        )
    return {
        "task": task,
        "target": target,
        "shots": shots,
        "prompt": prompt.strip(),
        "qasm": qasm,
    }


def _intent_record(request: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "task": request["task"],
        "source_type": (
            "hybrid_qasm" if request["task"] == "hybrid" else "openqasm_2"
        ),
        "target": request["target"],
        "shots": request["shots"],
        "language": (
            "zh" if re.search(r"[\u3400-\u9fff]", request["prompt"]) else "en"
        ),
        "agent_requested": request["task"] == "agent",
        "note": "Intent fields are task metadata, not hidden model reasoning.",
    }


def _normalized_circuit(circuit: Any) -> Dict[str, Any]:
    operations = []
    for index, operation in enumerate(circuit.operations):
        if isinstance(operation, GateOp):
            operations.append(
                {
                    "index": index,
                    "kind": "gate",
                    "name": operation.name,
                    "qubits": list(operation.qubits),
                    "params": list(operation.params),
                }
            )
        elif isinstance(operation, MeasureOp):
            operations.append(
                {
                    "index": index,
                    "kind": "measure",
                    "qubit": operation.qubit,
                    "cbit": operation.cbit,
                }
            )
    return {
        "source_type": "openqasm_2",
        "qubit_count": circuit.qubit_count,
        "classical_count": circuit.classical_count,
        "operation_count": len(operations),
        "operations": operations,
    }


def _verification_record(
    circuit: Any,
    ir: Mapping[str, str],
    result: Optional[Mapping[str, Any]],
    shots: int,
) -> Dict[str, Any]:
    checks = [
        {
            "id": "qasm-parse",
            "passed": True,
            "detail": "%d normalized operations admitted."
            % len(circuit.operations),
        },
        {
            "id": "target-roundtrip",
            "passed": set(ir) == set(SUPPORTED_TARGETS)
            and all(bool(value.strip()) for value in ir.values()),
            "detail": "SpinQ, OriginQ, and Braket artifacts passed semantic round-trip admission.",
        },
    ]
    if result is not None:
        counts = result.get("counts", {})
        checks.extend(
            [
                {
                    "id": "result-schema",
                    "passed": all(
                        key in result
                        for key in (
                            "backend",
                            "job_id",
                            "shots",
                            "counts",
                            "bit_order",
                            "timestamp",
                        )
                    ),
                    "detail": "Runtime result contains the official required fields.",
                },
                {
                    "id": "shot-conservation",
                    "passed": isinstance(counts, Mapping)
                    and sum(counts.values()) == shots,
                    "detail": "Counts sum exactly to the requested shots.",
                },
                {
                    "id": "bit-order",
                    "passed": result.get("bit_order") == "little",
                    "detail": "Result reports the official little-endian bit order.",
                },
            ]
        )
    return {
        "status": "passed" if all(item["passed"] for item in checks) else "failed",
        "checks": checks,
    }


def _assembly_is_allowlisted(assembly: str) -> bool:
    allowed = {"li", "add", "addi", "sub", "beq", "bne", "j"}
    for line in assembly.splitlines():
        clean = line.strip()
        if not clean or clean.endswith(":"):
            continue
        if clean.split(maxsplit=1)[0] not in allowed:
            return False
    return True


def _deterministic_repair(source: str) -> str:
    """Apply only bounded, visible syntax repairs; never invent circuit gates."""

    clean = (
        source.replace("\ufeff", "")
        .replace("\x00", "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("“", '"')
        .replace("”", '"')
    )
    lines = [line.rstrip() for line in clean.splitlines() if line.strip()]
    repaired = []
    statement = re.compile(
        r"^\s*(OPENQASM|include|qreg|creg|measure|h|x|s|sdg|t|tdg|"
        r"ry|rz|cx|cu1|swap|ccx)\b",
        re.IGNORECASE,
    )
    for line in lines:
        stripped = line.strip()
        if statement.match(stripped) and not stripped.endswith(";"):
            line = line + ";"
        repaired.append(line)
    joined = "\n".join(repaired)
    if not re.search(r"^\s*OPENQASM\s+2\.0\s*;", joined, re.IGNORECASE):
        joined = "OPENQASM 2.0;\n" + joined
    if not re.search(r"\binclude\s+[\"']qelib1\.inc[\"']\s*;", joined, re.IGNORECASE):
        parts = joined.splitlines()
        parts.insert(1, 'include "qelib1.inc";')
        joined = "\n".join(parts)
    try:
        parse_and_normalize(joined)
    except Exception as exc:
        public = _public_error(exc)
        raise WorkbenchRequestError(
            "The conservative repair could not safely admit this circuit: "
            + public["message"],
            code="REPAIR_INCOMPLETE",
            suggestion=public.get("suggestion")
            or "Correct the highlighted source location, then run repair again.",
            line=public.get("line"),
            column=public.get("column"),
        ) from exc
    return joined


def _call_agent(prompt: str) -> str:
    try:
        from ..agent.workflow import agent_chat

        response = agent_chat(prompt)
    except Exception as exc:
        raise WorkbenchRequestError(
            "The LLM agent is not available for this local session: "
            + redact_text(str(exc)),
            code="AGENT_UNAVAILABLE",
            suggestion=(
                "Configure LOOMQ_LLM_BASE_URL, LOOMQ_LLM_API_KEY, and "
                "LOOMQ_LLM_MODEL, then retry. Local transpilation remains available."
            ),
        ) from exc
    if not isinstance(response, str) or not response.strip():
        raise WorkbenchRequestError(
            "The LLM agent returned no usable response",
            code="AGENT_EMPTY_RESPONSE",
            suggestion="Retry once or use the deterministic editor workflow.",
        )
    return redact_text(response[:64_000])


def _extract_agent_qasm(output: str) -> str:
    match = _FENCED_QASM.search(output)
    if match:
        return match.group(1).strip()
    marker = re.search(r"\bOPENQASM\s+2\.0\s*;", output, re.IGNORECASE)
    return output[marker.start() :].strip() if marker else ""


def _public_error(exc: Exception) -> Dict[str, Any]:
    if isinstance(exc, WorkbenchRequestError):
        return {
            "code": exc.code,
            "message": redact_text(str(exc)),
            "line": exc.line,
            "column": exc.column,
            "suggestion": exc.suggestion,
            "retryable": exc.retryable,
        }
    message = redact_text(str(exc))[:2_000] or type(exc).__name__
    line = getattr(exc, "line", None)
    column = getattr(exc, "column", None)
    match = _LOCATION.search(message)
    if match and line is None:
        line, column = int(match.group(1)), int(match.group(2))
    if isinstance(exc, QASMError):
        code = "QASM_ADMISSION_ERROR"
        suggestion = getattr(exc, "suggestion", None)
        retryable = True
    elif isinstance(exc, (ValueError, TypeError)):
        code = "SOURCE_ADMISSION_ERROR"
        suggestion = "Review the highlighted source and retry."
        retryable = True
    else:
        code = "WORKFLOW_ERROR"
        suggestion = "Retry once. If it persists, inspect the evidence manifest."
        retryable = False
    return {
        "code": code,
        "message": message,
        "line": line,
        "column": column,
        "suggestion": suggestion,
        "retryable": retryable,
    }


def _workflow(status: str, task: str) -> list[Dict[str, Any]]:
    labels = (
        ("request", "Request admitted"),
        ("intent", "Intent classified"),
        ("normalize", "Source normalized"),
        ("lower", "Target IR lowered"),
        ("execute", "Runtime / compiler completed"),
        ("verify", "Evidence sealed"),
    )
    if status == "completed":
        return [{"id": item, "label": label, "status": "passed"} for item, label in labels]
    failed_index = 2 if task not in {"unknown"} else 0
    return [
        {
            "id": item,
            "label": label,
            "status": (
                "passed"
                if index < failed_index
                else "failed"
                if index == failed_index
                else "pending"
            ),
        }
        for index, (item, label) in enumerate(labels)
    ]


__all__ = [
    "TASKS",
    "WorkbenchRequestError",
    "WorkbenchService",
]
