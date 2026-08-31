#!/usr/bin/env python3
"""Tiny assert-based test harness shared by the LoomQ test files.

A test file imports check / check_raises to record results, then calls summary()
at the end to print the tally and set the exit code (0 = all passed, 1 = a
failure) so run_tests.py and CI can gate on it. No third-party dependencies.
"""

_passed = 0
_failed = 0


def check(label, got, want):
    """Record a pass/fail by comparing got == want, printing a readable line."""
    global _passed, _failed
    if got == want:
        _passed += 1
        print(f"PASS  {label}")
    else:
        _failed += 1
        print(f"FAIL  {label}\n        got : {got}\n        want: {want}")


def check_raises(label, fn, exc):
    """Record a pass iff calling fn() raises the given exception type."""
    global _passed, _failed
    try:
        fn()
    except exc:
        _passed += 1
        print(f"PASS  {label}")
    else:
        _failed += 1
        print(f"FAIL  {label}  (expected {exc.__name__} to be raised)")


def summary():
    """Print the tally and exit non-zero if anything failed."""
    print(f"\n{_passed} passed, {_failed} failed")
    if _failed:
        raise SystemExit(1)
