#!/usr/bin/env python3
"""LoomQ submission adapter.

实现思路：把 OpenQASM 2.0 作为唯一源语言，先解析成统一的电路中间表示
（Circuit + Gate），再分两条路处理：

- ``transpile``  把 IR 转译为三种后端的原生 IR 文本（纯文本转译，零依赖）；
- ``run``        用自带的无噪声状态向量模拟器执行 IR，得到统一 Schema 结果。

两条路共享同一个 IR 与同一套门定义，因此转译结果与执行结果在语义上必然一致。
"""

import ast
import json
import math
import os
import random
import re
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

SUPPORTED_TARGETS = ("spinq", "originq", "braket")


# --------------------------------------------------------------------------- #
# 1. 电路中间表示（IR）
# --------------------------------------------------------------------------- #

@dataclass
class Gate:
    name: str                 # 小写门名（measure 为特殊门）
    params: List[str]         # 参数原文，如 ["pi/2"]
    params_val: List[float]   # 参数数值（仅模拟器使用）
    qubits: List[int]         # 作用的量子比特索引
    cbits: List[int]          # 仅 measure 使用：写入的经典比特索引


@dataclass
class Circuit:
    n_qubits: int
    n_cbits: int
    gates: List[Gate]


# --------------------------------------------------------------------------- #
# 2. OpenQASM 2.0 解析器
# --------------------------------------------------------------------------- #

def _parse_param(text: str) -> float:
    """把 QASM 参数表达式（支持 pi 与 + - * / ** 及括号）安全求值为浮点数。"""

    def eval_node(node):
        if isinstance(node, ast.Expression):
            return eval_node(node.body)
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id == "pi":
            return math.pi
        if isinstance(node, ast.UnaryOp):
            value = eval_node(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            left = eval_node(node.left)
            right = eval_node(node.right)
            op = node.op
            if isinstance(op, ast.Add):
                return left + right
            if isinstance(op, ast.Sub):
                return left - right
            if isinstance(op, ast.Mult):
                return left * right
            if isinstance(op, ast.Div):
                return left / right
            if isinstance(op, ast.Pow):
                return left ** right
        raise ValueError("unsupported parameter expression: %s" % text)

    return eval_node(ast.parse(text.strip(), mode="eval"))


_GATE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(([^)]*)\))?\s*(.*)$")
_ARG_RE = re.compile(r"(\w+)\s*\[\s*(\d+)\s*\]")
_QREG_RE = re.compile(r"\bqreg\s+\w+\s*\[\s*(\d+)\s*\]")
_CREG_RE = re.compile(r"\bcreg\s+\w+\s*\[\s*(\d+)\s*\]")
_MEASURE_RE = re.compile(
    r"measure\s+(\w+)\s*(?:\[\s*(\d+)\s*\])?\s*->\s*(\w+)\s*(?:\[\s*(\d+)\s*\])?"
)


def parse_qasm2(qasm_str: str) -> Circuit:
    """把 OpenQASM 2.0 文本解析为 Circuit 中间表示。"""
    text = re.sub(r"//[^\n]*", "", qasm_str)
    statements = [s.strip() for s in text.split(";") if s.strip()]

    n_qubits = 0
    n_cbits = 0
    for stmt in statements:
        match_q = _QREG_RE.search(stmt)
        if match_q:
            n_qubits = max(n_qubits, int(match_q.group(1)))
        match_c = _CREG_RE.search(stmt)
        if match_c:
            n_cbits = max(n_cbits, int(match_c.group(1)))

    gates: List[Gate] = []
    for stmt in statements:
        low = stmt.lower()
        if (
            low.startswith("openqasm")
            or low.startswith("include")
            or low.startswith("qreg")
            or low.startswith("creg")
            or low.startswith("barrier")
        ):
            continue

        match_m = _MEASURE_RE.match(stmt)
        if match_m:
            _qname, qidx, _cname, cidx = match_m.groups()
            if qidx is None:
                for i in range(n_qubits):
                    gates.append(Gate("measure", [], [], [i], [i]))
            else:
                qi = int(qidx)
                ci = int(cidx) if cidx is not None else qi
                gates.append(Gate("measure", [], [], [qi], [ci]))
            continue

        match_g = _GATE_RE.match(stmt)
        if not match_g:
            continue
        name = match_g.group(1).lower()
        params = (
            [p.strip() for p in match_g.group(2).split(",")]
            if match_g.group(2)
            else []
        )
        args = _ARG_RE.findall(match_g.group(3))
        qubits = [int(idx) for _, idx in args]
        gates.append(
            Gate(
                name=name,
                params=params,
                params_val=[_parse_param(p) for p in params],
                qubits=qubits,
                cbits=[],
            )
        )

    return Circuit(n_qubits=n_qubits, n_cbits=n_cbits, gates=gates)


# --------------------------------------------------------------------------- #
# 3. 无噪声状态向量模拟器（覆盖 12 门白名单）
# --------------------------------------------------------------------------- #

def _apply_gate(state: List[complex], gate: Gate, size: int) -> None:
    name = gate.name
    if name == "h":
        k = gate.qubits[0]
        mask = 1 << k
        inv = 1.0 / math.sqrt(2.0)
        for i in range(size):
            if i & mask:
                continue
            a0 = state[i]
            a1 = state[i | mask]
            state[i] = inv * (a0 + a1)
            state[i | mask] = inv * (a0 - a1)
    elif name == "x":
        k = gate.qubits[0]
        mask = 1 << k
        for i in range(size):
            if i & mask:
                continue
            state[i], state[i | mask] = state[i | mask], state[i]
    elif name == "s":
        k = gate.qubits[0]
        mask = 1 << k
        for i in range(size):
            if i & mask:
                state[i] *= 1j
    elif name == "sdg":
        k = gate.qubits[0]
        mask = 1 << k
        for i in range(size):
            if i & mask:
                state[i] *= -1j
    elif name == "t":
        k = gate.qubits[0]
        mask = 1 << k
        phase = (1.0 + 1j) / math.sqrt(2.0)
        for i in range(size):
            if i & mask:
                state[i] *= phase
    elif name == "tdg":
        k = gate.qubits[0]
        mask = 1 << k
        phase = (1.0 - 1j) / math.sqrt(2.0)
        for i in range(size):
            if i & mask:
                state[i] *= phase
    elif name == "rz":
        k = gate.qubits[0]
        mask = 1 << k
        theta = gate.params_val[0]
        c = math.cos(theta / 2.0)
        s = math.sin(theta / 2.0)
        p0 = complex(c, -s)
        p1 = complex(c, s)
        for i in range(size):
            state[i] *= p1 if (i & mask) else p0
    elif name == "ry":
        k = gate.qubits[0]
        mask = 1 << k
        theta = gate.params_val[0]
        c = math.cos(theta / 2.0)
        s = math.sin(theta / 2.0)
        for i in range(size):
            if i & mask:
                continue
            a0 = state[i]
            a1 = state[i | mask]
            state[i] = c * a0 - s * a1
            state[i | mask] = s * a0 + c * a1
    elif name == "cx":
        a, b = gate.qubits[0], gate.qubits[1]
        mask_a = 1 << a
        mask_b = 1 << b
        for i in range(size):
            if (i & mask_a) and not (i & mask_b):
                j = i | mask_b
                state[i], state[j] = state[j], state[i]
    elif name == "cu1":
        a, b = gate.qubits[0], gate.qubits[1]
        mask_a = 1 << a
        mask_b = 1 << b
        theta = gate.params_val[0]
        phase = complex(math.cos(theta), math.sin(theta))
        for i in range(size):
            if (i & mask_a) and (i & mask_b):
                state[i] *= phase
    elif name == "swap":
        a, b = gate.qubits[0], gate.qubits[1]
        mask_a = 1 << a
        mask_b = 1 << b
        for i in range(size):
            if not (i & mask_a) and (i & mask_b):
                j = i ^ mask_a ^ mask_b
                state[i], state[j] = state[j], state[i]
    elif name == "ccx":
        a, b, c = gate.qubits[0], gate.qubits[1], gate.qubits[2]
        mask_a = 1 << a
        mask_b = 1 << b
        mask_c = 1 << c
        for i in range(size):
            if (i & mask_a) and (i & mask_b) and not (i & mask_c):
                j = i | mask_c
                state[i], state[j] = state[j], state[i]
    else:
        raise ValueError("unsupported gate: %s" % name)


def _measure_state(state: List[complex], qubit: int, size: int) -> int:
    mask = 1 << qubit
    p0 = 0.0
    for i in range(size):
        if not (i & mask):
            p0 += abs(state[i]) ** 2
    bit = 0 if random.random() < p0 else 1
    if bit == 1:
        for i in range(size):
            if not (i & mask):
                state[i] = 0.0
    else:
        for i in range(size):
            if i & mask:
                state[i] = 0.0
    norm = math.sqrt(sum(abs(a) ** 2 for a in state))
    if norm > 0.0:
        for i in range(size):
            state[i] /= norm
    return bit


def simulate(circuit: Circuit, shots: int) -> Dict[str, int]:
    """无噪声状态向量采样。counts 的 key 最右字符对应 c[0]（little 位序）。"""
    size = 1 << circuit.n_qubits
    counts: Dict[str, int] = {}
    for _ in range(shots):
        state = [0.0 + 0.0j] * size
        state[0] = 1.0 + 0.0j
        cvals: Dict[int, int] = {}
        for gate in circuit.gates:
            if gate.name == "measure":
                cvals[gate.cbits[0]] = _measure_state(state, gate.qubits[0], size)
            else:
                _apply_gate(state, gate, size)
        key = "".join(str(cvals.get(j, 0)) for j in reversed(range(circuit.n_cbits)))
        counts[key] = counts.get(key, 0) + 1
    return counts


# --------------------------------------------------------------------------- #
# 4. 转译器（IR -> 目标原生 IR 文本）
# --------------------------------------------------------------------------- #

_GATE_MAP_BRAKET = {
    "h": "h", "x": "x", "s": "s", "sdg": "sdg", "t": "t", "tdg": "tdg",
    "rz": "rz", "ry": "ry", "cx": "cx", "cu1": "cp", "swap": "swap", "ccx": "ccx",
}

_GATE_MAP_ORIGINQ = {
    "h": "H", "x": "X", "s": "S", "sdg": "SDAG", "t": "T", "tdg": "TDAG",
    "rz": "RZ", "ry": "RY", "cx": "CNOT", "cu1": "CU1", "swap": "SWAP", "ccx": "TOFFOLI",
}


def _is_full_measure(circuit: Circuit) -> bool:
    measures = [g for g in circuit.gates if g.name == "measure"]
    if len(measures) != circuit.n_qubits:
        return False
    mapping = {g.qubits[0]: g.cbits[0] for g in measures}
    return all(mapping.get(i) == i for i in range(circuit.n_qubits))


def _format_params(gate: Gate) -> str:
    return "(" + ",".join(gate.params) + ")" if gate.params else ""


def _to_qasm2(circuit: Circuit) -> str:
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[%d];" % circuit.n_qubits,
        "creg c[%d];" % circuit.n_cbits,
    ]
    if _is_full_measure(circuit):
        for gate in circuit.gates:
            if gate.name == "measure":
                continue
            qubits = ",".join("q[%d]" % i for i in gate.qubits)
            lines.append("%s%s %s;" % (gate.name, _format_params(gate), qubits))
        lines.append("measure q -> c;")
    else:
        for gate in circuit.gates:
            if gate.name == "measure":
                lines.append("measure q[%d] -> c[%d];" % (gate.qubits[0], gate.cbits[0]))
            else:
                qubits = ",".join("q[%d]" % i for i in gate.qubits)
                lines.append("%s%s %s;" % (gate.name, _format_params(gate), qubits))
    return "\n".join(lines) + "\n"


def _to_qasm3(circuit: Circuit) -> str:
    lines = [
        "OPENQASM 3.0;",
        'include "stdgates.inc";',
        "qubit[%d] q;" % circuit.n_qubits,
        "bit[%d] c;" % circuit.n_cbits,
    ]
    if _is_full_measure(circuit):
        for gate in circuit.gates:
            if gate.name == "measure":
                continue
            mapped = _GATE_MAP_BRAKET[gate.name]
            qubits = ", ".join("q[%d]" % i for i in gate.qubits)
            lines.append("%s%s %s;" % (mapped, _format_params(gate), qubits))
        lines.append("c = measure q;")
    else:
        for gate in circuit.gates:
            if gate.name == "measure":
                lines.append("c[%d] = measure q[%d];" % (gate.cbits[0], gate.qubits[0]))
            else:
                mapped = _GATE_MAP_BRAKET[gate.name]
                qubits = ", ".join("q[%d]" % i for i in gate.qubits)
                lines.append("%s%s %s;" % (mapped, _format_params(gate), qubits))
    return "\n".join(lines) + "\n"


def _to_originir(circuit: Circuit) -> str:
    lines = [
        "QINIT %d" % circuit.n_qubits,
        "CREG %d" % circuit.n_cbits,
    ]
    for gate in circuit.gates:
        if gate.name == "measure":
            lines.append("MEASURE q[%d],c[%d]" % (gate.qubits[0], gate.cbits[0]))
            continue
        mapped = _GATE_MAP_ORIGINQ[gate.name]
        qubits = ",".join("q[%d]" % i for i in gate.qubits)
        lines.append("%s%s %s" % (mapped, _format_params(gate), qubits))
    return "\n".join(lines) + "\n"


_EMITTERS = {
    "spinq": _to_qasm2,
    "braket": _to_qasm3,
    "originq": _to_originir,
}


def _circuit_depth(circuit: Circuit) -> int:
    layers = [0] * circuit.n_qubits
    depth = 0
    for gate in circuit.gates:
        if gate.name == "measure":
            continue
        level = max((layers[q] for q in gate.qubits), default=0) + 1
        for q in gate.qubits:
            layers[q] = level
        depth = max(depth, level)
    return depth


# --------------------------------------------------------------------------- #
# 5. 提交契约入口
# --------------------------------------------------------------------------- #

def transpile(qasm_str: str, target: str) -> str:
    """将 OpenQASM 2.0 转译为目标后端的原生指令字符串。"""
    if target not in SUPPORTED_TARGETS:
        raise ValueError("unknown target: %s" % target)
    circuit = parse_qasm2(qasm_str)
    return _EMITTERS[target](circuit)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """运行电路并返回符合大赛标准 Schema 的字典结果。"""
    if target not in SUPPORTED_TARGETS:
        raise ValueError("unknown target: %s" % target)
    circuit = parse_qasm2(qasm_str)
    counts = simulate(circuit, shots)

    backend_name = {
        "spinq": "spinq_taurus_simulator",
        "originq": "originq_local_simulator",
        "braket": "braket_local_simulator",
    }[target]

    non_measure = [g for g in circuit.gates if g.name != "measure"]
    return {
        "backend": backend_name,
        "job_id": str(uuid.uuid4()),
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "meta": {
            "transpiled_gates": len(non_measure),
            "depth": _circuit_depth(circuit),
        },
    }


# --------------------------------------------------------------------------- #
# 6. L2 智能体（自然语言 → QASM / 修复 / 选后端）
# --------------------------------------------------------------------------- #

_SYSTEM_PROMPT = """你是 LoomQ 量子编程助手，帮助没有量子背景的用户使用量子计算机。\
根据用户的自然语言需求，你完成以下三类任务之一：

【任务一：生成量子电路】用户描述想要的量子态或操作，你生成完整、可直接运行的 OpenQASM 2.0 代码。

【任务二：修复量子电路】用户给出一段有错误的 OpenQASM 2.0 代码，并通常声明期望的目标态。\
你修复其中的错误，同时严格保持用户声明的意图不变。

【任务三：选择后端】用户描述运行约束（比特数、排队、成本、真机/模拟器等），\
你从下方能力表中选择满足全部约束的后端。

——OpenQASM 2.0 编写规则——
1. 版本声明行必须是：OPENQASM 2.0;（注意结尾分号，版本是 2.0 不是 3.0）
2. 必须包含 include "qelib1.inc";
3. 寄存器声明：qreg q[N]; 与 creg c[N];
4. 只允许使用以下 12 个门：h, x, s, sdg, t, tdg, rz(θ), ry(θ), cx, cu1(θ), swap, ccx
5. 参数门写法：rz(pi/2) q[0];（角度可用 pi 表达式，如 pi/2、pi/4）
6. 全测量写法：measure q -> c;

——后端能力表（选择后端的唯一依据，严格按约束筛选，禁止自由发挥）——
| 规范标识 | 类型 | 比特上限 | 排队 | 费用 | 账号 |
| spinq_taurus_simulator | 模拟器 | 24 | 无排队 | 免费 | 无需 |
| spinq_cloud_qpu | 真机 | 8 | 分钟~小时 | 免费额度 | 需注册 |
| originq_local_simulator | 模拟器 | 30 | 无排队 | 免费 | 无需 |
| originq_wukong | 真机 | 72 | 小时级 | 免费额度 | 需注册+Token |
| braket_local_simulator | 模拟器 | 25 | 无排队 | 免费 | 无需 |
| braket_cloud | 云端 | 34 | 分钟~小时 | 付费 | 需AWS账号 |

筛选规则：先看比特上限（max_qubits ≥ 需求比特数），再看排队与费用约束；\
"真机"要求类型为真机(qpu)，"零排队"要求排队为无排队，多约束需同时满足。\
若没有后端满足全部约束，如实说明"超出所有可用后端能力"，并给出最接近的替代。

——输出格式（严格遵守）——
任务一、任务二：输出一个代码块（三个反引号包裹，语言标记 qasm），\
内容是完整 OpenQASM 2.0 代码，以 OPENQASM 2.0; 开头。可附一行简短中文说明。
任务三：输出规范标识（上表第一列的原文，如 braket_local_simulator），并附一句理由。"""

_BACKEND_IDS = (
    "spinq_taurus_simulator",
    "spinq_cloud_qpu",
    "originq_local_simulator",
    "originq_wukong",
    "braket_local_simulator",
    "braket_cloud",
)

_QASM_RE = re.compile(r"OPENQASM\s+2\.0;.*?(?=^\s*```|\Z)", re.DOTALL | re.MULTILINE)

_MAX_RETRIES = 3

_L2_REQUIRED_ENV = ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")


def _chat_completion(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    missing = [name for name in _L2_REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "missing required LoomQ L2 environment variable(s): " + ", ".join(missing)
        )
    base_url = os.environ["LOOMQ_LLM_BASE_URL"].rstrip("/")
    api_key = os.environ["LOOMQ_LLM_API_KEY"]
    model = os.environ["LOOMQ_LLM_MODEL"]
    try:
        timeout = float(os.environ.get("LOOMQ_LLM_TIMEOUT_SECONDS", "120"))
        max_output = int(os.environ.get("LOOMQ_LLM_MAX_OUTPUT_TOKENS", "4096"))
    except ValueError as exc:
        raise RuntimeError("invalid LoomQ L2 numeric environment variable") from exc
    if timeout <= 0 or max_output <= 0:
        raise RuntimeError("LoomQ L2 timeout and output-token limit must be positive")

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "temperature": 0,
        "max_tokens": max_output,
    }
    if model == "deepseek-v4-flash":
        payload["thinking"] = {"type": "disabled"}
    request = urllib.request.Request(
        base_url + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError("LoomQ L2 API returned HTTP %d" % exc.code) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("LoomQ L2 API is unreachable") from exc


def _chat(messages: List[Dict[str, str]]) -> str:
    response = _chat_completion(messages)
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("unexpected LLM response format") from exc


def _extract_qasm(reply: str) -> str:
    match = _QASM_RE.search(reply)
    return match.group(0).strip() if match else ""


def _validate_qasm(qasm: str) -> str:
    """返回空串表示语法通过，否则返回错误描述。"""
    try:
        circuit = parse_qasm2(qasm)
    except Exception as exc:
        return "%s: %s" % (type(exc).__name__, exc)
    if circuit.n_qubits <= 0:
        return "缺少量子寄存器声明 qreg q[N]"
    if circuit.n_cbits <= 0:
        return "缺少经典寄存器声明 creg c[N]"
    if not circuit.gates:
        return "电路没有任何门或测量语句"
    for gate in circuit.gates:
        if gate.name == "measure":
            for c in gate.cbits:
                if c >= circuit.n_cbits:
                    return "经典比特索引越界: c[%d]" % c
            continue
        if gate.name not in _GATE_MAP_BRAKET:
            return "不支持的量子门: %s（白名单：h x s sdg t tdg rz ry cx cu1 swap ccx）" % gate.name
        for q in gate.qubits:
            if q >= circuit.n_qubits:
                return "量子比特索引越界: q[%d]，寄存器只有 %d 个比特" % (q, circuit.n_qubits)
    return ""


def _extract_backend_id(reply: str) -> str:
    for backend_id in _BACKEND_IDS:
        if backend_id in reply:
            return backend_id
    return ""


def agent_chat(prompt: str) -> str:
    """从 LOOMQ_LLM_* 环境变量读取模型配置，返回智能体响应文本。"""
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    reply = _chat(messages)

    for _ in range(_MAX_RETRIES):
        qasm = _extract_qasm(reply)
        if qasm:
            error = _validate_qasm(qasm)
            if not error:
                break
            messages.append({"role": "assistant", "content": reply})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "你输出的 QASM 有错误：%s。请重新输出修正后的完整 OpenQASM 2.0 代码，"
                        "放在代码块内，并以 OPENQASM 2.0; 开头。" % error
                    ),
                }
            )
        else:
            backend_id = _extract_backend_id(reply)
            if backend_id:
                break
            messages.append({"role": "assistant", "content": reply})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "请严格按照输出格式回复：生成/修复电路时输出以 OPENQASM 2.0; 开头的"
                        " OpenQASM 代码块；选择后端时输出能力表中的规范标识。"
                    ),
                }
            )
        reply = _chat(messages)

    return reply


# --------------------------------------------------------------------------- #
# 7. L3 混合编译（Hybrid-QASM → 量子操作序列 + RISC-V 汇编）
# --------------------------------------------------------------------------- #

def _split_hybrid(text: str) -> Tuple[str, str]:
    """把 Hybrid-QASM 拆成 (纯量子 QASM 文本, 经典块内容)。"""
    match = re.search(r"classical\s*\{", text)
    if not match:
        return text, ""
    start = match.end()
    depth = 1
    index = start
    while index < len(text) and depth > 0:
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
        index += 1
    classical_text = text[start:index - 1]
    quantum_text = text[:match.start()] + text[index:]
    return quantum_text, classical_text


_TOKEN_SPEC = [
    ("IF", r"if\b"),
    ("ELSE", r"else\b"),
    ("NUM", r"\d+"),
    ("MEAS", r"c\[\d+\]"),
    ("REG", r"r[1-9]"),
    ("EQEQ", r"=="),
    ("NEQ", r"!="),
    ("ASSIGN", r"="),
    ("PLUS", r"\+"),
    ("MINUS", r"-"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("LBRACE", r"\{"),
    ("RBRACE", r"\}"),
    ("SEMI", r";"),
    ("SKIP", r"\s+"),
]

_TOKEN_MASTER = re.compile(
    "|".join("(?P<%s>%s)" % (name, pattern) for name, pattern in _TOKEN_SPEC)
)


def _tokenize_classical(text: str) -> List[Tuple[str, str]]:
    text = re.sub(r"//[^\n]*", "", text)
    tokens: List[Tuple[str, str]] = []
    for match in _TOKEN_MASTER.finditer(text):
        kind = match.lastgroup
        if kind != "SKIP":
            tokens.append((kind, match.group()))
    return tokens


class _ClassicalParser:
    """经典块迷你文法的递归下降解析器。"""

    def __init__(self, tokens: List[Tuple[str, str]]):
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> Tuple[str, str]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else ("EOF", "")

    def _next(self) -> Tuple[str, str]:
        token = self._peek()
        self.pos += 1
        return token

    def _expect(self, kind: str) -> None:
        actual, value = self._next()
        if actual != kind:
            raise ValueError("expected %s, got %s" % (kind, value or actual))

    def parse_program(self) -> List[Tuple]:
        statements: List[Tuple] = []
        while self.pos < len(self.tokens):
            statements.append(self._parse_stmt())
        return statements

    def _parse_stmt(self) -> Tuple:
        kind, _ = self._peek()
        if kind == "IF":
            return self._parse_if()
        return self._parse_assign()

    def _parse_assign(self) -> Tuple:
        kind, value = self._next()
        if kind != "REG":
            raise ValueError("expected register, got %s" % value)
        reg_idx = int(value[1:])
        self._expect("ASSIGN")
        expr = self._parse_expr()
        self._expect("SEMI")
        return ("assign", reg_idx, expr)

    def _parse_if(self) -> Tuple:
        self._expect("IF")
        self._expect("LPAREN")
        cond = self._parse_cond()
        self._expect("RPAREN")
        self._expect("LBRACE")
        then_stmts = self._parse_until("RBRACE")
        self._expect("RBRACE")
        else_stmts: List[Tuple] = []
        if self._peek()[0] == "ELSE":
            self._next()
            self._expect("LBRACE")
            else_stmts = self._parse_until("RBRACE")
            self._expect("RBRACE")
        return ("if", cond, then_stmts, else_stmts)

    def _parse_until(self, stop_kind: str) -> List[Tuple]:
        statements: List[Tuple] = []
        while self.pos < len(self.tokens) and self._peek()[0] != stop_kind:
            statements.append(self._parse_stmt())
        return statements

    def _parse_cond(self) -> Tuple:
        left = self._parse_operand()
        kind, _ = self._next()
        if kind not in ("EQEQ", "NEQ"):
            raise ValueError("expected == or != in condition")
        op = "==" if kind == "EQEQ" else "!="
        right = self._parse_operand()
        return ("cmp", op, left, right)

    def _parse_expr(self) -> Tuple:
        node = self._parse_operand()
        while self._peek()[0] in ("PLUS", "MINUS"):
            kind, _ = self._next()
            op = "+" if kind == "PLUS" else "-"
            right = self._parse_operand()
            node = ("binop", op, node, right)
        return node

    def _parse_operand(self) -> Tuple:
        kind, value = self._next()
        if kind == "NUM":
            return ("lit", int(value))
        if kind == "REG":
            return ("reg", int(value[1:]))
        if kind == "MEAS":
            return ("meas", int(re.search(r"\d+", value).group()))
        raise ValueError("unexpected token: %s" % value)


def _serialize_quantum_ops(circuit: Circuit) -> List[str]:
    ops: List[str] = []
    for gate in circuit.gates:
        if gate.name == "measure":
            ops.append("measure q[%d] -> c[%d];" % (gate.qubits[0], gate.cbits[0]))
        else:
            params = "(" + ",".join(gate.params) + ")" if gate.params else ""
            qubits = ",".join("q[%d]" % i for i in gate.qubits)
            ops.append("%s%s %s;" % (gate.name, params, qubits))
    return ops


def _load_operand(operand: Tuple, instrs: List[str], scratch: List[int]) -> str:
    kind = operand[0]
    if kind == "lit":
        reg = "x%d" % scratch[0]
        scratch[0] += 1
        instrs.append("li %s, %d" % (reg, operand[1]))
        return reg
    if kind == "reg":
        return "x%d" % operand[1]
    if kind == "meas":
        return "x%d" % (10 + operand[1])
    raise ValueError("invalid operand")


def _compile_expr(expr: Tuple, rd: str, instrs: List[str], scratch: List[int]) -> None:
    kind = expr[0]
    if kind == "lit":
        instrs.append("li %s, %d" % (rd, expr[1]))
        return
    if kind == "reg":
        instrs.append("addi %s, x%d, 0" % (rd, expr[1]))
        return
    if kind == "meas":
        instrs.append("addi %s, x%d, 0" % (rd, 10 + expr[1]))
        return

    _, op, left, right = expr
    if op in ("+", "-") and left[0] == "reg" and right[0] == "lit":
        value = right[1] if op == "+" else -right[1]
        instrs.append("addi %s, x%d, %d" % (rd, left[1], value))
        return
    if op == "+" and left[0] == "lit" and right[0] == "reg":
        instrs.append("addi %s, x%d, %d" % (rd, right[1], left[1]))
        return
    if op in ("+", "-") and left[0] == "lit" and right[0] == "lit":
        value = left[1] + right[1] if op == "+" else left[1] - right[1]
        instrs.append("li %s, %d" % (rd, value))
        return

    s1 = "x%d" % scratch[0]
    scratch[0] += 1
    s2 = "x%d" % scratch[0]
    scratch[0] += 1
    _compile_expr(left, s1, instrs, scratch)
    _compile_expr(right, s2, instrs, scratch)
    opcode = "add" if op == "+" else "sub"
    instrs.append("%s %s, %s, %s" % (opcode, rd, s1, s2))


def _compile_stmt(node: Tuple, instrs: List[str], scratch: List[int], labels: List[int]) -> None:
    if node[0] == "assign":
        _, reg_idx, expr = node
        _compile_expr(expr, "x%d" % reg_idx, instrs, scratch)
        return

    _, cond, then_stmts, else_stmts = node
    _, op, left, right = cond
    left_reg = _load_operand(left, instrs, scratch)
    right_reg = _load_operand(right, instrs, scratch)
    labels[0] += 1
    else_label = ".L%d_else" % labels[0]
    end_label = ".L%d_end" % labels[0]
    branch = "bne" if op == "==" else "beq"
    instrs.append("%s %s, %s, %s" % (branch, left_reg, right_reg, else_label))
    for stmt in then_stmts:
        _compile_stmt(stmt, instrs, scratch, labels)
    instrs.append("j %s" % end_label)
    instrs.append("%s:" % else_label)
    for stmt in else_stmts:
        _compile_stmt(stmt, instrs, scratch, labels)
    instrs.append("%s:" % end_label)


def _compile_classical(statements: List[Tuple]) -> str:
    instrs: List[str] = []
    scratch = [20]
    labels = [0]
    for stmt in statements:
        _compile_stmt(stmt, instrs, scratch, labels)
    return "\n".join(instrs) + "\n" if instrs else ""


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """混合编译接口：返回 (量子操作序列, RISC-V 汇编文本)。"""
    quantum_text, classical_text = _split_hybrid(hybrid_qasm_str)
    circuit = parse_qasm2(quantum_text)
    quantum_ops = _serialize_quantum_ops(circuit)

    if classical_text.strip():
        tokens = _tokenize_classical(classical_text)
        parser = _ClassicalParser(tokens)
        statements = parser.parse_program()
        assembly = _compile_classical(statements)
    else:
        assembly = ""

    return quantum_ops, assembly
