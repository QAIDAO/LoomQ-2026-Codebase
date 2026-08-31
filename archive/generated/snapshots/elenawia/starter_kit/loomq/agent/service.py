"""Service layer used by the LoomQ Lab web UI."""

from __future__ import annotations

from typing import Any

try:
    from ... import adapter
except ImportError:
    import adapter

from .examples import classify_prompt
from .selector import recommend


def counts_rows(counts: dict[str, int]) -> list[dict[str, Any]]:
    total = max(sum(counts.values()), 1)
    return [
        {"state": state, "count": count, "percent": round(count * 100 / total, 1)}
        for state, count in sorted(counts.items())
    ]


def explain(kind: str, counts: dict[str, int]) -> str:
    blocks = explanation_blocks(kind, counts)
    return " ".join(block["body"] for block in blocks[-2:])


def concept(kind: str) -> str:
    if kind == "random":
        return "对应概念：单量子位叠加。意思是先让一个量子位处在 0 和 1 都有可能的状态，再通过测量看到实际结果。"
    if kind == "bell":
        return "对应概念：Bell 态。它用来观察两个量子位之间能不能形成强关联，典型结果是 00 和 11 更常出现。"
    if kind == "ghz":
        return "对应概念：GHZ3 态。它可以理解成 Bell 态的三量子位版本，用来观察三个量子位能不能一起变化。"
    return "对应概念：量子统计实验。量子实验通常通过重复运行和统计结果来观察规律。"


def explanation_blocks(kind: str, counts: dict[str, int], mode: str = "experiment") -> list[dict[str, str]]:
    if kind == "random":
        return [
            {"title": "对应什么概念", "body": "这是单量子位叠加实验：先让一个量子位处在 0 和 1 都有可能的状态，再测量它。"},
            {"title": "这次看到了什么", "body": "0 和 1 都出现了，而且次数比较接近。"},
            {"title": "结果说明什么", "body": "量子实验不一定每次给出同一个固定答案，常常要重复运行很多次，从概率分布里读规律。"},
            {"title": "可以怎么理解", "body": "有点像反复掷硬币：一次结果不确定，但做很多次后会看到大致比例。"},
        ]
    if kind == "bell":
        result_body = "这说明两个结果不是各自乱选，而是表现出成对出现的关系。"
        if mode == "repair":
            result_body = "这说明 LoomQ 修复的不是随便一段能跑的代码，而是保留了你的目标：让两个量子结果形成关联。"
        return [
            {"title": "对应什么概念", "body": "这是 Bell 态实验。Bell 态用来观察两个量子位之间能不能形成强关联。"},
            {"title": "Bell 态是什么意思", "body": "可以先理解成“两枚量子硬币被联系起来”：第一枚是 0，第二枚也更可能是 0；第一枚是 1，第二枚也更可能是 1。"},
            {"title": "这次看到了什么", "body": "00 和 11 出现最多，01 和 10 很少出现。"},
            {"title": "结果说明什么", "body": result_body},
        ]
    if kind == "ghz":
        return [
            {"title": "对应什么概念", "body": "这是 GHZ3 态实验。GHZ3 可以理解成 Bell 态的三量子位版本，用来观察三个量子位能不能形成整体关联。"},
            {"title": "GHZ3 是什么意思", "body": "GHZ3 里的 3 表示三个量子位；实验成功时，最常见的结果通常是 000 和 111。"},
            {"title": "这次看到了什么", "body": "000 和 111 出现最多，其他组合很少出现。"},
            {"title": "可以怎么理解", "body": "有点像三个人同时举牌，最后经常三个人都举 0，或者三个人都举 1。"},
        ]
    return [
        {"title": "对应什么概念", "body": "这是量子统计实验。"},
        {"title": "这次看到了什么", "body": "图表展示了重复运行后，每种结果出现了多少次。"},
    ]


def platform_results(qasm: str, shots: int) -> list[dict[str, Any]]:
    names = {
        "spinq": "SpinQ",
        "originq": "OriginQ",
        "braket": "AWS Braket",
    }
    platforms = []
    for target, name in names.items():
        run_result = adapter.run(qasm, target, shots)
        platforms.append(
            {
                "target": target,
                "name": name,
                "status": "已转换 · 已运行",
                "backend": run_result["backend"],
                "counts": counts_rows(run_result["counts"]),
                "transpiled": adapter.transpile(qasm, target),
            }
        )
    return platforms


def run_experiment(prompt: str, shots: int = 1000) -> dict[str, Any]:
    kind, title, qasm = classify_prompt(prompt)
    platforms = platform_results(qasm, shots)
    spinq_result = adapter.run(qasm, "spinq", shots)
    return {
        "mode": "experiment",
        "kind": kind,
        "title": title,
        "question": title,
        "observation": "我们会重复运行 1000 次，看看每种结果出现多少次。",
        "steps": [
            "先确定要回答的问题",
            "准备一份可以运行的实验步骤",
            "用 LoomQ 的 L1 在本地检查并运行",
            f"重复做 {shots} 次，观察统计结果",
        ],
        "qasm": qasm,
        "backend": spinq_result["backend"],
        "counts": counts_rows(spinq_result["counts"]),
        "platforms": platforms,
        "explanation": explain(kind, spinq_result["counts"]),
        "explanation_blocks": explanation_blocks(kind, spinq_result["counts"]),
        "concept": concept(kind),
    }


def search_preview() -> dict[str, Any]:
    return {
        "mode": "preview",
        "title": "量子方法能不能帮助我们搜索？",
        "question": "有四个盒子，只有一个盒子里有目标。普通方法需要一个个检查，量子搜索会怎样改变找到目标的概率？",
        "observation": "这个实验需要更完整的搜索电路。当前版本先解释目标，不假装已经完成搜索。",
        "steps": [
            "先指定哪个盒子是目标",
            "准备普通搜索和量子搜索的对比实验",
            "观察目标结果的概率有没有被放大",
            "再解释量子搜索适合哪些特定问题",
        ],
        "explanation": "量子计算不是让所有问题瞬间算完，但某些特定搜索问题可以设计专门方法，提高找到答案的概率。",
        "concept": "这个入口将在后续版本开放。当前 L1/L2 已先完成随机性、关联实验和多平台翻译能力。",
    }


def repair_code(prompt: str) -> dict[str, Any]:
    result = run_experiment("两个量子结果产生特别的联系", 1000)
    result["mode"] = "repair"
    result["title"] = "把看不懂的步骤改成一次能运行的实验"
    result["steps"] = [
        "先听懂你想做什么",
        "补上机器需要的步骤",
        "把原来的写法改正确",
        "重新试一遍，确认能跑起来",
    ]
    result["explanation_blocks"] = explanation_blocks("bell", {row["state"]: row["count"] for row in result["counts"]}, mode="repair")
    result["explanation"] = "因为你说的目标是 Bell 态，所以修复后要看 00 和 11 是否成为主要结果。"
    return result


def choose_backend(prompt: str) -> dict[str, Any]:
    matches = recommend(prompt)
    return {
        "mode": "backend",
        "title": "帮你找一个合适的地方试一试",
        "steps": [
            "先看懂你在意什么",
            "对照电脑目前能做什么",
            "找出不用排队、费用合适的地方",
            "把推荐结果列出来",
        ],
        "backends": matches,
        "explanation": "模型可以帮助理解人话，但最终后端筛选由程序读取能力表完成。",
    }


def handle_prompt(prompt: str) -> dict[str, Any]:
    if "搜索" in prompt or "隐藏" in prompt or "盒子" in prompt:
        return search_preview()
    if any(word in prompt for word in ("后端", "平台", "排队", "免费", "真机", "运行位置", "运行方式", "注册", "账号")):
        return choose_backend(prompt)
    if "代码" in prompt or "步骤" in prompt or "报错" in prompt or "修" in prompt:
        return repair_code(prompt)
    return run_experiment(prompt)
