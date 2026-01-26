package logger

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestInitLoggerWritesLogFile(t *testing.T) {
	runID := "test-run-logger"
	logPath := filepath.Join("..", "..", "logs", runID+".jsonl")

	_ = os.Remove(logPath)

	if err := InitLogger(runID); err != nil {
		t.Fatalf("InitLogger failed: %v", err)
	}
	LogEvent(nil, runID, "orchestrator", "test_event", map[string]string{"msg": "ok"})
	Close()

	content, err := os.ReadFile(logPath)
	if err != nil {
		t.Fatalf("read log file: %v", err)
	}
	if !strings.Contains(string(content), runID) {
		t.Fatalf("expected run_id in log output")
	}

	_ = os.Remove(logPath)
}
