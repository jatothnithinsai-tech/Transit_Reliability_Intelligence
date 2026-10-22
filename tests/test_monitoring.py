
import unittest
from unittest.mock import MagicMock, patch

from src.pipeline import run_pipeline as pipeline


class TestPipelineMonitoring(unittest.TestCase):

    def setUp(self):
        """Create mocked database objects."""
        self.audit = pipeline.PostgresRunAudit()

        self.connection = MagicMock()

        self.cursor = (
            self.connection.cursor.return_value
            .__enter__.return_value
        )

        self.cursor.rowcount = 1

        patcher = patch.object(
            self.audit,
            "connect",
            return_value=self.connection
        )

        patcher.start()
        self.addCleanup(patcher.stop)

        self.run_id = (
            "6fdfe04a-0184-41c3-bf9c-6389ba106e26"
        )

    def test_start_creates_running_record(self):
        """A new execution should create a RUNNING audit row."""

        self.audit.start(self.run_id)

        sql, parameters = self.cursor.execute.call_args.args

        self.assertIn(
            "INSERT INTO monitoring.pipeline_runs",
            sql
        )

        self.assertIn("'RUNNING'", sql)

        self.assertEqual(
            parameters,
            (self.run_id,)
        )

        self.connection.close.assert_called_once()

    def test_success_updates_run(self):
        """Successful executions should be marked SUCCESS."""

        self.audit.succeed(self.run_id)

        sql, parameters = self.cursor.execute.call_args.args

        self.assertIn(
            "UPDATE monitoring.pipeline_runs",
            sql
        )

        self.assertIn(
            "status = 'SUCCESS'",
            sql
        )

        self.assertIn(
            "finished_at = NOW()",
            sql
        )

        self.assertIn(
            "AND status = 'RUNNING'",
            sql
        )

        self.assertEqual(
            parameters,
            (self.run_id,)
        )

    def test_failure_records_failed_stage(self):
        """Failed executions should record the failing stage."""

        self.audit.fail(
            self.run_id,
            "Data Quality Validation",
            RuntimeError("Simulated failure")
        )

        sql, parameters = self.cursor.execute.call_args.args

        self.assertIn(
            "status = 'FAILED'",
            sql
        )

        self.assertEqual(
            parameters[0],
            "Data Quality Validation"
        )

        self.assertEqual(
            parameters[1],
            "RuntimeError"
        )

        self.assertEqual(
            parameters[2],
            self.run_id
        )

    def test_unexpected_row_count_rejected(self):
        """Audit updates must affect exactly one row."""

        self.cursor.rowcount = 0

        with self.assertRaises(RuntimeError):
            self.audit.succeed(self.run_id)

        self.connection.close.assert_called_once()

    def test_database_error_propagates(self):
        """Database errors must not be silently ignored."""

        self.cursor.execute.side_effect = RuntimeError(
            "Simulated database error"
        )

        with self.assertRaises(RuntimeError):
            self.audit.start(self.run_id)

        self.connection.__exit__.assert_called_once()
        self.connection.close.assert_called_once()

    def test_pipeline_success_calls_audit(self):
        """A successful pipeline should start and finish auditing."""

        audit = MagicMock()

        with (
            patch.object(pipeline, "run_step") as mock_step,
            patch.object(pipeline, "logger")
        ):
            pipeline.main(audit=audit)

        audit.start.assert_called_once()
        audit.succeed.assert_called_once()
        audit.fail.assert_not_called()

        started_id = audit.start.call_args.args[0]
        finished_id = audit.succeed.call_args.args[0]

        self.assertEqual(started_id, finished_id)

        self.assertEqual(
            mock_step.call_count,
            len(pipeline.PIPELINE_STEPS)
        )

    def test_pipeline_failure_calls_audit(self):
        """A failed ETL stage should create a FAILED audit."""

        audit = MagicMock()
        executed = []

        def simulated_step(name, script_path):
            executed.append(name)

            if name == "Data Quality Validation":
                raise RuntimeError(
                    "Simulated validation failure"
                )

        with (
            patch.object(
                pipeline,
                "run_step",
                side_effect=simulated_step
            ),
            patch.object(pipeline, "logger")
        ):
            with self.assertRaises(SystemExit) as error:
                pipeline.main(audit=audit)

        self.assertEqual(error.exception.code, 1)

        audit.start.assert_called_once()
        audit.fail.assert_called_once()
        audit.succeed.assert_not_called()

        failure_args = audit.fail.call_args.args

        self.assertEqual(
            failure_args[1],
            "Data Quality Validation"
        )

        self.assertIsInstance(
            failure_args[2],
            RuntimeError
        )

        self.assertNotIn(
            "PostgreSQL Loading",
            executed
        )

    def test_audit_start_failure_stops_pipeline(self):
        """ETL must not start if required monitoring fails."""

        audit = MagicMock()

        audit.start.side_effect = ConnectionError(
            "Simulated monitoring connection failure"
        )

        with (
            patch.object(pipeline, "run_step") as mock_step,
            patch.object(pipeline, "logger")
        ):
            with self.assertRaises(SystemExit) as error:
                pipeline.main(audit=audit)

        self.assertEqual(error.exception.code, 1)

        mock_step.assert_not_called()
        audit.succeed.assert_not_called()
        audit.fail.assert_not_called()


if __name__ == "__main__":
    unittest.main()
