"""Command-line entry point for formal and local LoomQ L2 interaction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping, Sequence, TextIO

try:
    from .l2_errors import L2ApiError, L2ConfigurationError, L2TransportError, L2ValidationError
    from .l2_probe import probe_cases, probe_models
    from .l2_profiles import PROFILES, local_settings, provider_names, temporary_environment
    from .loomq_l2 import agent_chat
except ImportError:
    from l2_errors import L2ApiError, L2ConfigurationError, L2TransportError, L2ValidationError
    from l2_probe import probe_cases, probe_models
    from l2_profiles import PROFILES, local_settings, provider_names, temporary_environment
    from loomq_l2 import agent_chat


def _models_from_file(path_source: str) -> list[str]:
    try:
        lines = Path(path_source).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise L2ConfigurationError("cannot read --models-file: " + path_source) from exc
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def _configure_default_console_encoding(stream: TextIO) -> None:
    """Keep Chinese CLI guidance readable when Python inherits a legacy code page."""
    if stream is sys.stdout or stream is sys.stderr:
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass


def _has_nonempty_piped_input(stdin: TextIO) -> bool:
    """Read piped input for validation without blocking an interactive terminal."""
    if stdin is sys.stdin and getattr(stdin, "isatty", lambda: False)():
        return False
    return bool(stdin.read().strip())


def _print_beginner_guide(stdout: TextIO) -> None:
    """Print a self-contained first experiment route without calling a model."""
    print(
        "LoomQ 五分钟第一站（不需要 API Key）\n"
        "\n"
        "把量子线路先想成一张食谱：QASM 是把食谱写给程序看的文字；"
        "后端是实际帮你做菜的厨房。\n"
        "\n"
        "1. 现在就在终端运行：python -m starter_kit.l2_cli --guide\n"
        "   这一步只显示路线，不会调用大模型、模拟器或真机。\n"
        "2. 读 starter_kit/circuits/bell.qasm：它让两个量子位做一次最小的 “一起翻硬币” 实验。\n"
        "3. 用 README 的 Docker 命令运行 L1 public evaluator。模拟器像练习厨房："
        "先在电脑里试做，结果快、可重复，也不占用真实设备。\n"
        "4. 检查试做后的常见结果，是否符合这份食谱的预期：看 counts。"
        "shots（读作“采样次数”）就是把同一食谱重复做多少次。可运行：\n"
        "   python -m starter_kit.l2_cli --explain-counts '{\"00\":4102,\"11\":4090}'\n"
        "5. 决定下一次在哪里做实验：先用模拟器，因为快、免费且可重复；"
        "只有需要真实设备验证时，再确认权限、费用和排队后选择真机 QPU。"
        "真机像真实厨房：会受噪声和排队影响。\n"
        "\n"
        "下一步：先用模拟器复现 Bell 线路；需要自然语言帮助时，再由评测环境或你自己的环境"
        "提供 LOOMQ_LLM_* 配置后运行 l2_cli 的普通提问模式。",
        file=stdout,
    )


def _parse_counts(source: str) -> dict[str, int]:
    try:
        decoded = json.loads(source)
    except json.JSONDecodeError as exc:
        raise ValueError("--explain-counts 需要一个 JSON 位串计数字典。") from exc
    if not isinstance(decoded, Mapping) or not decoded:
        raise ValueError("--explain-counts 需要一个非空 JSON 位串计数字典。")

    counts: dict[str, int] = {}
    for key, value in decoded.items():
        if not isinstance(key, str) or not key or set(key) - {"0", "1"}:
            raise ValueError("计数键必须是非空的 0/1 位串，例如 \"00\"。")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("每个计数必须是零或正整数。")
        counts[key] = value
    if not any(counts.values()):
        raise ValueError("至少需要一个大于零的计数。")
    return counts


def _ascii_bar(count: int, maximum: int, width: int = 24) -> str:
    filled = max(1, round(width * count / maximum)) if count else 0
    return "#" * filled


def _print_counts_explanation(source: str, stdout: TextIO) -> None:
    """Render local count data without inferring a hardware run from it."""
    counts = _parse_counts(source)
    total = sum(counts.values())
    maximum = max(counts.values())
    print(f"测量分布（共 {total} shots；每个 shots 是同一线路的一次读数）：", file=stdout)
    for bits, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        percent = 100 * count / total
        print(f"{bits:>8} | {_ascii_bar(count, maximum):<24} | {count:>6} ({percent:5.1f}%)", file=stdout)

    if set(counts).issubset({"00", "11"}) and counts.get("00", 0) and counts.get("11", 0):
        print(
            "解读：两种读数都是“两个位相同”，所以这批样本呈现关联；"
            "这与常见 Bell 线路的目标分布相符。仅凭这些计数不能证明真机纠缠质量，"
            "也不能说明结果来自真实硬件。",
            file=stdout,
        )
        print("下一步：在模拟器重复同一 Bell QASM，并提高 shots 比较比例是否稳定。", file=stdout)
    else:
        print(
            "解读：柱子表示这批重复读数的频率，不单独证明线路正确、纠缠或真机运行。",
            file=stdout,
        )
        print("下一步：对照线路预期分布，在模拟器用更多 shots 再比较。", file=stdout)


def _safe_error_message(exc: Exception) -> str:
    if isinstance(exc, L2ConfigurationError):
        variables = ", ".join(exc.variable_names) or "LOOMQ L2 configuration"
        return f"L2 配置错误：检查 {variables}。{exc}"
    if isinstance(exc, L2TransportError):
        return (
            f"L2 网络错误：无法在 {exc.timeout_seconds:g} 秒内连接 {exc.host}。"
            "请检查 base URL、网络或代理后重试。"
        )
    if isinstance(exc, L2ApiError):
        suffix = f"（request id: {exc.request_id}）" if exc.request_id else ""
        if exc.status in {401, 403}:
            return f"L2 鉴权错误：{exc.host} 返回 HTTP {exc.status}{suffix}。请检查该提供商的 API Key。"
        if exc.status == 429:
            return f"L2 限流：{exc.host} 返回 HTTP 429{suffix}。请稍后重试。"
        return f"L2 API 错误：{exc.host} 返回 HTTP {exc.status}{suffix}。请检查端点后重试。"
    if isinstance(exc, L2ValidationError):
        return f"L2 结果校验失败：{exc.reason}。可根据该原因修正提示词后重试。"
    if "LOOMQ_LLM_" in str(exc):
        return "L2 配置错误：检查 LOOMQ_LLM_BASE_URL、LOOMQ_LLM_API_KEY、LOOMQ_LLM_MODEL。"
    return "L2 请求失败。请检查模型端点后重试。"


def _profile_agent(prompt: str, provider: str, model: str | None, base_url: str | None) -> str:
    settings = local_settings(provider, model=model, base_url=base_url)
    with temporary_environment(settings):
        return agent_chat(prompt)


def _probe_model_names(args: argparse.Namespace) -> list[str]:
    models = list(args.model or [])
    if args.models_file:
        models.extend(_models_from_file(args.models_file))
    if not models:
        default_model = PROFILES[args.provider].default_model
        if default_model:
            models.append(default_model)
    if not models:
        raise L2ConfigurationError("supply at least one --model for this provider", variable_names=("--model",))
    if not args.all and len(models) > 1:
        raise L2ConfigurationError("multiple models require --all", variable_names=("--all",))
    return models if args.all else models[:1]


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run one formal L2 request or an explicitly local provider probe."""
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    _configure_default_console_encoding(stdout)
    _configure_default_console_encoding(stderr)
    parser = argparse.ArgumentParser(description="Ask or locally probe the LoomQ quantum assistant.")
    parser.add_argument("prompt", nargs="*", help="question to ask; reads one line from stdin when omitted")
    parser.add_argument("--provider", choices=provider_names(), help="explicit local provider profile")
    parser.add_argument("--base-url", help="override the selected local provider endpoint")
    parser.add_argument("--model", action="append", help="local model id; repeat with --all for probing")
    parser.add_argument("--models-file", help="UTF-8 file containing one local model id per line")
    parser.add_argument("--probe", action="store_true", help="run the three local semantic probe tasks")
    parser.add_argument("--all", action="store_true", help="probe every model explicitly supplied by --model/file")
    parser.add_argument("--execute", action="store_true", help="permit local probe network calls")
    parser.add_argument("--json", action="store_true", help="emit machine-readable local output")
    local_only_group = parser.add_mutually_exclusive_group()
    local_only_group.add_argument("--guide", action="store_true", help="print a no-key five-minute LoomQ beginner route")
    local_only_group.add_argument("--explain-counts", metavar="JSON", help="locally explain a JSON count dictionary")
    args = parser.parse_args(argv)

    if (args.guide or args.explain_counts is not None) and args.prompt:
        parser.error("--guide and --explain-counts cannot be combined with a prompt")
    if (args.guide or args.explain_counts is not None) and _has_nonempty_piped_input(stdin):
        parser.error("--guide and --explain-counts cannot be combined with piped input")
    if args.guide:
        _print_beginner_guide(stdout)
        return 0
    if args.explain_counts is not None:
        try:
            _print_counts_explanation(args.explain_counts, stdout)
        except ValueError as exc:
            print(f"结果输入错误：{exc}", file=stderr)
            return 2
        return 0

    if (args.base_url or args.model or args.models_file or args.all) and not args.provider:
        print("L2 配置错误：--base-url、--model、--models-file、--all 需要显式 --provider。", file=stderr)
        return 2
    if args.probe and not args.provider:
        print("L2 配置错误：--probe 需要显式 --provider。", file=stderr)
        return 2

    try:
        if args.probe:
            models = _probe_model_names(args)
            if not args.execute:
                preview = {
                    "mode": "dry-run",
                    "models": models,
                    "calls_per_model": len(probe_cases()),
                    "total_calls": len(models) * len(probe_cases()),
                    "hint": "pass --execute to allow model calls",
                }
                if args.json:
                    print(json.dumps(preview, ensure_ascii=False), file=stdout)
                else:
                    print(
                        f"Dry run: {preview['total_calls']} 次模型调用（每模型 {preview['calls_per_model']} 次）。"
                        "确认成本后加 --execute。",
                        file=stdout,
                    )
                return 0

            report = probe_models(
                models,
                lambda model, prompt: _profile_agent(prompt, args.provider, model, args.base_url),
            )
            if args.json:
                print(json.dumps(report.as_dict(), ensure_ascii=False), file=stdout)
            else:
                for model_result in report.models:
                    print(
                        f"{model_result.model}: {model_result.passed}/{len(model_result.tasks)} passed",
                        file=stdout,
                    )
                    for task in model_result.tasks:
                        if task.error:
                            print(f"  - {task.case}: {task.error}", file=stdout)
            return 0

        prompt = " ".join(args.prompt).strip()
        if not prompt:
            prompt = stdin.readline().strip()
        if not prompt:
            print("No prompt supplied. Pass a prompt or pipe one line to stdin.", file=stderr)
            return 2
        if args.provider:
            if args.models_file or args.all or len(args.model or []) > 1:
                raise L2ConfigurationError("direct chat accepts at most one --model", variable_names=("--model",))
            reply = _profile_agent(prompt, args.provider, (args.model or [None])[0], args.base_url)
        else:
            reply = agent_chat(prompt)
    except Exception as exc:
        print(_safe_error_message(exc), file=stderr)
        return 2
    if args.json:
        print(json.dumps({"reply": reply}, ensure_ascii=False), file=stdout)
    else:
        print(reply, file=stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
