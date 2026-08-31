# LoomQ novice blind test — final human evidence

> Small-N qualitative usability evidence from two independent low-background sessions. This is not a statistically representative user study and is not organizer feedback.
>
> No names, emails, phone numbers, or other identifying information are included in this report.

## Scope and evidence boundary

This report records the final human tally for a closed-book usability check of the LoomQ onboarding path. Round 1 and Round 2 are reported as two independent low-background sessions.

The evidence supports only a qualitative comparison of observed misunderstandings and task completion in these sessions. It does not support population-level claims, statistical significance, completion-rate estimates, or a claim that all zero-background users can understand quantum computing or LoomQ.

Synthetic AI walkthroughs, if present elsewhere in the repository, are not human participants and are not counted in this evidence.

## Round 1 — baseline session

Submission time: 2026-08-24 09:20:28 UTC

Device: laptop
Prior quantum background: had heard terms such as qubit / entanglement but could not explain them

Observed outcomes:

| Measure | Baseline result |
|---|---|
| Product goal after hero | Goal unclear; the participant only knew it was related to quantum computing and did not know what the site wanted them to do |
| Explain qubit unaided | Could recognize the wording but could not explain it |
| `|0⟩` | Understood only after opening the tooltip |
| H | Incorrect — mistaken for a type/model of quantum computer |
| CNOT | Correct |
| Bell purpose | Correct |
| API key required for ready-made Bell | Incorrect — thought an API key was mandatory |
| Independent Bell run | Did not attempt Bell |
| First point of confusion | Quantum computing / qubit introduction |
| Tooltip usefulness | A little helpful |
| Overall ease | 1 / 5 |
| Willingness to continue with own quantum question | Completely unwilling |

## Round 2 — final participant session

Submission time: 2026-08-24 17:45:46 UTC

Device: mobile

First time seeing LoomQ: **yes**
Prior quantum background: almost no prior quantum knowledge; had only heard of quantum computing

Final participant record:

- H: correct.
- CNOT: correct.
- Bell purpose: correct.
- `1024 shots`: correct — repeat the same circuit 1024 times and count outcomes.
- API optionality: correct — the ready-made Bell/local path does not require an API key.
- Independent Bell run: completed independently, with some searching and hesitation.
- First confusion: experiment area / shots / backend.
- Overall ease: 3 / 5.

Observed outcomes:

| Measure | Final result |
|---|---|
| Product goal after hero | Very clear — understood that the site would help them understand and run a minimal two-qubit experiment |
| Explain qubit unaided | Roughly able to explain |
| `|0⟩` | Understood after opening the tooltip |
| H | Correct |
| CNOT | Correct |
| Bell purpose | Correct |
| `1024 shots` | Correct — repeat the same circuit 1024 times and count outcomes |
| API key required for ready-made Bell | Correct — no API key required |
| Independent Bell run | **Succeeded**, with some searching / hesitation |
| First point of confusion | Experiment area / shots / backend |
| Tooltip usefulness | Very helpful; the participant actively used them |
| Overall ease | 3 / 5 |
| Willingness to continue with own quantum question | Uncertain |

## Observed before / after boundary

The strongest observed changes between these two independent sessions were:

1. **Goal clarity:** from quantum-related but unclear to a clear understanding of the two-qubit/Bell task.
2. **H comprehension:** from a concrete computer-model misconception to the intended operational meaning.
3. **API-key misconception:** from believing a key was mandatory to correctly understanding that the ready-made Bell/local path works without one.
4. **Independent execution:** from not attempting a run to successfully completing the Bell experiment.
5. **Perceived ease:** from 1/5 to 3/5.

The final session still showed a usability boundary: confidence first decreased around the experiment controls, shots, and backend concepts, and the Bell run was completed with hesitation rather than effortlessly.

## What this evidence does and does not show

This evidence supports a qualitative claim that the final onboarding addressed several concrete failure modes observed in the earlier low-background session.

It does not show that the result is statistically representative, statistically significant, population-wide, or true for all beginners. It does not prove that all zero-background users can understand quantum computing or complete the flow in five minutes.

Synthetic personas and AI walkthroughs remain separate regression material. They are not human users and are not included in the session count or interpretation above.

## Judge-facing one-line summary

> In two independent low-background sessions, the baseline exposed concrete misunderstandings around the site goal, H, API-key requirements, and experiment execution; the final first-time mobile participant correctly understood H/CNOT/shots/API optionality and independently completed the Bell experiment, while still showing some hesitation around backend and experiment controls.
