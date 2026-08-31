#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
VENV_PATH=${LOOMQ_VENV_PATH:-"$REPOSITORY_ROOT/.venv"}
PYTHON_PATH="$VENV_PATH/bin/python"

export PYTHONUTF8=1

if [ ! -x "$PYTHON_PATH" ]; then
    python3.10 -m venv "$VENV_PATH"
fi

"$PYTHON_PATH" -c 'import sys; assert sys.version_info[:2] == (3, 10), sys.version'
"$PYTHON_PATH" -m pip install --upgrade 'pip==26.2'
"$PYTHON_PATH" -m pip install --requirement "$REPOSITORY_ROOT/starter_kit/requirements.txt"
"$PYTHON_PATH" -m pip check

printf 'LoomQ environment ready: %s\n' "$PYTHON_PATH"
printf 'Public evaluator: %s starter_kit/evaluator.py --level l1 --target spinq,originq,braket\n' "$PYTHON_PATH"
printf 'LoomQ Lab: %s -m starter_kit.loomq.web.server\n' "$PYTHON_PATH"
