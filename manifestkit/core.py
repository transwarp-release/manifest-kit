"""Deterministic inventories and comparisons; input files are read only."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

DEFAULT_EXCLUDES = (
    ".git", ".hg", ".svn", ".local", ".venv", "venv", "__pycache__", "node_modules"
)
CHUNK_SIZE = 1024 * 1024


class ManifestError(ValueError):
    """An input cannot be represented or checked reliably."""


def normalize_excludes(patterns: Iterable[str]) -> tuple[str, ...]:
    values = list(patterns)
    if any(
        not isinstance(value, str)
        or not value
        or "\\" in value
        or any(ord(char) < 32 for char in value)
        for value in values
    ):
        raise ManifestError("Exclude patterns must be nonempty strings using forward slashes.")
    return tuple(sorted(set(values)))


def portable_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError("Each file needs a nonempty relative path.")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or str(path) != value
        or value == "."
        or "\\" in value
        or ":" in value
        or any(ord(char) < 32 for char in value)
    ):
        raise ManifestError(f"Not a portable relative file path: {value!r}")
    return value


def is_linklike(path: Path) -> bool:
    """Include Windows junctions and other reparse points in the link check."""
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


@dataclass(frozen=True)
class FileEntry:
    path: str
    size: int
    sha256: str

    def to_dict(self) -> dict:
        return {"path": self.path, "size": self.size, "sha256": self.sha256}


@dataclass(frozen=True)
class Manifest:
    files: tuple[FileEntry, ...]
    exclude: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "format_version": 1,
            "hash_algorithm": "sha256",
            "exclude": list(self.exclude),
            "files": [entry.to_dict() for entry in self.files],
        }

    @property
    def total_bytes(self) -> int:
        return sum(entry.size for entry in self.files)


def is_excluded(relative: str, patterns: tuple[str, ...]) -> bool:
    parts = PurePosixPath(relative).parts
    return any(
        fnmatch.fnmatchcase(relative, pattern)
        or ("/" not in pattern and any(fnmatch.fnmatchcase(part, pattern) for part in parts))
        for pattern in patterns
    )


def _fingerprint(path: Path, relative: str) -> FileEntry:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ManifestError(f"Not a regular file: {relative}")
        while chunk := source.read(CHUNK_SIZE):
            digest.update(chunk)
            byte_count += len(chunk)
        after = os.fstat(source.fileno())
    if (
        (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        or byte_count != after.st_size
    ):
        raise ManifestError(f"File changed during scanning; retry with a stable tree: {relative}")
    return FileEntry(portable_path(relative), byte_count, digest.hexdigest())


def scan_tree(root: Path | str, exclude: Iterable[str] = ()) -> Manifest:
    root = Path(root)
    if is_linklike(root) or not root.is_dir():
        raise ManifestError("The scan root must be a real directory, not a link or junction.")
    patterns = normalize_excludes((*DEFAULT_EXCLUDES, *exclude))
    root = root.resolve()
    files = []
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as children:
            entries = sorted(children, key=lambda entry: entry.name)
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix()
            if is_excluded(relative, patterns) or is_linklike(path):
                continue
            if entry.is_dir(follow_symlinks=False):
                pending.append(path)
            elif entry.is_file(follow_symlinks=False):
                files.append(_fingerprint(path, relative))
    return Manifest(tuple(sorted(files, key=lambda item: item.path)), patterns)


def load_manifest(path: Path | str) -> Manifest:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {
        "format_version", "hash_algorithm", "exclude", "files"
    }:
        raise ManifestError("Unsupported manifest fields.")
    if type(raw["format_version"]) is not int or raw["format_version"] != 1:
        raise ManifestError("Only manifest format_version 1 is supported.")
    if raw["hash_algorithm"] != "sha256":
        raise ManifestError("Only SHA-256 manifests are supported.")
    if not isinstance(raw["exclude"], list) or not isinstance(raw["files"], list):
        raise ManifestError("Manifest exclude and files must be arrays.")
    exclude = normalize_excludes(raw["exclude"])
    if not set(DEFAULT_EXCLUDES).issubset(exclude):
        raise ManifestError("The manifest must retain the default exclusions.")
    files = []
    seen = set()
    for item in raw["files"]:
        if not isinstance(item, dict) or set(item) != {"path", "size", "sha256"}:
            raise ManifestError("Each file must contain path, size and sha256.")
        relative = portable_path(item["path"])
        if relative in seen:
            raise ManifestError(f"Duplicate file path: {relative}")
        if type(item["size"]) is not int or item["size"] < 0:
            raise ManifestError(f"Invalid byte size for: {relative}")
        if not isinstance(item["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ManifestError(f"Invalid SHA-256 value for: {relative}")
        if is_excluded(relative, exclude):
            raise ManifestError(f"Manifest file conflicts with its exclusion policy: {relative}")
        seen.add(relative)
        files.append(FileEntry(relative, item["size"], item["sha256"]))
    return Manifest(tuple(sorted(files, key=lambda item: item.path)), exclude)


def compare_manifests(baseline: Manifest, current: Manifest) -> dict:
    before = {entry.path: entry for entry in baseline.files}
    after = {entry.path: entry for entry in current.files}
    common = before.keys() & after.keys()
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())
    changed = [
        {"path": path, "before": before[path].to_dict(), "after": after[path].to_dict()}
        for path in sorted(common)
        if before[path] != after[path]
    ]
    policy_changed = baseline.exclude != current.exclude
    return {
        "status": "different" if added or removed or changed or policy_changed else "match",
        "baseline_file_count": len(baseline.files),
        "current_file_count": len(current.files),
        "unchanged_count": len(common) - len(changed),
        "added": added,
        "removed": removed,
        "changed": changed,
        "exclusions_changed": policy_changed,
        "baseline_exclude": list(baseline.exclude),
        "current_exclude": list(current.exclude),
    }
