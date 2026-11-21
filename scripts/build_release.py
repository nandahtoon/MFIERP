"""Build a reproducible addon archive without local secrets or compiled files."""
import ast
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "addons" / "mfierp"
manifest = ast.literal_eval((ADDON / "__manifest__.py").read_text(encoding="utf-8"))
destination = ROOT / "dist" / f"mfierp-{manifest['version']}.zip"
destination.parent.mkdir(exist_ok=True)
with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
    for path in sorted(ADDON.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        name = "mfierp/" + path.relative_to(ADDON).as_posix()
        info = ZipInfo(name, date_time=(2026, 11, 18, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        archive.writestr(info, path.read_bytes())
print(destination)
