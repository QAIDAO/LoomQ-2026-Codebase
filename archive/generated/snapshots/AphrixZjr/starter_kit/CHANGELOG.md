# Starter Kit Changelog

## Unreleased

- Use the importable `starter_kit/` name for the submission root.
- Add `__init__.py` so tests can use `from starter_kit import adapter` directly.
- Bind every archived SpinQ task to source/submitted QASM, request, raw result and a timestamped standard summary; enforce exact provider shots and preserve the historical files byte-for-byte.
- Harden L2 backend negation, semantic repair fallback and the cumulative 3-attempt / 8,000-input / 2,000-output budget; add deterministic budget tests and a three-round adversarial live benchmark harness.
- Record the real-model 312/312 three-round result and 1/1 public L2 evaluator with hash-bound stdout, distinct from the 2026-08-11 accepted archive.
- Lower all supported L3 classical widths to shared control flow, including the `c[21]` specialization needed to reuse and restore `x31`, with sequential and nested size gates.
- Align Web proposal/run safety with measurement validation, add a read-only allowlisted SpinQ/OriginQ hardware comparison, and extend browser checks through the full eight-stage flow.
- Add a Linux cold-build workflow with container tests, public evaluators, hardware-evidence integrity checks and headless browser verification.

## 1.1.0 - 2026-07-27

- Publish the environment-only OpenAI-compatible L2 runtime contract.
- Fix the formal L2 scoring model to DeepSeek `deepseek-v4-flash`.
- Publish the formal model, per-case timeout, and case count in `l2_policy.json`; call and token budgets remain organizer-injected rather than public policy fields.
- Add a dependency-free `llm_client.py` transport helper without prompts or scoring logic.
- Clarify that the organizer provides no API endpoint, key, or credit before formal scoring.

## 1.0.1 - 2026-07-27

- Add the read-only local final-submission preflight.
- Define `starter_kit/` as the build and evaluation root in official forks.
- Document commit-SHA submission, server-side cutoff time, receipts, and resubmission rules.

## 1.0.0 - 2026-07-11

- Freeze submission contract v1.0.
- Add `submission.yaml`, version metadata, and machine-readable public reports.
- Remove mock scoring paths, prompt-specific answers, and the L3 reference solution.
- Clarify that formal scoring runs in an organizer-owned isolated environment.
