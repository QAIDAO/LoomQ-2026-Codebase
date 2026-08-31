#!/usr/bin/env python3
"""Finalize two distinct genuine hardware records into evidence/README.md."""

from __future__ import annotations

import argparse
from pathlib import Path

from starter_kit.hardware.common import STARTER_ROOT
from starter_kit.hardware.validate_evidence import validate_metadata


README = STARTER_ROOT / "evidence" / "README.md"


def _block(item: dict[str, object]) -> str:
    shots = item["shots"] if item["shots"] is not None else item.get("shots_note", "N/A")
    screenshot = item.get("task_screenshot_path") or "未提供"
    return f"""平台名称：{item['platform']}
设备：{item['device']}
平台 job ID：{item['job_id']}
提交时间：{item['submitted_at']}
完成时间：{item['completed_at']}
shots：{shots}
实际执行的 QASM：`{item['qasm_path']}`
平台返回的原始结果：`{item['raw_result_path']}`
规范化结果：`{item['normalized_result_path']}`
元数据：`{item['metadata_path']}`
任务页截图：`{screenshot}`
真实性边界：该记录来自平台任务页与原始导出文件中的可追溯硬件任务 ID，不是 simulator；组织方仍可登录平台复核。
"""


def render(readme: str, items: list[dict[str, object]]) -> str:
    providers = {str(item["provider"]) for item in items}
    if len(items) != 2 or len(providers) != 2:
        raise ValueError("exactly two distinct eligible hardware providers are required")
    start = readme.index("## L1 真机")
    end = readme.index("## L2 交互体验")
    section = "## L1 真机\n\n" + "\n".join(_block(item) for item in items) + "\n"
    updated = readme[:start] + section + readme[end:]
    return updated.replace("- [ ] L1 真机", "- [x] L1 真机", 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize two-platform LoomQ hardware evidence")
    parser.add_argument("metadata", nargs=2)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    items = [validate_metadata(Path(path).resolve()) for path in args.metadata]
    updated = render(README.read_text(encoding="utf-8"), items)
    if args.dry_run:
        print(updated)
    else:
        README.write_text(updated, encoding="utf-8")
        print(f"updated={README}")
    print("LOCAL VALIDATION DOES NOT PROVE REMOTE JOB TRACEABILITY; ORGANIZERS MAY LOG IN AND VERIFY THE JOB ID.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
