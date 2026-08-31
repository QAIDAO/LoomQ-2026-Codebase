This is an AI-assisted cognitive walkthrough for regression detection. It is not a substitute for external human usability testing and is not counted as human-user evidence.

# Synthetic cognitive walkthrough

Date: 2026-08-25. Method: five agent-controlled, newly created local-browser tabs at the requested viewport sizes. Each tab started at the local candidate Web root and was judged only from rendered page state. No source, README, JUDGE_GUIDE, or quantum-knowledge search was used during the walkthrough.

Storage reset: `NOT RUN`. Browser safety rules prohibit inspecting or clearing cookies, localStorage, or sessionStorage through the browser-control surface. The security sweep separately checks the static assets for key persistence.

## Shared task

Each persona was asked to infer the purpose from the first screen and complete the existing Bell experiment without external reference material. The local Bell flow was exercised through the visible Bell CTA and local run control.

## Session observations

| Persona | Viewport | Goal legible | Bell CTA | Local Bell result | Notes |
|---|---:|---|---|---|---|
| A · humanities beginner | 390 × 844 | PASS | PASS | PASS | Hero gives a next step; no-key message is visible in the experiment route. |
| B · low technical familiarity | 1366 × 900 | PASS | PASS | PASS | API-key optionality and shots/repetition explanation are visible. |
| C · STEM without quantum background | 1440 × 900 | PASS | PASS | PASS | H/CNOT explanation, OpenQASM result surface, and science-boundary language are present. |
| D · fast mobile scan | 360 × 800 | PASS | PASS | PASS | No horizontal overflow detected; CTA and result route remained reachable. |
| E · English beginner | 430 × 900 | PASS | PASS | PASS | Language toggle, English Bell CTA, local run, measured-state table, and OpenQASM result surface were present. |

These are walkthrough observations, not participant counts, comprehension rates, completion rates, or usability scores.

## Common findings

- No blocker was observed in the tested local flow: each persona could locate the Bell entry and the local result surface at the tested viewport.
- The no-key message is explicit: the saved Bell example can run locally without an LLM connection.
- The result surface exposes counts, verification, circuit, and the OpenQASM that ran.
- The page explicitly distinguishes one-basis `00/11` correlation from the need for more measurement directions and reconstruction.
- The page is long and information-dense. A real human review should still check whether a fast-scanning newcomer notices the Bell CTA without reading the full path.

## Persona-specific edge cases

- Mobile widths 390 and 360 had no detected document horizontal overflow in the read-only layout check.
- The English route uses localized labels such as `Repeat the Bell experiment` and `Run this experiment`; this is a localization check, not a failure of the Chinese labels.
- Tooltip clicks were not exercised in this pass; their presence was observed in the rendered DOM. This remains a manual follow-up.
- No genuine first-time participant or external human was used.

## Status

- Checked by this synthetic pass: hero direction, no-key Bell path, local run, result surface, mobile overflow heuristic, and English route presence.
- Not established: human comprehension, human ease ratings, blind-test rates, human discovery latency, accessibility conformance, or external device behavior.
- Required next evidence: a real external novice round recorded in `NOVICE_BLIND_TEST.md`; until then the newcomer bonus remains `WAIT_FOR_HUMAN_FINAL_REVIEW`.
