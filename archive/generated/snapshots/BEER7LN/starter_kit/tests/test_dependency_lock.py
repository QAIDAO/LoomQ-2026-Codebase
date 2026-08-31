"""Offline audit checks for the generated transitive dependency lock."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import unittest


STARTER_KIT = Path(__file__).resolve().parents[1]
DIRECT = STARTER_KIT / "requirements.txt"
LOCK = STARTER_KIT / "requirements-lock.txt"


class DependencyLockTests(unittest.TestCase):
    def test_lock_covers_direct_requirements_and_records_source_hash(self) -> None:
        content = LOCK.read_text(encoding="utf-8")
        expected_hash = hashlib.sha256(DIRECT.read_bytes()).hexdigest()
        self.assertIn(f"# Direct requirements SHA256: {expected_hash}", content)

        direct = {
            line.strip().lower()
            for line in DIRECT.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        locked = {
            line.strip().lower()
            for line in content.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertTrue(direct <= locked)
        self.assertGreater(len(locked), len(direct))
        self.assertTrue(all(re.fullmatch(r"[a-z0-9_.-]+==[^=\s]+", line) for line in locked))
        self.assertNotIn("C:\\Users\\", content)


if __name__ == "__main__":
    unittest.main()
