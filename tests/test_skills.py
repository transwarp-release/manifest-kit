import json

from tests.support import PROJECT_ROOT, WorkspaceTestCase


class SkillAndDemoTests(WorkspaceTestCase):
    def test_both_skill_scripts_from_an_unrelated_working_directory(self):
        self.put("说明.txt", "portable skill\n")
        output = self.work / "baseline.json"
        create = PROJECT_ROOT / "skills/create-file-manifest/scripts/create_manifest.py"
        verify = PROJECT_ROOT / "skills/verify-file-manifest/scripts/verify_manifest.py"
        result = self.python(create, self.root, "--output", output, cwd=self.work)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.python(verify, self.root, "--manifest", output, cwd=self.work)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "match")

    def test_complete_positive_demo_is_repeatable(self):
        output = self.work / "demo-reports"
        script = PROJECT_ROOT / "scripts/run_demo.py"
        for _ in range(2):
            result = self.python(script, "--output-dir", output, cwd=self.work)
            self.assertEqual(result.returncode, 0, result.stderr)
            baseline = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(baseline["files"]), 4)
            self.assertEqual((output / "manifest.json").read_bytes(), (output / "repeated.json").read_bytes())
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["file_count"], 4)
            self.assertEqual(summary["total_bytes"], 643)
            self.assertEqual(
                {item["extension"]: item["file_count"] for item in summary["extensions"]},
                {".json": 1, ".md": 1, ".txt": 2},
            )
            for name in ("verification.json", "comparison.json"):
                report = json.loads((output / name).read_text(encoding="utf-8"))
                self.assertEqual(report["status"], "match")
                self.assertEqual(report["unchanged_count"], 4)
                self.assertEqual(report["added"], [])
                self.assertEqual(report["removed"], [])
                self.assertEqual(report["changed"], [])
