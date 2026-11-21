"""Cache selected text from the pinned public Mifos source; never execute its code.

``--fetch-tree`` resolves the pinned commit through GitHub's Git data API and saves
its complete recursive tree under .research. Commit and tree are distinct objects;
every subtree hash is reconstructed before selected archive blobs are trusted.

Scopes: app = src/app TS/HTML/JSON/SCSS; supporting = public source governance,
environment templates, KYC setup, translation JSONs, i18n documentation, Playwright
config TS and error-handler README. Other blobs (including binary assets,
lockfiles and deployment material) are indexed but never extracted. No local
environment, credentials or runtime config is read. A failed refresh preserves
the old cache and lock. These are reference caches, not application installs.
"""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import stat
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

SOURCE_REPOSITORY = "nandahtoon/Mifosx-web-app"
PINNED_REVISION = "34c7f278861ef25052f2e00d106d8527f5d270d3"
# Independently confirmed through the GitHub connector's Git commit API.
PINNED_TREE_SHA = "559162e9aeb0903a7909752ec8f1e513827f105f"
RESEARCH_ROOT = Path(__file__).resolve().parents[1] / ".research"
APP_SUFFIXES = {".ts", ".html", ".json", ".scss"}
SUPPORTING_FILES = {
    "AGENTS.md", "skills/SKILL.md", "docs/i18n.md",
    "src/assets/setup/dt_kyc_validation.json", "src/app/core/error-handler/README.md",
}
MAX_ARCHIVE_SIZE = 100 * 1024 * 1024
MAX_TEXT_SIZE = 4 * 1024 * 1024
MAX_TOTAL_TEXT_SIZE = 200 * 1024 * 1024
SHA = re.compile(r"[a-f0-9]{40}\Z")


def git_hash(kind, data):
    return hashlib.sha1(kind.encode() + b" " + str(len(data)).encode() + b"\0" + data).hexdigest()


def safe_parts(path):
    """Reject archive and Windows filesystem aliases before normalization."""
    if not isinstance(path, str) or not path or any(char in path for char in '\\:*?"<>|'):
        raise ValueError("Unsafe source path.")
    parts = path.split("/")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    for part in parts:
        if (part in {"", ".", ".."} or part.endswith((" ", "."))
                or any(ord(char) < 32 for char in part)
                or part.split(".")[0].upper() in reserved):
            raise ValueError("Source traversal or filesystem alias is unsupported.")
    return tuple(parts)


def validate_revision(revision):
    if revision != PINNED_REVISION:
        raise ValueError("Use the exact reviewed pinned commit; repinning requires source review.")


def validate_tree(tree, revision):
    """Validate a complete recursive tree, not a filtered path listing."""
    validate_revision(revision)
    if (tree.get("repository") != SOURCE_REPOSITORY or tree.get("revision") != revision
            or tree.get("commit_tree_sha") != PINNED_TREE_SHA or tree.get("sha") != PINNED_TREE_SHA):
        raise ValueError("The complete tree does not match the reviewed commit/tree relationship.")
    if tree.get("truncated") is not False or not isinstance(tree.get("tree"), list):
        raise ValueError("A complete non-truncated recursive source tree is required.")
    entries = {}
    aliases = set()
    children = {"": []}
    modes = {"blob": {"100644", "100755", "120000"}, "tree": {"040000"}, "commit": {"160000"}}
    for item in tree["tree"]:
        path = item.get("path")
        parts = safe_parts(path)
        if path.casefold() in aliases:
            raise ValueError("Duplicate or case-aliased source-tree path.")
        aliases.add(path.casefold())
        if (item.get("mode") not in modes.get(item.get("type"), set())
                or not isinstance(item.get("sha"), str) or not SHA.fullmatch(item["sha"])):
            raise ValueError("Invalid Git tree object identity or mode.")
        if item["type"] == "blob" and (type(item.get("size")) is not int or item["size"] < 0):
            raise ValueError("Invalid Git blob size.")
        entries[path] = item
        parent = "/".join(parts[:-1])
        children.setdefault(parent, []).append(item)
        if item["type"] == "tree":
            children.setdefault(path, [])
    for path in children:
        if path and (path not in entries or entries[path]["type"] != "tree"):
            raise ValueError("Incomplete source tree: a parent directory is absent.")
        ordered = sorted(children[path], key=lambda item: (
            PurePosixPath(item["path"]).name + ("/" if item["type"] == "tree" else "")
        ).encode("utf-8"))
        raw = b"".join(
            item["mode"].lstrip("0").encode() + b" " + PurePosixPath(item["path"]).name.encode("utf-8")
            + b"\0" + bytes.fromhex(item["sha"]) for item in ordered
        )
        expected = entries[path]["sha"] if path else tree["sha"]
        if git_hash("tree", raw) != expected:
            raise ValueError("Incomplete or tampered recursive Git tree.")
    return entries


def selected_path(path, scope):
    app = path.startswith("src/app/") and PurePosixPath(path).suffix in APP_SUFFIXES
    supporting = (path in SUPPORTING_FILES
                  or (path.startswith("src/environments/") and PurePosixPath(path).suffix in {".ts", ".js"})
                  or (path.startswith("src/assets/translations/") and PurePosixPath(path).suffix == ".json")
                  or (path.startswith("playwright/config/") and PurePosixPath(path).suffix == ".ts"))
    return (scope in {"app", "all"} and app) or (scope in {"supporting", "all"} and supporting)


def expected_files(tree, revision, scope="app"):
    if scope not in {"app", "supporting", "all"}:
        raise ValueError("Unknown source scope.")
    entries = validate_tree(tree, revision)
    result = {}
    for path, item in entries.items():
        if item["type"] == "blob" and selected_path(path, scope):
            if item["mode"] not in {"100644", "100755"}:
                raise ValueError("Selected source links are not supported.")
            result[path] = item["sha"]
    if not result:
        raise ValueError("No reviewed source text files were found.")
    return result


def checked_research_path(path):
    path = Path(path).absolute()
    root = RESEARCH_ROOT.absolute()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Source evidence must be inside this repository's ignored .research directory.")
    for candidate in (path, *path.parents):
        if candidate.is_symlink() or (hasattr(candidate, "is_junction") and candidate.is_junction()):
            raise ValueError("Source cache links are not supported.")
        if candidate == root.parent:
            break
    if path.resolve() == root.resolve() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Source cache escaped the ignored research directory.")
    return path


def download(url, limit):
    # Fixed public URLs only; this helper never reads tokens or deployment settings.
    request = urllib.request.Request(url, headers={"User-Agent": "MFIERP-source-verifier",
                                                 "Accept": "application/vnd.github+json"})
    chunks = []
    size = 0
    with urllib.request.urlopen(request, timeout=60) as response:
        while chunk := response.read(min(1024 * 1024, limit + 1 - size)):
            size += len(chunk)
            if size > limit:
                raise ValueError("Public source download exceeds the research size limit.")
            chunks.append(chunk)
    return b"".join(chunks)


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".source-json-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def fetch_repository_tree(revision, path):
    validate_revision(revision)
    path = checked_research_path(path)
    api = f"https://api.github.com/repos/{SOURCE_REPOSITORY}"
    commit_url = f"{api}/git/commits/{revision}"
    commit = json.loads(download(commit_url, 1024 * 1024))
    if commit.get("sha") != revision or commit.get("tree", {}).get("sha") != PINNED_TREE_SHA:
        raise ValueError("GitHub commit/tree relationship differs from the reviewed pin.")
    tree_url = f"{api}/git/trees/{PINNED_TREE_SHA}?recursive=1"
    tree = json.loads(download(tree_url, 8 * 1024 * 1024))
    tree.update(repository=SOURCE_REPOSITORY, revision=revision, commit_tree_sha=commit["tree"]["sha"],
                commit_api_url=commit_url, tree_api_url=tree_url)
    validate_tree(tree, revision)
    atomic_json(path, tree)
    return tree


def extract_verified(archive_bytes, expected, destination, revision=PINNED_REVISION):
    """Verify the entire archive selection before writing any selected bytes."""
    validate_revision(revision)
    if len(archive_bytes) > MAX_ARCHIVE_SIZE:
        raise ValueError("Compressed source archive exceeds the research size limit.")
    root_name = f"Mifosx-web-app-{revision}"
    contents = {}
    names = set()
    total_size = 0
    with ZipFile(io.BytesIO(archive_bytes)) as archive:
        for member in archive.infolist():
            # ZipInfo.filename normalizes backslashes on Windows and truncates NUL;
            # validate orig_filename so dangerous input cannot disappear first.
            original = member.orig_filename
            path = original[:-1] if original.endswith("/") else original
            parts = safe_parts(path)
            if parts[0] != root_name or (len(parts) == 1 and not member.is_dir()):
                raise ValueError("Archive root does not match the reviewed commit.")
            if path.casefold() in names:
                raise ValueError("Duplicate or case-aliased archive member.")
            names.add(path.casefold())
            if stat.S_ISLNK(member.external_attr >> 16) or member.flag_bits & 1:
                raise ValueError("Archive links and encrypted files are unsupported.")
            source_path = "/".join(parts[1:])
            if member.is_dir() or source_path not in expected:
                continue
            total_size += member.file_size
            if member.file_size > MAX_TEXT_SIZE or total_size > MAX_TOTAL_TEXT_SIZE:
                raise ValueError("Source archive exceeds the research text size limit.")
            data = archive.read(member)
            if git_hash("blob", data) != expected[source_path]:
                raise ValueError("Archive file does not match the reviewed Git blob.")
            data.decode("utf-8")
            if b"\0" in data:
                raise ValueError("Selected source text contains binary data.")
            contents[source_path] = data
    if contents.keys() != expected.keys():
        raise ValueError("The archive is missing reviewed source files.")
    destination = Path(destination).resolve()
    for source_path, data in contents.items():
        target = destination / source_path
        if not target.resolve().is_relative_to(destination):
            raise ValueError("Archive target escaped the research directory.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return len(contents)


def verify_cache(destination, expected):
    actual = set()
    for path in Path(destination).rglob("*"):
        if path.is_symlink():
            raise ValueError("Source cache contains a link.")
        if path.is_file():
            relative = path.relative_to(destination).as_posix()
            if relative == ".source-lock.json":
                continue
            if relative not in expected or git_hash("blob", path.read_bytes()) != expected[relative]:
                raise ValueError("Source cache contains an unexpected or tampered file.")
            actual.add(relative)
    if actual != expected.keys():
        raise ValueError("Source cache is partial.")
    return len(actual)


def validate_existing_cache(destination, expected, revision, scope):
    """Do not replace another source scope or unrelated research material."""
    if not destination.exists():
        return
    if not destination.is_dir():
        raise ValueError("Source cache destination is not a directory.")
    for path in destination.rglob("*"):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ValueError("Existing source cache contains a link.")
        if path.is_file() and path.relative_to(destination).as_posix() not in {*expected, ".source-lock.json"}:
            raise ValueError("Existing destination contains another scope or unrelated research files.")
    lock_path = destination / ".source-lock.json"
    if lock_path.exists():
        previous = json.loads(lock_path.read_text(encoding="utf-8"))
        if (previous.get("repository") != SOURCE_REPOSITORY or previous.get("revision") != revision
                or previous.get("scope", scope) != scope):
            raise ValueError("Existing source lock belongs to another repository, revision or scope.")


def cache_archive(archive_bytes, tree, revision, destination, scope="app"):
    expected = expected_files(tree, revision, scope)
    destination = checked_research_path(destination)
    validate_existing_cache(destination, expected, revision, scope)
    destination.parent.mkdir(parents=True, exist_ok=True)
    blobs = [item for item in tree["tree"] if item["type"] == "blob"]
    lock = {"repository": SOURCE_REPOSITORY, "revision": revision, "tree_sha": tree["sha"],
            "tree_truncated": False, "repository_entries": len(tree["tree"]), "repository_blobs": len(blobs),
            "scope": scope, "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
            "verified_text_files": len(expected), "excluded_blobs": len(blobs) - len(expected),
            "selection": "selected_path() in scripts/fetch_mifos_source.py; binary and unselected blobs excluded"}
    with tempfile.TemporaryDirectory(prefix=".source-stage-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "cache"
        stage.mkdir()
        extract_verified(archive_bytes, expected, stage, revision)
        verify_cache(stage, expected)
        atomic_json(stage / ".source-lock.json", lock)
        backup = Path(temporary) / "previous"
        if destination.exists():
            os.replace(destination, backup)
        try:
            os.replace(stage, destination)
        except OSError:
            if backup.exists():
                os.replace(backup, destination)
            raise
        # Remove only the newly generated backup, after checking its absolute path.
        if backup.exists():
            checked_research_path(backup)
            shutil.rmtree(backup)
    return lock


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path, help="complete Git tree evidence JSON inside .research")
    parser.add_argument("destination", type=Path, help="separate ignored source cache")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--scope", choices=("app", "supporting", "all"), default="app")
    parser.add_argument("--fetch-tree", action="store_true", help="fetch and verify complete public Git tree")
    args = parser.parse_args(argv)
    try:
        validate_revision(args.revision)
        tree_path = checked_research_path(args.tree)
        destination = checked_research_path(args.destination)
        if tree_path.is_relative_to(destination):
            raise ValueError("The complete tree evidence must be outside the replaceable source cache.")
        tree = (fetch_repository_tree(args.revision, tree_path) if args.fetch_tree
                else json.loads(tree_path.read_text(encoding="utf-8")))
        expected_files(tree, args.revision, args.scope)
        archive = download(f"https://codeload.github.com/{SOURCE_REPOSITORY}/zip/{args.revision}", MAX_ARCHIVE_SIZE)
        lock = cache_archive(archive, tree, args.revision, args.destination, args.scope)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(lock), flush=True)


if __name__ == "__main__":
    main()
