"""Thin, dependency-free entry point for the verify-file-manifest skill."""

from pathlib import Path
import sys

# Import only the application shipped in this same repository.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from manifestkit.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["verify", *sys.argv[1:]]))
