# LoomQ scoring self-audit

`TARGET: 112` is the official theoretical maximum, not an awarded score.

| Area | Target | Status | Evidence boundary |
|---|---:|---|---|
| L1 software/semantic | 35 | OBJECTIVELY VERIFIED | Three SDK runners; public and hidden-shape local regression |
| L1 genuine hardware | 10 | TWO-PLATFORM EVIDENCE READY / ORGANIZER TRACEABILITY REVIEW | **Only the designated canonical packages are relied upon here**: SpinQ `G-260820-0008` and OriginQ `D0C7F...B342`, both covered by the canonical validator. Earlier accepted submissions are historical context only. The five `WK_C180_2` Runtime packages are supplemental only: not a replacement for canonical OriginQ, not an additional hardware platform, and not relied upon for this +10 ladder. Their independent validator checks job separation, QASM, provider probabilities, SHA-256 and no fabricated timestamps/counts. |
| L2 objective | 20 | OBJECTIVELY VERIFIED (public contract) + LOCAL REAL-MODEL STRESS | Real HTTP model call in public fake; historical 102-case stress remains in `L2_REAL_MODEL_VALIDATION.md`; formal private semantics remain organizer-scored |
| L2 final-candidate gate | — | LOCALLY VERIFIED / ORGANIZER-SCORED SEMANTICS REMAIN SEPARATE | P0 backend-34-cloud-sim post-fix: 5/5 (`braket_cloud`); backend-40-real: 5/5 (`originq_wukong`); old 12 unseen paraphrases: 12/12; new cloud-simulator paraphrases: 8/8; balanced 6-case gate: 6/6; full 30-case smoke: 29/30, provider timeout 0, retained semantic failure `backend-9-real`; subsequent diagnostic replay: 3/3 stochastic residual, not a replacement |
| L2 interaction | 10 | MANUAL REVIEW CLAIMED | Runnable Web, three tasks, screenshots, structured recovery |
| L3 | 15 | OBJECTIVELY VERIFIED (public + local randomized) | Public evaluator; reference-interpreter randomized tests |
| Engineering/productization | 10 | MANUAL REVIEW CLAIMED | Setup/verify scripts, architecture, pinned SDKs, safe boundaries |
| Custom quantum RISC-V | +8 | OBJECTIVELY VERIFIED locally / BONUS CLAIMED | Encoding spec, emulator extension, `.word` E2E |
| Newcomer/visual narrative | +4 | MANUAL REVIEW CLAIMED | Recommended no-LLM path, readable Web, scientific boundary |

## Current ceiling

- Software/manual opportunities claimed: `102 / 112` theoretical ceiling before hardware.
- Two-platform hardware evidence is packaged for the `10`-point ladder: SpinQ `G-260820-0008` and OriginQ `D0C7F...B342`.
- `112` is the official **theoretical ceiling**, not an awarded score. Earlier accepted submissions are historical context only; authoritative current submission identity and acceptance are determined by the upstream Final Submission Issue. Manual/private judging and organizer hardware traceability review remain organizer-controlled. Organizers determine the awarded score.

Local validation cannot award manual points or prove a remote job exists. Organizers retain final scoring and may log in to verify hardware IDs.

## Final candidate evidence

The P0 backend fix is present in this candidate: `zero_queue=true` requires `queue="none"`; `zero_queue=false` or null leaves queueing allowed; QPU requests preserve the canonical hardware target. The regression is covered by the agent-service tests.

The historical Clean V2 record remains `499/500` with its retained provider-transient failure. It is not rewritten as evidence for this candidate. The current full smoke record is `29/30`, with zero provider timeouts and one retained semantic failure (`backend-9-real`) described in `FINAL_RELEASE_CHECKLIST.md`. Its subsequent `3/3` replay is a separate diagnostic marked stochastic residual and does not replace the original smoke record.
