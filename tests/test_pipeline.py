
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.pipeline import run_pipeline as pipeline


class TestPipelineController(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.root = Path(self.temp_dir.name)

        self.script = (
            self.root / "src" / "ingestion" / "save_raw_status.py"
        )

        self.script.parent.mkdir(parents=True)
        self.script.write_text(
            "print('Test ingestion')",
            encoding="utf-8"
        )

        patcher = patch.object(
            pipeline,
            "PROJECT_ROOT",
            self.root
        )

        patcher.start()
        self.addCleanup(patcher.stop)

    def test_step_uses_active_python(self):
        """Pipeline must use the active Python interpreter."""

        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Test successful",
            stderr=""
        )

        with patch.object(
            pipeline.subprocess,
            "run",
            return_value=completed
        ) as mock_run:

            pipeline.run_step(
                "Test ingestion",
                "src/ingestion/save_raw_status.py"
            )

        args = mock_run.call_args.args[0]

        self.assertEqual(args[0], sys.executable)
        self.assertEqual(args[1], str(self.script))

    def test_step_uses_correct_working_directory(self):
        """Every stage must run from the project root."""

        with patch.object(
            pipeline.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="", stderr=""
            )
        ) as mock_run:

            pipeline.run_step(
                "Test ingestion",
                "src/ingestion/save_raw_status.py"
            )

        self.assertEqual(
            mock_run.call_args.kwargs["cwd"],
            self.root
        )

    def test_missing_script_rejected(self):
        """Missing pipeline scripts must stop execution."""

        with patch.object(
            pipeline.subprocess,
            "run"
        ) as mock_run:

            with self.assertRaises(FileNotFoundError):
                pipeline.run_step(
                    "Missing stage",
                    "src/missing.py"
                )

        mock_run.assert_not_called()

    def test_subprocess_failure_propagates(self):
        """A failed stage must raise an exception."""

        error = subprocess.CalledProcessError(
            1,
            ["python", "test.py"],
            output="Failed validation",
            stderr="Simulated failure"
        )

        with patch.object(
            pipeline.subprocess,
            "run",
            side_effect=error
        ):
            with self.assertRaises(
                subprocess.CalledProcessError
            ):
                pipeline.run_step(
                    "Test ingestion",
                    "src/ingestion/save_raw_status.py"
                )

    def test_timeout_protection(self):
        """Long-running pipeline stages must time out."""

        error = subprocess.TimeoutExpired(
            cmd=["python", "test.py"],
            timeout=180
        )

        with patch.object(
            pipeline.subprocess,
            "run",
            side_effect=error
        ) as mock_run:

            with self.assertRaises(
                subprocess.TimeoutExpired
            ):
                pipeline.run_step(
                    "Test ingestion",
                    "src/ingestion/save_raw_status.py"
                )

        self.assertEqual(
            mock_run.call_args.kwargs["timeout"],
            180
        )

    def test_all_pipeline_stages_execute_in_order(self):
        """Successful runs must execute all stages in order."""

        with patch.object(
            pipeline,
            "run_step"
        ) as mock_step:

            pipeline.main()

        expected_calls = [
            (name, path)
            for name, path in pipeline.PIPELINE_STEPS
        ]

        actual_calls = [
            call.args
            for call in mock_step.call_args_list
        ]

        self.assertEqual(
            actual_calls,
            expected_calls
        )

    def test_pipeline_stops_after_failure(self):
        """A failed stage must prevent subsequent stages."""

        executed = []

        def simulated_step(name, path):
            executed.append(name)

            if name == "Data Quality Validation":
                raise RuntimeError(
                    "Simulated validation failure"
                )

        with patch.object(
            pipeline,
            "run_step",
            side_effect=simulated_step
        ):
            with self.assertRaises(SystemExit) as error:
                pipeline.main()

        self.assertEqual(error.exception.code, 1)

        self.assertEqual(
            executed,
            [
                "TfL API Ingestion",
                "Data Transformation",
                "Data Quality Validation"
            ]
        )

        self.assertNotIn(
            "PostgreSQL Loading",
            executed
        )


if __name__ == "__main__":
    unittest.main()
