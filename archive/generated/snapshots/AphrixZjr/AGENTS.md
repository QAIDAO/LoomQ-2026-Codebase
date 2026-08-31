# Repository Guidelines

## Project Structure & Module Organization

This repository contains the LoomQ competition materials and tooling. Contestant-facing code lives in `starter_kit/`: `adapter.py` defines the submission interface, `evaluator.py` runs public checks, `circuits/` holds sample QASM inputs, and `examples/` contains backend examples. Organizer-side intake and archive logic is under `competition/`, with its authoritative settings in `competition/config.json`. Repository-level tests are in `tests/`. Competition documents and generated formats (`problem_statement.md`, PDF, HTML, DOCX, and PNG) remain at the root. GitHub issue forms and automation live in `.github/`.

## Build, Test, and Development Commands

- `python -m unittest discover -s tests -v` runs the organizer and L2 contract test suite, matching CI.
- `python -m py_compile competition/*.py starter_kit/prepare_submission.py` performs the CI syntax check (use a shell that expands `*.py`).
- `cd starter_kit && python evaluator.py --json-out report.json` runs all enabled public submission checks.
- `cd starter_kit && python evaluator.py --level l1 --target spinq,originq,braket` targets a specific level and backend set.
- `cd starter_kit && docker build -t loomq-submission .` builds the Python 3.10 evaluation image.
- `python starter_kit/prepare_submission.py --team-id <GITHUB_USERNAME>` validates a contestant fork before final submission.

## Coding Style & Naming Conventions

Use Python 3.10-compatible code, four-space indentation, UTF-8 text, and standard-library solutions where practical. Follow existing conventions: `snake_case` for modules, functions, and variables; `PascalCase` for test classes; and uppercase constants such as `ROOT` or `SHA`. Keep adapter signatures aligned with `starter_kit/target_ir_contract.md`. Pin every third-party dependency exactly in `starter_kit/requirements.txt` (`package==1.2.3`). No formatter or linter is enforced, so keep imports grouped and changes consistent with nearby code.

## Testing Guidelines

Tests use `unittest` and files named `test_*.py`; test methods also begin with `test_`. Add regression tests for contract, validation, archive-safety, and submission-flow changes. Tests must be deterministic and must not require real credentials or public network access. Run the full suite before opening a pull request; there is currently no numeric coverage threshold.

## Commit & Pull Request Guidelines

Recent history favors short, imperative subjects, optionally with a scope (`docs: ...`), such as `Clarify contestant submission guidance`. Keep each commit focused. Pull requests should explain the behavior changed, identify affected competition levels or contracts, and list verification commands. Link relevant issues; include screenshots only for rendered documentation, forms, or UI changes. Never commit API keys, tokens, cookies, private contestant data, or generated evaluation reports.
