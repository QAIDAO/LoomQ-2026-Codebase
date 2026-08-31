# SpinQ Cloud QPU runbook

The implementation uses the public functions in
`spinqit_mcp_tools.qasm_submitter`: `get_platforms()`, `qasm_submit(...)`, and
`get_task_result_by_id(...)`.  The audited package metadata is version `0.0.2`.
Its QASM submitter fixes the task at **1000 shots**, rejects explicit `measure`
statements, and performs final measurement on the cloud.  The LoomQ runner
therefore rejects other shot values instead of silently changing them.

## 1. Isolated environment

From `starter_kit/`, create a dedicated Python 3.10 environment; do not add the
vendor package to the main application requirements.

```powershell
py -3.10 -m venv .venv-spinq-hardware
.\.venv-spinq-hardware\Scripts\python.exe -m pip install spinqit_mcp_tools==0.0.2
```

The official package declares `mcp>=1.8.1`, `pycryptodome`, and
`spinqit>=0.2.4`; installing `spinqit_mcp_tools==0.0.2` resolves them inside this
isolated environment.

## 2. Prepare QASM

Use complete OpenQASM 2 without comments, backslash escaping, classical
measurement declarations, or explicit `measure` operations:

```qasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
cx q[0],q[1];
```

The same circuit is provided at
`docs/hardware/examples/spinq_bell_no_measure.qasm`.  Do not put credentials in
the file or task name.

## 3. Dry run

Dry-run needs no account and cannot submit:

```powershell
.\.venv-spinq-hardware\Scripts\python.exe scripts\hardware\run_spinq.py `
  --qasm docs\hardware\examples\spinq_bell_no_measure.qasm `
  --shots 1000 `
  --platform-code <candidate-platform-code> `
  --dry-run
```

The JSON output must say `network_called: false`, `vendor_imported: false`, and
`evidence_written: false`; it deliberately has no `job_id`.

## 4. Credentials and live platform selection

Register at SpinQ Cloud, configure the public key in the account, and point the
runner at the corresponding private-key file.  Set the three official variables
only in the current shell:

```powershell
$env:PRIVATEKEYPATH = '<absolute-private-key-path>'
$env:SPINQCLOUDUSERNAME = '<cloud-username>'
$env:SPINQCLOUDHOST = '<SpinQ-Cloud-host-from-your-account>'
```

Use the official `get_platforms` tool to obtain the live `pcode`.  The runner
will independently rediscover it and proceeds only when that exact item reports:

- `simu` is the Boolean `false`; and
- `countOnlineMachine` is a positive integer.

Do not infer QPU status from a platform name.  `simulator` and any platform that
does not provide the explicit live flags are rejected.

## 5. Submit and record

```powershell
.\.venv-spinq-hardware\Scripts\python.exe scripts\hardware\run_spinq.py `
  --qasm docs\hardware\examples\spinq_bell_no_measure.qasm `
  --shots 1000 `
  --platform-code <live-qpu-pcode> `
  --task-name loomq-hardware-evidence `
  --timeout 600 `
  --poll-interval 5 `
  --record
```

The runner accepts only an HTTP/API success response containing the vendor field
`task.tcode`, then polls for a terminal response containing `run.count` and a
matching `shots=1000`.  Only then is a directory created under
`evidence/files/hardware/`.

Clear the shell variables after the run:

```powershell
Remove-Item Env:PRIVATEKEYPATH
Remove-Item Env:SPINQCLOUDUSERNAME
Remove-Item Env:SPINQCLOUDHOST
```

## Expected external blockers

- Missing or unreadable private-key file: fail before vendor import/network.
- Platform absent, simulator, or no online machine: fail before submission.
- Account permissions/quota/network/vendor queue: safe error, no evidence bundle.
- Poll timeout or incomplete counts: no evidence bundle; inspect the job in the
  authenticated vendor console using the returned vendor task history.
