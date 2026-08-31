# Genuine two-platform hardware evidence

This package contains two distinct eligible platform families. It is intended for the official L1 hardware ladder; final traceability and score remain subject to organizer login review.

## SpinQ Cloud

- Device: SpinQ Cloud 2-qubit NMR quantum computer
- Job code: `G-260820-0008`
- Platform task ID / URL: `61373` · `https://cloud.spinq.cn/circuitDesign/taskResult/61373`
- Created / started / completed: `2026-08-20 19:13:25 / 19:13:42 / 19:15:15 UTC+8`
- Circuit: exact provider-exported OpenQASM bytes are preserved losslessly as `files/spinq-hardware-bell.raw.qasm.gz` with original SHA-256 recorded in metadata; a whitespace-clean semantic copy is `files/spinq-hardware-bell.qasm` (`H`, `CX` Bell preparation)
- Raw result: provider-exported 49-byte MessagePack, SHA-256 `b7a66c66a5d69aaeda2857a8ba99d08f1f0a214671c02740be434ea3aa72d195`
- Raw probabilities: `00=0.42899157`, `01=0.02230567`, `10=0.04003949`, `11=0.50866326`
- Shots: N/A. The NMR task page/export exposes ensemble projection probabilities rather than a discrete shot count; none is fabricated.
- Main evidence: `files/spinq-hardware-metadata.json`, `files/spinq-hardware-task.png`

The dominant states are `00` and `11`, consistent with Bell correlation. The screenshot account region is deterministically redacted; task/result pixels are preserved.

## Origin Quantum Cloud

- Device: Origin Wukong 180-2
- Job ID / URL: `D0C7F490B43D9B04FDF19ABF3DB8B342` · `https://console.originqc.com.cn/zh/jobs/D0C7F490B43D9B04FDF19ABF3DB8B342`
- Created / completed: `2026-08-20 20:29:51.026 / 21:16:43.073 UTC+8`
- Shots: `1000`
- Physical qubits: `q[49]`, `q[58]`
- Chip execution time: `0.313 s`
- Raw provider CSV probabilities: `00=0.501`, `01=0.012`, `10=0.037`, `11=0.450`
- Derived counts: `501 / 12 / 37 / 450`. The derivation is exactly probability × 1000; the untouched CSV remains authoritative.
- Circuit: faithful reconstruction from the exported logical SVG (`H(q0), H(q1), CZ(q0,q1), H(q1), measure`), with provider physical mapping retained separately.
- Main evidence: `files/originq-hardware-metadata.json`, `files/originq-hardware-task.png`

## Validation

```powershell
.\.venv\Scripts\python.exe -m starter_kit.hardware.validate_evidence `
  starter_kit\evidence\files\spinq-hardware-metadata.json `
  starter_kit\evidence\files\originq-hardware-metadata.json
```

Local validation checks structure, paths, timestamps, provider families, non-simulator identity, distributions and secret-like fields. It cannot prove remote traceability; organizers may log in and verify both task IDs.
