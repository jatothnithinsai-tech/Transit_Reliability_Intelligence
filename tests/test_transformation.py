
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.transformation import transform_tube_status as transformation


class TestTfLTransformation(unittest.TestCase):

    def setUp(self):
        """Create isolated temporary project folders."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        self.raw_dir = self.root / "data" / "raw"
        self.processed_dir = self.root / "data" / "processed"

        self.raw_dir.mkdir(parents=True)
        self.processed_dir.mkdir(parents=True)

        self.patches = [
            patch.object(transformation, "PROJECT_ROOT", self.root),
            patch.object(transformation, "RAW_DIR", self.raw_dir),
            patch.object(
                transformation, "PROCESSED_DIR", self.processed_dir
            )
        ]

        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

        self.addCleanup(self.temp_dir.cleanup)

    def create_raw_file(self, timestamp, data):
        """Write a sample TfL JSON snapshot."""
        path = self.raw_dir / f"tube_status_{timestamp}.json"

        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file)

        return path

    def sample_data(self):
        return [
            {
                "id": "central",
                "name": "Central",
                "modeName": "tube",
                "lineStatuses": [
                    {
                        "statusSeverity": 6,
                        "statusSeverityDescription": "Severe Delays",
                        "reason": "Train cancellations",
                        "validityPeriods": [
                            {
                                "fromDate": "2026-10-15T10:00:00Z",
                                "toDate": "2026-10-15T12:00:00Z",
                                "isNow": True
                            }
                        ],
                        "disruption": {
                            "category": "RealTime",
                            "description": "Service disruption"
                        }
                    },
                    {
                        "statusSeverity": 9,
                        "statusSeverityDescription": "Minor Delays",
                        "reason": "Signal failure",
                        "validityPeriods": []
                    }
                ]
            },
            {
                "id": "victoria",
                "name": "Victoria",
                "modeName": "tube",
                "lineStatuses": [
                    {
                        "statusSeverity": 10,
                        "statusSeverityDescription": "Good Service",
                        "validityPeriods": []
                    }
                ]
            }
        ]

    def test_transform_creates_csv(self):
        """Transformation must generate a readable CSV."""
        self.create_raw_file(
            "20261015_103000", self.sample_data()
        )

        transformation.transform_tube_status()

        output = self.processed_dir / "tube_status_clean.csv"

        self.assertTrue(output.is_file())

        df = pd.read_csv(output)

        self.assertEqual(len(df), 3)
        self.assertEqual(len(df.columns), 13)

    def test_original_snapshot_timestamp(self):
        """Preserve collection time from the raw filename."""
        self.create_raw_file(
            "20261015_103000", self.sample_data()
        )

        transformation.transform_tube_status()

        df = pd.read_csv(
            self.processed_dir / "tube_status_clean.csv"
        )

        self.assertEqual(
            set(df["snapshot_time"]),
            {"2026-10-15 10:30:00"}
        )

    def test_status_and_disruption_fields(self):
        """Extract status, disruption and validity information."""
        self.create_raw_file(
            "20261015_103000", self.sample_data()
        )

        transformation.transform_tube_status()

        df = pd.read_csv(
            self.processed_dir / "tube_status_clean.csv"
        )

        central = df[
            (df["line_id"] == "central") &
            (df["status_severity"] == 6)
        ].iloc[0]

        self.assertEqual(
            central["status_description"], "Severe Delays"
        )
        self.assertEqual(
            central["disruption_category"], "RealTime"
        )
        self.assertEqual(
            central["from_date"], "2026-10-15T10:00:00Z"
        )
        self.assertTrue(bool(central["is_now"]))

    def test_source_file_lineage(self):
        """Every row must reference the original raw JSON."""
        self.create_raw_file(
            "20261015_103000", self.sample_data()
        )

        transformation.transform_tube_status()

        df = pd.read_csv(
            self.processed_dir / "tube_status_clean.csv"
        )

        expected = (
            "data/raw/tube_status_20261015_103000.json"
        )

        self.assertEqual(
            set(df["source_file"]),
            {expected}
        )

    def test_latest_snapshot_selected(self):
        """Choose the most recent snapshot by filename."""
        self.create_raw_file(
            "20261014_090000",
            [{"id": "old", "lineStatuses": [
                {
                    "statusSeverity": 10,
                    "statusSeverityDescription": "Good Service"
                }
            ]}]
        )

        self.create_raw_file(
            "20261015_103000",
            self.sample_data()
        )

        transformation.transform_tube_status()

        df = pd.read_csv(
            self.processed_dir / "tube_status_clean.csv"
        )

        self.assertEqual(len(df), 3)
        self.assertNotIn("old", set(df["line_id"]))

    def test_invalid_raw_data_rejected(self):
        """Reject an invalid API response structure."""
        self.create_raw_file(
            "20261015_103000",
            {"error": "Invalid response"}
        )

        with self.assertRaises(ValueError):
            transformation.transform_tube_status()

    def test_atomic_csv_write(self):
        """No temporary CSV files should remain after success."""
        self.create_raw_file(
            "20261015_103000", self.sample_data()
        )

        transformation.transform_tube_status()

        self.assertTrue(
            (self.processed_dir / "tube_status_clean.csv").exists()
        )

        self.assertEqual(
            list(self.processed_dir.glob("*.tmp")),
            []
        )


if __name__ == "__main__":
    unittest.main()
