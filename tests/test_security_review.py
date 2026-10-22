"""Exercise actual Git ignore/staging behavior in disposable repositories."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from scripts.security_review import ROOT, review_repository


class GitPublicationSafetyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        shutil.copy2(ROOT / ".gitignore", self.root / ".gitignore")

    def write(self, name, value="test fixture"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def stage(self, name):
        subprocess.run(["git", "add", "-f", "--", name], cwd=self.root, check=True, capture_output=True)

    def test_sensitive_artifacts_are_ignored_by_git(self):
        for name in [".env", "data/raw/sample.json", "database.dump", "database.backup",
                     "database.sql.gz", "credentials.json", "db_backups/history.sql",
                     "infra/aws/terraform.tfstate.backup"]:
            self.write(name, "DB_PASSWORD=local-test-placeholder\n" if name == ".env" else "test fixture")
        result = review_repository(self.root)
        self.assertTrue(result["passed"])
        self.assertEqual(result["unprotected_probes"], [])
        self.assertEqual(result["candidate_files"], 1)

    def test_force_staged_backup_is_rejected(self):
        self.write("database.dump")
        self.stage("database.dump")
        result = review_repository(self.root)
        self.assertFalse(result["passed"])
        self.assertIn("database.dump", result["staged_files"])
        self.assertIn("database.dump", result["secret_or_sensitive_file_findings"])

    def test_force_staged_raw_data_is_rejected(self):
        for source in ["data/raw/sample.json", "data/cloud_inbox/sample.json"]:
            with self.subTest(source=source):
                self.write(source, "[]")
                self.stage(source)
                self.assertIn(source, review_repository(self.root)["secret_or_sensitive_file_findings"])

    def test_known_secret_in_unignored_source_is_rejected_without_disclosure(self):
        secret = "LOCAL-TEST-CREDENTIAL-7654321"
        self.write(".env", "DB_PASSWORD=" + secret)
        self.write("config.py", "password = '" + secret + "'")
        result = review_repository(self.root)
        self.assertFalse(result["passed"])
        self.assertEqual(result["secret_or_sensitive_file_findings"], ["config.py"])
        self.assertNotIn(secret, str(result))

    def test_plain_sql_data_dump_under_unexpected_name_is_rejected(self):
        self.write("export.sql", "COPY staging.tube_lines (line_id) FROM stdin;\ncentral\n\\.\n")
        self.assertIn("export.sql", review_repository(self.root)["secret_or_sensitive_file_findings"])

    def test_schema_and_environment_templates_remain_publishable(self):
        self.write("sql/00_schema_reference.sql", "CREATE SCHEMA staging;\n")
        self.write(".env.example", "DB_PASSWORD=your_password_here\n")
        self.assertTrue(review_repository(self.root)["passed"])

    def test_secret_still_in_index_is_rejected_when_working_copy_is_clean(self):
        secret = "LOCAL-TEST-CREDENTIAL-7654321"
        self.write(".env", "DB_PASSWORD=" + secret)
        self.write("config.py", "password = '" + secret + "'")
        self.stage("config.py")
        self.write("config.py", "# working copy is clean\n")
        result = review_repository(self.root)
        self.assertFalse(result["passed"])
        self.assertIn("config.py", result["secret_or_sensitive_file_findings"])
        self.assertTrue(result["index_content_checked"])

    def test_custom_postgres_dump_detected_under_unexpected_extension(self):
        (self.root / "export.bin").write_bytes(b"PGDMP\x01\x00test fixture")
        self.assertIn("export.bin", review_repository(self.root)["secret_or_sensitive_file_findings"])

    def test_force_staged_terraform_inputs_plans_and_cache_are_rejected(self):
        names = ["infra/aws/production.tfvars", "infra/aws/terraform.auto.tfvars.json",
                 "infra/aws/review.tfplan", "infra/aws/.terraform/providers/example",
                 "infra/aws/dist/lambda.zip"]
        for name in names:
            self.write(name)
            self.stage(name)
        result = review_repository(self.root)
        self.assertFalse(result["passed"])
        self.assertTrue(set(names).issubset(result["secret_or_sensitive_file_findings"]))
        self.assertEqual(result["unprotected_probes"], [])

    def test_force_staged_logs_certificates_and_local_data_are_rejected(self):
        names = ["pipeline.log", "identity.p12", "identity.pfx", "history.sqlite3",
                 "data/other_snapshot.csv"]
        for name in names:
            self.write(name)
            self.stage(name)
        result = review_repository(self.root)
        self.assertFalse(result["passed"])
        self.assertTrue(set(names).issubset(result["secret_or_sensitive_file_findings"]))

    def test_oversized_publication_file_is_rejected(self):
        with (self.root / "large.bin").open("wb") as stream:
            stream.truncate(10 * 1024 * 1024 + 1)
        result = review_repository(self.root)
        self.assertFalse(result["passed"])
        self.assertEqual(result["files_over_10_mib"], ["large.bin"])
