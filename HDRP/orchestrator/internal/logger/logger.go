package logger

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"

	"github.com/google/uuid"
)

// LogSchema defines the structure for our research events
type LogSchema struct {
	Timestamp string      `json:"timestamp"`
	RunID     string      `json:"run_id"`
	Component string      `json:"component"` // orchestrator, principal, researcher, critic
	Event     string      `json:"event"`     // dag_update, claim_extracted, verification_result
	Payload   interface{} `json:"payload"`
}

var (
	currentLogger *slog.Logger
	logFile       *os.File
)

// InitLogger sets up a new logging session for a specific run
func InitLogger(runID string) error {
	if runID == "" {
		runID = uuid.New().String()
	}

	// Ensure logs directory exists
	logDir := "../../logs"
	if err := os.MkdirAll(logDir, 0755); err != nil {
		return fmt.Errorf("failed to create log dir: %w", err)
	}

	// Create a log file specifically for this run: HDRP/logs/<run_id>.jsonl
	path := filepath.Join(logDir, fmt.Sprintf("%s.jsonl", runID))
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return fmt.Errorf("failed to open log file: %w", err)
	}
	logFile = f

	// JSON Handler for structured output
	handler := slog.NewJSONHandler(f, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	})
	currentLogger = slog.New(handler)

	// Log the start of the session
	LogEvent(context.Background(), runID, "orchestrator", "session_start", map[string]string{
		"message": "Research session started",
	})

	return nil
}

// LogEvent writes a structured log entry
func LogEvent(ctx context.Context, runID, component, event string, payload interface{}) {
	if currentLogger == nil {
		// Fallback if not initialized
		handler := slog.NewJSONHandler(os.Stdout, nil)
		currentLogger = slog.New(handler)
	}

	// We use the attributes to match our schema
	currentLogger.Info(event,
		slog.String("run_id", runID),
		slog.String("component", component),
		slog.Any("payload", payload),
	)
}

// GenerateRunID helper
func GenerateRunID() string {
	return uuid.New().String()
}

// Close ensures the file is closed
func Close() {
	if logFile != nil {
		logFile.Close()
	}
}
