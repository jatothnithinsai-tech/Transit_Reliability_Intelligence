
import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

VALIDATOR_SCRIPT = (
    PROJECT_ROOT / "src" / "quality" / "validate_tube_status.py"
)

COLUMNS = [
    "snapshot_time",
    "line_id",
    "line_name",
    "mode",
    "status_severity",
    "status_description"
]


class TestTfLDataQuality(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.root = Path(self.temp_dir.name)
        self.processed_dir = self.root / "data" / "processed"
        self.processed_dir.mkdir(parents=True)

        self.csv_file = (
            self.processed_dir / "tube_status_clean.csv"
        )

        self.valid_row = {
            "snapshot_time": "2026-10-15 10:30:00",
            "line_id": "central",
            "line_name": "Central",
            "mode": "tube",
            "status_severity": "10",
            "status_description": "Good Service"
        }

    def write_csv(self, rows, columns=None):
        columns = columns or COLUMNS

        with self.csv_file.open(
            "w",
            newline="",
            encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=columns,
                extrasaction="ignore"
            )

            writer.writeheader()
            writer.writerows(rows)

    def run_validation(self):
        return subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=30
        )

    def test_valid_data_passes(self):
        self.write_csv([self.valid_row])

        result = self.run_validation()

        self.assertEqual(result.returncode, 0)
        self.assertIn(
            "RESULT: DATA PASSED QUALITY CHECKS",
            result.stdout
        )

    def test_missing_column_rejected(self):
        columns = [
            column for column in COLUMNS
            if column != "line_id"
        ]

        self.write_csv([self.valid_row], columns)

        result = self.run_validation()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "Missing required columns",
            result.stdout
        )

    def test_missing_line_id_rejected(self):
        row = self.valid_row.copy()
        row["line_id"] = ""

        self.write_csv([row])

        result = self.run_validation()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "Missing line_id",
            result.stdout
        )

    def test_missing_line_name_rejected(self):
        row = self.valid_row.copy()
        row["line_name"] = ""

        self.write_csv([row])

        result = self.run_validation()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "Missing line_name",
            result.stdout
        )

    def test_missing_status_description_rejected(self):
        row = self.valid_row.copy()
        row["status_description"] = ""

        self.write_csv([row])

        result = self.run_validation()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "Missing status descriptions",
            result.stdout
        )

    def test_invalid_severity_rejected(self):
        invalid_values = [
            "-1",
            "21",
            "5.5",
            "invalid",
            ""
        ]

        for severity in invalid_values:
            with self.subTest(severity=severity):
                row = self.valid_row.copy()
                row["status_severity"] = severity

                self.write_csv([row])

                result = self.run_validation()

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "Invalid status severity",
                    result.stdout
                )

    def test_duplicate_status_rejected(self):
        self.write_csv([
            self.valid_row,
            self.valid_row.copy()
        ])

        result = self.run_validation()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "duplicate status records found",
            result.stdout
        )

    def test_invalid_timestamp_rejected(self):
        row = self.valid_row.copy()
        row["snapshot_time"] = "2026-99-99 25:70:00"

        self.write_csv([row])

        result = self.run_validation()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "invalid snapshot timestamps",
            result.stdout
        )


if __name__ == "__main__":
    unittest.main()
