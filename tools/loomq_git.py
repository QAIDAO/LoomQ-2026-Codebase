from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional, Sequence, Tuple


class GitArchiveError(RuntimeError):
    pass


class TreeAuditError(GitArchiveError):
    def __init__(self, issues: Sequence[str]):
        self.issues = tuple(issues)
        super().__init__("\n".join(self.issues))


@dataclass(frozen=True)
class TreeEntry:
    mode: str
    name: bytes
    oid: str
    child: Optional["TreeNode"] = None


@dataclass(frozen=True)
class TreeNode:
    oid: str
    entries: Tuple[TreeEntry, ...]


@dataclass(frozen=True)
class TreeAudit:
    root: TreeNode
    object_oids: Tuple[str, ...]
    lfs_paths: Tuple[bytes, ...]
    gitlink_paths: Tuple[bytes, ...]


@dataclass(frozen=True)
class InspectedCommit:
    canonical_bytes: bytes
    root_tree: str
    audit: TreeAudit


_COMMON_CONFIG = (
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "credential.helper=",
    "-c",
    "submodule.recurse=false",
    "-c",
    "fetch.recurseSubmodules=false",
    "-c",
    "filter.lfs.smudge=",
    "-c",
    "filter.lfs.process=",
    "-c",
    "filter.lfs.required=false",
)


def _git_environment(extra: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "never",
            "GIT_ASKPASS": "/bin/false",
            "SSH_ASKPASS": "/bin/false",
            "GIT_LFS_SKIP_SMUDGE": "1",
            "LC_ALL": "C",
        }
    )
    if extra:
        env.update(extra)
    return env


def _git_command(args: Sequence[str]) -> list[str]:
    return ["git", *_COMMON_CONFIG, *args]


def run_git(
    args: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    input_bytes: Optional[bytes] = None,
    extra_env: Optional[Mapping[str, str]] = None,
) -> bytes:
    completed = subprocess.run(
        _git_command(args),
        cwd=os.fspath(cwd) if cwd else None,
        env=_git_environment(extra_env),
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        command = " ".join(args)
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise GitArchiveError(f"git {command} failed: {detail}")
    return completed.stdout


def initialize_bare(git_dir: Path) -> None:
    run_git(["init", "--bare", os.fspath(git_dir)])


def fetch_exact_https(repository_url: str, commit_sha: str, git_dir: Path) -> None:
    run_git(
        [
            "-c",
            "protocol.allow=never",
            "-c",
            "protocol.https.allow=always",
            "-c",
            "http.followRedirects=initial",
            "--git-dir",
            os.fspath(git_dir),
            "fetch",
            "--force",
            "--no-tags",
            "--no-write-fetch-head",
            "--no-recurse-submodules",
            "--no-auto-maintenance",
            "--depth=1",
            repository_url,
            commit_sha,
        ]
    )


class ObjectReader:
    def __init__(self, git_dir: Path):
        self._process = subprocess.Popen(
            _git_command(["--git-dir", os.fspath(git_dir), "cat-file", "--batch"]),
            env=_git_environment(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def __enter__(self) -> "ObjectReader":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._process.stdin:
            self._process.stdin.close()
        returncode = self._process.wait()
        detail = b""
        if self._process.stderr:
            detail = self._process.stderr.read()
            self._process.stderr.close()
        if self._process.stdout:
            self._process.stdout.close()
        if returncode and exc is None:
            raise GitArchiveError(
                f"git cat-file failed: {detail.decode('utf-8', 'replace').strip()}"
            )

    def read(self, oid: str, expected_type: Optional[str] = None) -> tuple[str, bytes]:
        if not self._process.stdin or not self._process.stdout:
            raise GitArchiveError("git cat-file is not available")
        self._process.stdin.write(oid.encode("ascii") + b"\n")
        self._process.stdin.flush()
        header = self._process.stdout.readline()
        if not header:
            raise GitArchiveError(f"object {oid} could not be read")
        fields = header.rstrip(b"\n").split(b" ")
        if len(fields) == 2 and fields[1] == b"missing":
            raise GitArchiveError(f"object {oid} is missing")
        if len(fields) != 3:
            raise GitArchiveError(f"object {oid} returned an invalid cat-file header")
        actual_oid = fields[0].decode("ascii", "strict")
        object_type = fields[1].decode("ascii", "strict")
        try:
            size = int(fields[2])
        except ValueError as error:
            raise GitArchiveError(f"object {oid} returned an invalid size") from error
        body = self._read_exact(size)
        if self._process.stdout.read(1) != b"\n":
            raise GitArchiveError(f"object {oid} returned invalid framing")
        if actual_oid != oid:
            raise GitArchiveError(f"object lookup changed {oid} to {actual_oid}")
        if expected_type and object_type != expected_type:
            raise GitArchiveError(
                f"object {oid} is {object_type}, expected {expected_type}"
            )
        canonical = (
            object_type.encode("ascii")
            + b" "
            + str(len(body)).encode("ascii")
            + b"\0"
            + body
        )
        actual_hash = hashlib.sha1(canonical).hexdigest()
        if actual_hash != oid:
            raise GitArchiveError(f"object {oid} hashes to {actual_hash}")
        return object_type, body

    def _read_exact(self, size: int) -> bytes:
        if not self._process.stdout:
            raise GitArchiveError("git cat-file is not available")
        chunks: list[bytes] = []
        remaining = size
        while remaining:
            chunk = self._process.stdout.read(remaining)
            if not chunk:
                raise GitArchiveError("git cat-file ended inside an object")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)


def _parse_tree(oid: str, body: bytes) -> TreeNode:
    entries: list[TreeEntry] = []
    offset = 0
    while offset < len(body):
        space = body.find(b" ", offset)
        nul = body.find(b"\0", space + 1 if space >= 0 else offset)
        if space < 0 or nul < 0 or nul + 21 > len(body):
            raise GitArchiveError(f"tree {oid} has invalid framing")
        try:
            mode = body[offset:space].decode("ascii", "strict")
        except UnicodeDecodeError as error:
            raise GitArchiveError(f"tree {oid} has a non-ASCII mode") from error
        name = body[space + 1 : nul]
        object_oid = body[nul + 1 : nul + 21].hex()
        entries.append(TreeEntry(mode=mode, name=name, oid=object_oid))
        offset = nul + 21
    return TreeNode(oid=oid, entries=tuple(entries))


def _display_path(path: bytes) -> str:
    return repr(path.decode("utf-8", "backslashreplace"))


def _is_lfs_pointer(body: bytes) -> bool:
    if len(body) > 8192 or not body.startswith(
        b"version https://git-lfs.github.com/spec/v1\n"
    ):
        return False
    lines = body.splitlines()
    has_oid = any(
        len(line) == 75
        and line.startswith(b"oid sha256:")
        and all(byte in b"0123456789abcdef" for byte in line[11:])
        for line in lines[1:]
    )
    has_size = any(
        line.startswith(b"size ") and line[5:].isdigit() for line in lines[1:]
    )
    return has_oid and has_size


def inspect_commit(
    git_dir: Path,
    commit_sha: str,
    *,
    lfs_policy: str,
    gitlink_policy: str,
) -> InspectedCommit:
    with ObjectReader(git_dir) as reader:
        _, commit_body = reader.read(commit_sha, "commit")
        canonical = (
            b"commit " + str(len(commit_body)).encode("ascii") + b"\0" + commit_body
        )
        if hashlib.sha1(canonical).hexdigest() != commit_sha:
            raise GitArchiveError(f"commit {commit_sha} failed canonical hashing")
        first_line = commit_body.split(b"\n", 1)[0]
        if len(first_line) != 45 or not first_line.startswith(b"tree "):
            raise GitArchiveError(f"commit {commit_sha} has no SHA-1 root tree")
        try:
            root_tree = first_line[5:].decode("ascii", "strict")
        except UnicodeDecodeError as error:
            raise GitArchiveError(f"commit {commit_sha} has an invalid root tree") from error
        if len(root_tree) != 40 or any(char not in "0123456789abcdef" for char in root_tree):
            raise GitArchiveError(f"commit {commit_sha} has an invalid root tree")
        audit = _audit_tree(
            reader,
            root_tree,
            lfs_policy=lfs_policy,
            gitlink_policy=gitlink_policy,
        )
    return InspectedCommit(canonical_bytes=canonical, root_tree=root_tree, audit=audit)


def audit_existing_tree(
    git_dir: Path,
    root_tree: str,
    *,
    lfs_policy: str,
    gitlink_policy: str,
) -> TreeAudit:
    with ObjectReader(git_dir) as reader:
        return _audit_tree(
            reader,
            root_tree,
            lfs_policy=lfs_policy,
            gitlink_policy=gitlink_policy,
        )


def _audit_tree(
    reader: ObjectReader,
    root_tree: str,
    *,
    lfs_policy: str,
    gitlink_policy: str,
) -> TreeAudit:
    issues: list[str] = []
    object_oids: set[str] = set()
    lfs_paths: list[bytes] = []
    gitlink_paths: list[bytes] = []
    blob_lfs: dict[str, bool] = {}
    active_trees: set[str] = set()

    def walk(tree_oid: str, prefix: bytes) -> TreeNode:
        if tree_oid in active_trees:
            issues.append(f"tree cycle at {_display_path(prefix)}")
            return TreeNode(tree_oid, ())
        active_trees.add(tree_oid)
        object_oids.add(tree_oid)
        try:
            _, tree_body = reader.read(tree_oid, "tree")
            parsed = _parse_tree(tree_oid, tree_body)
        except GitArchiveError as error:
            issues.append(f"{_display_path(prefix)}: {error}")
            active_trees.remove(tree_oid)
            return TreeNode(tree_oid, ())
        seen_names: dict[str, bytes] = {}
        hydrated: list[TreeEntry] = []
        for entry in parsed.entries:
            path = entry.name if not prefix else prefix + b"/" + entry.name
            try:
                decoded = entry.name.decode("utf-8", "strict")
            except UnicodeDecodeError:
                issues.append(f"{_display_path(path)} is not valid UTF-8")
                decoded = entry.name.decode("utf-8", "replace")
            normalized = unicodedata.normalize("NFC", decoded).casefold()
            previous = seen_names.get(normalized)
            if previous is not None:
                issues.append(
                    f"case or normalization collision between "
                    f"{_display_path(prefix + b'/' + previous if prefix else previous)} and "
                    f"{_display_path(path)}"
                )
            else:
                seen_names[normalized] = entry.name
            if not entry.name or entry.name in (b".", b"..") or b"/" in entry.name:
                issues.append(f"unsafe path component at {_display_path(path)}")
            if normalized == ".git":
                issues.append(f"forbidden .git path component at {_display_path(path)}")

            if entry.mode == "40000":
                child = walk(entry.oid, path)
                if not child.entries:
                    issues.append(f"empty tree cannot be staged at {_display_path(path)}")
                hydrated.append(TreeEntry(entry.mode, entry.name, entry.oid, child))
                continue
            if entry.mode in ("100644", "100755", "120000"):
                object_oids.add(entry.oid)
                try:
                    if entry.oid not in blob_lfs:
                        _, blob = reader.read(entry.oid, "blob")
                        blob_lfs[entry.oid] = _is_lfs_pointer(blob)
                    else:
                        _, blob = reader.read(entry.oid, "blob")
                    if blob_lfs[entry.oid]:
                        lfs_paths.append(path)
                    if entry.mode == "120000" and b"\0" in blob:
                        issues.append(f"symlink target contains NUL at {_display_path(path)}")
                except GitArchiveError as error:
                    issues.append(f"{_display_path(path)}: {error}")
                hydrated.append(entry)
                continue
            if entry.mode == "160000":
                gitlink_paths.append(path)
                hydrated.append(entry)
                continue
            issues.append(f"unsupported mode {entry.mode} at {_display_path(path)}")
            hydrated.append(entry)
        active_trees.remove(tree_oid)
        return TreeNode(tree_oid, tuple(hydrated))

    root = walk(root_tree, b"")
    if not root.entries:
        issues.append("root tree is empty and cannot be staged")
    if lfs_policy == "reject":
        issues.extend(
            f"Git LFS pointer rejected at {_display_path(path)}" for path in lfs_paths
        )
    if gitlink_policy == "reject":
        issues.extend(f"gitlink rejected at {_display_path(path)}" for path in gitlink_paths)
    if issues:
        raise TreeAuditError(issues)
    return TreeAudit(
        root=root,
        object_oids=tuple(sorted(object_oids)),
        lfs_paths=tuple(lfs_paths),
        gitlink_paths=tuple(gitlink_paths),
    )


def copy_objects(source_git_dir: Path, target_git_dir: Path, object_oids: Iterable[str]) -> None:
    oids = tuple(dict.fromkeys(object_oids))
    if not oids:
        return
    with tempfile.TemporaryFile() as pack:
        producer = subprocess.run(
            _git_command(
                ["--git-dir", os.fspath(source_git_dir), "pack-objects", "--stdout"]
            ),
            env=_git_environment(),
            input=("\n".join(oids) + "\n").encode("ascii"),
            stdout=pack,
            stderr=subprocess.PIPE,
            check=False,
        )
        if producer.returncode:
            detail = producer.stderr.decode("utf-8", "replace").strip()
            raise GitArchiveError(f"git pack-objects failed: {detail}")
        pack.seek(0)
        consumer = subprocess.run(
            _git_command(["--git-dir", os.fspath(target_git_dir), "index-pack", "--stdin"]),
            env=_git_environment(),
            stdin=pack,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if consumer.returncode:
            detail = consumer.stderr.decode("utf-8", "replace").strip()
            raise GitArchiveError(f"git index-pack failed: {detail}")


def write_blob(git_dir: Path, body: bytes) -> str:
    return run_git(
        ["--git-dir", os.fspath(git_dir), "hash-object", "-w", "-t", "blob", "--stdin"],
        input_bytes=body,
    ).decode("ascii").strip()


@dataclass(frozen=True)
class Repository:
    root: Path
    git_dir: Path
    index_path: Path

    @classmethod
    def discover(cls, start: Path) -> "Repository":
        root = Path(run_git(["-C", os.fspath(start), "rev-parse", "--show-toplevel"]).decode().strip())
        git_dir = Path(
            run_git(["-C", os.fspath(root), "rev-parse", "--absolute-git-dir"])
            .decode()
            .strip()
        )
        object_format = (
            run_git(["-C", os.fspath(root), "rev-parse", "--show-object-format"])
            .decode()
            .strip()
        )
        if object_format != "sha1":
            raise GitArchiveError(f"target repository uses {object_format}, expected sha1")
        index_text = (
            run_git(["-C", os.fspath(root), "rev-parse", "--git-path", "index"])
            .decode()
            .strip()
        )
        index_path = Path(index_text)
        if not index_path.is_absolute():
            index_path = root / index_path
        return cls(root=root, git_dir=git_dir, index_path=index_path)

    def head_tree(self) -> str:
        return (
            run_git(["-C", os.fspath(self.root), "rev-parse", "HEAD^{tree}"])
            .decode("ascii")
            .strip()
        )

    def index_tree(self, index_file: Optional[Path] = None, alternates: Optional[Path] = None) -> str:
        env: dict[str, str] = {}
        if index_file:
            env["GIT_INDEX_FILE"] = os.fspath(index_file)
        if alternates:
            env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = os.fspath(alternates / "objects")
        return (
            run_git(["-C", os.fspath(self.root), "write-tree"], extra_env=env)
            .decode("ascii")
            .strip()
        )

    def create_desired_index(
        self,
        *,
        snapshots: Mapping[str, str],
        commit_blobs: Mapping[str, str],
        quarantine_git_dir: Path,
    ) -> tuple[Path, str, bytes]:
        initial_index = self.index_path.read_bytes()
        handle, name = tempfile.mkstemp(prefix="loomq-index-")
        index_file = Path(name)
        with os.fdopen(handle, "wb") as temporary_index:
            temporary_index.write(initial_index)
        env = {
            "GIT_INDEX_FILE": os.fspath(index_file),
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": os.fspath(quarantine_git_dir / "objects"),
        }
        try:
            base_tree = self.index_tree(index_file, quarantine_git_dir)
            run_git(
                ["-C", os.fspath(self.root), "read-tree", base_tree],
                extra_env=env,
            )
            managed = run_git(
                ["-C", os.fspath(self.root), "ls-files", "-z", "--", "archive/generated"],
                extra_env=env,
            )
            if managed:
                run_git(
                    [
                        "-C",
                        os.fspath(self.root),
                        "update-index",
                        "--force-remove",
                        "-z",
                        "--stdin",
                    ],
                    input_bytes=managed,
                    extra_env=env,
                )
            index_info = b"".join(
                f"100644 {oid}\tarchive/generated/commit-objects/{contestant_id}.obj\0".encode(
                    "utf-8"
                )
                for contestant_id, oid in commit_blobs.items()
            )
            run_git(
                [
                    "-C",
                    os.fspath(self.root),
                    "update-index",
                    "--add",
                    "-z",
                    "--index-info",
                ],
                input_bytes=index_info,
                extra_env=env,
            )
            for contestant_id, tree_oid in snapshots.items():
                prefix = f"archive/generated/snapshots/{contestant_id}/"
                run_git(
                    [
                        "-C",
                        os.fspath(self.root),
                        "read-tree",
                        f"--prefix={prefix}",
                        tree_oid,
                    ],
                    extra_env=env,
                )
            desired_tree = self.index_tree(index_file, quarantine_git_dir)
            return index_file, desired_tree, initial_index
        except BaseException:
            if index_file.exists():
                index_file.unlink()
            raise

    def import_objects(self, quarantine_git_dir: Path, object_oids: Iterable[str]) -> None:
        copy_objects(quarantine_git_dir, self.git_dir, object_oids)

    def publish(
        self,
        *,
        desired_index: Path,
        initial_index: bytes,
        generated_directory: Path,
    ) -> None:
        lock_path = Path(os.fspath(self.index_path) + ".lock")
        lock_fd: Optional[int] = None
        backup: Optional[Path] = None
        destination = self.root / "archive" / "generated"
        installed_worktree = False
        try:
            try:
                lock_fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError as error:
                raise GitArchiveError(f"index lock already exists at {lock_path}") from error
            current_index = self.index_path.read_bytes()
            if current_index != initial_index:
                raise GitArchiveError("repository index changed during sync")
            desired_bytes = desired_index.read_bytes()
            with os.fdopen(lock_fd, "wb", closefd=True) as lock_file:
                lock_fd = None
                lock_file.write(desired_bytes)
                lock_file.flush()
                os.fsync(lock_file.fileno())
            if os.path.lexists(destination):
                backup = destination.parent / f".loomq-generated-backup-{uuid.uuid4().hex}"
                os.rename(destination, backup)
            os.rename(generated_directory, destination)
            installed_worktree = True
            os.replace(lock_path, self.index_path)
        except BaseException:
            if installed_worktree and os.path.lexists(destination):
                _remove_path(destination)
            if backup and os.path.lexists(backup):
                os.rename(backup, destination)
            if lock_fd is not None:
                os.close(lock_fd)
            if os.path.lexists(lock_path):
                os.unlink(lock_path)
            raise
        finally:
            if desired_index.exists():
                desired_index.unlink()
        if backup and os.path.lexists(backup):
            _remove_path(backup)


def _remove_path(path: Path) -> None:
    mode = os.lstat(path).st_mode
    if stat.S_ISDIR(mode) and not stat.S_ISLNK(mode):
        shutil.rmtree(path)
    else:
        os.unlink(path)


def materialize_generated(
    git_dir: Path,
    destination: Path,
    *,
    commits: Mapping[str, bytes],
    snapshots: Mapping[str, TreeNode],
) -> None:
    commit_directory = destination / "commit-objects"
    snapshot_directory = destination / "snapshots"
    commit_directory.mkdir()
    snapshot_directory.mkdir()
    with ObjectReader(git_dir) as reader:
        for contestant_id, canonical in commits.items():
            _write_regular(commit_directory / f"{contestant_id}.obj", canonical, False)
        for contestant_id, root in snapshots.items():
            path = snapshot_directory / contestant_id
            path.mkdir()
            _materialize_tree(reader, root, os.fsencode(path))


def _materialize_tree(reader: ObjectReader, node: TreeNode, destination: bytes) -> None:
    for entry in node.entries:
        path = os.path.join(destination, entry.name)
        if entry.mode == "40000":
            os.mkdir(path, 0o755)
            if entry.child is None:
                raise GitArchiveError(f"tree {entry.oid} was not audited")
            _materialize_tree(reader, entry.child, path)
        elif entry.mode in ("100644", "100755"):
            _, body = reader.read(entry.oid, "blob")
            _write_regular(path, body, entry.mode == "100755")
        elif entry.mode == "120000":
            _, target = reader.read(entry.oid, "blob")
            os.symlink(target, path)
        elif entry.mode == "160000":
            os.mkdir(path, 0o755)
        else:
            raise GitArchiveError(f"unsupported mode {entry.mode}")


def _write_regular(path: os.PathLike[str] | os.PathLike[bytes], body: bytes, executable: bool) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o700 if executable else 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as output:
            output.write(body)
            output.flush()
        os.chmod(path, 0o755 if executable else 0o644, follow_symlinks=False)
    finally:
        os.close(fd)


def verify_generated_worktree(
    generated_directory: Path,
    *,
    git_dir: Path,
    commits: Mapping[str, bytes],
    snapshots: Mapping[str, TreeNode],
) -> tuple[str, ...]:
    issues: list[str] = []
    root = os.fsencode(generated_directory)
    expected_root = {b"commit-objects", b"snapshots"}
    actual_root = _list_directory(root, issues, "archive/generated")
    _compare_names(actual_root, expected_root, b"archive/generated", issues)
    commit_root = os.path.join(root, b"commit-objects")
    snapshot_root = os.path.join(root, b"snapshots")
    actual_commits = _list_directory(commit_root, issues, "archive/generated/commit-objects")
    expected_commits = {os.fsencode(f"{contestant_id}.obj") for contestant_id in commits}
    _compare_names(actual_commits, expected_commits, b"archive/generated/commit-objects", issues)
    for contestant_id, canonical in commits.items():
        path = os.path.join(commit_root, os.fsencode(f"{contestant_id}.obj"))
        body, executable = _read_regular(path, issues)
        if body is not None and body != canonical:
            issues.append(f"worktree commit record differs for {contestant_id}")
        if executable:
            issues.append(f"worktree commit record is executable for {contestant_id}")
    actual_snapshots = _list_directory(snapshot_root, issues, "archive/generated/snapshots")
    expected_snapshots = {os.fsencode(contestant_id) for contestant_id in snapshots}
    _compare_names(actual_snapshots, expected_snapshots, b"archive/generated/snapshots", issues)
    with ObjectReader(git_dir) as reader:
        for contestant_id, node in snapshots.items():
            path = os.path.join(snapshot_root, os.fsencode(contestant_id))
            actual_oid = _hash_worktree_tree(reader, node, path, issues)
            if actual_oid is not None and actual_oid != node.oid:
                issues.append(
                    f"worktree snapshot {contestant_id} hashes to {actual_oid}, expected {node.oid}"
                )
    return tuple(issues)


def _list_directory(path: bytes, issues: list[str], label: str) -> set[bytes]:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        issues.append(f"worktree directory is missing: {label}")
        return set()
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        issues.append(f"worktree path is not a real directory: {label}")
        return set()
    try:
        return set(os.listdir(path))
    except OSError as error:
        issues.append(f"cannot list worktree directory {label}: {error}")
        return set()


def _compare_names(
    actual: set[bytes], expected: set[bytes], prefix: bytes, issues: list[str]
) -> None:
    for name in sorted(expected - actual):
        issues.append(f"worktree path is missing: {_display_path(prefix + b'/' + name)}")
    for name in sorted(actual - expected):
        issues.append(f"unexpected worktree path: {_display_path(prefix + b'/' + name)}")


def _read_regular(path: bytes, issues: list[str]) -> tuple[Optional[bytes], bool]:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return None, False
    if not stat.S_ISREG(metadata.st_mode):
        issues.append(f"worktree path is not a regular file: {_display_path(path)}")
        return None, False
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as source:
            body = source.read()
    except OSError as error:
        issues.append(f"cannot read worktree file {_display_path(path)}: {error}")
        return None, False
    return body, bool(metadata.st_mode & 0o111)


def _hash_worktree_tree(
    reader: ObjectReader,
    expected: TreeNode,
    path: bytes,
    issues: list[str],
) -> Optional[str]:
    actual_names = _list_directory(path, issues, _display_path(path))
    expected_names = {entry.name for entry in expected.entries}
    before = len(issues)
    _compare_names(actual_names, expected_names, path, issues)
    encoded: list[bytes] = []
    for entry in expected.entries:
        child_path = os.path.join(path, entry.name)
        actual_oid: Optional[str] = None
        actual_mode = entry.mode
        if entry.mode == "40000":
            if entry.child is None:
                issues.append(f"tree {entry.oid} was not audited")
            else:
                actual_oid = _hash_worktree_tree(reader, entry.child, child_path, issues)
        elif entry.mode in ("100644", "100755"):
            body, executable = _read_regular(child_path, issues)
            if body is not None:
                actual_oid = _object_hash("blob", body)
                actual_mode = "100755" if executable else "100644"
                if actual_oid != entry.oid:
                    issues.append(f"worktree file differs at {_display_path(child_path)}")
                if actual_mode != entry.mode:
                    issues.append(f"worktree executable mode differs at {_display_path(child_path)}")
        elif entry.mode == "120000":
            try:
                metadata = os.lstat(child_path)
                if not stat.S_ISLNK(metadata.st_mode):
                    issues.append(f"worktree path is not a symlink: {_display_path(child_path)}")
                else:
                    target = os.readlink(child_path)
                    if isinstance(target, str):
                        target = os.fsencode(target)
                    actual_oid = _object_hash("blob", target)
                    if actual_oid != entry.oid:
                        issues.append(f"worktree symlink differs at {_display_path(child_path)}")
            except FileNotFoundError:
                pass
            except OSError as error:
                issues.append(f"cannot read worktree symlink {_display_path(child_path)}: {error}")
        elif entry.mode == "160000":
            contents = _list_directory(child_path, issues, _display_path(child_path))
            if contents:
                issues.append(f"gitlink worktree directory is not empty at {_display_path(child_path)}")
            else:
                actual_oid = entry.oid
        if actual_oid is not None:
            encoded.append(
                actual_mode.encode("ascii")
                + b" "
                + entry.name
                + b"\0"
                + bytes.fromhex(actual_oid)
            )
    if len(issues) != before or len(encoded) != len(expected.entries):
        return None
    return _object_hash("tree", b"".join(encoded))


def _object_hash(object_type: str, body: bytes) -> str:
    canonical = (
        object_type.encode("ascii")
        + b" "
        + str(len(body)).encode("ascii")
        + b"\0"
        + body
    )
    return hashlib.sha1(canonical).hexdigest()


def load_tree(git_dir: Path, oid: str) -> TreeNode:
    with ObjectReader(git_dir) as reader:
        _, body = reader.read(oid, "tree")
    return _parse_tree(oid, body)


def load_blob(git_dir: Path, oid: str) -> bytes:
    with ObjectReader(git_dir) as reader:
        _, body = reader.read(oid, "blob")
    return body


def find_tree_entry(git_dir: Path, root_oid: str, components: Sequence[bytes]) -> Optional[TreeEntry]:
    current_oid = root_oid
    for index, component in enumerate(components):
        node = load_tree(git_dir, current_oid)
        matches = [entry for entry in node.entries if entry.name == component]
        if len(matches) != 1:
            return None
        entry = matches[0]
        if index == len(components) - 1:
            return entry
        if entry.mode != "40000":
            return None
        current_oid = entry.oid
    return None


def list_tree(git_dir: Path, tree_oid: str) -> Tuple[TreeEntry, ...]:
    return load_tree(git_dir, tree_oid).entries
