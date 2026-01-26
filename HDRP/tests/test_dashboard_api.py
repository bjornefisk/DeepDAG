"""Tests for dashboard QueryExecutor behavior."""

import threading
import time
import unittest
from unittest.mock import patch

from HDRP.dashboard.api import QueryExecutor, ExecutionStatus


class TestQueryExecutor(unittest.TestCase):
    """QueryExecutor unit tests."""

    def setUp(self):
        self.executor = QueryExecutor()

    def _wait_for_status(self, run_id, expected_status, timeout=2.0):
        """Wait for a specific status or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            status = self.executor.get_status(run_id)
            if status and status["status"] == expected_status:
                return status
            time.sleep(0.05)
        return self.executor.get_status(run_id)

    @patch("HDRP.dashboard.api.QueryExecutor._execute_python_mode")
    def test_execute_query_completes_python_mode(self, mock_run):
        """Query completes successfully in python mode."""
        mock_run.return_value = {"success": True, "report": "ok"}

        run_id = self.executor.execute_query("test query", provider="simulated", mode="python")
        status = self._wait_for_status(run_id, ExecutionStatus.COMPLETED.value)

        self.assertIsNotNone(status)
        self.assertEqual(status["status"], ExecutionStatus.COMPLETED.value)
        self.assertEqual(status.get("report"), "ok")

    @patch("HDRP.dashboard.api.QueryExecutor._execute_orchestrator_mode")
    def test_execute_query_completes_orchestrator_mode(self, mock_run):
        """Query completes successfully in orchestrator mode."""
        mock_run.return_value = {"success": True, "report": "orchestrated"}

        run_id = self.executor.execute_query("test query", provider="simulated", mode="orchestrator")
        status = self._wait_for_status(run_id, ExecutionStatus.COMPLETED.value)

        self.assertIsNotNone(status)
        self.assertEqual(status["status"], ExecutionStatus.COMPLETED.value)
        self.assertEqual(status.get("report"), "orchestrated")

    @patch("HDRP.dashboard.api.QueryExecutor._execute_python_mode")
    def test_cancel_query_marks_cancelled(self, mock_run):
        """Cancelling a running query updates status to cancelled."""
        block = threading.Event()

        def fake_run(*_args, **_kwargs):
            block.wait(0.2)
            return {"success": True, "report": "ok"}

        mock_run.side_effect = fake_run

        run_id = self.executor.execute_query("test query", provider="simulated", mode="python")
        cancelled = self.executor.cancel_query(run_id)
        block.set()

        status = self._wait_for_status(run_id, ExecutionStatus.CANCELLED.value)

        self.assertTrue(cancelled)
        self.assertIsNotNone(status)
        self.assertEqual(status["status"], ExecutionStatus.CANCELLED.value)


if __name__ == "__main__":
    unittest.main()
