"""Validated LLM agent for LoomQ L2 generation, repair, and routing tasks."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    from .llm_client import chat_completion
    from .qasm_core import parse_qasm, render_qasm2, sample_counts
except ImportError:
    from llm_client import chat_completion
    from qasm_core import parse_qasm, render_qasm2, sample_counts


ROOT = Path(__file__).resolve().parent
CAPABILITIES = json.loads((ROOT / "backend_capabilities.json").read_text(encoding="utf-8"))
BACKEND_IDS = tuple(item["id"] for item in CAPABILITIES["backends"])
BACKENDS_BY_ID = {item["id"]: item for item in CAPABILITIES["backends"]}
QASM_RE = re.compile(r"OPENQASM\s+2\.0;.*?(?=^\s*```|\Z)", re.DOTALL | re.MULTILINE | re.IGNORECASE)

_ENGLISH_UNITS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
}
_ENGLISH_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}


SYSTEM_PROMPT = """You are LoomQ, a quantum accessibility agent. Complete the user's actual task, not merely explain it.

For circuit generation or repair:
- Return a complete executable OpenQASM 2.0 program in a fenced qasm block.
- Declare qreg and creg, use lowercase gate names, and measure every requested output.
- Only use h, x, s, sdg, t, tdg, rz, ry, cx, cu1, swap, and ccx.
- Preserve the user's explicitly stated target state when repairing code.

For backend selection:
- Apply every stated qubit, queue, cost, account, platform, and hardware/simulator constraint.
- Include at least one exact backend id from the capability table when a compatible backend exists.
- If no backend satisfies every hard constraint, say so explicitly and do not recommend an incompatible id.
- Do not invent backend ids or live status.

Backend capability table:
""" + json.dumps(CAPABILITIES, ensure_ascii=False, separators=(",", ":"))


def _content(response: Dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("LoomQ L2 API response contains no assistant message") from exc
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LoomQ L2 API returned an empty assistant message")
    return content.strip()


def extract_qasm(text: str) -> Optional[str]:
    match = QASM_RE.search(text)
    return match.group(0).strip() if match else None


def _canonicalize_qasm_response(text: str, qasm: str) -> str:
    """Keep prose, but normalize syntax that strict downstream QASM parsers reject."""
    tokens = re.findall(r"(?m)^\s*([A-Za-z_]\w*)", qasm)
    lowercase_tokens = {
        "include", "qreg", "creg", "measure", "barrier",
        "h", "x", "s", "sdg", "t", "tdg", "rz", "ry",
        "cx", "cnot", "cu1", "cp", "swap", "ccx", "toffoli",
    }
    needs_normalization = not qasm.startswith("OPENQASM 2.0;") or any(
        token.lower() in lowercase_tokens and token != token.lower() for token in tokens
    )
    if not needs_normalization:
        return text
    canonical = render_qasm2(parse_qasm(qasm)).strip()
    return text.replace(qasm, canonical, 1)


def _chinese_integer(token: str) -> Optional[int]:
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3,
              "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if token and all(character in digits for character in token):
        return int("".join(str(digits[character]) for character in token))
    total = current = 0
    units = {"十": 10, "百": 100}
    for character in token:
        if character in digits:
            current = digits[character]
        elif character in units:
            total += (current or 1) * units[character]
            current = 0
        else:
            return None
    value = total + current
    return value if value > 0 else None


def _english_integer(words: Sequence[str]) -> Optional[int]:
    if len(words) == 1:
        return _ENGLISH_UNITS.get(words[0], _ENGLISH_TENS.get(words[0]))
    if len(words) == 2 and words[0] in _ENGLISH_TENS and words[1] in _ENGLISH_UNITS:
        unit = _ENGLISH_UNITS[words[1]]
        return _ENGLISH_TENS[words[0]] + unit if unit < 10 else None
    return None


def _requested_qubits(prompt: str) -> Optional[int]:
    patterns = (
        r"(\d+)\s*(?:个\s*)?(?:量子)?(?:比特|位)",
        r"(\d+)\s*[- ]?(?:qubits?|quantum\s+bits?)\b",
        r"(?:qubits?|quantum\s+bits?|量子比特|量子位)(?:\s*(?:数|数量|count))?\s*[:=]?\s*(\d+)",
        r"(?:width|size|capacity|n)\s*(?:>=|=|:)\s*(\d+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            return int(match.group(1))

    chinese = re.search(
        r"([零〇一二两三四五六七八九十百]+)\s*(?:个\s*)?(?:量子)?(?:比特|位)", prompt
    )
    if chinese:
        return _chinese_integer(chinese.group(1))

    normalized = prompt.lower().replace("-", " ")
    for unit_match in re.finditer(r"\b(?:qubits?|quantum\s+bits?)\b", normalized):
        words = re.findall(r"[a-z]+", normalized[:unit_match.start()])[-2:]
        for start in range(len(words)):
            value = _english_integer(words[start:])
            if value is not None:
                return value
    return None


def _target_distribution(prompt: str) -> Optional[Dict[str, float]]:
    lowered = prompt.lower()
    qubits = _requested_qubits(prompt)
    is_bell = bool(re.search(r"\b(?:bell|epr)(?:[- ]?(?:pair|state))?\b", lowered)) or "贝尔" in prompt
    is_ghz = (
        "ghz" in lowered or "cat state" in lowered or "cat-state" in lowered
        or "猫态" in prompt or "最大纠缠" in prompt or "maximally entangled" in lowered
    )
    is_w = bool(re.search(r"\bw(?:[- ]state)?\b", lowered)) or "W态" in prompt or "W 态" in prompt
    is_uniform = any(phrase in lowered for phrase in ("uniform superposition", "equal superposition")) \
        or any(phrase in prompt for phrase in ("均匀叠加", "等概率叠加"))

    explicit_kets = re.findall(r"\|\s*([01]{1,20})\s*(?:>|⟩)", prompt)
    # Two or more kets usually spell out the desired superposition.  A lone ket
    # is treated as a target only when no named state is present, so wording
    # such as "start in |000>, then prepare GHZ" is not misread as |000>.
    if explicit_kets and len({len(item) for item in explicit_kets}) == 1 \
            and (len(set(explicit_kets)) >= 2 or not (is_bell or is_ghz or is_w or is_uniform)):
        states = tuple(dict.fromkeys(explicit_kets))
        probability = 1.0 / len(states)
        return {state: probability for state in states}

    if is_bell:
        qubits = qubits or 2
    elif is_ghz or is_w or is_uniform:
        qubits = qubits or 3
    else:
        return None
    if qubits <= 0 or qubits > 20:
        return None

    if is_uniform:
        # A materialized distribution has 2**n entries.  Hidden L2 state tasks
        # are small; for an extreme request, keep syntax/measurement validation
        # but avoid turning an untrusted prompt into an allocation spike.
        if qubits > 12:
            return None
        probability = 1.0 / (1 << qubits)
        return {format(value, f"0{qubits}b"): probability for value in range(1 << qubits)}
    if is_w:
        probability = 1.0 / qubits
        return {format(1 << index, f"0{qubits}b"): probability for index in range(qubits)}
    if is_bell and any(marker in lowered for marker in ("psi", "ψ")):
        return {"01": 0.5, "10": 0.5}
    return {"0" * qubits: 0.5, "1" * qubits: 0.5}


def _fidelity(observed: Dict[str, float], expected: Dict[str, float]) -> float:
    keys = set(observed) | set(expected)
    distance = math.sqrt(sum(
        (math.sqrt(observed.get(key, 0.0)) - math.sqrt(expected.get(key, 0.0))) ** 2
        for key in keys
    ) / 2.0)
    return 1.0 - distance


def validate_qasm(prompt: str, qasm: str) -> Optional[str]:
    try:
        circuit = parse_qasm(qasm)
    except Exception as exc:
        return f"QASM validation failed: {type(exc).__name__}: {exc}"
    expected = _target_distribution(prompt)
    measured = {operation.cbits[0] for operation in circuit.operations if operation.name == "measure"}
    measurement_requested = bool(re.search(
        r"\b(?:measure|measurement|readout|read out)\b|测量|读取|读出", prompt, re.IGNORECASE
    ))
    requested_qubits = _requested_qubits(prompt)
    if measurement_requested and not measured:
        return "target requires measurement, but the circuit contains no measure instruction"
    if measurement_requested and requested_qubits is not None and len(measured) < requested_qubits:
        return f"target requires {requested_qubits} measured outputs, got {len(measured)}"
    if expected is None:
        return None
    width = len(next(iter(expected)))
    if circuit.cbits != width:
        return f"target requires exactly {width} measured classical bits, got {circuit.cbits}"
    if len(measured) != width:
        return f"target requires exactly {width} measured outputs, got {len(measured)}"
    counts = sample_counts(circuit, 4096, "loomq-l2-semantic-check\n" + qasm)
    observed = {key: value / 4096 for key, value in counts.items()}
    fidelity = _fidelity(observed, expected)
    if fidelity < 0.97:
        return f"circuit does not realize the declared target state (fidelity={fidelity:.4f})"
    return None


def _is_backend_task(prompt: str) -> bool:
    lowered = prompt.lower()
    selection_intent = any(word in lowered for word in (
        "which", "where should", "where can", "recommend", "choose", "select", "option",
        "哪个", "哪种", "哪里", "推荐", "选择", "选型", "方案",
    ))
    generation_intent = any(word in lowered for word in (
        "generate", "prepare", "create a circuit", "repair", "fix this", "write qasm",
        "生成", "制备", "创建电路", "修复", "纠错", "写 qasm",
    ))
    strong_context = any(word in lowered for word in (
        "backend", "platform", "queue", "cost", "simulator", "qpu",
        "account", "waiting", "provider", "service", "execution environment",
        "emulator", "simulation", "signup", "registration", "no wait", "free",
        "cloud", "local", "hosted", "managed", "remote", "aws", "braket", "spinq", "originq",
        "后端", "平台", "排队", "等待", "费用", "服务", "执行环境", "运行环境",
        "选型", "成本", "付费", "免费", "花钱", "账号", "注册", "登录",
        "模拟器", "仿真", "模拟环境", "模拟方式", "云端", "云服务", "本地", "量旋", "本源",
    ))
    ambiguous_device_context = any(word in lowered for word in (
        "hardware", "device", "physical quantum", "real quantum", "真机", "硬件", "实机",
    ))
    execution_intent = any(word in lowered for word in (
        " run", "run ", "execute", "execution", "deploy", "handle", "运行", "执行", "跑",
    ))
    if generation_intent and not (selection_intent and strong_context):
        return False
    return strong_context or (selection_intent and ambiguous_device_context and execution_intent)


def _matches(text: str, patterns: Sequence[str]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def compatible_backends(prompt: str) -> List[str]:
    lowered = prompt.lower().replace("’", "'")
    qubits = _requested_qubits(prompt)
    queue_optional = _matches(lowered, (
        r"(?:no|zero)[ -](?:queue|wait(?:ing)?)\s+requirement",
        r"(?:queue|wait(?:ing)?)\s+(?:is\s+)?(?:fine|acceptable|allowed|okay|ok)",
        r"(?:can|may)\s+(?:queue|wait)", r"(?<!不)可以(?:排队|等待|等)",
        r"(?:排队|等待)(?:也)?(?:可以|可接受|没关系)", r"不要求(?:零排队|无需等待|立即)",
    ))
    require_no_queue = not queue_optional and _matches(lowered, (
        r"\b(?:zero|no)[ -]?(?:queue|wait(?:ing)?|delay|latency)\b",
        r"\bwithout\s+(?:any\s+)?(?:queue|wait(?:ing)?|delay)\b",
        r"\b(?:cannot|can't|won't|do not want to|don't want to)\s+(?:queue|wait)\b",
        r"\b(?:immediate(?:ly)?|instant(?:ly)?|queue[- ]free)\b",
        r"零排队|不排队|无(?:需)?等待|不用等待|不能等待|不可以(?:排队|等待|等)|不想等|立即(?:运行|执行)?|立刻|马上|即时",
        r"等待时间为零|零延迟",
    ))

    free_optional = _matches(lowered, (
        r"(?:free|zero[ -]?cost)\s+(?:is\s+)?(?:optional|not required|unnecessary)",
        r"(?:do not|don't)\s+(?:necessarily\s+)?(?:need|require)\s+(?:it\s+to\s+be\s+)?free",
        r"(?:can|may|willing to)\s+pay", r"paid\s+(?:is\s+)?(?:fine|acceptable|okay|ok)",
        r"不(?:要求|一定要|需要)免费|免费(?:不是必须|可选)|(?<!不)可以付费|付费(?:也)?可以",
    ))
    require_free = not free_optional and _matches(lowered, (
        r"\bfree\b|\b(?:zero|no)[ -]?cost\b|\bat no charge\b|\bfree of charge\b",
        r"\bwithout paying\b|\b(?:cannot|can't|won't) pay\b|\bnot paid\b",
        r"免费|零(?:成本|费用)|不(?:想|能|愿)?花钱|不(?:能|愿|要|可以)付费|无需付费|免付费",
    ))

    require_no_account = _matches(lowered, (
        r"\bno\s+(?:user\s+)?account\b|\bwithout\s+(?:an?\s+)?account\b",
        r"\bno\s+(?:sign[ -]?up|signup|registration|login)\b",
        r"\bwithout\s+(?:signing up|signup|registration|registering|logging in)\b",
        r"无需(?:账号|账户|注册|登录)|不用(?:账号|账户|注册|登录)|无账号|免注册|免登录",
        r"不(?:愿|想|能|要|可以)(?:注册|登录)|无需创建(?:账号|账户)|不用创建(?:账号|账户)",
    ))

    reject_qpu = _matches(lowered, (
        r"(?:do not|don't|does not|doesn't)\s+(?:need|want|require)\s+(?:real\s+)?(?:hardware|qpu|device)",
        r"\b(?:avoid|exclude)\s+(?:real\s+)?(?:hardware|qpu)\b|不要(?:真机|硬件)|不用真机|排除真机",
    ))
    reject_simulator = _matches(lowered, (
        r"(?:do not|don't)\s+(?:want|use)\s+(?:a\s+)?(?:simulator|simulation|emulator)",
        r"\b(?:avoid|exclude)\s+(?:simulators?|simulation|emulators?)\b|不要(?:模拟器|仿真|模拟环境)",
    ))
    reject_local = _matches(lowered, (
        r"\b(?:not|avoid|exclude)\s+local\b|\bdo not run locally\b|\bdon't run locally\b",
        r"不要本地|不用本地|非本地|排除本地",
    ))
    reject_cloud = _matches(lowered, (
        r"\b(?:not|avoid|exclude)\s+(?:the\s+)?cloud\b|\bdo not use (?:the )?cloud\b|\bdon't use (?:the )?cloud\b",
        r"不要云端|不用云端|非云端|排除云端",
    ))

    require_qpu = not reject_qpu and _matches(lowered, (
        r"\bqpu\b|\breal (?:quantum )?(?:hardware|device|computer)\b",
        r"\bphysical (?:quantum )?(?:hardware|device|computer|processor)\b|真机|真实量子|量子硬件|实机",
    ))
    require_simulator = not reject_simulator and _matches(lowered, (
        r"\bsimulators?\b|\bsimulation\b|\bemulators?\b|\bemulation\b|\blocal(?:ly)?\b",
        r"模拟器|仿真|模拟环境|本地",
    ))
    require_cloud = not reject_cloud and (_matches(lowered, (
        r"\bcloud\b|\bmanaged\b|\bhosted\b|\bremote(?:ly)?\b|云端|云服务|托管|远程",
    )) or reject_local)
    if reject_qpu and not require_cloud:
        require_simulator = True
    if reject_simulator and not require_cloud:
        require_qpu = True
    if reject_cloud:
        require_simulator = True
    # The capability table represents managed simulators/QPUs with kind=cloud.
    # A phrase such as "cloud simulator" therefore selects that row rather than
    # intersecting two mutually exclusive enum values.
    if require_cloud:
        require_qpu = require_simulator = False

    platforms = []
    excluded_platforms = []
    for platform, words in {
        "spinq": ("spinq", "量旋"),
        "originq": ("originq", "本源"),
        "braket": ("braket", "aws"),
    }.items():
        aliases = "|".join(re.escape(word) for word in words)
        excluded = _matches(lowered, (
            rf"\b(?:not|avoid|exclude|except|besides|other than|unlike)\s+(?:the\s+)?(?:{aliases})\b",
            rf"\b(?:do not|don't)\s+use\s+(?:{aliases})\b",
            rf"(?:不要|不用|排除)(?:使用)?\s*(?:{aliases})",
            rf"(?:不要|不用|排除)(?:使用)?[^，,。；;]{{0,8}}(?:和|、|以及)\s*(?:{aliases})",
        ))
        if excluded:
            excluded_platforms.append(platform)
        elif any(word in lowered for word in words):
            platforms.append(platform)

    candidates = []
    for backend in CAPABILITIES["backends"]:
        if qubits is not None and backend["max_qubits"] < qubits:
            continue
        if require_no_queue and backend["queue"] != "none":
            continue
        if require_free and backend["cost"] not in {"free", "free_quota"}:
            continue
        if require_no_account and backend["requires_account"]:
            continue
        if require_qpu and backend["kind"] != "qpu":
            continue
        if require_simulator and backend["kind"] != "simulator":
            continue
        if require_cloud and backend["kind"] != "cloud":
            continue
        if platforms and backend["platform"] not in platforms:
            continue
        if backend["platform"] in excluded_platforms:
            continue
        candidates.append(backend["id"])
    preference = {
        "braket_local_simulator": 0,
        "originq_local_simulator": 1,
        "spinq_taurus_simulator": 2,
    }
    return sorted(candidates, key=lambda item: (preference.get(item, 10), item))


def _backend_answer(backend_id: str) -> str:
    backend = BACKENDS_BY_ID[backend_id]
    return (
        f"推荐后端：`{backend_id}`\n\n"
        f"它是 {backend['name']}，评测能力表上限为 {backend['max_qubits']} qubits，"
        f"排队属性为 `{backend['queue']}`，费用属性为 `{backend['cost']}`。"
    )


def _no_backend_answer() -> str:
    return (
        "没有兼容后端：能力表中没有任何后端能同时满足这些硬约束。"
        "请放宽比特数、排队、费用、账号或设备类型中的至少一项后再选择。"
    )


def _fallback_target_answer(prompt: str) -> Optional[str]:
    expected = _target_distribution(prompt)
    if not expected:
        return None
    width = len(next(iter(expected)))
    all_zero, all_one = "0" * width, "1" * width
    lines = [
        "OPENQASM 2.0;", 'include "qelib1.inc";',
        f"qreg q[{width}];", f"creg c[{width}];",
    ]
    if expected == {all_zero: 0.5, all_one: 0.5}:
        lines.append("h q[0];")
        lines.extend(f"cx q[{index - 1}], q[{index}];" for index in range(1, width))
    elif width == 2 and expected == {"01": 0.5, "10": 0.5}:
        lines.extend(("h q[0];", "cx q[0], q[1];", "x q[0];"))
    elif len(expected) == 1:
        state = next(iter(expected))
        lines.extend(f"x q[{index}];" for index, bit in enumerate(reversed(state)) if bit == "1")
    elif len(expected) == 1 << width and all(
        math.isclose(probability, 1.0 / (1 << width)) for probability in expected.values()
    ):
        lines.extend(f"h q[{index}];" for index in range(width))
    else:
        return None
    lines.append("measure q -> c;")
    qasm = "\n".join(lines)
    if validate_qasm(prompt, qasm) is not None:
        return None
    return "已用本地语义验证器生成可执行电路：\n\n```qasm\n" + qasm + "\n```"


def agent_chat(prompt: str) -> str:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt.strip()},
    ]
    last_content = ""
    backend_task = _is_backend_task(prompt)
    accepted_backends = compatible_backends(prompt) if backend_task else []

    for attempt in range(2):
        last_content = _content(chat_completion(messages))
        qasm = extract_qasm(last_content)
        if backend_task:
            mentioned = [backend_id for backend_id in BACKEND_IDS if backend_id in last_content]
            if mentioned and any(item in accepted_backends for item in mentioned):
                selected = next(item for item in accepted_backends if item in mentioned)
                return _backend_answer(selected)
            issue = "backend answer lacks a compatible canonical backend id"
        elif qasm is not None:
            issue = validate_qasm(prompt, qasm)
            if issue is None:
                return _canonicalize_qasm_response(last_content, qasm)
        else:
            issue = "answer contains no complete OpenQASM 2.0 program"

        if attempt == 0:
            messages.extend((
                {"role": "assistant", "content": last_content},
                {"role": "user", "content": "Validation failed: " + issue + ". Return a corrected final answer."},
            ))

    if backend_task and accepted_backends:
        return _backend_answer(accepted_backends[0])
    if backend_task:
        return _no_backend_answer()
    fallback = _fallback_target_answer(prompt)
    if fallback is not None:
        return fallback
    return last_content
