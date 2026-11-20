import json

from manifestkit.config import load_excludes
from manifestkit.core import FileEntry, Manifest, ManifestError, scan_tree
from manifestkit.reports import manifest_markdown
from tests.support import WorkspaceTestCase


class CommandTests(WorkspaceTestCase):
    def baseline(self):
        path = self.work / "baseline.json"
        result = self.cli("scan", self.root, "--output", path)
        self.assertEqual(result.returncode, 0, result.stderr)
        return path

    def test_scan_emits_json_to_stdout(self):
        self.put("说明.txt", "中文\n")
        result = self.cli("scan", self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["files"][0]["path"], "说明.txt")

    def test_scan_writes_json_and_markdown_with_parent_directories(self):
        self.put("a.txt")
        output = self.work / "reports" / "manifest.json"
        markdown = output.with_suffix(".md")
        result = self.cli("scan", self.root, "--output", output, "--markdown", markdown)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(output.read_text(encoding="utf-8"))["files"]), 1)
        self.assertIn("a\\.txt", markdown.read_text(encoding="utf-8"))

    def test_toml_and_cli_exclusions_are_merged(self):
        for relative in ("a.tmp", "b.bak", "keep.txt"):
            self.put(relative)
        config = self.work / "scan.toml"
        config.write_text('[scan]\nexclude = ["*.tmp"]\n', encoding="utf-8")
        result = self.cli("scan", self.root, "--config", config, "--exclude", "*.bak")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([item["path"] for item in json.loads(result.stdout)["files"]], ["keep.txt"])

    def test_verify_success(self):
        self.put("a.txt")
        result = self.cli("verify", self.root, "--manifest", self.baseline())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "match")

    def test_verify_uses_saved_exclusions(self):
        temporary = self.put("working.tmp", "first")
        self.put("a.txt")
        baseline = self.work / "baseline.json"
        result = self.cli("scan", self.root, "--exclude", "*.tmp", "--output", baseline)
        self.assertEqual(result.returncode, 0, result.stderr)
        temporary.write_text("second", encoding="utf-8")
        result = self.cli("verify", self.root, "--manifest", baseline)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_verify_reports_difference_with_exit_code_one(self):
        path = self.put("a.txt", "first")
        baseline = self.baseline()
        path.write_text("second", encoding="utf-8")
        result = self.cli("verify", self.root, "--manifest", baseline)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "different")

    def test_diff_compares_saved_manifests(self):
        self.put("a.txt")
        baseline = self.baseline()
        result = self.cli("diff", baseline, baseline)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["unchanged_count"], 1)

    def test_existing_output_requires_explicit_force(self):
        baseline = self.baseline()
        original = baseline.read_bytes()
        result = self.cli("scan", self.root, "--output", baseline)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(baseline.read_bytes(), original)
        self.put("a.txt")
        result = self.cli("scan", self.root, "--output", baseline, "--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(baseline.read_text(encoding="utf-8"))["files"]), 1)

    def test_output_cannot_overwrite_a_scanned_file_even_with_force(self):
        source = self.put("a.txt", "original")
        result = self.cli("scan", self.root, "--output", source, "--force")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(source.read_text(encoding="utf-8"), "original")

    def test_diff_output_cannot_replace_input_manifest(self):
        baseline = self.baseline()
        before = baseline.read_bytes()
        result = self.cli("diff", baseline, baseline, "--output", baseline, "--force")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(baseline.read_bytes(), before)

    def test_output_paths_must_be_distinct(self):
        output = self.work / "out.json"
        result = self.cli("scan", self.root, "--output", output, "--markdown", output)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(output.exists())

    def test_missing_input_has_clear_error_and_exit_code_two(self):
        result = self.cli("scan", self.work / "does-not-exist")
        self.assertEqual(result.returncode, 2)
        self.assertIn("manifest-kit:", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_version(self):
        result = self.cli("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual("manifest-kit 1.1.0", result.stdout.strip())


class ConfigurationAndReportTests(WorkspaceTestCase):
    def test_optional_config_has_no_additional_rules(self):
        self.assertEqual(load_excludes(None), ())

    def test_empty_scan_table(self):
        path = self.work / "scan.toml"
        path.write_text("[scan]\n", encoding="utf-8")
        self.assertEqual(load_excludes(path), ())

    def test_config_is_data_and_requires_string_patterns(self):
        path = self.work / "scan.toml"
        path.write_text("[scan]\nexclude = [3]\n", encoding="utf-8")
        with self.assertRaises(ManifestError):
            load_excludes(path)

    def test_markdown_escapes_filename_punctuation_and_html(self):
        manifest = Manifest((FileEntry("a[1]|notes<draft>.md", 0, "0" * 64),), ())
        output = manifest_markdown(manifest)
        self.assertIn("a\\[1\\]\\|notes&lt;draft&gt;\\.md", output)
        self.assertNotIn("<draft>", output)

    def test_markdown_contains_counts_and_complete_hash(self):
        self.put("a.txt", "abc")
        manifest = scan_tree(self.root)
        output = manifest_markdown(manifest)
        self.assertIn("Files: 1", output)
        self.assertIn("Total bytes: 3", output)
        self.assertIn(manifest.files[0].sha256, output)
