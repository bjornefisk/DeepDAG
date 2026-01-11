"""
Unit tests for HDRP logger module.

Tests JsonFormatter JSON output structure, ResearchLogger run ID generation,
event logging with payloads, and dynamic run ID updates.
"""

import json
import logging
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from HDRP.services.shared.logger import JsonFormatter, ResearchLogger, LOG_DIR


class TestJsonFormatter(unittest.TestCase):
    """Tests for JsonFormatter class."""

    def setUp(self):
        self.formatter = JsonFormatter()

    def test_format_outputs_valid_json(self):
        """Ensure format() outputs valid JSON."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test_event",
            args=(),
            exc_info=None,
        )
        record.component = "test_component"
        record.run_id = "test-run-123"
        record.event = "test_event"
        record.payload = {"key": "value"}

        output = self.formatter.format(record)
        
        # Should be valid JSON
        parsed = json.loads(output)
        self.assertIsInstance(parsed, dict)

    def test_format_includes_required_fields(self):
        """Verify all required fields are present in output."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="my_event",
            args=(),
            exc_info=None,
        )
        record.component = "researcher"
        record.run_id = "run-abc-123"
        record.event = "my_event"
        record.payload = {"data": 42}

        output = self.formatter.format(record)
        parsed = json.loads(output)

        # Check required fields
        self.assertIn("timestamp", parsed)
        self.assertIn("level", parsed)
        self.assertIn("component", parsed)
        self.assertIn("run_id", parsed)
        self.assertIn("event", parsed)
        self.assertIn("payload", parsed)

        # Check values
        self.assertEqual(parsed["level"], "INFO")
        self.assertEqual(parsed["component"], "researcher")
        self.assertEqual(parsed["run_id"], "run-abc-123")
        self.assertEqual(parsed["event"], "my_event")
        self.assertEqual(parsed["payload"], {"data": 42})

    def test_format_timestamp_is_iso_utc(self):
        """Verify timestamp is ISO format with Z suffix."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="event",
            args=(),
            exc_info=None,
        )
        record.component = "test"
        record.run_id = "run-1"
        record.event = "event"
        record.payload = {}

        output = self.formatter.format(record)
        parsed = json.loads(output)

        timestamp = parsed["timestamp"]
        # Should end with Z (UTC)
        self.assertTrue(timestamp.endswith("Z"))
        # Should be parseable as ISO format
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            self.fail("Timestamp is not valid ISO format")

    def test_format_uses_defaults_for_missing_attributes(self):
        """Verify defaults when record lacks custom attributes."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="fallback_message",
            args=(),
            exc_info=None,
        )
        # Don't set custom attributes

        output = self.formatter.format(record)
        parsed = json.loads(output)

        # Should use defaults
        self.assertEqual(parsed["component"], "unknown")
        self.assertEqual(parsed["run_id"], "unknown")
        self.assertEqual(parsed["event"], "fallback_message")  # Falls back to msg
        self.assertEqual(parsed["payload"], {})

    def test_format_handles_complex_payload(self):
        """Verify complex nested payloads are serialized correctly."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="complex_event",
            args=(),
            exc_info=None,
        )
        record.component = "critic"
        record.run_id = "run-complex"
        record.event = "complex_event"
        record.payload = {
            "claims": [
                {"id": "c1", "text": "claim one"},
                {"id": "c2", "text": "claim two"},
            ],
            "stats": {
                "total": 10,
                "verified": 8,
                "nested": {"deep": True}
            }
        }

        output = self.formatter.format(record)
        parsed = json.loads(output)

        self.assertEqual(len(parsed["payload"]["claims"]), 2)
        self.assertEqual(parsed["payload"]["stats"]["verified"], 8)
        self.assertTrue(parsed["payload"]["stats"]["nested"]["deep"])


class TestResearchLogger(unittest.TestCase):
    """Tests for ResearchLogger class."""

    def setUp(self):
        # Clear any existing handlers to avoid test interference
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

    @patch('HDRP.services.shared.logger.os.makedirs')
    @patch('HDRP.services.shared.logger.logging.FileHandler')
    def test_init_generates_run_id_when_not_provided(self, mock_file_handler, mock_makedirs):
        """Verify run_id is auto-generated when not provided."""
        mock_file_handler.return_value = MagicMock()
        
        logger = ResearchLogger("test_component")
        
        # Should have a UUID-style run_id
        self.assertIsNotNone(logger.run_id)
        self.assertIsInstance(logger.run_id, str)
        # UUID format check (8-4-4-4-12 characters)
        parts = logger.run_id.split("-")
        self.assertEqual(len(parts), 5)

    @patch('HDRP.services.shared.logger.os.makedirs')
    @patch('HDRP.services.shared.logger.logging.FileHandler')
    def test_init_uses_provided_run_id(self, mock_file_handler, mock_makedirs):
        """Verify provided run_id is used."""
        mock_file_handler.return_value = MagicMock()
        
        logger = ResearchLogger("test_component", run_id="my-custom-run-id")
        
        self.assertEqual(logger.run_id, "my-custom-run-id")

    @patch('HDRP.services.shared.logger.os.makedirs')
    @patch('HDRP.services.shared.logger.logging.FileHandler')
    def test_init_sets_component_name(self, mock_file_handler, mock_makedirs):
        """Verify component name is stored correctly."""
        mock_file_handler.return_value = MagicMock()
        
        logger = ResearchLogger("my_component", run_id="run-123")
        
        self.assertEqual(logger.component, "my_component")

    @patch('HDRP.services.shared.logger.os.makedirs')
    @patch('HDRP.services.shared.logger.logging.FileHandler')
    def test_init_creates_log_directory(self, mock_file_handler, mock_makedirs):
        """Verify log directory is created if needed."""
        mock_file_handler.return_value = MagicMock()
        
        # Clear handlers so initialization happens
        logger_name = f"HDRP.test_init_creates_log_dir_{id(self)}"
        test_logger = logging.getLogger(logger_name)
        test_logger.handlers.clear()
        
        with patch.object(logging, 'getLogger', return_value=test_logger):
            logger = ResearchLogger("test_comp", run_id="run-dir-test")
        
        mock_makedirs.assert_called_with(LOG_DIR, exist_ok=True)

    @patch('HDRP.services.shared.logger.os.makedirs')
    @patch('HDRP.services.shared.logger.logging.FileHandler')
    def test_log_with_payload(self, mock_file_handler, mock_makedirs):
        """Verify log() passes payload correctly."""
        mock_handler = MagicMock()
        mock_file_handler.return_value = mock_handler
        
        # Create a fresh logger
        logger_name = f"HDRP.test_log_payload_{id(self)}"
        test_logger = logging.getLogger(logger_name)
        test_logger.handlers.clear()
        
        with patch.object(logging, 'getLogger', return_value=test_logger):
            research_logger = ResearchLogger("test_comp", run_id="run-log-test")
        
        # Log an event
        research_logger.log("test_event", {"key": "value", "count": 42})
        
        # Verify handler was called
        mock_handler.emit.assert_called()

    @patch('HDRP.services.shared.logger.os.makedirs')
    @patch('HDRP.services.shared.logger.logging.FileHandler')
    def test_log_with_none_payload(self, mock_file_handler, mock_makedirs):
        """Verify log() handles None payload gracefully."""
        mock_handler = MagicMock()
        mock_file_handler.return_value = mock_handler
        
        logger_name = f"HDRP.test_none_payload_{id(self)}"
        test_logger = logging.getLogger(logger_name)
        test_logger.handlers.clear()
        
        with patch.object(logging, 'getLogger', return_value=test_logger):
            research_logger = ResearchLogger("test_comp", run_id="run-none")
        
        # Should not raise
        research_logger.log("event_no_payload")
        research_logger.log("event_explicit_none", None)

    def test_set_run_id_updates_run_id(self):
        """Verify set_run_id() updates the run_id."""
        with patch('HDRP.services.shared.logger.os.makedirs'):
            with patch('HDRP.services.shared.logger.logging.FileHandler') as mock_fh:
                mock_fh.return_value = MagicMock()
                
                logger = ResearchLogger("test_comp", run_id="original-id")
                self.assertEqual(logger.run_id, "original-id")
                
                logger.set_run_id("new-run-id")
                self.assertEqual(logger.run_id, "new-run-id")

    def test_set_run_id_affects_subsequent_logs(self):
        """Verify set_run_id() affects future log calls."""
        with patch('HDRP.services.shared.logger.os.makedirs'):
            with patch('HDRP.services.shared.logger.logging.FileHandler') as mock_fh:
                mock_handler = MagicMock()
                mock_fh.return_value = mock_handler
                
                logger_name = f"HDRP.test_set_run_id_{id(self)}"
                test_logger = logging.getLogger(logger_name)
                test_logger.handlers.clear()
                
                with patch.object(logging, 'getLogger', return_value=test_logger):
                    research_logger = ResearchLogger("comp", run_id="old-id")
                
                research_logger.set_run_id("updated-id")
                
                # Run_id should be updated
                self.assertEqual(research_logger.run_id, "updated-id")


class TestResearchLoggerIntegration(unittest.TestCase):
    """Integration tests that write actual log files."""

    def test_log_writes_to_file(self):
        """Verify logs are actually written to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Patch LOG_DIR to use temp directory
            with patch('HDRP.services.shared.logger.LOG_DIR', tmpdir):
                # Create a unique logger name to avoid handler reuse
                logger_name = f"HDRP.integration_test_{id(self)}"
                test_logger = logging.getLogger(logger_name)
                test_logger.handlers.clear()
                
                with patch.object(logging, 'getLogger', return_value=test_logger):
                    research_logger = ResearchLogger("integration_comp", run_id="int-test-run")
                
                # Log some events
                research_logger.log("event_one", {"data": "first"})
                research_logger.log("event_two", {"data": "second"})
                
                # Check the log file exists
                log_file = os.path.join(tmpdir, "int-test-run.jsonl")
                self.assertTrue(os.path.exists(log_file))
                
                # Read and verify contents
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                
                # Should have 2 lines
                self.assertEqual(len(lines), 2)
                
                # Each line should be valid JSON
                for line in lines:
                    parsed = json.loads(line)
                    self.assertIn("timestamp", parsed)
                    self.assertIn("event", parsed)


if __name__ == "__main__":
    unittest.main()

