# L1 Implementation and Verification

## Scope

L1 software implementation supports all three required targets and the twelve-gate whitelist. It includes native local execution for SpinQit BasicSimulator, OriginQ pyqpanda CPUQVM, and AWS Braket LocalSimulator. A bundled standard-library state-vector engine is retained as an explicit fallback and as a deterministic test oracle.

This document covers the automatically testable L1 software portion. Real-hardware evidence is separate: hardware points require platform accounts, in-window job IDs, raw results, and evidence files supplied by the team.

## Data Flow

```text
OpenQASM 2.0
  -> loomq/qasm.py: validated AST
  -> loomq/transpilers/: SpinQ QASM 2 / OriginIR / Braket QASM 3
  -> loomq/backends.py: native local SDK execution
  -> normalized counts c[n-1]...c[0]
  -> official result schema
```

`adapter.py` is intentionally a thin official-contract layer. Parsing, target rendering, execution, and normalization are separate modules so target-specific behavior does not become three hard-coded end-to-end branches.

## Files

| File | Responsibility |
|---|---|
| `adapter.py` | Official `transpile()` and `run()` entry points |
| `loomq/qasm.py` | Restricted OpenQASM 2 parser, validation, immutable AST |
| `loomq/transpilers/spinq.py` | Complete OpenQASM 2 target |
| `loomq/transpilers/originq.py` | Canonical OriginIR target |
| `loomq/transpilers/braket.py` | Complete OpenQASM 3 target |
| `loomq/backends.py` | Native SDK adapters and bit-order normalization |
| `loomq/simulator.py` | Dependency-free state-vector fallback for all 12 gates |
| `tests/test_l1_contract.py` | Adapter and result-schema contract |
| `tests/test_l1_property.py` | Fixed-seed random circuits and independent reference evolution |
| `tests/test_l1_native.py` | Native SDK, 12-gate and asymmetric bit-order checks |

## Gate Mapping

The shared AST accepts `h`, `x`, `s`, `sdg`, `t`, `tdg`, `rz`, `ry`, `cx`, `cu1`, `swap`, and `ccx`.

- OriginIR maps inverse gates to `SDAG` / `TDAG`, `cx` to `CNOT`, and `ccx` to `TOFFOLI`.
- Braket QASM 3 maps `cx` to `cnot` and `cu1` to standard `cp`.
- Native Braket execution uses Circuit API methods `si`, `ti`, `cphaseshift`, and `ccnot` because the Python 3.10 OpenQASM parser cannot load `stdgates.inc` from the filesystem.

## Bit Order

The public result schema always returns `c[n-1]...c[0]` with `bit_order: little`.

Asymmetric native tests prepare `q[0]=1` and `q[1]=1` separately. This detected that SpinQ raw counts require reversal, OriginQ already uses the required classical order, and Braket Circuit results must be mapped from measured qubits into the declared classical register.

## Verification Commands

Dependency-free verification:

```bash
python scripts/verify_all.py
```

Pinned Python 3.10 native verification:

```bash
python -m pip install -r requirements.txt
LOOMQ_REQUIRE_NATIVE=1 python scripts/verify_all.py
```

The native suite verifies all three SDK imports, all twelve gates, three target formats, partial measurement mapping, asymmetric bit order, public Bell/GHZ circuits, and 32 fixed-seed random circuits at 8192 shots with fidelity threshold `0.97`.
