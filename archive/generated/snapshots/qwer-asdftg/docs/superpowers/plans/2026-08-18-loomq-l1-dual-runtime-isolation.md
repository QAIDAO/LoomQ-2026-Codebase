# LoomQ L1 Dual-Runtime Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the three mandated LoomQ L1 local simulators in one Python 3.10 Docker submission image without changing the four direct provider pins.

**Architecture:** The primary Python 3.10 interpreter contains SpinQit and pyQPanda; a second Python 3.10 venv contains the incompatible Amazon Braket SDK stack.  The parent Braket runner keeps its lazy direct-import mode, but when `LOOMQ_BRAKET_PYTHON` is set it delegates local execution through a JSON-only internal worker and returns the same `RawExecution` record.

**Tech Stack:** Python 3.10, Docker, venv, standard-library `json`/`subprocess`, unittest, SpinQit 0.2.4, pyQPanda 3.8.5, Amazon Braket SDK 1.108.0.

---

### Task 1: Add a bounded Braket worker protocol

**Files:**
- Create: `starter_kit/loomq_l1/runners/braket_worker.py`
- Modify: `starter_kit/loomq_l1/runners/braket.py`
- Modify: `starter_kit/tests/l1/test_runners.py`

- [ ] **Step 1: Write failing worker-protocol tests**

Add tests that patch `subprocess.run` and set `LOOMQ_BRAKET_PYTHON` to an explicit fake interpreter.  They must assert the parent sends only this exact JSON object on stdin:

```python
{"native_ir": "OPENQASM 3.0;\\n", "shots": 8}
```

Assert that a valid worker response produces `RawExecution("braket_local_simulator", ...)`, preserves binary counts and provider metadata, and creates a nonempty local job ID if the worker has no provider ID.  Add negative tests for a timeout, nonzero return code, invalid JSON, a non-mapping `counts`, invalid `job_id`, and a response containing an `is_mock` field; each must raise `ProviderExecutionError` without including child stderr or environment values.

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```powershell
$env:PYTHONUTF8='1'
& 'C:\Users\lixin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest starter_kit.tests.l1.test_runners.BraketRunnerTests -v
```

Expected: the isolated-worker tests fail because the runner has no subprocess path.

- [ ] **Step 3: Implement the worker and parent response validator**

Implement these worker functions:

```python
def execute_payload(payload: dict[str, object]) -> dict[str, object]:
    # validate exact built-in str/int fields; import Braket locally;
    # Program(source=native_ir) -> LocalSimulator().run(...).result();
    # return JSON-safe counts, job_id, sdk_version, and no secrets.

def main() -> int:
    # json.load(sys.stdin), print one JSON response, return nonzero on bad input.
```

In `run_braket`, branch only when `LOOMQ_BRAKET_PYTHON` is a nonempty string.  Call:

```python
subprocess.run(
    [worker_python, "-m", "loomq_l1.runners.braket_worker"],
    input=json.dumps({"native_ir": native_ir, "shots": shots}),
    text=True,
    capture_output=True,
    timeout=120,
    check=False,
)
```

Validate the successful JSON response before building `RawExecution`; use existing `local_job_id`, `metadata`, and `ProviderExecutionError`.  Leave the direct lazy-import path unchanged when the variable is absent.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run the command from Step 2.

Expected: all Braket runner tests pass, including worker failures and direct lazy-import tests.

- [ ] **Step 5: Commit**

```bash
git add starter_kit/loomq_l1/runners/braket.py starter_kit/loomq_l1/runners/braket_worker.py starter_kit/tests/l1/test_runners.py
git commit -m "feat: isolate LoomQ Braket local runner"
```

### Task 2: Build the prescribed pins into isolated Python 3.10 environments

**Files:**
- Modify: `starter_kit/Dockerfile`
- Modify: `starter_kit/tests/l1/test_provider_integration.py`

- [ ] **Step 1: Write a failing container-layout assertion**

Extend the integration test module with an environment-aware assertion:

```python
def test_braket_worker_runtime_is_configured(self):
    worker = os.environ["LOOMQ_BRAKET_PYTHON"]
    self.assertTrue(Path(worker).is_file())
```

Inside the image, also run each interpreter with `-c` to assert `sys.version_info[:2] == (3, 10)` and its assigned distribution has the exact required version.  Keep the module skipped on host interpreters when the SDK environments are unavailable.

- [ ] **Step 2: Run the new test to verify RED**

Run the module with the bundled host interpreter before changing the Dockerfile:

```powershell
$env:PYTHONUTF8='1'
& 'C:\Users\lixin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest starter_kit.tests.l1.test_provider_integration.ProviderIntegrationTests.test_braket_worker_runtime_is_configured -v
```

Expected: it skips because the real SDK environment is unavailable; the subsequent Docker execution is the required non-skipped proof.

- [ ] **Step 3: Implement the two-environment Dockerfile**

Replace the single conflicting install with this logical sequence:

```dockerfile
COPY requirements.txt .
RUN python -m pip install --no-cache-dir numpy==1.26.4 pyqpanda==3.8.5 spinqit==0.2.4
RUN python -m venv /opt/loomq-braket-venv \
 && /opt/loomq-braket-venv/bin/pip install --no-cache-dir numpy==1.26.4 amazon-braket-sdk==1.108.0
ENV LOOMQ_BRAKET_PYTHON=/opt/loomq-braket-venv/bin/python
```

Retain `requirements.txt` unchanged as the canonical direct dependency declaration.  The Dockerfile must contain comments documenting the ANTLR conflict and why the two commands deliberately install complementary subsets.
After copying the project, create `/workspace/starter_kit -> /workspace/submission` and set `PYTHONPATH=/workspace`, so the same image supports both the evaluator's top-level `import adapter` and package-style unittest imports.  Run package-style tests with `docker run -w /workspace ...`; keep the evaluator at its `/workspace/submission` workdir so its top-level imports remain unchanged.

- [ ] **Step 4: Build the Python 3.10 image and verify GREEN**

Run:

```bash
docker build -t loomq-l1-deps starter_kit
docker run --rm loomq-l1-deps python -c "import sys,spinqit,pyqpanda; assert sys.version_info[:2] == (3,10)"
docker run --rm loomq-l1-deps /opt/loomq-braket-venv/bin/python -c "import sys,braket; assert sys.version_info[:2] == (3,10)"
```

Expected: image builds with the exact direct pins, while each conflicting ANTLR runtime remains inside its own interpreter environment.

- [ ] **Step 5: Commit**

```bash
git add starter_kit/Dockerfile starter_kit/tests/l1/test_provider_integration.py
git commit -m "build: isolate LoomQ provider dependencies"
```

### Task 3: Prove all three real local simulators and finalize bit order

**Files:**
- Modify: `starter_kit/loomq_l1/runners/braket.py` only if the real asymmetric result requires `reverse_bits=True`
- Modify: `starter_kit/tests/l1/test_provider_integration.py`

- [ ] **Step 1: Run the asymmetric real-SDK test and record raw keys**

Run inside the image:

```bash
docker run --rm -w /workspace loomq-l1-deps python -m unittest starter_kit.tests.l1.test_provider_integration.ProviderIntegrationTests.test_asymmetric_bit_order -v
```

The circuit has `x q[0]` then `measure q -> c`; the canonical result must be exactly `{"01": 128}` because the contest renders `c[1]c[0]`.

- [ ] **Step 2: Verify RED or GREEN and update one global flag if needed**

If a provider returns the reverse raw ordering, change only that runner's `RawExecution(reverse_bits=...)` constant.  Add the observed raw key to the integration assertion; do not add circuit-specific logic.

- [ ] **Step 3: Run the all-12-gate real-SDK test**

Run:

```bash
docker run --rm -w /workspace loomq-l1-deps python -m unittest starter_kit.tests.l1.test_provider_integration.ProviderIntegrationTests.test_all_gates_transpile_run_and_validate_schema -v
```

Expected: each target emits nonempty native IR, returns 256 total counts, and passes `evaluator.validate_schema`.

- [ ] **Step 4: Run the full L1 and official evaluator verification**

Run:

```bash
docker run --rm -w /workspace loomq-l1-deps python -m unittest discover -s starter_kit/tests/l1 -v
docker run --rm loomq-l1-deps python evaluator.py --level l1 --target spinq,originq,braket --json-out /tmp/loomq-report.json
```

Expected: no SDK-unavailable skips in the container and all L1 public evaluator cases pass.

- [ ] **Step 5: Commit any verified bit-order change**

```bash
git add starter_kit/loomq_l1/runners/braket.py starter_kit/tests/l1/test_provider_integration.py
git commit -m "test: verify three local LoomQ backends"
```

### Task 4: Final isolation review and evidence record

**Files:**
- Modify: `starter_kit/tests/l1/test_provider_integration.py` only if verification needs a missing regression

- [ ] **Step 1: Verify no credentials cross the worker boundary**

Add a subprocess mock assertion that the JSON input has exactly `native_ir` and `shots`, and that the runner's raised error cannot include a supplied fake credential environment variable.

- [ ] **Step 2: Run all targeted checks**

Run:

```bash
docker run --rm -w /workspace loomq-l1-deps python -m unittest starter_kit.tests.l1.test_runners starter_kit.tests.l1.test_provider_integration -v
git diff --check
git status --short --branch
```

Expected: worker protocol, real SDK integration, Docker image, and whitespace checks pass; the branch is clean except for intentional changes awaiting commit.

- [ ] **Step 3: Commit final verification regression if needed**

```bash
git add starter_kit/tests/l1/test_runners.py starter_kit/tests/l1/test_provider_integration.py
git commit -m "test: harden LoomQ isolated provider runtime"
```
