#!/usr/bin/env python3
"""L2 智能体：把人话变成能跑的量子电路

对外只有一个入口 `agent_chat(prompt) -> str`，评测系统直接调它。

**这个文件的核心主张：模型只负责听懂人话，不负责给出答案。**

    用户的话 ──[模型]──> 结构化的意图 ──[确定性代码]──> 答案

为什么这么切：

- 选后端这类问题**有唯一正确答案**（查官方能力表）。让模型背表，它迟早背错一行；
  让代码查表，就不可能错。
- 生成电路这类问题没有唯一写法，但**有唯一验收标准**——跑出来的分布对不对。
  所以模型写完之后，我们**真的把它跑一遍**，不对就带着具体错误让它重写。

赛题推荐的正是这个闭环："生成 QASM → 用自己的 L1 跑一遍自验 → 不对就重试"。
我们的 L1 已经写好了，所以自验是现成的。

配置全部从环境变量读（`LOOMQ_LLM_BASE_URL` / `LOOMQ_LLM_API_KEY` / `LOOMQ_LLM_MODEL`），
**不硬编码任何服务地址、密钥或模型名**——这是赛题的硬性要求，
也顺带带来一个好处：换成任何 OpenAI 协议的服务都不用改代码。
"""

import json
import re
import time

try:
    from .. import llm_client
except (ImportError, ValueError):  # 允许把 starter_kit 直接加进 sys.path 使用
    import llm_client

try:
    from . import backend_selector, qasm_parser
    from .backends import execute
    from .target_states import describe, ideal_distribution
except ImportError:
    import backend_selector
    import qasm_parser
    from backends import execute
    from target_states import describe, ideal_distribution


# 自验用的后端与采样次数。originq 最快，跑不了就退到 braket。
SELF_CHECK_TARGETS = ("originq", "braket")

# ★ 这两个数字必须和评委的判据**完全一致**，不能自作主张调严。
#
# 一开始写的是 2048 次采样、阈值 0.99（想着"比评测的 0.97 更严，留余量"），
# 结果测出来正确的 GHZ-3 电路会拿到 0.9893 —— 被自己打回去了。
# 原因是采样本身就有涨落：2 个结果、2048 次采样时，完美电路的保真度
# 期望值也只有 0.992 左右，压根碰不到 0.99 这条线。
#
# 后果不只是多跑一轮：重试次数用完后，一个**本来正确**的电路会以
# "没有通过自验"的名义交出去，白白丢分。
#
# 所以自验的职责是**复刻评委的判据**，不是自创一个更难的。
# 8192 次采样下，2 个结果的噪声底是 0.994、16 个结果是 0.985，都远高于 0.97；
# 而真正写错的电路（比如 GHZ 写成均匀叠加）保真度只有 0.29 —— 中间隔着鸿沟，
# 不存在"放宽阈值就漏判"的风险。
SELF_CHECK_SHOTS = 8192
SELF_CHECK_FIDELITY = 0.97
# 首次生成之外，最多再让模型改几轮。
# 实测一轮往返约 1.5–2.5 秒，而正式评测每 case 限时 120 秒——时间根本不是瓶颈，
# 所以轮数按"多试几次总比交白卷好"来定，真正的刹车是下面那个 deadline，不是这个计数。
# （这里刻意不写具体模型名：源码里不出现任何模型名/服务地址/密钥，
#   由 tools/verify_l2.py 第六节做静态检查，注释也不放行。）
MAX_FIX_ROUNDS = 4
TIME_BUDGET_SECONDS = 100.0  # 正式评测每 case 限时 120 秒，留 20 秒余量


PLANNER_SYSTEM_PROMPT = """你是量子计算平台的意图解析器。你的唯一职责是把用户的话解析成结构化 JSON。

只输出一个 JSON 对象，不要输出任何别的文字，不要用代码块包裹。

字段：
{
  "task": "generate" | "fix" | "select_backend" | "explain" | "reject" | "unclear",
  "target": {"kind": "ghz"|"bell"|"w"|"uniform"|"basis"|"unknown", "qubits": 整数, "bits": "仅 basis 时填，如 101"},
  "constraints": {"min_qubits": 整数, "kind": "simulator"|"qpu"|"cloud", "queue": "none", "cost": "free"|"no_paid", "allow_account": true|false, "platform": "spinq"|"originq"|"braket"},
  "qasm": "完整的 OpenQASM 2.0 程序",
  "note": "一句话说明你的理解"
}

task 怎么判（**按这个顺序判，前面的命中了就不要再考虑后面的**）：
1. 用户在问用哪个平台 / 能不能在真机上跑 / 要多少比特 / 排队和费用 -> select_backend
   **即使他的条件根本满足不了（比如"真机 100 比特还不许排队"），也仍然是 select_backend。**
   查表会逐条告出哪一项满足不了、最接近的是哪几个，这比一段泛泛的解释有用得多。
2. 用户给了一段有问题的代码要求修复 -> fix
3. 用户在**问问题**（某个门是什么意思、量子为什么这样、我该从哪开始），而不是要一段电路 -> explain
4. 用户要的事情**量子计算这门技术本身做不了或不适合**（挖矿、炒股、写代码、生成图片），
   或者用户的**前提本身是错的**（比如"量子计算能同时试出所有答案"）-> reject
   注意：只是超出本平台的规模上限，不属于这一类，那是第 1 条。
5. 用户只表达了"想试试"但**没说要什么**，信息不足以确定一个目标 -> unclear
6. 其余情况 -> generate

**拿不准就选 generate。** 只要用户是在要一段电路，哪怕话说得又短又不规范
（例如"ghz 3bit 跑一下"），也一律 generate，不要因为格式不规范就判成 unclear。

各 task 该填什么：
- select_backend 时只填 constraints，不填 target 和 qasm。用户没提到的约束项一律省略，不要臆造。
- generate / fix 时必须填 target 和 qasm，不填 constraints。
- explain / reject / unclear 时**不要填 qasm**，target 填 {"kind": "unknown"}，
  note 写一句话说明用户到底在问什么或者错在哪。
- fix 时必须保持用户声明的目标态不变，只改正错误。
- target.kind 只有在你确信时才填具体值，否则填 "unknown"。
- qasm 必须是完整可执行的 OpenQASM 2.0：以 OPENQASM 2.0; 开头，包含 include "qelib1.inc";、qreg、creg、门操作和 measure。
- 只允许使用这 12 个门：h, x, s, sdg, t, tdg, rz(θ), ry(θ), cx, cu1(θ), swap, ccx。
- 用户说"全测量"时，每个量子比特都要测量到对应的经典比特。

平台限制与对应写法（重要，白名单之外的门一律不可用，必须按下面改写）：
- 没有受控旋转门。controlled-RY(θ) 控制位 a、目标位 b，写成：
    ry(θ/2) q[b]; cx q[a],q[b]; ry(-θ/2) q[b]; cx q[a],q[b];
  controlled-RZ(θ) 同理，把 ry 换成 rz。
- 没有 z / y / cz / cy / u1 / u2 / u3 / p。z 用 rz(pi) 代替；cz 用 h q[b]; cx q[a],q[b]; h q[b]; 代替。
- 需要把振幅按不等比例分给多个基态时，用 ry 配合上面的受控旋转分解逐级传递。
"""

FIXER_SYSTEM_PROMPT = """你是 OpenQASM 2.0 修复器。用户给你一段电路和它的实测问题，你要改正它。

只输出一个 JSON 对象，不要输出别的文字，不要用代码块包裹：
{"qasm": "修正后的完整 OpenQASM 2.0 程序", "note": "一句话说明你改了什么"}

规则：
- 必须保持原本要达成的目标态不变。
- 只允许使用这 12 个门：h, x, s, sdg, t, tdg, rz(θ), ry(θ), cx, cu1(θ), swap, ccx。
- 必须是完整程序：OPENQASM 2.0; / include "qelib1.inc"; / qreg / creg / 门 / measure。
- 问题描述里如果写了实测分布，请据此判断哪一步错了，不要重复同样的错误。
  特别注意"实测里多出来的基态"和"应该出现却没出现的基态"，它们直接指出哪一步的纠缠或旋转接错了。

平台限制与对应写法（白名单之外的门一律不可用）：
- 没有受控旋转门。controlled-RY(θ) 控制位 a、目标位 b，写成：
    ry(θ/2) q[b]; cx q[a],q[b]; ry(-θ/2) q[b]; cx q[a],q[b];
  controlled-RZ(θ) 同理，把 ry 换成 rz。
- 没有 z / y / cz / cy / u1 / u2 / u3 / p。z 用 rz(pi) 代替；cz 用 h q[b]; cx q[a],q[b]; h q[b]; 代替。
"""

JUDGE_SYSTEM_PROMPT = """你的唯一职责是读懂用户想要什么**目标态**，然后输出一个 JSON。

只输出这个 JSON，不要输出别的文字，不要用代码块包裹：
{"kind": "ghz"|"bell"|"w"|"uniform"|"basis"|"gates"|"unknown", "qubits": 整数, "bits": "仅 basis 时填，如 101"}

判断规则：
- 说"最大纠缠态"、"GHZ"、"所有比特要么全 0 要么全 1" -> ghz
- 说"贝尔态"、"两个比特永远一致" -> bell
- 说"恰好一个比特是 1"、"W 态" -> w
- 说"等概率"、"每种结果一样多"、"一半一半"、"一半正面一半反面"、"随机" -> uniform
  （n 个比特的均匀叠加，一个比特时就是 0 和 1 各一半）
- 说"结果固定是 101 这种"、"确定的某一个结果" -> basis
- ★ 用户直接报的是**操作步骤或门的名字**（"先做一个 H 再做一个 H"、
  "H 门，测量，再 H 门"、"加一个 cx"），而**没有说想得到什么结果** -> gates
  这一类不要试着替他推算最后是什么分布，填 gates 就好。
- 看不出来就填 unknown。**宁可填 unknown，也不要猜。**

为什么要单独分出 gates：你说的东西会被当成验收标准。上面那几个名字各自
对应一个确定的分布，能拿来比对；而"连做两次 H"这种说法**不在这套词汇里**，
硬套一个最像的（比如 uniform）会造出一个错的标准——错的电路配上错的标准，
反而能拿到接近满分的保真度，一路绿灯交给用户。**这种事真发生过。**

★ 你**看不到**任何电路，这是故意的。你只根据用户的原话判断他想要什么。
  你说出来的东西会被当成验收标准去检查别人写的电路，所以你绝不能受那段电路影响。
"""

EXPLAIN_SYSTEM_PROMPT = """你在帮一个**完全没有物理背景**的人理解量子计算。对方可能连「比特」都没听过。

只输出给对方看的正文。不要输出 JSON，不要用代码块，不要列 markdown 标题。

硬规则：
- 不用行话。非要用到「叠加」「纠缠」「振幅」「量子态」这类词时，先用一句日常的话说清它指什么。
- **不许夸大。**特别不要说量子计算「能同时算出所有答案」「一定比经典计算机快」
  「能拿来破解所有密码」——这些是最常见的误解，说了等于骗人。
- 不知道就说不知道，不要编。
- ★ **不许摆"我知道但说不清"的姿态。**这类话一句都不许出现：
    "这取决于程序内部的规则" / "不是一两句话能说清的" /
    "这背后涉及复杂的数学" / "细节比较深入"
  它们读起来就是解释不清在嘴硬，比直接承认不懂难看得多。
  只有两条路可选：**用大白话讲清楚**，或者**直说"这个我讲不清"**。没有第三条。
- 上下文里要是给了具体的电路和实测数字，就**针对那些数字**解释，
  引用它们（"你那两行里第二个 H 把……"、"所以 0 占了 100%"）。
  泛泛地讲一遍概念不算回答。
- 不要提任何具体的服务商、模型或产品名。
- **对方已经在一个能直接跑量子程序的环境里**，正在跟这个程序对话。
  所以不要建议他"去找一个模拟器""去装个工具""先看点资料"——他要的东西此刻就在手边。
- 不要劝对方"先把理论学明白再动手"。这里的路子是先跑起来看见现象，再回头理解。
- 最多 150 字，说完就停。宁可少说，不要说满。
- **不要推荐任何具体实验，不要说"第一个实验就做某某"，也不要给示例代码。**
  你回答完之后，程序会紧接着列出这套环境**确实提供**的那几件事。
  你要是自己点了一个具体实验的名字，跟那份清单对不上，对方就会被指到一件
  他做不了的事上——那比不回答更糟。你只负责把道理说清楚，能做什么由程序来说。

如果对方的话里含有对量子计算的误解，**先用一句话点明误解在哪**，再说正确的说法。
"""


def agent_chat(prompt):
    """L2 对外入口。任何情况下都返回一段文本，不向调用方抛异常。"""
    deadline = time.monotonic() + TIME_BUDGET_SECONDS
    try:
        plan = _make_plan(prompt)
    except Exception as exc:  # noqa: BLE001
        return _model_unavailable_reply(exc)

    task = str(plan.get("task", "")).strip().lower()
    if task == "select_backend":
        return _reply_backend(plan)
    if task in NON_CIRCUIT_TASKS and not _contradicts(task, plan):
        return _reply_non_circuit(prompt, task, plan)
    return _reply_circuit(prompt, plan, deadline)


# ★ 不生成电路的三条路。**加这三条路是因为实测被撞出来的**：
#
# 原先只有"生成电路"和"选后端"两条路，于是任何输入都被硬塞进生成电路。
# 用 tools/probe_l2_robustness.py 打过去的结果是：用户说"帮我挖矿"、
# 说"量子能同时试出所有答案帮我破密码"、贴一段普通 Python，
# 三种情况全都收到一段一本正经的单比特电路 —— 装懂、顺着错前提答、
# 还给出一个毫无意义的产物。而模型其实判断对了（它在 note 里写了
# "量子计算并不适合传统挖矿"），只是我们没给它一条能表达"这事不该做"的路。
#
# 对照组是"选后端"：那条路的判断由代码查表完成，实测表现最好。
# 结论就是把"这件事该不该做"的守门权从模型手里收回到代码里。
NON_CIRCUIT_TASKS = ("explain", "reject", "unclear")


def _contradicts(task, plan):
    """这个 task 标签是不是自相矛盾？矛盾就不认，退回去生成电路。

    **为什么要有这道检查。**误判的代价是不对称的：
    - 把"其实不该生成"判成生成，只是回复不好看，扣的是交互体验的主观分；
    - 把"其实是正常请求"判成不生成，等于交白卷，直接丢客观分。

    所以只在标签**自己跟自己打架**时才推翻它，不做任何猜测性的推翻：
    `unclear` 的意思就是"没看出用户要什么"，可是 target 已经认出来了 ——
    那它就不是 unclear。（"ghz 3bit 跑一下"正是这种：话很不规范，但要什么很清楚。）

    explain / reject 是模型做出的语义判断，代码没有更好的依据去反驳，一律尊重。
    """
    if task == "unclear":
        return ideal_distribution(plan.get("target")) is not None
    return False


# --------------------------------------------------------------------------
# 第一步：让模型把人话解析成结构
# --------------------------------------------------------------------------


def _make_plan(prompt):
    response = llm_client.chat_completion(
        [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    )
    return _extract_json(_message_text(response))


def _message_text(response):
    try:
        return response["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("模型返回的结构不符合 OpenAI 协议：%r" % (response,)) from exc


def _extract_json(text):
    """从模型回复里挖出 JSON。模型经常会加代码块围栏或前后废话，都要能扛住。"""
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except ValueError:
        pass

    # 退而求其次：找第一个花括号配对的片段
    start = text.find("{")
    while start >= 0:
        depth = 0
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start : index + 1])
                        if isinstance(parsed, dict):
                            return parsed
                    except ValueError:
                        break
        start = text.find("{", start + 1)

    raise RuntimeError("模型没有返回可解析的 JSON，原文开头：%r" % text[:200])


# --------------------------------------------------------------------------
# 选后端：交给确定性的筛选逻辑
# --------------------------------------------------------------------------


def _reply_backend(plan):
    constraints = plan.get("constraints")
    if not isinstance(constraints, dict):
        constraints = {}
    result = backend_selector.select(constraints)
    reply = backend_selector.format_reply(result)
    return reply + "\n\n---\n" + BACKEND_FOOTER


# --------------------------------------------------------------------------
# 不生成电路的三条路：解释 / 说清做不到 / 问清楚要什么
# --------------------------------------------------------------------------


# 这份清单是**写死在代码里**的，不由模型生成。
# 理由跟选后端那条路一样：能不能做到这件事，是确定的事实，不该让模型即兴发挥。
# 三条各自对应一个能亲眼看见的现象，而且都在 verify_l2 里跑过。
# 每一项：(发给自己的原话, 用户视角的问题, 会看到什么)
#
# ★ 中间那个字段是**用户视角的问题**，不是功能名。这是改过来的。
#   原先写的是"替你写电路 / 修好一段电路 / 帮你选平台"——那是赛题的评分项分类，
#   我把评分表的目录直接端给了用户。一个不知道量子是什么的人不会想
#   "我要修一段坏电路"，那三个词只对已经懂的人有意义。
#   零基础的人真正会问的是"这玩意儿跟普通电脑到底哪里不一样"。
#
# ★ 第一项是"抛硬币"：它是最小的一个量子程序，也是三关的第一关。
#   原先第一项直接跳到 3 比特纠缠态，而模型被问"第一个实验做什么"时
#   会自然地答"就做抛硬币"——清单里却没有它，等于叫人去做一件我们不提供的事。
# ★ 中间那个字段是给人看的标签，它必须**说清会看到什么**，落在日常语言里。
#
#   写过一版是"三个东西永远一致，这可能吗"、"一个东西能同时压在两边吗"。
#   那是空话：没说三个什么东西，也没说是哪两边——**含糊比术语更糟**，
#   术语至少能查，含糊连读都读不通。
#
#   还删掉了一项"2 比特四种结果等概率"。它不是标签没写好，是**这件事本身
#   什么都没展示**：两枚普通硬币一起掷也是四种各四分之一。我当时是在列
#   "系统能做什么"，而不是"什么值得看"。
#
# 真正反直觉的那两个（连掷两次 100% 正面、中间偷看一眼就变回一半一半）
# 不在这里，因为它们只能说成**门的序列**，而验收标准的词汇表里没有这种东西
# （见 JUDGE_SYSTEM_PROMPT 里 gates 那一条）——验不了的东西不摆出来卖。
# 那两个由三关负责，那边电路是写死的、结果是确定的。
STARTERS = (
    ("做一个 1 比特的电路，让结果一半正面一半反面，并且测量",
     "掷一枚量子硬币几千次，看正反各占多少",
     "最小的一个量子程序，也是后面所有东西的地基"),
    ("生成一个 3 比特的最大纠缠态，并全部测量",
     "三枚硬币一起掷：只会「全正」或「全反」，中间那六种一次都不出现",
     "八种组合里有六种概率是零。这不是概率小，是真的一次都不出现"),
)

# 命令行入口靠这两个标记认出回复的类型，好接上对应的下一步。
# **两边都是我们自己写的**，所以这算一份约定，不是在猜模型的输出。
STARTER_LEAD = "你现在这套环境**确定能做**的事（下面每句话都可以直接复制发给我）："
BACKEND_FOOTER = (
    "这个结论不是模型「记得」的，是直接查官方《后端能力表》比对出来的——"
    "模型只负责把你的话翻译成条件，查表由代码完成，所以不会背错。"
)


def _starter_menu(lead=STARTER_LEAD):
    lines = [lead]
    for text, _question, effect in STARTERS:
        lines.append("  - `%s`" % text)
        lines.append("      → %s" % effect)
    return lines


def _reply_non_circuit(prompt, task, plan):
    if task == "unclear":
        # 没说要什么，不需要模型再解释一遍，直接问清楚 + 给可选项。
        # 清单的引导句统一用 STARTER_LEAD，命令行入口靠它一个字符串就能把
        # 这段切掉换成可敲编号的版本——引导句要是每处写得不一样，那边就得猜。
        lines = [
            "我可以帮你把想法变成一段真的能跑的量子程序，但得先知道你想看到什么。",
            "",
        ]
        lines += _starter_menu()
        return "\n".join(lines)

    if task == "reject":
        framing = (
            "用户说：%s\n\n"
            "这件事量子计算做不了、不适合，或者用户的前提本身就是错的。"
            "请先用一句话说清做不到什么 / 前提哪里错了，再简短说说量子计算实际擅长什么。"
            % prompt
        )
        fallback = "你要的这件事，量子计算做不了或者并不适合——与其给你一段跑不出意义的程序，我先说清这一点。"
    else:  # explain
        framing = "用户问：%s\n\n请回答这个问题。" % prompt
        fallback = "这个问题我需要连上模型才能好好回答，现在连不上。"

    body = _ask_prose(framing) or fallback
    lines = [body.strip(), "", "---", ""]
    lines += _starter_menu()
    return "\n".join(lines)


def _ask_prose(user_content):
    """让模型写一段给零基础用户看的正文。失败就返回 None，由调用方兜底。

    这段文字是模型自由生成的，**无法自动验证**，所以两处上了缰绳：
    系统提示明确禁止那几个最常见的夸大说法；而回复里真正可执行的部分
    （上面那份清单）由代码写死，不经过模型。
    """
    try:
        response = llm_client.chat_completion(
            [
                {"role": "system", "content": EXPLAIN_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ]
        )
        return _message_text(response).strip() or None
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------
# 生成 / 纠错：写完真的跑一遍，不对就重写
# --------------------------------------------------------------------------


def _reply_circuit(prompt, plan, deadline):
    # ★ 验收标准**不用**写电路那次调用给出的 target。
    #
    # 实测撞出来的：用户说"做一个 1 比特的电路，让结果一半正面一半反面"，
    # 模型交回来的电路一个门都没有（只有 measure），同时把目标态申报成
    # "确定的基态 0"。于是拿错答案去对错标准，保真度 1.0000，一路绿灯——
    # 而它自己的说明里还写着"使用 Hadamard 门实现均匀叠加"。
    #
    # 根子不在阈值，在**答案和标准出自同一次调用**：只要两者一致地错，自验必然通过。
    # 这就是既当运动员又当裁判员。所以标准改由一次独立调用给出，
    # 那次调用只看用户的原话、**看不到任何电路**（见 JUDGE_SYSTEM_PROMPT）。
    target = _declare_target(prompt)
    if ideal_distribution(target) is None:
        # 独立判断认不出来时，退回写电路那次的申报——它至少能让 describe() 说点人话。
        # 认不出来本来就不做分布比对，所以这里不存在"用它当标准"的风险。
        target = plan.get("target") if isinstance(plan.get("target"), dict) else {}
    qasm = plan.get("qasm")
    history = []

    for attempt in range(MAX_FIX_ROUNDS + 1):
        if not isinstance(qasm, str) or "OPENQASM" not in qasm.upper():
            problems = ["模型没有给出 OpenQASM 2.0 程序"]
            evidence = None
        else:
            problems, evidence = _self_check(qasm, target)

        if not problems:
            return _success_reply(qasm, target, evidence, attempt, plan.get("note"))

        history.append(problems)
        if attempt >= MAX_FIX_ROUNDS or time.monotonic() > deadline:
            break
        try:
            qasm = _ask_fix(prompt, qasm, problems)
        except Exception:  # noqa: BLE001
            break

    return _failure_reply(qasm, target, history)


def _declare_target(prompt):
    """独立判一次"用户想要什么目标态"。只看原话，看不到电路。

    失败就返回空字典——那时自验退回结构检查，不做分布比对。
    """
    try:
        response = llm_client.chat_completion(
            [
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )
        parsed = _extract_json(_message_text(response))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _self_check(qasm, target):
    """把电路真的跑一遍。返回 (问题列表, 实测证据)。问题列表为空即通过。"""
    try:
        circuit = qasm_parser.parse(qasm)
    except Exception as exc:  # noqa: BLE001
        return ["解析失败：%s" % exc], None

    if circuit.num_qubits == 0:
        return ["电路里没有声明任何量子比特"], None
    if not circuit.measurements:
        return ["电路里没有任何 measure 语句，跑出来不会有结果"], None
    if not circuit.gates:
        # 一个门都没有的电路只会把初始状态原样测出来，永远是 100% 全 0。
        # 这一条**不依赖任何目标态**就能判死，所以即使目标态判错了也拦得住——
        # 上面那个"一半正面一半反面"的例子交回来的正是这种电路。
        return ["电路里没有任何量子门，只有测量——这样跑出来必然是 100% 全 0"], None

    measured = {op.qubit for op in circuit.measurements}
    if len(measured) < circuit.num_qubits:
        missing = sorted(set(range(circuit.num_qubits)) - measured)
        return ["这些量子比特没有被测量：%s" % ", ".join("q[%d]" % q for q in missing)], None

    last_error = None
    for backend in SELF_CHECK_TARGETS:
        try:
            payload = execute(circuit, backend, SELF_CHECK_SHOTS)
            break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    else:
        return ["电路无法执行：%s" % last_error], None

    observed = {key: value / SELF_CHECK_SHOTS for key, value in payload["counts"].items()}
    evidence = {"backend": payload["backend"], "counts": payload["counts"], "shots": SELF_CHECK_SHOTS}

    ideal = ideal_distribution(target)
    if ideal is None:
        # 认不出目标态时不做分布比对——宁可少判，不要判错
        evidence["fidelity"] = None
        return [], evidence

    fidelity = _hellinger_fidelity(observed, ideal)
    evidence["fidelity"] = fidelity
    if fidelity < SELF_CHECK_FIDELITY:
        return [
            "实测分布与目标态不符（保真度 %.4f，需要 ≥ %.2f，与评测阈值一致）。实测：%s；应为：%s"
            % (
                fidelity,
                SELF_CHECK_FIDELITY,
                _short(observed),
                _short(ideal),
            )
        ], evidence
    return [], evidence


def _ask_fix(prompt, qasm, problems):
    response = llm_client.chat_completion(
        [
            {"role": "system", "content": FIXER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "用户最初的要求：\n%s\n\n当前电路：\n%s\n\n实测发现的问题：\n%s"
                % (prompt, qasm, "\n".join("- " + item for item in problems)),
            },
        ]
    )
    return _extract_json(_message_text(response)).get("qasm")


def _hellinger_fidelity(observed, expected):
    import math

    states = set(observed) | set(expected)
    distance = math.sqrt(
        sum(
            (math.sqrt(observed.get(state, 0.0)) - math.sqrt(expected.get(state, 0.0))) ** 2
            for state in states
        )
    ) / math.sqrt(2.0)
    return max(0.0, min(1.0, 1.0 - distance))


def _bars(counts, limit=8, width=30):
    """把采样结果画成横条。赛题第五节 3 把「结果可视化」写进了评分标准。

    一串"`000` 出现 4080 次（49.8%）"式的文字，零基础的人得逐行读、
    在脑子里比大小才知道发生了什么；画成条之后，"两条一样长、别的一条都没有"
    是一眼的事——而这一眼恰好就是纠缠的那个现象。

    条长按**最高的一条**归一化，不是按 100%。因为均匀叠加 8 个结果时
    每条只占 12.5%，按 100% 画出来全是一格，什么都看不出来；
    按最高归一化则是 8 条一样长，正好读作"所有结果一样多"。
    准确的数值就印在条子右边，所以归一化方式不会造成误读。
    """
    total = sum(counts.values()) or 1
    top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    if not top:
        return ["（没有任何结果）"]
    peak = top[0][1] or 1
    key_width = max(len(key) for key, _ in top)

    lines = []
    for key, value in top:
        share = value / total
        filled = int(round(width * value / peak))
        bar = "█" * max(filled, 1) if value else ""
        lines.append("  %s │%-*s %5.1f%%  (%d 次)" % (key.rjust(key_width), width, bar, share * 100, value))
    if len(counts) > limit:
        hidden = sorted(counts.values())[: len(counts) - limit]
        lines.append("  %s   还有 %d 个结果，合计 %.1f%%"
                     % (" " * key_width, len(counts) - limit, 100.0 * sum(hidden) / total))
    return lines


def _short(distribution, limit=6):
    items = sorted(distribution.items(), key=lambda item: -item[1])[:limit]
    text = "，".join("%s 占 %.0f%%" % (key, value * 100) for key, value in items)
    return text + ("……" if len(distribution) > limit else "")


# --------------------------------------------------------------------------
# 回复文本
# --------------------------------------------------------------------------


def _success_reply(qasm, target, evidence, attempts, note):
    lines = ["好了。下面这段程序我**已经真的跑过**，不是写完就交给你。", ""]

    what = describe(target)
    if what:
        lines.append("**你要的是**：%s" % what)
    if note:
        lines.append("")
        lines.append("**我的理解**：%s" % note)

    lines.append("")
    lines.append("```qasm")
    lines.append(qasm.strip())
    lines.append("```")
    lines.append("")

    if evidence:
        lines.append("**实测结果**（在 `%s` 上采样 %d 次）：" % (evidence["backend"], evidence["shots"]))
        lines.append("")
        lines.append("```")
        lines += _bars(evidence["counts"])
        lines.append("```")
        if evidence.get("fidelity") is not None:
            lines.append("")
            lines.append("与目标态的保真度 **%.4f**（评测阈值是 0.97）。" % evidence["fidelity"])
        else:
            # ★ 没比对过就必须说出来，不能只是默默不打印那一行。
            # 少一行数字，用户会当成"没什么可说的"，而实际含义是"这次没验分布"——
            # 沉默在这里等于默认担保。真踩过：用户报的是门序列（"先 H 再 H"），
            # 交回来的电路少了一个门，我们没有标准可比，却什么都没提。
            lines.append("")
            lines.append(
                "**这一次我没有比对分布**：你说的是具体的操作步骤，没有说想得到什么结果，"
                "所以我没有可比的标准，只能保证它跑得起来、上面这些数是真跑出来的。"
                "想让我验对不对，就告诉我你期望看到什么结果。"
            )
    if attempts:
        lines.append("")
        lines.append("（第一版没通过自验，改了 %d 轮才对。改的过程你不用管，交给你的是过了的那版。）" % attempts)

    lines.append("")
    lines.append("---")
    lines.append("**为什么要测量这一步**：量子比特在被看之前没有确定的值，")
    lines.append("看一次只会得到一个结果。所以要知道它的「分布」，只能把同一段程序")
    lines.append("重复跑几千次再数数——上面那些百分比就是这么来的。")
    return "\n".join(lines)


def _failure_reply(qasm, target, history):
    lines = ["我没能给出一个**通过自验**的电路，所以不打算把没验过的东西交给你。", ""]
    what = describe(target)
    if what:
        lines.append("**想达成的目标**：%s" % what)
        lines.append("")
    lines.append("**卡在哪里**：")
    for round_index, problems in enumerate(history, start=1):
        for item in problems:
            lines.append("  - 第 %d 轮：%s" % (round_index, item))
    if isinstance(qasm, str) and "OPENQASM" in qasm.upper():
        lines.append("")
        lines.append("这是最后一版的样子，供你参考（**它没有通过自验**）：")
        lines.append("")
        lines.append("```qasm")
        lines.append(qasm.strip())
        lines.append("```")
    lines.append("")
    lines.append("把你的目标说得更具体一点（比如要几个比特、想看到什么结果），我再试一次。")
    return "\n".join(lines)


def _model_unavailable_reply(exc):
    return (
        "我现在连不上模型服务，所以没法把你的话翻译成电路。\n\n"
        "原因：%s\n\n"
        "本程序按赛题要求从环境变量读取配置，需要设置好这三个：\n"
        "  - `LOOMQ_LLM_BASE_URL`\n"
        "  - `LOOMQ_LLM_API_KEY`\n"
        "  - `LOOMQ_LLM_MODEL`\n\n"
        "（不硬编码服务地址与密钥是赛题的硬性要求，也意味着换任何 OpenAI 协议的服务都不用改代码。）"
        % exc
    )
