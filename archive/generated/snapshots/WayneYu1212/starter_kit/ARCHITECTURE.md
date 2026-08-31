# LoomQ Architecture

## Source of truth

The public contract is fixed by `target_ir_contract.md`, `l2_policy.json`, `backend_capabilities.json`, and the unchanged public evaluator. `adapter.py` is intentionally a thin compatibility boundary; business logic is under `loomq/`.

## One parser, one IR

`compiler.parser.parse_qasm()` removes line/block comments, parses declarations and statements, flattens any number of quantum/classical registers into offsets, expands whole-register measurement, and calls semantic validation. Parameter expressions use an AST allowlist: numeric literals, `pi`, parentheses, unary signs, `+ - * / ^`; arbitrary names and calls never execute.

The immutable `Circuit` contains ordered `Gate` and `Measurement` values. All three emitters and all three runners consume this same object. A platform cannot quietly reinterpret the source with its own parser branch.

## Target boundaries

## How to add a fourth backend

No fourth backend is invented here. An adapter contributes a capability entry, an emitter from the shared `Circuit`, an SDK runner, declared native measurement ordering, normalization into the unified result schema, and the shared conformance/differential tests. The parser and typed IR stay unchanged.

### SpinQ

- Artifact: complete OpenQASM 2.0.
- Runtime: SpinQit `QASMCompiler` → `BasicSimulator`.
- Native counts are ordered by measurement instructions from left to right. LoomQ reconstructs declared classical positions from the IR.

### OriginQ

- Artifact: canonical OriginIR.
- Runtime: pyQPanda parses that exact OriginIR and runs it on `CPUQVM`.
- pyQPanda 3.8.5 requires `RZ q[i],(theta)` / `RY q[i],(theta)` and `CR q[a],q[b],(theta)`. These forms are also allowed by the contest contract.
- pyQPanda's OriginIR parser does not define `SDAG/TDAG`, despite the scoring parser allowing those names. The emitter therefore performs exact whitelist-only lowering: `sdg = s³`, `tdg = t⁷`.
- Native counts already use the declared classical register width and rightmost `c[0]`.

### Braket

- Artifact: complete OpenQASM 3 with `stdgates.inc` and Braket-native operation names (`si`, `ti`, `cnot`, `cphaseshift`, `ccnot`).
- Runtime: `Program` → `LocalSimulator`.
- The Python-3.10-compatible default simulator line treats `stdgates.inc` as a filesystem include even though native operations need no definitions. The runner removes only that include line before local execution; the submitted transpilation artifact retains the contract form.
- Native counts are ordered by `result.measured_qubits`; LoomQ maps them into IR classical positions.

## Result normalization

`runners.result` distinguishes binary strings before decimal strings, preventing the common pyQPanda bug where raw `"11"` is interpreted as decimal eleven. It accepts integer, decimal, `0b`, and fixed-width binary keys, merges normalized duplicates, enforces non-negative integer counts and an exact shots sum, and always emits `c[n-1]...c[0]` with `bit_order="little"`.

The SDK-provided task ID is used where available. Local runtimes without one receive a local ID containing the emitted-program digest and a random nonce; those IDs are never described as QPU jobs.

## Independent verifier

`simulator.py` implements all 12 gates with standard-library complex arithmetic and seeded sampling. It is deliberately separate from SDK runners. It supports at most 16 qubits to keep Agent verification bounded and is never an automatic fallback for a missing target SDK.

## L2 data flow

1. `llm_client.chat_completion()` reads only `LOOMQ_LLM_*` and performs a non-streaming temperature-zero request.
2. The model returns one strict JSON `AgentPlan`: generate, repair, or recommend.
3. Generate/repair QASM goes through the same parser, validator, and independent simulator as L1. A failed candidate is returned to the model once with a sanitized verifier error.
4. Recommend constraints are applied in program code to the organizer's `backend_capabilities.json`; the model cannot invent or rename canonical backend IDs.
5. Only verified QASM or table-backed backend IDs reach the caller.

Every case requires at least one actual model response. Deterministic tools constrain the model; they do not replace it with prompt-keyword lookup.

## L3 Hybrid-QASM boundary

`loomq.hybrid` is isolated from the accepted L1/L2 compiler. A stateful scanner removes comments without touching quoted QASM strings, extracts one or more balanced `classical { ... }` blocks, and preserves every non-declaration quantum/measurement statement in source order. The classical lexer/parser builds immutable assignment, expression, condition, and nested-if AST nodes; it never uses `eval`, `exec`, or sample-text substitutions.

`compile_hybrid()` maps `r1..r9` to `x1..x9`, referenced `c[k]` to `x10+k`, and allocates scratch registers from unclaimed `x10..x31`. It emits only the official `li/add/sub/addi/beq/bne/j` subset with deterministic labels. Custom Bonus opcodes are never mixed into official L3 output.

## Custom quantum RISC-V extension

`riscv_emulator.py` retains stock behavior and additionally decodes a six-instruction family in RISC-V `custom-0` opcode space. Custom words append a deterministic `quantum_trace` describing intent; they never write general registers, invent measurements, simulate amplitudes, or claim QPU execution. The stable encoding and error behavior are specified in `QUANTUM_RISCV_EXTENSION.md` and exercised through encoded `.word` E2E tests.

## Web boundary

`loomq.web.server` uses `ThreadingHTTPServer`, listens on `127.0.0.1` by default, caps request bodies at 64 KiB and shots at 8192, prevents static path traversal, and serves a same-origin static UI with a restrictive Content Security Policy. Model text is inserted with `textContent`, never HTML interpretation.

Bell/GHZ local examples are explicitly labeled `local_example`; they bypass the LLM but still parse, verify, transpile, and run through the selected SDK. Free-form tasks use `agent_chat`.

## Test boundary

- Unit: expressions, parser, validator, IR, simulator, emitters, normalization.
- SDK integration: public Bell/GHZ, all 12 gates, non-identity classical mapping.
- Hidden-shape regression: GHZ-5, QFT-like, Grover-like, three seeded random circuits at 8192 shots across three SDKs.
- L2: real local OpenAI-compatible HTTP server, generate/repair/recommend, one retry, missing configuration, secret non-disclosure.
- Product: real HTTP server, static traversal/request limits, desktop/mobile browser runs, accessible DOM and no external assets.
- L3: public evaluator, nested/multi-block semantics, fixed-seed randomized programs, exhaustive measurement combinations, malformed input, and quantum-operation order.
- Quantum RISC-V Bonus: literal 32-bit encodings, decode errors, mnemonic/word trace parity, E2E demo, and stock emulator compatibility.

Automated checks are not QPU acceptance. Screenshots are not formal score receipts. A local venv is not a Docker build.
