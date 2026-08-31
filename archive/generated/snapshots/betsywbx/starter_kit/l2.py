import os
import re
import json
import time
from typing import Optional

from llm_client import chat_completion

# match starting of "OPENQASM 2.0;" until next ``` or the end
_QASM_EXTRACT_RE = re.compile(
    r"OPENQASM\s+2\.0;.*?(?=^\s*```|\Z)", re.DOTALL | re.MULTILINE
)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_CAPS_PATH = os.path.join(_THIS_DIR, "backend_capabilities.json")


def _load_backend_capabilities() -> str:
    with open(_BACKEND_CAPS_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _build_system_prompt() -> str:
    backend_caps_json = _load_backend_capabilities()
    return f"""你是 LoomQ 量子计算助手,服务对象是完全没有量子计算背景的用户。
    你需要根据用户的自然语言请求,判断它属于以下三类任务之一(不需要用户明说,自己判断):

    1. 【生成】根据用户描述的意图,直接写出正确的 OpenQASM 2.0 代码。
    2. 【纠错与修复】如果用户提供了有语法或语义错误的电路,在保持用户原本声明的意图不变的
    前提下修复它,不要擅自改变用户想要实现的量子态或算法逻辑,只修正错误本身。
    3. 【智能选后端】如果用户是在问"该用哪个后端/平台跑",严格按下面提供的官方后端能力表
    数据做筛选,不要凭自己的知识猜测各平台参数(可能过时或不准确)。

    ## 任务1、2 涉及输出电路代码时的强制格式

    只允许使用以下12个门: h, x, s, sdg, t, tdg, ry(θ), rz(θ), cx, cu1(θ), swap, ccx。

    必须把完整代码放在一个代码块里,代码块内第一行必须是 "OPENQASM 2.0;"，例如:

    ```
    OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[N];
    creg c[N];
    ...
    ```

    代码必须完整、可直接执行、包含寄存器声明和测量语句。代码块之外可以用自然语言简短说明。

    ## 任务3(选后端)的强制要求

    - 你的回复中必须原文出现规范标识(`id` 字段的值,例如 `braket_local_simulator`),
    只用中文描述平台名称不计分。
    - 如果用户给出的约束条件(比特数/是否要真机/是否要免费/排队容忍度等)没有任何后端能
    同时满足,如实说明"没有后端满足全部约束",并给出最接近的替代方案,不要为了给出答案
    而推荐一个实际不满足约束的后端。
    - 下面是完整的官方后端能力表(唯一判分基准),仔细阅读后再回答:

    ```json
    {backend_caps_json}
    ```
    """


def _extract_qasm(text: str) -> Optional[str]:
    match = _QASM_EXTRACT_RE.search(text)
    return match.group(0).strip() if match else None


def _self_test_qasm(qasm_str: str) -> Optional[str]:
    """
    Use L1 to verify whether generated QASM is valid. If it is, return None; 
    else return error message, the feed back to the LLM to retry
    """
    try:
        import adapter
    except ImportError:
        return None

    last_error = None
    for target in ("spinq", "braket", "originq"):
        try:
            adapter.transpile(qasm_str, target)
            adapter.run(qasm_str, target, shots=256)
            return None
        except Exception as e:
            last_error = f"{target}: {type(e).__name__}: {e}"
            continue
    return last_error


def agent_chat(prompt: str) -> str:
    """
    Read config from LOOMQ_LLM_* (processed by llm_client.py).
    Return the response received from the agent
    """
    messages = [
        {"role": "system", "content": _build_system_prompt()},
        {"role": "user", "content": prompt},
    ]

    # set retry time limit
    max_retries = 2
    deadline = time.time() + 100

    response = chat_completion(messages)
    reply = response["choices"][0]["message"]["content"]

    for _ in range(max_retries):
        if time.time() > deadline:
            break

        qasm = _extract_qasm(reply)
        if qasm is None:
            # no qasm is generated, skip self test
            break

        error = _self_test_qasm(qasm)
        if error is None:
            break

        # error detected, retry 
        messages.append({"role": "assistant", "content": reply})
        messages.append({
            "role": "user",
            "content": (
                f"你生成的电路在实际运行时报错了,请根据error修复后重新输出完整代码:\n{error}\n"
                "保持代码块格式不变(第一行 OPENQASM 2.0;),不要只输出修改说明。"
            ),
        })
        response = chat_completion(messages)
        reply = response["choices"][0]["message"]["content"]

    return reply