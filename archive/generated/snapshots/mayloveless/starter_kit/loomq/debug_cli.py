"""Extremely thin interactive consumer for LoomQ agent and circuit traces."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Callable, Sequence

from .circuit_trace import trace_circuit
from .debug_trace import TraceEvent, TraceRecorder
from .l2_agent import _run_agent
from .parser import parse_qasm
from .qasm_tools import extract_qasm


PROBABILITY_BAR_WIDTH = 20
_ANSI_RESET = "\033[0m"
_ANSI_BOLD = "\033[1m"
_ANSI_DIM = "\033[2m"
_ANSI_COLORS = {
    "agent": "\033[35m",
    "circuit": "\033[36m",
    "llm": "\033[34m",
    "local": "\033[90m",
    "running": "\033[34m",
    "ok": "\033[32m",
    "warning": "\033[33m",
    "error": "\033[31m",
    "probability": "\033[36m",
}
_LAYER_LABELS = {"agent": "Agent", "circuit": "电路"}
_EXECUTOR_LABELS = {"llm": "模型", "local": "本地"}
_STATUS_LABELS = {
    "running": "进行中",
    "ok": "成功",
    "warning": "警告",
    "error": "失败",
}
_STAGE_LABELS = {
    "intent": "识别任务",
    "qasm_candidate": "生成候选 QASM",
    "target_spec": "提取目标态",
    "parser_validation": "语法校验",
    "semantic_verification": "语义验证",
    "repair_started": "开始修复",
    "repair_candidate": "修复结果",
    "backend_constraints": "提取后端约束",
    "backend_selected": "本地筛选后端",
    "agent_result": "最终结果",
    "gate_step": "量子门步骤",
    "measurement": "测量",
    "statevector_skipped": "跳过状态可视化",
    "trace_stopped_after_measurement": "中途测量后停止追踪",
}


def build_debug_trace(prompt: str) -> tuple[str, tuple[TraceEvent, ...]]:
    """Run the production agent once, then trace its validated final circuit."""
    recorder = TraceRecorder()
    reply = _run_agent(prompt, trace_sink=recorder)
    qasm = extract_qasm(reply)
    if qasm is not None:
        trace_circuit(parse_qasm(qasm), recorder)
    return reply, recorder.events


def _probability_bar(probability: float) -> str:
    probability = min(1.0, max(0.0, probability))
    filled = int(probability * PROBABILITY_BAR_WIDTH + 0.5)
    if probability > 0.0 and filled == 0:
        filled = 1
    if probability < 1.0 and filled == PROBABILITY_BAR_WIDTH:
        filled -= 1
    return "█" * filled + "░" * (PROBABILITY_BAR_WIDTH - filled)


def _colorize(text: str, color: str, *, enabled: bool) -> str:
    """仅在交互终端启用颜色，避免污染管道和测试输出。"""
    if not enabled:
        return text
    return color + text + _ANSI_RESET


def _probability_line(
    item: dict[str, object], *, amplitude: bool, color: bool = False
) -> str:
    raw_probability = float(item["probability"])
    bar = _probability_bar(raw_probability)
    if color:
        filled = bar.rstrip("░")
        empty = bar[len(filled) :]
        bar = (
            _colorize(filled, _ANSI_COLORS["probability"], enabled=bool(filled))
            + _colorize(empty, _ANSI_DIM, enabled=bool(empty))
        )
    line = "|%s>  %s  %5.1f%%" % (
        item["basis"],
        bar,
        100.0 * raw_probability,
    )
    if amplitude:
        line += "  (%+.6f%+.6fi)" % (
            float(item.get("real", 0.0)),
            float(item.get("imag", 0.0)),
        )
    return line


def _state_lines(
    entries: Sequence[dict[str, object]], *, color: bool = False
) -> list[str]:
    lines = []
    for item in entries:
        lines.append(_probability_line(item, amplitude=True, color=color))
    return lines or ["没有超过显示阈值的振幅"]


def render_event(event: TraceEvent, *, color: bool = False) -> str:
    """Render one event without making terminal text part of the protocol."""
    layer = _LAYER_LABELS.get(event.layer, event.layer)
    executor = _EXECUTOR_LABELS.get(event.executor, event.executor)
    stage = _STAGE_LABELS.get(event.stage, event.stage)
    status = _STATUS_LABELS.get(event.status, event.status)
    header = "[%d] %s · %s · %s · %s" % (
        event.seq,
        _colorize(layer, _ANSI_COLORS.get(event.layer, ""), enabled=color),
        _colorize(executor, _ANSI_COLORS.get(event.executor, ""), enabled=color),
        _colorize(stage, _ANSI_BOLD, enabled=color),
        _colorize(status, _ANSI_COLORS.get(event.status, ""), enabled=color),
    )
    lines = [header, "    " + event.summary]
    if event.stage == "gate_step":
        lines.extend(
            [
                "    %s %s"
                % (str(event.data["gate"]).upper(), ", ".join(event.data["qubits"])),
                "",
                "    执行前",
                *(
                    "    " + line
                    for line in _state_lines(event.data["state_before"], color=color)
                ),
                "",
                "    执行后",
                *(
                    "    " + line
                    for line in _state_lines(event.data["state_after"], color=color)
                ),
                "",
                "    " + str(event.data["gate_description"]),
            ]
        )
    elif event.stage == "measurement":
        mappings = " · ".join(
            "%s → %s" % (item["qubit"], item["classical_bit"])
            for item in event.data["mappings"]
        )
        lines.extend(
            [
                "    映射：" + mappings,
                "    测量前概率",
                *(
                    "    " + _probability_line(item, amplitude=False, color=color)
                    for item in event.data["probabilities_before"]
                ),
                "    " + str(event.data["gate_description"]),
            ]
        )
    elif event.data:
        lines.append("    数据：" + json.dumps(event.data, ensure_ascii=False))
    return "\n".join(lines)


def consume_events(
    events: Sequence[TraceEvent],
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    color: bool = False,
) -> bool:
    """Step through events; return False only when the user quits early."""
    continuing = False
    for index, event in enumerate(events):
        output_fn(render_event(event, color=color))
        if continuing or index == len(events) - 1:
            continue
        while True:
            command = input_fn(
                "[Enter/n] 下一步 · [c] 连续执行 · [q] 退出："
            ).strip().lower()
            if command in ("", "n"):
                break
            if command == "c":
                continuing = True
                break
            if command == "q":
                return False
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LoomQ 量子调试 Trace CLI")
    parser.add_argument("prompt", help="自然语言 L2 请求")
    parser.add_argument("--no-color", action="store_true", help="关闭终端颜色")
    args = parser.parse_args(argv)
    # 遵循 NO_COLOR 约定，非交互输出默认也不写入 ANSI 控制字符。
    use_color = (
        not args.no_color
        and "NO_COLOR" not in os.environ
        and hasattr(sys.stdout, "isatty")
        and sys.stdout.isatty()
    )
    try:
        _, events = build_debug_trace(args.prompt)
    except Exception as exc:
        print(
            _colorize(
                "调试失败：%s" % type(exc).__name__,
                _ANSI_COLORS["error"],
                enabled=use_color,
            )
        )
        return 1
    consume_events(events, color=use_color)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "build_debug_trace",
    "consume_events",
    "main",
    "render_event",
]
