#!/usr/bin/env python3
"""Submit OpenQASM 2 to a live SpinQ QPU and atomically record evidence."""

import argparse
import json
from pathlib import Path
import sys


STARTER_ROOT = Path(__file__).resolve().parents[2]
if str(STARTER_ROOT) not in sys.path:
    sys.path.insert(0, str(STARTER_ROOT))

from loomq.hardware.common import read_qasm_file
from loomq.hardware.errors import HardwareError
from loomq.hardware.evidence import record_evidence
from loomq.hardware.spinq import build_dry_run, execute, load_credentials


DEFAULT_EVIDENCE_ROOT = STARTER_ROOT / "evidence" / "files" / "hardware"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qasm", required=True, help="UTF-8 OpenQASM 2 file without explicit measure statements")
    parser.add_argument("--shots", type=int, default=1000, help="must be 1000 for the official 0.0.2 submitter")
    parser.add_argument("--platform-code", required=True, help="live platform pcode returned by SpinQ discovery")
    parser.add_argument("--task-name", default="loomq-hardware-evidence")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="validate only; no credentials, import, network, or write")
    mode.add_argument("--record", action="store_true", help="submit to a proven QPU and commit a complete evidence bundle")
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        source = read_qasm_file(args.qasm)
        if args.dry_run:
            print(json.dumps(build_dry_run(source, args.shots, args.platform_code, args.task_name), indent=2))
            return 0

        credentials = load_credentials()
        bundle = execute(
            source,
            args.shots,
            args.platform_code,
            args.task_name,
            credentials=credentials,
            timeout_seconds=args.timeout,
            poll_interval=args.poll_interval,
        )
        evidence_path = record_evidence(
            args.evidence_root,
            bundle,
            secret_values=(credentials.username, str(credentials.private_key_path)),
        )
        print(
            json.dumps(
                {
                    "status": "recorded",
                    "provider": "spinq",
                    "backend": bundle.normalized_result["backend"],
                    "job_id": bundle.normalized_result["job_id"],
                    "evidence_path": str(evidence_path),
                },
                indent=2,
            )
        )
        return 0
    except HardwareError as exc:
        print(json.dumps({"status": "error", "message": str(exc)}), file=sys.stderr)
        return 2
    except Exception:
        print(
            json.dumps(
                {"status": "error", "message": "Unexpected runner failure; raw exceptions were suppressed to protect credentials."}
            ),
            file=sys.stderr,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
