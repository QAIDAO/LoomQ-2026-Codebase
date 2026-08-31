# L1 Verification Report

## Verified Baseline

- Date: 2026-08-07
- Clean runtime: CPython 3.10.19
- Installation source: repository `requirements.txt`
- Native mode: `LOOMQ_REQUIRE_NATIVE=1`
- SpinQit: 0.2.4
- pyqpanda: 3.8.5
- pyqpanda3: 0.4.0
- Amazon Braket SDK: 1.95.0
- Amazon Braket default simulator: 1.27.0

## Results

The clean Python 3.10 verification completed successfully:

```text
Official public evaluator: 6 passed, 0 failed
Project L1 suite: 21 passed, 0 failed
Extended native surrogate suite: 201 passed, 0 failed
```

The same source also passed the dependency-free fallback suite. `scripts/verify_all.py` is the authoritative L1 command.

## Coverage

- Public Bell and GHZ-3 on `spinq`, `originq`, and `braket` at 8192 shots.
- Surrogate GHZ-5, QFT-4, and Grover-3 circuits on all three native SDK backends.
- All 12 whitelisted gates through each target IR.
- All 12 gates on all three installed native local SDK backends.
- 64 hidden-set surrogate random circuits with 3-5 qubits and 20-36 gates.
- All 12 gates in every surrogate random circuit, including 12 parameter boundary forms.
- Independent reference state evolution and Hellinger fidelity threshold 0.97.
- Whole-register, reverse, rotated, and partial measurement mapping.
- Asymmetric `q[0]` / `q[1]` bit-order probes.
- Unified result schema and exact count total.
- Extended native minimum observed fidelity: 0.980806 across 201 executions.

## Environment Limitation

Docker is not installed on the verification workstation, so `docker build` was not executed. Dependency reconstruction was performed in a fresh repository-local CPython 3.10.19 virtual environment using only the committed `requirements.txt`.

The remaining environment-level gap is a native Linux container run. SpinQit pulls a large Torch dependency tree on Linux; allow sufficient container build time before final submission.

## Hardware Boundary

SpinQ read-only hardware preflight passed on 2026-08-07 using an account-visible, online `gemini_vp` real device. The preflight used the shared `adapter.transpile()` path, compiled the Bell circuit with SpinQit, generated a 1024-shot task payload preview, wrote only Git-ignored local artifacts, and found no credential values in 112 scanned files.

One real-QPU evidence job then completed successfully:

```text
Platform: SpinQ Cloud gemini_vp (2-qubit NMR real device)
Job ID: G-260807-0011
Timestamp: 2026-08-07T09:37:30.832+0000
Shots: 1024
Derived counts: 00=360, 01=114, 10=87, 11=463
Top-2 states: 11, 00
Bell Top-K match: PASS
```

The original platform result, normalized result, and executed QASM are stored under `evidence/files/`. The raw platform response reports probabilities; counts are derived with the SpinQit rule `round(probability * shots)` and explicitly labeled as derived.

OriginQ was migrated from the retired pyqpanda chip-72 path to the current QPanda3 cloud API. Online preflight confirmed that `WK_C180_2` was available, exposed 180 physical qubits, and returned physical qubits `[38, 47]` as the best two-qubit block. One real-QPU job completed successfully:

```text
Platform: Origin Quantum Cloud WK_C180_2 (Wukong 180 real QPU)
Job ID: E03FE919C438D14649B3C227CB6979D8
Timestamp: 2026-08-07T12:13:30.819000Z
Physical qubits: 38, 47
Shots: 1024
Counts: 00=509, 01=87, 10=43, 11=385
Top-2 states: 00, 11
Bell Top-K match: PASS
```

The executed OriginIR, complete QPanda3 `origin_data()` response, and normalized result are stored under `evidence/files/`. The raw response contains no credential or account-identity fields. SpinQ and OriginQ therefore provide the two traceable real-hardware evidence sets required for the full hardware-evidence tier, subject to organizer verification of both job IDs.
