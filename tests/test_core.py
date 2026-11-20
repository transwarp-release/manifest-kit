import hashlib
import json

from manifestkit.core import (
    CHUNK_SIZE, DEFAULT_EXCLUDES, ManifestError, compare_manifests,
    load_manifest, scan_tree,
)
from tests.support import WorkspaceTestCase


class ScanTests(WorkspaceTestCase):
    def test_known_sha256_and_size(self):
        self.put("hello.txt", "hello\n")
        entry, = scan_tree(self.root).files
        self.assertEqual(entry.path, "hello.txt")
        self.assertEqual(entry.size, 6)
        self.assertEqual(entry.sha256, "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03")

    def test_nested_unicode_paths_are_sorted(self):
        for name in ("说明/说明.txt", "z.txt", "a/sub.txt"):
            self.put(name)
        paths = [entry.path for entry in scan_tree(self.root).files]
        self.assertEqual(paths, ["a/sub.txt", "z.txt", "说明/说明.txt"])

    def test_empty_directory_and_empty_file(self):
        self.assertEqual(scan_tree(self.root).files, ())
        self.put("empty.txt", b"")
        entry, = scan_tree(self.root).files
        self.assertEqual(entry.size, 0)
        self.assertEqual(entry.sha256, hashlib.sha256(b"").hexdigest())

    def test_binary_file_across_multiple_chunks(self):
        content = b"\x00\x01\xff" * (CHUNK_SIZE + 7)
        self.put("large.dat", content)
        entry, = scan_tree(self.root).files
        self.assertEqual(entry.size, len(content))
        self.assertEqual(entry.sha256, hashlib.sha256(content).hexdigest())

    def test_default_metadata_and_output_directories_are_excluded(self):
        for relative in (".git/config", ".local/report.json", "a/__pycache__/item.pyc", "node_modules/a.txt"):
            self.put(relative)
        self.put("keep.txt")
        self.assertEqual([entry.path for entry in scan_tree(self.root).files], ["keep.txt"])

    def test_custom_globs_and_nested_directory_exclusion(self):
        for relative in ("one.tmp", "nested/two.tmp", "nested/cache/a.txt", "keep.txt", "UPPER.TMP"):
            self.put(relative)
        manifest = scan_tree(self.root, ["*.tmp", "cache"])
        self.assertEqual([entry.path for entry in manifest.files], ["UPPER.TMP", "keep.txt"])

    def test_path_glob(self):
        self.put("drafts/a.txt")
        self.put("nested/drafts/b.txt")
        manifest = scan_tree(self.root, ["drafts/*"])
        self.assertEqual([entry.path for entry in manifest.files], ["nested/drafts/b.txt"])

    def test_manifest_is_independent_of_root_location(self):
        self.put("hello.txt", "same bytes\n")
        other = self.work / "other"
        other.mkdir()
        (other / "hello.txt").write_bytes((self.root / "hello.txt").read_bytes())
        self.assertEqual(scan_tree(self.root).to_dict(), scan_tree(other).to_dict())
        encoded = json.dumps(scan_tree(self.root).to_dict())
        self.assertNotIn(str(self.root), encoded)
        self.assertNotIn("same bytes", encoded)

    def test_repeated_scans_and_rule_order_are_deterministic(self):
        self.put("a.txt")
        self.assertEqual(
            scan_tree(self.root, ["*.tmp", "cache"]).to_dict(),
            scan_tree(self.root, ["cache", "*.tmp", "cache"]).to_dict(),
        )

    def test_links_to_files_and_directories_are_skipped(self):
        outside = self.work / "outside"
        outside.mkdir()
        target = outside / "outside.txt"
        target.write_text("outside\n", encoding="utf-8")
        try:
            (self.root / "file-link").symlink_to(target)
            (self.root / "dir-link").symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Symbolic links unavailable: {error}")
        self.put("inside.txt")
        self.assertEqual([entry.path for entry in scan_tree(self.root).files], ["inside.txt"])


class LoadAndCompareTests(WorkspaceTestCase):
    def save(self, raw):
        path = self.work / "manifest.json"
        path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        return path

    def test_round_trip(self):
        self.put("说明.txt", "测试\n")
        manifest = scan_tree(self.root, ["*.tmp"])
        self.assertEqual(load_manifest(self.save(manifest.to_dict())), manifest)

    def test_unmodified_tree_matches(self):
        self.put("a.txt")
        result = compare_manifests(scan_tree(self.root), scan_tree(self.root))
        self.assertEqual(result["status"], "match")
        self.assertEqual(result["unchanged_count"], 1)

    def test_added_removed_and_same_size_content_changes(self):
        changed = self.put("changed.txt", "AAA")
        removed = self.put("removed.txt")
        self.put("same.txt")
        baseline = scan_tree(self.root)
        changed.write_text("BBB", encoding="utf-8")
        removed.unlink()
        self.put("added.txt")
        result = compare_manifests(baseline, scan_tree(self.root))
        self.assertEqual(result["status"], "different")
        self.assertEqual(result["added"], ["added.txt"])
        self.assertEqual(result["removed"], ["removed.txt"])
        self.assertEqual([item["path"] for item in result["changed"]], ["changed.txt"])
        self.assertEqual(result["unchanged_count"], 1)

    def test_changed_exclusion_policy_is_visible(self):
        result = compare_manifests(scan_tree(self.root), scan_tree(self.root, ["*.tmp"]))
        self.assertEqual(result["status"], "different")
        self.assertTrue(result["exclusions_changed"])

    def test_manifest_cannot_contain_traversal_or_absolute_paths(self):
        for invalid in ("../outside.txt", "/root.txt", "C:/data.txt", "a\\b.txt", "a/../b.txt"):
            with self.subTest(invalid=invalid):
                raw = scan_tree(self.root).to_dict()
                raw["files"] = [{"path": invalid, "size": 0, "sha256": "0" * 64}]
                with self.assertRaises(ManifestError):
                    load_manifest(self.save(raw))

    def test_duplicate_manifest_paths_are_rejected(self):
        self.put("a.txt")
        raw = scan_tree(self.root).to_dict()
        raw["files"].append(raw["files"][0].copy())
        with self.assertRaises(ManifestError):
            load_manifest(self.save(raw))

    def test_invalid_digest_or_byte_size_is_rejected(self):
        self.put("a.txt")
        for key, value in (("sha256", "not-a-digest"), ("size", -1), ("size", True)):
            with self.subTest(key=key, value=value):
                raw = scan_tree(self.root).to_dict()
                raw["files"][0][key] = value
                with self.assertRaises(ManifestError):
                    load_manifest(self.save(raw))

    def test_default_exclusions_are_preserved_on_load(self):
        raw = scan_tree(self.root).to_dict()
        raw["exclude"] = []
        with self.assertRaises(ManifestError):
            load_manifest(self.save(raw))
        self.assertTrue(set(DEFAULT_EXCLUDES).issubset(scan_tree(self.root).exclude))
