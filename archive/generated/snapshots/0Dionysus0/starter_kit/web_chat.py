#!/usr/bin/env python3
"""One-command web entry for LoomQ L2 interaction.

Usage (from starter_kit/, with LOOMQ_LLM_* set):

    python web_chat.py
    python web_chat.py --port 8877 --no-browser
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loomq_l2.webapp import main

if __name__ == "__main__":
    raise SystemExit(main())
