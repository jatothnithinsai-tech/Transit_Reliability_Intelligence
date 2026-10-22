
import logging
import os
import subprocess
import sys
import time
import uuid

from pathlib import Path

import psycopg2
from dotenv import load_dotenv


# ==================================================
# PROJECT CONFIGURATION
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "pipeline.log"


# ==================================================
# LOGGING
# ==================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ]
)

logger = logging.getLogger("transit_pipeline")


# ==================================================
# PIPELINE STAGES
# ==================================================

PIPELINE_STEPS = [
    (
        "TfL API Ingestion",
        "src/ingestion/save_raw_status.py"
    ),
    (
        "Data Transformation",
        "src/transformation/transform_tube_status.py"
    ),
    (
        "Data Quality Validation",
        "src/quality/validate_tube_status.py"
    ),
    (
        "PostgreSQL Loading",
        "src/loading/load_tube_status.py"
    )
]


# ==================================================
# POSTGRESQL MONITORING AND CONCURRENCY CONTROL
# ==================================================

class PostgresRunAudit:
    """
    Records pipeline history and prevents
    overlapping pipeline executions.
    """

    # Two integer keys identify this specific
    # pipeline's PostgreSQL advisory lock.
    LOCK_KEY_1 = 74110
    LOCK_KEY_2 = 26001

    def __init__(self):
        self._lock_connection = None

    def connect(self):
        return psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            connect_timeout=10,
            application_name="tfl_pipeline_monitor"
        )

    # ----------------------------------------------
    # Concurrency protection
    # ----------------------------------------------

    def acquire_lock(self):
        """
        Attempt to obtain the pipeline lock.

        Returns True when acquired.
        Returns False when another execution
        already holds the lock.
        """

        if self._lock_connection is not None:
            raise RuntimeError(
                "This audit instance already holds a lock."
            )

        connection = self.connect()

        try:
            # Advisory locks are session-scoped.
            # Autocommit avoids holding a transaction
            # open during the entire ETL process.
            connection.autocommit = True

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT pg_try_advisory_lock(%s, %s)
                    """,
                    (
                        self.LOCK_KEY_1,
                        self.LOCK_KEY_2
                    )
                )

                result = cursor.fetchone()

            if result is None or not isinstance(
                result[0], bool
            ):
                raise RuntimeError(
                    "Unexpected PostgreSQL lock response."
                )

            if not result[0]:
                connection.close()
                return False

            # Keep this session open throughout
            # the entire pipeline execution.
            self._lock_connection = connection

            logger.info(
                "PIPELINE LOCK ACQUIRED"
            )

            return True

        except Exception:
            connection.close()
            raise

    def release_lock(self):
        """
        Closing the dedicated PostgreSQL session
        automatically releases its advisory lock.
        """

        if self._lock_connection is not None:
            try:
                self._lock_connection.close()

                logger.info(
                    "PIPELINE LOCK RELEASED"
                )

            finally:
                self._lock_connection = None

    # ----------------------------------------------
    # Database audit operations
    # ----------------------------------------------

    def execute(self, query, values):
        connection = self.connect()

        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, values)

                    if cursor.rowcount != 1:
                        raise RuntimeError(
                            "Pipeline audit operation affected "
                            "an unexpected number of rows."
                        )

        finally:
            connection.close()

    def start(self, run_id):
        self.execute(
            """
            INSERT INTO monitoring.pipeline_runs (
                run_id,
                started_at,
                status
            )
            VALUES (
                %s::uuid,
                NOW(),
                'RUNNING'
            )
            """,
            (str(run_id),)
        )

    def succeed(self, run_id):
        self.execute(
            """
            UPDATE monitoring.pipeline_runs
            SET
                status = 'SUCCESS',
                finished_at = NOW(),
                failed_step = NULL,
                error_message = NULL
            WHERE run_id = %s::uuid
              AND status = 'RUNNING'
            """,
            (str(run_id),)
        )

    def fail(self, run_id, failed_step, error):
        self.execute(
            """
            UPDATE monitoring.pipeline_runs
            SET
                status = 'FAILED',
                finished_at = NOW(),
                failed_step = %s,
                error_message = %s
            WHERE run_id = %s::uuid
              AND status = 'RUNNING'
            """,
            (
                failed_step,
                type(error).__name__,
                str(run_id)
            )
        )


# ==================================================
# EXECUTE ONE ETL STAGE
# ==================================================

def run_step(step_name, script_path):
    script = PROJECT_ROOT / script_path

    if not script.is_file():
        raise FileNotFoundError(
            f"Pipeline script not found: {script}"
        )

    logger.info(
        "STARTED: %s",
        step_name
    )

    start_time = time.monotonic()

    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=180
        )

        if result.stdout.strip():
            logger.info(
                "\n%s",
                result.stdout.strip()
            )

        duration = time.monotonic() - start_time

        logger.info(
            "COMPLETED: %s | %.2f seconds",
            step_name,
            duration
        )

    except subprocess.TimeoutExpired:
        logger.exception(
            "TIMEOUT: %s",
            step_name
        )
        raise

    except subprocess.CalledProcessError as error:
        if error.stdout:
            logger.error(
                "Output:\n%s",
                error.stdout
            )

        if error.stderr:
            logger.error(
                "Error:\n%s",
                error.stderr
            )

        logger.error(
            "FAILED: %s",
            step_name
        )
        raise


# ==================================================
# FULL PIPELINE CONTROLLER
# ==================================================

def main(audit=None):
    run_id = uuid.uuid4()

    failed_step = "Pipeline initialization"
    audit_started = False
    lock_acquired = False

    logger.info(
        "PIPELINE RUN STARTED | ID: %s",
        run_id
    )

    try:
        if audit is not None:

            # Do not run ETL if another execution
            # already holds the advisory lock.
            lock_acquired = audit.acquire_lock()

            if not lock_acquired:
                logger.warning(
                    "PIPELINE SKIPPED: Another execution "
                    "is already running | ID: %s",
                    run_id
                )

                # Exit code 2 means overlap prevented.
                # No RUNNING audit row is created.
                raise SystemExit(2)

            # Begin database monitoring only after
            # successfully obtaining the lock.
            audit.start(run_id)
            audit_started = True

            logger.info(
                "Monitoring audit started | ID: %s",
                run_id
            )

        # Run ETL stages sequentially.
        for step_name, script_path in PIPELINE_STEPS:
            failed_step = step_name

            run_step(
                step_name,
                script_path
            )

        # Mark successful completion.
        if audit is not None:
            failed_step = "Monitoring completion"
            audit.succeed(run_id)

        logger.info(
            "PIPELINE RUN SUCCESSFUL | ID: %s",
            run_id
        )

    except SystemExit:
        raise

    except Exception as error:
        logger.exception(
            "PIPELINE RUN FAILED | ID: %s",
            run_id
        )

        if audit is not None and audit_started:
            try:
                audit.fail(
                    run_id,
                    failed_step,
                    error
                )

            except Exception:
                logger.exception(
                    "FAILED TO UPDATE MONITORING AUDIT"
                )

        raise SystemExit(1)

    finally:
        # Always release the lock, including when
        # an ETL stage or monitoring operation fails.
        if audit is not None and lock_acquired:
            try:
                audit.release_lock()

            except Exception:
                logger.exception(
                    "FAILED TO RELEASE PIPELINE LOCK"
                )


if __name__ == "__main__":
    main(audit=PostgresRunAudit())
