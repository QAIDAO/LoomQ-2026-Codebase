# LoomQ Custom Quantum RISC-V Extension

## Purpose and boundary

This bonus extension defines a small architectural interface for recording quantum intent beside classical RISC-V control code. It does **not** simulate amplitudes, sample measurements, claim hardware execution, or change the official L3 compiler output. `compile_hybrid()` continues to emit only the stock `li/add/sub/addi/beq/bne/j` subset.

The extension uses the standard RISC-V `custom-0` opcode space. `TinyRISCVEmulator` decodes the words and appends deterministic dictionaries to `quantum_trace`; general-purpose registers are unchanged.

## 32-bit encoding

All words use opcode `0001011` (`0x0B`) in bits `[6:0]`.

| Mnemonic | `funct3` `[14:12]` | Fields | Meaning |
|---|---:|---|---|
| `qinit q` | `000` | `rd[11:7] = q` | Declare/reset qubit intent `q` |
| `qh q` | `001` | `rd[11:7] = q` | Record a Hadamard intent |
| `qx q` | `010` | `rd[11:7] = q` | Record an X intent |
| `qrz q, mr` | `011` | `rd = q`, signed `imm12[31:20] = mr` | Record an RZ intent in integer milliradians |
| `qcx control, target` | `100` | `rs1[19:15] = control`, `rs2[24:20] = target` | Record a controlled-X intent |
| `qmeasure q, slot` | `101` | `rs1 = q`, `rd = slot` | Bind a symbolic measurement intent to result slot |

`funct3` values `110` and `111` are reserved. Fields not named in the table must be zero. Qubit and result-slot fields are unsigned five-bit integers (`0..31`). `qcx` requires distinct control and target values. `qrz` uses a signed 12-bit two's-complement integer (`-2048..2047`) so encoding and review remain deterministic without floating-point ambiguity.

## Stable examples

```text
qinit 3                 -> 0x0000018b
qh 3                    -> 0x0000118b
qx 4                    -> 0x0000220b
qrz 2, -1571            -> 0x9dd0310b
qcx 1, 2                -> 0x0020c00b
qmeasure 2, 5           -> 0x0001528b
```

The emulator accepts either review-friendly mnemonics or encoded words:

```text
qinit 0
qh 0
qcx 0, 1
qmeasure 1, 0
```

```text
.word 0x0000000b
.word 0x0000100b
.word 0x0010400b
.word 0x0000d00b
```

Both forms produce the same `quantum_trace`. An unsupported opcode, reserved `funct3`, non-zero reserved field, out-of-range operand, or same-qubit `qcx` fails explicitly with `ValueError`.

## Emulator semantics

Example trace:

```json
[
  {"op": "qinit", "qubit": 0},
  {"op": "qh", "qubit": 0},
  {"op": "qcx", "control": 0, "target": 1},
  {"op": "qmeasure", "qubit": 1, "result_slot": 0}
]
```

The trace is a bounded, deterministic coprocessor-command record. `qmeasure` records a binding only; it never invents a measurement value. A real quantum runtime could consume this interface, but the included emulator intentionally makes no physics or hardware claim.

## Backward compatibility

- Stock RISC-V parsing and execution are unchanged.
- Programs using only the official L3 subset produce an empty `quantum_trace`.
- Custom instructions do not write `x0..x31`.
- The official L3 compiler never emits these custom instructions.

## Reproduction

From the fork root:

```powershell
.\.venv\Scripts\python.exe starter_kit\examples\quantum_riscv_demo.py
.\.venv\Scripts\python.exe -m unittest starter_kit.tests.test_quantum_riscv_extension -v
```

Unix:

```bash
.venv/bin/python starter_kit/examples/quantum_riscv_demo.py
.venv/bin/python -m unittest starter_kit.tests.test_quantum_riscv_extension -v
```

The tests lock the literal 32-bit words, round-trip decoding, error behavior, deterministic trace, encoded-word E2E path, and stock-instruction compatibility.
