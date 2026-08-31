# L2 Provider Profiles and Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe local provider selection, exact L2 remediation errors, and three-task model probes without changing LoomQ's formal `agent_chat` contract.

**Architecture:** Formal `adapter.agent_chat` continues to read only the organizer-injected `LOOMQ_LLM_*` values. A local-only profile module temporarily maps a selected provider's endpoint, default model, and environment-held key into those variables for the CLI. A separate probe calls that same agent and independently checks GHZ/Bell semantics and capability-table backend answers.

**Tech Stack:** Python 3.10 standard library, existing LoomQ OpenQASM parser, `unittest`, OpenAI Chat Completions-compatible HTTP.

---

## Files

- Create: `starter_kit/l2_errors.py` — typed, secret-safe diagnostics.
- Create: `starter_kit/l2_profiles.py` — local provider presets and reversible environment override.
- Create: `starter_kit/l2_probe.py` — three task definitions, semantic checks, aggregation.
- Modify: `starter_kit/llm_client.py`, `starter_kit/loomq_l2.py`, `starter_kit/l2_cli.py`.
- Create: `starter_kit/tests/l2/test_errors.py`, `test_profiles.py`, `test_probe.py`.
- Modify: `starter_kit/tests/l2/test_agent.py`, `test_cli.py`, `starter_kit/README.md`, and `starter_kit/evidence/README.md`.

### Task 1: Typed transport diagnostics

**Files:**
- Create: `starter_kit/l2_errors.py`
- Modify: `starter_kit/llm_client.py`
- Test: `starter_kit/tests/l2/test_errors.py`

- [ ] **Step 1: Write failing tests**

```python
def test_http_error_keeps_status_and_request_id_but_not_body(self):
    error = urllib.error.HTTPError(
        "https://api.example.test/v1/chat/completions", 429, "Too Many Requests",
        {"x-request-id": "req-123"}, io.BytesIO(b"provider-secret-body"),
    )
    with mock.patch("starter_kit.llm_client._open_request", side_effect=error):
        with self.assertRaises(L2ApiError) as caught:
            llm_client.chat_completion([])
    self.assertEqual(caught.exception.status, 429)
    self.assertEqual(caught.exception.request_id, "req-123")
    self.assertNotIn("provider-secret-body", str(caught.exception))

def test_missing_key_names_only_the_missing_variable(self):
    with mock.patch.dict(os.environ, {
        "LOOMQ_LLM_BASE_URL": "https://api.example.test/v1",
        "LOOMQ_LLM_MODEL": "demo",
    }, clear=True):
        with self.assertRaisesRegex(L2ConfigurationError, "LOOMQ_LLM_API_KEY"):
            llm_client.chat_completion([])
```

- [ ] **Step 2: Verify tests fail**

Run:

```powershell
& 'C:\Users\lixin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest starter_kit.tests.l2.test_errors -v
```

Expected: FAIL because the typed L2 errors do not exist.

- [ ] **Step 3: Implement minimal safe errors**

```python
class L2Error(RuntimeError):
    category = "l2"

class L2ConfigurationError(L2Error):
    category = "configuration"

class L2TransportError(L2Error):
    category = "transport"
    def __init__(self, host, timeout_seconds):
        super().__init__(f"cannot reach {host} within {timeout_seconds:g}s")
        self.host, self.timeout_seconds = host, timeout_seconds

class L2ApiError(L2Error):
    category = "api"
    def __init__(self, status, host, request_id=None):
        suffix = f"; request_id={request_id}" if request_id else ""
        super().__init__(f"API at {host} returned HTTP {status}{suffix}")
        self.status, self.host, self.request_id = status, host, request_id

class L2ValidationError(L2Error):
    category = "validation"
```

Validate `LOOMQ_LLM_BASE_URL` has an HTTP(S) scheme and hostname. Convert `HTTPError` to `L2ApiError`, retaining only status and `x-request-id`/`request-id`; never call `exc.read()`. Convert timeout and URL errors to `L2TransportError(host, timeout)`.

- [ ] **Step 4: Verify and commit**

Run:

```powershell
& 'C:\Users\lixin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest starter_kit.tests.l2.test_errors starter_kit.tests.l2.test_agent starter_kit.tests.l2.test_cli -v
git add starter_kit/l2_errors.py starter_kit/llm_client.py starter_kit/tests/l2/test_errors.py
git commit -m "feat: add safe L2 transport diagnostics"
```

Expected: tests PASS.

### Task 2: Local provider profiles

**Files:**
- Create: `starter_kit/l2_profiles.py`
- Test: `starter_kit/tests/l2/test_profiles.py`

- [ ] **Step 1: Write failing tests**

```python
def test_token_plan_profile_uses_compatible_url_and_dashscope_key(self):
    with mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}, clear=True):
        settings = local_settings("bailian-token-plan", model=None, base_url=None)
    self.assertEqual(settings["LOOMQ_LLM_BASE_URL"],
        "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1")
    self.assertEqual(settings["LOOMQ_LLM_MODEL"], "qwen3.8-max")
    self.assertEqual(settings["LOOMQ_LLM_API_KEY"], "test-key")

def test_custom_profile_requires_url_and_model(self):
    with self.assertRaisesRegex(L2ConfigurationError, "--base-url"):
        local_settings("custom", model=None, base_url=None)

def test_temporary_environment_restores_formal_values(self):
    with mock.patch.dict(os.environ, {"LOOMQ_LLM_BASE_URL": "https://judge.test/v1"}, clear=True):
        with temporary_environment({"LOOMQ_LLM_BASE_URL": "https://local.test/v1"}):
            self.assertEqual(os.environ["LOOMQ_LLM_BASE_URL"], "https://local.test/v1")
        self.assertEqual(os.environ["LOOMQ_LLM_BASE_URL"], "https://judge.test/v1")
```

- [ ] **Step 2: Verify tests fail**

Run:

```powershell
& 'C:\Users\lixin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest starter_kit.tests.l2.test_profiles -v
```

Expected: FAIL because `l2_profiles` does not exist.

- [ ] **Step 3: Implement explicit local presets**

Create immutable `ProviderProfile(name, base_url, default_model, key_environment)` entries:

```python
"bailian-token-plan": ("https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1", "qwen3.8-max", "DASHSCOPE_API_KEY")
"bailian-dashscope": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus", "DASHSCOPE_API_KEY")
"openai": ("https://api.openai.com/v1", None, "OPENAI_API_KEY")
"deepseek": ("https://api.deepseek.com/v1", None, "DEEPSEEK_API_KEY")
"custom": (None, None, "LOOMQ_LLM_API_KEY")
```

`local_settings(provider, model, base_url)` must require the selected key environment variable, apply explicit CLI URL/model overrides, and return only the three `LOOMQ_LLM_*` values. `temporary_environment` must restore values on success and exceptions. Neither `adapter.py` nor `loomq_l2.py` imports this local-only module.

- [ ] **Step 4: Verify and commit**

Run:

```powershell
& 'C:\Users\lixin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest starter_kit.tests.l2.test_profiles starter_kit.tests.l2.test_agent -v
git add starter_kit/l2_profiles.py starter_kit/tests/l2/test_profiles.py
git commit -m "feat: add local L2 provider profiles"
```

Expected: tests PASS.

### Task 3: Semantic model-probe core

**Files:**
- Create: `starter_kit/l2_probe.py`
- Test: `starter_kit/tests/l2/test_probe.py`

- [ ] **Step 1: Write failing tests**

```python
def test_parseable_non_entangled_ghz_reply_fails(self):
    result = validate_generation_reply(
        'OPENQASM 2.0; include "qelib1.inc"; qreg q[3]; creg c[3]; h q[0]; measure q -> c;'
    )
    self.assertFalse(result.passed)
    self.assertIn("expected probability", result.reason)

def test_semantic_bell_repair_passes(self):
    reply = ('OPENQASM 2.0; include "qelib1.inc"; qreg q[2]; creg c[2]; '
             'h q[0]; cx q[0],q[1]; measure q -> c;')
    self.assertTrue(validate_repair_reply(reply).passed)

def test_backend_accepts_every_matching_capability_id(self):
    self.assertTrue(validate_backend_reply("originq_local_simulator").passed)

def test_probe_continues_after_first_model_failure(self):
    report = probe_models(("bad", "good"), mock.Mock(side_effect=[
        L2TransportError("x.test", 1), GHZ_REPLY, BELL_REPLY, "braket_local_simulator",
    ]))
    self.assertEqual(report.models[0].passed_tasks, 0)
    self.assertEqual(report.models[1].passed_tasks, 3)
```

- [ ] **Step 2: Verify tests fail**

Run:

```powershell
& 'C:\Users\lixin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest starter_kit.tests.l2.test_probe -v
```

Expected: FAIL because `l2_probe` does not exist.

- [ ] **Step 3: Implement the three manual task families**

Create `ProbeCase`, `TaskResult`, `ModelResult`, and `ProbeReport` dataclasses. Define exactly three local tasks: 3-bit GHZ generation, malformed Bell repair, and 15-bit/free/zero-queue backend selection.

Use `parse_qasm` and a standard-library statevector that supports only `h`, `x`, and `cx`; reject unsupported gates in probe validation. Require GHZ probabilities `000=0.5`, `111=0.5`; require Bell probabilities `00=0.5`, `11=0.5`; tolerance is `1e-12`. Load `backend_capabilities.json` and accept every ID with `max_qubits >= 15`, `queue == "none"`, and `cost == "free"`.

`probe_models(models, invoke)` runs every case per model, times each call with `time.monotonic()`, records typed error category/reason, and continues after a failure. JSON report data comes only from dataclasses; it contains no environment values.

- [ ] **Step 4: Verify and commit**

Run:

```powershell
& 'C:\Users\lixin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest starter_kit.tests.l2.test_probe starter_kit.tests.l2.test_agent -v
git add starter_kit/l2_probe.py starter_kit/tests/l2/test_probe.py
git commit -m "feat: add semantic L2 model probes"
```

Expected: tests PASS.

### Task 4: CLI, repair feedback, and documentation

**Files:**
- Modify: `starter_kit/l2_cli.py`, `starter_kit/loomq_l2.py`
- Modify: `starter_kit/tests/l2/test_agent.py`, `starter_kit/tests/l2/test_cli.py`
- Modify: `starter_kit/README.md`, `starter_kit/evidence/README.md`

- [ ] **Step 1: Write failing CLI tests**

```python
def test_validation_reason_is_in_the_single_repair_prompt(self):
    with mock.patch("starter_kit.llm_client.chat_completion",
                    side_effect=[completion("not qasm"), completion(GHZ_QASM)]) as chat:
        adapter.agent_chat("生成 GHZ")
    self.assertIn("reply must contain valid OpenQASM", chat.call_args_list[1].args[0][-1]["content"])

def test_api_429_shows_request_id_and_retry_guidance(self):
    code, stderr = run_cli_with(L2ApiError(429, "api.example.test", "req-123"))
    self.assertEqual(code, 2)
    self.assertIn("HTTP 429", stderr)
    self.assertIn("req-123", stderr)
    self.assertIn("稍后重试", stderr)

def test_probe_is_dry_run_without_execute(self):
    code, stdout = run_cli(["--probe", "--provider", "bailian-token-plan", "--model", "qwen3.8-max"])
    self.assertEqual(code, 0)
    self.assertIn("dry_run", stdout)
```

- [ ] **Step 2: Verify tests fail**

Run:

```powershell
& 'C:\Users\lixin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest starter_kit.tests.l2.test_agent starter_kit.tests.l2.test_cli -v
```

Expected: FAIL because typed rendering and probe options are absent.

- [ ] **Step 3: Implement command behavior**

Add `--provider`, `--base-url`, repeatable `--model`, `--models-file`, `--probe`, `--all`, `--execute`, and `--json`. Without `--provider`, normal prompt mode must call `agent_chat` exactly as before. With `--provider`, build local settings, enter `temporary_environment`, then call the same `agent_chat`.

Render these exact safe actions:

```text
configuration: 检查并设置 <variable>，然后重新运行。
transport: 无法在 <seconds>s 内连接 <host>；检查网络或端点后重试。
api 401/403: 服务拒绝凭据；检查该服务商的 Key 权限后重试。
api 429: 服务限流；请稍后重试。
api other: 服务返回 HTTP <status>；保留 request_id 后联系服务商或更换模型。
validation: 模型输出未通过本地校验：<reason>；请重试，或改写任务并保留目标态和测量要求。
```

Replace the final generic error in `loomq_l2.agent_chat` with `L2ValidationError`, preserving one initial call plus at most one repair. Probe mode reads UTF-8 non-empty/non-comment model lines plus repeated `--model`; it refuses `--all` without a supplied model; it prints dry-run JSON until `--execute`; execution prints redacted JSON and writes no file by default.

- [ ] **Step 4: Document, verify, and commit**

Document the formal-versus-local boundary, Token Plan endpoint, all three probe tasks, dry-run billing safeguard, and safe error recovery. Do not present local logs as official proof.

Run:

```powershell
& 'C:\Users\lixin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s starter_kit/tests/l2 -v
& 'C:\Users\lixin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile starter_kit/l2_errors.py starter_kit/l2_profiles.py starter_kit/l2_probe.py starter_kit/llm_client.py starter_kit/loomq_l2.py starter_kit/l2_cli.py
git add starter_kit/l2_cli.py starter_kit/loomq_l2.py starter_kit/tests/l2 starter_kit/README.md starter_kit/evidence/README.md
git commit -m "feat: add guided L2 provider workflow"
```

Expected: all tests PASS and compilation has no output.

### Task 5: Bounded live execution

**Files:** no tracked credential or transcript files.

- [ ] **Step 1: Dry-run the user-supplied candidate list**

```powershell
python -m starter_kit.l2_cli --probe --provider bailian-token-plan --models-file models.txt --all --json
```

Show the exact model count and `3 × model_count` paid calls.

- [ ] **Step 2: Obtain confirmation before billing and execute**

```powershell
python -m starter_kit.l2_cli --probe --execute --provider bailian-token-plan --models-file models.txt --all --json
```

Do not infer account entitlement from a global catalog; do not save the API key, authorization header, or raw provider metadata.

## Plan self-review

- Spec coverage: Tasks 1/4 implement precise safe errors; Task 2 isolates local profiles; Task 3 covers generation, repair, and backend semantics; Task 5 bounds external cost.
- Placeholder scan: no unfinished markers or unspecified test command remains.
- Type consistency: every later use of `L2ConfigurationError`, `L2TransportError`, `L2ApiError`, `L2ValidationError`, `local_settings`, `temporary_environment`, and `probe_models` is defined in an earlier task.
