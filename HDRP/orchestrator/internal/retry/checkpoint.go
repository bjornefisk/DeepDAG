package retry

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// NodeCheckpoint stores the retry state for a specific node execution.
type NodeCheckpoint struct {
	NodeID        string    `json:"node_id"`
	RunID         string    `json:"run_id"`
	AttemptNumber int       `json:"attempt_number"`
	LastError     string    `json:"last_error"`
	Timestamp     time.Time `json:"timestamp"`
}

// CheckpointStore defines the interface for checkpoint persistence.
type CheckpointStore interface {
	// Save stores a checkpoint for a node.
	Save(runID, nodeID string, attemptNumber int, err error) error
	
	// Load retrieves a checkpoint for a node.
	Load(runID, nodeID string) (*NodeCheckpoint, error)
	
	// Delete removes a checkpoint (called when node succeeds).
	Delete(runID, nodeID string) error
	
	// LoadAll retrieves all checkpoints for a run.
	LoadAll(runID string) ([]*NodeCheckpoint, error)
	
	// DeleteAll removes all checkpoints for a run.
	DeleteAll(runID string) error
}

// FileCheckpointStore implements CheckpointStore using the filesystem.
type FileCheckpointStore struct {
	baseDir string
	mu      sync.RWMutex
}

// NewFileCheckpointStore creates a new file-based checkpoint store.
func NewFileCheckpointStore(baseDir string) (*FileCheckpointStore, error) {
	if baseDir == "" {
		baseDir = "./checkpoints"
	}

	// Create base directory if it doesn't exist
	if err := os.MkdirAll(baseDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create checkpoint directory: %w", err)
	}

	return &FileCheckpointStore{
		baseDir: baseDir,
	}, nil
}

// Save stores a checkpoint for a node.
func (fcs *FileCheckpointStore) Save(runID, nodeID string, attemptNumber int, err error) error {
	fcs.mu.Lock()
	defer fcs.mu.Unlock()

	checkpoint := &NodeCheckpoint{
		NodeID:        nodeID,
		RunID:         runID,
		AttemptNumber: attemptNumber,
		LastError:     "",
		Timestamp:     time.Now(),
	}

	if err != nil {
		checkpoint.LastError = err.Error()
	}

	// Create run directory if it doesn't exist
	runDir := filepath.Join(fcs.baseDir, runID)
	if err := os.MkdirAll(runDir, 0755); err != nil {
		return fmt.Errorf("failed to create run checkpoint directory: %w", err)
	}

	// Write checkpoint file
	filePath := filepath.Join(runDir, fmt.Sprintf("%s.json", nodeID))
	data, err := json.MarshalIndent(checkpoint, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal checkpoint: %w", err)
	}

	if err := os.WriteFile(filePath, data, 0644); err != nil {
		return fmt.Errorf("failed to write checkpoint file: %w", err)
	}

	return nil
}

// Load retrieves a checkpoint for a node.
func (fcs *FileCheckpointStore) Load(runID, nodeID string) (*NodeCheckpoint, error) {
	fcs.mu.RLock()
	defer fcs.mu.RUnlock()

	filePath := filepath.Join(fcs.baseDir, runID, fmt.Sprintf("%s.json", nodeID))
	data, err := os.ReadFile(filePath)
	if err != nil {
		if os.IsNotExist(err) {
			// No checkpoint exists, return empty checkpoint
			return &NodeCheckpoint{
				NodeID:        nodeID,
				RunID:         runID,
				AttemptNumber: 0,
			}, nil
		}
		return nil, fmt.Errorf("failed to read checkpoint file: %w", err)
	}

	var checkpoint NodeCheckpoint
	if err := json.Unmarshal(data, &checkpoint); err != nil {
		return nil, fmt.Errorf("failed to unmarshal checkpoint: %w", err)
	}

	return &checkpoint, nil
}

// Delete removes a checkpoint (called when node succeeds).
func (fcs *FileCheckpointStore) Delete(runID, nodeID string) error {
	fcs.mu.Lock()
	defer fcs.mu.Unlock()

	filePath := filepath.Join(fcs.baseDir, runID, fmt.Sprintf("%s.json", nodeID))
	if err := os.Remove(filePath); err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("failed to delete checkpoint file: %w", err)
	}

	return nil
}

// LoadAll retrieves all checkpoints for a run.
func (fcs *FileCheckpointStore) LoadAll(runID string) ([]*NodeCheckpoint, error) {
	fcs.mu.RLock()
	defer fcs.mu.RUnlock()

	runDir := filepath.Join(fcs.baseDir, runID)
	entries, err := os.ReadDir(runDir)
	if err != nil {
		if os.IsNotExist(err) {
			return []*NodeCheckpoint{}, nil
		}
		return nil, fmt.Errorf("failed to read checkpoint directory: %w", err)
	}

	var checkpoints []*NodeCheckpoint
	for _, entry := range entries {
		if entry.IsDir() || filepath.Ext(entry.Name()) != ".json" {
			continue
		}

		filePath := filepath.Join(runDir, entry.Name())
		data, err := os.ReadFile(filePath)
		if err != nil {
			continue // Skip files we can't read
		}

		var checkpoint NodeCheckpoint
		if err := json.Unmarshal(data, &checkpoint); err != nil {
			continue // Skip malformed files
		}

		checkpoints = append(checkpoints, &checkpoint)
	}

	return checkpoints, nil
}

// DeleteAll removes all checkpoints for a run.
func (fcs *FileCheckpointStore) DeleteAll(runID string) error {
	fcs.mu.Lock()
	defer fcs.mu.Unlock()

	runDir := filepath.Join(fcs.baseDir, runID)
	if err := os.RemoveAll(runDir); err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("failed to delete checkpoint directory: %w", err)
	}

	return nil
}

// InMemoryCheckpointStore implements CheckpointStore in memory (for testing).
type InMemoryCheckpointStore struct {
	mu          sync.RWMutex
	checkpoints map[string]map[string]*NodeCheckpoint // runID -> nodeID -> checkpoint
}

// NewInMemoryCheckpointStore creates a new in-memory checkpoint store.
func NewInMemoryCheckpointStore() *InMemoryCheckpointStore {
	return &InMemoryCheckpointStore{
		checkpoints: make(map[string]map[string]*NodeCheckpoint),
	}
}

// Save stores a checkpoint in memory.
func (imcs *InMemoryCheckpointStore) Save(runID, nodeID string, attemptNumber int, err error) error {
	imcs.mu.Lock()
	defer imcs.mu.Unlock()

	if imcs.checkpoints[runID] == nil {
		imcs.checkpoints[runID] = make(map[string]*NodeCheckpoint)
	}

	checkpoint := &NodeCheckpoint{
		NodeID:        nodeID,
		RunID:         runID,
		AttemptNumber: attemptNumber,
		LastError:     "",
		Timestamp:     time.Now(),
	}

	if err != nil {
		checkpoint.LastError = err.Error()
	}

	imcs.checkpoints[runID][nodeID] = checkpoint
	return nil
}

// Load retrieves a checkpoint from memory.
func (imcs *InMemoryCheckpointStore) Load(runID, nodeID string) (*NodeCheckpoint, error) {
	imcs.mu.RLock()
	defer imcs.mu.RUnlock()

	if runCheckpoints, exists := imcs.checkpoints[runID]; exists {
		if checkpoint, exists := runCheckpoints[nodeID]; exists {
			return checkpoint, nil
		}
	}

	return &NodeCheckpoint{
		NodeID:        nodeID,
		RunID:         runID,
		AttemptNumber: 0,
	}, nil
}

// Delete removes a checkpoint from memory.
func (imcs *InMemoryCheckpointStore) Delete(runID, nodeID string) error {
	imcs.mu.Lock()
	defer imcs.mu.Unlock()

	if runCheckpoints, exists := imcs.checkpoints[runID]; exists {
		delete(runCheckpoints, nodeID)
	}

	return nil
}

// LoadAll retrieves all checkpoints for a run from memory.
func (imcs *InMemoryCheckpointStore) LoadAll(runID string) ([]*NodeCheckpoint, error) {
	imcs.mu.RLock()
	defer imcs.mu.RUnlock()

	runCheckpoints, exists := imcs.checkpoints[runID]
	if !exists {
		return []*NodeCheckpoint{}, nil
	}

	var result []*NodeCheckpoint
	for _, cp := range runCheckpoints {
		result = append(result, cp)
	}

	return result, nil
}

// DeleteAll removes all checkpoints for a run from memory.
func (imcs *InMemoryCheckpointStore) DeleteAll(runID string) error {
	imcs.mu.Lock()
	defer imcs.mu.Unlock()

	delete(imcs.checkpoints, runID)
	return nil
}
