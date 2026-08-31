#!/usr/bin/env python3
"""Run Bell on a cloud backend and write evidence files (local helper).

Does not submit to the competition by itself. Secrets stay in the environment /
starter_kit/.env (gitignored). Usage examples:

  export LOOMQ_ORIGINQ_API_KEY=...
  export LOOMQ_ORIGINQ_MODE=wukong
  PYTHONPATH=starter_kit python starter_kit/tools/run_bell_evidence.py --platform originq

  # SpinQ cloud wiring depends on your account; local spinq simulator also works
  # for a dry-run of the file layout (not valid as hardware evidence):
  PYTHONPATH=starter_kit python starter_kit/tools/run_bell_evidence.py --platform spinq --allow-simulator
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BELL = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;
"""


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and not os.environ.get(key):
            os.environ[key] = value


def main() -> int:
    parser = argparse.ArgumentParser(description="Save Bell run evidence JSON")
    parser.add_argument("--platform", choices=("originq", "spinq", "braket"), required=True)
    parser.add_argument("--shots", type=int, default=1024)
    parser.add_argument(
        "--allow-simulator",
        action="store_true",
        help="allow local simulator results (NOT valid LoomQ hardware evidence)",
    )
    args = parser.parse_args()
    _load_dotenv()

    from adapter import run

    if args.platform == "originq" and not args.allow_simulator:
        mode = (os.environ.get("LOOMQ_ORIGINQ_MODE") or "").strip().lower()
        if mode not in {"wukong", "cloud", "qpu", "real", "chip"}:
            print(
                "Set LOOMQ_ORIGINQ_MODE=wukong (and API key) for hardware evidence, "
                "or pass --allow-simulator for a layout dry-run.",
                file=sys.stderr,
            )
            return 2
    if args.platform == "spinq" and not args.allow_simulator:
        mode = (os.environ.get("LOOMQ_SPINQ_MODE") or "").strip().lower()
        if mode not in {"cloud", "qpu", "real", "nmr", "gemini"}:
            print(
                "Set LOOMQ_SPINQ_MODE=cloud plus LOOMQ_SPINQ_USERNAME / "
                "LOOMQ_SPINQ_KEYFILE for hardware evidence, or pass "
                "--allow-simulator for a layout dry-run.",
                file=sys.stderr,
            )
            return 2

    try:
        result = run(BELL, args.platform, args.shots)
    except Exception as exc:
        # If a job_id is already in the message, print it loudly — never resubmit.
        print(f"OriginQ/SpinQ run failed: {exc}", file=sys.stderr)
        print(
            "If a job_id appears above, open the cloud console and archive that job. "
            "Do not rerun this script to 'retry' the same submission.",
            file=sys.stderr,
        )
        return 1

    backend = str(result.get("backend", ""))
    if not args.allow_simulator and (
        "sim" in backend.lower() or "local" in backend.lower()
    ):
        print(
            f"Refusing to treat simulator backend {backend!r} as hardware evidence. "
            "Use cloud mode or --allow-simulator.",
            file=sys.stderr,
        )
        return 3

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "evidence" / "files"
    out_dir.mkdir(parents=True, exist_ok=True)
    qasm_path = out_dir / f"{args.platform}-bell.qasm"
    result_path = out_dir / f"{args.platform}-bell-result-{stamp}.json"
    canonical = out_dir / f"{args.platform}-bell-result.json"
    qasm_path.write_text(BELL, encoding="utf-8")

    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    originir = meta.get("submitted_originir")
    if args.platform == "originq" and isinstance(originir, str) and originir.strip():
        ir_path = out_dir / "originq-bell.originir"
        ir_path.write_text(originir if originir.endswith("\n") else originir + "\n", encoding="utf-8")
        print("wrote", ir_path)

    # Canonical evidence JSON: keep schema fields; stash submitted IR paths in note-friendly meta.
    evidence = dict(result)
    evidence_meta = dict(meta)
    evidence_meta.pop("submitted_originir", None)  # already written as .originir file
    evidence_meta.pop("submitted_qasm", None)
    evidence_meta["evidence_qasm"] = str(qasm_path.relative_to(ROOT))
    if args.platform == "originq":
        evidence_meta["evidence_originir"] = "evidence/files/originq-bell.originir"
    evidence["meta"] = evidence_meta

    payload = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    result_path.write_text(payload, encoding="utf-8")
    canonical.write_text(payload, encoding="utf-8")

    print("wrote", qasm_path)
    print("wrote", result_path)
    print("wrote", canonical)
    print("backend:", evidence.get("backend"))
    print("job_id:", evidence.get("job_id"))
    print("shots:", evidence.get("shots"))
    print("counts:", evidence.get("counts"))
    print("chip_id:", evidence_meta.get("chip_id"))
    counts = evidence.get("counts") or {}
    if isinstance(counts, dict) and counts:
        peak = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:2]
        print("top counts:", peak)
    print(
        "SUCCESS path: fill starter_kit/evidence/README.md (job_id/time/chip/shots/"
        "00+11 peaks), commit+push, then open a NEW Final Issue only after that. "
        "Keep API keys out of git. MODE back to local after the run."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
