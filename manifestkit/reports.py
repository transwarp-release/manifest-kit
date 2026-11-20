"""Markdown renderers; filenames are treated as text, never as instructions."""

import html
import re

from .core import Manifest


def _cell(value: str) -> str:
    value = html.escape(str(value), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|~\-])", r"\\\1", value)


def manifest_markdown(manifest: Manifest) -> str:
    lines = [
        "# File manifest", "",
        f"Files: {len(manifest.files)}  ",
        f"Total bytes: {manifest.total_bytes}  ",
        "Hash algorithm: SHA-256", "",
        "Excluded patterns: " + ", ".join(_cell(item) for item in manifest.exclude), "",
        "| Relative path | Bytes | SHA-256 |",
        "| --- | ---: | --- |",
    ]
    lines.extend(
        f"| {_cell(entry.path)} | {entry.size} | `{entry.sha256}` |"
        for entry in manifest.files
    )
    return "\n".join(lines) + "\n"


def comparison_markdown(result: dict) -> str:
    lines = [
        "# Integrity comparison", "",
        f"Status: **{result['status']}**", "",
        "| Metric | Count |", "| --- | ---: |",
        f"| Baseline files | {result['baseline_file_count']} |",
        f"| Current files | {result['current_file_count']} |",
        f"| Unchanged | {result['unchanged_count']} |",
        f"| Added | {len(result['added'])} |",
        f"| Removed | {len(result['removed'])} |",
        f"| Changed | {len(result['changed'])} |", "",
        "Exclusion policy changed: " + str(result["exclusions_changed"]).lower(), "",
        "| Change | Relative path |", "| --- | --- |",
    ]
    for category in ("added", "removed"):
        lines.extend(f"| {category} | {_cell(path)} |" for path in result[category])
    lines.extend(f"| changed | {_cell(item['path'])} |" for item in result["changed"])
    return "\n".join(lines) + "\n"


def summary_markdown(result: dict) -> str:
    lines = [
        "# File extension summary", "",
        f"Files: {result['file_count']}  ",
        f"Total bytes: {result['total_bytes']}", "",
        "| Extension | Files | Bytes |", "| --- | ---: | ---: |",
    ]
    lines.extend(
        f"| {_cell(group['extension'])} | {group['file_count']} | {group['total_bytes']} |"
        for group in result["extensions"]
    )
    return "\n".join(lines) + "\n"
