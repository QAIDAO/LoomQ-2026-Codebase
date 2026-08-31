"""Beginner-friendly CLI for the LoomQ assistant."""
from .adapter import _counts, agent_chat
import argparse
import re


def _qasm_from_reply(reply: str) -> str | None:
    match = re.search(r"```qasm\s*(OPENQASM\s+2\.0;.*?)(?:```|\Z)", reply, re.I | re.S)
    return match.group(1).strip() if match else None


def _print_distribution(qasm: str, shots: int = 1024) -> None:
    """Show an approachable local preview of a generated circuit's outcomes."""
    try:
        counts = _counts(qasm, shots)
    except Exception:
        print("\n无法生成本地结果预览：请检查回复中的 QASM 后重试。")
        return
    width = 24
    print("\n本地结果预览（理想模拟，非真机结果）：")
    for state, value in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        bar = "█" * max(1, round(value / shots * width))
        print(f"  {state}  {bar:<{width}}  {value / shots:6.1%} ({value}/{shots})")


def _recovery_message(error: Exception) -> str:
    message = str(error)
    if "missing required LoomQ L2 environment variable" in message:
        return (
            "请先设置 LOOMQ_LLM_BASE_URL、LOOMQ_LLM_API_KEY 和 LOOMQ_LLM_MODEL，"
            "再重新运行。详细步骤见 starter_kit/BEGINNER_GUIDE.md。"
        )
    if "unreachable" in message or "HTTP" in message:
        return "模型服务暂时无法访问。请检查网络、接口地址和账号额度后重试。"
    return "请检查问题是否完整后重试；常见问题和恢复方法见 starter_kit/BEGINNER_GUIDE.md。"

def main() -> int:
    parser = argparse.ArgumentParser(description="LoomQ beginner quantum assistant")
    parser.add_argument("prompt", nargs="*", help="natural-language request")
    args = parser.parse_args()
    prompt = " ".join(args.prompt).strip()
    if not prompt:
        prompt = input("LoomQ> ").strip()
    if not prompt:
        print("请输入一个问题，例如：生成一个 3 比特 GHZ 态并进行全测量。")
        return 2
    try:
        reply = agent_chat(prompt)
        print(reply)
        qasm = _qasm_from_reply(reply)
        if qasm:
            _print_distribution(qasm)
    except Exception as exc:
        print(f"请求失败：{exc}")
        print("下一步：" + _recovery_message(exc))
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
