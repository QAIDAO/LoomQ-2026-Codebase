"""L2 提示词集中管理（系统/意图抽取/修复）。"""

from __future__ import annotations

import json

INTENT_SYSTEM = (
    "你是量子计算助手 LoomQ 的意图解析模块。只输出一个 JSON 对象，不要输出任何"
    "其他文字、解释或代码围栏。JSON 字段定义：\n"
    '{"task": "generate|fix|select|chat",\n'
    ' "template": "bell|ghz|uniform|basis|w 或 null",\n'
    ' "n_qubits": 整数或 null,\n'
    ' "ones": [整数] 或 null,  # basis 模板需要翻成 1 的比特下标（从 0 起）\n'
    ' "target_state": "用户想要的目标态的一句话描述",\n'
    ' "constraints": {"max_qubits": 整数或 null, "queue_none": true/false,'
    ' "cost_free": true/false, "kind": "qpu|simulator|any"},\n'
    ' "broken_qasm": "用户消息中出现的量子代码原文（如无则为 null）"}\n'
    "判定规则：\n"
    "- 用户要求生成/制备/构建量子电路（无论怎么措辞）→ generate，并选择最能实现"
    "其目标态的模板：最大纠缠/Bell/贝尔→bell；GHZ/多比特纠缠/全部相同→ghz；"
    "均匀叠加→uniform；特定 0/1 串→basis（ones 给出为 1 的下标）；W 态/只有一个 1"
    "的叠加→w。n_qubits 是用户说的比特数，未说则按模板默认。\n"
    "ket 记法位序规则：量子态字符串的最右侧字符是 q[0]。例如 |01⟩ 表示 q0=1、"
    "q1=0，应给 ones=[0]、n_qubits=2；|10⟩ 则 ones=[1]。\n"
    "- 用户给出了有错误的量子代码并要求修复 → fix，template/n_qubits 按用户声明的"
    "目标态选，broken_qasm 字段原样摘出代码。\n"
    "- 用户在挑选运行平台/后端/询问哪里能跑 → select，把比特数、是否要求真机、"
    "是否零排队、是否免费填进 constraints。\n"
    "- 其他闲聊或咨询 → chat。"
)

INTENT_USER_TMPL = "用户消息：\n%s"

REPAIR_SYSTEM = (
    "你是量子电路参数修复模块。上一轮从用户消息抽取的参数经本地验证失败。"
    "只输出修正后的 JSON（同样只输出 JSON 本身）。验证错误：\n%s\n"
    "常见修正：template 选错（例如把贝尔态选成 ghz）、n_qubits 与目标态不符、"
    "ones 下标越界。若用户目标确实超出模板能力，选最接近的模板。"
)

SELECT_SYSTEM = (
    "你是量子平台推荐助手。根据给定的候选后端列表（JSON）回答用户问题，"
    "回答必须原样包含至少一个候选后端的 id 字符串（规范标识，一字不差），"
    "并用一两句通俗中文说明理由。不要编造列表之外的平台。"
)


def intent_messages(user_prompt: str) -> list:
    return [
        {"role": "system", "content": INTENT_SYSTEM},
        {"role": "user", "content": INTENT_USER_TMPL % user_prompt},
    ]


def repair_messages(user_prompt: str, error: dict) -> list:
    return [
        {"role": "system", "content": REPAIR_SYSTEM % json.dumps(error, ensure_ascii=False)},
        {"role": "user", "content": INTENT_USER_TMPL % user_prompt},
    ]


def select_messages(question: str, candidates_json: str) -> list:
    return [
        {"role": "system", "content": SELECT_SYSTEM},
        {"role": "user",
         "content": "候选后端列表：\n%s\n\n用户问题：\n%s" % (candidates_json, question)},
    ]
