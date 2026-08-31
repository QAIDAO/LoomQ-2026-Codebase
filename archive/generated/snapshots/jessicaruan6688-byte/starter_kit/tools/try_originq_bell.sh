#!/usr/bin/env bash
# One-shot OriginQ Wukong Bell evidence attempt.
# Secrets stay in starter_kit/.env (gitignored). Does not open a Final Issue.
#
# Live chip is numeric chipId=180 (WK_C180). Do NOT map to retired origin_72/72.
# Default shots=100 — on success, stop; never resubmit the same Bell to "confirm".
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi
# Prefer a venv that already has pyqpanda when available.
# ROOT is starter_kit/; sibling clone lives next to this repo root.
REPO_ROOT="$(cd "$ROOT/.." && pwd)"
PARENT="$(cd "$REPO_ROOT/.." && pwd)"
for candidate in \
  "$PARENT/LoomQ-2026-Jessica/.venv/bin/python" \
  "$REPO_ROOT/.venv/bin/python" \
  "$ROOT/.venv/bin/python"; do
  if [ ! -x "$candidate" ]; then
    continue
  fi
  # Prefer path that ships pyqpanda even if a sandboxed import probe segfaults.
  if "$candidate" -c "import pyqpanda" 2>/dev/null \
    || [ -d "$(dirname "$candidate")/../lib/python3.10/site-packages/pyqpanda" ] \
    || ls "$(dirname "$candidate")/../lib"/python*/site-packages/pyqpanda >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done

export LOOMQ_ORIGINQ_MODE="${LOOMQ_ORIGINQ_MODE:-wukong}"
# Prefer bare 180; WK_C180 / wukong aliases also resolve to 180 in backends.py.
export LOOMQ_ORIGINQ_CHIP="${LOOMQ_ORIGINQ_CHIP:-180}"
export LOOMQ_ORIGINQ_TIMEOUT_SEC="${LOOMQ_ORIGINQ_TIMEOUT_SEC:-120}"
export LOOMQ_ORIGINQ_POLL_SEC="${LOOMQ_ORIGINQ_POLL_SEC:-2}"
export PYTHONPATH="$ROOT"

SHOTS="${1:-100}"
echo "OriginQ Bell attempt: mode=$LOOMQ_ORIGINQ_MODE chip=$LOOMQ_ORIGINQ_CHIP timeout=${LOOMQ_ORIGINQ_TIMEOUT_SEC}s shots=$SHOTS"
echo "python: $PY"
echo "If you already have a job_id, do NOT rerun — open console.originqc.com.cn and archive that job."
exec "$PY" "$ROOT/tools/run_bell_evidence.py" --platform originq --shots "$SHOTS"
