# OriginQ QCloud QPU runbook

This path is audited against the public pyqpanda3 **0.4.0** QCloud API.  It uses:

1. `convert_qasm_string_to_qprog(qasm)`;
2. `QCloudService(api_key).backends()` and `.backend(name)`;
3. QPU-only `QCloudBackend.chip_info()`;
4. `QCloudBackend.run(QProg, shots)`;
5. `QCloudJob.job_id()` / `.result()`; and
6. `QCloudResult.get_counts(base=DataBase.Binary)` / `.origin_data()`.

The loader refuses any installed pyqpanda3 version other than `0.4.0`, so an API
change cannot be mistaken for a tested integration.

## 1. Isolated environment

From `starter_kit/`:

```powershell
py -3.10 -m venv .venv-originq-hardware
.\.venv-originq-hardware\Scripts\python.exe -m pip install pyqpanda3==0.4.0
```

This dependency stays outside the main `requirements.txt`.

## 2. Prepare QASM and dry-run

OriginQ's documented converter accepts OpenQASM 2.0.  Use a complete program,
including final measurements:

```powershell
.\.venv-originq-hardware\Scripts\python.exe scripts\hardware\run_originq.py `
  --qasm circuits\bell.qasm `
  --shots 1000 `
  --backend <candidate-real-qpu-backend> `
  --dry-run
```

Dry-run performs no SDK import, credential read, network call, or evidence write,
and emits no `job_id`.

## 3. Credentials and backend

Create an OriginQ Cloud account/API key and determine a currently available real
QPU from `QCloudService(...).backends()` or the authenticated console.  Do not
hard-code an example backend without checking live availability.

```powershell
$env:QPANDA_QCLOUD_API_KEY = '<api-key>'
$env:QPANDA_QCLOUD_BACKEND = '<live-real-qpu-backend>'
```

Only if your account instructions require an explicit service endpoint:

```powershell
$env:QPANDA_QCLOUD_URL = '<absolute-http-or-https-service-url>'
```

The URL may not contain embedded username/password credentials.

## 4. Submit and record

```powershell
.\.venv-originq-hardware\Scripts\python.exe scripts\hardware\run_originq.py `
  --qasm circuits\bell.qasm `
  --shots 1000 `
  --record
```

The runner requires the selected backend to be live in `backends()`.  It then
calls `chip_info()` and requires non-empty `chip_id()` plus positive
`qubits_num()`.  The 0.4.0 documentation states that `chip_info()` is available
only for real QPU backends and raises on cloud simulators, making this a stronger
qualification than a backend-name allowlist.

Evidence is committed only when a vendor job ID exists, the result carries the
same job ID, the result has no error message, and binary counts sum exactly to
the requested shots.

Clear credentials after the run:

```powershell
Remove-Item Env:QPANDA_QCLOUD_API_KEY
Remove-Item Env:QPANDA_QCLOUD_BACKEND
Remove-Item Env:QPANDA_QCLOUD_URL -ErrorAction SilentlyContinue
```

## Expected external blockers

- No API key/backend: fail before SDK import/network; no job ID.
- Wrong pyqpanda3 version: fail before service creation.
- Unavailable backend or simulator: fail before submission.
- Account permission/quota/network/queue error: safe message without raw exception
  or credential value; incomplete responses are not recorded.
