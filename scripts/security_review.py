"""Scan Git publication candidates without disclosing matched secret values.

This is a focused pre-publication check, not a complete secret-scanner substitute.
"""
import json
from pathlib import Path
import re
import subprocess

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]

IGNORE_PROBES = [
    ".env", ".venv/Scripts/python.exe", "logs/pipeline.log", "data/raw/example.json",
    "powerbi/example.pbix", "powerbi/x.SemanticModel/.pbi/cache.abf", "infra/aws/terraform.tfstate",
    "database.dump", "database.backup", "database.bak", "database.sql.gz",
    "database.sql.zip", "database_backup.sql", "db_backups/history.sql",
    "database_backups/history.sql", "pg_backup/history.sql", "data/backups/history.sql",
    "credentials", "credentials.json", ".aws/credentials", "secrets.json",
    "data/cloud_inbox/sample.json",
    ".env.production", "data/other_snapshot.csv", "pipeline.log", ".aws/config",
    "infra/aws/terraform.auto.tfvars.json", "infra/aws/production.tfvars",
    "infra/aws/review.tfplan", "infra/aws/.terraform/providers/example",
    "infra/aws/dist/lambda.zip", "identity.p12", "identity.pfx", "history.sqlite3",
]


def is_sensitive_artifact(name):
    path = Path(name)
    lower_parts = {part.lower() for part in path.parts}
    lower_name = path.name.lower()
    return (
        lower_name == ".env" or (lower_name.startswith(".env.") and lower_name != ".env.example")
        or bool(lower_parts & {".venv", ".aws", ".pbi", "backups", "db_backups",
                               "database_backups", "pg_backup", "logs", ".terraform", "data"})
        or path.suffix.lower() in {".pbix", ".pbit", ".dump", ".backup", ".bak", ".pem", ".key",
                                   ".p12", ".pfx", ".log", ".tfvars", ".tfplan", ".sqlite", ".sqlite3", ".db"}
        or lower_name.endswith(".tfvars.json")
        or ("infra" in lower_parts and "aws" in lower_parts and "dist" in lower_parts)
        or bool(re.search(r"\.tfstate(?:\.|$)", lower_name))
        or lower_name.endswith((".sql.gz", ".sql.zip"))
        or (lower_name.endswith(".sql") and ("backup" in lower_name or "dump" in lower_name))
        or lower_name == "credentials" or lower_name.startswith("credentials.")
        or lower_name in {"secrets.json", "secrets.yaml", "secrets.yml"}
    )


def review_repository(root=ROOT):
    output = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root)
    paths = sorted(set(p for p in output.decode().split("\0") if p))
    tracked = [p for p in subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0") if p]
    tracked_paths = set(tracked)
    sensitive = [v for k, v in dotenv_values(root / ".env").items()
                 if any(word in k.upper() for word in ("PASSWORD", "TOKEN", "SECRET", "KEY"))
                 and v and len(v) >= 8]
    patterns = [rb"(?:AKIA|ASIA)[A-Z0-9]{16}", rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                rb"postgres(?:ql)?://[^\s/:]+:[^\s/@]+@"]
    findings, large = [], []
    for name in paths:
        path = root / name
        versions = [path.read_bytes()] if path.is_file() else []
        if name in tracked_paths:
            # The staged blob may still contain a secret removed from the
            # working copy. Inspect Git's actual index without changing it.
            versions.append(subprocess.check_output(["git", "show", f":{name}"], cwd=root))
        # Check tracked/force-staged files too: .gitignore cannot protect them.
        if is_sensitive_artifact(name):
            findings.append(name)
        for data in versions:
            if len(data) > 10 * 1024 * 1024:
                large.append(name)
            if any(value.encode() in data for value in sensitive) or any(re.search(p, data) for p in patterns):
                findings.append(name)
            if data.startswith(b"PGDMP"):
                findings.append(name)
            # Detect a data-bearing plain SQL dump under an unexpected name.
            if path.suffix.lower() == ".sql" and re.search(
                    rb"^COPY\s+[^\r\n]+\s+FROM stdin;\s*$", data, re.MULTILINE):
                findings.append(name)
    probes = IGNORE_PROBES
    # Check the rules even for force-staged files; Git otherwise skips tracked paths.
    ignored = subprocess.run(["git", "check-ignore", "--no-index", "-z", "--stdin"],
                             input=("\0".join(probes) + "\0").encode(),
                             capture_output=True, cwd=root).stdout.decode().strip("\0").split("\0")
    missing = sorted(set(probes) - set(ignored))
    staged = subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"], cwd=root).decode().split("\0")
    return {"passed": not findings and not missing and not large,
              "candidate_files": len(paths), "tracked_files": len(tracked),
              "staged_files": [p for p in staged if p],
              "index_content_checked": True,
              "secret_or_sensitive_file_findings": sorted(set(findings)),
              "files_over_10_mib": sorted(set(large)), "ignored_probes": ignored, "unprotected_probes": missing,
              "scope": "Current tracked, staged and unignored files; no Git history or external PBIX scan"}


def main():
    result = review_repository()
    target = ROOT / "docs/validation/security_review.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
