#!/usr/bin/env python3
"""Run the public contract check and project-local regression suite."""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loomq.verification import (  # noqa: E402
    verify_official_family_roundtrips,
    verify_vendor_executions,
    verify_vendor_parsers,
)
from tests.live_l2_deepseek_harness import verify_campaign_report  # noqa: E402


def run_public_evaluator(level: str) -> int:
    completed = subprocess.run(
        [
            sys.executable,
            "evaluator.py",
            "--level",
            level,
            "--target",
            "spinq,originq,braket",
        ],
        cwd=ROOT,
    )
    return completed.returncode


def run_local_tests(*, forbid_skips: bool = False) -> bool:
    suite = unittest.defaultTestLoader.discover(str(TESTS), pattern="test_*.py")
    release_value = os.environ.pop("LOOMQ_RELEASE_MODE", None)
    require_native_value = os.environ.pop("LOOMQ_REQUIRE_NATIVE", None)
    try:
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
        if release_value is not None:
            os.environ["LOOMQ_RELEASE_MODE"] = release_value
        if require_native_value is not None:
            os.environ["LOOMQ_REQUIRE_NATIVE"] = require_native_value
    if forbid_skips and result.skipped:
        print(
            f"Release verification forbids skipped tests; observed {len(result.skipped)}.",
            file=sys.stderr,
        )
        return False
    return result.wasSuccessful()


def run_pipeline_verification(
    *, require_native: bool = False, forbid_skips: bool = False
) -> bool:
    records = verify_official_family_roundtrips()
    records.extend(verify_vendor_parsers(require_native=require_native))
    records.extend(verify_vendor_executions(require_native=require_native))
    counts = {
        status: sum(record.status == status for record in records)
        for status in ("pass", "fail", "skip")
    }
    print(
        "Official-family pipeline verification: "
        f"{counts['pass']} passed, {counts['fail']} failed, {counts['skip']} skipped."
    )
    for record in records:
        if record.status == "fail":
            print(
                f"[FAIL] {record.case}/{record.target}/{record.check}: "
                f"{record.detail}",
                file=sys.stderr,
            )
    return counts["fail"] == 0 and (not forbid_skips or counts["skip"] == 0)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--release",
        action="store_true",
        help="require native SDK execution and reject every fallback or skip",
    )
    parser.add_argument(
        "--l2-report",
        type=Path,
        default=TESTS / "generated" / "l2-live-deepseek-report.json",
        help="real-model campaign report required by --release",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    release = args.release or os.environ.get("LOOMQ_RELEASE_MODE") == "1"
    if release:
        os.environ["LOOMQ_RELEASE_MODE"] = "1"
        os.environ["LOOMQ_REQUIRE_NATIVE"] = "1"
    require_native = release or os.environ.get("LOOMQ_REQUIRE_NATIVE") == "1"
    if require_native:
        required = {"spinq": "spinqit", "originq": "pyqpanda", "braket": "braket"}
        missing = [target for target, module in required.items() if importlib.util.find_spec(module) is None]
        if missing:
            print("Missing required native SDKs: " + ", ".join(missing), file=sys.stderr)
            return 1
    l1_status = run_public_evaluator("l1")
    l3_status = run_public_evaluator("l3")
    pipeline_ok = run_pipeline_verification(
        require_native=require_native, forbid_skips=release
    )
    tests_ok = run_local_tests(forbid_skips=release)
    campaign_ok = True
    if release:
        campaign_errors = verify_campaign_report(args.l2_report.resolve())
        campaign_ok = not campaign_errors
        for error in campaign_errors:
            print(f"[FAIL] L2 campaign: {error}", file=sys.stderr)
    if l1_status or l3_status or not pipeline_ok or not tests_ok or not campaign_ok:
        return 1
    print("All public and local checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
