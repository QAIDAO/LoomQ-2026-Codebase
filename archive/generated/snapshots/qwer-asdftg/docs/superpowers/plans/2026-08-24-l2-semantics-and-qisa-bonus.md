# L2 Semantic Validation and Quantum RISC-V Bonus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject semantically wrong L2 answers before returning them and submit the three required custom quantum RISC-V Bonus artifacts.

**Architecture:** A shared pure-Python validator recognizes only explicit GHZ, Bell, and backend constraints, then checks parseable output with exact statevector probabilities or the supplied capability table. The official `TinyRISCVEmulator` is extended in place with a bounded quantum coprocessor and RISC-V Custom-0 instruction encoding.

**Tech Stack:** Python 3.10, standard library, existing OpenQASM parser, `unittest`, Docker.

---

### Task 1: Shared L2 semantic validation

**Files:**
- Create: `starter_kit/l2_semantics.py`
- Modify: `starter_kit/l2_probe.py`
- Test: `starter_kit/tests/l2/test_probe.py`

- [ ] **Step 1: Write failing semantic tests**

Add a parseable product-state Bell circuit and assert it is rejected, then assert an explicit free/zero-queue 15-qubit request rejects `originq_wukong`.

```python
requirement = infer_requirement("修复 Bell 态并全测量")
self.assertIn("distribution", validate_reply(requirement, PRODUCT_BELL, BACKENDS))

backend_requirement = infer_requirement("运行 15 比特电路，免费且零排队")
self.assertIn("queue", validate_reply(backend_requirement, "originq_wukong", BACKENDS))
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python -m unittest starter_kit.tests.l2.test_probe -v`

Expected: import failure for `starter_kit.l2_semantics`.

- [ ] **Step 3: Add the minimal production module**

Define:

```python
@dataclass(frozen=True)
class Requirement:
    kind: str
    qubits: int | None = None
    require_free: bool = False
    require_zero_queue: bool = False

def infer_requirement(prompt: str) -> Requirement | None: ...
def validate_reply(requirement: Requirement | None, reply: str,
                   backends: Sequence[Mapping[str, Any]]) -> str | None: ...
```

Use the existing QASM parser. Implement exact H/CX statevector evaluation. A GHZ requirement must fully measure the requested width and have only all-zero/all-one states at probability 1/2. Bell uses the two-bit equivalent. Backend requirements check only explicit bit, free, and zero-queue constraints. Unknown intent returns `None`, avoiding false rejection.

- [ ] **Step 4: Delegate probe checks to the shared module**

Keep `ProbeCase`, JSON report shape, and CLI flags unchanged. Replace duplicated distribution/backend logic with `validate_reply`.

- [ ] **Step 5: Verify and commit**

Run: `python -m unittest starter_kit.tests.l2.test_probe -v`

Expected: all pass.

```bash
git add starter_kit/l2_semantics.py starter_kit/l2_probe.py starter_kit/tests/l2/test_probe.py
git commit -m "feat: add reusable L2 semantic validation"
```

### Task 2: Semantic retry in formal `agent_chat`

**Files:**
- Modify: `starter_kit/loomq_l2.py`
- Test: `starter_kit/tests/l2/test_agent.py`

- [ ] **Step 1: Write the failing retry test**

Mock two replies: first a parseable but unentangled Bell product state, then a valid Bell circuit.

```python
with mock.patch(
    "starter_kit.llm_client.chat_completion",
    side_effect=[completion(PRODUCT_BELL), completion(BELL_QASM)],
) as chat:
    reply = adapter.agent_chat("请修复并生成 Bell 态，全部测量")

self.assertEqual(chat.call_count, 2)
self.assertEqual(reply, BELL_QASM.strip())
self.assertIn("distribution", chat.call_args_list[1].args[0][-1]["content"])
```

Add a separate unknown-intent valid-QASM case that remains a one-call return.

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest starter_kit.tests.l2.test_agent -v`

Expected: existing agent accepts the product state after one call.

- [ ] **Step 3: Wire the semantic check**

Pass the original prompt and backend records into `_valid_reply`. Preserve existing QASM/canonical-ID shape validation, then call `infer_requirement` and `validate_reply`. Feed only the precise safe reason into the existing one repair request. Preserve the two-call maximum and never include Key, header, or response body in an error.

- [ ] **Step 4: Verify and commit**

Run: `python -m unittest starter_kit.tests.l2 -v`

Expected: all pass; the parseable-wrong Bell test makes exactly two calls.

```bash
git add starter_kit/loomq_l2.py starter_kit/tests/l2/test_agent.py
git commit -m "feat: retry L2 replies that fail semantic checks"
```

### Task 3: Custom-0 support in the official emulator

**Files:**
- Modify: `starter_kit/riscv_emulator.py`
- Create: `starter_kit/tests/l3/test_quantum_riscv_extension.py`

- [ ] **Step 1: Write failing instruction and Bell tests**

```python
word = encode_quantum_instruction("qcx", rs1=0, rs2=1)
self.assertEqual(word & 0x7F, 0x0B)
self.assertEqual(decode_quantum_instruction(word), ("qcx", 0, 1, 0))

emulator = TinyRISCVEmulator(seed=7)
emulator.load_program("qh q0\nqcx q0, q1\nqmeas x5, q0\nqmeas x6, q1")
state = emulator.execute()
self.assertEqual(state.get("x5", 0), state.get("x6", 0))
```

Also run the current `li/add/sub/addi/beq/bne/j` example unchanged.

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest starter_kit.tests.l3.test_quantum_riscv_extension -v`

Expected: import failure for the Custom-0 helper functions.

- [ ] **Step 3: Implement the extension in `riscv_emulator.py`**

Add `CUSTOM_0 = 0x0B`, `QH_FUNCT3 = 0`, `QCX_FUNCT3 = 1`, `QMEAS_FUNCT3 = 2`, plus validated `encode_quantum_instruction` and `decode_quantum_instruction`. Keep current classical mnemonics untouched. Add optional `seed`, q-registers `q0..q7`, an eight-qubit statevector, H/CX application, and seeded Born measurement. `qmeas rd, qs` writes through existing `set_register`, preserving x0 immutability.

- [ ] **Step 4: Verify and commit**

Run: `python -m unittest starter_kit.tests.l3 -v`

Expected: all existing L3 and new extension tests pass.

```bash
git add starter_kit/riscv_emulator.py starter_kit/tests/l3/test_quantum_riscv_extension.py
git commit -m "feat: extend official RISC-V emulator with quantum custom ops"
```

### Task 4: Required Bonus documents, evidence, and verification

**Files:**
- Create: `starter_kit/quantum_riscv_extension.md`
- Modify: `starter_kit/evidence/README.md`

- [ ] **Step 1: Write the encoding specification**

Document Custom-0 `0x0B`, funct3 values, 32-bit fields, q-register range, eight-qubit limit, deterministic seed behavior, and the exact end-to-end command:

```bash
python -m unittest starter_kit.tests.l3.test_quantum_riscv_extension -v
```

- [ ] **Step 2: Fill evidence without secrets**

Fill the three Bonus fields with the specification, official emulator path, and test command. Add a dated L2 note: Cherry DeepSeek Flash and Kimi K2.5 passed all three probes; Qwen/GLM/MiniMax non-reports or HTTP errors are not passes. No Key, headers, or request bodies enter the repository.

- [ ] **Step 3: Run complete verification**

```bash
docker run --rm -w /workspace loomq-l1 python -m unittest discover -s starter_kit/tests -p "test_*.py" -q
docker run --rm -w /workspace loomq-l1 python -m starter_kit.evaluator --level l1 --target spinq,originq,braket --shots 8192
docker run --rm -w /workspace loomq-l1 python -m starter_kit.evaluator --level l3
```

Expected: all unit tests exit 0; L1 reports `passed: 6`; L3 reports `passed: 1`.

- [ ] **Step 4: Probe GLM replacement and commit**

Use the Key only in the current process to probe `agent/glm-5-turbo` and then `agent/qwen3.5-flash` if the former returns a safe error. Record only pass, HTTP status, or no-report anomaly.

```bash
git add starter_kit/quantum_riscv_extension.md starter_kit/evidence/README.md
git commit -m "docs: add quantum RISC-V bonus evidence"
git push -u origin feat/loomq-l1-unified-transpiler
```

## Plan self-review

- Tasks 1-2 cover semantic checking, safe reasons, and exactly one repair retry.
- Task 3 modifies the official emulator rather than replacing it.
- Task 4 supplies all three Bonus artifacts, documents model evidence without secrets, and verifies L1/L3 regressions.

