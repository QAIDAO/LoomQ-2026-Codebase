# LoomQ 2026 submission archive

This repository archives all 58 formal LoomQ 2026 submissions. Each entry records the organizer-supplied GitHub HTTPS URL and an exact 40-character commit SHA in `archive/submissions.json`.

## Exactness proof

`archive/generated/snapshots/<contestant_id>/` is the exact root Git tree from the recorded upstream commit. The sync tool grafts that tree object into this repository. It does not copy a checkout, run `git archive`, or rebuild the tree from files.

`archive/generated/commit-objects/<contestant_id>.obj` stores the canonical commit object bytes, including the Git object header. Offline verification proves both conditions for every submission:

```text
sha1(canonical commit object bytes) == manifest commit SHA
commit root tree OID == archived snapshot subtree OID
```

Verification also rejects missing or extra contestant paths and commit records.

## Update and verify the archive

Run these commands from the repository:

```sh
python3 tools/loomq_archive.py sync
python3 tools/loomq_archive.py verify --staged
git commit
python3 tools/loomq_archive.py verify
python3 tools/loomq_archive.py verify --remote
```

`sync` fetches only each exact SHA over HTTPS. It validates all 58 manifest rows before the first fetch. It builds the complete result in isolated bare repositories. After every submission passes, it replaces the generated worktree and stages `archive/submissions.json` with the complete generated archive. A second `sync` with unchanged inputs produces no staged or unstaged diff.

Edit only `archive/submissions.json` to change the roster. The sync tool owns all files under `archive/generated/` and removes stale generated paths.

## Untrusted content and external objects

All submission contents are untrusted. Do not run scripts, builds, package managers, tests, hooks, or discovery tools under `archive/generated/snapshots/`. The archive workflow and CI only read Git objects and file metadata.

The manifest uses the `pointer-only` policy for Git LFS pointers and gitlinks. Git LFS pointer files remain exact pointer blobs. Their external payloads are not part of this archive. Gitlinks retain the submitted commit OID, but nested repository contents are not part of this archive.

The tool preserves executable modes and symlink targets. It rejects paths that cannot be safely materialized, including `.git` components, prefix collisions, and case or Unicode-normalization collisions.
