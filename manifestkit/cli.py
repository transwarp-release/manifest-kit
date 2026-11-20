"""Command-line interface with machine-readable output and explicit exit codes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from . import __version__
from .config import load_excludes
from .core import ManifestError, compare_manifests, is_linklike, load_manifest, scan_tree
from .reports import comparison_markdown, manifest_markdown, summary_markdown
from .summary import summarize_manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create and verify portable SHA-256 file inventories.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples (run from the repository root):\n"
            "  python -m manifestkit scan examples/demo --output .local/manifest.json\n"
            "  python -m manifestkit verify examples/demo --manifest .local/manifest.json\n"
            "  python -m manifestkit diff .local/manifest.json .local/manifest.json\n\n"
            "  python -m manifestkit summary .local/manifest.json\n\n"
            "Exit codes: 0 = success / match, 1 = differences, 2 = input or I/O error.\n"
            "Keep output reports outside the scanned directory."
        ),
    )
    parser.add_argument("--version", action="version", version=f"manifest-kit {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan", help="Create a deterministic file manifest.")
    scan.add_argument("root", type=Path, help="Directory to inventory; source files are read only.")
    scan.add_argument("--config", type=Path, help="TOML file with a [scan] exclude array.")
    scan.add_argument(
        "--exclude", action="append", default=[], metavar="GLOB",
        help="Case-sensitive glob; repeat to combine patterns with the configuration.",
    )
    verify = commands.add_parser("verify", help="Compare a directory against a saved manifest.")
    verify.add_argument("root", type=Path, help="Directory to check against the saved manifest.")
    verify.add_argument("--manifest", type=Path, required=True, help="Baseline JSON; its exclusions are reused.")
    diff = commands.add_parser("diff", help="Compare two saved manifests without reading their source trees.")
    diff.add_argument("baseline", type=Path, help="Earlier manifest JSON.")
    diff.add_argument("current", type=Path, help="Later manifest JSON.")
    summary = commands.add_parser("summary", help="Summarize a saved manifest by file extension.")
    summary.add_argument("manifest", type=Path, help="Saved manifest JSON; source files are not needed.")
    for command in (scan, verify, diff, summary):
        command.add_argument("--output", type=Path, help="Write UTF-8 JSON here instead of stdout.")
        command.add_argument("--markdown", type=Path, help="Also write a Markdown report.")
        command.add_argument("--force", action="store_true", help="Replace existing report files.")
    return parser


def _check_destinations(args: argparse.Namespace, protected: list[Path]) -> None:
    destinations = [path for path in (args.output, args.markdown) if path is not None]
    resolved = [path.resolve() for path in destinations]
    if len(set(resolved)) != len(resolved):
        raise ManifestError("JSON and Markdown outputs must be different files.")
    for path, target in zip(destinations, resolved):
        if target in {item.resolve() for item in protected}:
            raise ManifestError("A report cannot replace an input file.")
        if args.command in {"scan", "verify"} and target.is_relative_to(args.root.resolve()):
            raise ManifestError("Keep reports outside the scanned directory.")
        if path.exists() or path.is_symlink():
            if is_linklike(path) or not path.is_file():
                raise ManifestError("A report destination must be a regular file, not a link or directory.")
            if not args.force:
                raise ManifestError(f"Report already exists; choose a new path or use --force: {path}")


def _write_text(path: Path, content: str, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not force:
        with path.open("x", encoding="utf-8", newline="\n") as output:
            output.write(content)
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=".manifestkit-", suffix=".tmp", delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        protected = []
        if args.command == "scan":
            if args.config:
                protected.append(args.config)
        elif args.command in {"verify", "summary"}:
            protected.append(args.manifest)
        else:
            protected.extend((args.baseline, args.current))
        _check_destinations(args, protected)
        if args.command == "scan":
            manifest = scan_tree(args.root, (*load_excludes(args.config), *args.exclude))
            data = manifest.to_dict()
            markdown = manifest_markdown(manifest)
            code = 0
        elif args.command == "summary":
            data = summarize_manifest(load_manifest(args.manifest))
            markdown = summary_markdown(data)
            code = 0
        else:
            if args.command == "verify":
                baseline = load_manifest(args.manifest)
                current = scan_tree(args.root, baseline.exclude)
            else:
                baseline = load_manifest(args.baseline)
                current = load_manifest(args.current)
            data = compare_manifests(baseline, current)
            markdown = comparison_markdown(data)
            code = 0 if data["status"] == "match" else 1
        encoded = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            _write_text(args.output, encoded, args.force)
        else:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            sys.stdout.write(encoded)
        if args.markdown:
            _write_text(args.markdown, markdown, args.force)
        return code
    except (OSError, ValueError, UnicodeError, RecursionError) as error:
        print(f"manifest-kit: {error}", file=sys.stderr)
        return 2
