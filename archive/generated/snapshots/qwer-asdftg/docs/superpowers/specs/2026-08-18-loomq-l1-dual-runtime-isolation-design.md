# LoomQ L1 dual-runtime dependency isolation

## Context

The mandated direct pins cannot be installed into one Python environment:

- `spinqit==0.2.4` requires `antlr4-python3-runtime==4.9.2`.
- `amazon-braket-sdk==1.108.0` resolves `amazon-braket-default-simulator`, which requires `antlr4-python3-runtime==4.13.2`.

Python 3.10 `pip` reports this as `ResolutionImpossible`.  The submission must still keep all four direct pins, support all three L1 local simulators, and expose the unchanged `adapter.transpile()` and `adapter.run()` contract.

## Decision

Build one Python 3.10 Docker image with two isolated runtimes:

1. The image's primary interpreter installs `numpy==1.26.4`, `pyqpanda==3.8.5`, and `spinqit==0.2.4`.  It runs the adapter, parser, emitters, SpinQ runner, and OriginQ runner directly.
2. `/opt/loomq-braket-venv` is a Python 3.10 virtual environment that installs `numpy==1.26.4` and `amazon-braket-sdk==1.108.0`.  It owns the incompatible ANTLR 4.13.2 runtime and runs Braket's local simulator.
3. The Docker image sets `LOOMQ_BRAKET_PYTHON=/opt/loomq-braket-venv/bin/python`.  Outside that image, the Braket runner retains its lazy in-process import path for unit tests and ordinary compatible installations.

The public dependency declaration remains exactly:

```text
amazon-braket-sdk==1.108.0
numpy==1.26.4
pyqpanda==3.8.5
spinqit==0.2.4
```

## Runtime protocol

When `LOOMQ_BRAKET_PYTHON` is set, the parent Braket runner serializes only `native_ir` and `shots` as JSON on standard input to a small internal worker executed by that interpreter.  The worker:

1. Creates `braket.ir.openqasm.Program` from the emitted OpenQASM 3 source.
2. Executes it with `braket.devices.LocalSimulator`.
3. Returns JSON-safe raw counts, a provider/local job ID, and SDK version metadata on standard output.

The parent validates the worker response and returns the same `RawExecution` shape as the direct runner.  It never sends environment variables, credentials, or cloud-device identifiers to the worker.  Timeouts, malformed JSON, a nonzero child exit, and invalid result shapes become `ProviderExecutionError` with a safe message.

## Boundary and compatibility rules

- This is local-simulator only.  It does not submit cloud or QPU jobs.
- SpinQ and OriginQ remain direct calls, matching the authoritative starter-kit examples.
- Braket's `reverse_bits` remains determined only by the existing real asymmetric Python 3.10 integration test.  The isolation layer may not hard-code a circuit-specific transformation.
- The adapter interface, target names, output schema, and declared dependency versions do not change.
- The normal host test suite still imports provider SDKs lazily and skips integration tests when the matching real SDK is absent.

## Verification

The implementation must prove all of the following in the rebuilt Docker image:

1. Both interpreters are Python 3.10 and expose their pinned provider SDK version.
2. `adapter.run()` on the asymmetric `x q[0]` two-qubit circuit returns only canonical `"01"` for all three targets; any provider reversal is changed once in its runner and rechecked.
3. A valid circuit containing all twelve whitelist gates transpiles and runs on all three local simulators; every result passes `evaluator.validate_schema` and totals 256 shots.
4. The documented L1 evaluator runs from the image.
5. Unit tests cover worker payload validation, safe child failure handling, and no credential forwarding.

## Rejected alternatives

- A single shared environment with `--no-deps` or forced ANTLR replacement: generated parser code can become runtime-incompatible.
- Separate submission images: the contest uses one Docker submission artifact.
- Changing the mandated provider versions: violates the target contract.
