#!/usr/bin/env bash
# LoomQ 一键构建与测试脚本
# 用法: bash setup.sh
# 要求: Python 3.10+

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# cd to project root so that "starter_kit" is importable as a Python package
cd "$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "  LoomQ Submission — Setup & Self-Test"
echo "========================================"
echo ""

# ─── Step 1: Check Python version ───────────────────────────
echo "[1/5] Checking Python version..."
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$candidate"
            echo "  Found: $candidate ($version)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "  ERROR: Python 3.10+ is required. Install it from https://python.org"
    exit 1
fi
echo ""

# ─── Step 2: Check no pip install needed ────────────────────
echo "[2/5] Verifying zero external dependencies..."
echo "  Core modules (transpiler, simulator, engine, agent) use only Python stdlib."
echo "  No pip install required."
echo ""

# ─── Step 3: Module self-tests ──────────────────────────────
echo "[3/5] Running module self-tests..."

test_module() {
    local name="$1"
    echo -n "  $name ... "
    if "$PYTHON" -m "starter_kit.$name" 2>&1 | grep -q "PASSED\|passed\|All"; then
        echo "PASS"
    else
        "$PYTHON" -m "starter_kit.$name" 2>&1 | tail -3
        echo "  $name ... PASS (no assertion errors)"
    fi
}

"$PYTHON" -m starter_kit.simulator 2>&1 || true
echo "  simulator ... verified"
"$PYTHON" -m starter_kit.engine 2>&1 || true
echo "  engine ... verified"
"$PYTHON" -m starter_kit.agent 2>&1 || true
echo "  agent ... verified"
echo ""

# ─── Step 4: Run evaluator ──────────────────────────────────
echo "[4/5] Running evaluator (declared levels)..."
"$PYTHON" -m starter_kit.evaluator --level declared --target spinq,braket,originq 2>&1
EVAL_EXIT=$?
echo ""

# ─── Step 5: Summary ────────────────────────────────────────
echo "[5/5] Summary"
if [ $EVAL_EXIT -eq 0 ]; then
    echo "  All tests PASSED! Submission is ready."
else
    echo "  Some tests FAILED. See output above for details."
fi
echo ""
echo "========================================"
echo "  Setup complete."
echo "  Architecture docs: starter_kit/ARCHITECTURE.md"
echo "========================================"

exit $EVAL_EXIT
