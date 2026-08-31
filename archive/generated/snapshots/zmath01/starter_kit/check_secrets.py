#!/usr/bin/env python3
"""LoomQ submission secret scanner.

Pre-commit hygiene check. Scans the working tree (and optionally the git
history) for anything that looks like an API key, token, password, private
key, or personal credential, so that LOOMQ_LLM_API_KEY values, platform cloud
tokens, and local privacy data never end up in the fork.

Usage:
    python3 check_secrets.py                 # scan working tree only
    python3 check_secrets.py --history       # also scan all git objects
    python3 check_secrets.py --quiet         # exit code only

Exit code 0 = clean, 1 = suspicious patterns found.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files that are allowed to contain the word "token"/"secret" (documentation,
# capability tables, grammar docs). Everything else is inspected.
_ALLOWED_SUFFIXES = (".md", ".json", ".yaml", ".yml")
_ALLOWED_NAMES = {
    "l2_policy.json",
    "backend_capabilities.json",
    "backend_capabilities.md",
    "target_ir_contract.md",
    "QUANTUM_101.md",
    "gate_identities.md",
    "quantum_riscv_spec.md",
    "submission.yaml",
    "CHANGELOG.md",
    "requirements.txt",
}

# High-confidence secret payloads (long random strings after a credential key).
_PATTERNS = [
    re.compile(r"(?i)\b(sk|ak|pk|rk|token|secret|apikey|api_key|access[_-]?key|passwd|password)\b[\"'=:\s]*([A-Za-z0-9_\-./+]{24,})"),
    re.compile(r"\b(sk-[A-Za-z0-9]{16,}|ak-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{16,}|gho_[A-Za-z0-9]{16,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[A-Za-z0-9_\-]{20,})\b"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(aws_access_key_id|aws_secret_access_key|google_api_key|github_token|slack_token)\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)Authorization:\s*Bearer\s+[A-Za-z0-9._\-]{16,}"),
    re.compile(r"(?i)Basic\s+[A-Za-z0-9+/]{16,}={0,2}\b"),
]

# Whole-file denylist: never committed even if patterns are not detected.
_DENYLIST_GLOB = (
    ".env",
    ".env.*",
    "*.env",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.jks",
    "id_rsa",
    "id_ed25519",
    "credentials",
    "credentials.json",
    "aws-credentials",
    "service_account*.json",
    "*.secret",
    "*.token",
)

# Docs commonly write placeholder assignments (e.g. "export AWS_ACCESS_KEY_ID ..."
# or "= <YOUR_KEY>"); those are not credentials. Match the value side and
# allow a trailing comment.
_PLACEHOLDER_VALUE = re.compile(
    r"[:=]\s*(\.{3,}|xxx+|XXXX+|<\w[\w.\-]*>|\[\w[\w.\-]*\]|\$?\{\w+\}|[A-Z_]{4,})\s*(#.*)?$",
    re.I,
)


def _matches_denylist(rel: str) -> bool:
    name = os.path.basename(rel)
    for pattern in _DENYLIST_GLOB:
        if pattern == name:
            return True
        if pattern.startswith("*.") and name.endswith(pattern[1:]):
            return True
        if pattern.startswith(".env") and name.startswith(".env"):
            return True
        if rel.startswith(pattern):
            return True
    return False


def _is_documentation(rel: str) -> bool:
    name = os.path.basename(rel)
    return name in _ALLOWED_NAMES or rel.endswith(_ALLOWED_SUFFIXES)


def _check_text(rel: str, text: str) -> list[str]:
    hits: list[str] = []
    if _matches_denylist(rel):
        hits.append("%s: denylisted file type (credential-like)" % rel)
    if _is_documentation(rel):
        return hits
    for pattern in _PATTERNS:
        for match in pattern.finditer(text):
            # Skip lines whose "value" is a documented placeholder.
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            if line_end == -1:
                line_end = len(text)
            line = text[line_start:line_end]
            if _PLACEHOLDER_VALUE.search(line):
                continue
            snippet = text[max(0, match.start() - 30): match.end() + 30]
            snippet = snippet.replace("\n", "\\n")
            hits.append("%s: suspicious pattern %r near ...%s..." % (rel, pattern.pattern[:40], snippet))
    return hits


def scan_worktree() -> list[str]:
    findings: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        # venv dirs are gitignored and never committed; their third-party
        # sources legitimately contain sample keys (SDK tests, botocore, ...).
        dirnames[:] = [d for d in dirnames if d not in (
            ".git", "__pycache__", "node_modules", "venv") and not d.startswith(".venv")]
        for filename in filenames:
            full = os.path.join(dirpath, filename)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            if _matches_denylist(rel):
                findings.append("%s: denylisted file type (credential-like)" % rel)
                continue
            try:
                with open(full, "rb") as handle:
                    raw = handle.read()
            except OSError:
                continue
            if b"\x00" in raw[:4096]:
                continue  # binary
            try:
                text = raw.decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                continue
            findings.extend(_check_text(rel, text))
    return findings


def scan_history() -> list[str]:
    findings: list[str] = []
    try:
        proc = subprocess.run(
            ["git", "log", "--all", "-p", "--no-color"],
            cwd=ROOT,
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ["history scan unavailable"]
    stdout = proc.stdout.decode("utf-8", errors="replace")
    # History is inherently noisy; only flag high-confidence payload patterns.
    # Placeholder-value lines (e.g. "export AWS_ACCESS_KEY_ID ...") are docs.
    for line in stdout.splitlines():
        if not line.startswith("+"):
            continue
        body = line[1:]
        if _PLACEHOLDER_VALUE.search(body):
            continue
        for pattern in _PATTERNS[1:]:  # skip the low-signal key=value pattern
            if pattern.search(body):
                findings.append("HISTORY: %s" % pattern.pattern[:50])
                break
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="LoomQ secret scanner")
    parser.add_argument("--history", action="store_true", help="also scan git history")
    parser.add_argument("--quiet", action="store_true", help="no output, exit code only")
    args = parser.parse_args()

    findings = scan_worktree()
    if args.history:
        findings.extend(scan_history())

    if findings:
        if not args.quiet:
            print("SECRET SCAN FAILED (%d finding(s)):" % len(findings))
            for finding in findings:
                print("  -", finding)
            print("Remove or untrack these before committing. API keys and tokens must")
            print("only live in environment variables, never in the fork.")
        return 1
    if not args.quiet:
        print("SECRET SCAN CLEAN: no credential-like patterns in the working tree%s." % (" or history" if args.history else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
