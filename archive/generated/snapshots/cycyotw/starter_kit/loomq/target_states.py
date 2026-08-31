#!/usr/bin/env python3
"""常见目标量子态的理想分布：Agent 自验时的标准答案

L2 的评分方式是：把 Agent 生成的电路真的跑一遍，看分布对不对。
既然评委会这么判，我们就在**回答之前自己先这么判一遍**——
不对就重来，别把没验过的东西交出去。

要自验就得知道"对"是什么。这个文件把常见的目标态写成理想分布：

| 名字 | 意思 | 3 比特时的分布 |
|---|---|---|
| `ghz` | 最大纠缠态（所有比特要么全 0 要么全 1） | 000 一半，111 一半 |
| `bell` | 两比特的 GHZ，就是贝尔态 | 00 一半，11 一半 |
| `w` | 恰好有一个比特是 1，是哪个不确定 | 001 / 010 / 100 各三分之一 |
| `uniform` | 所有结果等概率（每个比特各来一个 H） | 8 个结果各八分之一 |
| `basis` | 确定的一个结果，比如 101 | 101 概率 1 |

认不出来的目标态返回 None，这时自验只做"能不能解析、能不能跑、有没有测量"
这几项结构检查，不做分布比对——**宁可少判，不要判错**。
"""


def ideal_distribution(target):
    """target 是个字典，例如 {"kind": "ghz", "qubits": 3}。

    返回 {结果字符串: 概率}；认不出来时返回 None。
    结果字符串的排法与赛题规范一致（最右边是 c[0]）。
    """
    if not isinstance(target, dict):
        return None

    kind = str(target.get("kind", "")).strip().lower()
    qubits = target.get("qubits")
    if isinstance(qubits, str) and qubits.isdigit():
        qubits = int(qubits)

    if kind in ("bell", "epr"):
        qubits = 2
        kind = "ghz"

    if kind == "ghz":
        if not isinstance(qubits, int) or qubits < 1:
            return None
        return {"0" * qubits: 0.5, "1" * qubits: 0.5}

    if kind == "w":
        if not isinstance(qubits, int) or qubits < 1:
            return None
        share = 1.0 / qubits
        return {
            "".join("1" if position == index else "0" for position in range(qubits - 1, -1, -1)): share
            for index in range(qubits)
        }

    if kind in ("uniform", "plus", "superposition"):
        if not isinstance(qubits, int) or qubits < 1 or qubits > 16:
            return None
        total = 2**qubits
        share = 1.0 / total
        return {format(value, "0%db" % qubits): share for value in range(total)}

    if kind in ("basis", "computational"):
        bits = str(target.get("bits", "")).strip()
        if bits and set(bits) <= {"0", "1"}:
            return {bits: 1.0}
        return None

    return None


def describe(target):
    """把目标态说成一句人话，用在回复里。认不出来时返回 None。

    **认不出来必须返回 None，不能返回一句"你要的电路"这样的废话。**
    实测发现过：目标态认不出来时，回复里会出现「**你要的是**：你要的电路」，
    用户看到的是一个明显坏掉的占位符。宁可不写这一行，也不要写这一行废话。
    """
    if not isinstance(target, dict):
        return None
    kind = str(target.get("kind", "")).strip().lower()
    qubits = target.get("qubits")
    if kind in ("bell", "epr"):
        return "贝尔态（两个比特永远一致：要么都是 0，要么都是 1）"
    if kind == "ghz":
        return "%s 比特的 GHZ 态（所有比特要么全 0、要么全 1，各占一半）" % qubits
    if kind == "w":
        return "%s 比特的 W 态（恰好有一个比特是 1，但不确定是哪一个）" % qubits
    if kind in ("uniform", "plus", "superposition"):
        return "%s 比特的均匀叠加态（所有结果等概率）" % qubits
    if kind in ("basis", "computational"):
        return "确定的基态 %s" % target.get("bits", "")
    return None
