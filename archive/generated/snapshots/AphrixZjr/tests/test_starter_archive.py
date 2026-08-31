"""Expose the self-contained starter_kit suite to repository-level CI."""

import unittest
from pathlib import Path


STARTER = Path(__file__).resolve().parents[1] / "starter_kit"


def load_tests(_loader, _tests, _pattern):
    # The repository discovery loader already owns the repository root as its
    # top-level directory.  A fresh loader lets the hyphenated starter_kit
    # subtree use its own import root without corrupting the outer discovery.
    return unittest.TestLoader().discover(
        str(STARTER / "tests"),
        pattern="test_*.py",
        top_level_dir=str(STARTER),
    )
