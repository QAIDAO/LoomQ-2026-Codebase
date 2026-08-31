# L2 Agent And Inclusive Experience

## Scope

L2 implements the required `agent_chat(prompt: str) -> str` entry point and a local Web experience for users without quantum-computing background. The formal entry combines six original micro-lessons, real L1 simulation, the three scored agent tasks, and an explicitly non-submitting hardware-preparation walkthrough.

## Deterministic Boundary

```text
user prompt
  -> OpenAI-compatible model call
  -> structured task plan
     -> generate/repair: L1 parse + 1024-shot local simulation
     -> select backend: backend_capabilities.json filter + ranking
  -> evaluator-facing text
  -> optional local Web rendering
```

The teaching path is separate from model reasoning:

```text
curriculum/lessons.json
  -> learning.lesson_catalog() (QASM removed)
  -> learning.simulate_lesson_experiment()
     -> L1 parse_openqasm2()
     -> L1 state-vector evolution
     -> L1 run_local() normalized result schema
  -> amplitude, probability, counts, and provenance in the browser
```

The model interprets natural language and drafts QASM. It cannot invent a backend, bypass QASM validation, or replace the L1 simulator. Invalid JSON or QASM is returned to the same model as a concise validation error, with at most three total calls.

## Protocol And Budgets

- Configuration is read only from `LOOMQ_LLM_BASE_URL`, `LOOMQ_LLM_API_KEY`, and `LOOMQ_LLM_MODEL`.
- Requests use OpenAI Chat Completions, `temperature: 0`, no streaming, and disabled thinking for `deepseek-v4-flash`.
- Each case is limited to three calls, an estimated 8,000 input tokens, 2,000 output tokens, and 120 seconds.
- API keys are sent only in the Authorization header. Exceptions name missing variables but never echo values.
- No external network resource is used besides the injected model endpoint.

## QASM Generation And Repair

The model returns a JSON plan containing a complete OpenQASM 2.0 program, a short summary, and optional expected dominant states. The deterministic layer then:

1. strips an optional code fence;
2. parses the circuit with `loomq.qasm.parse_openqasm2()`;
3. requires at least one explicit measurement;
4. executes 1,024 shots with the L1 state-vector simulator;
5. checks stated dominant states when the requested intent makes them explicit;
6. retries with the validation error or returns fenced QASM and observed leading counts.

## Backend Selection

The model extracts normalized constraints such as qubit count, real-hardware requirement, zero queue, paid-service exclusion, account requirement, and allowed platforms. `loomq.l2` applies those constraints to `backend_capabilities.json`, ranks only compatible records, and returns one canonical backend ID. An empty result is reported honestly instead of relaxing constraints silently.

## Inclusive Web Entry

Run:

```bash
python l2_app.py --host 127.0.0.1 --port 8765
```

For daily Windows use, `.\l2.cmd start|stop|restart|status` wraps `scripts/l2-service.ps1`, loads the ignored `.env.l2.local`, starts a hidden process, verifies `/api/health`, and records a port-specific PID. Double-clicking `l2.cmd` defaults to `start`. The controller refuses to stop a PID that is no longer a Python process.

The first screen assumes no quantum vocabulary. A learner operates a classical bit, prepares and measures an H state through L1, predicts a Bell result, runs a 1,024-shot L1 simulation, checks their understanding, and sees the exact consent boundary before any hardware step. The six-lesson catalog is now an enterable lab player rather than a read-only index: every lesson has at least two comparison circuits, a prediction field, a shots control, statevector probabilities, and L1 counts.

The lab player does not present rubric-like learning objectives as explanations. Each lesson starts from a concrete question, keeps technical vocabulary in a disclosure, and uses one concept-specific animation: path splitting, repeated-shot voting, paired outcomes, phase arrows, correlation propagation, or ideal-vs-hardware noise. The 40-second foundation now explicitly teaches only the measured-vs-premeasurement distinction and routes phase/interference and entanglement to the later labs instead of claiming they were already demonstrated.

The six visual families are authored as deterministic Remotion compositions and embedded with `@remotion/player`, but the course deliberately does not present them as videos. All 13 lesson conditions map to 5–6 named key states. A LeetCode-style controller seeks between those states and shows one title plus one plain-language explanation at a time, with previous, next, step dots, and optional auto-advance. Native video controls, autoplay and the progress scrubber are hidden; explanatory videos are treated as a separate future content type. A mobile-only compact mode increases conclusion and evidence typography without changing the scientific content. Source lives in `motion/remotion/`; `npm run build` emits the dependency-free browser bundle under `web/motion/`.

`motion/hyperframes/` is the matching reproducibility and motion-audit artifact: a 48-second, six-act timeline covering paths, shots, Bell correlation, phase cancellation, GHZ propagation, and ideal-versus-real counts. It uses one seek-safe paused GSAP timeline, fixed data, motion assertions, and no runtime randomness. HyperFrames `0.7.107` reports zero runtime errors, zero layout issues, zero motion failures, and 71/71 WCAG AA contrast checks; its only non-gating warning recommends splitting the six coherent audit acts into sub-compositions. This audit artifact is explanatory evidence, not a second controller for the web Player.

`GET /api/evidence/hardware/bell` returns a strict, secret-free projection of the archived OriginQ and SpinQ Bell evidence. The noise lesson compares those real counts with an explicitly ideal baseline and exposes platform, timestamp and job ID. Reading this endpoint creates no supplier job and consumes no hardware quota.

The creative path treats the visitor as the learner and accepts an open phenomenon or outcome rather than a teaching-only prompt. Generate and repair remain distinct because repair needs both the declared intent and an editable QASM source. Backend selection is presented as controls over actual locally available environments. The web API exposes only visitor-created hardware profiles; development credentials from `.env.hardware.local` cannot be selected or submitted through the browser. Visitor credentials live only in backend process memory and are cleared on service restart. They never enter browser responses, SQLite, task history, or local credential files.

Real-hardware task history is persisted in the local `local_docs/loomq.sqlite3` SQLite database under the `local` owner. The indexed ledger stores credential-free task metadata, QASM, stage updates, provider job IDs, and results. On first startup it imports and removes legacy `local_docs/hardware_jobs/*.json` records; pending work found after a service restart is marked interrupted without claiming that the provider task was cancelled.

The same page leads into the scored L2 workbench. Generate and repair requests call `/api/chat`, which routes to the evaluator-facing `adapter.agent_chat()` boundary. Generated or repaired QASM is shown only after L1 parsing and 1,024-shot simulation. “执行已有代码” bypasses the model and calls `/api/validate-qasm` for deterministic parsing and measurement checks before exposing the environment chooser. The selected circuit can then run locally or be submitted to a confirmed, configured QPU.

`l2_app.py` also serves hardware profile and asynchronous job endpoints under `/api/hardware/`. Job summaries power a separate “真机执行记录” screen; expanding a record fetches its QASM and result on demand. The implementation uses Python's standard-library SQLite driver, keeps provider credentials out of API responses, and exposes credential-safe stage and failure messages.

Browser acceptance on 2026-08-12 covered dynamic loading of all six lessons and direct interaction with the path, repeated-shot, Bell, phase-interference, GHZ, and archived-hardware-noise step diagrams. Previous/next navigation, direct step dots and auto-advance/pause were verified; no native video controls were exposed. At 390x844 the compact composition mounted with all three step controls visible and no horizontal overflow. The final lesson displayed both real evidence records, including non-zero 01/10 counts and traceable job IDs. The existing `l2-studio-*.png` files predate this redesign and must be refreshed before final evidence submission.

## Verification

```bash
python -m unittest tests.test_l2_agent tests.test_l2_learning tests.test_l2_experience
python -m unittest ..\tests\test_l2_contract.py
cd motion/remotion && npm run check && npm run build
cd ../hyperframes && npm run check
python scripts/verify_all.py
```

The local L2 suite uses an in-process OpenAI-compatible mock server. A real DeepSeek endpoint is still required for model-quality validation and the official hidden prompt variants.
