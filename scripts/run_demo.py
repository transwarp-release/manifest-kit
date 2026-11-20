"""Run the complete successful scan / verify / diff example locally."""

from pathlib import Path
import argparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from manifestkit.cli import main


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / ".local" / "demo")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    source = PROJECT_ROOT / "examples" / "demo"
    config = PROJECT_ROOT / "examples" / "scan.toml"
    baseline = output / "manifest.json"
    repeated = output / "repeated.json"
    commands = [
        ["scan", str(source), "--config", str(config), "--output", str(baseline),
         "--markdown", str(output / "manifest.md"), "--force"],
        ["verify", str(source), "--manifest", str(baseline),
         "--output", str(output / "verification.json"),
         "--markdown", str(output / "verification.md"), "--force"],
        ["scan", str(source), "--config", str(config), "--output", str(repeated), "--force"],
        ["diff", str(baseline), str(repeated), "--output", str(output / "comparison.json"),
         "--markdown", str(output / "comparison.md"), "--force"],
        ["summary", str(baseline), "--output", str(output / "summary.json"),
         "--markdown", str(output / "summary.md"), "--force"],
    ]
    for command in commands:
        code = main(command)
        if code:
            return code
    print("Demo completed: scan, verify, diff and summary all returned 0.")
    print(f"Reports: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
