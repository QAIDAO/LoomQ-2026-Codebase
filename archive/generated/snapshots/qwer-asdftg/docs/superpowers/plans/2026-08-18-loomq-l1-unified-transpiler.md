# LoomQ L1 Unified Transpiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python 3.10-compatible LoomQ L1 submission that parses the contest OpenQASM 2.0 subset once, emits all three target IRs, executes all three local simulators, survives hidden-style circuits, and prepares credential-safe real-QPU evidence collection.

**Architecture:** `starter_kit/adapter.py` is a thin facade over a provider-neutral `Circuit` IR. A safe expression parser and OpenQASM parser produce the IR; deterministic emitters produce SpinQ OpenQASM 2.0, OriginIR, and Braket OpenQASM 3.0; provider runners return raw execution records that one normalization module converts to the official schema.

**Tech Stack:** Python 3.10, standard-library `unittest`, NumPy 1.26.4 for test-only statevector validation, SpinQit 0.2.4, pyQPanda 3.8.5, Amazon Braket SDK 1.108.0, Docker.

---

## File Map

- `starter_kit/adapter.py`: official `transpile()` and `run()` facade.
- `starter_kit/loomq_l1/errors.py`: stable exception hierarchy.
- `starter_kit/loomq_l1/model.py`: immutable register, operation, measurement, circuit, and raw execution records.
- `starter_kit/loomq_l1/expressions.py`: safe arithmetic parser for gate parameters.
- `starter_kit/loomq_l1/parser.py`: OpenQASM 2.0 subset parser and semantic validator.
- `starter_kit/loomq_l1/emitters/*.py`: deterministic target IR generation.
- `starter_kit/loomq_l1/runners/*.py`: provider SDK integration only.
- `starter_kit/loomq_l1/normalize.py`: counts and result-schema normalization.
- `starter_kit/hardware/run_qpu.py`: dry-run and real-result evidence bundle CLI.
- `starter_kit/tests/l1/`: unit, contract, differential, and hidden-style tests retained inside the submitted directory.
- `starter_kit/requirements.txt`: exact Python 3.10-compatible dependency pins.
- `starter_kit/submission.yaml`: L1-only declaration with no L1 network requirement.
- `starter_kit/README.md`: setup, local execution, test, Docker, and hardware-evidence commands.

### Task 1: Create the L1 model and error vocabulary

**Files:**
- Create: `starter_kit/loomq_l1/__init__.py`
- Create: `starter_kit/loomq_l1/errors.py`
- Create: `starter_kit/loomq_l1/model.py`
- Create: `starter_kit/tests/__init__.py`
- Create: `starter_kit/tests/l1/__init__.py`
- Create: `starter_kit/tests/l1/test_model.py`

- [ ] **Step 1: Write the failing model test**

```python
import unittest

from starter_kit.loomq_l1.model import Circuit, Measurement, Operation, Register


class ModelTests(unittest.TestCase):
    def test_circuit_exposes_global_widths_and_depth_inputs(self):
        circuit = Circuit(
            qregs=(Register("qa", 2, 0), Register("qb", 1, 2)),
            cregs=(Register("c", 3, 0),),
            operations=(
                Operation("h", (0,)),
                Operation("cx", (0, 2)),
            ),
            measurements=(Measurement(0, 0), Measurement(2, 2)),
        )
        self.assertEqual(circuit.num_qubits, 3)
        self.assertEqual(circuit.num_clbits, 3)
        self.assertEqual(circuit.gate_count, 2)

    def test_register_rejects_non_positive_size(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            Register("q", 0, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m unittest starter_kit.tests.l1.test_model -v`

Expected: import failure for `starter_kit.loomq_l1.model`.

- [ ] **Step 3: Implement the immutable model and exceptions**

`errors.py` must define `LoomQError`, `QASMParseError`, `QASMSemanticError`, `ExpressionError`, `UnsupportedTargetError`, `DependencyUnavailableError`, `ProviderExecutionError`, `NormalizationError`, and `CredentialError`, each inheriting from `LoomQError` except the base.

`model.py` must define these exact records:

```python
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple


@dataclass(frozen=True)
class Register:
    name: str
    size: int
    offset: int

    def __post_init__(self) -> None:
        if self.size <= 0:
            raise ValueError("register size must be positive")
        if self.offset < 0:
            raise ValueError("register offset must be non-negative")


@dataclass(frozen=True)
class Operation:
    name: str
    qubits: Tuple[int, ...]
    parameter: Optional[float] = None


@dataclass(frozen=True)
class Measurement:
    qubit: int
    cbit: int


@dataclass(frozen=True)
class Circuit:
    qregs: Tuple[Register, ...]
    cregs: Tuple[Register, ...]
    operations: Tuple[Operation, ...]
    measurements: Tuple[Measurement, ...]

    @property
    def num_qubits(self) -> int:
        return sum(register.size for register in self.qregs)

    @property
    def num_clbits(self) -> int:
        return sum(register.size for register in self.cregs)

    @property
    def gate_count(self) -> int:
        return len(self.operations)


@dataclass(frozen=True)
class RawExecution:
    backend: str
    job_id: str
    counts: Mapping[Any, int]
    key_format: str = "binary"
    reverse_bits: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Run the model tests and verify GREEN**

Run: `python -m unittest starter_kit.tests.l1.test_model -v`

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add starter_kit/loomq_l1 starter_kit/tests
git commit -m "feat: add LoomQ L1 circuit model"
```

### Task 2: Implement safe parameter-expression evaluation

**Files:**
- Create: `starter_kit/loomq_l1/expressions.py`
- Create: `starter_kit/tests/l1/test_expressions.py`

- [ ] **Step 1: Write failing expression tests**

```python
import math
import unittest

from starter_kit.loomq_l1.errors import ExpressionError
from starter_kit.loomq_l1.expressions import evaluate_expression


class ExpressionTests(unittest.TestCase):
    def test_evaluates_contest_parameter_grammar(self):
        cases = {
            "pi/2": math.pi / 2,
            "-(pi/4)": -math.pi / 4,
            "2*(pi/8+0.25)": 2 * (math.pi / 8 + 0.25),
            ".5": 0.5,
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertAlmostEqual(evaluate_expression(source), expected)

    def test_rejects_code_and_non_finite_arithmetic(self):
        for source in ("__import__('os')", "1/0", "unknown+1"):
            with self.subTest(source=source):
                with self.assertRaises(ExpressionError):
                    evaluate_expression(source)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest starter_kit.tests.l1.test_expressions -v`

Expected: import failure for `evaluate_expression`.

- [ ] **Step 3: Implement a tokenizer and recursive-descent parser**

Implement tokens `NUMBER`, `PI`, `PLUS`, `MINUS`, `STAR`, `SLASH`, `LPAREN`, and `RPAREN`. Use the grammar:

```text
expression := term ((PLUS | MINUS) term)*
term       := unary ((STAR | SLASH) unary)*
unary      := (PLUS | MINUS) unary | primary
primary    := NUMBER | PI | LPAREN expression RPAREN
```

`evaluate_expression(source: str) -> float` must consume every token, reject every other character, convert `pi` to `math.pi`, reject division by zero, and reject non-finite results with `ExpressionError`. It must never call `eval`, `exec`, `ast.literal_eval`, or import user-provided names.

- [ ] **Step 4: Run and verify GREEN**

Run: `python -m unittest starter_kit.tests.l1.test_expressions -v`

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add starter_kit/loomq_l1/expressions.py starter_kit/tests/l1/test_expressions.py
git commit -m "feat: parse QASM parameter expressions safely"
```

### Task 3: Parse and validate the contest OpenQASM 2.0 subset

**Files:**
- Create: `starter_kit/loomq_l1/parser.py`
- Create: `starter_kit/tests/l1/test_parser.py`

- [ ] **Step 1: Write failing happy-path parser tests**

```python
import math
import unittest

from starter_kit.loomq_l1.parser import parse_qasm


ALL_GATES = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3]; creg c[3];
h q[0]; x q[1]; s q[0]; sdg q[0]; t q[1]; tdg q[1];
rz(pi/2) q[0]; ry(-pi/4) q[1];
cx q[0],q[1]; cu1(pi/3) q[1],q[2]; swap q[0],q[2]; ccx q[0],q[1],q[2];
measure q -> c;
"""


class ParserTests(unittest.TestCase):
    def test_parses_all_whitelisted_gates_and_expands_measurement(self):
        circuit = parse_qasm(ALL_GATES)
        self.assertEqual(circuit.num_qubits, 3)
        self.assertEqual(circuit.num_clbits, 3)
        self.assertEqual([op.name for op in circuit.operations], [
            "h", "x", "s", "sdg", "t", "tdg", "rz", "ry",
            "cx", "cu1", "swap", "ccx",
        ])
        self.assertAlmostEqual(circuit.operations[6].parameter, math.pi / 2)
        self.assertEqual([(m.qubit, m.cbit) for m in circuit.measurements], [(0, 0), (1, 1), (2, 2)])

    def test_flattens_multiple_registers_to_global_indices(self):
        circuit = parse_qasm("""OPENQASM 2.0; include "qelib1.inc";
            qreg left[1]; qreg right[2]; creg out[2];
            cx left[0], right[1]; measure right -> out;
        """)
        self.assertEqual(circuit.operations[0].qubits, (0, 2))
        self.assertEqual([(m.qubit, m.cbit) for m in circuit.measurements], [(1, 0), (2, 1)])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest starter_kit.tests.l1.test_parser.ParserTests.test_parses_all_whitelisted_gates_and_expands_measurement -v`

Expected: import failure for `parse_qasm`.

- [ ] **Step 3: Implement header, declaration, gate, operand, and measurement parsing**

Use these exact gate contracts:

```python
GATE_ARITY = {
    "h": 1, "x": 1, "s": 1, "sdg": 1, "t": 1, "tdg": 1,
    "rz": 1, "ry": 1, "cx": 2, "cu1": 2, "swap": 2, "ccx": 3,
}
PARAMETER_GATES = frozenset({"rz", "ry", "cu1"})
```

Implementation requirements:

1. Remove `//` and `/* ... */` comments before splitting semicolon-terminated statements.
2. Require exactly one `OPENQASM 2.0` declaration and one `include "qelib1.inc"` declaration before executable statements.
3. Assign monotonically increasing offsets independently to quantum and classical registers.
4. Resolve `name[index]` operands to global indices and report the full offending statement in errors.
5. Expand whole-register measurements into ordered `Measurement` records.
6. Mark the first measurement as the end of the gate section and reject every later gate.
7. Return immutable tuples in the `Circuit` record.

- [ ] **Step 4: Add failing semantic-error tests**

Add table-driven cases that assert `QASMParseError` or `QASMSemanticError` for: missing header, missing include, duplicate register, zero size, unknown gate, wrong gate arity, missing/excess parameter, unknown register, out-of-range index, unequal whole-register measurement, duplicate classical destination, gate after measurement, malformed expression, and unterminated statement.

- [ ] **Step 5: Run the new tests and verify RED for each missing validation**

Run: `python -m unittest starter_kit.tests.l1.test_parser -v`

Expected: happy-path tests pass and semantic-error tests fail until every listed validation exists.

- [ ] **Step 6: Implement the semantic validations**

Add one validation branch per failing case. Preserve `ExpressionError` as the cause of a `QASMSemanticError` that identifies the gate and parameter source.

- [ ] **Step 7: Run and verify GREEN**

Run: `python -m unittest starter_kit.tests.l1.test_parser -v`

Expected: all parser tests pass.

- [ ] **Step 8: Commit**

```bash
git add starter_kit/loomq_l1/parser.py starter_kit/tests/l1/test_parser.py
git commit -m "feat: parse LoomQ OpenQASM subset"
```

### Task 4: Emit deterministic native IR for all targets

**Files:**
- Create: `starter_kit/loomq_l1/emitters/__init__.py`
- Create: `starter_kit/loomq_l1/emitters/spinq.py`
- Create: `starter_kit/loomq_l1/emitters/originq.py`
- Create: `starter_kit/loomq_l1/emitters/braket.py`
- Create: `starter_kit/tests/l1/test_emitters.py`

- [ ] **Step 1: Write failing exact-output tests**

Parse a two-qubit circuit containing `h`, `sdg`, `tdg`, `cu1(pi/2)`, `cx`, `swap`, `ccx` on a three-qubit variant, and explicit measurements. Assert that:

```python
spinq = emit(circuit, "spinq")
self.assertIn("OPENQASM 2.0;", spinq)
self.assertIn("qreg q[3];", spinq)
self.assertIn("cu1(1.5707963267948966) q[0], q[1];", spinq)

originq = emit(circuit, "originq")
self.assertTrue(originq.startswith("QINIT 3\nCREG 3\n"))
self.assertIn("SDAG q[1]", originq)
self.assertIn("CU1 q[0], q[1], (1.5707963267948966)", originq)
self.assertIn("TOFFOLI q[0], q[1], q[2]", originq)

braket = emit(circuit, "braket")
self.assertIn("OPENQASM 3.0;", braket)
self.assertIn('include "stdgates.inc";', braket)
self.assertIn("cp(1.5707963267948966) q[0], q[1];", braket)
self.assertIn("cnot q[0], q[1];", braket)
self.assertIn("c[0] = measure q[0];", braket)
```

Also assert that `emit(circuit, "unknown")` raises `UnsupportedTargetError`.

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest starter_kit.tests.l1.test_emitters -v`

Expected: import failure for the emitters package.

- [ ] **Step 3: Implement the emitter dispatcher and three deterministic emitters**

Use `format(value, ".17g")` for finite parameters. Flatten all source registers to one `q` and one `c` register in emitted text. Use these target mappings:

```python
ORIGIN_NAMES = {
    "h": "H", "x": "X", "s": "S", "sdg": "SDAG", "t": "T",
    "tdg": "TDAG", "rz": "RZ", "ry": "RY", "cx": "CNOT",
    "cu1": "CU1", "swap": "SWAP", "ccx": "TOFFOLI",
}
BRAKET_NAMES = {"cx": "cnot", "cu1": "cp"}
```

Every emitter must end with a newline, preserve operation order, and emit explicit measurement statements.

- [ ] **Step 4: Run and verify GREEN**

Run: `python -m unittest starter_kit.tests.l1.test_emitters -v`

Expected: all emitter tests pass.

- [ ] **Step 5: Commit**

```bash
git add starter_kit/loomq_l1/emitters starter_kit/tests/l1/test_emitters.py
git commit -m "feat: emit three LoomQ target IRs"
```

### Task 5: Normalize provider counts and build the official result schema

**Files:**
- Create: `starter_kit/loomq_l1/normalize.py`
- Create: `starter_kit/tests/l1/test_normalize.py`

- [ ] **Step 1: Write failing normalization tests**

```python
import unittest
from datetime import datetime, timezone

from starter_kit.loomq_l1.model import RawExecution
from starter_kit.loomq_l1.normalize import build_result, normalize_counts


class NormalizeTests(unittest.TestCase):
    def test_normalizes_integer_decimal_and_spaced_binary_keys(self):
        self.assertEqual(normalize_counts({1: 3}, 3, "integer", False), {"001": 3})
        self.assertEqual(normalize_counts({"3": 2}, 3, "decimal", False), {"011": 2})
        self.assertEqual(normalize_counts({"0 1": 4}, 2, "binary", False), {"01": 4})

    def test_reverses_only_when_runner_declares_it(self):
        self.assertEqual(normalize_counts({"10": 5}, 2, "binary", True), {"01": 5})

    def test_builds_contract_schema(self):
        raw = RawExecution("spinq_basic_simulator", "job-1", {"00": 4, "11": 4})
        result = build_result(raw, width=2, shots=8, now=lambda: datetime(2026, 8, 18, tzinfo=timezone.utc))
        self.assertEqual(result["shots"], 8)
        self.assertEqual(result["bit_order"], "little")
        self.assertEqual(result["timestamp"], "2026-08-18T00:00:00+00:00")
```

Add failures for empty counts, negative/non-integer values, invalid keys, overflow beyond width, unsupported key format, and totals unequal to shots.

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest starter_kit.tests.l1.test_normalize -v`

Expected: import failure for `normalize_counts`.

- [ ] **Step 3: Implement explicit normalization**

`normalize_counts(raw_counts, width, key_format, reverse_bits)` must support only `binary`, `decimal`, and `integer`; strip spaces only for binary strings; convert to a zero-padded width; reverse only when requested; merge colliding normalized keys; and raise `NormalizationError` for every invalid condition.

`build_result(raw, width, shots, now=utc_now)` must call `normalize_counts`, require the normalized total to equal shots, set `bit_order` to `little`, copy metadata, and never add `is_mock`.

- [ ] **Step 4: Run and verify GREEN**

Run: `python -m unittest starter_kit.tests.l1.test_normalize -v`

Expected: all normalization tests pass.

- [ ] **Step 5: Commit**

```bash
git add starter_kit/loomq_l1/normalize.py starter_kit/tests/l1/test_normalize.py
git commit -m "feat: normalize LoomQ execution results"
```

### Task 6: Add provider runners with lazy SDK imports

**Files:**
- Create: `starter_kit/loomq_l1/runners/__init__.py`
- Create: `starter_kit/loomq_l1/runners/spinq.py`
- Create: `starter_kit/loomq_l1/runners/originq.py`
- Create: `starter_kit/loomq_l1/runners/braket.py`
- Create: `starter_kit/tests/l1/test_runners.py`
- Modify: `starter_kit/requirements.txt`

- [ ] **Step 1: Write failing dependency and fake-SDK tests**

For each runner, patch its private import helper to raise `ImportError` and assert `DependencyUnavailableError` names the exact package. Then inject a minimal fake SDK object and assert a `RawExecution` is returned with the expected backend ID, counts, key format, and bit-order declaration.

The fake OriginQ test must assert that the exact emitted OriginIR is written to a temporary file passed to `convert_originir_to_qprog`, and that the path no longer exists after the call. The fake SpinQ test must assert that the QASM compiler receives a temporary `.qasm` file. The fake Braket test must assert that `Program(source=native_ir)` is passed to `LocalSimulator.run(..., shots=shots)`.

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest starter_kit.tests.l1.test_runners -v`

Expected: import failures for the runner modules.

- [ ] **Step 3: Implement SpinQ runner**

Use `NamedTemporaryFile(mode="w", suffix=".qasm", delete=False, encoding="utf-8")`, `get_compiler("qasm")`, `compile(path, 0)`, `get_basic_simulator()`, `BasicSimulatorConfig.configure_shots(shots)`, and `engine.execute(ir, config)`. Remove the file in `finally`. Return backend `spinq_basic_simulator`, provider job/task ID when available, binary keys, and SDK metadata.

- [ ] **Step 4: Implement OriginQ runner**

Initialize `CPUQVM`, write OriginIR to a temporary `.ir` file, call `convert_originir_to_qprog(path, machine)`, execute `run_with_configuration(prog, cbit_list, shots)`, remove the file in `finally`, and finalize the machine in an outer `finally`. Return backend `originq_cpu_simulator`, binary keys, and SDK metadata.

- [ ] **Step 5: Implement Braket runner**

Create `braket.ir.openqasm.Program(source=native_ir)`, execute it on `braket.devices.LocalSimulator`, call `task.result()`, and return `measurement_counts`. Use task/result metadata for job ID. Declare the source bit order according to the asymmetric integration test in Task 8 rather than guessing.

- [ ] **Step 6: Pin direct dependencies**

Replace the example-only requirements file with:

```text
amazon-braket-sdk==1.108.0
numpy==1.26.4
pyqpanda==3.8.5
spinqit==0.2.4
```

- [ ] **Step 7: Run fake-SDK tests and verify GREEN**

Run: `python -m unittest starter_kit.tests.l1.test_runners -v`

Expected: all runner tests pass without requiring installed provider SDKs.

- [ ] **Step 8: Commit**

```bash
git add starter_kit/loomq_l1/runners starter_kit/tests/l1/test_runners.py starter_kit/requirements.txt
git commit -m "feat: execute LoomQ circuits on local providers"
```

### Task 7: Wire the official adapter contract

**Files:**
- Modify: `starter_kit/adapter.py`
- Create: `starter_kit/tests/l1/test_adapter_contract.py`

- [ ] **Step 1: Write failing adapter contract tests**

```python
import unittest
from unittest.mock import patch

from starter_kit import adapter
from starter_kit.loomq_l1.model import RawExecution


BELL = """OPENQASM 2.0; include "qelib1.inc";
qreg q[2]; creg c[2]; h q[0]; cx q[0],q[1]; measure q -> c;
"""


class AdapterContractTests(unittest.TestCase):
    def test_transpile_supports_all_targets(self):
        self.assertTrue(adapter.transpile(BELL, "spinq").startswith("OPENQASM 2.0;"))
        self.assertTrue(adapter.transpile(BELL, "originq").startswith("QINIT 2"))
        self.assertTrue(adapter.transpile(BELL, "braket").startswith("OPENQASM 3.0;"))

    def test_run_uses_native_artifact_and_normalizes_result(self):
        def fake_runner(circuit, native_ir, shots):
            self.assertTrue(native_ir.startswith("QINIT 2"))
            return RawExecution("originq_cpu_simulator", "job-7", {"00": 4, "11": 4})

        with patch.dict(adapter.RUNNERS, {"originq": fake_runner}):
            result = adapter.run(BELL, "originq", 8)
        self.assertEqual(result["counts"], {"00": 4, "11": 4})
        self.assertEqual(result["bit_order"], "little")


if __name__ == "__main__":
    unittest.main()
```

Add tests for unsupported targets, non-string QASM, Boolean/zero/negative shots, and preservation of `NotImplementedError` in L2/L3 functions.

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest starter_kit.tests.l1.test_adapter_contract -v`

Expected: current `NotImplementedError` failures.

- [ ] **Step 3: Implement the thin facade**

Define `EMITTERS` and `RUNNERS` dictionaries keyed by `spinq`, `originq`, and `braket`. `transpile()` validates input, calls `parse_qasm`, then the selected emitter. `run()` validates input and shots, parses once, emits once, invokes the selected runner, and calls `build_result` with `circuit.num_clbits`. Leave `agent_chat()` and `compile_hybrid()` unchanged.

- [ ] **Step 4: Run and verify GREEN**

Run: `python -m unittest starter_kit.tests.l1.test_adapter_contract -v`

Expected: all adapter contract tests pass.

- [ ] **Step 5: Commit**

```bash
git add starter_kit/adapter.py starter_kit/tests/l1/test_adapter_contract.py
git commit -m "feat: implement LoomQ L1 adapter contract"
```

### Task 8: Install SDKs and verify actual local backends and bit order

**Files:**
- Create: `starter_kit/tests/l1/test_provider_integration.py`
- Modify: runner bit-order flags only if the asymmetric test proves a provider requires reversal.

- [ ] **Step 1: Install pinned dependencies in a Python 3.10 environment**

Preferred command after Docker Desktop is running:

```bash
docker build -t loomq-l1-deps starter_kit
```

Do not use the host interpreter as a fallback. If Docker is unavailable, pause this integration task until Docker Desktop is running so the compatibility result is guaranteed to match Python 3.10.

Expected: all four direct pins resolve without changing versions.

- [ ] **Step 2: Write the asymmetric bit-order integration test**

Use a two-qubit circuit with only `x q[0]` and `measure q -> c`. For each provider, run 128 shots and assert the only normalized key is `01`, because the contract renders `c[1]c[0]` and `c[0] == 1`.

- [ ] **Step 3: Run and verify RED where provider ordering differs**

Run: `python -m unittest starter_kit.tests.l1.test_provider_integration.ProviderIntegrationTests.test_asymmetric_bit_order -v`

Expected: either all providers pass or a failing provider exposes its documented source ordering.

- [ ] **Step 4: Set the failing runner's explicit `reverse_bits` flag**

Change only that runner's `RawExecution(reverse_bits=...)` construction. Do not add circuit-specific conditions.

- [ ] **Step 5: Verify native parsing for all 12 gates**

Add one integration circuit that includes all 12 gates with valid operands and final measurement. For each target, call both `transpile()` and `run(..., shots=256)`; assert non-empty native IR, schema validity through `evaluator.validate_schema`, and counts totaling 256.

- [ ] **Step 6: Run integration tests and verify GREEN**

Run: `python -m unittest starter_kit.tests.l1.test_provider_integration -v`

Expected: SpinQ, OriginQ, and Braket tests pass with real local SDKs.

- [ ] **Step 7: Commit**

```bash
git add starter_kit/tests/l1/test_provider_integration.py starter_kit/loomq_l1/runners
git commit -m "test: verify three local LoomQ backends"
```

### Task 9: Add hidden-style differential tests and reference simulation

**Files:**
- Create: `starter_kit/tests/l1/support/__init__.py`
- Create: `starter_kit/tests/l1/support/circuit_factory.py`
- Create: `starter_kit/tests/l1/support/reference_simulator.py`
- Create: `starter_kit/tests/l1/test_hidden_style_circuits.py`

- [ ] **Step 1: Write failing reference-simulator gate tests**

For every whitelist gate, construct a small circuit and assert exact probabilities or equivalence against its known identity. Include `swap == 3*cx`, the documented `cu1` decomposition, and the documented `ccx` decomposition.

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest starter_kit.tests.l1.test_hidden_style_circuits.ReferenceSimulatorTests -v`

Expected: import failure for the support modules.

- [ ] **Step 3: Implement the test-only statevector simulator**

Use NumPy complex arrays with q0 as the least-significant basis bit. Implement matrix application for `h`, `x`, `s`, `sdg`, `t`, `tdg`, `rz`, and `ry`; controlled-index updates for `cx`, `cu1`, and `ccx`; and amplitude swaps for `swap`. Convert final basis probabilities through the circuit's measurement map to canonical classical strings.

- [ ] **Step 4: Implement deterministic circuit factories**

Provide exact builders for GHZ-5, QFT-4, Grover-3, and three five-qubit random circuits generated with `random.Random(20260818)`. Random builders may choose only whitelist gates and must always append full measurement.

- [ ] **Step 5: Write provider-vs-reference fidelity tests**

For every hidden-style circuit and provider, run 8192 shots, divide counts by shots, call the official `calculate_hellinger_fidelity`, and assert `>= 0.97`. Include the target and circuit name in every subtest label.

- [ ] **Step 6: Run all hidden-style tests and verify GREEN**

Run: `python -m unittest starter_kit.tests.l1.test_hidden_style_circuits -v`

Expected: every gate identity and provider/circuit fidelity test passes.

- [ ] **Step 7: Commit**

```bash
git add starter_kit/tests/l1/support starter_kit/tests/l1/test_hidden_style_circuits.py
git commit -m "test: cover LoomQ hidden-style circuits"
```

### Task 10: Prepare real-QPU evidence collection without credentials

**Files:**
- Create: `starter_kit/hardware/__init__.py`
- Create: `starter_kit/hardware/run_qpu.py`
- Create: `starter_kit/tests/l1/test_hardware_cli.py`
- Modify: `starter_kit/evidence/README.md`

- [ ] **Step 1: Write failing dry-run, credential, redaction, and import tests**

Test these exact CLI behaviors through `run_qpu.main(argv, environ)`:

1. `--provider originq --qasm bell.qasm --shots 8192 --dry-run` returns 0, emits OriginIR, and never reads or prints a token value.
2. A non-dry run without provider credentials raises `CredentialError` before network or SDK calls.
3. `--import-result provider-result.json` accepts a real provider result only when it contains non-empty `job_id`, valid UTC `timestamp`, positive `shots`, non-empty counts totaling shots, and a supported provider.
4. Imported evidence writes `<provider>-<job_id>-submission.qasm`, `native.ir`, `raw-result.json`, and `normalized-result.json` under the selected output directory.
5. Environment values matching credential-variable names never appear in stdout, stderr, or written files.

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest starter_kit.tests.l1.test_hardware_cli -v`

Expected: import failure for `starter_kit.hardware.run_qpu`.

- [ ] **Step 3: Implement safe dry-run and evidence import**

Support providers `spinq`, `originq`, and `braket`. Default output directory is `starter_kit/evidence/files`. Credential names are `SPINQ_API_TOKEN`, `ORIGINQ_API_TOKEN`, and the standard AWS credential chain plus `AWS_BRAKET_DEVICE_ARN`. Dry-run parses and emits without accessing credentials. Evidence import validates and copies only circuit/IR/result data; it never copies process environment data.

Because no account exists, automatic paid/queued submission is not enabled by default. The evidence importer is the supported path for provider-console or account-specific SDK results until an account supplies the exact live API contract. This is an explicit safety boundary, not a mock execution path.

- [ ] **Step 4: Document account-time execution workflow**

In `evidence/README.md`, add commands for dry-run, credential environment variables, provider result import, required raw fields, and the rule that only a traceable provider `job_id` from the contest window counts. State that SpinQ and OriginQ accounts are the first targets and AWS QPU use may incur charges.

- [ ] **Step 5: Run and verify GREEN**

Run: `python -m unittest starter_kit.tests.l1.test_hardware_cli -v`

Expected: all hardware preparation tests pass without network or credentials.

- [ ] **Step 6: Commit**

```bash
git add starter_kit/hardware starter_kit/tests/l1/test_hardware_cli.py starter_kit/evidence/README.md
git commit -m "feat: prepare traceable QPU evidence workflow"
```

### Task 11: Finalize submission metadata, documentation, and verification

**Files:**
- Modify: `starter_kit/submission.yaml`
- Modify: `starter_kit/README.md`
- Modify: `starter_kit/Dockerfile` only if build evidence proves a compatibility change is required.

- [ ] **Step 1: Update submission metadata**

Keep `contract_version: "1.0"`, `starter_kit_version: "1.1.0"`, and `levels.l1: true`; keep L2/L3 false; keep `network.required_for_l1: false`; set Python to `3.10`; leave `allowed_hosts` empty.

- [ ] **Step 2: Write executable README commands**

Document exact commands for dependency installation, all unit tests, public evaluator across three targets, individual target debugging, Docker build/run, QPU dry-run, and evidence import. Explain the internal IR and bit-order convention in one concise architecture section.

- [ ] **Step 3: Run the complete Python test suite**

Run: `python -m unittest discover -s starter_kit/tests -p "test_*.py" -v`

Expected: zero failures and zero errors.

- [ ] **Step 4: Run the official public evaluator**

Run: `python -m starter_kit.evaluator --level l1 --target spinq,originq,braket --shots 8192`

Expected: 6 passed, 0 failed.

- [ ] **Step 5: Build and run the official Python 3.10 container**

Run from `starter_kit/`:

```bash
docker build -t loomq-l1 .
docker run --rm loomq-l1
```

Expected: image build exits 0 and the container reports all declared public L1 cases passing.

- [ ] **Step 6: Run source and secret scans**

Run:

```bash
python -m compileall -q starter_kit
rg -n "(api[_-]?key|token|secret|cookie)\s*[:=]\s*['\"][^'\"]+" starter_kit -g "*.py" -g "*.yaml" -g "*.json"
git diff --check
git status --short
```

Expected: compile exits 0; secret scan finds no credential literals; diff check is empty; status contains only intentional final documentation/configuration changes before commit.

- [ ] **Step 7: Commit final submission configuration**

```bash
git add starter_kit/submission.yaml starter_kit/README.md starter_kit/Dockerfile
git commit -m "docs: finalize LoomQ L1 submission workflow"
```

- [ ] **Step 8: Run final verification after the last commit**

Repeat the complete test suite, official evaluator, Docker run, secret scan, `git diff --check`, and `git status --short --branch`. Record exact pass counts and any unavailable real-QPU checks in the handoff. Do not push or create the final submission Issue.

## Plan Self-Review Result

- Every design requirement maps to Tasks 1-11.
- L1 parsing, emission, execution, normalization, hidden tests, QPU preparation, dependency locking, Docker, documentation, and security checks each have explicit verification.
- L2 and L3 remain unchanged and disabled.
- Production behavior is always preceded by a failing test.
- Real-QPU success is not claimed without credentials and a traceable provider job.
