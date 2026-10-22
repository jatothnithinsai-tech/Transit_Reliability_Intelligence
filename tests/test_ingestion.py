
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.ingestion import save_raw_status as ingestion


class TestTfLIngestion(unittest.TestCase):

    def test_api_response_success(self):
        """Valid TfL API responses should be accepted."""

        sample_data = [
            {
                "id": "central",
                "name": "Central",
                "lineStatuses": [
                    {
                        "statusSeverity": 10,
                        "statusSeverityDescription": "Good Service"
                    }
                ]
            }
        ]

        with patch.object(ingestion.requests, "Session") as mock_session:
            session = mock_session.return_value.__enter__.return_value

            response = MagicMock()
            response.json.return_value = sample_data
            session.get.return_value = response

            result = ingestion.fetch_tfl_data()

            self.assertEqual(result, sample_data)
            response.raise_for_status.assert_called_once()

            self.assertEqual(
                session.get.call_args.kwargs["timeout"],
                (5, 30)
            )

    def test_invalid_api_response(self):
        """Invalid API structures must be rejected."""

        with patch.object(ingestion.requests, "Session") as mock_session:
            session = mock_session.return_value.__enter__.return_value

            response = MagicMock()
            response.json.return_value = {"error": "invalid data"}
            session.get.return_value = response

            with self.assertRaises(ValueError):
                ingestion.fetch_tfl_data()

    def test_retry_configuration(self):
        """HTTP retry configuration must be enabled."""

        with patch.object(ingestion.requests, "Session") as mock_session:
            session = mock_session.return_value.__enter__.return_value

            response = MagicMock()
            response.json.return_value = [{"id": "central"}]
            session.get.return_value = response

            ingestion.fetch_tfl_data()

            session.mount.assert_called_once()

            adapter = session.mount.call_args.args[1]
            retry = adapter.max_retries

            self.assertEqual(retry.total, 3)
            self.assertTrue(
                {429, 500, 502, 503, 504}.issubset(
                    set(retry.status_forcelist)
                )
            )

    def test_atomic_json_saving(self):
        """Raw JSON must save without leftover temporary files."""

        sample_data = [
            {"id": "victoria", "name": "Victoria"}
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(
                ingestion, "RAW_DATA_DIR", Path(temp_dir)
            ):
                output = ingestion.save_raw_data(sample_data)

                self.assertTrue(output.exists())

                with output.open("r", encoding="utf-8") as file:
                    saved_data = json.load(file)

                self.assertEqual(saved_data, sample_data)

                temporary_files = list(
                    Path(temp_dir).glob("*.tmp")
                )

                self.assertEqual(len(temporary_files), 0)

    def test_failed_save_cleans_up(self):
        """Failed atomic replacement must clean temporary files."""

        sample_data = [{"id": "bakerloo"}]

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(
                ingestion, "RAW_DATA_DIR", Path(temp_dir)
            ):
                with patch.object(
                    ingestion.os,
                    "replace",
                    side_effect=OSError("Simulated write failure")
                ):
                    with self.assertRaises(OSError):
                        ingestion.save_raw_data(sample_data)

                self.assertEqual(
                    list(Path(temp_dir).iterdir()),
                    []
                )


if __name__ == "__main__":
    unittest.main()
