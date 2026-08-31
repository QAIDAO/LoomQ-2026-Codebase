#!/usr/bin/env python3
"""Find today's LoomQ web task in the configured SpinQ account without submitting."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys


STARTER_KIT = Path(__file__).resolve().parents[1]
REPOSITORY = STARTER_KIT.parent
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

from loomq.hardware import extract_spinq_counts, load_env_file  # noqa: E402


def main() -> int:
    from spinqit import get_spinq_cloud

    config = load_env_file(REPOSITORY / ".env.hardware.local")
    backend = get_spinq_cloud(
        config["LOOMQ_SPINQ_USERNAME"],
        config["LOOMQ_SPINQ_KEYFILE"],
        config["LOOMQ_SPINQ_HOST"],
    )
    date_code = datetime.now(timezone.utc).strftime("%y%m%d")
    matches = []
    for sequence in range(1, 101):
        task_id = f"G-{date_code}-{sequence:04d}"
        try:
            response = backend._api_client.get_task_by_code(task_id)
            if response.status_code != 200:
                continue
            payload = json.loads(bytes(response.content).decode("utf-8"))
        except Exception:
            continue
        task = payload.get("task") if isinstance(payload, dict) else None
        if not isinstance(task, dict):
            continue
        name = str(task.get("tname") or task.get("taskName") or task.get("name") or "")
        if name.startswith("LoomQ-web-"):
            match = {
                "job_id": task_id,
                "task_name": name,
                "status": task.get("tstatus"),
                "created_at": task.get("createdTime") or task.get("created_time"),
            }
            result_response = backend._api_client.task_result(task_id)
            if result_response.status_code in (200, 202):
                result = json.loads(bytes(result_response.content).decode("utf-8"))
                run = result.get("run") if isinstance(result, dict) else None
                if isinstance(run, dict) and (run.get("count") or run.get("module")):
                    match["counts"] = extract_spinq_counts(
                        result, shots=int(task.get("shots") or 1024), width=2
                    )
            matches.append(match)
    print(json.dumps({"matches": matches}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
