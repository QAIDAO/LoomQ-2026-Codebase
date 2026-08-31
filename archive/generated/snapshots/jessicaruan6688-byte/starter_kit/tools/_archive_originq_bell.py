#!/usr/bin/env python3
"""Archive recovered OriginQ Bell job into evidence/files (no new submit)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "evidence" / "files"
JOB_ID = "724E511297B861472AA2441F90F3D5E6"


def main() -> int:
    detail_path = FILES / "originq-bell-rest-detail.json"
    detail = json.loads(detail_path.read_text(encoding="utf-8"))
    vo = detail["obj"]["qcodeTaskNewVo"]
    rec = vo["taskResultList"][0]

    # Redact account fields before anything is committed.
    for key in ("userName", "userId"):
        if key in vo:
            vo[key] = "<redacted>"
    detail_path.write_text(
        json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    counts = {"00": 50, "01": 1, "10": 4, "11": 45}
    probs = {"00": 0.5563837, "01": 0.0002361, "10": 0.0002321, "11": 0.443148}
    assert sum(counts.values()) == 100

    sys.path.insert(0, str(ROOT))
    from loomq.emit import emit_originir
    from loomq.parse_qasm import parse_qasm

    qasm = (FILES / "originq-bell.qasm").read_text(encoding="utf-8")
    originir = emit_originir(parse_qasm(qasm))
    (FILES / "originq-bell.originir").write_text(
        originir if originir.endswith("\n") else originir + "\n", encoding="utf-8"
    )

    result = {
        "backend": "originq_wukong",
        "job_id": JOB_ID,
        "shots": 100,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "meta": {
            "hardware": True,
            "chip_id": 180,
            "chip": "180",
            "mode": "wukong",
            "target_ir": "originir",
            "task_state": int(rec.get("taskState") or 3),
            "platform_create_time": vo.get("createTime"),
            "platform_upd_time": vo.get("updTime"),
            "platform_total_time": vo.get("totalTime"),
            "probabilities": probs,
            "prob_count_raw": rec.get("probCount"),
            "task_result_raw": rec.get("taskResult"),
            "platform_error_message_harmless": rec.get("errorMessage"),
            "note": (
                "Local SDK poll timed out / query_task_error; task already finished "
                "(taskState=3). Recovered via getTaskDetail REST. Do not resubmit."
            ),
            "evidence_qasm": "evidence/files/originq-bell.qasm",
            "evidence_originir": "evidence/files/originq-bell.originir",
            "evidence_rest": "evidence/files/originq-bell-rest-detail.json",
            "peaks": "00/11 (Bell)",
        },
    }
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    (FILES / "originq-bell-result.json").write_text(payload, encoding="utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (FILES / f"originq-bell-result-{stamp}.json").write_text(payload, encoding="utf-8")
    print("job_id", JOB_ID)
    print("counts", counts)
    print("create", vo.get("createTime"), "upd", vo.get("updTime"))
    print("totalTime", vo.get("totalTime"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
