#!/usr/bin/env python3
"""按约束挑后端：一段完全确定性的筛选逻辑

L2 的三类任务里，「智能选后端」是唯一一个**答案是唯一确定的**：
评测方按官方《后端能力表》推导正确答案集，回复里出现正确的规范标识才计分。

**所以这件事不该交给模型去做。** 官方文档自己写着：
"强烈建议你的 Agent 直接加载 JSON 作为选型知识库，而不是把表塞进 prompt 靠模型背诵"。

分工是这样的：

    用户的话 ──[模型]──> 结构化的约束 ──[这个文件，确定性]──> 后端 id

模型只负责"听懂人话"（15 比特、零排队、不想花钱、要真机……），
一旦变成结构化的约束，剩下的就是查表，不存在"发挥"的余地。
模型背错表、少记一行、把 24 记成 42——这些错误在这个架构下都不可能发生。

**约束无解时怎么办**：赛题明说"如实说明超出所有可用后端能力比给错答案得分更高"。
所以这里会同时给出"最接近的替代"，并且**照样带上规范标识**——
因为回复里没有任何规范标识就一定不得分。
"""

import json
import os

_CAPABILITIES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend_capabilities.json"
)

# queue 字段的等待程度排序，用于"最接近"的排序
_QUEUE_RANK = {"none": 0, "minutes_to_hours": 1, "hours": 2}
# cost 字段的花钱程度排序
_COST_RANK = {"free": 0, "free_quota": 1, "paid": 2}

_CACHE = {}


def load_backends(path=None):
    """读取官方《后端能力表》。这是选型判定的唯一基准数据。"""
    path = path or _CAPABILITIES_PATH
    if path not in _CACHE:
        with open(path, encoding="utf-8") as handle:
            _CACHE[path] = json.load(handle)["backends"]
    return _CACHE[path]


# 一条约束 = (名字, 判断函数, 说给人听的描述)
def _checks(constraints):
    checks = []

    min_qubits = constraints.get("min_qubits")
    if isinstance(min_qubits, int) and min_qubits > 0:
        checks.append(
            ("min_qubits", lambda b: b["max_qubits"] >= min_qubits, "至少 %d 个比特" % min_qubits)
        )

    kind = constraints.get("kind")
    if kind in ("simulator", "qpu", "cloud"):
        label = {"simulator": "模拟器", "qpu": "真机", "cloud": "云端"}[kind]
        checks.append(("kind", lambda b: b["kind"] == kind, "必须是%s" % label))

    queue = constraints.get("queue")
    if queue == "none":
        checks.append(("queue", lambda b: b["queue"] == "none", "零排队等待"))

    cost = constraints.get("cost")
    if cost == "free":
        checks.append(("cost", lambda b: b["cost"] == "free", "完全免费"))
    elif cost == "no_paid":
        checks.append(("cost", lambda b: b["cost"] != "paid", "不产生费用"))

    if constraints.get("allow_account") is False:
        checks.append(("account", lambda b: not b["requires_account"], "无需注册账号"))

    platform = constraints.get("platform")
    if platform in ("spinq", "originq", "braket"):
        checks.append(("platform", lambda b: b["platform"] == platform, "限定平台 %s" % platform))

    return checks


def select(constraints, path=None):
    """按约束筛后端。

    constraints 支持的键（全部可选，缺省即不限制）：
        min_qubits     int    电路需要多少比特
        kind           str    'simulator' / 'qpu' / 'cloud'
        queue          str    'none' 表示不接受排队
        cost           str    'free' 完全免费 / 'no_paid' 只要不额外花钱
        allow_account  bool   False 表示不愿意注册账号
        platform       str    'spinq' / 'originq' / 'braket'

    返回：
        {
          "matches":   [满足全部约束的后端, ...]，按"最省事"排序
          "exhausted": bool，True 表示没有任何后端满足
          "closest":   无解时给出的最接近替代，附违反了哪几条
          "criteria":  说给人听的约束列表
        }
    """
    constraints = constraints or {}
    backends = load_backends(path)
    checks = _checks(constraints)

    scored = []
    for backend in backends:
        violated = [description for _, test, description in checks if not test(backend)]
        scored.append((backend, violated))

    matches = [backend for backend, violated in scored if not violated]
    matches.sort(key=lambda b: (_QUEUE_RANK.get(b["queue"], 9), _COST_RANK.get(b["cost"], 9),
                                b["requires_account"], -b["max_qubits"]))

    result = {
        "matches": matches,
        "exhausted": not matches,
        "closest": [],
        "criteria": [description for _, _, description in checks],
    }

    if not matches:
        # 违反的条数越少越接近；同样接近时比特数大的排前面
        scored.sort(key=lambda item: (len(item[1]), -item[0]["max_qubits"]))
        fewest = len(scored[0][1]) if scored else 0
        result["closest"] = [
            {"backend": backend, "violated": violated}
            for backend, violated in scored
            if len(violated) == fewest
        ][:3]

    return result


def format_reply(result):
    """把筛选结果写成给人看的回复。

    硬要求：**回复里必须出现规范标识原文**（如 `braket_local_simulator`），
    只写"AWS 本地模拟器"是不计分的。所以无论有解无解，都要带上 id。
    """
    lines = []
    if result["criteria"]:
        lines.append("按你的条件（%s）查了官方后端能力表：" % "、".join(result["criteria"]))
    else:
        lines.append("你没有给出限制条件，下面是全部可用后端：")
    lines.append("")

    if not result["exhausted"]:
        for backend in result["matches"]:
            lines.append(_describe(backend))
        lines.append("")
        best = result["matches"][0]
        lines.append(
            "推荐 `%s`（%s）——在满足条件的选项里它最省事：%s。"
            % (best["id"], best["name"], _why(best))
        )
        return "\n".join(lines)

    lines.append("**没有任何后端能同时满足这些条件。**如实说明比给你一个跑不通的答案更有用。")
    lines.append("")
    lines.append("最接近的选项是：")
    for item in result["closest"]:
        backend = item["backend"]
        lines.append(_describe(backend))
        lines.append("    差在：%s" % "、".join(item["violated"]))
    lines.append("")
    lines.append("可行的走法有两条：放宽其中一个条件，或者把电路拆小再分批跑。")
    return "\n".join(lines)


def _describe(backend):
    queue_text = {"none": "无排队", "minutes_to_hours": "排队分钟到小时级", "hours": "排队小时级"}
    cost_text = {"free": "免费", "free_quota": "有免费额度", "paid": "付费"}
    return "  - `%s` — %s，最多 %d 比特，%s，%s，%s" % (
        backend["id"],
        backend["name"],
        backend["max_qubits"],
        queue_text.get(backend["queue"], backend["queue"]),
        cost_text.get(backend["cost"], backend["cost"]),
        "需注册" if backend["requires_account"] else "无需注册",
    )


def _why(backend):
    reasons = []
    if backend["queue"] == "none":
        reasons.append("不用排队")
    if backend["cost"] == "free":
        reasons.append("不花钱")
    if not backend["requires_account"]:
        reasons.append("不用注册")
    return "、".join(reasons) or "在可选项里综合最优"
