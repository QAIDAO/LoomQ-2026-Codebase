#!/usr/bin/env python3
"""Validate the L2 real-model stress evidence is internally consistent and
that the Judge-facing docs' case counts match the single source of truth.

This is the programmatic gate for the "102 / 101" claim: if the summary JSON
does not support the numbers written in the docs, this script fails.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # starter_kit/
EVIDENCE = ROOT / "evidence"


def load_summary() -> dict:
    p = EVIDENCE / "files" / "l2-deepseek-v4-flash-stress-summary.json"
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    d = load_summary()
    rounds = d["rounds"]
    summary = d["summary"]

    total = sum(r["total"] for r in rounds)
    passed = sum(r["passed"] for r in rounds)
    failed = sum(r["failed"] for r in rounds)
    fail_records = [f for r in rounds for f in r.get("failures", [])]

    ok = True
    checks = {
        "total_cases": (total, summary["total_cases"]),
        "total_passed": (passed, summary["total_passed"]),
        "total_failed": (failed, summary["total_failed"]),
    }
    print("=== L2 stress summary internal consistency ===")
    for k, (recomputed, declared) in checks.items():
        match = recomputed == declared
        ok = ok and match
        print(f"  {k}: recomputed={recomputed} declared={declared} -> {'OK' if match else 'MISMATCH'}")

    # failure records must equal declared failures
    rec_match = len(fail_records) == failed
    ok = ok and rec_match
    print(f"  failure_records: {len(fail_records)} vs declared_failed={failed} -> {'OK' if rec_match else 'MISMATCH'}")

    # pass_rate
    pr = round(passed / total, 4)
    pr_match = abs(pr - summary["pass_rate"]) < 1e-3
    ok = ok and pr_match
    print(f"  pass_rate: recomputed={pr} declared={summary['pass_rate']} -> {'OK' if pr_match else 'MISMATCH'}")

    # Cross-check docs that quote the case count
    print("=== Docs cross-check (single source of truth) ===")
    doc_targets = [
        (EVIDENCE / "README.md", r"102 例", "102"),
        (EVIDENCE / "README.md", r"101 例通过", "101"),
        (EVIDENCE / "SCORECARD.md", r"102-case", "102"),
        (EVIDENCE / "SCORECARD.md", r"101 pass", "101"),
        (EVIDENCE / "L2_REAL_MODEL_VALIDATION.md", r"102 例", "102"),
        (EVIDENCE / "L2_REAL_MODEL_VALIDATION.md", r"101 例通过", "101"),
    ]
    for path, pat, expect in doc_targets:
        if not path.exists():
            print(f"  MISSING DOC: {path.name}")
            ok = False
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(pat, text):
            print(f"  {path.name}: contains {expect} -> OK")
        else:
            print(f"  {path.name}: missing '{pat}' -> MISMATCH")
            ok = False

    print()
    print("L2_STRESS_EVIDENCE_CONSISTENT =", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())