import re


BACKEND_ID = re.compile(r"\b(?:spinq|originq|braket)_[a-z0-9_]+\b")
FENCE = re.compile(r"```+")

VERIFY_THRESHOLD = 0.99


def _intro(explanation: str, default: str = "已按你的目标生成量子电路。") -> str:
    # The evaluator scans from the literal token OPENQASM to the next code
    # fence, so neither may appear in the prose that precedes the program.
    text = explanation.strip().replace("OPENQASM", "Open QASM")
    text = FENCE.sub("", text).strip()
    return text or default


def qasm(
    explanation: str,
    program: str,
    fidelity: float | None = None,
    *,
    verified: bool = True,
    synthesized: bool = False,
) -> str:
    """Render one answer containing exactly one fenced OpenQASM 2.0 program."""
    if fidelity is None:
        status = "已通过本地语法与门集检查（本次未做语义验证）。"
    elif verified:
        status = f"已通过本地模拟验证，保真度 {fidelity:.3f}。"
    else:
        status = (
            f"本地模拟保真度 {fidelity:.3f}，未达自验阈值 {VERIFY_THRESHOLD}，"
            "以下是当前最优版本。"
        )
    if synthesized:
        status += "（模型结果未通过自验，已按确认后的目标态在本地重建。）"
    return f"{_intro(explanation)}\n{status}\n```qasm\n{program.strip()}\n```"


def backend(explanation: str, selected: dict) -> str:
    reason = BACKEND_ID.sub(
        "该后端", _intro(explanation, "它满足你声明的容量、排队和费用约束。")
    )
    return f"{selected['id']} — {selected['name']}。{reason}"


def fallback(message: str) -> str:
    return f"LoomQ Agent 暂时无法完成这次请求：{message}。请保留原始目标并重试。"
