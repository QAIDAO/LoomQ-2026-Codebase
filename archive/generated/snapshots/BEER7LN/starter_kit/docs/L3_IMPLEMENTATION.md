# L3 Implementation Plan: Hybrid-QASM to RISC-V

## Score target and boundary

L3 is a deterministic 15-point task. `compile_hybrid(source)` must return `(quantum_operations, assembly)`. The evaluator randomly varies legal Hybrid-QASM programs, injects every measured-bit combination into `x10, x11, ...`, executes the assembly using the provided `riscv_emulator.py`, and compares all observable `r1..r9` final values with its reference interpreter. It also checks that the returned quantum operation list is semantically equivalent to the source program outside `classical { ... }`.

The main implementation therefore does not use an LLM, external network, or example-specific lookup. It deliberately leaves the official emulator unchanged. The optional +8 custom-opcode bonus is a separate deliverable because the rules require an instruction specification, an emulator extension, and an end-to-end test.

## Accepted language and semantics

The compiler accepts the stated Hybrid-QASM subset:

- normal OpenQASM 2.0 declarations plus the existing L1 gate/measurement subset;
- exactly one `classical { ... }` block at any statement boundary;
- integer literals, variables `r1` through `r9`, measurement values `c[k]`;
- left-associative `+` and `-`; assignments; nested `if (...) { ... } else { ... }`;
- equality and inequality conditions using `==` and `!=`.

`c[k]` maps to RISC-V `x(10+k)` exactly. User registers map directly: `rN -> xN`. The code generator reserves no observable user register: it lowers each `+`/`-` expression symbolically as a constant plus `c[k]` coefficients, uses only `x1` to materialize a branch comparison, and materializes all observable `r1..r9` at each control-flow exit. Thus high measurement inputs such as `c[21] -> x31` are not overwritten. Inputs that cannot be represented by the 32-register emulator receive a clear validation error.

## Compilation approach

1. Locate and remove the balanced `classical { ... }` block while preserving the surrounding QASM.
2. Parse the quantum remainder with the existing L1 OpenQASM parser and return normalized, executable quantum gate/measurement statements in source order.
3. Tokenize the classical block into an AST (`Assign`, `If`, `Binary`, `Register`, `Measurement`, `Integer`).
4. Compile symbolic assignments with `li`, `addi`, `add`, and `sub`; compile structured branches with unique labels plus `beq`, `bne`, and `j`.
5. Never execute or simulate a measurement inside L3: the official evaluator injects those values into the documented registers.

## Test-first evidence

`tests/test_l3_hybrid.py` will provide parser failures, quantum extraction checks, direct RISC-V execution checks, nested branch cases, exhaustive all-bit measurement injection, and a deterministic generated corpus. A local reference AST interpreter is intentionally independent from the assembler generator. `tests/test_l3_bonus_contract.py` verifies the optional custom-0 extension end to end.

Run:

```bash
python -m unittest tests.test_l3_hybrid
python evaluator.py --level l3
python -m unittest tests.test_l3_bonus_contract
python scripts/verify_all.py
```

## Residual risks

Only organizer-generated programs establish official credit. Local generated cases cannot certify the unknown generator distribution. Before final submission, run the full differential corpus under Python 3.10 and the same unmodified `riscv_emulator.py` shipped with the kit.