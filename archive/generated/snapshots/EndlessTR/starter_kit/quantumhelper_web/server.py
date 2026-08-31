#!/usr/bin/env python3
"""Small production-friendly HTTP wrapper around the unchanged LoomQ adapter."""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import ipaddress
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit


APP_DIR = Path(__file__).resolve().parent
if (APP_DIR.parent / "adapter.py").is_file():
    STARTER_KIT_ROOT = APP_DIR.parent
elif (APP_DIR / "starter_kit" / "adapter.py").is_file():
    STARTER_KIT_ROOT = APP_DIR / "starter_kit"
elif (APP_DIR.parent / "starter_kit" / "adapter.py").is_file():
    STARTER_KIT_ROOT = APP_DIR.parent / "starter_kit"
else:
    raise RuntimeError("Cannot locate the LoomQ starter_kit adapter")
PROJECT_ROOT = STARTER_KIT_ROOT.parent
STATIC_ROOT = APP_DIR / "static"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(STARTER_KIT_ROOT))

try:
    from starter_kit import adapter  # type: ignore  # noqa: E402
except ModuleNotFoundError as exc:  # extracted submission root has no outer package
    if exc.name != "starter_kit":
        raise
    import adapter  # type: ignore  # noqa: E402

try:  # web-only orchestration layer; the adapter stays untouched
    from . import web_agent  # type: ignore  # noqa: E402
except ImportError:  # server.py executed directly as a script
    import web_agent  # type: ignore  # noqa: E402

try:  # Wave 3: backend requirement model + runtime config (own modules)
    from . import backend_selector, runtime_config, qasm_extract  # type: ignore  # noqa: E402
except ImportError:  # server.py executed directly as a script
    import backend_selector, runtime_config, qasm_extract  # type: ignore  # noqa: E402

# Optional persistent server-side configuration. Real environment variables
# always win; the file is outside STATIC_ROOT and ignored by Git.
runtime_config.load_env_file(APP_DIR / ".env")

try:  # raised by adapter when LOOMQ_LLM_* is missing - map to a friendly error
    from starter_kit.llm_client import LoomQLLMConfigurationError  # type: ignore  # noqa: E402
except ModuleNotFoundError:  # extracted submission root has no outer package
    from llm_client import LoomQLLMConfigurationError  # type: ignore  # noqa: E402


MAX_BODY_BYTES = 128 * 1024
MAX_QUBITS = 12
MAX_OPERATIONS = 2_000
MAX_SHOTS = 10_000
REQUESTS_PER_MINUTE = 60
RUN_SLOTS = threading.BoundedSemaphore(4)
RATE_LOCK = threading.Lock()
RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
BACKENDS = (
    {
        "id": "spinq",
        "adapter_target": "spinq",
        "name": "SpinQ 本地模拟器",
        "description": "使用 adapter 的 SpinQ 目标执行；未安装 SDK 时使用内置精确模拟器。",
    },
    {
        "id": "originq",
        "adapter_target": "originq",
        "name": "OriginQ 本地模拟器",
        "description": "使用 adapter 的 OriginQ 目标执行；未安装 SDK时使用内置精确模拟器。",
    },
    {
        "id": "braket",
        "adapter_target": "braket",
        "name": "Braket 本地模拟器",
        "description": "使用 adapter 的 Braket 目标执行；未安装 SDK 时使用内置精确模拟器。",
    },
)
ALLOWED_TARGETS = {item["adapter_target"] for item in BACKENDS}
BACKEND_CAPABILITIES = {
    item["id"]: item
    for item in json.loads(
        (STARTER_KIT_ROOT / "backend_capabilities.json").read_text(
            encoding="utf-8"
        )
    )["backends"]
}
PLAN_TEMPLATES = {
    "查找": {
        "goal": "在 8 个候选中读取示例目标 6",
        "condition": "候选范围和示例目标编号明确",
        "output": "三位测量结果 110",
        "method": "目标态编码演示",
        "description": "这是可执行的入门演示：把示例目标 6 编码为 110 后测量。它不宣称已经实现通用 Grover 搜索。",
        "steps": (
            ("准备三位寄存器", "使用 3 个量子比特表示 0 到 7。"),
            ("编码示例目标", "用 X 门把目标 6 写成二进制状态 110。"),
            ("测量读取", "重复执行并读取三位输出。"),
        ),
        "qasm": 'OPENQASM 2.0; include "qelib1.inc"; qreg q[3]; creg c[3]; x q[1]; x q[2]; measure q -> c;',
    },
    "优化": {
        "goal": "比较流程所需的候选编码和测量输出",
        "condition": "示例用 4 位状态 0101 代表一个候选方案",
        "output": "四位候选编码 0101",
        "method": "候选方案编码演示",
        "description": "这是可运行的流程演示，不会把未提供的成本函数伪装成完整 QAOA。实际优化还需要明确目标函数和约束。",
        "steps": (
            ("准备候选寄存器", "使用 4 个量子比特表示候选方案。"),
            ("编码演示候选", "把示例候选编码为 0101。"),
            ("测量候选", "运行并读取当前候选编码。"),
        ),
        "qasm": 'OPENQASM 2.0; include "qelib1.inc"; qreg q[4]; creg c[4]; x q[0]; x q[2]; measure q -> c;',
    },
    "测量": {
        "goal": "观察两比特叠加线路的测量分布",
        "condition": "两比特分别进入叠加状态并重复测量",
        "output": "00、01、10、11 的实际 counts",
        "method": "直接线路执行",
        "description": "adapter 会实际执行线路并汇总测量次数，不使用预置柱状图。",
        "steps": (
            ("准备线路", "让两个量子比特分别进入叠加状态。"),
            ("选择 adapter 目标", "可比较 SpinQ、OriginQ 与 Braket 本地目标。"),
            ("统计分布", "按输入 shots 汇总四种测量结果。"),
        ),
        "qasm": 'OPENQASM 2.0; include "qelib1.inc"; qreg q[2]; creg c[2]; h q[0]; h q[1]; measure q -> c;',
    },
    "关联": {
        "goal": "观察两个量子比特的关联测量结果",
        "condition": "H 和 CX 构成 Bell 线路",
        "output": "以 00 和 11 为主的实际 counts",
        "method": "Bell 关联线路",
        "description": "adapter 实际运行 H、CX 和末端测量，用结果验证两比特关联。",
        "steps": (
            ("准备叠加", "对 q[0] 应用 H 门。"),
            ("建立关联", "用 CX 连接 q[0] 与 q[1]。"),
            ("测量验证", "重复执行并查看 00 与 11 的 counts。"),
        ),
        "qasm": 'OPENQASM 2.0; include "qelib1.inc"; qreg q[2]; creg c[2]; h q[0]; cx q[0],q[1]; measure q -> c;',
    },
}


#: Router scenario ids -> the adapter-validated templates above.
SCENARIO_TEMPLATE_KEYS = {
    "search": "查找",
    "optimization": "优化",
    "measurement": "测量",
    "correlation": "关联",
}
#: Scenarios the repo can actually generate and run end to end.  "查找" (Grover)
#: and "优化" (QAOA) are explanation-only until a real generator exists; the UI
#: must not promise otherwise (任务书 §9.1/§9.2/§40.13).
DIRECTLY_SUPPORTED_SCENARIOS = frozenset({"measurement", "correlation"})

#: goal slug -> 前端 Current Task 面板可读标签（第二轮 §2 唯一 canonical task）。
GOAL_LABELS = {
    "bell": "Bell 态",
    "ghz": "GHZ 态",
    "qft": "QFT",
    "superposition": "叠加态",
}

#: Friendly wording per adapter error code, so a refused task never degrades
#: into "请补充量子比特数量和测量范围" (任务书 §2.2/§40.4).
ADAPTER_ERROR_MESSAGES = {
    "AMBIGUOUS": "我还不能确定你想要哪一种线路。可以说得更具体一点，"
                 "例如「两比特 Bell 态」或「3 比特 GHZ 态」。",
    "UNSUPPORTED": "这个目标当前还不支持。现在可以可靠生成的是：单比特叠加与测量、"
                   "Bell 态、GHZ 态和 QFT。",
    "SEMANTIC_MISMATCH": "你描述的目标和线路细节对不上，我不能凑一条看起来像但其实不对的线路。"
                         "可以确认一下目标态和量子比特数吗？",
    "UNGROUNDED": "你的描述里缺少可以对应到具体门序列的信息，我不想凭猜测生成线路。"
                  "可以补充想要的目标态吗？",
    "INVALID_INPUT": "这段输入我没法当作量子线路请求来处理。可以换一种说法吗？",
    "INPUT_TOO_LONG": "输入太长了，请精简一下再试。",
    "PARSE_FAILED": "我没能把这段描述解析成可靠的线路请求。可以说得更具体一点吗？",
    "REPAIR_FAILED": "这段代码我暂时修不好。可以确认一下你想要的目标态是什么吗？",
}

#: adapter error code -> the web error taxonomy (任务书 §26).  Keeping both means
#: the user sees one friendly sentence while the debug panel keeps the原始 code.
WEB_ERROR_CODES = {
    "AMBIGUOUS": "MISSING_REQUIRED_INFO",
    "UNGROUNDED": "MISSING_REQUIRED_INFO",
    "INPUT_TOO_LONG": "MISSING_REQUIRED_INFO",
    "GENERATION": "MISSING_REQUIRED_INFO",
    "INVALID_INPUT": "INTENT_UNCLEAR",
    "INVALID_INTENT": "INTENT_UNCLEAR",
    "UNSUPPORTED": "QASM_UNSUPPORTED_GATE",
    "SEMANTIC_MISMATCH": "SEMANTIC_MISMATCH",
    "PARSE_FAILED": "QASM_PARSE_ERROR",
    "REPAIR_FAILED": "QASM_VALIDATION_ERROR",
    "L1_VALIDATION": "QASM_VALIDATION_ERROR",
    "WRONG_TASK": "INTENT_UNCLEAR",
}


def _json_default(value):
    item = getattr(value, "item", None)
    if callable(item):
        return item()
    return str(value)


def _client_allowed(address: str) -> bool:
    now = time.monotonic()
    cutoff = now - 60
    with RATE_LOCK:
        bucket = RATE_BUCKETS[address]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= REQUESTS_PER_MINUTE:
            return False
        bucket.append(now)
        if len(RATE_BUCKETS) > 4096:
            for key in list(RATE_BUCKETS):
                if not RATE_BUCKETS[key] or RATE_BUCKETS[key][-1] < cutoff:
                    RATE_BUCKETS.pop(key, None)
        return True


def _local_config_client(address: str) -> bool:
    """Configuration and credentials are manageable from loopback only."""
    try:
        return ipaddress.ip_address(address).is_loopback
    except ValueError:
        return False


def _local_config_host(host_header: str) -> bool:
    """Accept only an explicit loopback Host for credential-management APIs.

    Checking the peer address alone is insufficient in a browser: a hostile
    domain can resolve to 127.0.0.1 (DNS rebinding) while retaining its own
    Host header.  Normal application APIs remain usable on a LAN; only model
    credential management is deliberately restricted this tightly.
    """
    if not isinstance(host_header, str) or not host_header.strip():
        return False
    try:
        authority = urlsplit(f"//{host_header.strip()}")
        hostname = authority.hostname
        # Force validation of a supplied port and reject every non-authority
        # component.  A Host header has no valid user-info, path or query.
        _ = authority.port
    except ValueError:
        return False
    if (
        authority.username is not None
        or authority.password is not None
        or authority.path
        or authority.query
        or authority.fragment
    ):
        return False
    return hostname is not None and hostname.lower() in {
        "localhost",
        "127.0.0.1",
        "::1",
    }


def _local_config_request(address: str, host_header: str) -> bool:
    """Require both a loopback TCP peer and a loopback HTTP authority."""
    return _local_config_client(address) and _local_config_host(host_header)


def _circuit_summary(qasm: str) -> tuple[object, dict]:
    circuit = adapter.parse_qasm(qasm)
    operations = list(adapter._iter_circuit_operations(circuit))
    if circuit.q_num > MAX_QUBITS:
        raise ValueError(f"网页运行最多支持 {MAX_QUBITS} 个量子比特")
    if len(operations) > MAX_OPERATIONS:
        raise ValueError(f"线路操作数不能超过 {MAX_OPERATIONS}")
    measurements = [op for op in operations if isinstance(op, adapter.Measurement)]
    gates = [op for op in operations if not isinstance(op, adapter.Measurement)]
    return circuit, {
        "qubits": circuit.q_num,
        "classical_bits": circuit.c_num,
        "gate_count": len(gates),
        "measurement_count": len(measurements),
        "operation_count": len(operations),
        "two_qubit_gates": sum(len(gate.qubits) == 2 for gate in gates),
        "gates": [gate.name.upper() for gate in gates],
        "has_measurement": bool(measurements),
    }


def _serialize_circuit(circuit: object) -> dict:
    operations = []
    for index, operation in enumerate(adapter._iter_circuit_operations(circuit)):
        measurement = isinstance(operation, adapter.Measurement)
        item = {
            "id": f"op-{index}",
            "index": index,
            "type": "measurement" if measurement else "gate",
            "name": "measure" if measurement else str(operation.name).lower(),
            "qubits": [operation.qubit] if measurement else list(operation.qubits),
            "clbits": [operation.clbit] if measurement else [],
            "params": [] if measurement or operation.params is None else (
                list(operation.params) if isinstance(operation.params, (list, tuple)) else [operation.params]
            ),
        }
        item["label"] = (
            f"Measure q[{operation.qubit}] → c[{operation.clbit}]"
            if measurement
            else f"{item['name'].upper()} " + ", ".join(f"q[{qubit}]" for qubit in item["qubits"])
        )
        operations.append(item)
    return {"qubits": circuit.q_num, "classical_bits": circuit.c_num, "operations": operations}


def _explanation_steps(circuit_payload: dict) -> list[dict]:
    gate_text = {
        "h": ("建立叠加", "H 门让量子比特进入叠加状态，为后续操作准备多个可能性。"),
        "cx": ("建立关联", "CX 门用控制量子比特影响目标量子比特，使两者的状态产生关联。"),
        "x": ("翻转状态", "X 门翻转量子比特的 0 和 1 状态。"),
        "swap": ("交换状态", "SWAP 门交换两个量子比特当前承载的状态。"),
    }
    steps = []
    measurement_ids = []
    for operation in circuit_payload["operations"]:
        if operation["type"] == "measurement":
            measurement_ids.append(operation["id"])
            continue
        title, explanation = gate_text.get(
            operation["name"],
            (f"应用 {operation['name'].upper()} 门", "这一步来自已经通过 adapter 校验的真实门序列。"),
        )
        steps.append({
            "id": f"step-{len(steps)}", "index": len(steps), "title": title,
            "operation_ids": [operation["id"]], "gates": [operation["label"]],
            "explanation": explanation,
        })
    if measurement_ids:
        measured = [
            f"q[{item['qubits'][0]}] → c[{item['clbits'][0]}]"
            for item in circuit_payload["operations"] if item["type"] == "measurement"
        ]
        steps.append({
            "id": f"step-{len(steps)}", "index": len(steps), "title": "测量",
            "operation_ids": measurement_ids, "gates": ["Measure"],
            "explanation": f"只读取 {', '.join(measured)}，并把多次运行结果汇总为测量分布。",
        })
    return steps


def _requested_measurements(prompt: str, qubits: int | None = None) -> list[tuple[int, int]] | None:
    """Return an explicit measurement selection, or None when none was requested."""
    if not re.search(r"测量|measure", prompt, re.IGNORECASE):
        return None
    if re.search(r"不(?:要|进行)?测量|no\s+measure", prompt, re.IGNORECASE):
        return []
    if qubits is not None and re.search(r"全部|全测量|all", prompt, re.IGNORECASE):
        return [(index, index) for index in range(qubits)]
    indexes = [int(value) for value in re.findall(r"q\s*\[?\s*(\d+)\s*\]?", prompt, re.IGNORECASE)]
    if indexes:
        indexes = list(dict.fromkeys(indexes))
        if qubits is not None and any(index >= qubits for index in indexes):
            raise ValueError("指定的测量量子比特超出当前线路范围")
        return [(index, index) for index in indexes]
    number_words = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8}
    first = re.search(r"只测量(?:前)?\s*(\d+|[一二两三四五六七八])\s*(?:个)?(?:量子)?比特", prompt)
    if first:
        count = int(first.group(1)) if first.group(1).isdigit() else number_words[first.group(1)]
        if qubits is not None and count > qubits:
            raise ValueError("指定的测量数量超出当前线路范围")
        return [(index, index) for index in range(count)]
    if re.search(r"只测量第一个|只测量第一位|只测量第一量子比特", prompt):
        return [(0, 0)]
    return None


def _qasm_with_measurements(circuit: object, pairs: list[tuple[int, int]]) -> str:
    operations = list(adapter._iter_circuit_operations(circuit))
    measurement_seen = False
    for operation in operations:
        if isinstance(operation, adapter.Measurement):
            measurement_seen = True
        elif measurement_seen:
            raise ValueError("当前线路在测量后仍包含量子门；为避免改变真实执行顺序，不能自动改写测量范围。")
    classical_bits = max(circuit.c_num, max((clbit for _, clbit in pairs), default=-1) + 1, 1)
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{circuit.q_num}];", f"creg c[{classical_bits}];"]
    for operation in operations:
        if isinstance(operation, adapter.Measurement):
            continue
        raw_params = operation.params
        if isinstance(raw_params, (list, tuple)):
            parameter = "" if not raw_params else "(" + ",".join(f"{float(value):.17g}" for value in raw_params) + ")"
        else:
            parameter = "" if raw_params is None else f"({float(raw_params):.17g})"
        operands = ",".join(f"q[{index}]" for index in operation.qubits)
        lines.append(f"{operation.name}{parameter} {operands};")
    lines.extend(f"measure q[{qubit}] -> c[{clbit}];" for qubit, clbit in pairs)
    return "\n".join(lines)


def _measurement_task_value(circuit_payload: dict):
    pairs = [
        {"qubit": item["qubits"][0], "classical_bit": item["clbits"][0]}
        for item in circuit_payload["operations"] if item["type"] == "measurement"
    ]
    if not pairs:
        return "none"
    if pairs == [{"qubit": index, "classical_bit": index} for index in range(circuit_payload["qubits"])]:
        return "all"
    return {"mode": "partial", "pairs": pairs}


def _chat_metadata(payload: dict) -> dict:
    schema_version = payload.get("schema_version", "1.0")
    if not isinstance(schema_version, str) or not schema_version.strip():
        raise TypeError("schema_version 必须是非空字符串")
    metadata = {"schema_version": schema_version.strip()}
    for key in ("request_id", "session_id", "task_id"):
        value = payload.get(key)
        if value is not None and not isinstance(value, str):
            raise TypeError(f"{key} 必须是字符串")
        metadata[key] = value
    base_revision = payload.get("base_revision")
    if base_revision is not None and (isinstance(base_revision, bool) or not isinstance(base_revision, int) or base_revision < 0):
        raise TypeError("base_revision 必须是非负整数")
    metadata["base_revision"] = base_revision
    return metadata


def _qasm_intent(prompt: str, requested_intent: object = None) -> str:
    explicit_repair = isinstance(requested_intent, str) and requested_intent.casefold() in {
        "repair", "repair_circuit", "circuit_repair",
    }
    repair_words = re.search(
        r"修复|纠错|改正|报错|错误|语法问题|\brepair\b|\bfix\b|\bdebug\b",
        prompt,
        re.IGNORECASE,
    )
    return "repair_circuit" if explicit_repair or repair_words else "generate_circuit"


def _extract_repair_source(prompt: str) -> str | None:
    fenced = re.findall(r"```(?:openqasm|qasm)?\s*(.*?)```", prompt, re.IGNORECASE | re.DOTALL)
    if fenced:
        return fenced[-1].strip() or None
    start = re.search(r"OPENQASM\s+2\.0", prompt, re.IGNORECASE)
    if start:
        return prompt[start.start():].strip()
    parts = re.split(r"请(?:帮我)?修复|修复(?:这段|以下)?|报错(?:了)?[：:]?", prompt, flags=re.IGNORECASE)
    candidate = parts[-1].strip(" ：:\n") if len(parts) > 1 else ""
    if re.search(r"\b(?:h|x|cx|measure|qreg|creg)\b", candidate, re.IGNORECASE):
        return candidate
    return None


def _repair_issues(before: str | None) -> list[dict]:
    """结构化 diagnostics（§24）：每项带 code/severity/message，能定位到行就带 line。"""
    if not before:
        return []
    issues: list[dict] = []
    if not re.search(r"OPENQASM\s+2\.0\s*;", before, re.IGNORECASE):
        issues.append({"code": "MISSING_HEADER", "severity": "error", "line": None,
                       "message": "输入中没有完整的 OpenQASM 2.0 头部。"})
    if re.search(r"\bcx\s+q\[\d+\]\s+q\[\d+\]", before, re.IGNORECASE):
        issues.append({"code": "MISSING_COMMA", "severity": "error", "line": None,
                       "message": "CX 的两个量子比特参数之间缺少逗号。"})
    for index, line in enumerate(before.splitlines(), 1):
        stripped = line.strip()
        if re.match(r"(?:h|x|cx|measure)\b", stripped, re.IGNORECASE) and not stripped.endswith(";"):
            issues.append({"code": "MISSING_SEMICOLON", "severity": "error", "line": index,
                           "message": f"第 {index} 行操作语句末尾缺少分号。"})
            break
    return issues


def _apply_textual_edit(qasm: str, instruction: str) -> str | None:
    """对 QASM 做少量、可安全解析的文本替换（§6 edit_current_qasm）。

    解析不出就返回 None，绝不擅自猜语义（§25/26）。
    """
    # 把 A 改成 B
    m = re.search(r"把\s*(.+?)\s*(?:改成|改为|换成)\s*(.+)", instruction)
    if m:
        old, new = m.group(1).strip().rstrip("。.;；"), m.group(2).strip().rstrip("。.;；")
        if "最后一行" in old or "最后" in old:
            lines = qasm.rstrip().splitlines()
            if lines:
                lines[-1] = new
                return "\n".join(lines)
            return None
        if old and old in qasm:
            return qasm.replace(old, new)
        return None
    # 删掉 / 删除 / 去掉 A
    m = re.search(r"(?:删掉|删除|去掉)\s*(.+)", instruction)
    if m:
        target = m.group(1).strip()
        # "删掉 X 后面的分号" -> 移除 X 之后紧跟的那个分号
        semicolon = re.search(r"(.+?)\s*(?:后面|之后)的\s*分号", target)
        if semicolon:
            anchor = semicolon.group(1).strip()
            if anchor in qasm:
                idx = qasm.find(anchor) + len(anchor)
                if idx < len(qasm) and qasm[idx] == ";":
                    return qasm[:idx] + qasm[idx + 1:]
        if target and target in qasm:
            return qasm.replace(target, "")
        return None
    return None


def _safe_summary(qasm: str) -> dict | None:
    try:
        return _circuit_summary(qasm)[1]
    except Exception:  # noqa: BLE001
        return None


def _safe_serialize(qasm: str) -> dict | None:
    try:
        return _serialize_circuit(_circuit_summary(qasm)[0])
    except Exception:  # noqa: BLE001
        return None


def _transpiled_outputs(qasm: str) -> dict[str, str]:
    """Return displayable target artifacts produced by the authoritative adapters."""
    return {target: adapter.transpile(qasm, target) for target in sorted(ALLOWED_TARGETS)}


def _diagnose_qasm_issues(source_qasm: str | None) -> list[dict]:
    """定位一段 QASM 的常见问题（§7 诊断流水线的「locate error」）。

    与 ``_repair_issues`` 不同，这里专门找「同一行塞了两条语句、第一条缺分号」这类
    结构错误——它不会被「整行以 ; 结尾」误判为没问题。
    """
    if not source_qasm:
        return [{"code": "NO_QASM", "severity": "error", "message": "没有从输入里提取到可识别的 QASM 代码。"}]
    issues: list[dict] = []
    if not re.search(r"OPENQASM\s+2\.0", source_qasm, re.IGNORECASE):
        issues.append({"code": "MISSING_HEADER", "severity": "error", "message": "缺少 OpenQASM 2.0 头部。"})

    # 越界 qubit：q[i] 里 i >= 寄存器宽度。只扫门/测量语句，跳过 qreg/creg 声明行，
    # 否则 "qreg q[2]" 里的 q[2]（寄存器宽度）会被误判成越界引用。
    qreg_match = re.search(r"qreg\s+q\s*\[\s*(\d+)\s*\]", source_qasm, re.IGNORECASE)
    qreg_size = int(qreg_match.group(1)) if qreg_match else None
    if qreg_size is not None:
        for line_no, line in enumerate(source_qasm.splitlines(), 1):
            stripped = line.strip()
            if not stripped or re.match(r"(?:qreg|creg|OPENQASM|include)\b", stripped, re.IGNORECASE):
                continue
            for match in re.finditer(r"q\s*\[\s*(\d+)\s*\]", stripped):
                index = int(match.group(1))
                if index >= qreg_size:
                    issues.append({
                        "code": "QUBIT_OUT_OF_RANGE",
                        "severity": "error",
                        "line": line_no,
                        "message": f"q[{index}] 越界：寄存器只声明了 q[0] 到 q[{qreg_size - 1}]。",
                    })
                    break
            if issues and issues[-1]["code"] == "QUBIT_OUT_OF_RANGE":
                break

    for line_no, line in enumerate(source_qasm.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        # 一行里出现两条门语句（gate q[...] gate q[...]）说明第一条缺分号。
        gates_on_line = re.findall(
            r"(?<![a-z0-9])(?:h|x|cx|swap|ccx|rz|ry|t|tdg|s|sdg|cu1)\s*(?:\([^)]*\))?\s*q\s*\[?\s*\d+",
            stripped, re.IGNORECASE,
        )
        if len(gates_on_line) >= 2:
            issues.append({
                "code": "MISSING_SEMICOLON",
                "severity": "error",
                "line": line_no,
                "message": f"一行里出现了多条语句（{gates_on_line[0][:20]}…），第一条语句后缺少分号。",
            })
            break
    return issues


def _repair_options_for_issues(source_qasm: str | None, issues: list[dict]) -> list[dict]:
    """为可定位的歧义错误给出修复选项（§25/§26），不擅自决定唯一修法。"""
    if not source_qasm:
        return []
    options: list[dict] = []
    for issue in issues:
        if issue["code"] == "QUBIT_OUT_OF_RANGE":
            m = re.search(r"q\[(\d+)\] 越界：寄存器只声明了 q\[0\] 到 q\[(\d+)\]", issue["message"])
            if m:
                bad, last = int(m.group(1)), int(m.group(2))
                options.append({
                    "label": f"把 q[{bad}] 改成 q[{last}]（更可能是笔误）",
                    "qasm": source_qasm.replace(f"q[{bad}]", f"q[{last}]", 1),
                })
                options.append({
                    "label": f"把寄存器扩成 q[{bad + 1}]",
                    "qasm": re.sub(rf"qreg\s+q\[{last + 1}\]", f"qreg q[{bad + 1}]", source_qasm, count=1),
                })
        elif issue["code"] == "MISSING_SEMICOLON":
            options.append({"label": "在语句末尾补上分号", "qasm": None})
    return options


def _default_backend_recommendation(qubits: int) -> dict:
    selected = adapter.select_backend_from_request(adapter.BackendRequest(
        required_qubits=qubits,
        device_types=("simulator",),
        queue_exact="none",
        cost_mode="free_only",
    ))
    backend = BACKEND_CAPABILITIES[selected.id]
    return {
        "status": "ready",
        "id": selected.id,
        "backend": backend,
        "runnable_locally": backend["kind"] == "simulator" and backend["platform"] in ALLOWED_TARGETS,
    }


def _validated_chat_context(payload: dict) -> dict | None:
    context = payload.get("context")
    if context is None:
        return None
    if not isinstance(context, dict):
        raise TypeError("context 必须是对象")
    if len(json.dumps(context, ensure_ascii=False, default=_json_default)) > 32_000:
        raise ValueError("context 不能超过 32000 个字符")
    unknown = set(context) - {"current_qasm", "task", "result"}
    if unknown:
        raise ValueError("context 包含不支持的字段")

    validated = {"current_qasm": None, "task": None, "result": None}
    current_qasm = context.get("current_qasm")
    if current_qasm is not None:
        if not isinstance(current_qasm, str) or not current_qasm.strip():
            raise TypeError("context.current_qasm 必须是非空字符串")
        if len(current_qasm) > 16_000:
            raise ValueError("context.current_qasm 不能超过 16000 个字符")
        circuit, summary = _circuit_summary(current_qasm)
        for target in sorted(ALLOWED_TARGETS):
            adapter.transpile(current_qasm, target)
        validated.update({
            "current_qasm": current_qasm,
            "circuit": circuit,
            "summary": summary,
            "circuit_payload": _serialize_circuit(circuit),
        })

    task = context.get("task")
    if task is not None:
        if not isinstance(task, dict):
            raise TypeError("context.task 必须是对象")
        if set(task) - {"type", "goal", "qubits", "measurement"}:
            raise ValueError("context.task 包含不支持的字段")
        goal = task.get("goal")
        if goal is not None and (not isinstance(goal, str) or len(goal) > 80):
            raise TypeError("context.task.goal 必须是短字符串")
        qubits = task.get("qubits")
        if qubits is not None and (isinstance(qubits, bool) or not isinstance(qubits, int)):
            raise TypeError("context.task.qubits 必须是整数")
        measurement = task.get("measurement")
        if measurement is not None and not (
            isinstance(measurement, str) and measurement in {"all", "none"}
        ):
            if not isinstance(measurement, dict) or measurement.get("mode") != "partial" or not isinstance(measurement.get("pairs"), list):
                raise ValueError("context.task.measurement 结构无效")
            normalized_pairs = []
            for pair in measurement["pairs"]:
                if not isinstance(pair, dict) or set(pair) != {"qubit", "classical_bit"}:
                    raise ValueError("context.task.measurement.pairs 结构无效")
                qubit, clbit = pair["qubit"], pair["classical_bit"]
                if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (qubit, clbit)):
                    raise ValueError("context.task.measurement.pairs 下标必须是非负整数")
                normalized_pairs.append((qubit, clbit))
            if len(normalized_pairs) != len(set(normalized_pairs)):
                raise ValueError("context.task.measurement.pairs 不能重复")
            if validated.get("circuit_payload"):
                actual_pairs = {
                    (item["qubits"][0], item["clbits"][0])
                    for item in validated["circuit_payload"]["operations"] if item["type"] == "measurement"
                }
                if set(normalized_pairs) != actual_pairs:
                    raise ValueError("context.task.measurement 与 current_qasm 的真实测量不一致")
        validated["task"] = dict(task)

    result = context.get("result")
    if result is not None:
        if not isinstance(result, dict) or set(result) - {"counts", "shots"}:
            raise ValueError("context.result 结构无效")
        counts = result.get("counts")
        if not isinstance(counts, dict) or len(counts) > 256:
            raise ValueError("context.result.counts 结构无效")
        for label, count in counts.items():
            if not isinstance(label, str) or len(label) > 64:
                raise ValueError("context.result.counts 标签无效")
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("context.result.counts 次数无效")
        validated["result"] = {"counts": dict(counts), "shots": result.get("shots")}
    return validated


def _modify_generation_prompt(prompt: str, context: dict | None) -> str | None:
    if not context or not context.get("current_qasm"):
        return None
    # 允许前缀（如「把当前线路改成 5 比特」），只要出现了「改成 N 比特」就提取 N。
    match = re.search(r"改成\s*(\d+)\s*(?:个?\s*)?(?:量子)?(?:比特|位)", prompt)
    if not match:
        return None
    qubits = int(match.group(1))
    if qubits <= 0 or qubits > MAX_QUBITS:
        raise ValueError(f"修改后的量子比特数必须在 1 到 {MAX_QUBITS} 之间")
    circuit_payload = context["circuit_payload"]
    current_qubits = circuit_payload["qubits"]
    operations = circuit_payload["operations"]
    gates = [item for item in operations if item["type"] == "gate"]
    measurements = [item for item in operations if item["type"] == "measurement"]
    expected_gates = [("h", [0])] + [("cx", [0, target]) for target in range(1, current_qubits)]
    actual_gates = [(item["name"], item["qubits"]) for item in gates]
    if current_qubits < 2 or actual_gates != expected_gates or operations[:len(gates)] != gates:
        raise ValueError("当前已验证线路不是 canonical GHZ，无法只凭比特数安全修改；请完整描述目标。")
    if not measurements:
        measurement = "none"
    elif len(measurements) == current_qubits and {
        (item["qubits"][0], item["clbits"][0]) for item in measurements
    } == {(index, index) for index in range(current_qubits)}:
        measurement = "all"
    else:
        raise ValueError("当前线路使用部分测量，无法安全推断修改后的测量范围；请完整描述目标。")
    suffix = "并进行全测量" if measurement == "all" else "且不要测量"
    return f"生成一个 {qubits} 比特 GHZ 态{suffix}"


def _circuit_explanation(
    prompt: str, context: dict | None, requested_gate: str | None = None
) -> tuple[str, list[str]] | None:
    """Explain the circuit currently on screen.

    Whether this turn *is* an explanation request is decided by
    ``web_agent.route``; this helper only builds the answer.  ``requested_gate``
    comes from the router's slots, with a local scan as fallback.
    """
    if not context or not context.get("circuit_payload"):
        return None
    if requested_gate is None:
        for name in ("cx", "swap", "h", "x"):
            if re.search(rf"(?<![a-z]){name}(?:\s*门)?(?![a-z])", prompt, re.IGNORECASE):
                requested_gate = name
                break
    # No explicit gate subject means this is not a gate-role question. Never
    # explain every/current-first gate as a fallback for unrelated QA.
    if requested_gate is None:
        return None
    operations = context["circuit_payload"]["operations"]
    related = [item for item in operations if item["type"] == "gate" and (requested_gate is None or item["name"] == requested_gate)]
    if not related:
        return "当前已验证线路中没有找到你询问的这个门。", []
    steps = _explanation_steps(context["circuit_payload"])
    related_ids = {item["id"] for item in related}
    messages = [step["explanation"] for step in steps if related_ids.intersection(step["operation_ids"])]
    return " ".join(dict.fromkeys(messages)), [item["id"] for item in related]


def _generation_prompt_from_route(decision: "web_agent.Route") -> str | None:
    """Turn a rule-resolved goal into an explicit prompt the adapter accepts.

    The router already worked out that "新手能看懂的量子线路" means a 1-qubit
    superposition, or that "最简单的纠缠例子" means a 2-qubit Bell state.  The
    adapter only understands concrete target names, so we spell them out here
    instead of forwarding the vague original (任务书 §6.1/§30).
    """
    if decision.intent != "generate_circuit":
        return None
    goal = decision.slots.get("goal")
    if goal not in web_agent.SUPPORTED_GOALS:
        return None
    qubits = decision.slots.get("qubits")
    if not isinstance(qubits, int) or qubits < 1:
        return None
    named = {
        "superposition": f"生成一个 {qubits} 比特叠加态电路，使用 H 门，并进行全测量",
        "bell": f"生成一个 {qubits} 比特 Bell 态并进行全测量",
        "ghz": f"生成一个 {qubits} 比特 GHZ 态并进行全测量",
        "qft": f"生成一个 {qubits} 比特 QFT 电路并进行全测量",
    }
    return named.get(goal)


def _superposition_qasm(qubits: int) -> str:
    """Deterministic 1..n qubit H + measure superposition circuit.

    "叠加态" is not one of adapter's named goals (bell/ghz/qft), so the adapter
    cannot generate it.  It *is* a trivial deterministic circuit, so build it
    here and let ``parse_qasm`` + ``transpile`` validate it like any other
    answer - no model, no faking (任务书 §30: 新手第一条线路 = 1-qubit H+测量).
    """
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{qubits}];",
        f"creg c[{qubits}];",
    ]
    lines.extend(f"h q[{index}];" for index in range(qubits))
    lines.append("measure q -> c;")
    return "\n".join(lines)


class QuantumHelperHandler(BaseHTTPRequestHandler):
    server_version = "QuantumHelper/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(
            f"{self.log_date_time_string()} {self.client_address[0]} {fmt % args}\n"
        )

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'",
        )
        super().end_headers()

    def _send_json(self, status: int, payload: dict) -> None:
        data = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), default=_json_default
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status: int, message: str, code: str = "REQUEST_ERROR") -> None:
        self._send_json(status, {"ok": False, "error": message, "code": code})

    def _read_json(self) -> dict:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip()
        if content_type != "application/json":
            raise ValueError("请求必须使用 application/json")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Content-Length 无效") from exc
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError(f"请求大小必须在 1 到 {MAX_BODY_BYTES} 字节之间")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("JSON 格式无效") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON 顶层必须是对象")
        return payload

    def do_GET(self) -> None:  # noqa: N802
        path = unquote(urlsplit(self.path).path)
        if path == "/api/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "QuantumHelper",
                    "adapter": "starter_kit.adapter",
                    "llm_enabled": web_agent.llm_enabled(),
                    "llm_available": web_agent.llm_available(),
                    "limits": {"qubits": MAX_QUBITS, "shots": MAX_SHOTS},
                },
            )
            return
        if path == "/api/backends":
            self._send_json(HTTPStatus.OK, {"ok": True, "backends": BACKENDS})
            return
        if path == "/api/config/status":
            if not _local_config_request(
                self.client_address[0], self.headers.get("Host", "")
            ):
                self._error(HTTPStatus.FORBIDDEN, "模型配置仅允许从服务器本机管理", "LOCAL_ONLY")
                return
            effective = runtime_config.get_runtime_config().effective()
            effective["enabled"] = web_agent.llm_enabled()
            effective["available"] = web_agent.llm_available()
            self._send_json(HTTPStatus.OK, {
                "ok": True,
                "config": effective,
            })
            return
        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if not path.startswith("/api/"):
            self._error(HTTPStatus.NOT_FOUND, "接口不存在", "NOT_FOUND")
            return
        if not _client_allowed(self.client_address[0]):
            self._error(HTTPStatus.TOO_MANY_REQUESTS, "请求过于频繁，请稍后再试", "RATE_LIMIT")
            return
        if path.startswith("/api/config") and not _local_config_request(
            self.client_address[0], self.headers.get("Host", "")
        ):
            self._error(HTTPStatus.FORBIDDEN, "模型配置仅允许从服务器本机管理", "LOCAL_ONLY")
            return
        try:
            payload = self._read_json()
            if path == "/api/check":
                self._check(payload)
            elif path == "/api/run":
                self._run(payload)
            elif path == "/api/plan":
                self._plan(payload)
            elif path == "/api/chat":
                self._chat(payload)
            elif path == "/api/config":
                self._config_set(payload)
            elif path == "/api/config/test":
                self._config_test(payload)
            else:
                self._error(HTTPStatus.NOT_FOUND, "接口不存在", "NOT_FOUND")
        except (TypeError, ValueError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc), "INVALID_INPUT")
        except LoomQLLMConfigurationError as exc:
            self._error(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "模型服务尚未配置，请先配置模型地址和密钥，或直接导入 OpenQASM 线路。",
                "LLM_NOT_CONFIGURED",
            )
        except Exception as exc:
            self.log_error("request failed: %s: %s", type(exc).__name__, exc)
            self._error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "处理失败，请检查输入或服务器配置",
                "ADAPTER_ERROR",
            )

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path != "/api/config":
            self._error(HTTPStatus.NOT_FOUND, "接口不存在", "NOT_FOUND")
            return
        if not _local_config_request(
            self.client_address[0], self.headers.get("Host", "")
        ):
            self._error(HTTPStatus.FORBIDDEN, "模型配置仅允许从服务器本机管理", "LOCAL_ONLY")
            return
        runtime_config.get_runtime_config().clear()
        self._send_json(HTTPStatus.OK, {
            "ok": True,
            "config": runtime_config.get_runtime_config().effective(),
        })

    def _config_set(self, payload: dict) -> None:
        base_url = payload.get("base_url")
        api_key = payload.get("api_key")
        model = payload.get("model")
        try:
            runtime_config.get_runtime_config().set(base_url, api_key, model)
        except (TypeError, ValueError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc), "INVALID_INPUT")
            return
        # effective() is the safe view: api_key_present bool, never the key (§22).
        self._send_json(HTTPStatus.OK, {
            "ok": True,
            "config": runtime_config.get_runtime_config().effective(),
        })

    def _config_test(self, payload: dict) -> None:
        # If the caller sent a candidate config, test it without persisting it;
        # otherwise probe whatever is currently effective (runtime or env).
        base_url = payload.get("base_url")
        api_key = payload.get("api_key")
        model = payload.get("model")
        cfg = runtime_config.get_runtime_config()
        if base_url or api_key or model:
            cfg = runtime_config.RuntimeConfig()
            try:
                cfg.set(base_url, api_key, model)
            except (TypeError, ValueError) as exc:
                self._error(HTTPStatus.BAD_REQUEST, str(exc), "INVALID_INPUT")
                return
        result = runtime_config.test_connection(cfg)
        status = HTTPStatus.OK if result["ok"] else HTTPStatus.BAD_GATEWAY
        self._send_json(status, {"ok": result["ok"], **result})

    def _check(self, payload: dict) -> None:
        qasm = payload.get("qasm")
        if not isinstance(qasm, str):
            raise TypeError("qasm 必须是字符串")
        _circuit, summary = _circuit_summary(qasm)
        transpiled = _transpiled_outputs(qasm)
        self._send_json(
            HTTPStatus.OK,
            {"ok": True, "summary": summary, "transpiled": transpiled},
        )

    def _run(self, payload: dict) -> None:
        qasm = payload.get("qasm")
        target = payload.get("target", "spinq")
        shots = payload.get("shots", 1024)
        if not isinstance(qasm, str):
            raise TypeError("qasm 必须是字符串")
        if target not in ALLOWED_TARGETS:
            raise ValueError("网页仅允许 adapter 的本地模拟目标")
        if isinstance(shots, bool) or not isinstance(shots, int):
            raise TypeError("shots 必须是整数")
        if shots <= 0 or shots > MAX_SHOTS:
            raise ValueError(f"shots 必须在 1 到 {MAX_SHOTS} 之间")
        _circuit, summary = _circuit_summary(qasm)
        if not summary["has_measurement"]:
            raise ValueError("线路必须包含测量")
        if not RUN_SLOTS.acquire(blocking=False):
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "服务器繁忙，请稍后重试", "BUSY")
            return
        try:
            result = adapter.run(qasm, target, shots)
        finally:
            RUN_SLOTS.release()
        self._send_json(
            HTTPStatus.OK,
            {"ok": True, "target": target, "summary": summary, "result": result},
        )

    def _plan(self, payload: dict) -> None:
        prompt = payload.get("prompt")
        type_hint = payload.get("type_hint")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("请先描述任务目标、候选或线路")
        if len(prompt) > 8_000:
            raise ValueError("任务描述不能超过 8000 个字符")
        if type_hint not in PLAN_TEMPLATES:
            if any(word in prompt for word in ("关联", "纠缠", "两个量子比特", "Bell")):
                type_hint = "关联"
            elif any(word in prompt for word in ("测量", "线路", "频率", "分布", "shots")):
                type_hint = "测量"
            elif any(word in prompt for word in ("优化", "冲突", "顺序", "安排", "路线", "成本", "方案")):
                type_hint = "优化"
            elif any(word in prompt for word in ("查找", "搜索", "候选", "目标", "编号")):
                type_hint = "查找"
            else:
                self._error(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "还无法判断任务类型。请补充目标、候选范围，以及怎样判断结果是否满足条件。",
                    "NEED_MORE_INFO",
                )
                return
        template = PLAN_TEMPLATES[type_hint]
        circuit, summary = _circuit_summary(template["qasm"])
        # The generated template must pass the same adapter translation used by users.
        adapter.transpile(template["qasm"], "spinq")
        operations = [
            {
                "name": gate.name,
                "qubits": list(gate.qubits),
                "parameter": gate.params,
            }
            for gate in circuit.gates
        ]
        plan = {
            "task": prompt.strip(),
            "type": type_hint,
            "goal": template["goal"],
            "condition": template["condition"],
            "output": template["output"],
            "method": template["method"],
            "description": template["description"],
            "steps": [
                {"title": title, "description": description}
                for title, description in template["steps"]
            ],
            "qasm": template["qasm"],
            "summary": summary,
            "operations": operations,
            "source": "adapter-validated guided template",
        }
        self._send_json(HTTPStatus.OK, {"ok": True, "plan": plan})

    def _debug_requested(self, payload: dict) -> bool:
        """Debug panel opt-in: ``{"debug": true}`` or ``?debug=1`` (任务书 §33)."""
        if payload.get("debug") is True:
            return True
        return "debug=1" in urlsplit(self.path).query

    def _agent_send(
        self,
        metadata: dict,
        decision: "web_agent.Route",
        debug: bool,
        fields: dict,
        status: int = HTTPStatus.OK,
    ) -> None:
        body = {**metadata, **fields}
        if debug:
            body["debug"] = decision.to_debug()
        self._send_json(status, body)

    def _agent_clarify(
        self,
        metadata: dict,
        decision: "web_agent.Route",
        debug: bool,
        message: str,
        code: str,
    ) -> None:
        """A clarifying question is a normal turn, not a failure (任务书 §27).

        The user sees plain language; ``code`` and router confidence stay in the
        developer layer.
        """
        self._agent_send(metadata, decision, debug, {
            "ok": True,
            "kind": "clarify",
            "intent": decision.intent,
            "code": code,
            "answer": message,
            "assistant_message": message,
            "developer_details": f"{code} router confidence = {decision.confidence:.2f}",
        })

    def _chat(self, payload: dict) -> None:
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt 不能为空")
        if len(prompt) > 8_000:
            raise ValueError("prompt 不能超过 8000 个字符")
        prompt = prompt.strip()
        scenario_id = payload.get("scenario_id")
        if scenario_id is not None and not isinstance(scenario_id, str):
            raise TypeError("scenario_id 必须是字符串")
        metadata = _chat_metadata(payload)
        context = _validated_chat_context(payload)
        debug = self._debug_requested(payload)

        decision = web_agent.route(prompt, context, scenario_id=scenario_id)

        routes = {
            "quantum_qa": ("general_qa", self._chat_quantum_qa),
            "explain_current_circuit": ("explain_circuit", self._chat_explain_circuit),
            "explain_result": ("explain_result", self._chat_explain_result),
            "modify_current_task": ("modify_task", self._chat_modify_task),
            "scenario_help": ("scenario_help", self._chat_scenario_help),
            "run_circuit": ("run_hint", self._chat_run_hint),
            "select_backend": ("select_backend", self._chat_select_backend),
            "diagnose_circuit": ("diagnose_circuit", self._chat_diagnose_circuit),
            "validate_circuit": ("validate_circuit", self._chat_validate_circuit),
            "edit_current_qasm": ("edit_current_qasm", self._chat_edit_current_qasm),
            "unknown": ("clarify", self._chat_unknown),
        }
        name, handler = routes.get(decision.intent, ("adapter_task", self._chat_adapter_task))
        if decision.requires_clarification and decision.intent != "unknown":
            name, handler = "clarify", self._chat_clarify
        web_agent.log_route(decision, name)
        handler(prompt, context, decision, metadata, debug)

    def _chat_unknown(self, prompt, context, decision, metadata, debug) -> None:
        self._agent_clarify(
            metadata, decision, debug,
            "我还不确定你想做什么。你可以告诉我想生成哪一种线路（例如叠加与测量、"
            "Bell 态、GHZ 态），或者直接问一个量子计算的概念问题。",
            "INTENT_UNCLEAR",
        )

    def _chat_clarify(self, prompt, context, decision, metadata, debug) -> None:
        message = decision.slots.get("clarification") or (
            "我还需要一点信息才能继续。可以再补充一句吗？"
        )
        self._agent_clarify(metadata, decision, debug, message, "MISSING_REQUIRED_INFO")

    def _chat_quantum_qa(self, prompt, context, decision, metadata, debug) -> None:
        try:
            answer = web_agent.answer_quantum_qa(
                prompt, context,
                no_formula=bool(decision.slots.get("no_formula")),
                question_type=decision.question_type,
                explicit_subject=decision.slots.get("explicit_subject"),
            )
        except web_agent.LLMNotConfigured:
            self._agent_send(metadata, decision, debug, {
                "ok": False,
                "kind": "error",
                "intent": decision.intent,
                "code": "LLM_NOT_CONFIGURED",
                "error": "模型服务尚未配置",
                "user_message": "这个问题需要模型服务才能回答。请先配置模型地址、密钥和模型名。",
            }, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        except Exception as exc:
            self.log_error("quantum_qa failed: %s: %s", type(exc).__name__, exc)
            self._agent_send(metadata, decision, debug, {
                "ok": False,
                "kind": "error",
                "intent": decision.intent,
                "code": "LLM_REQUEST_FAILED",
                "error": "模型调用失败",
                "user_message": "模型暂时没有响应，请稍后再试一次。",
            }, HTTPStatus.BAD_GATEWAY)
            return
        qa_debug = {
            "user_question": prompt,
            "intent": decision.intent,
            "question_type": answer.question_type,
            "explicit_subject": answer.explicit_subject,
            "current_gate": decision.slots.get("gate"),
            "selected_qa_handler": answer.selected_handler,
            "used_glossary": answer.used_glossary,
            "used_llm": answer.used_llm,
            "fallback_reason": answer.fallback_reason,
        }
        if debug:
            web_agent.log_qa_debug(qa_debug)
        fields = {
            "ok": True,
            "kind": "qa",
            "intent": "quantum_qa",
            "answer": answer.text,
            "assistant_message": answer.text,
            "answer_source": answer.source,
            "topic": answer.topic,
            "question_type": answer.question_type,
            "explicit_subject": answer.explicit_subject,
        }
        if debug:
            fields["qa_debug"] = qa_debug
        self._agent_send(metadata, decision, debug, fields)

    def _chat_explain_circuit(self, prompt, context, decision, metadata, debug) -> None:
        explanation = _circuit_explanation(prompt, context, decision.slots.get("gate"))
        if explanation is None:  # nothing on screen to talk about - answer generally
            self._chat_quantum_qa(prompt, context, decision, metadata, debug)
            return
        message, operation_ids = explanation
        # "explain_circuit" is the wire value the workspace already understands;
        # the taxonomy name stays visible in the debug payload.
        qa_debug = {
            "user_question": prompt,
            "intent": decision.intent,
            "question_type": decision.question_type,
            "explicit_subject": decision.slots.get("explicit_subject"),
            "current_gate": decision.slots.get("gate"),
            "selected_qa_handler": "current_gate_explanation",
            "used_glossary": False,
            "used_llm": False,
            "fallback_reason": None,
        }
        if debug:
            web_agent.log_qa_debug(qa_debug)
        fields = {
            "ok": True,
            "kind": "explanation",
            "intent": "explain_circuit",
            "answer": message,
            "assistant_message": message,
            "related_operation_ids": operation_ids,
            "question_type": decision.question_type,
            "explicit_subject": decision.slots.get("explicit_subject"),
        }
        if debug:
            fields["qa_debug"] = qa_debug
        self._agent_send(metadata, decision, debug, fields)

    def _chat_explain_result(self, prompt, context, decision, metadata, debug) -> None:
        result = (context or {}).get("result") or {}
        counts = result.get("counts") or {}
        if not counts:
            self._agent_clarify(
                metadata, decision, debug,
                "现在还没有运行结果。先运行一次线路，我再帮你解读测量分布。",
                "MISSING_REQUIRED_INFO",
            )
            return
        total = sum(counts.values()) or 1
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        lines = [f"这次一共运行了 {total} 次，测量结果的分布是："]
        for label, count in ordered[:8]:
            lines.append(f"· {label}：{count} 次（约 {100 * count / total:.1f}%）")
        if len(ordered) > 8:
            lines.append(f"…… 还有 {len(ordered) - 8} 种较少出现的结果。")
        lines.append("")
        if len(ordered) == 1:
            lines.append("结果每次都一样，说明这条线路的输出是确定的，没有随机性。")
        else:
            top_share = ordered[0][1] / total
            uniform = all(abs(count / total - 1 / len(ordered)) < 0.08 for _, count in ordered)
            if len(ordered) == 2 and top_share < 0.65:
                lines.append(
                    "两种结果各占大约一半，其余组合几乎不出现——这正是量子关联的典型表现："
                    "单看每个比特都是随机的，但它们总是一起变化。"
                )
            elif uniform:
                lines.append("各种结果出现的次数接近，说明线路把可能性均匀地摊开了。")
            else:
                lines.append(
                    f"出现最多的是 {ordered[0][0]}，占了约 {100 * top_share:.1f}%，"
                    "说明线路把概率明显偏向了这个结果。"
                )
        lines.append("每次运行的具体结果都是随机的，所以要重复很多次才能看出上面这种规律。")
        message = "\n".join(lines)
        fields = {
            "ok": True,
            "kind": "qa",
            "intent": "explain_result",
            "answer": message,
            "assistant_message": message,
            "answer_source": "deterministic",
            "question_type": decision.question_type or "current_result_explanation",
            "explicit_subject": decision.slots.get("explicit_subject") or "current_result",
        }
        if debug:
            qa_debug = {
                "user_question": prompt,
                "intent": decision.intent,
                "question_type": fields["question_type"],
                "explicit_subject": fields["explicit_subject"],
                "current_gate": None,
                "selected_qa_handler": "current_result_explanation",
                "used_glossary": False,
                "used_llm": False,
                "fallback_reason": None,
            }
            web_agent.log_qa_debug(qa_debug)
            fields["qa_debug"] = qa_debug
        self._agent_send(metadata, decision, debug, fields)

    def _chat_run_hint(self, prompt, context, decision, metadata, debug) -> None:
        message = (
            "当前线路已经通过校验，可以直接运行。"
            "在下面选择运行次数（shots）然后点运行，我会把真实的测量分布展示出来。"
        )
        self._agent_send(metadata, decision, debug, {
            "ok": True,
            "kind": "qa",
            "intent": "run_circuit",
            "answer": message,
            "assistant_message": message,
            "answer_source": "deterministic",
        })

    def _chat_select_backend(self, prompt, context, decision, metadata, debug) -> None:
        """Backend selection via the deterministic requirement model (任务书 §11/12/13).

        This replaces the old ``_backend_requirements`` + ``_backend_match_details``
        path, which never extracted "真机" or "账号" and so could mark a simulator
        as fully satisfying a hardware request.  The backend id always comes from
        the capability table (任务书 §14).
        """
        req = backend_selector.extract_requirements(prompt)
        result = backend_selector.match_backends(req)
        chosen = result.best_match
        if chosen is None:
            self._agent_clarify(
                metadata, decision, debug,
                "没有找到可用的运行环境，请换一种条件再试。",
                "BACKEND_NO_EXACT_MATCH",
            )
            return

        runnable_locally = chosen.kind == "simulator" and chosen.platform in ALLOWED_TARGETS
        exact = not result.no_exact_match
        matched: list[str] = []
        unmet: tuple[str, ...] = ()
        if exact:
            if req.backend_type is not None:
                matched.append("满足后端类型")
            if req.free is True:
                matched.append("完全免费")
            if req.zero_queue is True:
                matched.append("无需排队")
            if req.account_required is False:
                matched.append("无需账号")
            if req.min_qubits is not None:
                matched.append(f"支持至少 {req.min_qubits} 比特")
        else:
            # 未满足项来自选中的那个后端（best_match），而非盲目取 alternatives[0]。
            unmet = tuple(backend_selector._unmet_conditions(chosen, req))

        body = {
            "ok": True,
            "kind": "backend",
            "intent": "select_backend",
            "answer": chosen.id,
            "backend": {
                "id": chosen.id,
                "platform": chosen.platform,
                "name": chosen.name,
                "kind": chosen.kind,
                "max_qubits": chosen.max_qubits,
                "queue": chosen.queue,
                "cost": chosen.cost,
                "requires_account": chosen.requires_account,
                "notes": chosen.notes,
            },
            "adapter_target": chosen.platform if runnable_locally else None,
            "backend_requirements": req.to_hard_constraints(),
            "matched_reasons": list(matched),
            "unmet_requirements": list(unmet),
            "match_status": "full" if exact else "no_exact_match",
            "runnable_locally": runnable_locally,
        }
        if not exact:
            body["conflict_explanation"] = result.conflict_explanation
            body["alternatives"] = [
                {
                    "id": backend.id,
                    "name": backend.name,
                    "kind": backend.kind,
                    "cost": backend.cost,
                    "queue": backend.queue,
                    "requires_account": backend.requires_account,
                    "unmet": list(unmet_list),
                }
                for backend, unmet_list in result.alternatives[:3]
            ]
        self._agent_send(metadata, decision, debug, body)

    def _chat_diagnose_circuit(self, prompt, context, decision, metadata, debug) -> None:
        """诊断一段带问题的 QASM（§7）：先定位错误，再解释，不直接修。"""
        source_qasm = decision.slots.get("source_qasm") or qasm_extract.extract_qasm_from_prompt(prompt)
        issues = _diagnose_qasm_issues(source_qasm)
        if not issues:
            # 规则层没发现明显结构错误，交给 adapter 做权威校验。
            try:
                adapter.parse_qasm(source_qasm)
                lines = ["这段代码我暂时没发现明显的语法问题。"]
            except Exception as exc:  # noqa: BLE001 - 把 adapter 的校验结果转成诊断
                lines = [f"这段代码没能通过 adapter 校验：{exc}"]
        else:
            lines = ["这段代码有问题，定位如下："]
            lines.extend(f"· {issue['message']}" for issue in issues)
        repair_options = _repair_options_for_issues(source_qasm, issues)
        if repair_options:
            lines.append("")
            lines.append("存在不止一种合理修法，我不擅自替你决定。你可能想：")
            lines.extend(f"· {option['label']}" for option in repair_options)
        lines.append("")
        lines.append("如果你希望我直接修好它，说「帮我修复」即可。")
        message = "\n".join(lines)
        self._agent_send(metadata, decision, debug, {
            "ok": True,
            "kind": "qa",
            "intent": "diagnose_circuit",
            "answer": message,
            "assistant_message": message,
            "answer_source": "deterministic",
            # 第三轮 §14/§15：检查的是外部粘贴的代码，不是当前任务线路。
            "workspace_mode": "inspection",
            "inspected_qasm": source_qasm,
            "diagnosis": {
                "source_qasm": source_qasm,
                "issues": issues,
                "repair_options": repair_options,
            },
        })

    def _chat_validate_circuit(self, prompt, context, decision, metadata, debug) -> None:
        """校验一段 QASM 能否运行（§五）：只做 valid/invalid 判断，不定位不修复。"""
        source_qasm = decision.slots.get("source_qasm") or qasm_extract.extract_qasm_from_prompt(prompt)
        if not source_qasm:
            self._agent_clarify(metadata, decision, debug, "没有找到要校验的 QASM 代码。", "QASM_PARSE_ERROR")
            return
        try:
            adapter.parse_qasm(source_qasm)
            message = "这段代码可以通过 adapter 校验，语法合法。"
            valid = True
        except Exception as exc:  # noqa: BLE001
            message = f"这段代码没能通过校验：{exc}"
            valid = False
        self._agent_send(metadata, decision, debug, {
            "ok": True,
            "kind": "qa",
            "intent": "validate_circuit",
            "answer": message,
            "assistant_message": message,
            "answer_source": "deterministic",
            # 第三轮 §14/§15：校验的是外部粘贴的代码。
            "workspace_mode": "inspection",
            "inspected_qasm": source_qasm,
            "validation": {"valid": valid, "errors": [] if valid else [message], "source": "adapter.parse_qasm"},
        })

    def _chat_edit_current_qasm(self, prompt, context, decision, metadata, debug) -> None:
        """直接编辑当前 QASM 代码记号（§6 原则1）：绝不重新生成任务。

        只做少量、可安全解析的文本替换；解析不出就澄清，不擅自改语义（§25/26）。
        """
        current_qasm = (context or {}).get("current_qasm")
        if not current_qasm:
            self._agent_clarify(metadata, decision, debug, "当前还没有可编辑的线路。先给我生成或导入一条线路吧。", "MISSING_REQUIRED_INFO")
            return
        instruction = decision.slots.get("edit_instruction") or prompt
        edited = _apply_textual_edit(current_qasm, instruction)
        if edited is None:
            self._agent_clarify(metadata, decision, debug, "我没有安全解析出这条修改，可以更具体地说要改哪一处吗？（例如「把 q[1] 改成 q[0]」「删掉这行最后的分号」）", "INTENT_UNCLEAR")
            return
        # 编辑后必须重新校验：validation 立即进入 stale → checking → valid/invalid。
        try:
            _circuit, summary = _circuit_summary(edited)
            transpiled = _transpiled_outputs(edited)
            valid = True
            errors = []
        except Exception as exc:  # noqa: BLE001
            transpiled = {}
            valid = False
            errors = [str(exc)]
            issues = _diagnose_qasm_issues(edited)
            if issues:
                errors = [issue["message"] for issue in issues]
        self._agent_send(metadata, decision, debug, {
            "ok": True,
            "kind": "qasm",
            "answer": edited,
            "qasm": edited,
            "summary": _safe_summary(edited),
            "intent": "edit_current_qasm",
            "circuit": _safe_serialize(edited),
            "transpiled": transpiled,
            # 文本编辑只改代码记号，任务语义不变：原样带回 context.task，
            # 避免前端把这次响应当成"生成"而清空/替换 Current Task 面板
            # （任务书原则1：Task modification ≠ QASM text editing）。
            "task": (context or {}).get("task"),
            "validation": {
                "valid": valid,
                "errors": errors,
                "source": "adapter.parse_qasm+transpile",
                "targets": sorted(ALLOWED_TARGETS),
            },
            "assistant_message": "已按你的要求直接修改了当前线路的代码，并重新检查。" if valid
                else "已修改，但修改后的代码有问题：" + "；".join(errors),
            "action": {
                "type": "edit_current_qasm",
                "updated_panels": ["qasm", "validation"],
                "primary_panel": "validation",
            },
        })

    def _chat_scenario_help(self, prompt, context, decision, metadata, debug) -> None:
        template = PLAN_TEMPLATES.get(SCENARIO_TEMPLATE_KEYS.get(decision.scenario_id or ""))
        if template is None:
            self._chat_unknown(prompt, context, decision, metadata, debug)
            return
        runnable = decision.scenario_id in DIRECTLY_SUPPORTED_SCENARIOS
        if runnable:
            # 测量/关联：真正可运行示例（§11/§12 测试）。
            qasm = template["qasm"]
            circuit, summary = _circuit_summary(qasm)
            circuit_payload = _serialize_circuit(circuit)
            transpiled = _transpiled_outputs(qasm)
            self._agent_send(metadata, decision, debug, {
                "ok": True,
                "kind": "qasm",
                "answer": qasm,
                "qasm": qasm,
                "summary": summary,
                "intent": "generate_circuit",
                "scenario_id": decision.scenario_id,
                "direct_generation_supported": True,
                "assumptions": [template["description"]],
                "task": {
                    "type": "generate_circuit",
                    "goal": template["goal"],
                    "qubits": summary["qubits"],
                    "measurement": _measurement_task_value(circuit_payload),
                },
                "circuit": circuit_payload,
                "transpiled": transpiled,
                "validation": {
                    "valid": True, "errors": [],
                    "source": "adapter.parse_qasm+transpile",
                    "targets": sorted(ALLOWED_TARGETS),
                },
                "explanation_steps": _explanation_steps(circuit_payload),
                "repair": None,
                "backend_recommendation": _default_backend_recommendation(summary["qubits"]),
            })
            return
        # 查找/优化：概念解释模式（§30/§31）。不生成演示线路，说明还缺什么信息，
        # 不把「任意排程/搜索」硬说成能直接变成量子任务。
        lines = [template["description"], ""]
        lines.extend(f"{index}. {title}：{body}" for index, (title, body) in enumerate(template["steps"], 1))
        lines.append("")
        lines.append("我可以：1) 先解释这类问题如何映射到量子计算；2) 用一个小例子演示思路。你想要哪一种？")
        message = "\n".join(lines)
        self._agent_send(metadata, decision, debug, {
            "ok": True,
            "kind": "scenario",
            "intent": "scenario_help",
            "scenario_id": decision.scenario_id,
            "answer": message,
            "assistant_message": message,
            "direct_generation_supported": False,
        })

    def _chat_modify_task(self, prompt, context, decision, metadata, debug) -> None:
        context_qubits = (
            context["circuit_payload"]["qubits"]
            if context and context.get("circuit_payload")
            else None
        )
        measurement_only = bool(
            context and context.get("circuit")
            and re.fullmatch(
                r"\s*(?:请)?(?:改成)?(?:只?测量|不要测量|不测量|全部测量|全测量).*?[。.!！]?\s*",
                prompt,
                re.IGNORECASE,
            )
        )
        requested_pairs = _requested_measurements(prompt, context_qubits if measurement_only else None)
        if measurement_only and requested_pairs is None:
            raise ValueError("暂时无法确定要测量哪些量子比特；请使用“只测量 q0、q1”“全部测量”或“不要测量”。")
        if measurement_only:
            self._chat_adapter_task(
                prompt, context, decision, metadata, debug,
                requested_pairs=requested_pairs,
                response_intent="modify_current_task",
                precomputed_answer=_qasm_with_measurements(context["circuit"], requested_pairs),
            )
            return
        effective_prompt = _modify_generation_prompt(prompt, context)
        self._chat_adapter_task(
            prompt, context, decision, metadata, debug,
            effective_prompt=effective_prompt,
            requested_pairs=requested_pairs,
            response_intent="modify_current_task" if effective_prompt else None,
        )

    def _chat_adapter_task(
        self,
        prompt,
        context,
        decision,
        metadata,
        debug,
        *,
        effective_prompt=None,
        requested_pairs=None,
        response_intent=None,
        precomputed_answer=None,
    ) -> None:
        """Hand a circuit/backend task to the untouched competition core."""
        measurement_only = precomputed_answer is not None
        answer = precomputed_answer
        if requested_pairs is None and not measurement_only:
            requested_pairs = _requested_measurements(prompt)
        # 网页运行上限：在进入任何生成路径前拦截，避免 999 比特这类越界落到
        # adapter 的 L2SemanticError -> 500（用户错误被误报成内部失败，§27）。
        if decision.slots.get("qubits") is not None and decision.slots["qubits"] > MAX_QUBITS:
            raise ValueError(f"网页运行最多支持 {MAX_QUBITS} 个量子比特")
        # 叠加态是确定性线路，直接构造（见 _superposition_qasm 注释），不走 LLM，
        # 也不依赖 adapter 认识这个目标名。必须在 LLM 闸门之前，这样即使未启用
        # 模型，这条新手线路也能生成（任务书 §30）。部分测量由下方
        # _qasm_with_measurements 在生成后重写。
        if answer is None and decision.slots.get("goal") == "superposition":
            answer = _superposition_qasm(decision.slots.get("qubits") or 1)
        if answer is None:
            if not web_agent.llm_enabled():
                self._error(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "自然语言功能尚未由部署者启用；仍可直接导入并运行 OpenQASM 2.0",
                    "LLM_DISABLED",
                )
                return
            # 规则解析出明确目标态时，用明确措辞进 adapter（修「新手能看懂的线路」
            # 「最简单的纠缠例子」被 adapter 判 AMBIGUOUS/UNGROUNDED 的问题）。
            # 但若用户显式指定了部分测量，沿用原流程：先剥离测量子句，生成后再补回，
            # 否则会错误地覆盖成全测量。
            resolved = None if requested_pairs is not None else _generation_prompt_from_route(decision)
            agent_prompt = effective_prompt or resolved or prompt
            if requested_pairs is not None:
                agent_prompt = re.sub(r"(?:，|,)?\s*只测量.*$", "，且不要测量", agent_prompt)
            # A missing LOOMQ_LLM_* configuration surfaces as
            # LoomQLLMConfigurationError from the adapter; do_POST maps it to
            # LLM_NOT_CONFIGURED (任务书 §26) instead of a bare 500.
            with runtime_config.use_runtime_config_if_set():
                answer = adapter.agent_chat(agent_prompt)
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Agent 没有返回可展示的内容")
        answer = answer.strip()
        if answer.startswith("ERROR["):
            matched = re.match(r"ERROR\[([A-Z_]+)\]", answer)
            adapter_code = matched.group(1) if matched else "GENERATION"
            self._agent_send(metadata, decision, debug, {
                "ok": False,
                "kind": "error",
                "intent": decision.intent,
                "code": WEB_ERROR_CODES.get(adapter_code, "MISSING_REQUIRED_INFO"),
                "adapter_code": adapter_code,
                "error": "这个任务暂时没能完成",
                "user_message": ADAPTER_ERROR_MESSAGES.get(
                    adapter_code,
                    "这个任务我暂时没能完成。可以换一种说法，或者说得更具体一点吗？",
                ),
                # 内部错误原文只进开发层（任务书 §27/§33），不向普通用户泄露。
                **({"developer_details": answer} if debug else {}),
            }, HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        if answer.startswith("OPENQASM 2.0;"):
            circuit, summary = _circuit_summary(answer)
            if requested_pairs is not None and not measurement_only:
                answer = _qasm_with_measurements(circuit, requested_pairs)
                circuit, summary = _circuit_summary(answer)
            transpiled = _transpiled_outputs(answer)
            circuit_payload = _serialize_circuit(circuit)
            intent = response_intent or decision.intent
            if intent not in {"generate_circuit", "repair_circuit", "modify_current_task"}:
                intent = _qasm_intent(prompt)
            # The router already separated prose from code (任务书 §15); only fall
            # back to the local scan when it had nothing to say.
            before = None
            if intent == "repair_circuit":
                before = decision.slots.get("source_qasm") or _extract_repair_source(prompt)
            self._agent_send(metadata, decision, debug, {
                "ok": True,
                "kind": "qasm",
                "answer": answer,
                "qasm": answer,
                "summary": summary,
                "intent": intent,
                # 6.1 - when we defaulted something, say so out loud.
                "assumptions": list(decision.assumptions),
                "task": {
                    "type": intent,
                    "goal": GOAL_LABELS.get(decision.slots.get("goal") or ""),
                    "qubits": summary["qubits"],
                    "measurement": _measurement_task_value(circuit_payload),
                },
                "circuit": circuit_payload,
                "transpiled": transpiled,
                "validation": {
                    "valid": True, "errors": [],
                    "source": "adapter.parse_qasm+transpile",
                    "targets": sorted(ALLOWED_TARGETS),
                },
                "explanation_steps": _explanation_steps(circuit_payload),
                "repair": ({
                    "before": before,
                    "proposed_qasm": answer,
                    "issues": _repair_issues(before),
                    # 第二轮 §24：结构化 diagnostics 是必需字段（带 severity/line）。
                    "diagnostics": _diagnose_qasm_issues(before) or _repair_issues(before),
                    "status": "awaiting_apply",
                } if intent == "repair_circuit" else None),
                "backend_recommendation": _default_backend_recommendation(summary["qubits"]),
                # 第二轮 §6：修改类响应带结构化 UI action，前端据此高亮/滚动面板。
                "action": ({
                    "type": "update_task",
                    "updated_panels": ["current_task", "circuit", "validation"],
                    "primary_panel": "current_task",
                } if intent == "modify_current_task" else None),
            })
            return
        # Backend selection is routed to _chat_select_backend (backend_selector),
        # so a bare backend id should never reach here from the adapter.  If it
        # somehow does, treat it as prose rather than re-running the old,
        # incomplete matcher that could overstate a simulator as satisfying
        # "真机" (任务书 §12/§13/§14).
        # Anything else the adapter said in prose.  "text" used to reach a
        # frontend that had no branch for it and threw; "qa" renders normally.
        self._agent_send(metadata, decision, debug, {
            "ok": True,
            "kind": "qa",
            "intent": decision.intent,
            "answer": answer,
            "assistant_message": answer,
            "answer_source": "adapter",
        })

    def _serve_static(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        candidate = (STATIC_ROOT / relative).resolve()
        try:
            candidate.relative_to(STATIC_ROOT.resolve())
        except ValueError:
            self._error(HTTPStatus.FORBIDDEN, "路径无效", "FORBIDDEN")
            return
        if not candidate.is_file():
            self._error(HTTPStatus.NOT_FOUND, "页面不存在", "NOT_FOUND")
            return
        data = candidate.read_bytes()
        if candidate.suffix.lower() == ".html":
            html = data.decode("utf-8")
            has_app_script = re.search(
                r"<script\b[^>]*\bsrc\s*=\s*['\"][^'\"]*app\.js(?:\?[^'\"]*)?['\"]",
                html,
                re.IGNORECASE,
            )
            if not has_app_script:
                html = html.replace("</body>", '<script src="app.js?v=20260820-1"></script></body>')
            data = html.encode("utf-8")
        mime = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if mime.startswith("text/") or mime in {"application/javascript", "application/json"}:
            mime += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        no_cache = candidate.suffix.lower() in {".html", ".js"}
        self.send_header("Cache-Control", "no-cache" if no_cache else "public, max-age=3600")
        self.end_headers()
        self.wfile.write(data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QuantumHelper adapter web service")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), QuantumHelperHandler)
    print(f"QuantumHelper running at http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
