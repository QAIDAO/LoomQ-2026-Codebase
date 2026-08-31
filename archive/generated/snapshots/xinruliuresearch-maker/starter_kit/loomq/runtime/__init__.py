"""Local deterministic runtime and result normalization."""

from .reference_simulator import simulate_counts
from .result_normalizer import build_result
from .providers import get_provider
from .verification import admit_result

__all__ = ["admit_result", "build_result", "get_provider", "simulate_counts"]
