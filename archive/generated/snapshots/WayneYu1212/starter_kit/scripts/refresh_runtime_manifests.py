#!/usr/bin/env python3
"""Regenerate derived Runtime manifests from current payload bytes only."""
from __future__ import annotations
import hashlib, json
from pathlib import Path

FILES = Path(__file__).resolve().parents[1] / "evidence" / "files"

def main() -> int:
    for path in sorted(FILES.glob("originq_runtime_*-manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        refreshed = []
        for entry in manifest["files"]:
            target = FILES / entry["name"]
            if target.name == path.name:
                raise ValueError(f"self-referential manifest: {path.name}")
            refreshed.append({"name": target.name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "size_bytes": target.stat().st_size})
        manifest["files"] = refreshed
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(path.name)
    return 0
if __name__ == "__main__": raise SystemExit(main())
