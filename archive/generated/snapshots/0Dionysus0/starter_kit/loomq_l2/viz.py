"""ASCII helpers for beginner-friendly measurement charts."""

from __future__ import annotations

from typing import Dict, Mapping


def counts_bar_chart(counts: Mapping[str, int], width: int = 28) -> str:
    """Render measurement counts as a plain-text bar chart."""
    if not counts:
        return "(没有测量结果)"
    total = sum(int(v) for v in counts.values()) or 1
    items = sorted(counts.items(), key=lambda kv: (-int(kv[1]), kv[0]))
    # Keep the chart readable: top outcomes + a leftover bucket if needed.
    head = items[:8]
    lines = ["测量结果（出现次数越多，横条越长）：", ""]
    max_count = max(int(v) for _, v in head) or 1
    for state, count in head:
        count_i = int(count)
        bar_len = max(1, int(round(width * count_i / max_count))) if count_i else 0
        bar = "█" * bar_len
        pct = 100.0 * count_i / total
        lines.append(f"  |{state}>  {bar}  {count_i} 次  ({pct:.1f}%)")
    if len(items) > len(head):
        rest = sum(int(v) for _, v in items[len(head) :])
        lines.append(f"  …其余 {len(items) - len(head)} 种结果合计 {rest} 次")
    lines.append("")
    lines.append(_plain_reading(dict(items), total))
    return "\n".join(lines)


def _plain_reading(counts: Dict[str, int], total: int) -> str:
    """One-sentence reading for non-experts."""
    ranked = sorted(counts.items(), key=lambda kv: (-int(kv[1]), kv[0]))
    top_state, top_count = ranked[0]
    top_pct = 100.0 * int(top_count) / total
    if len(ranked) >= 2:
        second_state, second_count = ranked[1]
        second_pct = 100.0 * int(second_count) / total
        # Two peaks near 50%.
        if top_pct < 60 and second_pct > 30:
            if len(top_state) <= 1:
                return (
                    f"人话解读：结果几乎一半是 |{top_state}>、一半是 |{second_state}>——"
                    "就像一枚很公平的「量子硬币」。"
                )
            return (
                f"人话解读：结果几乎只出现 |{top_state}> 和 |{second_state}>，"
                "其他组合很少——这通常就是「纠缠」看起来的样子。"
            )
    if top_pct >= 85:
        return f"人话解读：绝大多数时候得到 |{top_state}>（约 {top_pct:.0f}%）。"
    return f"人话解读：最常见的结果是 |{top_state}>（约 {top_pct:.0f}%）。"
