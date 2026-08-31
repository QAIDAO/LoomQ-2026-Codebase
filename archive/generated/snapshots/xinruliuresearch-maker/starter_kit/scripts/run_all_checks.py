#!/usr/bin/env python3
"""Run LoomQ's reproducible public, regression, and integration checks."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class Check:
    name: str
    command: Sequence[str]
    working_directory: Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="skip duplicate top-level and 100-seed stress checks",
    )
    parser.add_argument(
        "--report-dir",
        default="evidence/files",
        help="report directory relative to starter_kit (default: evidence/files)",
    )
    return parser.parse_args()


def _python_files() -> Iterable[Path]:
    excluded = {"__pycache__", ".git", ".venv", "node_modules"}
    for path in sorted(ROOT.rglob("*.py")):
        if not any(part in excluded for part in path.parts):
            yield path


def _syntax_check() -> None:
    """Compile every Python file into a temporary directory, leaving no cache."""

    import py_compile

    with tempfile.TemporaryDirectory(prefix="loomq-compile-") as temporary:
        target = Path(temporary)
        count = 0
        for source in _python_files():
            relative = source.relative_to(ROOT)
            compiled = target / relative.with_suffix(".pyc")
            compiled.parent.mkdir(parents=True, exist_ok=True)
            py_compile.compile(str(source), cfile=str(compiled), doraise=True)
            count += 1
    print("[PASS] syntax: %d Python files" % count)


def _checks(report_dir: Path, quick: bool) -> List[Check]:
    executable = sys.executable
    base: List[Check] = [
        Check(
            "starter unit/integration suite",
            [executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
            ROOT,
        ),
        Check(
            "public L1, all targets",
            [
                executable,
                "-B",
                "evaluator.py",
                "--level",
                "l1",
                "--target",
                "spinq,originq,braket",
                "--json-out",
                str(report_dir / "l1-public-report.json"),
            ],
            ROOT,
        ),
        Check(
            "public L3",
            [
                executable,
                "-B",
                "evaluator.py",
                "--level",
                "l3",
                "--json-out",
                str(report_dir / "l3-public-report.json"),
            ],
            ROOT,
        ),
        Check(
            "public L2 over local HTTP model transport",
            [
                executable,
                "-B",
                "scripts/run_l2_stub_evaluator.py",
                "--json-out",
                str(report_dir / "l2-public-report.json"),
            ],
            ROOT,
        ),
    ]
    if not quick:
        base.extend(
            [
                Check(
                    "100-seed target semantic differential",
                    [executable, "-B", "scripts/run_random_differential_tests.py"],
                    ROOT,
                ),
                Check(
                    "official repository contract suite",
                    [
                        executable,
                        "-B",
                        "-m",
                        "unittest",
                        "discover",
                        "-s",
                        "tests",
                        "-p",
                        "test_*.py",
                        "-v",
                    ],
                    REPOSITORY,
                ),
            ]
        )
    return base


def _run(check: Check, environment: dict[str, str]) -> bool:
    started = time.monotonic()
    print("\n== %s ==" % check.name, flush=True)
    completed = subprocess.run(
        list(check.command),
        cwd=check.working_directory,
        env=environment,
        check=False,
    )
    duration = time.monotonic() - started
    status = "PASS" if completed.returncode == 0 else "FAIL"
    print("[%s] %s (%.2fs)" % (status, check.name, duration), flush=True)
    return completed.returncode == 0


def main() -> int:
    args = _arguments()
    if sys.version_info[:2] != (3, 10):
        print(
            "FAIL: run_all_checks requires the formal Python 3.10 runtime; got %s"
            % sys.version.split()[0],
            file=sys.stderr,
        )
        return 2
    report_dir = Path(args.report_dir)
    if not report_dir.is_absolute():
        report_dir = ROOT / report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    _syntax_check()
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUTF8": "1",
        }
    )
    checks = _checks(report_dir, args.quick)
    passed = sum(_run(check, environment) for check in checks)
    failed = len(checks) - passed
    print("\nChecks: %d passed, %d failed" % (passed, failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
