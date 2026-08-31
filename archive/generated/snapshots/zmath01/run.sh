#!/usr/bin/env bash
# LoomQ 一键启动：自检全部通过后，打开产品入口。
# One command: secret scan -> full self-test -> open the Web UI.
set -euo pipefail
cd "$(dirname "$0")"

echo "═══════════════════════════════════════════════"
echo " LoomQ · 量子接入平权计划 —— 一键自检 + 启动"
echo "═══════════════════════════════════════════════"

echo
echo "[1/4] 密钥/隐私扫描（工作树）"
python3 starter_kit/check_secrets.py

echo
echo "[2/4] L1 三后端 + L3 混合编译 扩展自测"
python3 starter_kit/selftest.py

echo
echo "[3/4] 量子 RISC-V 扩展端到端测试"
python3 starter_kit/test_quantum_riscv.py

echo
echo "[4/4] Web UI 端到端测试（自动拉起临时服务器）"
python3 starter_kit/test_web_api.py --spawn

echo
echo "✅ 全部自检通过。启动产品入口……"
echo "   浏览器打开： http://127.0.0.1:8003"
python3 starter_kit/loomq_web.py --port 8003
