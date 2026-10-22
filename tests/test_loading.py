
import csv
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.loading import load_tube_status as loading


COLUMNS = [
    "snapshot_time",
    "line_id",
    "line_name",
    "status_severity",
    "status_description",
    "reason",
    "from_date",
    "to_date",
    "is_now",
    "source_file"
]


class TestPostgreSQLLoader(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.root = Path(self.temp.name)
        self.csv_file = self.root / "tube_status_clean.csv"

        self.source = (
            "data/raw/tube_status_20261015_103000.json"
        )

        self.raw_file = self.root / self.source
        self.raw_file.parent.mkdir(parents=True)
        self.raw_file.write_text("[]", encoding="utf-8")

        self.row = {
            "snapshot_time": "2026-10-15 10:30:00",
            "line_id": "central",
            "line_name": "Central",
            "status_severity": "10",
            "status_description": "Good Service",
            "reason": "",
            "from_date": "",
            "to_date": "",
            "is_now": "True",
            "source_file": self.source
        }

        for name, value in [
            ("PROJECT_ROOT", self.root),
            ("CSV_FILE", self.csv_file)
        ]:
            patcher = patch.object(loading, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_csv(self, rows, columns=None):
        columns = COLUMNS if columns is None else columns

        with self.csv_file.open(
            "w", encoding="utf-8", newline=""
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=columns,
                extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(rows)

    def test_valid_csv_accepted(self):
        self.write_csv([self.row])

        result = loading.read_processed_data()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["line_id"], "central")

    def test_missing_required_column_rejected(self):
        columns = [
            c for c in COLUMNS if c != "source_file"
        ]

        self.write_csv([self.row], columns)

        with self.assertRaises(ValueError):
            loading.read_processed_data()

    def test_invalid_severity_rejected(self):
        for value in ["-1", "21", "invalid", "5.5"]:
            with self.subTest(severity=value):
                row = self.row.copy()
                row["status_severity"] = value
                self.write_csv([row])

                with self.assertRaises(ValueError):
                    loading.read_processed_data()

    def test_missing_raw_file_rejected(self):
        self.write_csv([self.row])
        self.raw_file.unlink()

        with self.assertRaises(FileNotFoundError):
            loading.read_processed_data()

    def test_invalid_boolean_rejected(self):
        row = self.row.copy()
        row["is_now"] = "maybe"

        self.write_csv([row])

        with self.assertRaises(ValueError):
            loading.read_processed_data()

    def test_mixed_snapshot_sources_rejected(self):
        other = (
            "data/raw/tube_status_20261015_113000.json"
        )

        other_file = self.root / other
        other_file.write_text("[]", encoding="utf-8")

        second = self.row.copy()
        second["source_file"] = other

        self.write_csv([self.row, second])

        with self.assertRaises(ValueError):
            loading.read_processed_data()

    def test_database_load_uses_conflict_protection(self):
        self.write_csv([self.row])

        connection = MagicMock()
        cursor = (
            connection.cursor.return_value
            .__enter__.return_value
        )

        executed_sql = []

        def fake_execute(sql, params):
            executed_sql.append(sql)

            if "INSERT INTO staging.tube_status_history" in sql:
                cursor.rowcount = 1
            else:
                cursor.rowcount = 0

        cursor.execute.side_effect = fake_execute

        with patch.object(
            loading,
            "connect_database",
            return_value=connection
        ):
            output = io.StringIO()

            with redirect_stdout(output):
                loading.load_tube_status()

        self.assertIn(
            "New history records inserted: 1",
            output.getvalue()
        )

        self.assertTrue(
            any("ON CONFLICT" in sql for sql in executed_sql)
        )

        self.assertTrue(
            any("DO NOTHING" in sql for sql in executed_sql)
        )

        connection.close.assert_called_once()

    def test_database_failure_propagates(self):
        self.write_csv([self.row])

        connection = MagicMock()

        cursor = (
            connection.cursor.return_value
            .__enter__.return_value
        )

        cursor.execute.side_effect = RuntimeError(
            "Simulated database failure"
        )

        with patch.object(
            loading,
            "connect_database",
            return_value=connection
        ):
            with redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError):
                    loading.load_tube_status()

        connection.__exit__.assert_called_once()
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
