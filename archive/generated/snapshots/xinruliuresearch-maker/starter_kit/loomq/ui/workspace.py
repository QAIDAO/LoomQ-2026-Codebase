"""Request-scoped, atomic evidence storage for the local workbench."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping


_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
_SENSITIVE_KEYS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
)
_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+\-/=]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(
        r"(?i)\b(api[_-]?key|token|password|secret)\s*[:=]\s*"
        r"([^\s,;]{6,})"
    ),
)


class WorkspaceError(ValueError):
    """Raised when an evidence path would escape the allocated workspace."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def redact_text(value: str) -> str:
    """Remove common credential shapes before text reaches disk or the UI."""

    clean = value
    for pattern in _SECRET_PATTERNS:
        if pattern.pattern.startswith("(?i)\\b(api"):
            clean = pattern.sub(lambda match: match.group(1) + "=[REDACTED]", clean)
        else:
            clean = pattern.sub("[REDACTED]", clean)
    return clean


def redact_value(value: Any) -> Any:
    """Recursively redact sensitive key names and credential-shaped strings."""

    if isinstance(value, Mapping):
        output: Dict[str, Any] = {}
        for key, item in value.items():
            rendered_key = str(key)
            lowered = rendered_key.lower()
            if any(fragment in lowered for fragment in _SENSITIVE_KEYS):
                output[rendered_key] = "[REDACTED]"
            else:
                output[rendered_key] = redact_value(item)
        return output
    if isinstance(value, (list, tuple)):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_text(str(value))


class RunWorkspace:
    """One UUID-named request directory owned by a ``WorkspaceSession``."""

    def __init__(self, session: "WorkspaceSession", run_id: str, path: Path) -> None:
        self.session = session
        self.run_id = run_id
        self.path = path
        self.created_at = utc_now()
        self._artifacts: Dict[str, Dict[str, Any]] = {}

    def _target(self, relative_name: str) -> Path:
        if not isinstance(relative_name, str) or not relative_name.strip():
            raise WorkspaceError("artifact name must be a non-empty relative path")
        relative = Path(relative_name)
        if relative.is_absolute() or ".." in relative.parts:
            raise WorkspaceError("artifact path traversal is not allowed")
        target = (self.path / relative).resolve()
        try:
            target.relative_to(self.path)
        except ValueError as exc:
            raise WorkspaceError("artifact path escaped its request workspace") from exc
        return target

    def write_json(self, relative_name: str, value: Any) -> Dict[str, Any]:
        redacted = redact_value(value)
        payload = (
            json.dumps(redacted, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8")
        return self._write(relative_name, payload, "application/json; charset=utf-8")

    def write_text(self, relative_name: str, value: str) -> Dict[str, Any]:
        payload = redact_text(value).encode("utf-8")
        return self._write(relative_name, payload, "text/plain; charset=utf-8")

    def _write(
        self, relative_name: str, payload: bytes, media_type: str
    ) -> Dict[str, Any]:
        target = self._target(relative_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_name = "._loomq-" + uuid.uuid4().hex + ".tmp"
        temporary = target.parent / temporary_name
        try:
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary), str(target))
        finally:
            if temporary.exists():
                temporary.unlink()
        record = {
            "name": relative_name.replace("\\", "/"),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "media_type": media_type,
        }
        self._artifacts[record["name"]] = record
        return dict(record)

    def finalize(self, status: str, summary: Mapping[str, Any]) -> Dict[str, Any]:
        manifest = {
            "schema": "loomq-workbench-manifest/v1",
            "run_id": self.run_id,
            "session_id": self.session.session_id,
            "created_at": self.created_at,
            "completed_at": utc_now(),
            "status": status,
            "summary": redact_value(summary),
            "artifacts": [
                dict(self._artifacts[name]) for name in sorted(self._artifacts)
            ],
        }
        self.write_json("manifest.json", manifest)
        ledger = dict(manifest)
        ledger["artifacts"] = [
            dict(self._artifacts[name]) for name in sorted(self._artifacts)
        ]
        self.session._complete(self, ledger)
        return ledger


class WorkspaceSession:
    """A server-lifetime workspace that can only create UUID request children."""

    def __init__(self, base_path: os.PathLike[str] | str | None = None) -> None:
        if base_path is None:
            base = Path(tempfile.gettempdir()) / "loomq-workbench"
        else:
            base = Path(base_path).expanduser()
        base.mkdir(parents=True, exist_ok=True)
        self.base_path = base.resolve()
        self.session_id = uuid.uuid4().hex
        self.path = (self.base_path / ("session-" + self.session_id)).resolve()
        try:
            self.path.relative_to(self.base_path)
        except ValueError as exc:
            raise WorkspaceError("session workspace escaped its configured base") from exc
        self.path.mkdir(mode=0o700, parents=False, exist_ok=False)
        self._lock = threading.RLock()
        self._runs: Dict[str, RunWorkspace] = {}
        self._history: Dict[str, Dict[str, Any]] = {}

    def begin_request(self) -> RunWorkspace:
        with self._lock:
            run_id = uuid.uuid4().hex
            path = (self.path / run_id).resolve()
            try:
                path.relative_to(self.path)
            except ValueError as exc:
                raise WorkspaceError("request workspace escaped its session") from exc
            path.mkdir(mode=0o700, parents=False, exist_ok=False)
            run = RunWorkspace(self, run_id, path)
            self._runs[run_id] = run
            return run

    def _complete(self, run: RunWorkspace, manifest: Dict[str, Any]) -> None:
        with self._lock:
            self._history[run.run_id] = manifest

    def history(self, limit: int = 30) -> list[Dict[str, Any]]:
        with self._lock:
            values = list(self._history.values())[-max(1, min(limit, 100)) :]
        return [
            {
                "run_id": item["run_id"],
                "created_at": item["created_at"],
                "completed_at": item["completed_at"],
                "status": item["status"],
                "summary": item["summary"],
            }
            for item in reversed(values)
        ]

    def artifact(self, run_id: str, relative_name: str) -> tuple[bytes, str]:
        if not _RUN_ID.fullmatch(run_id):
            raise WorkspaceError("invalid run id")
        with self._lock:
            run = self._runs.get(run_id)
            manifest = self._history.get(run_id)
        if run is None or manifest is None:
            raise WorkspaceError("run is not part of this server session")
        allowed: Iterable[str] = (
            item["name"] for item in manifest.get("artifacts", [])
        )
        allowed_names = set(allowed)
        if relative_name not in allowed_names:
            raise WorkspaceError("artifact is not listed in the run manifest")
        target = run._target(relative_name)
        if not target.is_file():
            raise WorkspaceError("artifact no longer exists")
        record = next(
            item for item in manifest["artifacts"] if item["name"] == relative_name
        )
        return target.read_bytes(), str(record["media_type"])


__all__ = [
    "RunWorkspace",
    "WorkspaceError",
    "WorkspaceSession",
    "redact_text",
    "redact_value",
    "utc_now",
]
