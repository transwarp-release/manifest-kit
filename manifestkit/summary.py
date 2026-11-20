"""Summarize a saved inventory without reading or modifying source files."""

from pathlib import PurePosixPath

from .core import Manifest


def summarize_manifest(manifest: Manifest) -> dict:
    groups = {}
    for entry in manifest.files:
        suffix = PurePosixPath(entry.path).suffix
        extension = suffix.casefold() if suffix not in {"", "."} else "(no extension)"
        group = groups.setdefault(extension, {"extension": extension, "file_count": 0, "total_bytes": 0})
        group["file_count"] += 1
        group["total_bytes"] += entry.size
    return {
        "report_type": "extension_summary",
        "file_count": len(manifest.files),
        "total_bytes": manifest.total_bytes,
        "extensions": [groups[key] for key in sorted(groups)],
    }
