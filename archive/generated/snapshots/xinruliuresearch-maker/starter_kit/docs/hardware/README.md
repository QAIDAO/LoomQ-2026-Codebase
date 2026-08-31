# Real-hardware preparation

This directory contains the reproducible path for collecting evidence from a
SpinQ or OriginQ **real QPU**.  The repository intentionally contains no
credentials and no fabricated hardware output.  Until an account owner runs one
of the `--record` commands successfully, `evidence/files/hardware/` contains only
`.gitkeep`.

## Safety boundary

The runners have two mutually exclusive modes:

- `--dry-run` validates the QASM and command.  It does not load a vendor SDK,
  read credentials, access the network, write evidence, or create a job ID.
- `--record` is the only submitting mode.  It requires credentials, proves that
  the selected target is a QPU, waits for a complete vendor response, validates
  counts, then atomically commits all five evidence artifacts.

A cloud simulator is not hardware evidence.  A submission receipt without a
completed result is not hardware evidence.  A locally invented ID is never
accepted as a job ID.

## Runbooks

- [SpinQ Cloud](SPINQ_RUNBOOK.md)
- [OriginQ QCloud](ORIGINQ_RUNBOOK.md)
- [Evidence contract](EVIDENCE_CONTRACT.md)
- [Official API sources and pinned audit](OFFICIAL_API_SOURCES.md)

Vendor SDKs are optional runtime dependencies and are deliberately absent from
the main `requirements.txt`.  Install each SDK in its own Python 3.10 virtual
environment as described in its runbook.

## External actions still required

At least one account owner must supply a valid account/API key, select an
available real-QPU backend, accept any vendor terms or quota consumption, and run
`--record`.  Those actions cannot be completed safely from an anonymous local
environment.
