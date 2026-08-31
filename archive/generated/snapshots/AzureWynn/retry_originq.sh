#!/usr/bin/env bash
# 本源悟空真机自动重试：机器维护中时每 N 秒重试一次，直到提交成功或超时。
# 用法：bash retry_originq.sh [bell|ghz3] [间隔秒] [最大等待秒]
set -u
set -a; source "$(dirname "$0")/.env"; set +a

CIRCUIT="${1:-bell}"
INTERVAL="${2:-300}"
MAX_WAIT="${3:-28800}"   # 默认最多等 8 小时

ROOT="$(cd "$(dirname "$0")" && pwd)"
elapsed=0
attempt=0
while [ "$elapsed" -lt "$MAX_WAIT" ]; do
  attempt=$((attempt + 1))
  echo "[$(date '+%H:%M:%S')] attempt #$attempt: submitting $CIRCUIT to originq ..."
  if "$ROOT/.venv/bin/python" "$ROOT/starter_kit/real_machine.py" --provider originq --circuit "$CIRCUIT"; then
    echo "SUCCESS: $CIRCUIT submitted to 本源悟空。证据已写入 evidence/files/"
    exit 0
  fi
  echo "  not available yet, retrying in ${INTERVAL}s ..."
  sleep "$INTERVAL"
  elapsed=$((elapsed + INTERVAL))
done
echo "TIMEOUT after ${MAX_WAIT}s. 请稍后手动重试。"
exit 1