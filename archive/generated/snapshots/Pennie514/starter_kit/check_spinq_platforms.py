#!/usr/bin/env python3
"""量旋云平台实时状态检查（真机/模拟器在线情况）

用法：
    export SPINQ_CLOUD_USERNAME="你的量旋云用户名"
    export SPINQ_CLOUD_KEYFILE="$HOME/.ssh/spinq_cloud"
    python3 starter_kit/check_spinq_platforms.py

输出各平台：名称 / 比特数 / 是否真机 / 在线机器数。
选「真机且在线」的平台，把 platform_code 写进 evidence/config_spinq_cloud.json。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

username = os.environ.get("SPINQ_CLOUD_USERNAME")
keyfile = os.environ.get("SPINQ_CLOUD_KEYFILE")
if not username or not keyfile:
    raise SystemExit("请先设置 SPINQ_CLOUD_USERNAME 与 SPINQ_CLOUD_KEYFILE 环境变量")

from spinqit.backend.backend import get_spinq_cloud  # noqa: E402

backend = get_spinq_cloud(username, keyfile)
codes = backend.get_platform_list()
print(f"{'平台代码':<20}{'名称':<28}{'比特':<6}{'类型':<8}{'在线机器'}")
print("-" * 78)
for code in codes:
    p = backend.get_platform(code)
    kind = "真机" if not p.simu else "模拟器"
    status = "🟢 %d" % p.machine_count if p.machine_count > 0 else "🔴 0（离线）"
    print(f"{code:<20}{p.name:<28}{p.max_bitnum:<6}{kind:<8}{status}")
print()
print("提示：真机证据需要『真机 + 在线』的平台。")
print("把选中的 platform_code 写进 starter_kit/evidence/config_spinq_cloud.json 后，")
print("重新运行 starter_kit/real_machine.py spinq_cloud ...")
