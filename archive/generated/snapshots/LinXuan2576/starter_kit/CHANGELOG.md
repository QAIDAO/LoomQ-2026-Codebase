# Starter Kit Changelog

## Unreleased

### Team LinXuan2576 · D5 交付（2026-08-23）

- Add `cli.py` — interactive L2 entry point: natural-language dialogue, paste-QASM path, offline `/run`, ASCII result visualization; zero third-party dependencies.
- Add `riscv_emulator_qext.py` — custom quantum RISC-V extension (Q-Ext: `qh/qx/qcx/qrz/qmeas`), fork of the official emulator with full backward compatibility; 6 end-to-end tests pass.
- Add `docs/riscv-quantum-ext.md` — instruction encoding spec (opcode `0x77`, R/I-type layouts).
- Add `docs/FIRST_RUN.md` — zero-background first-run guide.
- Rewrite root `README.md` as the team project README (architecture, one-command setup/run, evidence index).
- Fill `evidence/README.md` — declare L2 interaction, engineering/product, RISC-V Bonus, and newbie-guide Bonus.
- Keep official `riscv_emulator.py` untouched (official evaluator imports it directly).

### Official starter kit

- Use the importable `starter_kit/` name for the submission root.
- Add `__init__.py` so tests can use `from starter_kit import adapter` directly.

## 1.1.0 - 2026-07-27

- Publish the environment-only OpenAI-compatible L2 runtime contract.
- Fix the formal L2 scoring model to DeepSeek `deepseek-v4-flash`.
- Publish per-case call, token, and timeout budgets in `l2_policy.json`.
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
