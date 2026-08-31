"""Terminal entry point for the LoomQ agent, written for a first-time user.

Design rules, in priority order:

1. Never require a word the reader does not already have. Outcomes are described
   as "what you will see", not as state names.
2. Ask a closed question first. Someone with no model of the domain cannot answer
   "what do you want to do?", but can pick from a list whose results are shown.
3. Say what is needed to run *before* anything fails, not after.
4. Order every answer as meaning -> evidence -> code, and give the reader explicit
   permission not to read the code.
5. Never trap an expert in the tour: free text, one-shot flags and a raw QASM mode
   are always available.
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
from typing import Callable, Sequence

try:
    from .l2.normalize import normalize
    from .l2.simulate import simulate
    from .l2.synthesize import synthesize
    from .l2_agent import agent_chat, extract_qasm
except ImportError as exc:
    # A missing third-party dependency must not be reported as "No module named
    # 'l2'"; that hides the real cause behind the flat-layout fallback below.
    if exc.name in {"qiskit", "numpy"}:
        raise SystemExit(
            f"缺少依赖 {exc.name}。请先运行：\n"
            "    pip install -r starter_kit/requirements.txt\n"
            "如果依赖装在虚拟环境里，请用那个环境的 python 启动，例如：\n"
            "    .venv/bin/python -m starter_kit.l2_cli\n"
            f"（原始错误：{exc}）"
        ) from exc
    # Support ``python starter_kit/l2_cli.py`` as well.
    from l2.normalize import normalize
    from l2.simulate import simulate
    from l2.synthesize import synthesize
    from l2_agent import agent_chat, extract_qasm


RULE = "─" * 66
BAR_WIDTH = 24
DISPLAY_SHOTS = 1024
REQUIRED_ENVIRONMENT = ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")

# Each example carries the sentence actually sent to the agent and, separately,
# the outcome a newcomer can check against. The preview is what makes the menu
# readable without knowing any state names.
EXAMPLES = (
    {
        "title": "两个粒子的结果永远相同",
        "preview": "跑 1024 次，只会出现 00 和 11，各约一半；01 和 10 一次都不会有",
        "prompt": "我想要两个量子比特，测量结果永远相同：要么都是 0，要么都是 1，"
                  "两种情况各占一半，两个比特都要测量。",
    },
    {
        "title": "两个粒子的结果永远相反",
        "preview": "只会出现 01 和 10，各约一半；00 和 11 一次都不会有",
        "prompt": "我想要两个量子比特，测量结果永远相反：一个是 0 时另一个必定是 1，"
                  "两种情况各占一半，两个比特都要测量。",
    },
    {
        "title": "三个粒子完全随机",
        "preview": "000 到 111 这 8 种结果都会出现，每种约 128 次",
        "prompt": "帮我准备 3 个量子比特的等概率叠加态，8 种测量结果机会一样大，全部测量。",
    },
    {
        "title": "三个粒子里恰好有一个是 1",
        "preview": "只会出现 001、010、100，各约三分之一",
        "prompt": "请生成一个 3 比特的 W 态，也就是恰好有一个比特为 1、三种情况等概率，并全测量。",
    },
)

REPAIR_EXAMPLE = {
    "title": "修好一段报错的程序",
    "preview": "下面这段有两个错：没有声明寄存器，而且 q[2] 超出了范围",
    "prompt": "我想制备一个两个比特结果永远相同的态，但这段代码报错了，帮我修好：\n"
              "H q[0]; CX q[0] q[2];",
}

BACKEND_EXAMPLE = {
    "title": "告诉我该用哪台机器",
    "preview": "从 6 个真实平台里挑一个，并说明为什么",
    "prompt": "我没有任何云平台账号，也不想付费，只想在本机跑一个 20 比特的电路，用什么？",
}

# The three things this tool does. Listed on screen, so they must be selectable:
# a menu entry the user cannot pick is worse than no menu entry at all.
CATEGORIES = {
    "a": (
        "把你的话变成量子程序",
        ("1", "2", "3", "4"),
        "直接描述你想看到的结果就行，例如：我想要三个粒子，只有中间那个是 1。",
    ),
    "b": (
        "修好一段报错的程序",
        ("5",),
        "把报错的代码整段贴进来，连同你原本想要的效果一起说，例如：\n"
        "  我想要两个比特结果相同，但这段报错了：H q[0]; CX q[0] q[2];",
    ),
    "c": (
        "告诉你该用哪台机器",
        ("6",),
        "说清楚你的限制就行：几个比特、能不能等排队、愿不愿付费、有没有账号。",
    ),
}


GLOSSARY = """名词对照表（够用就好，不用背）

  量子比特 qubit   普通比特只能是 0 或 1；量子比特在被测量之前可以同时带着
                   两种可能，测量的那一刻才随机变成 0 或 1。

  叠加             "同时带着两种可能"的那个状态。它不是"我们不知道是哪个"，
                   而是两种可能都真实存在，所以才会有下面的纠缠。

  纠缠             两个粒子的结果被绑在一起：单看每一个都是随机的，但它们之间
                   永远满足某种关系，例如永远相同、或者永远相反。

  测量             把量子比特读成一个确定的 0 或 1。同一个电路要测很多次，
                   得到的是一个分布，所以本工具总是告诉你"跑 1024 次会看到什么"。

  电路 / QASM      给量子计算机执行的程序。QASM 是它的文本写法，本工具生成的
                   就是这个，可以直接贴到各家平台上运行。

  保真度 fidelity  本机模拟出来的分布和你要求的分布有多接近，1.0 表示完全一致。

想再深一点：starter_kit/QUANTUM_101.md
"""

HARDWARE_HELP = """本机模拟 与 真机，差别在哪

  本工具默认给你的是本机模拟的结果：用普通电脑精确算出理想情况，没有噪声、
  不排队、不要钱，同一个电路每次算出来的分布都一样。它回答的是"这个电路在
  数学上应该给出什么"。

  真机会有误差。我们自己在本源悟空 180 上跑同一个两比特纠缠电路，1024 次里
  00 和 11 合计 1023 次，剩下 1 次落在了本不该出现的 10 上——那 1 次就是硬件
  噪声。原始结果和任务截图都在 starter_kit/evidence/ 里。

真机怎么接（本工具不替你提交，需要你自己的账号）

  拿到生成的 QASM 之后，任选一个平台：

  · 本源悟空 180   72 比特超导真机，有免费额度，排队小时级，需注册 + API Token
      1. 到本源量子云注册，在控制台申请 API Token
      2. export ORIGINQ_API_TOKEN=<你的 Token>
      3. python3 starter_kit/examples/submit_originq_hardware.py
      我们自己就是用这个脚本拿到 job FFA39889... 那次真机结果的。

  · SpinQ Cloud    2 比特核磁真机，注册即用，有免费额度，排队分钟到小时级
      注册后在网页上传 QASM 即可；它返回的是投影概率，不是 shots 计数。

  · AWS Braket     34 比特云端模拟器和多家厂商真机，按任务 + shots 计费
      需要 AWS 账号；本机的 LocalSimulator 不需要账号，装了 SDK 就能用。

  完全不想注册也没关系：上面每个例子在本机模拟器上都能跑完，
  而且给出的是精确的理想值。
"""


def _describe(state: str) -> str:
    """Say what one outcome means, for a reader who cannot yet read bit strings."""
    n = len(state)
    ones = [n - 1 - index for index, bit in enumerate(state) if bit == "1"]
    if not ones:
        return "全部是 0"
    if len(ones) == n:
        return "全部是 1"
    listed = "、".join(f"q[{qubit}]" for qubit in sorted(ones))
    return f"只有 {listed} 是 1"


def histogram(qasm: str) -> str:
    """Turn a circuit into "what you would see if you actually ran it"."""
    _, circuit = normalize(qasm)
    distribution = simulate(circuit)
    width = max((len(state) for state in distribution), default=1)
    lines = [f"如果真的运行 {DISPLAY_SHOTS} 次，你会看到："]
    present = 0
    for state, probability in sorted(distribution.items(), key=lambda kv: -kv[1]):
        if probability <= 0:
            continue
        present += 1
        count = round(probability * DISPLAY_SHOTS)
        bar = "█" * max(1, round(probability * BAR_WIDTH))
        lines.append(
            f"  {state:>{width}}  {bar:<{BAR_WIDTH}} {count:>5} 次  {probability:6.1%}"
            f"   {_describe(state)}"
        )
    total = 1 << width
    missing = total - present
    if 0 < missing <= 8:
        absent = [
            format(value, f"0{width}b")
            for value in range(total)
            if distribution.get(format(value, f"0{width}b"), 0.0) <= 0
        ]
        lines.append("")
        lines.append(f"  {'、'.join(absent)} 一次都不会出现。")
    elif missing > 8:
        lines.append("")
        lines.append(f"  另外 {missing} 种结果一次都不会出现。")
    return "\n".join(lines)


def preflight() -> tuple[list[str], bool]:
    """Report everything needed to run, before the first question is asked."""
    lines = ["环境自检", f"  ✓ Python {platform.python_version()}"]
    try:
        import qiskit

        lines.append(
            f"  ✓ 本地模拟器 qiskit {qiskit.__version__} —— 生成的电路会先在这里跑一遍"
        )
    except Exception:  # pragma: no cover - qiskit is a hard dependency in practice
        lines.append("  ✗ 本地模拟器不可用：pip install -r starter_kit/requirements.txt")
    missing = [name for name in REQUIRED_ENVIRONMENT if not os.environ.get(name)]
    if missing:
        lines.append("  ✗ 模型服务未配置 —— 用自然语言提问需要这 3 个环境变量：")
        lines.append("      export LOOMQ_LLM_BASE_URL=https://api.deepseek.com")
        lines.append("      export LOOMQ_LLM_API_KEY=<你自己的 Key>")
        lines.append("      export LOOMQ_LLM_MODEL=deepseek-v4-flash")
        lines.append(f"    还缺：{'、'.join(missing)}")
    else:
        key = os.environ.get("LOOMQ_LLM_API_KEY", "")
        lines.append("  ✓ 模型服务已配置，本次使用的是：")
        lines.append(f"      LOOMQ_LLM_BASE_URL = {os.environ.get('LOOMQ_LLM_BASE_URL', '')}")
        lines.append(f"      LOOMQ_LLM_MODEL    = {os.environ.get('LOOMQ_LLM_MODEL', '')}")
        # The key itself is never printed, here or anywhere else.
        lines.append(f"      LOOMQ_LLM_API_KEY  = 已设置（长度 {len(key)}，不会被打印或写入文件）")
    timeout = os.environ.get("LOOMQ_LLM_TIMEOUT_SECONDS")
    lines.append(
        f"  · LOOMQ_LLM_TIMEOUT_SECONDS 可选，当前 {timeout}"
        if timeout
        else "  · LOOMQ_LLM_TIMEOUT_SECONDS 可选，未设置时用内置预算"
    )
    lines.append("  · 真机是可选的，需要各平台自己的账号；输入 h 看怎么接")
    return lines, not missing


def offline_demo() -> str:
    """Something honest to show when no model service is configured."""
    built = synthesize({"kind": "bell", "n": 2})
    if built is None:  # pragma: no cover - the bell construction is deterministic
        return "离线演示暂时不可用。"
    program, _score = built
    return (
        "离线演示 · 两个粒子的结果永远相同\n"
        "（这段电路由本机确定性生成并模拟，完全不经过模型服务）\n\n"
        + histogram(program)
        + "\n\n配好上面那 3 个环境变量之后，你就可以用自己的话提问了。"
    )


# agent_chat swallows model failures and returns this sentence rather than
# raising, so the recovery path has to recognise it instead of waiting for an
# exception. tests/test_l2_cli.py pins this against l2.render.fallback().
AGENT_FAILURE_PREFIX = "LoomQ Agent 暂时无法完成这次请求"


def recovery_help(detail: str) -> str:
    """What to do next, in the order a beginner can actually follow."""
    return (
        "模型服务没有响应。这通常不是你的问题，按顺序检查三件事：\n"
        "  1  三个变量都设了吗    echo $LOOMQ_LLM_BASE_URL $LOOMQ_LLM_MODEL\n"
        "  2  Key 还有额度吗      到服务商控制台看一眼\n"
        "  3  网络到得了吗        curl -sI $LOOMQ_LLM_BASE_URL\n"
        "你刚才的问题我留着了，配好之后再问一次就行。\n"
        f"诊断信息：{detail}"
    )


def handle(prompt: str, completion: Callable[[str], str] = agent_chat) -> str:
    """One question in, one readable answer out."""
    try:
        answer = completion(prompt)
    except Exception as exc:
        return recovery_help(f"{type(exc).__name__}: {exc}")
    if answer.startswith(AGENT_FAILURE_PREFIX):
        return recovery_help(answer)
    qasm = extract_qasm(answer)
    if not qasm:
        # Backend recommendations and refusals carry no circuit; pass them through.
        return answer
    try:
        picture = histogram(qasm)
    except Exception as exc:
        return (
            f"{answer}\n\n电路已经生成，但本地结果图这次没画出来："
            f"{type(exc).__name__}: {exc}。上面的 QASM 仍然可以直接使用。"
        )
    return (
        f"{picture}\n\n"
        "这是本机模拟算出来的理想结果，没有噪声；真机上会有误差（输入 h 看区别）。\n\n"
        f"{answer}\n\n"
        "上面那段 QASM 是给机器执行的，看不懂完全没关系，可以直接贴到量子平台上运行。"
    )


def menu() -> str:
    lines = [
        "这个工具能做三件事：",
        "",
        "  A  把你的话变成量子程序    你描述想要的结果，我生成电路，并先在本机模拟给你看",
        "  B  修好一段报错的程序      你贴一段代码，我找出问题并给出能跑的版本",
        "  C  告诉你该用哪台机器      按比特数、排队时间、费用，从 6 个真实平台里挑",
        "",
        "输入 A / B / C 看某一类的例子，或者直接输入下面的数字：",
        "",
    ]
    for index, example in enumerate(EXAMPLES, 1):
        lines.append(f"  {index}  {example['title']}")
        lines.append(f"     {example['preview']}")
    lines.extend([
        f"  5  {REPAIR_EXAMPLE['title']}",
        f"     {REPAIR_EXAMPLE['preview']}",
        f"  6  {BACKEND_EXAMPLE['title']}",
        f"     {BACKEND_EXAMPLE['preview']}",
        "",
        "也可以直接用自己的话说，例如：我想要三个粒子，只有中间那个是 1。",
        "",
        "  ?  名词解释    h  本机模拟和真机的区别、真机怎么接    q  退出",
        "",
        "已经知道自己要什么？直接把要求打出来即可；一次性用法见 --help。",
    ])
    return "\n".join(lines)


def prompt_for(choice: str) -> str | None:
    if choice in {"1", "2", "3", "4"}:
        return EXAMPLES[int(choice) - 1]["prompt"]
    if choice == "5":
        return REPAIR_EXAMPLE["prompt"]
    if choice == "6":
        return BACKEND_EXAMPLE["prompt"]
    return None


def category_view(letter: str) -> str:
    """Show one category's examples, so A / B / C actually do something."""
    title, choices, hint = CATEGORIES[letter]
    lines = [f"{letter.upper()} · {title}", ""]
    for choice in choices:
        lines.append(f"  {choice}  {prompt_title(choice)}")
        lines.append(f"     {example_preview(choice)}")
    lines.extend(["", hint, "", "输入上面的数字直接看，或者直接把你的要求打出来。"])
    return "\n".join(lines)


def looks_like_a_request(text: str) -> bool:
    """Cheap sanity check so a stray keystroke does not spend a model call.

    Deliberately permissive: anything with Chinese, a digit, or a bit of length
    goes straight through, because "bell state" and "GHZ 3" are real requests.
    Only the obviously-accidental input is held back, and even that is let
    through the moment the user repeats it.
    """
    if len(text) >= 6:
        return True
    if any("\u4e00" <= character <= "\u9fff" for character in text):
        return True
    return any(character.isdigit() for character in text)


def interactive(input_fn: Callable[[str], str] = input) -> int:
    checks, configured = preflight()
    print("LoomQ · 用日常语言做量子实验")
    print("你不需要懂量子物理，也不需要会写代码。\n")
    print("\n".join(checks))
    print()
    if not configured:
        print(offline_demo())
        print()
    print(menu())
    pending: str | None = None
    while True:
        try:
            raw = input_fn("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出 LoomQ。")
            return 0
        if raw.lower() in {"q", "quit", "exit", "退出"}:
            print("已退出 LoomQ。")
            return 0
        if not raw:
            print("说点什么都行，或者输入 1 到 6 选一个现成例子，? 看名词解释。")
            continue
        if raw in {"?", "？", "help", "帮助"}:
            print("\n" + GLOSSARY)
            continue
        if raw.lower() in {"h", "hardware", "真机"}:
            print("\n" + HARDWARE_HELP)
            pending = None
            continue
        if raw.lower() in CATEGORIES:
            print("\n" + category_view(raw.lower()))
            pending = None
            continue
        if raw.isdigit():
            selected = prompt_for(raw)
            if selected is None:
                print(f"没有第 {raw} 个例子，现在有 1 到 6；也可以直接用自己的话描述。")
                pending = None
                continue
            prompt = selected
            print(f"\n你选的是：{prompt_title(raw)}")
        elif not looks_like_a_request(raw) and raw != pending:
            # Confirm by repetition: costs the model nothing, and an expert who
            # really meant it just presses the same keys again.
            pending = raw
            print(f"我不太确定「{raw}」是什么意思，所以先没有去问模型。")
            print("可以试试这样说：")
            print("  · 我想要两个粒子，测量结果永远相同")
            print("  · 帮我修一下这段电路：H q[0]; CX q[0] q[1];")
            print("  · 我没有账号也不想付费，20 比特的电路该用哪个平台")
            print(f"或者输入 1 到 6 选现成例子；确实要原样提问的话，再输入一次「{raw}」。")
            continue
        else:
            prompt = raw
        pending = None
        if not configured:
            print("\n还没配置模型服务，没法把你的话变成电路。上面自检的第 3 项给了具体命令。")
            continue
        print("正在生成，并在本机模拟检查……")
        print(f"\n{RULE}")
        print(handle(prompt))
        print(RULE)
        print("接下来：输入数字换一个例子 · 直接说你想怎么改 · 输入 6 看这段能在哪跑 · q 退出")


def example_preview(choice: str) -> str:
    if choice in {"1", "2", "3", "4"}:
        return EXAMPLES[int(choice) - 1]["preview"]
    if choice == "5":
        return REPAIR_EXAMPLE["preview"]
    if choice == "6":
        return BACKEND_EXAMPLE["preview"]
    return ""


def prompt_title(choice: str) -> str:
    if choice in {"1", "2", "3", "4"}:
        return EXAMPLES[int(choice) - 1]["title"]
    if choice == "5":
        return REPAIR_EXAMPLE["title"]
    if choice == "6":
        return BACKEND_EXAMPLE["title"]
    return choice


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m starter_kit.l2_cli",
        description="LoomQ 自然语言量子助手（无额外界面依赖）",
        epilog="不带参数直接运行会进入交互模式，并先做一次环境自检。",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--prompt", help="直接问一个问题然后退出")
    group.add_argument("--example", type=int, choices=range(1, 7), help="运行内置例子 1-6")
    group.add_argument("--glossary", action="store_true", help="打印名词解释后退出")
    group.add_argument("--hardware", action="store_true", help="打印真机接入说明后退出")
    group.add_argument("--check", action="store_true", help="只做环境自检后退出")
    parser.add_argument(
        "--qasm-only",
        action="store_true",
        help="只输出 QASM，不输出解释和结果图，方便重定向到文件",
    )
    args = parser.parse_args(argv)

    if args.glossary:
        print(GLOSSARY)
        return 0
    if args.hardware:
        print(HARDWARE_HELP)
        return 0
    checks, configured = preflight()
    if args.check:
        print("\n".join(checks))
        return 0 if configured else 1

    prompt = args.prompt or (prompt_for(str(args.example)) if args.example else None)
    if prompt is None:
        return interactive()
    if not configured:
        print("\n".join(checks), file=sys.stderr)
        return 1
    if args.qasm_only:
        program = extract_qasm(agent_chat(prompt))
        if not program:
            print("这次没有生成电路（选后端一类的问题本来就没有电路）。", file=sys.stderr)
            return 1
        print(program)
        return 0
    print(handle(prompt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
