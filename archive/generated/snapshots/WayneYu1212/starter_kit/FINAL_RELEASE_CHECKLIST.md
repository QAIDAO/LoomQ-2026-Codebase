# LoomQ release checklist — candidate evidence handoff

> This document records candidate evidence and boundaries; authoritative submission identity and acceptance are determined by the upstream Final Submission Issue.

## Candidate identity

- Base UX candidate: `98d2ce03c927fab57ec12f7901652880c33afa2a`.
- Current candidate identity: `git rev-parse HEAD`.
- Final submitted identity: the exact 40-character SHA recorded in the Final Submission Issue.
- Earlier accepted fallback reference: Issue `#119` is historical context only; authoritative current submission identity and acceptance are determined by the upstream Final Submission Issue.
- Submission state: use the upstream Final Submission Issue and its archive receipt as the authoritative external record.
- Theoretical maximum `112` is not an awarded score.
- Final product Demo: `evidence/files/loomq-final-demo.mp4` — 8,817,627 bytes; SHA-256 `b4efb73bedeba32766e7a4a62d3149a6790352e038738a322efd08587d9d4ab2`; byte-identical to the user-provided reviewed file. No original 200+ MB recording is included.

## P0 backend merge

The candidate contains the backend polarity correction and its regression test:

- `zero_queue=true` requires `queue="none"`.
- `zero_queue=false` or null leaves queueing allowed.
- `kind=qpu` preserves a real hardware request; account and cost constraints remain explicit.
- The red-before-fix test was observed once; the corrected P0 test passes 1/1.

## Final-candidate L2 evidence

| Gate | Result | Boundary |
|---|---:|---|
| `backend-34-cloud-sim` post-fix gate | 5/5 PASS | Five distinct real-model runs; canonical `braket_cloud`; no rerun substitution |
| `backend-40-real` repeated gate | 5/5 PASS | Five distinct real-model runs; canonical `originq_wukong`; no rerun substitution |
| Old 12 unseen paraphrases | 12/12 PASS | Fresh prompts; canonical backend IDs; no provider timeout or semantic failure |
| New cloud-simulator paraphrases | 8/8 PASS | Chinese/English coverage; cloud simulator, 34 qubits, no local simulator, QPU not required, queue/registration unspecified or allowed |
| Balanced 6-case gate | 6/6 PASS | 2 generation + 2 repair + 2 backend recommendation |
| Full interleaved 30-case smoke | 29/30 | Provider timeout 0; the retained semantic failure is `backend-9-real`; this remains 29/30, not 30/30 |
| `backend-9-real` subsequent diagnostic replay | 3/3 PASS | Diagnostic replay only; stochastic residual; does not overwrite or replace the original 29/30 smoke |
| Agent service | 10/10 PASS | Local unit/integration contract |
| Timeout/campaign/watchdog focused tests | 18/18 PASS | Local regression |
| Historical Clean V2 | 499/500 | Retained historical record; not rewritten or relabeled as current |

The retained failure in the original full 30-case smoke is evidence, not discarded noise:

- `backend-9-real`: semantic failure.
- A subsequent three-run `backend-9-real` diagnostic replay returned 3/3 PASS. It is a separate stochastic-residual diagnostic and does not overwrite the original 29/30 smoke result.
- The final current failure set contains only `backend-9-real`; the post-fix `backend-34-cloud-sim` gate is 5/5 PASS with canonical `braket_cloud`.
- The final 30-case smoke recorded zero provider timeouts.

## Regression status

- Starter suite: 138/138.
- Organizer suite: 26/26.
- L1 public evaluator: PASS — 6/6 in a fresh temporary output file; canonical evidence was not overwritten.
- Public L2 fake protocol test: PASS — 1/1, one local HTTP model call.
- L3 evaluator: PASS — 1/1 public branch.
- Quantum RISC-V focused/adversarial tests: PASS — 12/12.
- Web asset/server checks: PASS — local HTTP homepage and `/api/health` returned 200; browser QA covered the final local route at 390, 360, 430, 1366, and 1440 widths, including the English control path.
- `node --check`: PASS. `compileall`: PASS. `pip check`: PASS. `git diff --check`: PASS.
- `mypy starter_kit/loomq`: PASS — no issues in 29 source files.

## Evidence and human-review boundaries

- Canonical SpinQ and OriginQ hardware evidence remains unchanged. No new hardware job was submitted.
- The five `WK_C180_2` Runtime packages remain supplemental and do not replace canonical OriginQ.
- Synthetic cognitive walkthrough is AI-assisted regression detection, not external human usability evidence.
- Final product Demo was provided and human-confirmed by the user at the canonical path above; no new recording was made and no duplicate video was added.
- Science text is a reference-based technical review, not a physical-expert endorsement.
- Provenance, raw exports, manifests, metadata, checksums, and hashes were not rewritten for tidiness.

## Final sweeps

- `SECURITY_SWEEP.md`: PASS for current tree, staged diff, history, static assets, storage-source boundary, and personal-path scan; no secret values were printed.
- `SCIENTIFIC_CLAIMS_AUDIT.md`: PASS as a reference-based final UX wording diff; it is not a physical-expert endorsement.
- `CLEAN_ROOM_REPRODUCTION.md`: PASS in a fresh no-hardlinks clone and new Python 3.10.11 venv; Docker was unavailable and the development `.venv` did not count.
- `prepare_submission.py --team-id WayneYu1212`: run against the clean candidate after its `origin` ref contains the exact SHA; its output is the local preflight source of truth.

## Human handoff

Submission identity, remote state, organizer evidence, real-device claims and final UI/device review remain governed by the upstream Final Submission Issue and organizer review.
