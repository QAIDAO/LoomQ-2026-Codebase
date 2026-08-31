# L2 provider profiles and model probe design

## Goal

Keep the LoomQ L2 submission contract unchanged for formal scoring while making
local L2 testing convenient across OpenAI-compatible providers. Add a safe
batch probe for the text chat models available to a configured provider.

The formal evaluator remains authoritative: `adapter.agent_chat(prompt)` reads
only `LOOMQ_LLM_BASE_URL`, `LOOMQ_LLM_API_KEY`, and `LOOMQ_LLM_MODEL`; it must
work with the evaluator-injected `deepseek-v4-flash` service and must not rely
on a provider SDK, account-specific endpoint, or public network access.

## Scope

- Add named, secret-free local provider presets for Bailian Token Plan,
  Bailian DashScope, OpenAI, DeepSeek, and a custom OpenAI-compatible service.
- Add CLI options to select a preset and override the model for a single local
  invocation without writing secrets or changing the formal contract.
- Add a model probe command that exercises the three L2 task families:
  generation, repair, and backend selection.
- Report per-model and per-task result, elapsed time, and a redacted error.
- Do not support image, video, audio, embedding, reranking, or provider SDK
  APIs; these are outside the L2 Chat Completions interface.

## Architecture

`llm_client.py` remains the sole HTTP transport. A new provider-profile module
maps a provider name to a default OpenAI-compatible base URL and model, then
builds a temporary environment mapping. Formal `agent_chat` never selects a
profile and reads the three injected `LOOMQ_LLM_*` values unchanged. For local
CLI use only, an explicit `--provider` temporarily supplies that provider's
base URL and default model; an explicit `--base-url` or `--model` wins over the
profile. The API key always comes from `LOOMQ_LLM_API_KEY` (or an explicitly
named local key environment variable), never from a profile file.

`l2_cli.py` gains `--provider`, `--model`, and `--models-file` options. Normal
single-prompt mode still calls `agent_chat` once. Probe mode calls the same
`agent_chat` path for each selected model and never bypasses LoomQ validation.

The probe task set uses the three task types specified in the competition
manual: a variable-size GHZ generation request, a malformed Bell-state repair
request, and a constrained backend-selection request. These are local smoke
tests, not a substitute for the organizer's private prompt variants.

The probe validates more than transport success: returned QASM is simulated
against the declared local task intent, and a backend reply is checked against
the capability-table answer set. This makes a local pass meaningful without
encoding the organizer's private prompt strings.

## Model discovery and cost controls

Provider model catalogues do not reliably encode account entitlement. The probe
therefore accepts an explicit model list from `--models-file` or repeated
`--model`; each entry is attempted and reported as supported or unavailable.

The command defaults to dry-run output and requires an explicit `--execute`
flag for network calls. `--all` means all models in the supplied model list,
not every catalog item globally. This avoids accidentally invoking non-text
models or an unbounded paid catalogue. No API key, authorization header, or
raw provider response metadata is written to reports.

## Error handling

- Invalid provider names, missing required environment variables, and empty
  model lists fail before any request.
- A failure for one model/task is recorded and does not stop the remaining
  explicitly selected models.
- The normal L2 agent preserves its one-repair limit. When its generated QASM
  or backend answer fails local validation, the concise validator reason is
  included in that repair request so the model can correct its own output.
- A final CLI failure is classified as configuration, transport, API response,
  or output-validation failure and includes a precise, deterministic next
  action. Configuration errors name the missing or malformed variable;
  transport errors name the configured host and timeout; API errors include
  the HTTP status and a provider request ID when supplied in a response header;
  validation errors include the parser's safe line/reason or the unmet semantic
  condition. It never prints an API key, authorization header, or provider
  response body.
- Batch reports retain the same safe error category and concise reason, so a
  user can change a model/profile and retry only failed cases.

## Verification

- Unit-test profile precedence, no-secret configuration handling, and invalid
  profile rejection.
- Unit-test probe aggregation with mocked L2 calls for pass, validation failure,
  and transport failure.
- Unit-test the repair prompt's validator feedback and every user-facing error
  category to ensure no credential substring is exposed.
- Unit-test exact remediation text for a missing variable, malformed URL,
  timeout, HTTP failure, invalid QASM, and semantic mismatch.
- Preserve and re-run existing L2 agent/CLI contract tests.
- Run a real local probe only after the user provides a bounded model list and
  explicitly authorizes its cost.

## Non-goals

- No changes to the `agent_chat` signature, `submission.yaml` L2 contract, or
  the organizer-injected runtime behavior.
- No claim that local provider results predict the official DeepSeek score.
- No storage of credentials, provider configuration files containing keys, or
  automated full-catalog billing sweep.
