#!/usr/bin/env python3
"""L2 智能体 · 验收测试（全程使用本地假模型，不需要 API Key，不需要联网）

测的不是"模型聪明不聪明"——那不归我们管，评测时跑的是组委会指定的模型。
测的是**我们的代码在模型各种表现下是否都拿得住**：

  模型答对了      -> 我们要认得出，并如实交付
  模型语法写错了  -> 我们要自验抓到，并带着具体错误让它重写
  模型态写错了    -> 只有真跑一遍才看得出来，必须抓到
  模型用了禁用门  -> 要抓到
  模型吐了一堆垃圾 -> 不能崩
  模型连不上      -> 不能崩，还要说清楚缺什么配置
  两轮都改不对    -> 老实说没通过，不把没验过的东西交出去

这些情况用真模型没法稳定复现，所以用 `fake_llm_server.py` 按剧本演。

用法：python3 starter_kit/tools/verify_l2.py
"""

import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from starter_kit import adapter  # noqa: E402
from starter_kit.loomq import agent  # noqa: E402
from starter_kit.evaluator import extract_qasm  # noqa: E402
from starter_kit.tools.fake_llm_server import ENV_KEYS, FakeLLM, NoConfig, NoServer  # noqa: E402

failures = []


def check(condition, message):
    if condition:
        print("  ✅ %s" % message)
    else:
        failures.append(message)
        print("  ❌ %s" % message)


def header(text):
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


def plan(**fields):
    return json.dumps(fields, ensure_ascii=False)


# 自验的验收标准由一次**独立**调用给出（只看用户原话、看不到电路），
# 见 agent.JUDGE_SYSTEM_PROMPT。下面两个小工具把这次调用单独拿开：
#
#   · scripted()      —— 判目标态那次单独应答，不占剧本的位置，
#                        否则它会吃掉本该给"改写"用的那一条
#   · scripted_calls() —— 数调用次数时把它排除掉
#
# 这样每个剧本仍然表达它本来的意思，测试里那些数字也还是原来的含义。
_JUDGE_HEAD = agent.JUDGE_SYSTEM_PROMPT[:24]


def _is_judge(body):
    try:
        return body["messages"][0]["content"].startswith(_JUDGE_HEAD)
    except (KeyError, IndexError, TypeError, AttributeError):
        return False


def scripted(items, judge=None):
    remaining = list(items)

    def respond(body):
        if _is_judge(body):
            return json.dumps(judge or {"kind": "unknown"}, ensure_ascii=False)
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    return respond


def scripted_calls(fake):
    return [body for body in fake.calls if not _is_judge(body)]


GHZ3_GOOD = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
measure q -> c;
"""

GHZ3_SYNTAX_BROKEN = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
H q[0]
CX q[0] q[1];
measure q -> c;
"""

# 语法完全正确，但少了纠缠——测出来是均匀分布，不是 GHZ。
# 这种错**只有真的跑一遍才看得出来**。
GHZ3_WRONG_STATE = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
h q[1];
h q[2];
measure q -> c;
"""

# 用了白名单以外的门
GHZ3_BAD_GATE = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cy q[0],q[1];
cx q[1],q[2];
measure q -> c;
"""

# 一个门都没有，只有测量。跑出来必然是 100% 全 0。
# 实测真的收到过这种东西：用户要"一半正面一半反面"，模型交回来的就是这个。
COIN_NO_GATE = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
measure q[0] -> c[0];
"""

# 正确的"抛硬币"
COIN_GOOD = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
h q[0];
measure q[0] -> c[0];
"""

# 忘了测量
GHZ3_NO_MEASURE = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
"""


def section_backend():
    header("一 · 选后端：官方三个示例，答案是唯一确定的")

    cases = [
        ("15 比特 + 零排队", {"min_qubits": 15, "queue": "none"},
         ["spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"], []),
        ("真机 + 5 比特 + 不花钱", {"kind": "qpu", "min_qubits": 5, "cost": "no_paid"},
         ["spinq_cloud_qpu", "originq_wukong"], ["braket_cloud"]),
        ("50 比特模拟器 + 零排队（无解）", {"min_qubits": 50, "kind": "simulator", "queue": "none"},
         [], []),
    ]

    for label, constraints, must_have, must_not in cases:
        with FakeLLM([plan(task="select_backend", constraints=constraints)]) as fake:
            reply = adapter.agent_chat("（测试）%s" % label)
        check(len(fake.calls) >= 1, "%s：确实调用了模型服务（评分资格的硬性前提）" % label)
        for backend_id in must_have:
            check(backend_id in reply, "%s：回复含规范标识 %s" % (label, backend_id))
        for backend_id in must_not:
            check(backend_id not in reply, "%s：回复不含错误答案 %s" % (label, backend_id))
        if not must_have:
            check("没有任何后端" in reply, "%s：如实说明无解" % label)
            check("originq_local_simulator" in reply,
                  "%s：无解时仍给出最接近替代的规范标识" % label)


def section_generate():
    header("二 · 生成电路：一次写对")

    with FakeLLM(scripted([plan(task="generate", target={"kind": "ghz", "qubits": 3},
                                qasm=GHZ3_GOOD, note="三比特 GHZ")],
                          judge={"kind": "ghz", "qubits": 3})) as fake:
        reply = adapter.agent_chat("生成一个 3 比特的最大纠缠态并进行全测量")

    check(len(scripted_calls(fake)) == 1, "一次写对时只写一次（省时间也省额度）")
    extracted = extract_qasm(reply)
    check(extracted is not None, "官方 evaluator 的提取函数能从回复里取出 QASM")
    if extracted:
        check(extracted.strip().startswith("OPENQASM 2.0;"), "提取出来的确实是完整程序")
        check("measure" in extracted, "提取出来的程序含测量语句")
    # 保真度是 2048 次采样算出来的，必然带统计涨落，不会正好是 1.0000
    matched = re.search(r"保真度 \*\*([0-9.]+)\*\*", reply)
    check(matched is not None, "回复里带上了实测保真度")
    if matched:
        check(float(matched.group(1)) >= 0.97,
              "实测保真度 %s ≥ 0.97（与评测阈值一致）" % matched.group(1))
    check("实测结果" in reply, "回复里带上了真实采样数据，不是空口说白话")


def section_retry():
    header("三 · 重试：模型第一版不对，带着具体错误让它重写")

    scenarios = [
        ("语法写错（大写门名、缺分号）", GHZ3_SYNTAX_BROKEN, "解析失败"),
        ("态写错了（少了纠缠，语法却完全正确）", GHZ3_WRONG_STATE, "保真度"),
        ("用了白名单以外的门 cy", GHZ3_BAD_GATE, "不认识的门"),
        ("忘了写测量", GHZ3_NO_MEASURE, "measure"),
    ]

    for label, broken, expect_in_complaint in scenarios:
        script = [
            plan(task="generate", target={"kind": "ghz", "qubits": 3}, qasm=broken, note="第一版"),
            json.dumps({"qasm": GHZ3_GOOD, "note": "改好了"}, ensure_ascii=False),
        ]
        with FakeLLM(scripted(script, judge={"kind": "ghz", "qubits": 3})) as fake:
            reply = adapter.agent_chat("生成一个 3 比特 GHZ 态并全测量")

        calls = scripted_calls(fake)
        check(len(calls) == 2, "%s：触发了一轮重写" % label)
        if len(calls) == 2:
            complaint = calls[1]["messages"][-1]["content"]
            check(expect_in_complaint in complaint,
                  "%s：把具体错误告诉了模型（含 %r）" % (label, expect_in_complaint))
        extracted = extract_qasm(reply)
        check(extracted is not None and "cx" in extracted,
              "%s：最终交付的是改好的那版" % label)


def section_giveup():
    header("四 · 改到次数用尽仍不对：老实说没通过，不交没验过的东西")

    # 期望的调用次数直接从代码里取，不写死数字——否则调整重试轮数时测试会假失败
    expected_calls = agent.MAX_FIX_ROUNDS + 1
    script = [plan(task="generate", target={"kind": "ghz", "qubits": 3}, qasm=GHZ3_WRONG_STATE)]
    script += [json.dumps({"qasm": GHZ3_WRONG_STATE}, ensure_ascii=False)] * agent.MAX_FIX_ROUNDS
    with FakeLLM(scripted(script, judge={"kind": "ghz", "qubits": 3})) as fake:
        reply = adapter.agent_chat("生成一个 3 比特 GHZ 态并全测量")

    check(len(scripted_calls(fake)) == expected_calls,
          "用满了重试次数（1 次生成 + %d 次重写）" % agent.MAX_FIX_ROUNDS)
    check("没能给出" in reply and "自验" in reply, "如实说明没有通过自验")
    check("没有通过自验" in reply, "即使附上最后一版，也明确标注它没通过")


def section_independent_judge():
    header("四点五 · 验收标准必须来自独立的一次判断（既当运动员又当裁判员）")
    print("   实测撞出来的：用户说「做一个 1 比特的电路，让结果一半正面一半反面」，")
    print("   交回来的电路一个门都没有，同时把目标态申报成「确定的基态 0」——")
    print("   于是拿错答案去对错标准，保真度 1.0000，一路绿灯交给了用户。")
    print("   根子不在阈值，在**答案和标准出自同一次调用**：一致地错就必然通过。")

    # 复刻那次事故：写电路的人申报 basis-0（跟他那段没有门的电路正好自洽）
    accident = [plan(task="generate", target={"kind": "basis", "bits": "0"},
                     qasm=COIN_NO_GATE, note="用 Hadamard 门实现均匀叠加")]
    accident += [json.dumps({"qasm": COIN_NO_GATE}, ensure_ascii=False)] * agent.MAX_FIX_ROUNDS

    # 独立那次只看用户原话，判出来是"1 比特均匀叠加"
    with FakeLLM(scripted(accident, judge={"kind": "uniform", "qubits": 1})):
        reply = adapter.agent_chat("做一个 1 比特的电路，让结果一半正面一半反面，并且测量")
    check("没能给出" in reply,
          "标准来自独立判断后，这个自洽的错答案被拦住了（原先它拿着 1.0000 过关）")
    check("100% 全 0" in reply or "没有任何量子门" in reply,
          "并且说清了错在哪：一个门都没有的电路只会把初始状态原样测出来")

    # 这条结构常识不依赖任何目标态——就算独立判断也失手，它照样拦得住
    problems, _evidence = agent._self_check(COIN_NO_GATE, {"kind": "unknown"})
    check(problems and "没有任何量子门" in problems[0],
          "兜底：没有门的电路一律判死，这一条**完全不看目标态**，判错目标也拦得住")
    problems, _evidence = agent._self_check(COIN_GOOD, {"kind": "uniform", "qubits": 1})
    check(not problems, "而正确的抛硬币电路照常通过，没有被这条兜底误伤")

    # ---- 验不了的时候必须说出来 ----
    print("\n   另一次事故：用户报的是门序列（「先做一个 H，再做一个 H」）。")
    print("   裁判的词汇表里只有 ghz/bell/w/uniform/basis，装不下「连做两次 H」，")
    print("   于是硬套了最像的 uniform——而重写那一轮为了迎合这个错标准，")
    print("   **主动删掉了一个 H**。错标准不只是漏判，它会反过来把对的电路改坏。")
    with FakeLLM(scripted([plan(task="generate", target={"kind": "unknown"},
                                qasm=COIN_GOOD + "", note="按步骤写的")],
                          judge={"kind": "gates"})) as fake:
        reply = adapter.agent_chat("做一个 1 比特的电路：先做一个 H 门，然后测量")
    check("没有比对分布" in reply,
          "判成 gates（说不出目标态）时，**明确告诉用户这次没验分布**")
    check("保真度" not in reply,
          "而且绝不印保真度——没有标准却给个数字，等于凭空担保")
    check(extract_qasm(reply) is not None, "但电路照常交付，并附上真实采样数据")
    check(len(scripted_calls(fake)) == 1,
          "也不会因为没有标准就一轮轮重写（没有标准，重写没有方向）")

    # 独立那次判不出来时，不能因此拒答
    with FakeLLM(scripted([plan(task="generate", target={"kind": "ghz", "qubits": 3},
                                qasm=GHZ3_GOOD, note="正常")],
                          judge={"kind": "unknown"})):
        reply = adapter.agent_chat("生成一个 3 比特的最大纠缠态并全测量")
    check("没能给出" not in reply and extract_qasm(reply) is not None,
          "独立判断说不出目标态时，退回结构检查照常交付——认不出不等于拒答")


def section_robust():
    header("五 · 模型不配合时不能崩")

    cases = [
        ("模型吐了一堆非 JSON 的废话", FakeLLM(["嗨！我很乐意帮忙 :) 不过我不太确定你要什么。"])),
        ("模型返回空字符串", FakeLLM([""])),
        ("模型返回 HTTP 500", FakeLLM([500])),
        ("模型服务连不上", NoServer()),
        ("三个环境变量根本没配", NoConfig()),
    ]
    for label, context in cases:
        try:
            with context:
                reply = adapter.agent_chat("生成一个贝尔态")
            crashed = False
        except Exception as exc:  # noqa: BLE001
            crashed = True
            reply = "%s: %s" % (type(exc).__name__, exc)
        check(not crashed, "%s：没有抛异常" % label)
        check(isinstance(reply, str) and len(reply) > 20, "%s：仍然返回了可读的文本" % label)

    with NoConfig():
        reply = adapter.agent_chat("生成一个贝尔态")
    check("LOOMQ_LLM_BASE_URL" in reply, "没配环境变量时，明确告诉用户缺哪三个")


def section_contract():
    header("六 · 契约合规：不得硬编码服务地址、密钥、模型名")

    # ★ 这里原先只扫 loomq/*.py，漏掉了 loomq_cli.py——而那个文件的"怎么配置"
    #   帮助文字里真的写了一组示例服务地址和模型名，正好压在"本程序不硬编码任何
    #   服务地址、密钥或模型名"那句话上面。**扫描范围本身就是这项检查的一部分**：
    #   漏扫一个文件，检查再严也没用。所以现在扫全部会提交的源码。
    source_files = []
    for relative in ("starter_kit/loomq", "starter_kit"):
        directory = os.path.join(_REPO_ROOT, relative)
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".py"):
                continue
            path = os.path.join(directory, name)
            if not os.path.isfile(path):
                continue
            label = os.path.join(relative, name)
            with open(path, encoding="utf-8") as handle:
                source_files.append((label, handle.read()))
    check(len(source_files) >= 10, "扫描到 %d 个源码文件（少于 10 个说明扫描范围又漏了）"
          % len(source_files))
    check(any(name.endswith("loomq_cli.py") for name, _ in source_files),
          "扫描范围覆盖 loomq_cli.py（曾经漏掉过的那个）")

    banned = ["api.deepseek.com", "deepseek-v4-flash", "sk-", "https://api.openai.com"]
    for name, text in source_files:
        for token in banned:
            check(token not in text, "%s 里没有硬编码 %r" % (name, token))

    # llm_client.py 是真正发请求的地方，它当然要读这几个变量；
    # 其余三个只是在提示文字里提到变量名，告诉用户该配什么。
    allowed_to_name_keys = ("llm_client.py", "agent.py", "envfile.py", "loomq_cli.py")
    for name, text in source_files:
        if "LOOMQ_LLM_API_KEY" in text:
            check(name.endswith(allowed_to_name_keys),
                  "%s 提到环境变量名（只允许 llm_client.py / agent.py / envfile.py / "
                  "loomq_cli.py）" % name)

    # 上面那条"不许出现模型名"原先是靠 `if model == "<某个模型名>"` 违反的：
    # 那行判断用来给认这个字段的服务加上 thinking=disabled。删掉名字之后，
    # 改成不认名字、只看服务端答不答应——所以得测这条退路真的通。
    print("\n   下面几条测的是替代方案：可选字段被服务端拒了要能自己去掉重发。")
    with FakeLLM(scripted([400, plan(task="generate", target={"kind": "ghz", "qubits": 3},
                                     qasm=GHZ3_GOOD, note="重发后成功")],
                          judge={"kind": "ghz", "qubits": 3})) as fake:
        reply = adapter.agent_chat("生成一个 3 比特 GHZ 态并全测量")
    check(len(scripted_calls(fake)) == 2, "服务端 400 拒了可选字段后，确实重发了一次（共 2 次请求）")
    check("thinking" in fake.calls[0], "第一次请求带了 thinking 字段")
    check("thinking" not in fake.calls[1], "重发那次已经把 thinking 去掉了")
    check("OPENQASM" in reply.upper(), "重发成功后照常交付电路，用户看不出中间绕了一下")

    with FakeLLM([400, 400]) as fake:
        reply = adapter.agent_chat("生成一个 3 比特 GHZ 态并全测量")
    check(len(fake.calls) == 2, "去掉字段后仍然 400：只重试一次，不无限重发")
    check("连不上模型" in reply, "去掉字段后仍然 400：如实告诉用户模型服务有问题")


UNIFORM3_GOOD = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
h q[1];
h q[2];
measure q -> c;
"""


def section_no_false_reject(rounds=30):
    header("七 · 回归：自验绝不能把「正确的电路」判成错的")
    print("   这一节是为一个真实踩过的坑加的：自验阈值曾设成 0.99（想着比评测的 0.97 更严），")
    print("   结果正确的 GHZ-3 会拿到 0.9893 被自己打回去——那只是采样涨落。")
    print("   后果不只是多跑一轮：重试用完后，本来正确的电路会以「没通过自验」交付，白丢分。")

    for label, qasm, target in [
        ("GHZ-3（2 个结果，涨落最大）", GHZ3_GOOD, {"kind": "ghz", "qubits": 3}),
        ("均匀叠加 3 比特（8 个结果）", UNIFORM3_GOOD, {"kind": "uniform", "qubits": 3}),
    ]:
        # 判据看的是**结果**：正确的电路必须被交付、且带着一个过线的保真度。
        # 原先数的是"调用了几次模型"，拿次数当"有没有被打回"的替身——
        # 后来验收标准改成由一次独立调用给出，次数天然变了，这一节就集体假失败了。
        # 替身会随实现变，结果不会。
        rejected = 0
        for _ in range(rounds):
            with FakeLLM(scripted([plan(task="generate", target=target, qasm=qasm)],
                                  judge=target)) as fake:
                reply = adapter.agent_chat("（回归）生成 %s" % label)
            matched = re.search(r"保真度 \*\*([0-9.]+)\*\*", reply)
            delivered = "没能给出" not in reply and matched and float(matched.group(1)) >= 0.97
            rejected += 0 if delivered else 1
        check(rejected == 0,
              "%s：连跑 %d 次，一次都没有被误判（误判 %d 次）" % (label, rounds, rejected))


def section_official_case():
    header("八 · 官方公开 L2 用例：接上任何一个能用的模型就必须 PASS")
    print("   没有 API Key 时，`evaluator.py --level declared` 里 l2 那条必然 FAIL——")
    print("   那是缺配置，不是代码不行。这里把假模型接上去，跑官方原样的判定逻辑。")

    from starter_kit import evaluator

    with FakeLLM([plan(task="generate", target={"kind": "ghz", "qubits": 3},
                       qasm=GHZ3_GOOD, note="三比特 GHZ 态")]):
        cases = evaluator.evaluate_l2()

    for case in cases:
        check(case["status"] == "PASS",
              "官方用例 %s：%s（%s）" % (case["case_id"], case["status"], case["reason"]))


def section_non_circuit():
    header("九 · 不生成电路的三条路：容错提示（主观分 10 分里点名的一项）")
    print("   这一节是被实测撞出来的。原先只有「生成电路」和「选后端」两条路，")
    print("   于是「帮我挖矿」也会收到一段一本正经的单比特电路——装懂，还给了个没意义的产物。")
    print("   见 tools/probe_l2_robustness.py。")

    # ---- reject / explain 走模型写正文，用假模型固定它的输出 ----
    for task, label, prose in (
        ("reject", "超出量子计算能力范围（挖矿）", "挖矿靠的是反复算哈希，量子计算在这件事上没有优势。"),
        ("explain", "问概念而不是要电路", "它让一个比特同时压在 0 和 1 两边，测量时两边各一半。"),
    ):
        with FakeLLM([plan(task=task, target={"kind": "unknown"}, note="n/a"), prose]) as fake:
            reply = adapter.agent_chat("（测试）%s" % label)
        check(len(fake.calls) == 2, "%s：解析一次 + 写正文一次，共两次模型调用" % label)
        check(prose in reply, "%s：模型写的正文出现在回复里" % label)
        check("OPENQASM" not in reply.upper(), "%s：**没有**生成任何电路" % label)
        for text, _question, _effect in agent.STARTERS:
            check(text in reply, "%s：附上了可直接复制的可行起点「%s」" % (label, text[:12]))

    # ---- unclear 不需要第二次调用，直接问清楚 ----
    with FakeLLM([plan(task="unclear", target={"kind": "unknown"}, note="没说要什么")]) as fake:
        reply = adapter.agent_chat("我想试试量子")
    check(len(fake.calls) == 1, "说不清要什么：只解析一次，不为了寒暄多调一次模型")
    check("OPENQASM" not in reply.upper(), "说不清要什么：**没有**替用户瞎挑一个目标去生成")
    check(all(text in reply for text, _q, _e in agent.STARTERS),
          "说不清要什么：给了 %d 个可选起点" % len(agent.STARTERS))

    # ---- ★ 反向保护：标签自相矛盾时必须退回去正常生成 ----
    print("\n   下面这条是护栏：误判成「不生成」等于交白卷，直接丢客观分，")
    print("   比误判成「生成」严重得多。所以标签自己跟自己打架时，代码要推翻它。")
    with FakeLLM([plan(task="unclear", target={"kind": "ghz", "qubits": 3},
                       qasm=GHZ3_GOOD, note="话很短但要什么很清楚")]):
        reply = adapter.agent_chat("ghz 3bit 跑一下")
    check("OPENQASM" in reply.upper(),
          "标成 unclear 但目标态认得出来（\"ghz 3bit 跑一下\"）：推翻标签，照常生成")
    check("0.9" in reply or "1.00" in reply, "同上：并且真的跑了自验，回复里有保真度")

    # ---- 占位符不许再漏出去 ----
    print("\n   实测漏过一次：目标态认不出来时，回复里出现「你要的是：你要的电路」。")
    with FakeLLM([plan(task="generate", target={"kind": "unknown"}, qasm=GHZ3_GOOD, note="目标态不明")]):
        reply = adapter.agent_chat("（测试）目标态认不出来")
    check("你要的电路" not in reply, "目标态认不出来时，不输出「你要的电路」这种占位符废话")
    check("OPENQASM" in reply.upper(), "同上：但电路照样交付（认不出目标态不等于拒答）")

    # ---- 结果可视化：评分标准原文点名的一项 ----
    with FakeLLM([plan(task="generate", target={"kind": "ghz", "qubits": 3},
                       qasm=GHZ3_GOOD, note="三比特 GHZ")]):
        reply = adapter.agent_chat("生成一个 3 比特 GHZ 态并全测量")
    check("█" in reply, "结果可视化：采样结果画成了横条，不是一串纯文字")
    check(reply.count("█\n") + reply.count("█ ") >= 1, "结果可视化：条形图有实际内容")

    bars = "\n".join(agent._bars({"000": 4096, "111": 4096}))
    check(bars.count("█" * 30) == 2, "条形图：50/50 时两条一样长（按最高那条归一化）")
    many = "\n".join(agent._bars({format(v, "05b"): 256 for v in range(32)}))
    check("还有 24 个结果" in many, "条形图：结果太多时只画前 8 条，其余合并成一行说明")


def section_cli():
    header("十 · 交互入口冒烟测试：评委真正会碰到的那个界面")
    print("   赛题写的是「评委**现场测试 Agent**」——被打分的就是这个入口。")
    print("   它之前一行自动化测试都没有：崩在评委面前，前面攒的分全白搭。")

    import subprocess

    cli = os.path.join(_REPO_ROOT, "starter_kit", "loomq_cli.py")

    def run(arguments, feed, env=None):
        return subprocess.run(
            [sys.executable, cli] + arguments,
            input=feed, capture_output=True, text=True, timeout=300,
            env=env if env is not None else os.environ.copy(),
        )

    done = run(["--help"], "")
    check(done.returncode == 0, "--help 正常退出")
    check("--chat" in done.stdout and "--guide" in done.stdout, "--help 列出了两个入口参数")

    # 三关那一段不需要模型服务、不需要联网，所以可以完整跑完。
    # 喂足够多的回车和选项，走到最后的总结。
    done = run(["--guide"], "\n1\n\n2\n\n2\n\n2\n\n")
    check(done.returncode == 0, "--guide 走完三关正常退出")
    check("你猜对了" in done.stdout or "你猜错了" in done.stdout, "--guide 打出了逐关判定")
    check("而你错的那些，就是量子" in done.stdout, "--guide 走到了最后的总结")
    check("正在真的跑一遍" in done.stdout, "--guide 真的执行了电路，不是写死的结果")
    check(not done.stderr.strip(), "--guide 没有任何报错输出（stderr 为空）")

    # --chat 需要模型服务：把假模型接上，环境变量由 FakeLLM 设好，子进程继承。
    with FakeLLM([plan(task="generate", target={"kind": "ghz", "qubits": 3},
                       qasm=GHZ3_GOOD, note="三比特 GHZ")]):
        done = run(["--chat"], "生成一个 3 比特 GHZ 态并全测量\nq\n")
    check(done.returncode == 0, "--chat 正常退出")
    check("┌─ 电路" in done.stdout, "--chat 把 QASM 渲染成了电路框，不是一堆反引号")
    check("█" in done.stdout, "--chat 把采样结果渲染成了条形图")
    check("`" not in done.stdout, "--chat 输出里没有残留的反引号")
    check("**" not in done.stdout, "--chat 输出里没有残留的星号")

    # ---- 编号必须真的能用，而且要按"使用者下一步想做什么"排 ----
    print("\n   反复推翻之后立起来的原则：编号按**使用者下一步想做什么**排，")
    print("   不按系统能做什么排。原先摆的是「写电路/修坏电路/挑运行平台」——")
    print("   那是赛题的评分项分类，等于把考卷目录端给了一个不知道量子是什么的人。")
    from starter_kit import loomq_cli

    first = loomq_cli.flatten(loomq_cli.turn_menu())
    labels = [label for label, _ in first]
    check(all("刚才" not in label and "为什么会是" not in label for label in labels),
          "第一屏不出现回顾性的条目（那时还没有「刚才」）：%s" % "、".join(labels))
    check("掷一枚量子硬币" in labels[0],
          "第一条说的是会看到什么，不是「写电路」这种动作名")
    # 标签必须**说清会看到什么**。写过一版是"三个东西永远一致""一个东西能同时压在两边"，
    # 那是空话：没说三个什么东西、也没说哪两边。含糊比术语更糟，术语至少能查。
    check(all("东西" not in label for label in labels),
          "标签里不出现「东西」这种没有指称的词：%s" % "、".join(labels))
    check(any("一次都不出现" in label for label in labels),
          "反直觉的那条直接把现象写在标签上（八种里六种一次都不出现）")
    check(any("修一段" in label for label in labels)
          and any("挑一个运行平台" in label for label in labels),
          "评委要测的那两类能力就摆在屏幕上，排在后面但**不藏起来**")
    check(labels.index("帮我修一段报错的电路") > 1, "它们排在零基础那几条后面，不挡路")

    after_circuit = [label for label, _ in loomq_cli.flatten(
        loomq_cli.turn_menu("x\n```qasm\nOPENQASM 2.0;\n```"))]
    check(any("改个数字" in label for label in after_circuit),
          "刚交了电路，第一条就是「改个数字再跑一遍」——此刻手边唯一真有东西可改")
    check(any("字母" in label for label in after_circuit), "并且可以直接问那些字母是什么意思")

    after_backend = [label for label, _ in loomq_cli.flatten(
        loomq_cli.turn_menu(agent.BACKEND_FOOTER))]
    check(any("换一组条件" in label for label in after_backend),
          "选后端之后不再是死路（原先告诉你推荐哪个，然后没有任何一条路往下走）")

    menu = loomq_cli.flatten(loomq_cli.turn_menu())
    sentence, echoed = loomq_cli.resolve("1", menu)
    check(echoed and sentence == menu[0][1], "输入「1」= 选中第一项，发出去的是那一整句话")
    check(loomq_cli.resolve("5 比特 GHZ", menu) == ("5 比特 GHZ", False),
          "「5 比特 GHZ」里也有数字，但它是一句话，原样发出去（只有纯数字才当编号）")
    check(loomq_cli.resolve("生成贝尔态", menu)[1] is False, "自由输入不当编号")

    with FakeLLM(scripted([plan(task="generate", target={"kind": "uniform", "qubits": 1},
                                qasm=COIN_GOOD, note="按编号选的")],
                          judge={"kind": "uniform", "qubits": 1})) as fake:
        done = run(["--chat"], "1\nq\n")
    check(done.returncode == 0, "只敲一个数字就能跑通一整轮")
    sent = "".join(m.get("content", "") for m in fake.calls[0].get("messages", []))
    check(menu[0][1] in sent, "敲 1 之后，真的把第一项那句话发给了模型")
    check("→ " + menu[0][1] in done.stdout,
          "并且回显给用户看——否则他不知道 1 变成了哪句话")
    check(agent.STARTER_LEAD not in done.stdout,
          "屏幕上不并排摆两份清单：Agent 回复自带的那份被切掉，只留可敲编号的版本")

    # ★ 必须包在 FakeLLM 里。这几条断言看的是**菜单渲染**，而菜单只有在
    #   配置齐全、真进了对话循环之后才会打出来。
    #   踩过：本地跑绿是因为开发机上有 .env 被自动读到；CI（以及评委的干净环境）
    #   没有 .env，--chat 直接走"缺配置"分支，菜单压根没渲染，四条断言集体失败。
    #   又是"测试因为本机状态而通过"——跟 NoConfig、跟子进程继承 cwd 是同一个毛病。
    with FakeLLM(scripted([plan(task="unclear", target={"kind": "unknown"}, note="n/a")])):
        done = run(["--chat"], "99\nq\n")
    check("上面只有 1 到" in done.stdout, "敲了范围外的数字，明确告诉他一共有几条")
    print("\n   曾经每轮只印 4 条，剩下的用「m 看全部选项」折起来——`m` 是编出来的键，")
    print("   得让人先猜是什么意思；而「看全部选项」这句话本身就在宣布有东西被藏着。")
    check("m  看全部" not in done.stdout and "看全部选项" not in done.stdout,
          "没有 `m` 这种自创的键，也没有「看全部选项」这种在宣布藏东西的话")
    check(all(label in done.stdout for label, _ in loomq_cli.STANDING_MENU),
          "所有条目每轮都摊在屏幕上，一条不藏（共 %d 条）" % len(loomq_cli.STANDING_MENU))

    # ---- 提示不能写成让人误读的样子 ----
    print("\n   原先输入行写的是「你说（q 退出）：」，读起来像在要求你说出这四个字。")
    check("你说： " in done.stdout, "输入提示就是干净的「你说：」")
    check("你说（" not in done.stdout, "输入提示的括号里不塞操作说明")
    check("想看什么？" in done.stdout, "第一屏的标题不写「接下来」——那时还没有「刚才」")

    # ---- Agent 自带的清单在这个界面里要切掉 ----
    stripped = loomq_cli.strip_starter_block(
        "正文一句话。\n\n---\n\n" + agent.STARTER_LEAD + "\n  - `随便`\n")
    check(stripped == "正文一句话。",
          "切掉自带清单时，连带那条孤零零的分隔线一起收拾干净")
    check(loomq_cli.strip_starter_block("没有清单的回复") == "没有清单的回复",
          "没有清单的回复原样保留")

    # ---- 多轮指代：「改成 5 比特」得知道上一轮是什么 ----
    print("\n   下面这条也是实测撞出来的，而且是界面自己的提示把人带进去的：")
    print("   提示用户说「改成 5 比特」，但 agent_chat 是单轮无记忆的，")
    print("   这句话被从零理解成「来个 5 比特电路」，给出的是均匀叠加而不是 GHZ——")
    print("   而且自验**通过**了：目标态也被认成均匀叠加，拿错答案对错标准。")

    check(loomq_cli.with_context("完整的一句话", None) == "完整的一句话",
          "第一轮没有上文，原话直接发出去，不加任何东西")
    composed = loomq_cli.with_context("改成 5 比特", "一个 3 比特的 GHZ 态并全测量")
    check("改成 5 比特" in composed and "一个 3 比特的 GHZ 态并全测量" in composed,
          "第二轮把这一轮和上一轮的原话都带上了")
    check("OPENQASM" not in composed.upper(),
          "**只带上一轮的原话，不带上一轮的电路**——带了代码会被判成「修坏代码」，"
          "而修错的职责是保持目标态不变，正好跟「我要改目标」打架")

    with FakeLLM([plan(task="generate", target={"kind": "ghz", "qubits": 3},
                       qasm=GHZ3_GOOD, note="第一轮"),
                  plan(task="generate", target={"kind": "ghz", "qubits": 3},
                       qasm=GHZ3_GOOD, note="第二轮")]) as fake:
        done = run(["--chat"], "一个 3 比特的 GHZ 态并全测量\n改成 5 比特\nq\n")
    check(done.returncode == 0, "多轮对话正常退出")
    bodies = ["".join(m.get("content", "") for m in body.get("messages", []))
              for body in fake.calls]
    check(len(bodies) >= 2, "两轮都调了模型（共 %d 次请求）" % len(bodies))
    # 不锚定"第几次调用"——独立判目标态那次一加，下标就会变。只要求存在这样一次请求。
    check(any("改成 5 比特" in body and "一个 3 比特的 GHZ 态并全测量" in body
              for body in bodies),
          "有一次请求同时带上了这一轮和上一轮的原话")

    # 缺配置时不能崩，要告诉用户怎么配，并且用非零退出码表示"没真正跑起来"。
    #
    # ★ 这一条**光清环境变量是测不出来的**：清掉之后 envfile 会去几个约定位置
    #   找 .env 补上，而开发机上那个文件就在 cwd 里，于是配置照样被找到，
    #   断言全绿但什么都没测到（第一版就是这样假通过的，和 NoConfig 当初一个毛病）。
    #   所以这里连"去哪儿找文件"一起在子进程里接管掉——接管写在测试侧，
    #   不为了测试往产品代码里加开关。
    blank = os.environ.copy()
    for key in ENV_KEYS:
        blank.pop(key, None)
    done = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r)\n"
         "from starter_kit.loomq import envfile\n"
         "envfile.search_paths = lambda: ()\n"      # 模拟一台什么都没配的机器
         "from starter_kit import loomq_cli\n"
         "sys.exit(loomq_cli.main(['--chat']))\n" % _REPO_ROOT],
        input="", capture_output=True, text=True, timeout=300, env=blank,
    )
    check(done.returncode == 2,
          "--chat 缺配置时退出码为 2（表示没真正跑起来，而不是假装成功），实际 %d"
          % done.returncode)
    check(all(key in done.stdout for key in ENV_KEYS),
          "--chat 缺配置时把三个变量名都告诉了用户")
    check("Traceback" not in done.stderr, "--chat 缺配置时没有抛异常栈到用户脸上")


def section_evidence():
    header("十一 · 证据包与代码不许说两套话")
    print("   赛题第五节 2 要求证据包写明「启动命令、测试入口和 3 个现场体验任务」，")
    print("   工作人员照着跑。所以那三个任务的文字必须和代码里的完全一致——")
    print("   改了一处忘了另一处，评委照着文档敲出来的就不是我们测过的东西。")

    from starter_kit import loomq_cli

    evidence = os.path.join(_REPO_ROOT, "starter_kit", "evidence", "README.md")
    with open(evidence, encoding="utf-8") as handle:
        text = handle.read()

    check(len(loomq_cli.EXPERIENCE_TASKS) == 3, "代码里正好 3 个现场体验任务")
    for index, (label, sentence, dimension, _why) in enumerate(
            loomq_cli.EXPERIENCE_TASKS, start=1):
        check(label in text, "证据包里有任务 %d 的界面文字" % index)
        check(sentence in text, "证据包里有任务 %d 实际发出去的那句话" % index)
        check(dimension in text, "证据包里写明了任务 %d 对应的评分项「%s」" % (index, dimension))

    for dimension in ("交互友好度", "结果可视化", "容错提示"):
        check(dimension in text, "10 分那一项的三个评分词都被覆盖：%s" % dimension)

    check("bash loomq.sh chat" in text, "证据包里的启动命令与 loomq.sh 的子命令一致")
    for path in ("loomq.sh", "SUBMISSION.md"):
        check(os.path.isfile(os.path.join(_REPO_ROOT, path)), "%s 存在" % path)

    with open(os.path.join(_REPO_ROOT, "SUBMISSION.md"), encoding="utf-8") as handle:
        submission = handle.read()
    # 必答题占工程与产品化那 10 分里的一条，空着等于白扣。
    # 之前这里断言的是"留着 TODO(CY)"（提醒别代笔）；填完之后断言反过来：
    # 不许再出现待办标记，而且两个版本都得在。
    check("TODO(CY)" not in submission and "（待填）" not in submission,
          "必答题已填，没有残留的待办标记")
    check("### 版本一 · 参赛者（CY）" in submission and "### 版本二 · 写代码的 Claude" in submission,
          "必答题交的是两个版本：参赛者本人写的，和写代码的 Claude 写的")
    check("我的工具做不到这一点。" in submission,
          "参赛者那一版原话未被改写（这一句是它的第一句）")

    # ---- 真机证据：文件、证据包、核验三者不许各说各的 ----
    print("\n   真机证据是人工评分项，评测组会抽样登录平台复核 job_id。")
    print("   所以这里钉三件事：结果文件在、job_id 写进了证据包、主峰与平台导出对得上。")
    import io
    import contextlib
    from starter_kit.tools import run_on_hardware as hw

    evidence_files = os.path.join(_REPO_ROOT, "starter_kit", "evidence", "files")
    for name in ("bell", "ghz3", "bitorder"):
        result = os.path.join(evidence_files, "originq-wukong-%s-result.json" % name)
        check(os.path.isfile(result), "真机结果文件在：%s" % os.path.basename(result))
        if not os.path.isfile(result):
            continue
        with open(result, encoding="utf-8") as handle:
            payload = json.load(handle)
        check(payload["job_id"] in text,
              "%s 的 job_id 写进了证据包（评测组要靠它溯源）" % name)
        check(payload["bit_order"] == "little", "%s 的 bit_order 按规范填 little" % name)
        check(payload["backend"] == "originq_wukong",
              "%s 用的是《后端能力表》里的规范标识" % name)

    # 量旋（第二个平台）
    for name in ("bell", "ghz3", "bitorder"):
        result = os.path.join(evidence_files, "spinq-%s-result.json" % name)
        check(os.path.isfile(result), "量旋结果文件在：%s" % os.path.basename(result))
        if not os.path.isfile(result):
            continue
        with open(result, encoding="utf-8") as handle:
            payload = json.load(handle)
        check(payload["job_id"] in text, "量旋 %s 的 job_id 写进了证据包" % name)
        check(payload["backend"] == "spinq_cloud_qpu",
              "量旋 %s 用的是《后端能力表》里的规范标识" % name)

    # ★ 位序：量旋返回的位串与赛题规范相反，中间层必须翻过来。
    #   这条只有不对称电路测得出来——Bell/GHZ 的理想分布是回文的。
    with open(os.path.join(evidence_files, "spinq-bitorder-result.json"), encoding="utf-8") as h:
        bo = json.load(h)
    top = max(bo["counts"], key=bo["counts"].get)
    check(top == "01",
          "量旋位序已归一化：x q[0] 的主峰是 01（规范要求最右为 c[0]），实测 %s" % top)
    raw_top = max(bo["meta"]["platform_raw"], key=bo["meta"]["platform_raw"].get)
    check(raw_top == "10",
          "而平台原始返回的是 %s——证明翻转真的发生了，不是碰巧两边一致" % raw_top)

    # 复用真机脚本自己的核验逻辑，别在测试里另写一份判据
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        verdict = hw.verify()
    check(verdict == 0,
          "`loomq.sh hardware --verify` 通过：主峰命中，且与平台控制台导出的文件逐位一致")
    check("位序" not in captured.getvalue() or "01，应为 01  ✅" in captured.getvalue(),
          "位序自检在真机上也过了（Bell/GHZ 是回文分布，验不出位序，靠这条）")

    # ---- submission.yaml 的声明必须与实际参赛档位一致 ----
    print("\n   starter_kit/README.md：「若参加 L2，请把 levels.l2 与")
    print("   network.required_for_l2 **同时**改为 true」。声明成 false 而评测器")
    print("   据此断网，12 个 L2 case 会全部失败——这一条是提交前逐项复查时抓到的。")
    declared = {}
    with open(os.path.join(_REPO_ROOT, "starter_kit", "submission.yaml"), encoding="utf-8") as h:
        section = None
        for raw in h:
            line = raw.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            key, _, value = line.strip().partition(":")
            key, value = key.strip(), value.strip().strip('"')
            if not line.startswith(" "):
                # 顶层：有值的是标量键（starter_kit_version），没值的是段落名（network:）
                section = key
                if value:
                    declared[key] = value
            elif value or value == "":
                declared["%s.%s" % (section, key)] = value
    check(declared.get("levels.l2") == "true", "submission.yaml 声明参加 L2")
    check(declared.get("network.required_for_l2") == "true",
          "并且同时声明 L2 需要网络（否则评测器可能断网跑，12 个 case 全挂）")
    check(declared.get("levels.l1") == "true" and declared.get("levels.l3") == "true",
          "L1 / L3 也都声明参加")
    with open(os.path.join(_REPO_ROOT, "starter_kit", "VERSION"), encoding="utf-8") as h:
        version = h.read().strip()
    check(declared.get("starter_kit_version") == version,
          "starter_kit_version 与 VERSION 文件一致（%s）" % version)

    with open(os.path.join(_REPO_ROOT, ".gitignore"), encoding="utf-8") as handle:
        ignored = handle.read()
    check(".venv/" in ignored,
          "loomq.sh 建的虚拟环境（约 620 MB）被 .gitignore 挡住"
          "——归档上限 100 MiB，且预检要求工作区干净")


def main():
    section_backend()
    section_generate()
    section_retry()
    section_giveup()
    section_independent_judge()
    section_robust()
    section_contract()
    section_no_false_reject()
    section_official_case()
    section_non_circuit()
    section_cli()
    section_evidence()

    print("\n" + "=" * 70)
    if failures:
        print("失败 %d 项：" % len(failures))
        for item in failures:
            print("  - " + item)
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
