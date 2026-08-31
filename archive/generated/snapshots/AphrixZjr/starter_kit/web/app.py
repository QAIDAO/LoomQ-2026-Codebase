"""Deterministic application service for the LoomQ guided L2 experience.

The web experience deliberately keeps model prose out of state transitions.
OpenQASM parsing, simulation and backend facts remain deterministic and work
without network credentials.
"""

from __future__ import annotations

import copy
import difflib
import functools
import json
import os
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from l1_braket import _load_sdk as _load_braket_sdk, run_braket
from evaluator import validate_schema
from l1_originq import _load_sdk as _load_originq_sdk, run_originq
from l1_reference import distribution
from l1_spinq import _load_sdk as _load_spinq_sdk, run_spinq
from loomq_l1 import Circuit, QASMError, emit_spinq, normalize_counts, parse_qasm
from loomq_l2 import _circuit_semantic_diagnostic, _target_spec
from llm_client import chat_completion


BELL_QASM = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[2];
creg c[2];
"""
STAGES = ("goal", "h", "cx", "measurement", "prediction", "validation", "run", "explore")
STAGE_LABELS = ("明确目标", "加入 H", "建立关联", "加入测量", "先做预测", "三层验证", "运行实验", "继续探索")
GUIDES = {
    "goal": ("先把目标说清楚", "我们要制备 Bell 态，并观察 00 与 11 两种相关结果。", "确定 Bell 实验"),
    "h": ("让第一条线路进入叠加", "H（Hadamard）门创建可产生 0 或 1 的量子叠加；它不是普通随机数。", "添加 H 门"),
    "cx": ("把两条线路关联起来", "CX（受控非门）在控制位为 1 时翻转目标位，与 H 共同构成 Bell 电路。", "添加 CX 门"),
    "measurement": ("把量子结果读成经典位", "测量把量子态映射为经典位；这里同时测量两条线路。", "添加测量"),
    "prediction": ("运行前先做预测", "预测用于形成可比较的预期，不计分，也没有答错。", "记录预测"),
    "validation": ("检查电路是否支持目标", "语法、结构和实验目标是三个不同层次的证据。", "验证电路"),
    "run": ("在本地模拟器运行", "运行使用当前所选的本地执行器；具体计数方法与模拟边界会随结果说明。", "运行 1024 shots"),
    "explore": ("用结果提出下一个问题", "比较删除 CX 或改变测量基后的结果，比重复一次更有信息。", "尝试删除 CX"),
}
GUIDE_PRESETS = {
    "goal": "请开始 Bell 引导：设定制备两比特 Bell 态并比较 Z 基测量结果的实验目标。",
    "h": "请继续 Bell 引导：在 q[0] 上加入 H 门建立叠加。",
    "cx": "请继续 Bell 引导：加入从 q[0] 到 q[1] 的 CX 门建立关联。",
    "measurement": "请继续 Bell 引导：将 q[0]、q[1] 分别测量到 c[0]、c[1]。",
    "prediction": "请继续 Bell 引导：记录运行前预测，00 和 11 将大致各占一半。",
    "validation": "请继续 Bell 引导：验证当前电路的语法、结构和测量完整性。",
    "run": "请继续 Bell 引导：在当前所选后端运行 1024 shots。",
    "explore": "请完成 Bell 引导：删除 CX 门，保留其他内容，便于与 Bell 结果对比。",
}
GUIDE_FALLBACK_REPLIES = {
    "goal": "实验目标已设为制备两比特 Bell 态，并比较 Z 基测量中的 00 与 11。",
    "h": "已在 q[0] 上加入 H 门；它先建立叠加，为后续关联两条线路做准备。",
    "cx": "已加入从 q[0] 到 q[1] 的 CX 门；它与 H 门共同形成 Bell 电路。",
    "measurement": "已把 q[0]、q[1] 分别测量到 c[0]、c[1]，保留完整读出映射。",
    "prediction": "已记录运行前预测：00 和 11 将大致各占一半；预测本身不计分。",
    "validation": "已运行本地验证；请在验证视图核对语法、结构、测量映射和目标一致性。",
    "run": "已在当前所选本地执行器运行 1024 shots；计数方法和模拟边界以结果区为准。",
    "explore": "已删除 CX 并保留其他内容；可重新验证和运行，与 Bell 结果作对照。",
}
WEB_BACKEND_ID = "loomq_reference_simulator"
WEB_BACKEND_NAME = "LoomQ 内置状态向量参考模拟器"
LOCAL_BACKENDS = {
    "spinq_taurus_simulator": ("spinq", run_spinq, _load_spinq_sdk),
    "originq_local_simulator": ("originq", run_originq, _load_originq_sdk),
    "braket_local_simulator": ("braket", run_braket, _load_braket_sdk),
}
HARDWARE_EVIDENCE_ROOT = (
    Path(__file__).resolve().parents[1] / "evidence" / "files" / "hardware"
)
ARCHIVED_HARDWARE_SUMMARIES = {
    ("spinq", "bell"): {
        "provider_label": "SpinQ",
        "filename": "spinq-formal-bell-S-260811-0004-summary.json",
        "backend": "spinq-cloud-hardware",
        "job_id": "S-260811-0004",
        "circuit": "bell",
        "mode": "formal",
        "shots": 8192,
        "width": 2,
        "meta_identity": {
            "provider": "SpinQ Cloud",
            "device_code": "triangulum_vp",
        },
    },
    ("spinq", "ghz3"): {
        "provider_label": "SpinQ",
        "filename": "spinq-formal-ghz3-S-260811-0005-summary.json",
        "backend": "spinq-cloud-hardware",
        "job_id": "S-260811-0005",
        "circuit": "ghz3",
        "mode": "formal",
        "shots": 8192,
        "width": 3,
        "meta_identity": {
            "provider": "SpinQ Cloud",
            "device_code": "triangulum_vp",
        },
    },
    ("originq", "bell"): {
        "provider_label": "OriginQ",
        "filename": "originq-bell-21E79A08CED67A08B9FFB8DC109DABD8-summary.json",
        "backend": "originq-qcloud-WK_C180",
        "job_id": "21E79A08CED67A08B9FFB8DC109DABD8",
        "circuit": "bell",
        "shots": 8192,
        "width": 2,
        # These legacy summaries predate a top-level mode field.  Exact file,
        # job, backend, task-name and provider identity bind the formal task.
        "meta_identity": {
            "provider": "Origin Quantum",
            "task_name": "LoomQ-L1-bell",
            "device_id": "WK_C180",
        },
    },
    ("originq", "ghz3"): {
        "provider_label": "OriginQ",
        "filename": "originq-ghz3-5F5EB24ADDB266E77E8A52A478D8AAF2-summary.json",
        "backend": "originq-qcloud-WK_C180",
        "job_id": "5F5EB24ADDB266E77E8A52A478D8AAF2",
        "circuit": "ghz3",
        "shots": 8192,
        "width": 3,
        "meta_identity": {
            "provider": "Origin Quantum",
            "task_name": "LoomQ-L1-ghz3",
            "device_id": "WK_C180",
        },
    },
}


def _validated_archived_summary(
    path: Path, identity: Dict[str, Any]
) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    try:
        schema_valid, schema_reason = validate_schema(value)
    except (AttributeError, TypeError) as exc:
        raise ValueError("invalid competition schema") from exc
    if not schema_valid:
        raise ValueError("invalid competition schema: " + schema_reason)

    for field in ("backend", "job_id", "timestamp", "circuit"):
        if type(value.get(field)) is not str or not value[field]:
            raise ValueError("invalid summary string field: " + field)
    for field in ("backend", "job_id", "circuit", "shots"):
        if value[field] != identity[field]:
            raise ValueError("summary does not match allowlisted " + field)
    expected_mode = identity.get("mode")
    if expected_mode is not None and (
        type(value.get("mode")) is not str or value["mode"] != expected_mode
    ):
        raise ValueError("summary is not an allowlisted formal task")
    if expected_mode is None and "mode" in value and (
        type(value["mode"]) is not str or value["mode"] != "formal"
    ):
        raise ValueError("legacy formal summary has a contradictory mode")

    counts = value["counts"]
    width = identity["width"]
    if not counts or any(
        type(key) is not str
        or len(key) != width
        or not key
        or set(key) - {"0", "1"}
        for key in counts
    ):
        raise ValueError("summary counts do not have the exact circuit width")

    meta = value.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("summary meta is missing")
    for field, expected in identity["meta_identity"].items():
        if type(meta.get(field)) is not str or meta[field] != expected:
            raise ValueError("summary does not match allowlisted meta identity")
    return value


def archived_hardware_evidence() -> Dict[str, Any]:
    """Load committed formal Bell/GHZ summaries for read-only comparison.

    The endpoint never talks to a provider.  It reads exactly four allowlisted
    formal-task files, runs the public competition schema first, then verifies
    task identity and exact binary-key width.  It never discovers candidates by
    globbing or choosing the file with the largest shot count.
    """

    provider_labels = {"spinq": "SpinQ", "originq": "OriginQ"}
    circuit_specs = {
        "bell": {"label": "Bell", "support": ["00", "11"]},
        "ghz3": {"label": "GHZ-3", "support": ["000", "111"]},
    }
    selected: Dict[Tuple[str, str], Tuple[Path, Dict[str, Any]]] = {}
    rejected: List[str] = []
    for key, identity in ARCHIVED_HARDWARE_SUMMARIES.items():
        provider, _circuit_id = key
        path = HARDWARE_EVIDENCE_ROOT / provider / identity["filename"]
        if not path.is_file():
            continue
        try:
            selected[key] = (path, _validated_archived_summary(path, identity))
        except (
            AttributeError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            rejected.append(path.name)

    circuits: List[Dict[str, Any]] = []
    missing: List[str] = []
    for circuit_id, spec in circuit_specs.items():
        actual: List[Dict[str, Any]] = []
        for provider, label in provider_labels.items():
            item = selected.get((provider, circuit_id))
            if item is None:
                missing.append("%s/%s" % (provider, circuit_id))
                continue
            path, value = item
            support_count = sum(value["counts"].get(bits, 0) for bits in spec["support"])
            ordered = sorted(value["counts"].items(), key=lambda pair: (-pair[1], pair[0]))
            actual.append({
                "provider": label,
                "kind": "archived_hardware",
                "backend": value["backend"],
                "job_id": str(value["job_id"]),
                "timestamp": value["timestamp"],
                "shots": value["shots"],
                "counts": value["counts"],
                "support_probability": round(support_count / value["shots"], 9),
                "leakage_probability": round(1.0 - support_count / value["shots"], 9),
                "dominant_states": [bits for bits, _ in ordered[:2]],
                "evidence_file": str(path.relative_to(HARDWARE_EVIDENCE_ROOT.parent.parent)).replace("\\", "/"),
            })
        ideal_shots = max((item["shots"] for item in actual), default=8192)
        ideal_counts = {
            spec["support"][0]: ideal_shots // 2,
            spec["support"][1]: ideal_shots - ideal_shots // 2,
        }
        circuits.append({
            "id": circuit_id,
            "label": spec["label"],
            "expected_support": spec["support"],
            "series": [{
                "provider": "Ideal",
                "kind": "ideal_reference",
                "backend": "理论参考",
                "job_id": None,
                "timestamp": None,
                "shots": ideal_shots,
                "counts": ideal_counts,
                "support_probability": 1.0,
                "leakage_probability": 0.0,
                "dominant_states": spec["support"],
                "evidence_file": None,
            }] + actual,
        })
    return {
        "archived": True,
        "complete": not missing and not rejected,
        "live_submission": False,
        "notice": "只读复盘：数据来自已提交到仓库的真机摘要；不会连接云平台或创建新任务。",
        "boundary": "计数只描述这些设备在对应任务和运行条件下的 Z 基统计；不能单独认证纠缠或代表设备当前状态。",
        "circuits": circuits,
        "missing": missing,
        "rejected": rejected,
    }


def _bell_qasm(stage_index: int) -> str:
    lines = BELL_QASM.rstrip().splitlines()
    if stage_index >= 2:
        lines.append("h q[0];")
    if stage_index >= 3:
        lines.append("cx q[0],q[1];")
    if stage_index >= 4:
        lines.extend(("measure q[0] -> c[0];", "measure q[1] -> c[1];"))
    return "\n".join(lines) + "\n"


def _circuit_ir(circuit: Circuit) -> Dict[str, Any]:
    qubit_offsets: Dict[str, int] = {}
    classical_offsets: Dict[str, int] = {}
    qubit_labels: List[str] = []
    classical_labels: List[str] = []
    offset = 0
    for name, size in circuit.qregs:
        qubit_offsets[name] = offset
        qubit_labels.extend("%s[%d]" % (name, index) for index in range(size))
        offset += size
    offset = 0
    for name, size in circuit.cregs:
        classical_offsets[name] = offset
        classical_labels.extend("%s[%d]" % (name, index) for index in range(size))
        offset += size

    def qubit_index(bit: Any) -> int:
        return qubit_offsets[bit.register] + bit.index

    def classical_index(bit: Any) -> int:
        return classical_offsets[bit.register] + bit.index

    return {
        "qubits": circuit.qubit_count,
        "classical_bits": circuit.classical_count,
        "qubit_labels": qubit_labels,
        "classical_labels": classical_labels,
        "gates": [
            {
                "name": gate.name.upper(),
                "qubits": [qubit_index(bit) for bit in gate.qubits],
                "qubit_labels": ["%s[%d]" % (bit.register, bit.index) for bit in gate.qubits],
            }
            for gate in circuit.gates
        ],
        "measurements": [
            {
                "qubit": qubit_index(item.qubit),
                "classical": classical_index(item.classical),
                "qubit_label": "%s[%d]" % (item.qubit.register, item.qubit.index),
                "classical_label": "%s[%d]" % (item.classical.register, item.classical.index),
            }
            for item in circuit.measurements
        ],
    }


def _description(circuit: Circuit) -> str:
    qubit_labels = [
        "%s[%d]" % (name, index)
        for name, size in circuit.qregs for index in range(size)
    ]
    parts = ["%d 条量子线路：%s。" % (circuit.qubit_count, "、".join(qubit_labels))]
    for gate in circuit.gates:
        labels = ["%s[%d]" % (item.register, item.index) for item in gate.qubits]
        if gate.name == "h":
            parts.append("H 门作用于 %s，建立叠加。" % labels[0])
        elif gate.name == "cx":
            parts.append("CX 门以 %s 为控制、%s 为目标，建立关联。" % (labels[0], labels[1]))
        else:
            parts.append("%s 门作用于 %s。" % (gate.name.upper(), "、".join(labels)))
    if circuit.measurements:
        parts.append("测量将%s。" % "、".join(
            " %s[%d] 写入 %s[%d]" % (
                item.qubit.register, item.qubit.index,
                item.classical.register, item.classical.index,
            ) for item in circuit.measurements
        ))
    return "".join(parts)


def _validation(circuit: Circuit, goal: str) -> Dict[str, Any]:
    syntax = {"status": "pass", "label": "语法有效", "detail": "OpenQASM 2.0 可解析"}
    definitions = {
        "status": "pass", "label": "寄存器定义有效",
        "detail": "已定义 %d 个量子位和 %d 个经典位" % (circuit.qubit_count, circuit.classical_count),
    }
    gates = {
        "status": "pass" if circuit.gates else "warn",
        "label": "量子门已定义" if circuit.gates else "未包含量子门",
        "detail": "共 %d 个量子门，引用的量子位均有效" % len(circuit.gates) if circuit.gates else "空操作电路语法有效；是否符合实验意图需由用户判断",
    }
    measurement_sources = [
        (item.qubit.register, item.qubit.index) for item in circuit.measurements
    ]
    measurement_destinations = [
        (item.classical.register, item.classical.index) for item in circuit.measurements
    ]
    mapping_has_collision = (
        len(measurement_sources) != len(set(measurement_sources))
        or len(measurement_destinations) != len(set(measurement_destinations))
    )
    if not circuit.measurements:
        measurements = {
            "status": "warn", "label": "未定义测量",
            "detail": "可以编辑和验证，但运行计数需要至少一个测量",
        }
    elif mapping_has_collision:
        measurements = {
            "status": "fail", "label": "测量映射存在覆盖",
            "detail": "同一量子位或经典位不能在工作台读出映射中重复使用",
        }
    else:
        measurements = {
            "status": "pass", "label": "测量映射有效",
            "detail": "共 %d 个互不覆盖的量子位到经典位映射" % len(circuit.measurements),
        }
    target_spec = _target_spec(goal) if goal else None
    if target_spec is None:
        target = {
            "status": "warn", "label": "当前未提供语义证明",
            "detail": "目标未映射到受控的 Bell/GHZ 语义 schema；以上仅为静态结构证据",
        }
    else:
        diagnostic = _circuit_semantic_diagnostic(circuit, target_spec)
        target = {
            "status": "pass" if diagnostic is None else "fail",
            "label": "目标一致" if diagnostic is None else "目标不一致",
            "detail": (
                "本地语义 oracle 已验证量子态与完整经典测量映射"
                if diagnostic is None else "本地语义检查未通过：%s" % diagnostic
            ),
        }
    return {
        "syntax": syntax, "definitions": definitions, "gates": gates,
        "measurements": measurements, "target": target,
        # Structural execution safety and target semantics are deliberately
        # separate.  A well-formed circuit that does not implement the current
        # Bell/GHZ goal can still be explored, but a lossy measurement mapping
        # must never reach an executor.
        "runnable": bool(circuit.measurements) and not mapping_has_collision,
        "target_supported": target["status"] != "fail",
    }


def _counts(qasm: str, shots: int) -> Dict[str, int]:
    probabilities = distribution(qasm)
    ordered = sorted(probabilities.items())
    raw = [(bits, probability * shots) for bits, probability in ordered]
    counts = {bits: int(value) for bits, value in raw}
    remaining = shots - sum(counts.values())
    for bits, value in sorted(raw, key=lambda item: (-(item[1] - int(item[1])), item[0]))[:remaining]:
        counts[bits] += 1
    return {bits: count for bits, count in counts.items() if count}


@dataclass
class ExperimentSession:
    session_id: str
    goal: str = ""
    goal_revision: int = 0
    circuit_revision: int = 1
    workbench_revision: int = 1
    guide_stage: int = 0
    guide_complete: bool = False
    state: str = "initial"
    qasm: str = BELL_QASM
    circuit_ir: Dict[str, Any] = field(default_factory=dict)
    circuit_description: str = "两条量子线路 q[0] 与 q[1]。"
    validation: Dict[str, Any] = field(default_factory=dict)
    backend_selection: str = WEB_BACKEND_ID
    result: Optional[Dict[str, Any]] = None
    prediction: Optional[str] = None
    notice: str = ""
    conversation: List[Dict[str, str]] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list, repr=False)
    future: List[Dict[str, Any]] = field(default_factory=list, repr=False)

    def public(self) -> Dict[str, Any]:
        value = asdict(self)
        value.pop("history", None)
        value.pop("future", None)
        stage = STAGES[self.guide_stage]
        title, body, action = GUIDES[stage]
        value["guide"] = {
            "stage": stage, "index": self.guide_stage + 1, "total": len(STAGES),
            "title": title, "body": body, "primary_action": action,
            "preset_instruction": GUIDE_PRESETS[stage], "complete": self.guide_complete,
        }
        value["stage_labels"] = list(STAGE_LABELS)
        value["can_undo"] = bool(self.history)
        value["can_redo"] = bool(self.future)
        return value

    def _snapshot(self) -> Dict[str, Any]:
        return {
            key: copy.deepcopy(value)
            for key, value in self.__dict__.items()
            if key not in ("history", "future", "workbench_revision")
        }

    def mutate(self) -> None:
        self.history.append(self._snapshot())
        self.future.clear()

    def restore(self, snapshot: Dict[str, Any]) -> None:
        history, future = self.history, self.future
        self.__dict__.update(copy.deepcopy(snapshot))
        self.history, self.future = history, future


def _session_locked(method: Callable[..., Any]) -> Callable[..., Any]:
    """Serialize reads and writes for one published experiment session."""

    @functools.wraps(method)
    def wrapped(self: "ExperimentStore", session_id: str, *args: Any, **kwargs: Any) -> Any:
        with self._session_lock(session_id):
            return method(self, session_id, *args, **kwargs)

    return wrapped


class ExperimentStore:
    def __init__(
        self,
        agent_transport: Optional[Callable[[List[Dict[str, str]]], Dict[str, Any]]] = None,
        backend_runners: Optional[Dict[str, Callable[[Circuit, int], Tuple[Any, str, str, Optional[Dict[str, Any]]]]]] = None,
        backend_probes: Optional[Dict[str, Callable[[], Any]]] = None,
    ) -> None:
        self.sessions: Dict[str, ExperimentSession] = {}
        self._registry_lock = threading.RLock()
        self._session_locks: Dict[str, threading.RLock] = {}
        self.runs: Dict[str, Dict[str, Any]] = {}
        self.pending_proposals: Dict[str, Dict[str, Any]] = {}
        self.agent_transport = agent_transport
        self.backend_runners = backend_runners or {
            backend_id: values[1] for backend_id, values in LOCAL_BACKENDS.items()
        }
        probes = backend_probes or {
            backend_id: values[2] for backend_id, values in LOCAL_BACKENDS.items()
        }
        self.backend_availability = self._probe_backends(probes)

    @staticmethod
    def _probe_backends(probes: Dict[str, Callable[[], Any]]) -> Dict[str, Dict[str, Any]]:
        availability: Dict[str, Dict[str, Any]] = {}
        for backend_id in LOCAL_BACKENDS:
            probe = probes.get(backend_id)
            if probe is None:
                availability[backend_id] = {"available": False, "reason": "Web 工作台未配置该本地执行器"}
                continue
            try:
                probe()
                availability[backend_id] = {"available": True, "reason": "本地 SDK 已连接，可直接执行"}
            except Exception as exc:
                detail = str(exc).strip() or exc.__class__.__name__
                availability[backend_id] = {
                    "available": False,
                    "reason": "本地 SDK 不可用：%s" % detail[:180],
                }
        return availability

    def create(self, mode: str = "bell", qasm: Optional[str] = None, goal: Optional[str] = None) -> Dict[str, Any]:
        session = ExperimentSession(session_id=str(uuid.uuid4()))
        if goal:
            session.goal = goal.strip()[:500]
            session.goal_revision = 1
        if mode == "qasm" and qasm is not None:
            self._set_qasm(session, qasm, push_history=False)
            session.guide_stage = 5
            syntax_status = session.validation.get("syntax", {}).get("status")
            if syntax_status == "fail":
                session.state = "invalid"
            elif session.validation.get("runnable"):
                session.state = "runnable"
            else:
                session.state = "draft"
        elif mode == "natural":
            target = _target_spec(goal or "")
            if target is not None and target.qubits <= 12:
                session.goal = goal or "制备三比特 GHZ 态并全部测量"
                lines = [
                    "OPENQASM 2.0;", 'include "qelib1.inc";',
                    "qreg q[%d];" % target.qubits,
                    "creg c[%d];" % target.qubits,
                    "h q[0];",
                ]
                lines.extend(
                    "cx q[0],q[%d];" % index for index in range(1, target.qubits)
                )
                lines.append("measure q -> c;")
                session.qasm = "\n".join(lines) + "\n"
                circuit = parse_qasm(session.qasm)
                session.circuit_ir, session.circuit_description = _circuit_ir(circuit), _description(circuit)
                session.validation = _validation(circuit, session.goal)
                session.guide_stage, session.state = 5, "runnable"
            else:
                session.notice = "目标已保留。受控 Bell/GHZ 本地生成支持 2–12 比特；其他目标可继续使用 QASM 工作台。"
        with self._registry_lock:
            self.sessions[session.session_id] = session
            self._session_locks[session.session_id] = threading.RLock()
        return session.public()

    def get(self, session_id: str) -> ExperimentSession:
        with self._registry_lock:
            try:
                return self.sessions[session_id]
            except KeyError as exc:
                raise KeyError("experiment not found") from exc

    def _session_lock(self, session_id: str) -> threading.RLock:
        with self._registry_lock:
            if session_id not in self.sessions:
                raise KeyError("experiment not found")
            return self._session_locks[session_id]

    @_session_locked
    def public(self, session_id: str) -> Dict[str, Any]:
        return self.get(session_id).public()

    @_session_locked
    def advance(
        self,
        session_id: str,
        prediction: Optional[str] = None,
        expected_revision: Optional[int] = None,
        expected_workbench_revision: Optional[int] = None,
        expected_stage: Optional[int] = None,
    ) -> Dict[str, Any]:
        session = self.get(session_id)
        if expected_revision is not None and expected_revision != session.circuit_revision:
            raise ConflictError("stale circuit revision")
        if (
            expected_workbench_revision is not None
            and expected_workbench_revision != session.workbench_revision
        ):
            raise ConflictError("stale workbench revision")
        if expected_stage is not None and expected_stage != session.guide_stage:
            raise ConflictError("stale Bell guide stage")

        original = copy.deepcopy(session.__dict__)
        try:
            session.mutate()
            stage = STAGES[session.guide_stage]
            if stage in ("goal", "h", "cx", "measurement"):
                if stage == "goal":
                    session.goal = "制备两比特 Bell 态，并在 Z 基测量中比较 00 与 11"
                    session.goal_revision += 1
                session.guide_stage += 1
                session.qasm = _bell_qasm(session.guide_stage)
                circuit = parse_qasm(session.qasm)
                session.circuit_ir = _circuit_ir(circuit)
                session.circuit_description = _description(circuit)
                session.circuit_revision += 1
                session.state = "draft"
                session.notice = "已由本地引导完成“%s”：%s" % (
                    GUIDES[stage][0], GUIDES[stage][1]
                )
            elif stage == "prediction":
                session.prediction = prediction or "00 与 11 大致各占一半"
                session.guide_stage += 1
                session.state = "draft"
                session.notice = "已由本地引导完成“%s”：%s" % (
                    GUIDES[stage][0], GUIDES[stage][1]
                )
            elif stage == "validation":
                circuit = parse_qasm(session.qasm)
                session.validation = _validation(circuit, session.goal)
                session.guide_stage += 1
                session.state = "runnable" if session.validation["runnable"] else "invalid"
                session.notice = "已由本地引导完成“%s”：请查看验证证据。" % GUIDES[stage][0]
            elif stage == "run":
                self.run(session_id)
                session.guide_stage += 1
                session.state = "completed"
                session.notice = "已由本地引导完成“%s”：%s" % (
                    GUIDES[stage][0], session.result["counting_method"]
                )
            else:
                lines = [line for line in session.qasm.splitlines() if not line.strip().lower().startswith("cx ")]
                session.qasm = "\n".join(lines) + "\n"
                circuit = parse_qasm(session.qasm)
                session.circuit_ir, session.circuit_description = _circuit_ir(circuit), _description(circuit)
                session.circuit_revision += 1
                session.state = "draft"
                session.guide_complete = True
                session.notice = "已删除 CX。再次验证并运行，可与 Bell 结果比较。可用“撤销”恢复。"
            session.workbench_revision += 1
            return session.public()
        except Exception:
            session.__dict__.clear()
            session.__dict__.update(original)
            raise

    def _set_qasm(self, session: ExperimentSession, qasm: str, push_history: bool = True) -> None:
        if not isinstance(qasm, str) or len(qasm) > 100_000:
            raise ValueError("QASM must be text within 100000 characters")
        if push_history:
            session.mutate()
        session.qasm = qasm
        session.circuit_revision += 1
        if push_history:
            session.workbench_revision += 1
        try:
            circuit = parse_qasm(qasm)
        except QASMError as exc:
            session.state = "invalid"
            session.validation = {"syntax": {"status": "fail", "label": "语法错误", "detail": str(exc)}, "runnable": False}
            session.notice = "图形仍保留最后一次有效电路；请预览修复或撤销。"
            return
        session.circuit_ir, session.circuit_description = _circuit_ir(circuit), _description(circuit)
        session.validation = _validation(circuit, session.goal)
        session.state = "draft"
        session.notice = "QASM 已同步到电路。"

    @_session_locked
    def update_qasm(self, session_id: str, qasm: str, expected_revision: Optional[int] = None) -> Dict[str, Any]:
        session = self.get(session_id)
        if expected_revision is not None and expected_revision != session.circuit_revision:
            raise ConflictError("stale circuit revision")
        self._set_qasm(session, qasm)
        return session.public()

    @_session_locked
    def update_goal(self, session_id: str, goal: str) -> Dict[str, Any]:
        session = self.get(session_id)
        if not isinstance(goal, str) or not goal.strip():
            raise ValueError("goal must be non-empty text")
        session.mutate()
        session.goal, session.goal_revision = goal.strip()[:500], session.goal_revision + 1
        session.workbench_revision += 1
        session.notice = "目标已更新；请重新验证目标一致性。"
        return session.public()

    @_session_locked
    def validate(self, session_id: str) -> Dict[str, Any]:
        session = self.get(session_id)
        try:
            circuit = parse_qasm(session.qasm)
            session.validation = _validation(circuit, session.goal)
            session.state = "runnable" if session.validation["runnable"] else "invalid"
        except QASMError as exc:
            session.validation = {"syntax": {"status": "fail", "label": "语法错误", "detail": str(exc)}, "runnable": False}
            session.state = "invalid"
        session.workbench_revision += 1
        return session.public()

    @_session_locked
    def repair(self, session_id: str, apply: bool = False) -> Dict[str, Any]:
        session = self.get(session_id)
        original = session.qasm
        repaired = re.sub(r"(?m)^(OPENQASM\s+2\.0|include\s+\"qelib1\.inc\"|(?:qreg|creg)\s+\w+\[\d+\]|(?:h|x|cx|measure)\s+[^;\n]+)$", r"\1;", original)
        try:
            parse_qasm(repaired)
            safe = True
        except QASMError:
            repaired, safe = original, False
        diff = "\n".join(difflib.unified_diff(original.splitlines(), repaired.splitlines(), fromfile="当前 QASM", tofile="安全修复", lineterm=""))
        proposal = {"kind": "syntax", "safe": safe and repaired != original, "diff": diff or "没有可自动应用的安全语法修复", "qasm": repaired}
        if apply and proposal["safe"]:
            self._set_qasm(session, repaired)
            session.notice = "已应用安全语法修复并重新验证；可用“撤销”恢复。"
            proposal["session"] = session.public()
        return proposal

    @_session_locked
    def recommendations(self, session_id: str) -> Dict[str, Any]:
        session = self.get(session_id)
        path = Path(__file__).resolve().parents[1] / "backend_capabilities.json"
        items = json.loads(path.read_text(encoding="utf-8"))["backends"]
        results = [{
            "id": WEB_BACKEND_ID, "platform": "loomq", "name": WEB_BACKEND_NAME,
            "kind": "simulator", "max_qubits": 24, "queue": "none", "cost": "free",
            "requires_account": False, "notes": "Web 工作台内置执行器",
            "available": True, "selectable": True, "recommended": True,
            "reason": "当前 Web 工作台实际连接的本地执行器",
        }] + [self._backend_recommendation(item) for item in items]
        return {"session_id": session.session_id, "circuit_revision": session.circuit_revision, "selected": session.backend_selection, "items": results}

    def _backend_recommendation(self, item: Dict[str, Any]) -> Dict[str, Any]:
        status = self.backend_availability.get(item["id"])
        available = bool(status and status["available"])
        if status is not None:
            reason = status["reason"]
        elif item["requires_account"]:
            reason = "需要账号、网络或云端排队；尚未连接到 Web 工作台"
        else:
            reason = "能力表中存在，但尚未连接到 Web 工作台执行器"
        return {
            **item,
            "available": available,
            "selectable": available,
            "recommended": False,
            "reason": reason,
        }

    @_session_locked
    def select_backend(self, session_id: str, backend_id: str) -> Dict[str, Any]:
        session = self.get(session_id)
        selectable = {item["id"] for item in self.recommendations(session_id)["items"] if item["selectable"]}
        if backend_id not in selectable:
            raise ValueError("该后端尚未连接到 Web 工作台执行器")
        session.mutate()
        session.backend_selection = backend_id
        session.workbench_revision += 1
        selected = next(item for item in self.recommendations(session_id)["items"] if item["id"] == backend_id)
        session.notice = "运行后端已选择：%s。" % selected["name"]
        return session.public()

    def _agent_content(self, response: Dict[str, Any]) -> str:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Agent 服务返回了无效响应") from exc
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Agent 服务返回了空响应")
        return content.strip()

    def _agent_message(self, response: Dict[str, Any]) -> Dict[str, Any]:
        try:
            message = response["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Agent 服务返回了无效响应") from exc
        if not isinstance(message, dict):
            raise RuntimeError("Agent 服务返回了无效响应")
        return message

    def _agent_tools(self) -> List[Dict[str, Any]]:
        return [
            {"type": "function", "function": {"name": "advance_bell_guide", "description": "仅执行当前 Bell 引导阶段的确定性工作台操作", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
            {"type": "function", "function": {"name": "run_experiment", "description": "在当前已同步 QASM 和所选 Web 执行器上运行实验", "parameters": {"type": "object", "properties": {"shots": {"type": "integer", "minimum": 1, "maximum": 100000}}, "additionalProperties": False}}},
            {"type": "function", "function": {"name": "validate_circuit", "description": "验证当前已同步 QASM 的语法、寄存器、量子门和测量", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
            {"type": "function", "function": {"name": "set_goal", "description": "设置当前实验目标", "parameters": {"type": "object", "properties": {"goal": {"type": "string", "minLength": 1, "maxLength": 500}}, "required": ["goal"], "additionalProperties": False}}},
            {"type": "function", "function": {"name": "undo_workbench", "description": "撤销最近一次工作台修改", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
            {"type": "function", "function": {"name": "redo_workbench", "description": "重做最近一次被撤销的工作台修改", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
        ]

    def _bell_guide_request(self, session: ExperimentSession, prompt: str) -> bool:
        return not session.guide_complete and prompt.strip() == GUIDE_PRESETS[STAGES[session.guide_stage]]

    @_session_locked
    def _guide_tool_error_response(
        self, session_id: str, model_attempted: bool,
    ) -> Dict[str, Any]:
        session = self.get(session_id)
        reply = (
            "【本地阶段操作未完成】当前确定性阶段工具执行失败，实验没有继续推进；"
            "请检查当前工作台或本地执行器后重试。本回复由本地工作台生成。"
        )
        session.conversation.append({"role": "assistant", "content": reply})
        return {
            "status": "error", "source": "local", "model": None,
            "model_attempted": model_attempted, "model_generated": False,
            "error_kind": "local_tool_error", "understanding": "",
            "response": reply, "proposal": None, "tools_used": [],
            "tools_attempted": ["advance_bell_guide"],
            "conversation": copy.deepcopy(session.conversation[-12:]),
            "session": session.public(),
        }

    @_session_locked
    def _preset_guide_fallback(
        self,
        session_id: str,
        starting_stage: int,
        expected_circuit_revision: int,
        expected_workbench_revision: int,
        reason: str,
        model_attempted: bool,
        tool_already_completed: bool = False,
    ) -> Dict[str, Any]:
        """Return a prewritten reply, advancing only when no tool ran yet."""
        session = self.get(session_id)
        stage = STAGES[starting_stage]
        if tool_already_completed:
            current = session.public()
        else:
            try:
                current = self.advance(
                    session_id,
                    expected_revision=expected_circuit_revision,
                    expected_workbench_revision=expected_workbench_revision,
                    expected_stage=starting_stage,
                )
            except ConflictError:
                raise
            except Exception:
                return self._guide_tool_error_response(session_id, model_attempted)
        suffix = (
            " Bell 引导已完成，可验证并比较探索结果。"
            if current["guide"]["complete"]
            else " 下一阶段仍需先点击“填入本阶段指令”，再从 Agent 对话框发送。"
        )
        label = "非模型生成" if model_attempted else "未调用模型"
        availability = "模型连接或响应未完成；" if model_attempted else "Agent 当前未配置；"
        reply = "【本地预置回复｜%s】%s%s%s" % (
            label, availability, GUIDE_FALLBACK_REPLIES[stage], suffix,
        )
        session.conversation.append({"role": "assistant", "content": reply})
        current = session.public()
        return {
            "status": "fallback", "source": "preset", "model": None,
            "model_attempted": model_attempted, "model_generated": False,
            "fallback_reason": reason, "understanding": "", "response": reply,
            "proposal": None, "tools_used": ["advance_bell_guide"],
            "conversation": copy.deepcopy(session.conversation[-12:]),
            "session": current,
        }

    def _allowed_agent_tool_names(self, prompt: str) -> set[str]:
        lowered = prompt.lower()
        allowed: set[str] = set()
        if re.search(r"请.*运行|帮我.*运行|运行一下|开始运行|执行实验|run\s+(?:it|the|\d)|execute\s+the\s+experiment", lowered):
            allowed.add("run_experiment")
        if re.search(r"请.*验证|帮我.*验证|验证一下|检查电路|validate\s+(?:it|the|current)|check\s+the\s+circuit", lowered):
            allowed.add("validate_circuit")
        if re.search(r"(?:修改|改成|设置|更新).*(?:目标|goal)|(?:目标|goal).*(?:修改|改成|设置|更新)|set\s+(?:the\s+)?goal", lowered):
            allowed.add("set_goal")
        if re.search(r"撤销|undo", lowered):
            allowed.add("undo_workbench")
        if re.search(r"重做|redo", lowered):
            allowed.add("redo_workbench")
        return allowed

    def _execute_agent_tool(
        self,
        session_id: str,
        name: str,
        arguments: Any,
        request_expectation: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ValueError("工具参数必须是对象")
        if request_expectation is None:
            raise ValueError("Agent 工具缺少请求快照")
        with self._session_lock(session_id):
            current = self.get(session_id)
            if current.workbench_revision != request_expectation["workbench_revision"]:
                raise ConflictError("stale Agent tool request")
            if name == "run_experiment":
                session = self.run(session_id, arguments.get("shots", 1024))
                result = {"ok": True, "state": session["state"], "result": session["result"]}
            elif name == "validate_circuit":
                session = self.validate(session_id)
                result = {"ok": True, "state": session["state"], "validation": session["validation"]}
            elif name == "set_goal":
                session = self.update_goal(session_id, arguments.get("goal", ""))
                result = {"ok": True, "goal": session["goal"], "goal_revision": session["goal_revision"]}
            elif name == "undo_workbench":
                session = self.undo(session_id)
                result = {"ok": True, "state": session["state"], "circuit_revision": session["circuit_revision"]}
            elif name == "redo_workbench":
                session = self.redo(session_id)
                result = {"ok": True, "state": session["state"], "circuit_revision": session["circuit_revision"]}
            elif name == "advance_bell_guide":
                session = self.advance(
                    session_id,
                    expected_revision=request_expectation["circuit_revision"],
                    expected_workbench_revision=request_expectation["workbench_revision"],
                    expected_stage=request_expectation["stage"],
                )
                result = {
                    "ok": True, "stage": session["guide"]["stage"],
                    "guide_complete": session["guide"]["complete"], "state": session["state"],
                    "goal": session["goal"], "qasm": session["qasm"],
                    "validation": session["validation"], "result": session["result"],
                }
            else:
                raise ValueError("未知的 Agent 工具")
            current = self.get(session_id)
            request_expectation.update({
                "stage": current.guide_stage,
                "circuit_revision": current.circuit_revision,
                "workbench_revision": current.workbench_revision,
            })
            return result

    def _agent_object(self, content: str) -> Dict[str, Any]:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I)
        try:
            value = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Agent 未返回结构化响应") from exc
        if not isinstance(value, dict):
            raise RuntimeError("Agent 未返回结构化响应")
        return value

    def _requested_proposal_kind(self, prompt: str) -> Optional[str]:
        """Conservatively authorize state-changing proposals from explicit user wording."""
        lowered = prompt.lower()
        action = re.search(r"选择|推荐|切换|修改|改成|设置|生成|创建|构建|制备|添加|加入|删除|移除|去掉|修复|choose|select|recommend|switch|change|set|generate|create|build|add|remove|delete|fix|repair", lowered)
        if not action:
            return None
        if re.search(r"后端|backend|qpu|模拟器|simulator", lowered):
            return "backend"
        if re.search(r"目标|goal|objective", lowered):
            return None
        if re.search(r"qasm|电路|circuit|bell|ghz|量子态", lowered):
            return "qasm"
        return None

    def agent_turn(self, session_id: str, prompt: str) -> Dict[str, Any]:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Agent 输入不能为空")
        if len(prompt) > 4_000:
            raise ValueError("Agent 输入超过长度限制")
        prompt = prompt.strip()
        with self._session_lock(session_id):
            session = self.get(session_id)
            session.conversation.append({"role": "user", "content": prompt})
            guide_request = self._bell_guide_request(session, prompt)
            guide_expectation = {
                "stage": session.guide_stage,
                "circuit_revision": session.circuit_revision,
                "workbench_revision": session.workbench_revision,
            }
            snapshot_session = session.public()
            history = copy.deepcopy(session.conversation[-10:-1])
            capabilities = self.recommendations(session_id)["items"]
        guide_stage_before = guide_expectation["stage"]
        configured = all(os.environ.get(name) for name in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL"))
        if self.agent_transport is None and not configured:
            if guide_request:
                return self._preset_guide_fallback(
                    session_id,
                    guide_stage_before,
                    guide_expectation["circuit_revision"],
                    guide_expectation["workbench_revision"],
                    "not_configured",
                    model_attempted=False,
                )
            reply = "Agent 尚未配置。当前电路、QASM、验证和本地运行仍可直接使用；配置 LOOMQ_LLM_* 后可在这里获得模型理解与修改提案。"
            with self._session_lock(session_id):
                session = self.get(session_id)
                session.conversation.append({"role": "assistant", "content": reply})
                conversation = copy.deepcopy(session.conversation[-12:])
            return {
                "status": "unavailable", "source": "none", "model": None,
                "model_attempted": False, "model_generated": False,
                "understanding": "未调用模型", "response": reply,
                "proposal": None, "conversation": conversation,
            }

        requested_kind = None if guide_request else self._requested_proposal_kind(prompt)
        allowed_tool_names = {"advance_bell_guide"} if guide_request else (self._allowed_agent_tool_names(prompt) if requested_kind is None else set())
        answer_system = """你是 LoomQ 工作台中的通用量子实验 Agent。直接以自然语言回答用户，可以回答量子概念、当前电路、QASM、验证、运行结果、后端和工作流等任意一般问题。不要输出 JSON 包装，不要生成修改提案，也不要把问题改写成项目任务。优先使用紧邻用户消息的最新工作台快照；对话历史只用于理解上下文，若与快照冲突必须以快照为准。区分确定事实、模型解释和尚未验证的推断。用户明确要求运行、验证、设置目标、撤销或重做时，直接调用相应工具；不要只口头声称可以代劳。不要在未获用户明确授权时调用会改变工作台的工具。"""
        action_system = """你是 LoomQ 工作台中的量子实验 Agent。本轮用户明确要求改变实验状态。只返回一个 JSON 对象：
{"understanding":"你对操作意图的简洁理解","response":"说明待确认操作","proposal":null}
proposal 必须且只能匹配系统指定的本轮提案类型：
{"kind":"qasm","qasm":"完整 OpenQASM 2.0","summary":"修改摘要"}
{"kind":"backend","backend_id":"能力表中的规范 ID","summary":"选择理由"}
不要声称已应用修改；提案必须等待用户确认。QASM 必须完整且可解析，后端 ID 必须来自能力表。始终以紧邻本轮用户消息的当前工作台快照为准。"""
        guide_system = """你是 LoomQ Bell 引导 Agent。用户发送的是当前阶段由界面提供的预设指令。你必须首先调用唯一提供的 advance_bell_guide 工具，且不得生成 QASM 或后端提案、不得调用其他工具、不得声称执行了工具尚未完成的操作。工具成功后，用简洁中文说明本阶段实际改变、它在 Bell 实验中的作用，并提示用户下一阶段再次点击“填入本阶段指令”后发送；最终阶段则建议用户验证并比较删除 CX 前后的结果。所有事实必须以工具结果为准。"""
        system = guide_system if guide_request else (answer_system if requested_kind is None else action_system)
        snapshot = "当前工作台实时快照（revision %d）：\n目标：%s\n执行状态：%s\n所选后端：%s\n电路描述：%s\nQASM：\n%s\n验证状态：\n%s\n最近运行结果：\n%s\n后端能力表：\n%s\n本轮提案权限：%s" % (
            snapshot_session["circuit_revision"], snapshot_session["goal"] or "未设定",
            snapshot_session["state"], snapshot_session["backend_selection"],
            snapshot_session["circuit_description"], snapshot_session["qasm"],
            json.dumps(snapshot_session["validation"], ensure_ascii=False),
            json.dumps(snapshot_session["result"], ensure_ascii=False) if snapshot_session["result"] else "尚未运行",
            json.dumps(capabilities, ensure_ascii=False), "Bell 引导阶段工具" if guide_request else (requested_kind or "无；这是通用自由文本问答"),
        )
        messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
        messages.extend(history)
        messages.extend([{"role": "system", "content": snapshot}, {"role": "user", "content": prompt}])
        available_tools = [item for item in self._agent_tools() if item["function"]["name"] in allowed_tool_names]

        def invoke(
            items: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None,
            tool_choice: Any = "auto",
        ) -> Dict[str, Any]:
            if self.agent_transport is not None:
                return self.agent_transport(items)
            extra = {"tools": tools, "tool_choice": tool_choice} if tools else {}
            return chat_completion(items, transport_timeout=30, **extra)
        guide_tool_completed = False
        try:
            forced_choice = {"type": "function", "function": {"name": "advance_bell_guide"}} if guide_request else "auto"
            response = invoke(messages, available_tools, forced_choice)
            tool_names: List[str] = []
            if requested_kind is None:
                message = self._agent_message(response)
                tool_calls = message.get("tool_calls") or []
                if tool_calls:
                    if not isinstance(tool_calls, list) or len(tool_calls) > 5:
                        raise RuntimeError("Agent 工具调用数量无效")
                    if guide_request and (
                        len(tool_calls) != 1
                        or tool_calls[0].get("function", {}).get("name") != "advance_bell_guide"
                    ):
                        raise RuntimeError("Bell 引导 Agent 必须且只能调用当前阶段工具一次")
                    followup: List[Dict[str, Any]] = list(messages)
                    followup.append({"role": "assistant", "content": message.get("content"), "tool_calls": tool_calls})
                    for call in tool_calls:
                        try:
                            function = call["function"]
                            name = function["name"]
                            if name not in allowed_tool_names:
                                raise ValueError("用户本轮未授权该工具")
                            raw_arguments = function.get("arguments", "{}")
                            if not isinstance(raw_arguments, str) or len(raw_arguments) > 10_000:
                                raise ValueError("工具参数无效")
                            arguments = json.loads(raw_arguments)
                            if not isinstance(arguments, dict):
                                raise ValueError("工具参数必须是对象")
                        except Exception as exc:
                            if guide_request:
                                raise RuntimeError("Bell 引导 Agent 工具调用格式无效") from exc
                            result = {"ok": False, "error": str(exc)}
                        else:
                            try:
                                result = self._execute_agent_tool(
                                    session_id,
                                    name,
                                    arguments,
                                    guide_expectation,
                                )
                            except ConflictError:
                                raise
                            except Exception as exc:
                                if guide_request:
                                    raise GuideToolExecutionError(
                                        "Bell guide local tool failed"
                                    ) from exc
                                result = {"ok": False, "error": str(exc)}
                            else:
                                tool_names.append(name)
                                if guide_request:
                                    guide_tool_completed = True
                        followup.append({
                            "role": "tool",
                            "tool_call_id": str(call.get("id", "unknown")),
                            "content": json.dumps(result, ensure_ascii=False),
                        })
                    reply = self._agent_content(invoke(followup))
                else:
                    if guide_request:
                        raise RuntimeError("Bell 引导 Agent 未调用当前阶段工具")
                    content = message.get("content")
                    if not isinstance(content, str) or not content.strip():
                        raise RuntimeError("Agent 服务返回了空响应")
                    reply = content.strip()
                understanding, proposal = "", None
            else:
                content = self._agent_content(response)
                payload = self._agent_object(content)
                understanding = payload.get("understanding")
                reply = payload.get("response")
                if not isinstance(understanding, str) or not understanding.strip() or not isinstance(reply, str) or not reply.strip():
                    raise RuntimeError("Agent 响应缺少理解或反馈")
                raw_proposal = payload.get("proposal")
                if raw_proposal is not None and (not isinstance(raw_proposal, dict) or raw_proposal.get("kind") != requested_kind):
                    raw_proposal = None
                with self._session_lock(session_id):
                    current = self.get(session_id)
                    if (
                        current.workbench_revision
                        != guide_expectation["workbench_revision"]
                    ):
                        raise ConflictError("stale Agent request")
                    proposal = self._prepare_agent_proposal(
                        current, raw_proposal
                    )
            if guide_request and not guide_tool_completed:
                raise RuntimeError("Bell 引导阶段工具未完成")
            with self._session_lock(session_id):
                session = self.get(session_id)
                session.conversation.append({"role": "assistant", "content": reply.strip()})
                conversation = copy.deepcopy(session.conversation[-12:])
                current_session = session.public() if tool_names else None
            return {
                "status": "ready", "source": "model", "model": os.environ.get("LOOMQ_LLM_MODEL", "test-model"),
                "model_attempted": True, "model_generated": True,
                "understanding": understanding.strip(), "response": reply.strip(), "proposal": proposal,
                "conversation": conversation, "tools_used": tool_names,
                "session": current_session,
            }
        except ConflictError:
            raise
        except GuideToolExecutionError:
            return self._guide_tool_error_response(session_id, model_attempted=True)
        except Exception:
            if guide_request:
                return self._preset_guide_fallback(
                    session_id,
                    guide_stage_before,
                    guide_expectation["circuit_revision"],
                    guide_expectation["workbench_revision"],
                    "explanation_failed" if guide_tool_completed else "model_response_unavailable",
                    model_attempted=True,
                    tool_already_completed=guide_tool_completed,
                )
            reply = "Agent 请求失败。实验内容未改变，你仍可使用手动编辑、验证和本地运行。"
            with self._session_lock(session_id):
                session = self.get(session_id)
                session.conversation.append({"role": "assistant", "content": reply})
                conversation = copy.deepcopy(session.conversation[-12:])
            return {
                "status": "error", "source": "model", "model": None,
                "model_attempted": True, "model_generated": False,
                "understanding": "请求未完成", "response": reply,
                "proposal": None, "conversation": conversation,
            }

    def _prepare_agent_proposal(self, session: ExperimentSession, raw: Any) -> Optional[Dict[str, Any]]:
        if raw is None:
            return None
        if not isinstance(raw, dict) or raw.get("kind") not in {"qasm", "goal", "backend"}:
            raise RuntimeError("Agent 提案类型无效")
        kind = raw["kind"]
        proposal_id = str(uuid.uuid4())
        stored: Dict[str, Any] = {
            "proposal_id": proposal_id, "kind": kind, "session_id": session.session_id,
            "circuit_revision": session.circuit_revision, "goal_revision": session.goal_revision,
            "workbench_revision": session.workbench_revision,
            "summary": str(raw.get("summary", "Agent 修改提案"))[:500],
        }
        if kind == "qasm":
            qasm = raw.get("qasm")
            if not isinstance(qasm, str):
                raise RuntimeError("Agent QASM 提案无效")
            circuit = parse_qasm(qasm)
            validation = _validation(circuit, session.goal)
            stored.update({
                "qasm": qasm, "validation": validation,
                "safe_to_apply": validation["runnable"],
                "diff": "\n".join(difflib.unified_diff(session.qasm.splitlines(), qasm.splitlines(), fromfile="当前 QASM", tofile="Agent 提案", lineterm="")),
            })
        elif kind == "goal":
            goal = raw.get("goal")
            if not isinstance(goal, str) or not goal.strip():
                raise RuntimeError("Agent 目标提案无效")
            stored["goal"] = goal.strip()[:500]
            stored["safe_to_apply"] = True
        else:
            backend_id = raw.get("backend_id")
            ids = {item["id"] for item in self.recommendations(session.session_id)["items"] if item["selectable"]}
            if backend_id not in ids:
                raise RuntimeError("Agent 后端提案不在能力表中")
            stored["backend_id"] = backend_id
            stored["safe_to_apply"] = True
        self.pending_proposals[proposal_id] = copy.deepcopy(stored)
        return {key: value for key, value in stored.items() if key not in {"session_id", "qasm"}}

    @_session_locked
    def apply_agent_proposal(self, session_id: str, proposal_id: str) -> Dict[str, Any]:
        session = self.get(session_id)
        proposal = self.pending_proposals.get(proposal_id)
        if not proposal or proposal["session_id"] != session_id:
            raise KeyError("Agent proposal not found")
        if (
            proposal["circuit_revision"] != session.circuit_revision
            or proposal["goal_revision"] != session.goal_revision
            or proposal["workbench_revision"] != session.workbench_revision
        ):
            raise ConflictError("Agent proposal is stale")
        kind = proposal["kind"]
        if kind == "qasm":
            circuit = parse_qasm(proposal["qasm"])
            validation = _validation(circuit, session.goal)
            if not proposal.get("safe_to_apply") or not validation["runnable"]:
                raise ValueError("Agent QASM proposal failed structural validation")
            self._set_qasm(session, proposal["qasm"])
        elif kind == "goal":
            self.update_goal(session_id, proposal["goal"])
        else:
            self.select_backend(session_id, proposal["backend_id"])
        self.pending_proposals.pop(proposal_id, None)
        session.conversation.append({"role": "assistant", "content": "提案已由用户确认并应用。"})
        return session.public()

    @_session_locked
    def run(self, session_id: str, shots: int = 1024) -> Dict[str, Any]:
        session = self.get(session_id)
        if type(shots) is not int or shots < 1 or shots > 100_000:
            raise ValueError("shots must be between 1 and 100000")
        circuit = parse_qasm(session.qasm)
        validation = _validation(circuit, session.goal)
        session.validation = validation
        if not validation["runnable"]:
            session.state = "invalid"
            if not circuit.measurements:
                session.notice = "当前电路没有测量。添加测量后即可恢复运行。"
                error = "circuit has no measurements"
            else:
                session.notice = "测量映射存在覆盖；修复为互不覆盖的读出映射后才能运行。"
                error = "circuit has an unsafe measurement mapping"
            session.workbench_revision += 1
            raise ValueError(error)
        target_supported = validation["target_supported"]
        run_id = str(uuid.uuid4())
        backend_id = session.backend_selection
        if backend_id == WEB_BACKEND_ID:
            counts = _counts(session.qasm, shots)
            backend_name = WEB_BACKEND_NAME
            job_id = run_id
            metadata = {"engine": WEB_BACKEND_NAME, "qubits": circuit.qubit_count}
            counting_method = "由理想概率按最大余数法确定性折算的教学计数，不是真实逐 shot 抽样"
            boundary = (
                "本次结果来自 LoomQ 本地理想参考模拟器（内置状态向量）；"
                "计数由理想概率确定性折算。它并非真机，不反映真机噪声、校准、"
                "排队或硬件误差。真机计数是特定设备与运行条件下的统计样本，"
                "不能单独证明未测量的量子性质。"
            )
        else:
            runner = self.backend_runners.get(backend_id)
            status = self.backend_availability.get(backend_id, {})
            if runner is None or not status.get("available"):
                raise ValueError("所选本地后端当前不可用，请在“运行位置”中重新选择")
            raw_counts, backend_name, job_id, metadata = runner(circuit, shots)
            counts = normalize_counts(raw_counts, shots, circuit.classical_count)
            provider = LOCAL_BACKENDS[backend_id][0]
            provider_names = {
                "spinq": "量旋 SpinQit", "originq": "本源 pyQPanda",
                "braket": "AWS Braket LocalSimulator",
            }
            counting_method = "供应商 %s 本地 SDK 模拟器返回的有限 shots 计数" % provider_names[provider]
            boundary = (
                "本次结果来自 %s（%s 本地 SDK 执行器）。它并非真机，不反映"
                "真实设备噪声、校准或排队；计数语义由该供应商本地模拟器决定。"
                "真机计数是特定设备与运行条件下的统计样本，不能单独证明未测量"
                "的量子性质。" % (backend_name, provider_names[provider])
            )
        if not target_supported:
            boundary = (
                "本次运行不支持当前目标：本地语义 oracle 判定电路与目标不一致。"
                "以下计数仍可用于探索该电路本身；不得把它解释为当前目标的实现证据。"
            ) + boundary
        result = {
            "run_id": run_id, "status": "completed", "backend": backend_name,
            "backend_id": backend_id, "job_id": str(job_id), "meta": metadata or {},
            "backend_kind": "simulator", "shots": shots, "counts": counts, "bit_order": "little",
            "counting_method": counting_method,
            "snapshot_revision": session.circuit_revision,
            "target_supported": target_supported,
            "ideal": {bits: round(probability, 6) for bits, probability in distribution(session.qasm).items()},
            "boundary": boundary,
        }
        self.runs[run_id] = copy.deepcopy(result)
        session.result = result
        session.state = "completed"
        session.workbench_revision += 1
        session.notice = (
            "运行完成，结果已保存为不可变快照。"
            if target_supported
            else "运行完成，但本次运行不支持当前目标；请查看目标验证与结论边界。"
        )
        return session.public()

    @_session_locked
    def undo(self, session_id: str) -> Dict[str, Any]:
        session = self.get(session_id)
        if session.history:
            current = session._snapshot()
            snapshot = session.history.pop()
            session.future.append(current)
            session.restore(snapshot)
            session.workbench_revision += 1
            session.notice = "已撤销上一步。"
        return session.public()

    @_session_locked
    def redo(self, session_id: str) -> Dict[str, Any]:
        session = self.get(session_id)
        if session.future:
            current = session._snapshot()
            snapshot = session.future.pop()
            session.history.append(current)
            session.restore(snapshot)
            session.workbench_revision += 1
            session.notice = "已恢复下一步。"
        return session.public()


class ConflictError(RuntimeError):
    """An update was based on an old experiment revision."""


class GuideToolExecutionError(RuntimeError):
    """The deterministic Bell-stage tool failed and must not be retried."""
