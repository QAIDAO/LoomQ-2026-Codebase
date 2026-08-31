#!/usr/bin/env python3
"""Run the official-family round-trip and optional vendor parser checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loomq.verification import (  # noqa: E402
    verify_official_family_roundtrips,
    verify_vendor_executions,
    verify_vendor_parsers,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-native",
        action="store_true",
        help="fail instead of skip when a vendor SDK is unavailable",
    )
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    records = verify_official_family_roundtrips()
    records.extend(verify_vendor_parsers(require_native=args.require_native))
    records.extend(verify_vendor_executions(require_native=args.require_native))
    payload = [record.to_dict() for record in records]
    if args.json_out:
        args.json_out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    for record in records:
        print(
            f"[{record.status.upper()}] "
            f"{record.case}/{record.target}/{record.check}: {record.detail}"
        )
    return 1 if any(record.status == "fail" for record in records) else 0


if __name__ == "__main__":
    raise SystemExit(main())
