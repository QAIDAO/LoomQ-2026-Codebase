# LoomQ Custom-0 Quantum RISC-V Extension

This optional L3 Bonus implementation extends the supplied tiny RISC-V model without changing `riscv_emulator.py`. The compatible fork is `loomq/riscv_quantum_extension.py`; it retains all official `li`, `add`, `sub`, `addi`, `beq`, `bne`, and `j` behavior and adds a single readable pseudo-assembly form:

```text
qop 0xXXXXXXXX
```

## 32-bit encoding

All quantum instructions use the standard RISC-V `custom-0` opcode `0b0001011` (`0x0b`). Qubit fields encode `0..31`; the executable state-vector implementation deliberately limits execution to 12 qubits.

| Form | `funct3` | Bits | Field | Meaning |
|---|---|---|---|---|
| all | all | 6:0 | opcode | `0x0b` / custom-0 |
| gate | `000` | 11:7, 19:15, 24:20 | `q0`, `q1`, `q2` | one, two, or three indexed gate operands; unused fields are zero |
| gate | `000` | 31:25 | gate id | `h`, `x`, `s`, `sdg`, `t`, `tdg`, `rz`, `ry`, `cx`, `cu1`, `swap`, `ccx` in implementation order |
| measure | `001` | 11:7, 19:15 | `q0`, `cbit` | measure `q[q0]` into `c[cbit]`; `cbit` is `0..21` and maps to `x10..x31` |
| parameter | `010` | 11:7 and 31:15 | payload | signed 22-bit Q7.15 radians, split low-five/high-seventeen bits; applies to immediately following `rz`, `ry`, or `cu1` |

Examples:

```text
qop 0x0000000b  # H q[0]
qop 0x0200008b  # X q[1]
qop 0x0001910b  # MEASURE q[2] -> c[3]
```

## Runtime model

`ExtendedTinyRISCVEmulator` is an independently named compatible fork. It executes the documented gate set over a little-endian state vector, using the same L1 gate semantics. `qop` events are retained as typed entries in `quantum_trace` for inspection.

Measurement samples amplitude-squared probabilities with a seeded pseudo-random generator, collapses and renormalizes state, and writes its bit to `x(10+cbit)`. Thus ordinary `beq`/`bne` instructions can branch on a quantum measurement. A parameter word must be followed immediately by its parameterized gate; malformed sequences fail explicitly.

`compile_quantum_operations()` parses the existing L1 operation syntax and emits executable `qop` words for every L1 whitelisted gate plus indexed measurement. Whole-register measurement is deliberately rejected because the operation-only list does not carry its width; the error is explicit rather than silently guessing a mapping.

The supplied `riscv_emulator.py` remains untouched and is the only emulator used by official L3 scoring.

## Verification

```bash
python -m unittest tests.test_l3_bonus_contract
```

The test covers all 12 gate forms, signed fixed-point parameter round trips, malformed encodings, conversion from an L3 operation list, Bell measurement driving a classical branch, and exact parity with the official emulator for ordinary RISC-V programs.