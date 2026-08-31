#!/usr/bin/env python3
"""Submit OpenQASM 2 to a live OriginQ QPU and atomically record evidence."""

import argparse
import json
import os
from pathlib import Path
import sys


STARTER_ROOT = Path(__file__).resolve().parents[2]
if str(STARTER_ROOT) not in sys.path:
    sys.path.insert(0, str(STARTER_ROOT))

from loomq.hardware.common import read_qasm_file
from loomq.hardware.errors import ConfigurationError, HardwareError
from loomq.hardware.evidence import record_evidence
from loomq.hardware.originq import build_dry_run, execute, load_credentials


DEFAULT_EVIDENCE_ROOT = STARTER_ROOT / "evidence" / "files" / "hardware"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qasm", required=True, help="UTF-8 OpenQASM 2 file")
    parser.add_argument("--shots", type=int, default=1000)
    parser.add_argument("--backend", help="real QPU backend name; otherwise QPANDA_QCLOUD_BACKEND")
    parser.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="validate only; no credentials, import, network, or write")
    mode.add_argument("--record", action="store_true", help="submit to a chip_info-qualified QPU and commit evidence")
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        source = read_qasm_file(args.qasm)
        backend_name = args.backend or os.environ.get("QPANDA_QCLOUD_BACKEND", "")
        if not backend_name:
            raise ConfigurationError("OriginQ backend is required via --backend or QPANDA_QCLOUD_BACKEND.")
        if args.dry_run:
            print(json.dumps(build_dry_run(source, args.shots, backend_name), indent=2))
            return 0

        credentials = load_credentials(backend_override=args.backend)
        bundle = execute(source, args.shots, credentials=credentials)
        evidence_path = record_evidence(
            args.evidence_root,
            bundle,
            secret_values=(credentials.api_key,),
        )
        print(
            json.dumps(
                {
                    "status": "recorded",
                    "provider": "originq",
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
