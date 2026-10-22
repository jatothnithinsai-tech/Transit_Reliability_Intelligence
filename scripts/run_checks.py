"""Run the automated suite with external socket connections forbidden."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    sys.dont_write_bytecode = True
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer), patch(
            "logging.FileHandler", side_effect=lambda *a, **k: logging.StreamHandler(buffer)), patch(
            "socket.socket.connect", side_effect=AssertionError("External network forbidden in tests")):
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
        result = unittest.TextTestRunner(stream=buffer, verbosity=2).run(suite)
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    (log_dir / "completion_tests.log").write_text(buffer.getvalue(), encoding="utf-8")
    evidence = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "tests_run": result.testsRun,
                "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
                "failures": len(result.failures), "errors": len(result.errors),
                "skipped": len(result.skipped), "external_sockets_forbidden": True,
                "live_pipeline_log_isolated": True,
                "successful": result.wasSuccessful()}
    target = ROOT / "docs/validation/tests.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence))
    if not result.wasSuccessful():
        print(buffer.getvalue())
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
