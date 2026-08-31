#!/usr/bin/env bash
# Fork 根目录一键进入第一次实验。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec "$ROOT/starter_kit/tools/start_l2_web.sh"
