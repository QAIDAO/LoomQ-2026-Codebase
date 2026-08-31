# LoomQ Final Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove objective L1/L2 compliance risks and turn the existing CLI into a reproducible, beginner-oriented LoomQ entrypoint with evidence for the engineering and UX criteria.

**Architecture:** Preserve the current unified parser-to-IR L1 architecture and organizer-injected L2 transport contract. Add a deadline-aware L2 request budget, transparent mock-result rejection, and a thin guided CLI presentation layer rather than a second agent or simulator. Documents link every claimed capability to executable tests.

**Tech Stack:** Python 3.10, `unittest`, Docker, existing OpenQASM/Hybrid-QASM toolchain.

---

### Task 1: Bound the L2 end-to-end request budget

**Files:**
- Modify: `starter_kit/llm_client.py`
- Modify: `starter_kit/loomq_l2.py`
- Modify: `starter_kit/tests/l2/test_agent.py`
- Create: `starter_kit/tests/l2/test_deadline.py`

- [ ] **Step 1: Write failing deadline tests**

```python
def test_agent_chat_never_passes_more_than_remaining_case_budget(monkeypatch):
    # Fake monotonic time and record the timeout sent to the transport.
    # A malformed first completion triggers one repair; their total budget is <= 120.
    ...

def test_expired_budget_raises_a_secret_free_validation_error(monkeypatch):
    # An exhausted deadline must not make a second remote call.
    ...
```

- [ ] **Step 2: Run them to verify failure**

Run: `python -m unittest starter_kit.tests.l2.test_deadline -v`

Expected: FAIL because no per-call deadline is propagated.

- [ ] **Step 3: Implement a monotonic deadline**

```python
CASE_TIMEOUT_SECONDS = 120.0

def chat_completion(messages, *, timeout_seconds=None, **extra):
    # Clamp a caller-provided positive timeout to configuration timeout.
    ...

def agent_chat(prompt):
    deadline = time.monotonic() + CASE_TIMEOUT_SECONDS
    # Each request receives max(0, deadline - time.monotonic()).
    ...
```

The deadline error must be a fixed category and never include a response body, endpoint path, or credential.

- [ ] **Step 4: Run L2 regression tests**

Run: `python -m unittest discover -s starter_kit/tests/l2 -p 'test_*.py' -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add starter_kit/llm_client.py starter_kit/loomq_l2.py starter_kit/tests/l2
git commit -m "fix(l2): bound total model-call deadline"
```

### Task 2: Make mock-result handling transparent

**Files:**
- Modify: `starter_kit/loomq_l1/normalize.py`
- Modify: `starter_kit/tests/l1/test_normalize.py`
- Modify: `starter_kit/tests/l1/test_adapter_contract.py`

- [ ] **Step 1: Write failing anti-mock tests**

```python
def test_build_result_rejects_true_is_mock_metadata_at_any_depth():
    raw = RawExecution(..., metadata={"nested": {"is_mock": True}})
    with self.assertRaises(NormalizationError):
        build_result(raw, width=1, shots=8192)

def test_build_result_preserves_false_is_mock_metadata_without_mutating_input():
    raw = RawExecution(..., metadata={"is_mock": False})
    self.assertIs(build_result(raw, width=1, shots=8192)["meta"]["is_mock"], False)
```

- [ ] **Step 2: Run the focused tests to verify failure**

Run: `python -m unittest starter_kit.tests.l1.test_normalize starter_kit.tests.l1.test_adapter_contract -v`

Expected: FAIL because the current normalizer silently removes every `is_mock` key.

- [ ] **Step 3: Implement recursive detection**

```python
def _reject_mock_metadata(value, seen):
    # Traverse mapping/list/tuple/set safely.
    # Raise NormalizationError if and only if key "is_mock" has value True.
    ...
```

Copy metadata unchanged after validation; never fabricate or erase a true mock marker.

- [ ] **Step 4: Run L1 regression tests in Docker**

Run: `docker run --rm -w /workspace loomq-l2-l3-verify python -m unittest discover -s starter_kit/tests/l1 -p 'test_*.py' -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add starter_kit/loomq_l1/normalize.py starter_kit/tests/l1
git commit -m "fix(l1): reject true mock execution metadata"
```

### Task 3: Strengthen semantic coverage for L2 prompt variations

**Files:**
- Modify: `starter_kit/l2_semantics.py`
- Modify: `starter_kit/tests/l2/test_probe.py`
- Modify: `starter_kit/tests/l2/test_agent.py`

- [ ] **Step 1: Write failing synonym tests**

```python
def test_semantics_recognizes_epr_and_maximally_entangled_requests():
    assert validate_prompt_reply("制备一个 EPR 对并全测量", BAD_QASM) is not None

def test_backend_zero_waiting_synonym_is_checked():
    assert validate_prompt_reply("15 比特、零等待，推荐平台", "originq_wukong") is not None
```

- [ ] **Step 2: Run focused tests to verify failure**

Run: `python -m unittest starter_kit.tests.l2.test_probe -v`

Expected: FAIL for the new intent variants.

- [ ] **Step 3: Extend only semantic intent patterns**

Recognize `EPR`, `Bell pair`, `最大纠缠态` only when the request explicitly asks for a two-qubit entangled state; recognize zero-wait synonyms only in an explicit backend-selection request. Preserve the unknown-intent pass-through rule.

- [ ] **Step 4: Run L2 regression tests**

Run: `python -m unittest discover -s starter_kit/tests/l2 -p 'test_*.py' -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add starter_kit/l2_semantics.py starter_kit/tests/l2
git commit -m "feat(l2): recognize equivalent task intents"
```

### Task 4: Add a five-minute beginner CLI journey and engineering evidence

**Files:**
- Modify: `starter_kit/l2_cli.py`
- Modify: `starter_kit/tests/l2/test_cli.py`
- Modify: `starter_kit/README.md`
- Modify: `starter_kit/evidence/README.md`
- Create: `starter_kit/newcomer_guide.md`
- Create: `scripts/verify_submission.ps1`

- [ ] **Step 1: Write failing CLI tests**

```python
def test_beginner_mode_explains_the_first_experiment_without_a_key():
    # `python -m starter_kit.l2_cli --guide` prints a no-jargon path and exits 0.
    ...

def test_result_explanation_maps_bell_counts_to_plain_language():
    # Known 00/11 counts produce an explanation of correlation and next action.
    ...
```

- [ ] **Step 2: Run focused CLI tests to verify failure**

Run: `python -m unittest starter_kit.tests.l2.test_cli -v`

Expected: FAIL because guide/result-explanation flags do not exist.

- [ ] **Step 3: Implement a no-key guide and deterministic result explainer**

`--guide` must explain QASM, backend, simulator, shots and real hardware in plain Chinese with one concrete Bell experiment. `--explain-counts '{"00":4102,"11":4090}'` must render a compact ASCII bar chart and explain only what the counts support. Do not invoke an LLM for either command.

- [ ] **Step 4: Add one-command verification and proof-oriented documents**

`verify_submission.ps1` must build the Starter Kit Docker image and run L1/L2/L3 test suites plus public evaluators, returning nonzero on failure. README must name the intended newcomer group and include a five-minute route. Evidence README must check only UX claims backed by the CLI/guide paths and test command.

- [ ] **Step 5: Run complete verification and commit**

Run: `powershell -ExecutionPolicy Bypass -File scripts/verify_submission.ps1`

Expected: Docker build, all unit suites, L1 public 6/6, and L3 public 1/1 pass.

```bash
git add starter_kit scripts
git commit -m "feat(ux): add beginner LoomQ journey and verification entrypoint"
```

### Task 5: Preflight and final handoff

**Files:**
- Modify: `starter_kit/prepare_submission.py`
- Modify: `tests/test_submission_tools.py`
- Modify: `starter_kit/README.md`

- [ ] **Step 1: Write a failing manifest/preflight test**

```python
def test_preflight_rejects_l2_manifest_without_required_environment_contract():
    # A temporary malformed submission.yaml must produce an actionable nonzero result.
    ...
```

- [ ] **Step 2: Add offline manifest checks only**

Validate the declared contract version, all three enabled levels, Python 3.10 and L2 environment variable names. Do not claim the injected host is externally reachable and do not create a final GitHub Issue.

- [ ] **Step 3: Run complete verification, prepare_submission and push**

Run: `python starter_kit/prepare_submission.py --team-id <TEAM_ID>` once the user-provided team id is available; otherwise document the one remaining required command without fabricating a report.

