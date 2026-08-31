# LoomQ — 让不懂量子的人也能跑量子电路

LoomQ is a small toolkit that lets someone with **no quantum background** describe
what they want in plain language and actually run it on real quantum simulators —
then see the result explained in words, not jargon.

It covers two competition levels:

- **L1 — universal transpiler.** One OpenQASM front-end, two backend-native
  targets (SpinQ OpenQASM 2.0 and OriginQ OriginIR), with a `run()` path that
  executes on both simulators and normalizes counts to a single bit-order
  contract (rightmost bit = `c[0]`).
- **L2 — the "speaks human" agent.** A natural-language agent that turns intent
  into a valid circuit, repairs broken circuits, and recommends a backend — with
  a **self-verify loop** that parses its own output and retries on error — plus a
  zero-dependency web UI that visualizes and narrates the circuit for beginners.

## Architecture

```
natural language ──▶ agent.py ──▶ QASM ──▶ parser.py ──▶ IR ──▶ emitters.py ──▶ backend-native text ──▶ runtime.py ──▶ counts
                     (L2)                  (L1 front)          (L1 targets)                            (L1 execute)
```

| Module | Role |
|---|---|
| `parser.py` | `parse_qasm()` — OpenQASM subset → LoomQ IR (the single source of truth). |
| `emitters.py` | `emit_spinq()` / `emit_originir()` — IR → backend-native circuit text. |
| `runtime.py` | `transpile()` / `run()` — dispatch to a target, execute on its simulator, normalize counts to little-endian. |
| `agent.py` | `agent_chat()` — one system prompt for GENERATE / FIX / RECOMMEND, with a validate-and-retry self-verify loop built on `parse_qasm`. |
| `webapp.py` + `index.html` | stdlib-only web UI: circuit diagram, plain-language legend, step-by-step walkthrough, animated results. |
| `adapter.py` (in `starter_kit/`) | competition entrypoint; delegates `transpile`/`run`/`agent_chat` here. |

The IR is deliberately the narrow waist: every backend and the agent's verifier
go through the same `parse_qasm` → IR shape, so a gate is defined once.

## Run it (clean environment)

Python 3.10 is required (spinqit ships cp310 wheels only).

```bash
# 1. install
python -m venv .venv
.venv/Scripts/python -m pip install -r starter_kit/requirements.txt   # Windows
# .venv/bin/python -m pip install -r starter_kit/requirements.txt     # Linux/macOS

# 2. L1 — no network needed
.venv/Scripts/python starter_kit/evaluator.py --level l1 --target spinq,originq

# 3. fast self-tests (parser + emitters + agent, no API key)
.venv/Scripts/python starter_kit/loomq/run_tests.py
```

### Try the agent + web UI (needs a DeepSeek-compatible key)

```bash
export LOOMQ_LLM_BASE_URL=https://api.deepseek.com
export LOOMQ_LLM_API_KEY=<your key>
export LOOMQ_LLM_MODEL=deepseek-v4-flash

.venv/Scripts/python starter_kit/loomq/webapp.py   # → http://localhost:8000
```

The agent runs at temperature 0 (thinking disabled) to satisfy the L2
consistency policy.

## Who this is for

The target user is a **curious beginner** — a student, a researcher in another
field, or a product person — who has heard of quantum computing but has never
written a circuit. LoomQ removes three barriers: the syntax (say it in English),
the backend zoo (the agent picks and explains), and the unreadable output (the
UI narrates what actually happened). The end-to-end flow is:

> type a request → agent returns a validated circuit → see it drawn and explained
> gate by gate → run it → read the result in plain language.
