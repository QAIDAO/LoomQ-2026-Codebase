#!/usr/bin/env python3
"""Poll an existing OriginQ job_id. Does NOT submit a new task."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
    if len(sys.argv) < 2:
        print("usage: _poll_originq_job.py <job_id>", file=sys.stderr)
        return 2
    job_id = sys.argv[1].strip()
    _load_dotenv()
    token = (
        os.environ.get("LOOMQ_ORIGINQ_API_KEY")
        or os.environ.get("ORIGINQ_API_KEY")
        or ""
    ).strip()
    if not token:
        print("missing LOOMQ_ORIGINQ_API_KEY", file=sys.stderr)
        return 2

    import pyqpanda as pq

    machine = pq.QCloud()
    machine.init_qvm(token, False)
    print("querying", job_id, "token_len", len(token))
    raw_saved = None
    last_err = None
    try:
        for attempt in range(30):
            try:
                payload = machine.query_task_state_result(str(job_id), True)
                print(f"attempt {attempt} type={type(payload).__name__}")
                print("repr", repr(payload)[:1000])
                if isinstance(payload, tuple):
                    print("tuple_len", len(payload))
                    for index, item in enumerate(payload):
                        print(f"  [{index}] {type(item).__name__} {repr(item)[:500]}")
                    if len(payload) >= 2 and payload[1]:
                        raw_saved = payload[1]
                        break
                    # finished enum with empty raw — keep trying briefly
                elif isinstance(payload, dict) and payload:
                    raw_saved = payload
                    break
            except Exception as exc:  # noqa: BLE001 — surface SDK errors
                last_err = exc
                print(f"attempt {attempt} ERR {type(exc).__name__}: {exc}")
            time.sleep(2)
    finally:
        if hasattr(machine, "finalize"):
            machine.finalize()

    out_dir = ROOT / "evidence" / "files"
    out_dir.mkdir(parents=True, exist_ok=True)
    note = {
        "job_id": job_id,
        "chip_id": 180,
        "poll_note": "no new submit; recovery poll only",
        "last_error": repr(last_err) if last_err else None,
        "raw": raw_saved if isinstance(raw_saved, (dict, list)) else repr(raw_saved),
    }
    out = out_dir / "originq-bell-query-raw.json"
    out.write_text(json.dumps(note, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print("wrote", out)
    return 0 if raw_saved else 1


if __name__ == "__main__":
    raise SystemExit(main())
