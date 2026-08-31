# OriginQ Reproducibility Evidence

> **Traceability boundary**: This is **participant-side** reproducibility evidence. It does **not** replace organizer hardware verification. Organizers may log into Origin Quantum Cloud and verify the recorded job ID. It does **not** claim any additional score.

## 1. Objective

Establish a reproducible, auditable, explainable record for the existing real OriginQ hardware evidence, and (when credentials are available) extend it with repeated independent runs.

## 2. Hardware

- Provider: Origin Quantum Cloud
- Device: **Origin Wukong 180-2** (superconducting; device id `WK_C180_2`)
- Physical qubits used: `q[49]`, `q[58]` (canonical Bell); GHZ-3 additionally used `q[67]`

## 3. Circuit

- Canonical Bell: `originq-hardware-bell.qasm`, gates `H(q0); H(q1); CZ(q0,q1); H(q1); measure q -> c`, SHA-256 `b83288d04f54fad40c776df9eb949e5cbf660b0dd67dd9eddbc301b0e19d8432`.
- Runtime Bell: `originq_runtime_bell-hardware-bell.qasm`, gates `H(q0); CX(q0,q1); measure`.
- Runtime GHZ-3: `originq_runtime_ghz3-hardware-bell.qasm`, gates `H(0); CX(0,1); CX(0,2); measure`.
- Runtime Multi: `originq_runtime_multi-hardware-bell.qasm`, gates `H(0); CX(0,1); H(0); CX(0,1); measure`.

## 4. Experimental procedure

- Canonical job was submitted via the legacy `pyqpanda.QCloud.async_real_chip_measure` (chip 72).
- After that legacy gateway returned `Quantum computer under maintenance` (2026-08-21), the path was migrated to the official **QPanda3 Runtime** API (`qpanda3_runtime.RuntimeService`, device `WK_C180_2`), which successfully ran three new jobs (Bell / GHZ-3 / Multi).
- `shots = 1000` for all jobs.
- Intended repetition: **5 runs minimum, 10 runs ideal** (legacy path could not meet this due to maintenance; the Runtime path added three diverse circuits).

## 5. Individual jobs

| Circuit | job_id | requested shots | qubits | P(00) | P(11) |
|---|---|---|---|---|---|
| Bell (canonical, legacy API) | `D0C7F490B43D9B04FDF19ABF3DB8B342` | 1000 | [49,58] | 0.501 | 0.450 |
| Bell (Runtime API) | `2C68A9D3E2F6626B55EEC966DBC3CE2B` | 1000 | [49,58] | 0.458 | 0.542 |
| GHZ-3 (Runtime API) | `B23E5B75D47D124A078F25B1C0083C2A` | 1000 | [49,58,67] | P(000)=0.703 | P(111)=0.108 |
| Multi (Runtime API) | `8575222FE2C04A065B38B9DEE5BA9AEE` | 1000 | [49,58] | 0.209 | 0.211 |

> **API migration note**: The legacy `pyqpanda.QCloud` path (chip 72) returned `Quantum computer under maintenance` on two independent attempts (2026-08-21), so no further jobs were submitted on that path. The modern **QPanda3 Runtime** API (`RuntimeService`, device `WK_C180_2`) produced five separate supplemental packages (Bell, GHZ-3, Multi, Bell X, Bell Y). They are not required for the canonical L1 hardware ladder. The captured response exposes provider probabilities only; precise provider timestamps and per-shot counts are not exposed, and no replacement values are fabricated. Each package has a manifest and SHA-256 checked by `scripts/validate_runtime_evidence.py`.

## 6. Result distribution

- Canonical Bell: P(00) = 0.501, P(11) = 0.450, P(01) = 0.012, P(10) = 0.037; **target_mass** = P(00)+P(11) = **0.951**.
- Runtime Bell: P(00) = 0.458, P(11) = 0.542, P(01) ≈ 0.0002, P(10) ≈ 0.0001; **target_mass** ≈ **1.000**.
- Runtime GHZ-3: P(000) = 0.703, P(111) = 0.108, P(011) = 0.187. **Target-state population (000/111) ≈ 0.81, affected by hardware noise**; the remaining computational-basis states carry non-zero probability.
- Runtime Multi: P(00)=0.209, P(01)=0.278, P(10)=0.302, P(11)=0.211. Compared against the LoomQ reference simulator for the exact same circuit, the ideal distribution is uniform (0.25 each); the hardware result has **TVD ≈ 0.08**, classical fidelity ≈ 0.993 — consistent with the intended circuit.
- Runtime Bell X-basis (2026-08-22): P(00)=0.5206, P(11)=0.4792 → **Cxx = 0.99956** (job `CA80432C...`).
- Runtime Bell Y-basis (2026-08-22): P(01)=0.4752, P(10)=0.5241 → **Cyy = −0.99865** (job `5ABEAE90...`).

## 7. Reproducibility statistics

- canonical runs_completed: **1**; successful: **1**; failed: **0**.
- supplemental Runtime jobs: **5** (Bell, GHZ-3, Multi, Bell X-basis, Bell Y-basis); they are not repeated replicates and are not used for a stability metric.
- mean_execution_time_s (canonical): **0.313**.
- **stability_metric: null** for the canonical job — n=1, so std / min / max are **not** computed. A single run cannot establish statistical reproducibility; the three runtime jobs are diverse circuits, not repeated replicates of the same circuit, so they are not averaged into a stability metric.

## 8. Scientific limitations

- For the canonical Bell, n=1 gives **no** run-to-run variance estimate.
- **Z-basis computational-basis correlation alone does not witness entanglement.** A classical mixture could produce the same Z-basis marginals. The 2026-08-22 X/Y-basis jobs on the same device and physical qubits ([49,58]) give point estimates |Cxx|+|Czz|=1.999 and F_Phi+=0.9994, but the Runtime API exported provider probabilities rather than raw per-shot counts. No independently justified confidence interval is available, so these jobs are not used for a statistical entanglement or fidelity-threshold claim. See `SCIENTIFIC_CLAIMS_AUDIT.md` §2.2b and `files/bell-witness-analysis.json`.
- The GHZ-3 result is a real-QPU computational-basis distribution **affected by hardware noise**; it is **not** a noiseless perfect GHZ state, and it is **not** claimed to prove three-qubit entanglement (no multipartite witness was run on it).
- The Multi result is compared to the ideal simulator distribution (TVD ≈ 0.08); this is a distribution-consistency check, not an entanglement witness.

## 9. Traceability boundary

- This file and `files/originq-reproducibility-summary.json` contain **no token, Authorization, cookie, account, phone, or API key**.
- The canonical raw CSV SHA-256 `934772c966c3e889d2615d6528ff9012e9e4dc31aa11d614be47510ed3263bb4` matches the recorded metadata.
- The six jobs are fully separated into independent evidence packages (`originq-*` canonical, `originq_runtime_*` for the five new jobs); each package's manifest records job_id, device_id, physical qubits, shots, circuit, file SHA-256, data source, and any missing provider exports.
- This evidence is **participant-side**; it does **not** replace organizer verification and does **not** claim additional score.
