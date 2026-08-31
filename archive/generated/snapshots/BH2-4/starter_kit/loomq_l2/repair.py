"""纠错任务：确定性的用户 QASM 规范化 + 对照声明意图验证，失败则按模板重建。"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

# 常见错误门名 -> 白名单规范名（大小写/别名归一）
_GATE_ALIASES = {
    "cnot": "cx", "x": "x", "y": None, "not": "x",
    "hadamard": "h", "h": "h", "s": "s", "sdg": "sdg", "sdg": "sdg",
    "t": "t", "tdg": "tdg", "rz": "rz", "ry": "ry", "cx": "cx",
    "cu1": "cu1", "swap": "swap", "ccx": "ccx", "toffoli": "ccx",
    "bell": None,
}

_GATE_LINE = re.compile(
    r"(?i)\b([a-z][a-z0-9_]*)\s*(?:\(([^)]*)\))?\s+"
    r"([a-z_]\w*\[\d+\](?:\s*[, ]\s*[a-z_]\w*\[\d+\])*)\s*;?")


def extract_code_from_prompt(prompt: str) -> Optional[str]:
    """从 prompt 里摘出疑似量子代码（ fenced 块或裸门语句行）。"""
    fenced = re.findall(r"```[a-zA-Z]*\n(.*?)```", prompt, re.DOTALL)
    if fenced:
        return fenced[0].strip()
    lines = [line.strip() for line in prompt.splitlines()
             if _GATE_LINE.search(line) or line.lower().startswith(("openqasm", "qreg", "creg"))]
    return "\n".join(lines) if lines else None


def normalize_user_qasm(code: str, min_qubits: int = 1) -> Tuple[str, list]:
    """尽力把用户代码规范成可解析 QASM2：门名归一、补头、补寄存器、补测量。

    返回 (规范后 QASM, 修复说明列表)。无法理解的行会被丢弃并记录。
    """
    notes = []
    out_lines = []
    max_qubit = -1
    saw_qreg = saw_creg = saw_measure = False
    # 单行多语句（如 "H q[0]; CX q[0] q[1]"）先按分号断行
    lines = code.replace(";", ";\n").splitlines()
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        low = line.lower()
        if low.startswith("openqasm"):
            continue
        if low.startswith(("qreg", "creg")):
            out_lines.append(line)
            if low.startswith("qreg"):
                saw_qreg = True
            else:
                saw_creg = True
            continue
        if low.startswith("measure"):
            out_lines.append(line)
            saw_measure = True
            continue
        match = _GATE_LINE.search(line)
        if not match:
            notes.append("丢弃无法识别的行：%s" % line)
            continue
        name = match.group(1).lower()
        canonical = _GATE_ALIASES.get(name, _GATE_ALIASES.get(name.lower()))
        if canonical is None:
            notes.append("门 %r 不在支持范围，已丢弃该行" % name)
            continue
        if name != canonical and name.upper() != canonical:
            notes.append("门名 %s 已更正为 %s" % (match.group(1), canonical))
        params = match.group(2)
        args = [a.strip() for a in re.split(r"[,\s]+", match.group(3).strip()) if a.strip()]
        for arg in args:
            idx = re.search(r"\[(\d+)\]$", arg)
            if idx:
                max_qubit = max(max_qubit, int(idx.group(1)))
        arg_text = ", ".join(args)
        if params is not None:
            out_lines.append("%s(%s) %s;" % (canonical, params, arg_text))
        else:
            out_lines.append("%s %s;" % (canonical, arg_text))
    n = max(max_qubit + 1, min_qubits)
    if not saw_qreg or not saw_creg:
        notes.append("补充了量子/经典寄存器声明（q[%d]/c[%d]）" % (n, n))
    if not saw_measure:
        notes.append("补充了整寄存器测量语句")
    header = ['OPENQASM 2.0;', 'include "qelib1.inc";',
              "qreg q[%d];" % n, "creg c[%d];" % n]
    body = [line for line in out_lines
            if not line.lower().startswith(("qreg", "creg"))]
    measures = ["measure q -> c;"] if not saw_measure else [
        line for line in out_lines if line.lower().startswith("measure")]
    qasm = "\n".join(header + body + measures) + "\n"
    return qasm, notes
