#!/usr/bin/env python3
"""One-command entry for the zero-foundation LoomQ chat CLI.

Usage (from starter_kit/):

    python chat.py
    python chat.py --tasks
    python chat.py --once 1
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loomq_l2.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
