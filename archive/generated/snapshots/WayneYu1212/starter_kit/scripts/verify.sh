#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
PYTHON_PATH=${LOOMQ_PYTHON_PATH:-"$REPOSITORY_ROOT/.venv/bin/python"}
REPORT_PATH="$REPOSITORY_ROOT/starter_kit/evidence/files/l1-public-report.json"

if [ ! -x "$PYTHON_PATH" ]; then
    printf '%s\n' 'Missing .venv. Run starter_kit/scripts/setup.sh first.' >&2
    exit 1
fi

export PYTHONUTF8=1
cd "$REPOSITORY_ROOT"

"$PYTHON_PATH" -m pip check
"$PYTHON_PATH" -m unittest discover -s tests -v
"$PYTHON_PATH" -m unittest discover -s starter_kit/tests -v
"$PYTHON_PATH" starter_kit/evaluator.py --level l1 --target spinq,originq,braket --json-out "$REPORT_PATH"
"$PYTHON_PATH" starter_kit/tests/public_l2_fake.py
"$PYTHON_PATH" starter_kit/evaluator.py --level l3
"$PYTHON_PATH" -m unittest starter_kit.tests.test_hybrid_compiler starter_kit.tests.test_quantum_riscv_extension -v
"$PYTHON_PATH" -m unittest starter_kit.tests.test_hardware_tools -v
git diff --check

bytes=$("$PYTHON_PATH" -c 'import pathlib, subprocess; paths = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "starter_kit"], text=True).splitlines(); print(sum(pathlib.Path(path).stat().st_size for path in paths if pathlib.Path(path).is_file()))')
if [ "$bytes" -ge 104857600 ]; then
    printf 'starter_kit archive projection exceeds 100 MiB\n' >&2
    exit 1
fi

printf 'VERIFICATION PASS: starter_kit projection %s bytes\n' "$bytes"
