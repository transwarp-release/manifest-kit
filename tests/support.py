"""Keep every test-generated file inside this repository's ignored .local tree."""

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class WorkspaceTestCase(unittest.TestCase):
    def setUp(self):
        temporary_root = PROJECT_ROOT / ".local" / "test-tmp"
        temporary_root.mkdir(parents=True, exist_ok=True)
        workspace = tempfile.TemporaryDirectory(prefix="case-", dir=temporary_root)
        self.addCleanup(workspace.cleanup)
        self.work = Path(workspace.name)
        self.root = self.work / "input"
        self.root.mkdir()

    def put(self, relative, content="sample\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
        return path

    def python(self, *arguments, cwd=PROJECT_ROOT):
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONUTF8"] = "1"
        child_temp = self.work / "child-tmp"
        child_temp.mkdir(exist_ok=True)
        environment["TEMP"] = str(child_temp)
        environment["TMP"] = str(child_temp)
        return subprocess.run(
            [sys.executable, "-B", *map(str, arguments)], cwd=cwd, env=environment,
            capture_output=True, text=True, encoding="utf-8", timeout=30,
            check=False,
        )

    def cli(self, *arguments):
        return self.python("-m", "manifestkit", *arguments)
