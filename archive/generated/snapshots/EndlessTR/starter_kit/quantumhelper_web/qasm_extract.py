#!/usr/bin/env python3
"""QASM extraction and goal separation for QuantumHelper web (任务书 §15/§16/§17/§36).

This module owns the "pull code out of mixed prose + code" logic that used to
live inline in ``web_agent``.  Wave 3 makes ``web_agent`` import it instead of
re-implementing it.

Rules that are load-bearing here:

* Gate vocabulary is *reused from ``adapter``* - never re-hardcoded (任务书 §16).
  Only ``adapter.L2_ALLOWED_GATES`` plus ``adapter._REPAIR_GATE_ALIASES`` name a
  "QASM-like statement".
* Statement-level extraction keeps *only the statement body* starting at the
  gate name, so Chinese lead-ins ("帮我修好：") can never survive into the
  result (任务书 §15).
* The goal vocabulary is exactly what ``adapter`` can build: bell/ghz/qft plus
  superposition.  Anything else returns ``None`` rather than being faked
  (任务书 §40.13).
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
if (APP_DIR.parent / "adapter.py").is_file():
    STARTER_KIT_ROOT = APP_DIR.parent
elif (APP_DIR / "starter_kit" / "adapter.py").is_file():
    STARTER_KIT_ROOT = APP_DIR / "starter_kit"
elif (APP_DIR.parent / "starter_kit" / "adapter.py").is_file():
    STARTER_KIT_ROOT = APP_DIR.parent / "starter_kit"
else:  # pragma: no cover - mirrors server.py bootstrap
    raise RuntimeError("Cannot locate the LoomQ starter_kit adapter")
for _root in (str(STARTER_KIT_ROOT.parent), str(STARTER_KIT_ROOT)):
    if _root not in sys.path:
        sys.path.insert(0, _root)

try:
    from starter_kit import adapter  # type: ignore  # noqa: E402
except ModuleNotFoundError as exc:  # extracted submission root has no outer package
    if exc.name != "starter_kit":
        raise
    import adapter  # type: ignore  # noqa: E402


# --------------------------------------------------------------------------
# Gate vocabulary - reused from adapter, never re-hardcoded (任务书 §16)
# --------------------------------------------------------------------------

_GATE_ALIASES: dict[str, str] = dict(getattr(adapter, "_REPAIR_GATE_ALIASES", {}) or {})
_GATE_WORDS = sorted(
    set(adapter.L2_ALLOWED_GATES) | set(_GATE_ALIASES),
    key=len,
    reverse=True,
)
_GATE_ALTERNATION = "|".join(re.escape(name) for name in _GATE_WORDS)

#: One complete QASM-like gate statement: ``h q[0]``, ``cx q[0], q[1]``,
#: ``rz(0.5) q[2]``.  Captures the full operand list so trailing prose (which
#: never looks like ``q[...]``) is excluded by construction.
_QASM_STATEMENT_RE = re.compile(
    rf"(?<![a-z0-9_])(?:{_GATE_ALTERNATION})(?:\s*\([^()\n]*\))?\s+"
    rf"q\s*\[?\s*\d+\s*\]?(?:\s*[,]?\s*q\s*\[?\s*\d+\s*\]?)*",
    re.IGNORECASE,
)
_QASM_STRUCTURE_RE = re.compile(
    r"OPENQASM\s+2\.0|qelib1\.inc|\bqreg\b|\bcreg\b|\bmeasure\b\s+q",
    re.IGNORECASE,
)
_FENCED_BLOCK_RE = re.compile(r"```(?:openqasm|qasm)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def _normalize(text: str) -> str:
    """Fold full-width punctuation/brackets/spaces to ASCII (matches adapter)."""
    return unicodedata.normalize("NFKC", text).strip()


def _looks_like_qasm_normalized(text: str) -> bool:
    return bool(_QASM_STATEMENT_RE.search(text) or _QASM_STRUCTURE_RE.search(text))


# --------------------------------------------------------------------------
# Public API (consumed by web_agent in Wave 3)
# --------------------------------------------------------------------------


def looks_like_qasm(text: str) -> bool:
    """True when *text* carries QASM statements/structure rather than prose alone."""
    return _looks_like_qasm_normalized(_normalize(text))


def extract_qasm_from_prompt(prompt: str) -> str | None:
    """Pull the code out of a mixed prose + code prompt.

    Priority (任务书 §15):

    1. a fenced ```qasm block,
    2. everything from ``OPENQASM 2.0;`` onwards,
    3. the contiguous run of QASM-like statements.

    Natural language must never survive into the result, so step 3 keeps only
    the statement bodies rather than "everything after the last colon".
    """
    text = _normalize(prompt)
    if not text:
        return None

    fenced = _extract_fenced_qasm(text)
    if fenced:
        return fenced

    header = re.search(r"OPENQASM\s+2\.0", text, re.IGNORECASE)
    if header:
        return text[header.start():].strip() or None

    return _collect_qasm_statements(text) or None


def extract_goal(prompt: str) -> str | None:
    """Best-effort named target state, restricted to what adapter can build.

    Mapping (任务书 §17): 贝尔/Bell -> bell; 纠缠/entangle -> bell;
    ghz -> ghz; qft/傅里叶 -> qft; 叠加/superposition -> superposition.
    """
    lowered = _normalize(prompt).lower()
    if re.search(r"贝尔|bell", lowered):
        return "bell"
    if re.search(r"(?<![a-z])ghz(?![a-z])", lowered):
        return "ghz"
    if re.search(r"(?<![a-z])qft(?![a-z])|傅里叶", lowered):
        return "qft"
    if re.search(r"纠缠|entangle", lowered):
        return "bell"
    if re.search(r"叠加|superposition", lowered):
        return "superposition"
    return None


def build_repair_input(prompt: str) -> dict:
    """Return ``{"goal": ..., "source_qasm": ...}`` (任务书 §17 shape).

    ``goal`` and ``source_qasm`` are separated; ``source_qasm`` carries code only.
    """
    return {
        "goal": extract_goal(prompt),
        "source_qasm": extract_qasm_from_prompt(prompt),
    }


# --------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------


def _extract_fenced_qasm(text: str) -> str | None:
    """Return the last fenced block that actually looks like QASM, else None."""
    candidates: list[str] = []
    for match in _FENCED_BLOCK_RE.finditer(text):
        content = match.group(1).strip()
        if content and _looks_like_qasm_normalized(content):
            candidates.append(content)
    return candidates[-1] if candidates else None


def _collect_qasm_statements(text: str) -> str:
    """Join the QASM-like statements found in *text*, dropping all prose.

    The prompt is split on ``;`` ``；`` ``\\n`` and each chunk is scanned with the
    gate+``q[数字]`` pattern.  Only the matched statement body is kept - never
    the Chinese lead-in ("帮我修好： H q[0]" -> "H q[0]").
    """
    pieces: list[str] = []
    for chunk in re.split(r"[；;\n\r]+", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        for match in _QASM_STATEMENT_RE.finditer(chunk):
            pieces.append(match.group(0).strip())
    return "; ".join(pieces)
