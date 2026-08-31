# LoomQ Quantum RISC-V Extension v1

## 1. Scope

This extension encodes LoomQ's 12-gate quantum whitelist as RISC-V `custom-0`
instructions. It is orthogonal to the base L3 classic-control ISA: `li`, `add`,
`sub`, `addi`, `beq`, `bne`, and `j` retain their official behavior.

The standard `adapter.compile_hybrid()` entry point remains compatible with the
base L3 evaluator. Bonus evaluation uses:

```python
adapter.compile_hybrid_bonus(hybrid_qasm_str) -> tuple[list[str], str]
```

The returned assembly contains `qinst` carriers followed by ordinary classic
control. `qinst` is decoded and recorded by the extended `riscv_emulator.py`.

## 2. Instruction word

Every quantum operation starts with one logical 32-bit instruction word. A
binary RISC-V stream serializes it in normal little-endian byte order.

| Bits | Width | Field | Meaning |
|---:|---:|---|---|
| 6:0 | 7 | `opcode` | `0001011` (`0x0B`, RISC-V `custom-0`) |
| 11:7 | 5 | `q0` | First qubit; measurement source |
| 16:12 | 5 | `q1` | Second qubit; measurement destination `c[k]` |
| 21:17 | 5 | `q2` | Third qubit |
| 26:22 | 5 | `gate_id` | Gate identifier from the table below |
| 27 | 1 | `has_param` | One binary32 payload word follows |
| 31:28 | 4 | `version` | Extension version, fixed to `1` |

Unused operand fields must be zero. Qubit and measurement indices are unsigned
and limited to `0..31`. Multi-qubit gates must use distinct qubits.

## 3. Gate identifiers

| ID | Gate | Arity | Parameter |
|---:|---|---:|---|
| 1 | `h` | 1 | no |
| 2 | `x` | 1 | no |
| 3 | `s` | 1 | no |
| 4 | `sdg` | 1 | no |
| 5 | `t` | 1 | no |
| 6 | `tdg` | 1 | no |
| 7 | `rz` | 1 | binary32 |
| 8 | `ry` | 1 | binary32 |
| 9 | `cx` | 2 | no |
| 10 | `swap` | 2 | no |
| 11 | `ccx` | 3 | no |
| 12 | `cu1` | 2 | binary32 |
| 13 | `measure` | `q0 -> c[q1]` | no |

Parameterized gates set `has_param=1` and carry exactly one following 32-bit
IEEE-754 binary32 payload. NaN and infinity are invalid. The adapter accepts
finite expressions containing numeric literals, `pi`, parentheses, unary
signs, and `+ - * / **`, then rounds once to binary32.

## 4. Assembly carrier

The lightweight emulator uses this textual carrier:

```asm
qinst 0x1040000b                 # h q[0]
qinst 0x19c0000b, 0x3fc90fdb     # rz(pi/2) q[0]
```

The first operand is the instruction word. The second is mandatory only when
`has_param=1`. Both must fit in an unsigned 32-bit word.

The emulator validates opcode, version, gate ID, operand count, unused fields,
qubit distinctness, parameter presence and parameter finiteness. Execution
records decoded operations in `TinyRISCVEmulator.quantum_operations`; the
lightweight emulator deliberately does not approximate quantum-state evolution.
A real backend can consume the same validated stream.

## 5. Register and execution contract

- Hybrid variable `r1..r9` maps to `x1..x9`.
- Measurement input `c[k]` maps to `x10+k` for classic control.
- Quantum instructions do not modify general-purpose registers.
- Whole-register `measure q -> c` expands in ascending index order and requires
  equal `q` and `c` sizes.
- Extension v1 requires exactly one quantum register named `q`, at most 32
  qubits, and the standard measurement register `c`.
- Quantum plus worst-case classic instructions must not exceed the emulator's
  1000-step execution limit.

## 6. Reproduction

From the submitted `starter_kit/` evaluation root:

```bash
python -m unittest test_l3_bonus -v
python evaluator.py --level l3
```

The Bonus suite checks encoding and decoding of all supported gates, binary32
parameters, whole-register measurement, classic control, invalid encodings,
invalid QASM, resource limits and boundary conditions. The second command
confirms compatibility with the official base L3 contract.
