# LoomQ Quantum RISC-V Extension v1.0

This extension lets a tiny classical RISC-V control program initialize and operate a state-vector quantum coprocessor. It uses the standard RISC-V `custom-0` opcode space and does not modify the meaning of the seven L3 base instructions.

## Binary format

All instructions use a 32-bit R-type-shaped word:

```text
31          25 24       20 19       15 14    12 11        7 6         0
+--------------+-----------+-----------+--------+------------+-----------+
| funct7 = 0   | rs2 / arg | rs1 / arg | funct3 | rd / arg   | 0001011   |
+--------------+-----------+-----------+--------+------------+-----------+
```

- Opcode `[6:0]` is `0x0B`, the RISC-V `custom-0` space.
- `funct7` must be zero. Non-zero reserved bits are rejected.
- Qubit indices and the qubit count use unsigned five-bit fields.
- `rd` is a normal integer register. `x0` retains its normal discard-write behavior.

| Mnemonic | funct3 | rd | rs1 | rs2 | Meaning |
|---|---:|---|---|---|---|
| `qinit n` | `000` | 0 | qubit count | 0 | Reset an `n`-qubit coprocessor to `|0...0>` |
| `qh q` | `001` | 0 | target qubit | 0 | Apply Hadamard |
| `qx q` | `010` | 0 | target qubit | 0 | Apply Pauli-X |
| `qcx control, target` | `011` | 0 | control | target | Apply controlled-X |
| `qmeasure rd, q` | `100` | destination | measured qubit | 0 | Collapse and write the measured bit to `rd` |

The lightweight implementation limits `qinit` to 20 qubits to bound memory. The binary format itself can represent up to 31.

## Reference implementation

`riscv_emulator.py` exports:

```python
encode_quantum_instruction(mnemonic, *operands) -> int
decode_quantum_instruction(word) -> tuple[str, list[str]]
```

`TinyRISCVEmulator` executes either textual mnemonics or one hexadecimal encoded instruction per line. Quantum measurement uses a seeded pseudo-random generator so tests are reproducible; the state collapse semantics remain correct.

## End-to-end example

```text
qinit 2
qh 0
qcx 0, 1
qmeasure x10, 0
qmeasure x11, 1
bne x10, x11, CORRELATION_ERROR
li x1, 1
j END
CORRELATION_ERROR:
li x1, -1
END:
```

The Bell circuit guarantees that `x10 == x11`, so the classical program finishes with `x1 = 1`. The same test is also executed from raw encoded words.

Run the archived end-to-end proof from the evaluation root:

```bash
python3 -m unittest test_quantum_riscv_extension -v
```
