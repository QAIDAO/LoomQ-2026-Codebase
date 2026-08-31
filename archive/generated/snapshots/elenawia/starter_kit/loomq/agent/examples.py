"""Built-in beginner experiments for LoomQ Lab."""

from __future__ import annotations


def bell_qasm() -> str:
    return "\n".join(
        [
            "OPENQASM 2.0;",
            'include "qelib1.inc";',
            "qreg q[2];",
            "creg c[2];",
            "h q[0];",
            "cx q[0], q[1];",
            "measure q -> c;",
        ]
    )


def random_qasm() -> str:
    return "\n".join(
        [
            "OPENQASM 2.0;",
            'include "qelib1.inc";',
            "qreg q[1];",
            "creg c[1];",
            "h q[0];",
            "measure q -> c;",
        ]
    )


def ghz_qasm(qubits: int = 3) -> str:
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{qubits}];",
        f"creg c[{qubits}];",
        "h q[0];",
    ]
    for index in range(1, qubits):
        lines.append(f"cx q[{index - 1}], q[{index}];")
    lines.append("measure q -> c;")
    return "\n".join(lines)


def classify_prompt(prompt: str) -> tuple[str, str, str]:
    text = prompt.lower()
    if "随机" in prompt or "掷" in prompt or "硬币" in prompt or "random" in text:
        return ("random", "电脑能不能像掷硬币一样随机给出 0 或 1？", random_qasm())
    if "ghz" in text or "全局关联" in prompt or "最大纠缠" in prompt or "三枚" in prompt or "3 比特" in prompt or "3个" in prompt:
        return ("ghz", "三个量子结果能不能一起保持某种关系？", ghz_qasm(3))
    if "联系" in prompt or "关联" in prompt or "两" in prompt or "纠缠" in prompt or "bell" in text or "贝尔" in prompt:
        return ("bell", "两个量子结果能不能产生特别的联系？", bell_qasm())
    return ("random", "电脑能不能像掷硬币一样随机给出 0 或 1？", random_qasm())
