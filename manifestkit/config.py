"""Read optional, data-only TOML scan settings."""

from pathlib import Path
import tomllib

from .core import ManifestError, normalize_excludes


def load_excludes(path: Path | str | None) -> tuple[str, ...]:
    if path is None:
        return ()
    with Path(path).open("rb") as source:
        config = tomllib.load(source)
    if set(config) != {"scan"} or not isinstance(config["scan"], dict):
        raise ManifestError("The configuration must contain a [scan] table.")
    settings = config["scan"]
    if set(settings) - {"exclude"}:
        raise ManifestError("The only supported scan setting is exclude.")
    patterns = settings.get("exclude", [])
    if not isinstance(patterns, list):
        raise ManifestError("scan.exclude must be an array of glob patterns.")
    return normalize_excludes(patterns)
