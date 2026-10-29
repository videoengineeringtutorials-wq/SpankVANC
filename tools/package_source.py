"""Create a transfer bundle without workstation state, credentials or SDK files."""
import argparse
import hashlib
from pathlib import Path
import zipfile
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from spankvanc import __version__


ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, default=ROOT / f"releases/SpankVANC-{__version__}-source.zip")
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
files = [ROOT / path for path in ("README.md", "AGENTS.md", "LICENSE", "pyproject.toml", ".gitignore", "CHANGELOG.md", "THIRD_PARTY_NOTICES.md", "CONTRIBUTING.md", "SECURITY.md")]
for directory in ("spankvanc", "native", "firmware", "tests", "docs", "examples", "tools", "windows", "licensing", ".github"):
    files.extend(path for path in (ROOT / directory).rglob("*")
                 if path.is_file() and "__pycache__" not in path.parts and path.suffix not in (".pyc", ".exe", ".dll", ".a", ".so", ".ts", ".flv", ".ndjson") and path.name not in ("WORKSTATION_HANDOFF.md", "control-panel.png"))
with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(files):
        archive.write(path, Path("SpankVANC") / path.relative_to(ROOT))
digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
print(f"{args.output} ({args.output.stat().st_size:,} bytes)")
args.output.with_suffix(".zip.sha256").write_text(digest+"  "+args.output.name+"\n")
print(f"SHA256 {digest}")
