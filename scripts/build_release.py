"""Build the HACS integration archive from a reviewed checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ALLOWED = {".py", ".json", ".yaml", ".svg", ".png"}

def build(root, output, tag=None):
    component = root / "custom_components" / "aula"
    manifest = json.loads((component / "manifest.json").read_text(encoding="utf-8"))
    if manifest["domain"] != "aula":
        raise ValueError("The existing aula domain must be preserved")
    if tag and tag.removeprefix("v") != manifest["version"]:
        raise ValueError("Release tag does not match the committed manifest version")
    output.mkdir(parents=True, exist_ok=True)
    archive = output / "aula.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(component.rglob("*")):
            if (path.is_file() and path.suffix in ALLOWED
                and not any(part.startswith(".") or part == "__pycache__"
                            for part in path.relative_to(component).parts)):
                zipped.write(path, path.relative_to(component).as_posix())
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / "SHA256SUMS").write_text(checksum + "  aula.zip\n", encoding="utf-8")
    return {"version": manifest["version"], "sha256": checksum, "archive": str(archive)}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag")
    parser.add_argument("--output", type=Path, default=Path("dist"))
    arguments = parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[1], arguments.output, arguments.tag)))
