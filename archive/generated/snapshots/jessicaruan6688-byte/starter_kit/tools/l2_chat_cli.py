#!/usr/bin/env python3
"""Minimal local CLI for LoomQ L2 agent_chat (experience / demo helper).

Requires LOOMQ_LLM_* in the environment or starter_kit/.env.
Not used by the official automated scorer; adapter.agent_chat is what counts.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
        if key and key not in os.environ:
            os.environ[key] = value


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    missing = [
        name
        for name in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")
        if not os.environ.get(name)
    ]
    if missing:
        print(
            "Missing env: " + ", ".join(missing) + "\n"
            "Copy starter_kit/.env.example -> starter_kit/.env and fill LOOMQ_LLM_*.",
            file=sys.stderr,
        )
        return 2

    from adapter import agent_chat

    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        prompt = " ".join(args)
        print(agent_chat(prompt))
        return 0

    print("LoomQ L2 chat (empty line to quit). Uses LOOMQ_LLM_*.")
    while True:
        try:
            prompt = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not prompt:
            return 0
        try:
            print(agent_chat(prompt))
        except Exception as exc:  # noqa: BLE001 — show user-facing errors in CLI
            print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
