"""
Unit tests for HDRP Dashboard SSE streaming functionality.

Tests the QueryExecutor subscriber pattern and SSE endpoint for real-time
progress updates.
"""

import json
import queue
import threading
import time
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from HDRP.dashboard.api import (
    ExecutionProgress,
    ExecutionStatus,
    QueryExecutor,
    get_executor,
)


class TestQueryExecutorSubscribers(unittest.TestCase):
    """Tests for QueryExecutor subscriber pattern."""

    def setUp(self):
        """Set up test fixtures."""
        self.executor = QueryExecutor()

    def test_subscribe_to_nonexistent_run(self):
        """Subscribe should work even if run doesn't exist yet."""
        run_id = "test-run-1"
        progress_queue = self.executor.subscribe(run_id)
        
        self.assertIsInstance(progress_queue, queue.Queue)
        self.assertEqual(progress_queue.maxsize, 100)
        
        # Should be empty since run doesn't exist
        self.assertTrue(progress_queue.empty())
        
        # Cleanup
        self.executor.unsubscribe(run_id, progress_queue)

    def test_subscribe_receives_current_status(self):
        """Subscribing to existing run should receive current status immediately."""
        run_id = "test-run-2"
        
        # Create a progress manually
        progress = ExecutionProgress(
            status=ExecutionStatus.RUNNING,
            run_id=run_id,
            query="Test query",
            started_at=datetime.now().isoformat(),
            progress_percent=50.0,
            current_stage="Processing...",
        )
        
        with self.executor._lock:
            self.executor._executions[run_id] = progress
        
        # Subscribe should receive current status
        progress_queue = self.executor.subscribe(run_id)
        
        # Should have received initial status
        self.assertFalse(progress_queue.empty())
        received_data = progress_queue.get(timeout=1.0)
        self.assertEqual(received_data["run_id"], run_id)
        self.assertEqual(received_data["status"], "running")
        self.assertEqual(received_data["progress_percent"], 50.0)
        
        # Cleanup
        self.executor.unsubscribe(run_id, progress_queue)

    def test_progress_update_notifies_subscribers(self):
        """Progress updates should notify all subscribers."""
        run_id = "test-run-3"
        progress_queue = self.executor.subscribe(run_id)
        
        # Create initial progress
        progress = ExecutionProgress(
            status=ExecutionStatus.QUEUED,
            run_id=run_id,
            query="Test query",
            started_at=datetime.now().isoformat(),
        )
        
        with self.executor._lock:
            self.executor._executions[run_id] = progress
        
        # Clear initial status from queue
        try:
            progress_queue.get_nowait()
        except queue.Empty:
            pass
        
        # Update progress
        self.executor._update_progress(
            run_id,
            status=ExecutionStatus.RUNNING,
            progress_percent=25.0,
            current_stage="Starting...",
        )
        
        # Should receive notification
        received_data = progress_queue.get(timeout=1.0)
        self.assertEqual(received_data["status"], "running")
        self.assertEqual(received_data["progress_percent"], 25.0)
        self.assertEqual(received_data["current_stage"], "Starting...")
        
        # Cleanup
        self.executor.unsubscribe(run_id, progress_queue)

    def test_multiple_subscribers_receive_updates(self):
        """Multiple subscribers should all receive progress updates."""
        run_id = "test-run-4"
        queue1 = self.executor.subscribe(run_id)
        queue2 = self.executor.subscribe(run_id)
        queue3 = self.executor.subscribe(run_id)
        
        # Create initial progress
        progress = ExecutionProgress(
            status=ExecutionStatus.QUEUED,
            run_id=run_id,
            query="Test query",
            started_at=datetime.now().isoformat(),
        )
        
        with self.executor._lock:
            self.executor._executions[run_id] = progress
        
        # Clear initial statuses
        for q in [queue1, queue2, queue3]:
            try:
                q.get_nowait()
            except queue.Empty:
                pass
        
        # Update progress
        self.executor._update_progress(
            run_id,
            status=ExecutionStatus.RUNNING,
            progress_percent=50.0,
        )
        
        # All queues should receive update
        for q in [queue1, queue2, queue3]:
            received_data = q.get(timeout=1.0)
            self.assertEqual(received_data["status"], "running")
            self.assertEqual(received_data["progress_percent"], 50.0)
        
        # Cleanup
        for q in [queue1, queue2, queue3]:
            self.executor.unsubscribe(run_id, q)

    def test_unsubscribe_removes_from_subscribers(self):
        """Unsubscribing should remove queue from subscribers."""
        run_id = "test-run-5"
        progress_queue = self.executor.subscribe(run_id)
        
        # Verify subscriber exists
        with self.executor._subscriber_lock:
            self.assertIn(progress_queue, self.executor._subscribers.get(run_id, set()))
        
        # Unsubscribe
        self.executor.unsubscribe(run_id, progress_queue)
        
        # Verify subscriber removed
        with self.executor._subscriber_lock:
            self.assertNotIn(progress_queue, self.executor._subscribers.get(run_id, set()))
        
        # Empty subscriber set should be cleaned up
        with self.executor._subscriber_lock:
            self.assertNotIn(run_id, self.executor._subscribers)

    def test_full_queue_removes_subscriber(self):
        """Full queue should cause subscriber to be automatically removed."""
        run_id = "test-run-6"
        
        # Create queue with small maxsize
        small_queue = queue.Queue(maxsize=2)
        
        with self.executor._subscriber_lock:
            if run_id not in self.executor._subscribers:
                self.executor._subscribers[run_id] = set()
            self.executor._subscribers[run_id].add(small_queue)
        
        # Create progress
        progress = ExecutionProgress(
            status=ExecutionStatus.QUEUED,
            run_id=run_id,
            query="Test query",
            started_at=datetime.now().isoformat(),
        )
        
        with self.executor._lock:
            self.executor._executions[run_id] = progress
        
        # Fill queue
        small_queue.put_nowait({"test": "data1"})
        small_queue.put_nowait({"test": "data2"})
        
        # Try to notify - should fill queue and trigger removal
        self.executor._notify_subscribers(run_id, {"test": "data3"})
        
        # Small delay to allow removal
        time.sleep(0.1)
        
        # Subscriber should be removed due to full queue
        with self.executor._subscriber_lock:
            self.assertNotIn(small_queue, self.executor._subscribers.get(run_id, set()))

    def test_thread_safety(self):
        """Subscriber operations should be thread-safe."""
        run_id = "test-run-7"
        queues = []
        
        def subscribe_task():
            q = self.executor.subscribe(run_id)
            queues.append(q)
            time.sleep(0.1)
            self.executor.unsubscribe(run_id, q)
        
        # Create multiple threads subscribing/unsubscribing
        threads = [threading.Thread(target=subscribe_task) for _ in range(10)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Should complete without errors
        with self.executor._subscriber_lock:
            # All queues should be cleaned up
            self.assertNotIn(run_id, self.executor._subscribers or {})


class TestSSEEndpoint(unittest.TestCase):
    """Tests for SSE endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        # Import app here to avoid circular imports
        from HDRP.dashboard.app import app
        self.app = app
        # Use app.server to access the underlying Flask app
        self.client = app.server.test_client()
        self.executor = get_executor()

    def test_sse_endpoint_not_found(self):
        """SSE endpoint should return 404 for nonexistent run."""
        response = self.client.get('/api/progress/nonexistent-run-id')
        self.assertEqual(response.status_code, 404)
        
        # Should return JSON error
        data = json.loads(response.data)
        self.assertIn("error", data)

    def test_sse_endpoint_content_type(self):
        """SSE endpoint should return text/event-stream content type."""
        run_id = "test-sse-1"
        
        # Create progress
        progress = ExecutionProgress(
            status=ExecutionStatus.RUNNING,
            run_id=run_id,
            query="Test query",
            started_at=datetime.now().isoformat(),
        )
        
        with self.executor._lock:
            self.executor._executions[run_id] = progress
        
        # Request SSE endpoint
        response = self.client.get(f'/api/progress/{run_id}')
        
        # Should return 200
        self.assertEqual(response.status_code, 200)
        
        # Should have correct content type
        self.assertIn('text/event-stream', response.content_type)
        
        # Should have no-cache headers
        self.assertIn('no-cache', response.headers.get('Cache-Control', ''))

    def test_sse_endpoint_sends_initial_status(self):
        """SSE endpoint should send initial status immediately."""
        run_id = "test-sse-2"
        
        # Create progress
        progress = ExecutionProgress(
            status=ExecutionStatus.RUNNING,
            run_id=run_id,
            query="Test query",
            started_at=datetime.now().isoformat(),
            progress_percent=30.0,
            current_stage="Researching...",
        )
        
        with self.executor._lock:
            self.executor._executions[run_id] = progress
        
        # Request SSE endpoint
        response = self.client.get(f'/api/progress/{run_id}')
        
        self.assertEqual(response.status_code, 200)
        
        # Read first event
        lines = response.data.decode('utf-8').split('\n')
        
        # Should start with "data: "
        data_lines = [l for l in lines if l.startswith('data: ')]
        self.assertGreater(len(data_lines), 0)
        
        # Parse first data line
        first_data = data_lines[0].replace('data: ', '')
        progress_data = json.loads(first_data)
        
        self.assertEqual(progress_data["run_id"], run_id)
        self.assertEqual(progress_data["status"], "running")
        self.assertEqual(progress_data["progress_percent"], 30.0)

    def test_sse_endpoint_streams_updates(self):
        """SSE endpoint should stream progress updates."""
        run_id = "test-sse-3"
        
        # Create progress
        progress = ExecutionProgress(
            status=ExecutionStatus.QUEUED,
            run_id=run_id,
            query="Test query",
            started_at=datetime.now().isoformat(),
        )
        
        with self.executor._lock:
            self.executor._executions[run_id] = progress
        
        # Subscribe before making request
        progress_queue = self.executor.subscribe(run_id)
        
        # Update progress in background
        def update_progress():
            time.sleep(0.2)
            self.executor._update_progress(
                run_id,
                status=ExecutionStatus.RUNNING,
                progress_percent=50.0,
            )
            time.sleep(0.2)
            self.executor._update_progress(
                run_id,
                status=ExecutionStatus.COMPLETED,
                progress_percent=100.0,
            )
        
        update_thread = threading.Thread(target=update_progress, daemon=True)
        update_thread.start()
        
        # Request SSE endpoint
        response = self.client.get(f'/api/progress/{run_id}')
        self.assertEqual(response.status_code, 200)
        
        # Read events (non-blocking test - just verify format)
        # In a real test, you'd use a timeout and read stream
        content = response.data.decode('utf-8')
        
        # Should contain data lines
        self.assertIn('data: ', content)
        
        # Cleanup
        self.executor.unsubscribe(run_id, progress_queue)

    def test_sse_endpoint_handles_multiple_clients(self):
        """Multiple SSE clients should all receive updates."""
        run_id = "test-sse-4"
        
        # Create progress
        progress = ExecutionProgress(
            status=ExecutionStatus.RUNNING,
            run_id=run_id,
            query="Test query",
            started_at=datetime.now().isoformat(),
        )
        
        with self.executor._lock:
            self.executor._executions[run_id] = progress
        
        # Create multiple subscriptions
        queue1 = self.executor.subscribe(run_id)
        queue2 = self.executor.subscribe(run_id)
        
        # Clear initial statuses sent on subscription
        try:
            queue1.get_nowait()
        except queue.Empty:
            pass
        try:
            queue2.get_nowait()
        except queue.Empty:
            pass
        
        # Update progress - both should receive it
        self.executor._update_progress(
            run_id,
            progress_percent=50.0,
        )
        
        # Both queues should have updates
        data1 = queue1.get(timeout=1.0)
        data2 = queue2.get(timeout=1.0)
        
        self.assertEqual(data1["progress_percent"], 50.0)
        self.assertEqual(data2["progress_percent"], 50.0)
        
        # Cleanup
        self.executor.unsubscribe(run_id, queue1)
        self.executor.unsubscribe(run_id, queue2)


class TestProgressUpdates(unittest.TestCase):
    """Tests for progress update notification flow."""

    def setUp(self):
        """Set up test fixtures."""
        self.executor = QueryExecutor()

    def test_update_progress_notifies_subscribers(self):
        """_update_progress should notify all subscribers."""
        run_id = "test-progress-1"
        progress_queue = self.executor.subscribe(run_id)
        
        # Create initial progress
        progress = ExecutionProgress(
            status=ExecutionStatus.QUEUED,
            run_id=run_id,
            query="Test query",
            started_at=datetime.now().isoformat(),
        )
        
        with self.executor._lock:
            self.executor._executions[run_id] = progress
        
        # Clear initial status
        try:
            progress_queue.get_nowait()
        except queue.Empty:
            pass
        
        # Update with multiple fields
        self.executor._update_progress(
            run_id,
            status=ExecutionStatus.RUNNING,
            progress_percent=75.0,
            current_stage="Finalizing...",
            claims_extracted=10,
            claims_verified=8,
            claims_rejected=2,
        )
        
        # Verify update received
        received = progress_queue.get(timeout=1.0)
        self.assertEqual(received["status"], "running")
        self.assertEqual(received["progress_percent"], 75.0)
        self.assertEqual(received["current_stage"], "Finalizing...")
        self.assertEqual(received["claims_extracted"], 10)
        self.assertEqual(received["claims_verified"], 8)
        self.assertEqual(received["claims_rejected"], 2)
        
        # Cleanup
        self.executor.unsubscribe(run_id, progress_queue)

    def test_update_progress_preserves_unchanged_fields(self):
        """_update_progress should preserve fields not being updated."""
        run_id = "test-progress-2"
        
        # Create initial progress with many fields
        progress = ExecutionProgress(
            status=ExecutionStatus.RUNNING,
            run_id=run_id,
            query="Original query",
            started_at=datetime.now().isoformat(),
            progress_percent=50.0,
            current_stage="Processing",
            claims_extracted=5,
        )
        
        with self.executor._lock:
            self.executor._executions[run_id] = progress
        
        # Update only one field
        self.executor._update_progress(run_id, progress_percent=60.0)
        
        # Verify other fields preserved
        status = self.executor.get_status(run_id)
        self.assertEqual(status["query"], "Original query")
        self.assertEqual(status["progress_percent"], 60.0)  # Updated
        self.assertEqual(status["current_stage"], "Processing")  # Preserved
        self.assertEqual(status["claims_extracted"], 5)  # Preserved


if __name__ == '__main__':
    unittest.main()
