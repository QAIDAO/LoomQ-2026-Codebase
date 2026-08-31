#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

This file intentionally contains no scoring implementation. Teams may implement
the functions directly or delegate to another language/runtime with subprocess.
"""

from typing import Any, Dict, List, Tuple

try:
    from .loomq import agent as _agent
    from .loomq import backends as _backends
    from .loomq import emitters as _emitters
    from .loomq import hybrid as _hybrid
    from .loomq import qasm_parser as _qasm_parser
except ImportError:  # 允许把 starter_kit 直接加进 sys.path 使用
    from loomq import agent as _agent
    from loomq import backends as _backends
    from loomq import emitters as _emitters
    from loomq import hybrid as _hybrid
    from loomq import qasm_parser as _qasm_parser


SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation.

    实现在 loomq/ 下，本函数只做转发。
    流水线：OpenQASM 2.0 -> 解析成中立的 Circuit -> 写成目标后端的方言。
    只有一个解析器、一份电路表示，三个后端共用——这就是"统一中间层"。
    """
    return _emitters.transpile(_qasm_parser.parse(qasm_str), target)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules.

    送进模拟器的文本就是 transpile() 返回的那份，两者不会互相掩护。
    结果的位序按赛题规范归一化（counts 的 key 最右边是 c[0]）。
    """
    return _backends.execute(_qasm_parser.parse(qasm_str), target, shots)


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment.

    实现在 loomq/agent.py，本函数只做转发。
    分工：模型只负责把人话解析成结构化意图，答案由确定性代码给出——
    选后端靠查官方能力表，生成电路靠用自己的 L1 真跑一遍自验，不对就重写。
    配置一律从 LOOMQ_LLM_* 环境变量读取，不硬编码。
    """
    return _agent.agent_chat(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Optional L3 entry point. Return quantum operations and RISC-V assembly.

    实现在 loomq/hybrid.py，本函数只做转发，保持提交契约文件的干净。
    流水线：拆分源码 -> 分词 -> 语法分析 -> 生成 RISC-V 汇编。
    """
    return _hybrid.compile_hybrid(hybrid_qasm_str)
