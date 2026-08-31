"""Fail-closed source -> target -> independent reparse -> execution pipeline."""

from __future__ import annotations

from .emitters import emit_target
from .ir import parse_qasm2
from .simulator import execute
from .verification import certify_translation


def verified_run(qasm: str, target: str, shots: int) -> tuple[dict, str]:
    """Execute only the independently reparsed target artifact after certification."""
    normalized_target = target.strip().lower() if isinstance(target, str) else ""
    source = parse_qasm2(qasm)
    artifact = emit_target(source, normalized_target)
    translated, certificate = certify_translation(source, artifact, normalized_target)
    result = execute(translated, normalized_target, shots, artifact)
    result["meta"]["translation_certificate"] = certificate.as_dict()
    result["meta"]["executed_ir"] = "independently-reparsed-target"
    return result, artifact
