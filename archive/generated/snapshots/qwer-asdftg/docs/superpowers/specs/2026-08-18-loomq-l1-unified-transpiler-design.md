# LoomQ L1 Unified Transpiler Design

## Objective

Build the complete LoomQ L1 submission on top of Starter Kit v1.1.0. One parser and one canonical circuit model will drive all three required targets (`spinq`, `originq`, and `braket`). The submission must pass the public evaluator for all three local simulators, remain robust against hidden Bell/GHZ/QFT/Grover/random circuits that use the 12-gate whitelist, and provide a separate credential-safe path for collecting real-QPU evidence later.

## Scope

Included:

- Implement `transpile(qasm_str, target)` and `run(qasm_str, target, shots)` in `starter_kit/adapter.py`.
- Parse the contest's OpenQASM 2.0 subset into a provider-neutral internal representation.
- Emit complete OpenQASM 2.0 for SpinQ, OriginIR for OriginQ, and OpenQASM 3.0 for Braket.
- Execute the emitted artifacts on SpinQit BasicSimulator, pyQPanda CPUQVM, and Amazon Braket LocalSimulator.
- Normalize all provider results to the contest schema and little-endian classical bit-string convention.
- Test all 12 whitelisted gates, public circuits, hidden-style circuits, malformed inputs, measurement mappings, and result normalization.
- Provide explicit QPU commands that read credentials only from environment variables and save evidence under `starter_kit/evidence/files/`.
- Pin Python 3.10-compatible dependencies and validate the official Docker workflow.

Excluded:

- L2 `agent_chat` and any UI.
- L3 `compile_hybrid`.
- Automatic account registration, credential storage, or paid cloud execution.
- Claims that a real-QPU path is verified before an actual account, job ID, and raw provider response exist.

## Chosen Approach

Use a lightweight parser and canonical circuit IR, followed by target-specific emitters and runners.

Rejected alternatives:

- Qiskit as the central IR adds a large dependency and version surface while still requiring a custom OriginIR emitter.
- Three independent provider branches are faster initially but duplicate parsing and gate semantics, weaken hidden-test reliability, and do not demonstrate a genuinely unified middleware layer.
- Regex-only source rewriting is too fragile for comments, whitespace, parameter expressions, register-wide measurements, bounds checks, and hidden test variants.

## Architecture

```text
OpenQASM 2.0 source
        |
        v
Lexer/parser + semantic validation
        |
        v
Canonical Circuit IR
        |
        +--> SpinQ emitter   --> OpenQASM 2.0 --> SpinQit BasicSimulator
        +--> OriginQ emitter --> OriginIR      --> pyQPanda CPUQVM
        +--> Braket emitter  --> OpenQASM 3.0 --> Braket LocalSimulator
                                                     |
                                                     v
                              Provider result normalization
                                                     |
                                                     v
                                  LoomQ unified result schema
```

`starter_kit/adapter.py` remains a thin contract facade. Parsing, emitting, execution, and normalization live in focused modules so the same semantics are reused by every target.

## File Responsibilities

```text
starter_kit/
|-- adapter.py
|-- requirements.txt
|-- submission.yaml
|-- loomq_l1/
|   |-- __init__.py
|   |-- errors.py
|   |-- model.py
|   |-- expressions.py
|   |-- parser.py
|   |-- normalize.py
|   |-- emitters/
|   |   |-- __init__.py
|   |   |-- spinq.py
|   |   |-- originq.py
|   |   `-- braket.py
|   `-- runners/
|       |-- __init__.py
|       |-- spinq.py
|       |-- originq.py
|       `-- braket.py
|-- hardware/
|   |-- __init__.py
|   `-- run_qpu.py
`-- tests/
    `-- l1/
        |-- support/
        |   |-- circuit_factory.py
        |   `-- reference_simulator.py
        |-- test_expressions.py
        |-- test_parser.py
        |-- test_emitters.py
        |-- test_normalize.py
        |-- test_adapter_contract.py
        |-- test_hidden_style_circuits.py
        `-- test_hardware_cli.py
```

`errors.py` defines stable, user-facing exception types. `model.py` owns immutable circuit, register, operation, and measurement records. `expressions.py` evaluates the restricted arithmetic used by gate parameters. `parser.py` performs syntactic and semantic validation. Emitters contain formatting only. Runners contain SDK calls only. `normalize.py` is the sole authority for result bit ordering and schema construction.

## Supported Input Language

The parser accepts the contest subset of OpenQASM 2.0:

- Required `OPENQASM 2.0;` declaration.
- Required `include "qelib1.inc";` declaration.
- One or more `qreg` and `creg` declarations with positive sizes.
- Gate calls from `h`, `x`, `s`, `sdg`, `t`, `tdg`, `rz`, `ry`, `cx`, `cu1`, `swap`, and `ccx`.
- Parameter expressions containing decimal/integer literals, `pi`, unary `+`/`-`, parentheses, and `+`, `-`, `*`, `/`.
- Bit-level measurement (`measure q[0] -> c[0];`) and equal-width whole-register measurement (`measure q -> c;`). Whole-register measurement is expanded to explicit bit pairs in the IR.
- Line comments, block comments, arbitrary whitespace, and multiple statements per line.

Semantic validation rejects duplicate registers, zero-sized registers, unknown registers, out-of-range indices, wrong gate arity, missing/wrong parameter counts, unsupported gates, unequal register-wide measurements, duplicate measurement destinations, gates placed after the first measurement, non-finite parameters, and division by zero.

The expression evaluator is implemented with a purpose-built tokenizer/parser. It does not use Python `eval` or execute input text.

## Canonical Circuit IR

The IR stores:

- Ordered quantum and classical register declarations.
- A deterministic global index for each register bit.
- Ordered gate operations with canonical lowercase names, evaluated floating-point parameters, and global qubit indices.
- Ordered measurements from global qubit indices to global classical bit indices.

Gate validation happens before an operation enters the IR. Emitters therefore never need to reinterpret source syntax or infer operand meaning.

## Target Emission

### SpinQ

Emit complete, normalized OpenQASM 2.0 with `qelib1.inc`, canonical register declarations, the 12-gate whitelist, and explicit per-bit measurements. No source text is passed through unchecked.

### OriginQ

Emit `QINIT`, `CREG`, uppercase OriginIR gate names, numeric parameters, and explicit `MEASURE` statements. Map `cx` to `CNOT`, `sdg` to `SDAG`, `tdg` to `TDAG`, and `ccx` to `TOFFOLI`. Use the target contract's accepted `CU1` spelling.

### Braket

Emit complete OpenQASM 3.0 with `stdgates.inc`, `qubit[n]`, `bit[n]`, numeric parameters, and explicit per-bit measurement assignments. Map `cx` to `cnot` and OpenQASM 2.0 `cu1` to the OpenQASM 3 standard controlled-phase spelling `cp`; preserve the remaining accepted standard-gate names.

All emitters produce deterministic text so syntax snapshots and failure reports are reproducible.

## Local Execution

`run()` validates `shots` as a positive integer, parses once, emits the selected native artifact, executes that artifact, and normalizes the result. Unsupported targets fail before importing provider SDKs.

- SpinQ uses `spinqit==0.2.4` and its QASM compiler plus BasicSimulator.
- OriginQ uses `pyqpanda==3.8.5`, writes the emitted OriginIR to a securely created temporary file, and loads that same artifact into CPUQVM through `convert_originir_to_qprog(file_path, machine)`. The temporary file is removed in a `finally` block after import.
- Braket uses `amazon-braket-sdk==1.108.0`, selected because it supports Python 3.10, and executes the emitted OpenQASM 3 program on `LocalSimulator`.

Provider imports are lazy so parser/emitter tests run without all SDKs installed and missing dependencies produce actionable errors rather than import-time crashes.

## Result Normalization

Every result contains:

- A canonical local backend ID.
- A non-mock local job ID derived from provider metadata when available, otherwise a UUID-based local execution ID.
- The requested positive `shots` value.
- Non-empty integer `counts` whose values sum exactly to `shots`.
- Bit strings padded to the total classical register width.
- Bit strings ordered as `c[n-1]...c[1]c[0]`, with `bit_order` fixed to `little`.
- A current UTC ISO-8601 timestamp.
- Metadata including target, emitted gate count, circuit depth where available, and provider SDK version.

Normalization accepts integer keys, decimal strings, binary strings, spaced bit strings, and provider-specific bit ordering only through explicit runner metadata. It never guesses ordering silently.

## Hidden-Test Strategy

Tests are written before production code. Each behavior is observed failing before the minimal implementation is added.

The test suite includes:

- Public Bell and GHZ-3 circuits.
- GHZ-5, QFT-4, Grover-3, and deterministic random circuits.
- Individual and composed tests for every whitelisted gate.
- Parameter expressions such as `pi/2`, `-pi/4`, nested parentheses, and decimal values.
- Whole-register and permuted bit-level measurements.
- Invalid syntax and semantic failures.
- Exact emitter syntax assertions for all three target contracts.
- A small test-only statevector reference simulator for the 12-gate whitelist.
- Distribution comparisons between each local provider and the reference probabilities at 8192 shots.
- A Hellinger fidelity threshold of at least 0.97, matching the official evaluator.
- Result schema checks identical to the public contract.

Random circuits use fixed test seeds for reproducibility. Tests do not encode expected answers for official public prompts or attempt to infer organizer hidden seeds.

## Real-QPU Preparation

Real-QPU execution is separate from `adapter.run()` so the offline evaluator never attempts network access.

`starter_kit.hardware.run_qpu` will:

- Require an explicit provider, input circuit, shots, and output directory.
- Read SpinQ, OriginQ, or AWS credentials from documented environment variables.
- Support `--dry-run` to parse, validate, emit, and display a redacted submission summary without contacting a provider.
- Refuse non-dry execution when credentials are missing.
- Import an account-generated raw provider result only after validating its job ID, timestamp, shots, counts, and provider identity.
- Save the exact submitted source/native IR, provider raw result, normalized result, job ID, backend ID, shots, and UTC timestamps under `starter_kit/evidence/files/`.
- Never log credential values or write credentials to files.

SpinQ and OriginQ are the first account targets; AWS cloud QPU support remains available but is not required because it is paid. With no account or stable account-specific cloud API contract available during implementation, the tool does not make speculative automatic QPU submissions. It prepares validated native artifacts and imports the raw result produced later through the provider console or account-specific SDK. Tests cover argument validation, result validation, redaction, dry-run behavior, evidence bundling, and safe missing-credential failures.

## Dependency and Environment Policy

The official build target is Python 3.10. Dependencies are exactly pinned:

```text
spinqit==0.2.4
pyqpanda==3.8.5
amazon-braket-sdk==1.108.0
numpy==1.26.4
```

The exact transitive resolution will be captured during the dependency compatibility test. No unpinned `>=` requirements are accepted. The host Docker client is installed, but the Docker daemon was not running during design; container verification occurs after Docker Desktop is started.

## Error Handling

Errors are categorized as parse, semantic, target, dependency, provider execution, normalization, or credential errors. Messages identify the statement or provider involved without exposing secrets. Provider exceptions are wrapped with stable LoomQ context while preserving the original exception as the Python cause.

No failure path returns fabricated counts, placeholder IR, `is_mock: true`, or a fake hardware job ID.

## Acceptance Criteria

The implementation is accepted only when fresh verification shows:

1. The official public evaluator passes Bell and GHZ-3 for `spinq`, `originq`, and `braket`.
2. Unit and integration tests cover all 12 gates and all documented parser/normalization errors.
3. GHZ-5, QFT-4, Grover-3, and deterministic random circuits reach Hellinger fidelity >= 0.97 on all three local simulators.
4. `transpile()` outputs parseable target-contract artifacts whose distributions match the input circuit.
5. The Python 3.10 Docker image builds and runs the declared L1 evaluator successfully.
6. `submission.yaml` enables L1 only and declares no L1 network requirement.
7. Repository scans find no API keys, tokens, cookies, or credentials.
8. The QPU CLI passes dry-run, redaction, and missing-credential tests, while its unverified real-provider status is documented honestly.

## Delivery and Version Control

Development occurs on the local `feat/loomq-l1-unified-transpiler` branch. Changes are committed in small test-driven increments. Nothing is pushed and no GitHub fork, issue, account, or paid job is created without separate user authorization.
