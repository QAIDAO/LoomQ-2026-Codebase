# LoomQ-Q Quantum RISC-V ISA Specification

Version: 1.0
Word size: 32 bits
Major opcode: RISC-V `custom-0` (`0001011`, hexadecimal `0x0b`)

This file is the normative machine-readable-implementation companion requested
for the Bonus. The longer reviewer guide is in
`starter_kit/docs/bonus/QUANTUM_RISCV_ISA.md`.

## Encoding

All instructions use the standard R-type field locations:

```text
31          25 24      20 19      15 14   12 11       7 6         0
+--------------+----------+----------+-------+----------+-----------+
|    funct7    |   rs2    |   rs1    |funct3 |    rd    | 0001011   |
+--------------+----------+----------+-------+----------+-----------+
```

```text
word = funct7<<25 | rs2<<20 | rs1<<15 | funct3<<12 | rd<<7 | 0x0b
```

The assembler emits one unsigned 32-bit word. Byte serialization is
little-endian. Unused fields MUST be zero; the decoder rejects non-canonical
encodings so each assembly instruction has exactly one representation.

## Register operand model

`rs1`, `rs2`, and `rd` name ordinary integer registers `x0..x31`. Except for
measurement destinations, the integer *value stored in the GPR* is an operand:

- a qubit GPR stores a qubit index;
- a QINIT GPR stores a positive qubit count;
- an angle GPR stores signed Q16.16 radians;
- QMEASURE writes 0 or 1 to its `rd` GPR.

Thus `li x1, 7; qh x1` applies H to qubit 7. Qubit operands are resolved only
when the instruction executes, so official `add`, `sub`, `addi` and branches
can compute and control them.

Signed Q16.16 uses `angle = signed32(gpr) / 65536`. Both negative Python
integers and unsigned two's-complement words are accepted. For example,
`pi/2` encodes as `102944`; `-1.0` encodes as `-65536` or `0xffff0000`.

## Instruction allocation

| Instruction | Assembly operands | funct3 | funct7 | Field use | Operation |
|---|---|---:|---:|---|---|
| QH | `qh rs1` | `000` | `0000000` | `rd=0, rs2=0` | Hadamard on qubit `[rs1]` |
| QX | `qx rs1` | `000` | `0000001` | `rd=0, rs2=0` | Pauli-X on qubit `[rs1]` |
| QS | `qs rs1` | `000` | `0000010` | `rd=0, rs2=0` | S on qubit `[rs1]` |
| QT | `qt rs1` | `000` | `0000011` | `rd=0, rs2=0` | T on qubit `[rs1]` |
| QCX | `qcx rs1, rs2` | `001` | `0000000` | `rd=0` | CX control `[rs1]`, target `[rs2]` |
| QSWAP | `qswap rs1, rs2` | `001` | `0000001` | `rd=0` | SWAP qubits `[rs1]`, `[rs2]` |
| QMEASURE | `qmeasure rd, rs1` | `010` | `0000000` | `rs2=0, rd!=0` | Z measurement of `[rs1]` into `rd` |
| QINIT | `qinit rs1` | `011` | `0000000` | `rd=0, rs2=0` | Reset to an `[rs1]`-qubit zero state |
| QRY | `qry rs1, rs2` | `100` | `0000000` | `rd=0` | RY of Q16.16 radians `[rs2]` on `[rs1]` |
| QRZ | `qrz rs1, rs2` | `100` | `0000001` | `rd=0` | RZ of Q16.16 radians `[rs2]` on `[rs1]` |
| QCCX | `qccx rs1, rs2, rd` | `101` | `0000000` | all fields used | Toffoli controls `[rs1]`,`[rs2]`, target `[rd]` |

Square brackets denote reading the named GPR. QCCX uses the physical `rd`
field as its third *source* operand and does not write that GPR.

Required contest set QINIT/QH/QX/QRY/QRZ/QCX/QSWAP/QCCX/QMEASURE is fully
covered; QS/QT are additional phase operations.

## Stable examples

| Assembly | Word |
|---|---:|
| `qh x1` | `0x0000800b` |
| `qx x1` | `0x0200800b` |
| `qcx x1, x2` | `0x0020900b` |
| `qmeasure x3, x2` | `0x0001218b` |
| `qinit x1` | `0x0000b00b` |
| `qry x1, x2` | `0x0020c00b` |
| `qrz x1, x2` | `0x0220c00b` |
| `qccx x1, x2, x3` | `0x0020d18b` |

## Execution rules

1. QINIT resets the full quantum state to `|0...0>` with the requested size;
   it does not erase the append-only execution log or reseed measurement RNG.
2. QH/QX/QS/QT/QRY/QRZ apply their standard unitary matrices.
3. QCX/QSWAP require two distinct resolved qubits; QCCX requires three.
4. QMEASURE performs seeded Born sampling, collapses the local statevector and
   writes the result through the official `set_register()` behavior.
5. Qubit indices must fit the emulator limit (default 0..11). QINIT count must
   be 1..12 by default. Invalid operands fail explicitly.
6. Quantum instructions obey the official program counter and branch labels;
   skipped instructions do not appear in the execution log.

The implementation is a deterministic-seed local ideal simulator. It is not
physical RISC-V or quantum-hardware execution and MUST NOT be cited as L1
hardware evidence. `execution_report()` states `hardware_execution: false`.

## Reference implementation mapping

- Encoding/decoding: `starter_kit/loomq/bonus/isa.py`
- Official-emulator extension: `starter_kit/loomq/bonus/emulator.py`
- Local quantum semantics: `starter_kit/loomq/bonus/statevector.py`
- End-to-end executable: `python -m loomq.bonus.demo`
- Tests: `starter_kit/tests/test_bonus_*.py`
