#!/usr/bin/env bash
# LoomQ local development environment (macOS arm64, Python 3.10).
# The official evaluator runs on Linux (python:3.10-slim + manylinux wheels),
# where the spinqit rpath patch below is NOT needed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is required (https://docs.astral.sh/uv)" >&2
  exit 1
fi

uv python install 3.10
uv venv --python 3.10 "$ROOT/.venv"
uv pip install --python "$ROOT/.venv/bin/python" -r "$ROOT/starter_kit/requirements.txt"

# spinqit 0.2.4 macOS wheel embeds an ELF-style $ORIGIN LC_RPATH, which the
# macOS loader treats as a literal path -> dylib not found. Patch the rpath
# to the installed package dir. Not needed on Linux (official runtime).
SPINQ_DIR="$("$ROOT/.venv/bin/python" -c 'import os, spinqit; print(os.path.dirname(spinqit.__file__))')"
if otool -l "$SPINQ_DIR/spinq_backends.cpython-310-darwin.so" 2>/dev/null | grep -q 'path \$ORIGIN'; then
  install_name_tool -rpath '$ORIGIN' "$SPINQ_DIR" "$SPINQ_DIR/spinq_backends.cpython-310-darwin.so"
  echo "patched spinqit rpath in $SPINQ_DIR"
fi

"$ROOT/.venv/bin/python" - <<'PY'
import spinqit, pyqpanda
from braket.devices import LocalSimulator
assert LocalSimulator() is not None
print("environment OK: spinqit / pyqpanda / braket LocalSimulator")
PY

echo
echo "Optional: drive L2 with a local OpenAI-compatible model (Ollama) before"
echo "switching to DeepSeek. Example:"
echo "  export LOOMQ_LLM_BASE_URL=http://localhost:11434/v1"
echo "  export LOOMQ_LLM_API_KEY=ollama"
echo "  export LOOMQ_LLM_MODEL=gemma4        # any model in: ollama list"
echo "  $ROOT/.venv/bin/python starter_kit/evaluator.py --level l2"