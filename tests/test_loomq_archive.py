from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, os.fspath(TOOLS))

import loomq_archive
import loomq_git


def git(repository: Path, *args: str, input_bytes: bytes | None = None) -> str:
    completed = subprocess.run(
        ["git", "-C", os.fspath(repository), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        raise AssertionError(completed.stderr.decode("utf-8", "replace"))
    return completed.stdout.decode("utf-8", "strict").strip()


def create_upstream(root: Path) -> tuple[Path, str, str]:
    upstream = root / "upstream"
    git(root, "init", os.fspath(upstream))
    git(upstream, "config", "user.name", "Fixture")
    git(upstream, "config", "user.email", "fixture@example.com")
    (upstream / "nested").mkdir()
    (upstream / "nested" / "data.txt").write_text("exact bytes\n", encoding="utf-8")
    executable = upstream / "run.sh"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    (upstream / "asset.bin").write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:" + "a" * 64 + "\n"
        "size 123\n",
        encoding="ascii",
    )
    os.symlink("nested/data.txt", upstream / "data-link")
    git(upstream, "add", "--all")
    git(upstream, "commit", "-m", "fixture root")
    gitlink_oid = git(upstream, "rev-parse", "HEAD")
    git(
        upstream,
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{gitlink_oid},vendor/submission",
    )
    git(upstream, "commit", "-m", "fixture gitlink")
    commit_sha = git(upstream, "rev-parse", "HEAD")
    tree_oid = git(upstream, "rev-parse", "HEAD^{tree}")
    return upstream, commit_sha, tree_oid


def create_target(root: Path, spec: loomq_archive.SubmissionSpec) -> loomq_git.Repository:
    target = root / "target"
    git(root, "init", os.fspath(target))
    git(target, "config", "user.name", "Fixture")
    git(target, "config", "user.email", "fixture@example.com")
    (target / "archive").mkdir()
    manifest = {
        "schema_version": 1,
        "submission_count": 1,
        "policies": {"git_lfs": "pointer-only", "gitlinks": "pointer-only"},
        "submissions": [
            {
                "contestant_id": spec.contestant_id,
                "repository_url": spec.repository_url,
                "commit_sha": spec.commit_sha,
            }
        ],
    }
    (target / "archive" / "submissions.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (target / "README.md").write_text("fixture\n", encoding="utf-8")
    git(target, "add", "README.md", "archive/submissions.json")
    git(target, "commit", "-m", "target root")
    return loomq_git.Repository.discover(target)


class ManifestTests(unittest.TestCase):
    def test_checked_in_manifest_is_complete(self) -> None:
        path = Path(__file__).resolve().parents[1] / "archive" / "submissions.json"
        manifest = loomq_archive.load_manifest(path)
        self.assertEqual(58, manifest.submission_count)
        self.assertEqual(58, len(manifest.submissions))

    def test_rejects_case_colliding_ids_before_fetch(self) -> None:
        first = loomq_archive.SubmissionSpec(
            "Alpha", "https://github.com/example/one", "1" * 40
        )
        second = loomq_archive.SubmissionSpec(
            "alpha", "https://github.com/example/two", "2" * 40
        )
        with self.assertRaisesRegex(loomq_archive.ManifestError, "duplicate contestant_id"):
            loomq_archive.Manifest(2, "pointer-only", "pointer-only", (first, second))

    def test_rejects_non_verbatim_url_and_uppercase_sha(self) -> None:
        with self.assertRaises(loomq_archive.ManifestError) as raised:
            loomq_archive.SubmissionSpec(
                "safe", "http://github.com/example/repo.git", "A" * 40
            )
        self.assertIn("malformed GitHub HTTPS URL", str(raised.exception))
        self.assertIn("lowercase", str(raised.exception))

    def test_rejects_count_drift(self) -> None:
        spec = loomq_archive.SubmissionSpec(
            "safe", "https://github.com/example/repo", "1" * 40
        )
        with self.assertRaisesRegex(loomq_archive.ManifestError, "submission_count"):
            loomq_archive.Manifest(2, "pointer-only", "pointer-only", (spec,))


class ArchiveIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="loomq-test-")
        self.root = Path(self.temporary.name)
        self.upstream, commit_sha, self.upstream_tree = create_upstream(self.root)
        self.spec = loomq_archive.SubmissionSpec(
            "fixture", "https://github.com/example/fixture", commit_sha
        )
        self.manifest = loomq_archive.Manifest(
            1, "pointer-only", "pointer-only", (self.spec,)
        )
        self.repository = create_target(self.root, self.spec)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def loader(self, spec: loomq_archive.SubmissionSpec, git_dir: Path) -> None:
        loomq_git.run_git(
            [
                "-c",
                "protocol.file.allow=always",
                "--git-dir",
                os.fspath(git_dir),
                "fetch",
                "--force",
                "--no-tags",
                "--no-write-fetch-head",
                "--depth=1",
                os.fspath(self.upstream),
                spec.commit_sha,
            ]
        )

    def test_sync_verify_commit_and_noop_rerun(self) -> None:
        report = loomq_archive.sync_archive(
            self.repository, self.manifest, source_loader=self.loader
        )
        self.assertEqual(1, report.lfs_count)
        self.assertEqual(1, report.gitlink_count)
        staged = loomq_archive.verify_archive(
            self.repository, self.manifest, staged=True
        )
        self.assertEqual(report, staged)
        mode = os.lstat(
            self.repository.root / "archive/generated/snapshots/fixture/run.sh"
        ).st_mode
        self.assertTrue(mode & 0o111)
        self.assertEqual(
            "nested/data.txt",
            os.readlink(
                self.repository.root / "archive/generated/snapshots/fixture/data-link"
            ),
        )
        git(self.repository.root, "commit", "-m", "archive fixture")
        committed = loomq_archive.verify_archive(self.repository, self.manifest)
        self.assertEqual(report, committed)
        loomq_archive.sync_archive(
            self.repository, self.manifest, source_loader=self.loader
        )
        self.assertEqual("", git(self.repository.root, "diff", "--name-only"))
        self.assertEqual("", git(self.repository.root, "diff", "--cached", "--name-only"))

    def test_fetch_failure_preserves_index_and_worktree(self) -> None:
        loomq_archive.sync_archive(
            self.repository, self.manifest, source_loader=self.loader
        )
        index_before = self.repository.index_path.read_bytes()
        record = self.repository.root / "archive/generated/commit-objects/fixture.obj"
        record_before = hashlib.sha256(record.read_bytes()).digest()

        def fail_loader(spec: loomq_archive.SubmissionSpec, git_dir: Path) -> None:
            raise loomq_git.GitArchiveError("fixture fetch failed")

        with self.assertRaisesRegex(loomq_archive.ArchiveError, "fixture fetch failed"):
            loomq_archive.sync_archive(
                self.repository, self.manifest, source_loader=fail_loader
            )
        self.assertEqual(index_before, self.repository.index_path.read_bytes())
        self.assertEqual(record_before, hashlib.sha256(record.read_bytes()).digest())

    def test_staged_verification_detects_symlink_tampering(self) -> None:
        loomq_archive.sync_archive(
            self.repository, self.manifest, source_loader=self.loader
        )
        link = self.repository.root / "archive/generated/snapshots/fixture/data-link"
        link.unlink()
        os.symlink("outside", link)
        with self.assertRaisesRegex(loomq_archive.ArchiveError, "symlink differs"):
            loomq_archive.verify_archive(self.repository, self.manifest, staged=True)


if __name__ == "__main__":
    unittest.main()
