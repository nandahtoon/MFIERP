"""Pinned public-source verification, archive containment and cache attestation."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import unittest
from unittest.mock import patch
import warnings
from zipfile import BadZipFile, ZipFile, ZipInfo

module = importlib.util.spec_from_file_location(
    "source_fetch", Path(__file__).resolve().parents[1] / "scripts/fetch_mifos_source.py")
source = importlib.util.module_from_spec(module)
module.loader.exec_module(source)


def synthetic_tree(files):
    """Build independent, real Git tree objects for bounded synthetic fixtures."""
    entries = {path: {"path": path, "type": "blob", "mode": "100644",
                      "sha": source.git_hash("blob", data), "size": len(data)} for path, data in files.items()}
    directories = {parent.as_posix() for path in files for parent in PurePosixPath(path).parents
                   if parent.as_posix() != "."}
    for directory in sorted(directories, key=lambda path: -len(path.split("/"))):
        children = [item for path, item in entries.items() if str(PurePosixPath(path).parent) == directory]
        raw = tree_bytes(children)
        entries[directory] = {"path": directory, "type": "tree", "mode": "040000",
                              "sha": source.git_hash("tree", raw)}
    root = tree_bytes([item for path, item in entries.items() if "/" not in path])
    sha = source.git_hash("tree", root)
    return {"repository": source.SOURCE_REPOSITORY, "revision": source.PINNED_REVISION,
            "commit_tree_sha": sha, "sha": sha, "truncated": False, "tree": list(entries.values())}


def tree_bytes(entries):
    ordered = sorted(entries, key=lambda item: (
        PurePosixPath(item["path"]).name + ("/" if item["type"] == "tree" else "")).encode())
    return b"".join(item["mode"].lstrip("0").encode() + b" " + PurePosixPath(item["path"]).name.encode()
                    + b"\0" + bytes.fromhex(item["sha"]) for item in ordered)


def zip_bytes(members, root=None):
    root = root or f"Mifosx-web-app-{source.PINNED_REVISION}"
    output = io.BytesIO()
    with warnings.catch_warnings(), ZipFile(output, "w") as archive:
        warnings.simplefilter("ignore", UserWarning)
        for path, data in members:
            name = f"{root}/{path}"
            member = ZipInfo(name)
            member.filename = name  # Preserve malicious backslashes on Windows.
            archive.writestr(member, data)
    return output.getvalue()


class SourceFetchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.research = Path(self.temporary.name) / ".research"
        self.research.mkdir()
        self.destination = self.research / "selected"
        self.files = {"src/app/a.ts": b"export const example = 1;\n", "AGENTS.md": b"Public source conventions\n",
                      "src/environments/environment.ts": b"export const template = {};\n",
                      "src/assets/translations/en-US.json": b'{"example":"Example"}\n',
                      "src/app/core/error-handler/README.md": b"Error handling documentation\n",
                      "playwright/config/routes.ts": b"export const routes = [];\n",
                      "src/assets/logo.png": b"\x89PNG\0binary"}
        self.tree = synthetic_tree(self.files)
        self.patch_root = patch.object(source, "RESEARCH_ROOT", self.research)
        self.patch_tree = patch.object(source, "PINNED_TREE_SHA", self.tree["sha"])
        self.patch_root.start()
        self.patch_tree.start()
        self.addCleanup(self.patch_root.stop)
        self.addCleanup(self.patch_tree.stop)
        self.revision = source.PINNED_REVISION
        self.archive = zip_bytes(self.files.items())

    def expected(self, scope="app"):
        return source.expected_files(self.tree, self.revision, scope)

    def cache(self, archive=None, scope="app"):
        return source.cache_archive(self.archive if archive is None else archive, self.tree,
                                    self.revision, self.destination, scope)

    def snapshot(self):
        return {path.relative_to(self.destination).as_posix(): path.read_bytes()
                for path in self.destination.rglob("*") if path.is_file()}

    def test_complete_tree_reconstructs_distinct_tree_identity_and_scope(self):
        self.assertNotEqual(self.revision, self.tree["sha"])
        self.assertEqual(set(self.expected()), {"src/app/a.ts"})
        self.assertEqual(set(self.expected("supporting")), set(self.files) - {"src/app/a.ts", "src/assets/logo.png"})
        self.assertEqual(len(self.expected("all")), 6)

    def test_supporting_scope_covers_declared_public_text_only(self):
        for path in ("skills/SKILL.md", "docs/i18n.md", "src/assets/setup/dt_kyc_validation.json",
                     "src/environments/.env.ts", "src/environments/microops-local/env.js"):
            self.assertTrue(source.selected_path(path, "supporting"), path)
        for path in (".env", "config/runtime.json", "package-lock.json", "src/assets/logo.png"):
            self.assertFalse(source.selected_path(path, "all"), path)

    def test_wrong_revision_repository_and_commit_tree_relationship_fail(self):
        for key, value in (("revision", "a" * 40), ("repository", "other/repo"),
                           ("sha", self.revision), ("commit_tree_sha", self.revision)):
            with self.subTest(key=key):
                tree = copy.deepcopy(self.tree)
                tree[key] = value
                with self.assertRaises(ValueError):
                    source.expected_files(tree, self.revision)
        for revision in ("main", "a" * 40, self.revision[:7]):
            with self.assertRaises(ValueError):
                source.expected_files(self.tree, revision)

    def test_truncated_missing_and_filtered_trees_fail(self):
        for value in (True, None, "false", 0):
            tree = copy.deepcopy(self.tree)
            tree["truncated"] = value
            with self.assertRaises(ValueError):
                source.expected_files(tree, self.revision)
        tree = copy.deepcopy(self.tree)
        del tree["truncated"]
        with self.assertRaises(ValueError):
            source.expected_files(tree, self.revision)
        for path in ("src/assets/logo.png", "src/app/a.ts", "src/app"):
            tree = copy.deepcopy(self.tree)
            tree["tree"] = [item for item in tree["tree"] if item["path"] != path]
            with self.assertRaises(ValueError):
                source.expected_files(tree, self.revision)

    def test_tree_tamper_duplicate_and_unsafe_paths_fail(self):
        for mutation in ("hash", "mode", "size", "duplicate", "case", "traversal"):
            with self.subTest(mutation=mutation):
                tree = copy.deepcopy(self.tree)
                item = tree["tree"][0]
                if mutation == "hash":
                    item["sha"] = "a" * 40
                elif mutation == "mode":
                    item["mode"] = "100777"
                elif mutation == "size":
                    item["size"] = True
                elif mutation == "duplicate":
                    tree["tree"].append(copy.deepcopy(item))
                elif mutation == "case":
                    alias = copy.deepcopy(item)
                    alias["path"] = item["path"].upper()
                    tree["tree"].append(alias)
                else:
                    item["path"] = "src/../outside.ts"
                with self.assertRaises(ValueError):
                    source.expected_files(tree, self.revision)

    def test_selected_symlink_is_rejected_even_with_matching_tree(self):
        tree = copy.deepcopy(self.tree)
        tree["tree"][0]["mode"] = "120000"
        with patch.object(source, "validate_tree", return_value={item["path"]: item for item in tree["tree"]}):
            with self.assertRaisesRegex(ValueError, "links"):
                source.expected_files(tree, self.revision)

    def test_verified_cache_has_exact_scope_lock_and_archive_hash(self):
        lock = self.cache(scope="supporting")
        self.assertEqual(lock["verified_text_files"], 5)
        self.assertEqual(lock["excluded_blobs"], 2)
        self.assertEqual(lock["tree_sha"], self.tree["sha"])
        self.assertEqual(lock["archive_sha256"], hashlib.sha256(self.archive).hexdigest())
        self.assertEqual(json.loads((self.destination / ".source-lock.json").read_text()), lock)
        self.assertEqual(set(self.snapshot()) - {".source-lock.json"}, set(self.expected("supporting")))
        self.assertEqual(source.verify_cache(self.destination, self.expected("supporting")), 5)

    def test_partial_tampered_and_extra_cache_bytes_are_not_verified(self):
        self.cache()
        target = self.destination / "src/app/a.ts"
        target.unlink()
        with self.assertRaisesRegex(ValueError, "partial"):
            source.verify_cache(self.destination, self.expected())
        target.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "tampered"):
            source.verify_cache(self.destination, self.expected())
        target.write_bytes(self.files["src/app/a.ts"])
        (self.destination / "unexpected.txt").write_text("extra")
        with self.assertRaisesRegex(ValueError, "unexpected"):
            source.verify_cache(self.destination, self.expected())

    def test_valid_archive_repairs_partial_cache_and_reverifies_lock(self):
        self.cache()
        (self.destination / "src/app/a.ts").unlink()
        self.cache()
        self.assertEqual(source.verify_cache(self.destination, self.expected()), 1)
        self.assertEqual(len(list(self.research.glob(".source-stage-*"))), 0)

    def test_missing_or_tampered_archive_preserves_prior_cache_and_lock(self):
        self.cache()
        before = self.snapshot()
        for members in ([("AGENTS.md", self.files["AGENTS.md"])], [("src/app/a.ts", b"tampered")]):
            with self.assertRaises(ValueError):
                self.cache(zip_bytes(members))
            self.assertEqual(self.snapshot(), before)

    def test_failed_first_fetch_creates_no_attested_cache(self):
        with self.assertRaises(ValueError):
            self.cache(zip_bytes([("src/app/a.ts", b"tampered")]))
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.research.glob(".source-stage-*")), [])

    def test_truncated_archive_preserves_valid_cache_and_lock(self):
        self.cache()
        before = self.snapshot()
        for archive in (b"", self.archive[:40], self.archive[:-22]):
            with self.assertRaises(BadZipFile):
                self.cache(archive)
            self.assertEqual(self.snapshot(), before)

    def test_refresh_cannot_replace_other_scope_or_unrelated_research(self):
        self.cache()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "another scope"):
            self.cache(scope="supporting")
        self.assertEqual(self.snapshot(), before)
        (self.destination / "unrelated.txt").write_text("preserve")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "unrelated"):
            self.cache()
        self.assertEqual(self.snapshot(), before)

    def test_refresh_cannot_replace_different_revision_lock(self):
        self.cache()
        path = self.destination / ".source-lock.json"
        lock = json.loads(path.read_text())
        lock["revision"] = "a" * 40
        path.write_text(json.dumps(lock))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "another repository, revision or scope"):
            self.cache()
        self.assertEqual(self.snapshot(), before)

    def test_unsafe_archive_paths_rejected_even_when_outside_selection(self):
        for path in ("../outside.txt", "src/../../outside.txt", "/absolute.txt", "C:/outside.txt",
                     "src\\outside.txt", "src/./a.ts", "src//a.ts", "src/a.ts:stream", "CON.txt", "src/a.ts."):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.cache(zip_bytes([*self.files.items(), (path, b"bad")]))
        self.assertFalse(self.destination.exists())

    def test_duplicate_and_case_alias_archive_members_rejected(self):
        for path in ("src/app/a.ts", "SRC/APP/A.TS", "src/assets/logo.png"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.cache(zip_bytes([*self.files.items(), (path, b"bad")]))

    def test_wrong_archive_root_and_symlink_rejected(self):
        with self.assertRaises(ValueError):
            self.cache(zip_bytes(self.files.items(), root="Mifosx-web-app-main"))
        data = io.BytesIO()
        with ZipFile(data, "w") as archive:
            member = ZipInfo(f"Mifosx-web-app-{self.revision}/src/app/a.ts")
            member.create_system = 3
            member.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(member, self.files["src/app/a.ts"])
        with self.assertRaisesRegex(ValueError, "links"):
            self.cache(data.getvalue())

    def test_text_and_archive_size_bounds_precede_attestation(self):
        for constant, limit in (("MAX_ARCHIVE_SIZE", 2), ("MAX_TEXT_SIZE", 2), ("MAX_TOTAL_TEXT_SIZE", 2)):
            with self.subTest(constant=constant), patch.object(source, constant, limit):
                with self.assertRaisesRegex(ValueError, "size limit"):
                    self.cache()
        self.assertFalse(self.destination.exists())

    def test_binary_selected_file_is_rejected(self):
        expected = {"src/app/a.ts": source.git_hash("blob", b"a\0b")}
        with self.assertRaisesRegex(ValueError, "binary"):
            source.extract_verified(zip_bytes([("src/app/a.ts", b"a\0b")]), expected, self.destination)
        self.assertFalse(self.destination.exists())

    def test_cache_destination_must_be_inside_repository_research(self):
        for path in (self.research, self.research / "folder/..", self.research / "../outside",
                     self.research.parent / "outside/.research/cache"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                source.checked_research_path(path)

    def test_failed_promotion_rolls_back_prior_cache_and_lock(self):
        self.cache()
        before = self.snapshot()
        original = os.replace

        def fail_promotion(start, end):
            if Path(start).name == "cache" and Path(end) == self.destination:
                raise OSError("synthetic promotion failure")
            return original(start, end)

        with patch.object(source.os, "replace", side_effect=fail_promotion):
            with self.assertRaisesRegex(OSError, "promotion"):
                self.cache()
        self.assertEqual(self.snapshot(), before)

    def test_fetch_saves_full_tree_after_commit_relationship_verification(self):
        commit = {"sha": self.revision, "tree": {"sha": self.tree["sha"]}}
        raw = {key: value for key, value in self.tree.items()
               if key not in {"repository", "revision", "commit_tree_sha"}}
        tree_path = self.research / "tree.json"
        with patch.object(source, "download", side_effect=[json.dumps(commit).encode(), json.dumps(raw).encode()]) as fetch:
            result = source.fetch_repository_tree(self.revision, tree_path)
        self.assertEqual(len(result["tree"]), len(self.tree["tree"]))
        self.assertEqual(json.loads(tree_path.read_text())["commit_tree_sha"], self.tree["sha"])
        self.assertEqual(fetch.call_args_list[1].args[0],
                         f"https://api.github.com/repos/{source.SOURCE_REPOSITORY}/git/trees/{self.tree['sha']}?recursive=1")

    def test_fetch_wrong_commit_tree_or_truncated_tree_preserves_old_evidence(self):
        tree_path = self.research / "tree.json"
        tree_path.write_text("prior complete evidence")
        for commit in ({"sha": "a" * 40, "tree": {"sha": self.tree["sha"]}},
                       {"sha": self.revision, "tree": {"sha": self.revision}}):
            with patch.object(source, "download", return_value=json.dumps(commit).encode()):
                with self.assertRaises(ValueError):
                    source.fetch_repository_tree(self.revision, tree_path)
            self.assertEqual(tree_path.read_text(), "prior complete evidence")
        raw = copy.deepcopy(self.tree)
        raw["truncated"] = True
        commit = {"sha": self.revision, "tree": {"sha": self.tree["sha"]}}
        with patch.object(source, "download", side_effect=[json.dumps(commit).encode(), json.dumps(raw).encode()]):
            with self.assertRaises(ValueError):
                source.fetch_repository_tree(self.revision, tree_path)
        self.assertEqual(tree_path.read_text(), "prior complete evidence")

    def test_download_bounds_response_without_reading_credentials(self):
        with patch.object(source.urllib.request, "urlopen", return_value=io.BytesIO(b"12345")):
            with self.assertRaisesRegex(ValueError, "size limit"):
                source.download("https://api.github.com/public-synthetic", 4)


if __name__ == "__main__":
    unittest.main()
