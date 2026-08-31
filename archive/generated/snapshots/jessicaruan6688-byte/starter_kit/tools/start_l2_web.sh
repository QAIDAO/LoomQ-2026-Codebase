#!/usr/bin/env bash
# One-command first-experiment demo (keeps running until Ctrl+C).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "找不到 python3。请先安装 Python 3.10+。" >&2
  exit 1
fi

PORT="${LOOMQ_WEB_PORT:-8765}"
export PYTHONPATH="$ROOT"
URL="http://127.0.0.1:${PORT}/"

already() {
  "$PY" - <<PY
import json, urllib.request
try:
    with urllib.request.urlopen("${URL}api/health", timeout=1) as resp:
        data = json.loads(resp.read().decode())
    raise SystemExit(0 if data.get("ok") and data.get("hardware_ready") else 1)
except Exception:
    raise SystemExit(1)
PY
}

if already; then
  echo "${PORT} 上已经有 LoomQ 演示在跑：${URL}"
  echo "直接打开即可。若要加载刚改过的页面：先在占用该端口的终端按 Ctrl+C，再重新 ./start_demo.sh"
  if [ "${LOOMQ_NO_BROWSER:-}" != "1" ]; then
    if command -v open >/dev/null 2>&1; then
      open "$URL"
    elif command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$URL"
    fi
  fi
  exit 0
fi

echo "LoomQ 第一次实验：${URL}"
echo "真机 Bell / GHZ 是归档回放，无需 API Key。"
echo "目录：$ROOT"
echo "按 Ctrl+C 停止。"

OPEN_FLAG=()
if [ "${LOOMQ_NO_BROWSER:-}" != "1" ]; then
  OPEN_FLAG=(--open)
fi

exec "$PY" web/server.py --host 127.0.0.1 --port "$PORT" "${OPEN_FLAG[@]}"
