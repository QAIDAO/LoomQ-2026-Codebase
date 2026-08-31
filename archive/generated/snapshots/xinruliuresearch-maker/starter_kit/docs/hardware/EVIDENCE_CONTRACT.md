# Hardware evidence contract

One successful `--record` creates one randomly named directory under
`evidence/files/hardware/`.  A same-filesystem rename commits the directory only
after every artifact is fully written and flushed.

## Required files

| File | Content |
| --- | --- |
| `input.qasm` | Exact UTF-8 QASM submitted to the vendor adapter |
| `submission.json` | Non-secret request summary and sanitized acceptance response |
| `raw_result.json` | Sanitized vendor result; credential-like fields are redacted |
| `normalized_result.json` | Backend, vendor job ID, shots, counts, bit-order declaration, zoned timestamp, QPU metadata |
| `metadata.json` | Independent QPU qualification, provider/version, job ID, zoned timestamps, and SHA-256 hashes of the other four files |

## Admission invariants

The recorder rejects the bundle before creating its root if any invariant fails:

- `execution_kind == "qpu"` and `qpu_verified == true` in metadata;
- native vendor SDK use is explicitly true in normalized metadata;
- backend and vendor-issued job ID are non-empty;
- `shots` is a positive integer;
- counts are non-empty, uniform-width binary keys with non-negative integer
  values and sum exactly to shots;
- job ID agrees between metadata and normalized result; and
- completion/record timestamps are ISO-8601 strings with a timezone.

`bit_order` is recorded as `vendor_native` because the reviewed vendor sources
do not establish one common cross-vendor endian convention.  The metadata sets
`bit_order_verified: false`; no unverified reversal is applied.

## Redaction

Recursive redaction replaces values under key names containing API key, token,
authorization, credentials, password, private key, signature, username, email,
or secret.  Explicit credential values supplied by the runner are also replaced
if they appear inside vendor text.  Credential values and raw vendor exceptions
are never printed by the CLI.

## Non-evidence

The following must not be moved into this directory or described as hardware:

- local/reference simulation;
- a cloud simulator;
- dry-run output;
- a submission receipt without completed counts;
- an invented or local job ID;
- a manually edited result; or
- a failed/timeout response.
