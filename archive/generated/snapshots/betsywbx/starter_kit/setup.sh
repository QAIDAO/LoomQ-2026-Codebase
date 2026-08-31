#!/usr/bin/env bash

# LoomQ 一键环境搭建脚本
# 用法: bash setup.sh
# 推荐在一个新的虚拟环境或 clean container 中运行
set -e

echo "======================================"
echo "  LoomQ 环境搭建"
echo "======================================"

# ---------------------------------------------------------------------------
# 1. 检查 Python 版本 (SpinQit/pyqpanda 系列SDK目前只支持 3.8-3.11)
# ---------------------------------------------------------------------------
PYTHON_BIN="${PYTHON_BIN:-python3}"
PY_VERSION=$($PYTHON_BIN -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "检测到 Python 版本: $PY_VERSION"

case "$PY_VERSION" in
  3.8|3.9|3.10|3.11) ;;
  *)
    echo "⚠️  警告: 依赖的 SpinQit/pyqpanda SDK 目前只对 Python 3.8-3.11 发布了预编译包。"
    echo "    你当前是 $PY_VERSION,继续安装大概率会在 pip install 阶段失败。"
    echo "    建议用 pyenv 或系统包管理器切换到 3.10 后重跑本脚本。"
    ;;
esac

# ---------------------------------------------------------------------------
# 2. 创建虚拟环境
# ---------------------------------------------------------------------------
if [ ! -d ".venv" ]; then
  echo "创建虚拟环境 .venv ..."
  $PYTHON_BIN -m venv .venv
else
  echo "已存在 .venv,跳过创建"
fi

source .venv/bin/activate

# ---------------------------------------------------------------------------
# 3. 装依赖 (先装wheel,避免部分包退化成本地编译走legacy setup.py路径)
# ---------------------------------------------------------------------------
pip install --upgrade pip wheel --quiet
echo "安装 requirements.txt 中的依赖(可能需要几分钟)..."
pip install -r requirements.txt

# ---------------------------------------------------------------------------
# 4. 环境自检 (不代替pip报错,但提前给出可读的诊断)
# ---------------------------------------------------------------------------
echo ""
echo "======================================"
echo "  环境自检"
echo "======================================"

$PYTHON_BIN - << 'PYEOF'
import importlib
import sys

checks = [
    ("amazon-braket-sdk", "braket.devices"),
    ("spinqit", "spinqit"),
    ("pyqpanda", "pyqpanda"),
    ("pyqpanda3", "pyqpanda3"),
    ("flask", "flask"),
]

all_ok = True
for pkg_name, import_name in checks:
    try:
        importlib.import_module(import_name)
        print(f"  ✓ {pkg_name} 可正常 import")
    except Exception as e:
        all_ok = False
        print(f"  ✗ {pkg_name} import失败: {type(e).__name__}: {e}")

if not all_ok:
    print()
    print("部分依赖 import 失败,常见原因(按平台):")
    print("  - macOS: 缺少 Xcode 命令行工具 -> 运行 `xcode-select --install`")
    print("  - macOS: SSL证书问题 -> `export SSL_CERT_FILE=$(python3 -c \"import certifi; print(certifi.where())\")`")
    print("  详细排查步骤见 README.md 的「常见问题」章节")
    sys.exit(1)
else:
    print()
    print("所有依赖正常。")
PYEOF

# ---------------------------------------------------------------------------
# 5. 检查 L2 所需的环境变量(不强制,只提示)
# ---------------------------------------------------------------------------
echo ""
echo "======================================"
echo "  L2 (Agent) 环境变量检查"
echo "======================================"
MISSING=""
for var in LOOMQ_LLM_BASE_URL LOOMQ_LLM_API_KEY LOOMQ_LLM_MODEL; do
  if [ -z "${!var}" ]; then
    MISSING="$MISSING $var"
  fi
done

if [ -n "$MISSING" ]; then
  echo "⚠️  以下环境变量未设置(不影响L1,但L2/网页入口需要):$MISSING"
  echo "    设置方式见 README.md"
else
  echo "✓ L2 所需的三个环境变量均已设置"
fi

echo ""
echo "======================================"
echo "  搭建完成"
echo "======================================"
echo "运行 L1 自测:   python3 evaluator.py --level l1 --target spinq,braket,originq"
echo "运行 L2 自测:   python3 evaluator.py --level l2"
echo "运行 L3 自测:   python3 evaluator.py --level l3"
echo "启动网页入口:   python3 app.py"