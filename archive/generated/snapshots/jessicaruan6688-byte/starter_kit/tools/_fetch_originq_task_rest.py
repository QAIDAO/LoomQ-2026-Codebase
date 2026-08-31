#!/usr/bin/env python3
"""Fetch OriginQ task detail by job_id via REST. Does NOT submit."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DETAIL_URL = "http://pyqanda-admin.qpanda.cn/api/taskApi/getTaskDetail.json"


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
        print("usage: _fetch_originq_task_rest.py <job_id>", file=sys.stderr)
        return 2
    job_id = sys.argv[1].strip()
    _load_dotenv()
    token = (os.environ.get("LOOMQ_ORIGINQ_API_KEY") or "").strip()
    if not token:
        print("missing LOOMQ_ORIGINQ_API_KEY", file=sys.stderr)
        return 2

    payload = json.dumps({"taskId": job_id, "apiKey": token}).encode("utf-8")
    request = urllib.request.Request(
        DETAIL_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print("HTTP", exc.code, exc.read()[:500], file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print("ERR", type(exc).__name__, exc, file=sys.stderr)
        return 1

    out = ROOT / "evidence" / "files" / "originq-bell-rest-detail.json"
    # Redact api key if echoed
    text = json.dumps(body, ensure_ascii=False, indent=2, default=str)
    text = text.replace(token, "<redacted>")
    out.write_text(text + "\n", encoding="utf-8")
    print("wrote", out)
    print("top_keys", list(body.keys()) if isinstance(body, dict) else type(body))
    obj = body.get("obj") if isinstance(body, dict) else None
    if isinstance(obj, dict):
        print("obj_keys", list(obj.keys())[:30])
        vo = obj.get("qcodeTaskNewVo") or {}
        if isinstance(vo, dict):
            print("vo_keys", list(vo.keys())[:40])
            records = vo.get("taskResultList") or []
            print("n_records", len(records))
            if records:
                rec = records[0]
                print("taskState", rec.get("taskState"))
                print("probCount", str(rec.get("probCount"))[:300])
                print("taskResult", str(rec.get("taskResult"))[:300])
                print("errorMessage", rec.get("errorMessage"))
    print("code", body.get("code") if isinstance(body, dict) else None)
    print("message", body.get("message") if isinstance(body, dict) else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
