import json

from manifestkit.core import scan_tree
from manifestkit.summary import summarize_manifest
from tests.support import WorkspaceTestCase


class SummaryTests(WorkspaceTestCase):
    def test_casefolded_extensions_sizes_and_last_suffix(self):
        for name, content in {
            "a.txt": "abc", "nested/b.TXT": "de", "readme.md": "hello",
            "archive.tar.gz": b"\0" * 4, "LICENSE": "x", ".hidden": "abc",
        }.items():
            self.put(name, content)
        result = summarize_manifest(scan_tree(self.root))
        self.assertEqual(result["report_type"], "extension_summary")
        self.assertEqual(result["file_count"], 6)
        self.assertEqual(result["total_bytes"], 18)
        self.assertEqual(result["extensions"], [
            {"extension": "(no extension)", "file_count": 2, "total_bytes": 4},
            {"extension": ".gz", "file_count": 1, "total_bytes": 4},
            {"extension": ".md", "file_count": 1, "total_bytes": 5},
            {"extension": ".txt", "file_count": 2, "total_bytes": 5},
        ])

    def test_empty_manifest_has_zero_totals(self):
        result = summarize_manifest(scan_tree(self.root))
        self.assertEqual(result["file_count"], 0)
        self.assertEqual(result["total_bytes"], 0)
        self.assertEqual(result["extensions"], [])

    def test_excluded_files_are_not_in_the_summary(self):
        self.put("keep.md", "hello")
        self.put("working.tmp", "ignored")
        result = summarize_manifest(scan_tree(self.root, ["*.tmp"]))
        self.assertEqual(result["file_count"], 1)
        self.assertEqual(result["total_bytes"], 5)

    def test_zero_byte_file_still_counts(self):
        self.put("empty.txt", b"")
        result = summarize_manifest(scan_tree(self.root))
        self.assertEqual(result["extensions"], [
            {"extension": ".txt", "file_count": 1, "total_bytes": 0},
        ])

    def test_totals_equal_the_sum_of_groups(self):
        self.put("a.txt", "hello")
        self.put("说明/说明.MD", "中文\n")
        result = summarize_manifest(scan_tree(self.root))
        self.assertEqual(result["file_count"], sum(group["file_count"] for group in result["extensions"]))
        self.assertEqual(result["total_bytes"], sum(group["total_bytes"] for group in result["extensions"]))


class SummaryCommandTests(WorkspaceTestCase):
    def baseline(self):
        output = self.work / "manifest.json"
        result = self.cli("scan", self.root, "--output", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        return output

    def test_summary_reads_saved_manifest_without_original_files(self):
        source = self.put("说明.TXT", "abc")
        baseline = self.baseline()
        source.unlink()
        result = self.cli("summary", baseline)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["extensions"], [
            {"extension": ".txt", "file_count": 1, "total_bytes": 3},
        ])

    def test_summary_writes_json_and_markdown(self):
        self.put("a.md", "hello")
        baseline = self.baseline()
        output = self.work / "reports" / "summary.json"
        markdown = output.with_suffix(".md")
        result = self.cli("summary", baseline, "--output", output, "--markdown", markdown)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["total_bytes"], 5)
        self.assertIn("# File extension summary", markdown.read_text(encoding="utf-8"))

    def test_summary_is_repeatable(self):
        self.put("a.txt")
        baseline = self.baseline()
        first = self.cli("summary", baseline)
        second = self.cli("summary", baseline)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)

    def test_summary_cannot_overwrite_its_input(self):
        self.put("a.txt")
        baseline = self.baseline()
        before = baseline.read_bytes()
        result = self.cli("summary", baseline, "--output", baseline, "--force")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(baseline.read_bytes(), before)
