"""Build the Terraform Lambda ZIP locally. Never calls AWS.

--installed copies portable Python sources from the verified environment without
network access. The default resolves portable wheels from PyPI.
"""
import argparse
import importlib.util
import importlib.metadata
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ["boto3", "botocore", "s3transfer", "jmespath", "dateutil", "six",
            "requests", "urllib3", "idna", "charset_normalizer", "certifi"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 13):
        raise RuntimeError("Build with Python 3.13, matching the Lambda runtime")
    with tempfile.TemporaryDirectory() as folder:
        stage = Path(folder)
        if args.installed:
            for line in (ROOT / "requirements-lambda.txt").read_text().splitlines():
                if "==" in line:
                    name, version = line.split("==", 1)
                    if importlib.metadata.version(name) != version:
                        raise RuntimeError(f"Installed dependency differs from Lambda lock: {name}")
            for name in PACKAGES:
                spec = importlib.util.find_spec(name)
                if spec is None:
                    raise RuntimeError(f"Missing dependency: {name}")
                path = Path(spec.origin)
                if spec.submodule_search_locations:
                    shutil.copytree(path.parent, stage / name,
                                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyd", "*.so"))
                else:
                    shutil.copy2(path, stage / path.name)
        else:
            subprocess.run([sys.executable, "-m", "pip", "install", "--only-binary=:all:",
                            "--implementation", "py", "--platform", "any", "--no-compile",
                            "--target", str(stage), "-r", str(ROOT / "requirements-lambda.txt")], check=True)
        for name in ["storage", "cloud"]:
            shutil.copytree(ROOT / "src" / name, stage / "src" / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (stage / "src/__init__.py").write_text("", encoding="utf-8")
        (stage / "src/ingestion").mkdir()
        (stage / "src/ingestion/__init__.py").write_text("", encoding="utf-8")
        shutil.copy2(ROOT / "src/ingestion/tfl_client.py", stage / "src/ingestion/tfl_client.py")
        target = ROOT / "infra/aws/dist/lambda.zip"
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(stage.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyd", ".so"}:
                    archive.write(path, path.relative_to(stage).as_posix())
        print(f"Built {target.relative_to(ROOT)} ({target.stat().st_size:,} bytes)")
        manifest = {"runtime": "python3.13", "architecture": "x86_64", "native_extensions": False,
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                    "dependency_lock": (ROOT / "requirements-lambda.txt").read_text().splitlines(),
                    "build_source": "installed" if args.installed else "portable wheels"}
        (target.parent / "build_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
