#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping, Optional, Sequence, Tuple

import loomq_git


EXPECTED_SUBMISSION_COUNT = 58
MANIFEST_RELATIVE_PATH = Path("archive/submissions.json")
_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_URL_PATTERN = re.compile(
    r"https://github\.com/"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/"
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z"
)
_SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
_POLICIES = frozenset(("pointer-only", "reject"))


class ArchiveError(RuntimeError):
    pass


class ManifestError(ArchiveError):
    pass


@dataclass(frozen=True)
class SubmissionSpec:
    contestant_id: str
    repository_url: str
    commit_sha: str

    def __post_init__(self) -> None:
        issues: list[str] = []
        if not isinstance(self.contestant_id, str) or not _ID_PATTERN.fullmatch(
            self.contestant_id
        ):
            issues.append(f"unsafe contestant_id {self.contestant_id!r}")
        elif unicodedata.normalize("NFC", self.contestant_id).casefold() == ".git":
            issues.append(f"forbidden contestant_id {self.contestant_id!r}")
        if not isinstance(self.repository_url, str) or not _URL_PATTERN.fullmatch(
            self.repository_url
        ):
            issues.append(f"malformed GitHub HTTPS URL {self.repository_url!r}")
        elif self.repository_url.casefold().endswith(".git"):
            issues.append(
                f"repository URL must be verbatim without .git: {self.repository_url!r}"
            )
        if not isinstance(self.commit_sha, str) or not _SHA_PATTERN.fullmatch(
            self.commit_sha
        ):
            issues.append(f"commit SHA must be 40 lowercase hexadecimal characters: {self.commit_sha!r}")
        if issues:
            raise ManifestError("; ".join(issues))


@dataclass(frozen=True)
class Manifest:
    submission_count: int
    git_lfs_policy: str
    gitlink_policy: str
    submissions: Tuple[SubmissionSpec, ...]

    def __post_init__(self) -> None:
        issues: list[str] = []
        if type(self.submission_count) is not int or self.submission_count != len(
            self.submissions
        ):
            issues.append(
                f"submission_count is {self.submission_count!r}, but the roster has {len(self.submissions)} rows"
            )
        if not isinstance(self.git_lfs_policy, str) or self.git_lfs_policy not in _POLICIES:
            issues.append(f"invalid Git LFS policy {self.git_lfs_policy!r}")
        if not isinstance(self.gitlink_policy, str) or self.gitlink_policy not in _POLICIES:
            issues.append(f"invalid gitlink policy {self.gitlink_policy!r}")
        seen_ids: dict[str, int] = {}
        seen_urls: dict[str, int] = {}
        seen_shas: dict[str, int] = {}
        for index, spec in enumerate(self.submissions, 1):
            if not isinstance(spec, SubmissionSpec):
                issues.append(f"row {index} is not a SubmissionSpec")
                continue
            id_key = unicodedata.normalize("NFC", spec.contestant_id).casefold()
            url_key = spec.repository_url.casefold()
            for label, key, seen in (
                ("contestant_id", id_key, seen_ids),
                ("repository_url", url_key, seen_urls),
                ("commit_sha", spec.commit_sha, seen_shas),
            ):
                if key in seen:
                    issues.append(
                        f"duplicate {label} in rows {seen[key]} and {index}: {key!r}"
                    )
                else:
                    seen[key] = index
        if issues:
            raise ManifestError("\n".join(issues))

    @property
    def ids(self) -> Tuple[str, ...]:
        return tuple(spec.contestant_id for spec in self.submissions)


@dataclass(frozen=True)
class CanonicalCommitObject:
    contestant_id: str
    commit_sha: str
    canonical_bytes: bytes
    root_tree: str

    def __post_init__(self) -> None:
        if hashlib.sha1(self.canonical_bytes).hexdigest() != self.commit_sha:
            raise ArchiveError(
                f"canonical commit object for {self.contestant_id} does not hash to {self.commit_sha}"
            )


@dataclass(frozen=True)
class DesiredArchive:
    manifest: Manifest
    commit_objects: Mapping[str, CanonicalCommitObject]
    snapshot_trees: Mapping[str, str]
    audits: Mapping[str, loomq_git.TreeAudit]

    def __post_init__(self) -> None:
        expected = set(self.manifest.ids)
        for label, values in (
            ("commit objects", self.commit_objects),
            ("snapshot trees", self.snapshot_trees),
            ("audits", self.audits),
        ):
            if set(values) != expected:
                missing = sorted(expected - set(values))
                extra = sorted(set(values) - expected)
                raise ArchiveError(f"{label} do not match manifest; missing={missing}, extra={extra}")
        object.__setattr__(self, "commit_objects", MappingProxyType(dict(self.commit_objects)))
        object.__setattr__(self, "snapshot_trees", MappingProxyType(dict(self.snapshot_trees)))
        object.__setattr__(self, "audits", MappingProxyType(dict(self.audits)))


@dataclass(frozen=True)
class VerificationReport:
    submission_count: int
    lfs_count: int
    gitlink_count: int
    lfs_by_submission: Mapping[str, int]
    gitlinks_by_submission: Mapping[str, int]


@dataclass(frozen=True)
class _Projection:
    commits: Mapping[str, bytes]
    snapshots: Mapping[str, loomq_git.TreeNode]
    report: VerificationReport


SourceLoader = Callable[[SubmissionSpec, Path], None]


def _strict_object(pairs: Sequence[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_manifest(path: Path, *, expected_count: Optional[int] = EXPECTED_SUBMISSION_COUNT) -> Manifest:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManifestError(f"cannot parse {path}: {error}") from error
    if not isinstance(raw, dict):
        raise ManifestError("manifest root must be an object")
    expected_keys = {"schema_version", "submission_count", "policies", "submissions"}
    if set(raw) != expected_keys:
        raise ManifestError(
            f"manifest keys must be {sorted(expected_keys)}, found {sorted(raw)}"
        )
    if raw["schema_version"] != 1 or type(raw["schema_version"]) is not int:
        raise ManifestError("schema_version must be 1")
    policies = raw["policies"]
    if not isinstance(policies, dict) or set(policies) != {"git_lfs", "gitlinks"}:
        raise ManifestError("policies must contain only git_lfs and gitlinks")
    rows = raw["submissions"]
    if not isinstance(rows, list):
        raise ManifestError("submissions must be an array")
    issues: list[str] = []
    specs: list[SubmissionSpec] = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or set(row) != {
            "contestant_id",
            "repository_url",
            "commit_sha",
        }:
            issues.append(f"row {index} must contain only contestant_id, repository_url, and commit_sha")
            continue
        try:
            specs.append(
                SubmissionSpec(
                    contestant_id=row["contestant_id"],
                    repository_url=row["repository_url"],
                    commit_sha=row["commit_sha"],
                )
            )
        except ManifestError as error:
            issues.append(f"row {index}: {error}")
    if issues:
        raise ManifestError("\n".join(issues))
    manifest = Manifest(
        submission_count=raw["submission_count"],
        git_lfs_policy=policies["git_lfs"],
        gitlink_policy=policies["gitlinks"],
        submissions=tuple(specs),
    )
    if expected_count is not None and manifest.submission_count != expected_count:
        raise ManifestError(
            f"submission count drift: expected {expected_count}, found {manifest.submission_count}"
        )
    return manifest


def _https_loader(spec: SubmissionSpec, git_dir: Path) -> None:
    loomq_git.fetch_exact_https(spec.repository_url, spec.commit_sha, git_dir)


def _build_desired_archive(
    manifest: Manifest,
    quarantine_git_dir: Path,
    source_loader: SourceLoader,
) -> DesiredArchive:
    commits: dict[str, CanonicalCommitObject] = {}
    snapshots: dict[str, str] = {}
    audits: dict[str, loomq_git.TreeAudit] = {}
    failures: list[str] = []
    for spec in manifest.submissions:
        try:
            with tempfile.TemporaryDirectory(prefix="loomq-source-") as source_name:
                source_git_dir = Path(source_name) / "source.git"
                loomq_git.initialize_bare(source_git_dir)
                source_loader(spec, source_git_dir)
                inspected = loomq_git.inspect_commit(
                    source_git_dir,
                    spec.commit_sha,
                    lfs_policy=manifest.git_lfs_policy,
                    gitlink_policy=manifest.gitlink_policy,
                )
                loomq_git.copy_objects(
                    source_git_dir,
                    quarantine_git_dir,
                    inspected.audit.object_oids,
                )
            commits[spec.contestant_id] = CanonicalCommitObject(
                contestant_id=spec.contestant_id,
                commit_sha=spec.commit_sha,
                canonical_bytes=inspected.canonical_bytes,
                root_tree=inspected.root_tree,
            )
            snapshots[spec.contestant_id] = inspected.root_tree
            audits[spec.contestant_id] = inspected.audit
        except (ArchiveError, loomq_git.GitArchiveError, OSError) as error:
            lines = str(error).splitlines() or [error.__class__.__name__]
            failures.extend(f"{spec.contestant_id}: {line}" for line in lines)
    if failures:
        raise ArchiveError("archive import failed:\n" + "\n".join(failures))
    return DesiredArchive(
        manifest=manifest,
        commit_objects=commits,
        snapshot_trees=snapshots,
        audits=audits,
    )


def sync_archive(
    repository: loomq_git.Repository,
    manifest: Manifest,
    *,
    source_loader: SourceLoader = _https_loader,
) -> VerificationReport:
    archive_directory = repository.root / "archive"
    metadata = os.lstat(archive_directory)
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ArchiveError("archive must be a real directory")
    with tempfile.TemporaryDirectory(prefix="loomq-quarantine-") as quarantine_name:
        quarantine_git_dir = Path(quarantine_name) / "archive.git"
        loomq_git.initialize_bare(quarantine_git_dir)
        desired = _build_desired_archive(manifest, quarantine_git_dir, source_loader)
        commit_blob_oids = {
            contestant_id: loomq_git.write_blob(
                quarantine_git_dir, commit.canonical_bytes
            )
            for contestant_id, commit in desired.commit_objects.items()
        }
        all_objects = set(commit_blob_oids.values())
        for audit in desired.audits.values():
            all_objects.update(audit.object_oids)
        repository.import_objects(quarantine_git_dir, sorted(all_objects))
        desired_index, desired_tree, initial_index = repository.create_desired_index(
            snapshots=desired.snapshot_trees,
            commit_blobs=commit_blob_oids,
            quarantine_git_dir=quarantine_git_dir,
        )
        generated_temp = Path(
            tempfile.mkdtemp(prefix=".loomq-generated-", dir=archive_directory)
        )
        published = False
        try:
            loomq_git.materialize_generated(
                repository.git_dir,
                generated_temp,
                commits={
                    key: value.canonical_bytes
                    for key, value in desired.commit_objects.items()
                },
                snapshots={key: value.root for key, value in desired.audits.items()},
            )
            worktree_issues = loomq_git.verify_generated_worktree(
                generated_temp,
                git_dir=repository.git_dir,
                commits={
                    key: value.canonical_bytes
                    for key, value in desired.commit_objects.items()
                },
                snapshots={key: value.root for key, value in desired.audits.items()},
            )
            if worktree_issues:
                raise ArchiveError("generated worktree failed verification:\n" + "\n".join(worktree_issues))
            projection = _verify_projection(repository.git_dir, desired_tree, manifest)
            repository.publish(
                desired_index=desired_index,
                initial_index=initial_index,
                generated_directory=generated_temp,
            )
            published = True
            return projection.report
        finally:
            if not published:
                if desired_index.exists():
                    desired_index.unlink()
                if os.path.lexists(generated_temp):
                    _remove_path(generated_temp)


def verify_archive(
    repository: loomq_git.Repository,
    manifest: Manifest,
    *,
    staged: bool = False,
    remote: bool = False,
    source_loader: SourceLoader = _https_loader,
) -> VerificationReport:
    tree_oid = repository.index_tree() if staged else repository.head_tree()
    projection = _verify_projection(repository.git_dir, tree_oid, manifest)
    if staged:
        worktree_issues = loomq_git.verify_generated_worktree(
            repository.root / "archive" / "generated",
            git_dir=repository.git_dir,
            commits=projection.commits,
            snapshots=projection.snapshots,
        )
        if worktree_issues:
            raise ArchiveError("staged worktree verification failed:\n" + "\n".join(worktree_issues))
    if remote:
        _verify_remote(manifest, projection.commits, source_loader)
    return projection.report


def _verify_projection(
    git_dir: Path, root_tree: str, manifest: Manifest
) -> _Projection:
    issues: list[str] = []
    archive = _required_tree(git_dir, root_tree, b"archive", "archive", issues)
    generated = (
        _required_tree(git_dir, archive.oid, b"generated", "archive/generated", issues)
        if archive
        else None
    )
    if generated is None:
        raise ArchiveError("offline verification failed:\n" + "\n".join(issues))
    generated_entries = loomq_git.list_tree(git_dir, generated.oid)
    _check_exact_names(
        generated_entries,
        {b"commit-objects", b"snapshots"},
        "archive/generated",
        issues,
    )
    commit_directory = _entry_named(generated_entries, b"commit-objects")
    snapshot_directory = _entry_named(generated_entries, b"snapshots")
    if commit_directory is None or commit_directory.mode != "40000":
        issues.append("archive/generated/commit-objects is not a tree")
    if snapshot_directory is None or snapshot_directory.mode != "40000":
        issues.append("archive/generated/snapshots is not a tree")
    if issues:
        raise ArchiveError("offline verification failed:\n" + "\n".join(issues))
    assert commit_directory is not None
    assert snapshot_directory is not None
    commit_entries = loomq_git.list_tree(git_dir, commit_directory.oid)
    snapshot_entries = loomq_git.list_tree(git_dir, snapshot_directory.oid)
    expected_commit_names = {
        os.fsencode(f"{spec.contestant_id}.obj") for spec in manifest.submissions
    }
    expected_snapshot_names = {os.fsencode(spec.contestant_id) for spec in manifest.submissions}
    _check_exact_names(
        commit_entries,
        expected_commit_names,
        "archive/generated/commit-objects",
        issues,
    )
    _check_exact_names(
        snapshot_entries,
        expected_snapshot_names,
        "archive/generated/snapshots",
        issues,
    )
    commits: dict[str, bytes] = {}
    snapshots: dict[str, loomq_git.TreeNode] = {}
    lfs_by_submission: dict[str, int] = {}
    gitlinks_by_submission: dict[str, int] = {}
    for spec in manifest.submissions:
        record = _entry_named(commit_entries, os.fsencode(f"{spec.contestant_id}.obj"))
        snapshot = _entry_named(snapshot_entries, os.fsencode(spec.contestant_id))
        if record is None:
            issues.append(f"missing commit record for {spec.contestant_id}")
            continue
        if record.mode != "100644":
            issues.append(f"commit record mode is {record.mode} for {spec.contestant_id}")
            continue
        if snapshot is None:
            issues.append(f"missing snapshot for {spec.contestant_id}")
            continue
        if snapshot.mode != "40000":
            issues.append(f"snapshot is not a tree for {spec.contestant_id}")
            continue
        try:
            canonical = loomq_git.load_blob(git_dir, record.oid)
            commit_tree = _parse_canonical_commit(canonical, spec)
            if commit_tree != snapshot.oid:
                issues.append(
                    f"snapshot tree for {spec.contestant_id} is {snapshot.oid}, commit names {commit_tree}"
                )
            audit = loomq_git.audit_existing_tree(
                git_dir,
                snapshot.oid,
                lfs_policy=manifest.git_lfs_policy,
                gitlink_policy=manifest.gitlink_policy,
            )
            commits[spec.contestant_id] = canonical
            snapshots[spec.contestant_id] = audit.root
            lfs_by_submission[spec.contestant_id] = len(audit.lfs_paths)
            gitlinks_by_submission[spec.contestant_id] = len(audit.gitlink_paths)
        except (ArchiveError, loomq_git.GitArchiveError) as error:
            lines = str(error).splitlines() or [error.__class__.__name__]
            issues.extend(f"{spec.contestant_id}: {line}" for line in lines)
    if issues:
        raise ArchiveError("offline verification failed:\n" + "\n".join(issues))
    return _Projection(
        commits=MappingProxyType(commits),
        snapshots=MappingProxyType(snapshots),
        report=VerificationReport(
            submission_count=manifest.submission_count,
            lfs_count=sum(lfs_by_submission.values()),
            gitlink_count=sum(gitlinks_by_submission.values()),
            lfs_by_submission=MappingProxyType(lfs_by_submission),
            gitlinks_by_submission=MappingProxyType(gitlinks_by_submission),
        ),
    )


def _required_tree(
    git_dir: Path,
    parent_oid: str,
    name: bytes,
    label: str,
    issues: list[str],
) -> Optional[loomq_git.TreeEntry]:
    try:
        entries = loomq_git.list_tree(git_dir, parent_oid)
    except loomq_git.GitArchiveError as error:
        issues.append(str(error))
        return None
    entry = _entry_named(entries, name)
    if entry is None:
        issues.append(f"missing tree {label}")
        return None
    if entry.mode != "40000":
        issues.append(f"{label} is not a tree")
        return None
    return entry


def _entry_named(
    entries: Sequence[loomq_git.TreeEntry], name: bytes
) -> Optional[loomq_git.TreeEntry]:
    matches = [entry for entry in entries if entry.name == name]
    return matches[0] if len(matches) == 1 else None


def _check_exact_names(
    entries: Sequence[loomq_git.TreeEntry],
    expected: set[bytes],
    label: str,
    issues: list[str],
) -> None:
    actual = {entry.name for entry in entries}
    for name in sorted(expected - actual):
        issues.append(f"missing {label}/{os.fsdecode(name)}")
    for name in sorted(actual - expected):
        issues.append(f"unexpected {label}/{name!r}")
    if len(actual) != len(entries):
        issues.append(f"duplicate tree entry under {label}")


def _parse_canonical_commit(canonical: bytes, spec: SubmissionSpec) -> str:
    nul = canonical.find(b"\0")
    if nul < 8 or not canonical.startswith(b"commit "):
        raise ArchiveError("commit record has invalid canonical framing")
    size_text = canonical[7:nul]
    if not size_text.isdigit() or (len(size_text) > 1 and size_text.startswith(b"0")):
        raise ArchiveError("commit record has invalid canonical size")
    body = canonical[nul + 1 :]
    if int(size_text) != len(body):
        raise ArchiveError("commit record canonical size does not match its body")
    actual_sha = hashlib.sha1(canonical).hexdigest()
    if actual_sha != spec.commit_sha:
        raise ArchiveError(
            f"commit record hashes to {actual_sha}, expected {spec.commit_sha}"
        )
    first_line = body.split(b"\n", 1)[0]
    if len(first_line) != 45 or not first_line.startswith(b"tree "):
        raise ArchiveError("commit record has no SHA-1 root tree")
    try:
        tree_oid = first_line[5:].decode("ascii", "strict")
    except UnicodeDecodeError as error:
        raise ArchiveError("commit record has an invalid root tree") from error
    if not _SHA_PATTERN.fullmatch(tree_oid):
        raise ArchiveError("commit record has an invalid root tree")
    return tree_oid


def _verify_remote(
    manifest: Manifest,
    stored_commits: Mapping[str, bytes],
    source_loader: SourceLoader,
) -> None:
    issues: list[str] = []
    for spec in manifest.submissions:
        try:
            with tempfile.TemporaryDirectory(prefix="loomq-remote-") as source_name:
                source_git_dir = Path(source_name) / "source.git"
                loomq_git.initialize_bare(source_git_dir)
                source_loader(spec, source_git_dir)
                inspected = loomq_git.inspect_commit(
                    source_git_dir,
                    spec.commit_sha,
                    lfs_policy=manifest.git_lfs_policy,
                    gitlink_policy=manifest.gitlink_policy,
                )
            if inspected.canonical_bytes != stored_commits[spec.contestant_id]:
                issues.append(f"{spec.contestant_id}: remote canonical commit bytes differ")
        except (ArchiveError, loomq_git.GitArchiveError, OSError) as error:
            lines = str(error).splitlines() or [error.__class__.__name__]
            issues.extend(f"{spec.contestant_id}: {line}" for line in lines)
    if issues:
        raise ArchiveError("remote verification failed:\n" + "\n".join(issues))


def _remove_path(path: Path) -> None:
    metadata = os.lstat(path)
    if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
        shutil.rmtree(path)
    else:
        os.unlink(path)


def _format_report(action: str, report: VerificationReport) -> str:
    lines = [
        f"{action} {report.submission_count} submissions",
        f"Git LFS pointers: {report.lfs_count}",
        f"gitlinks: {report.gitlink_count}",
    ]
    for contestant_id, count in report.lfs_by_submission.items():
        if count:
            lines.append(f"  {contestant_id}: {count} Git LFS pointer(s)")
    for contestant_id, count in report.gitlinks_by_submission.items():
        if count:
            lines.append(f"  {contestant_id}: {count} gitlink(s)")
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Archive and verify exact LoomQ submission commits."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("sync", help="fetch and stage the complete generated archive")
    verify = subparsers.add_parser("verify", help="verify the committed archive")
    verify.add_argument("--staged", action="store_true", help="verify the index and managed worktree")
    verify.add_argument("--remote", action="store_true", help="refetch exact commits and compare proof bytes")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        repository = loomq_git.Repository.discover(Path.cwd())
        manifest = load_manifest(repository.root / MANIFEST_RELATIVE_PATH)
        if arguments.command == "sync":
            report = sync_archive(repository, manifest)
            print(_format_report("staged", report))
        else:
            report = verify_archive(
                repository,
                manifest,
                staged=arguments.staged,
                remote=arguments.remote,
            )
            source = "staged archive" if arguments.staged else "committed archive"
            if arguments.remote:
                source += " and remotes"
            print(_format_report(f"verified {source} for", report))
        return 0
    except (ArchiveError, ManifestError, loomq_git.GitArchiveError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
