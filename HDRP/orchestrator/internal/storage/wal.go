package storage

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
)

// MutationType represents the type of mutation being logged.
type MutationType string

const (
	MutationCreateGraph      MutationType = "CREATE_GRAPH"
	MutationUpdateGraphStatus MutationType = "UPDATE_GRAPH_STATUS"
	MutationAddNode          MutationType = "ADD_NODE"
	MutationUpdateNodeStatus MutationType = "UPDATE_NODE_STATUS"
	MutationAddEdge          MutationType = "ADD_EDGE"
	MutationSignalReceived   MutationType = "SIGNAL_RECEIVED"
)

// WALEntry represents a single write-ahead log entry.
type WALEntry struct {
	ID            int64
	GraphID       string
	MutationType  MutationType
	Payload       interface{} // Mutation-specific data
	SequenceNum   int64
	Replayed      bool
}

// Mutation payload types
type CreateGraphPayload struct {
	Graph GraphState
}

type UpdateGraphStatusPayload struct {
	OldStatus string
	NewStatus string
}

type AddNodePayload struct {
	Node NodeState
}

type UpdateNodeStatusPayload struct {
	NodeID      string
	OldStatus   string
	NewStatus   string
	RetryCount  int
	LastError   string
}

type AddEdgePayload struct {
	From string
	To   string
}

type SignalReceivedPayload struct {
	SignalType string
	Source     string
	Payload    map[string]string
}

// AppendWAL adds a mutation entry to the write-ahead log.
func (s *SQLiteStorage) AppendWAL(entry *WALEntry) error {
	payloadJSON, err := json.Marshal(entry.Payload)
	if err != nil {
		return fmt.Errorf("failed to encode WAL payload: %w", err)
	}

	result, err := s.db.Exec(`
		INSERT INTO wal_log (graph_id, mutation_type, payload, sequence_num)
		VALUES (?, ?, ?, ?)
	`, entry.GraphID, entry.MutationType, string(payloadJSON), entry.SequenceNum)

	if err != nil {
		return err
	}

	id, err := result.LastInsertId()
	if err == nil {
		entry.ID = id
	}

	return nil
}

// GetUnreplayedWAL retrieves all unreplayed WAL entries for a graph in sequence order.
func (s *SQLiteStorage) GetUnreplayedWAL(graphID string) ([]*WALEntry, error) {
	rows, err := s.db.Query(`
		SELECT id, graph_id, mutation_type, payload, sequence_num
		FROM wal_log
		WHERE graph_id = ? AND replayed = 0
		ORDER BY sequence_num
	`, graphID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var entries []*WALEntry
	for rows.Next() {
		var entry WALEntry
		var payloadJSON string

		if err := rows.Scan(&entry.ID, &entry.GraphID, &entry.MutationType, &payloadJSON, &entry.SequenceNum); err != nil {
			return nil, err
		}

		// Decode payload based on mutation type
		entry.Payload, err = decodeWALPayload(entry.MutationType, payloadJSON)
		if err != nil {
			return nil, fmt.Errorf("failed to decode WAL entry %d: %w", entry.ID, err)
		}

		entries = append(entries, &entry)
	}

	return entries, rows.Err()
}

// MarkWALReplayed marks WAL entries as replayed up to a sequence number.
func (s *SQLiteStorage) MarkWALReplayed(graphID string, upToSeqNum int64) error {
	_, err := s.db.Exec(`
		UPDATE wal_log
		SET replayed = 1
		WHERE graph_id = ? AND sequence_num <= ?
	`, graphID, upToSeqNum)
	return err
}

// CleanupOldWAL removes replayed WAL entries before a sequence number.
func (s *SQLiteStorage) CleanupOldWAL(graphID string, beforeSeqNum int64) error {
	result, err := s.db.Exec(`
		DELETE FROM wal_log
		WHERE graph_id = ? AND sequence_num < ? AND replayed = 1
	`, graphID, beforeSeqNum)

	if err != nil {
		return err
	}

	rows, _ := result.RowsAffected()
	if rows > 0 {
		log.Printf("[Storage] Cleaned up %d old WAL entries for graph %s", rows, graphID)
	}

	return nil
}

// SaveSnapshot creates a state snapshot for fast recovery.
func (s *SQLiteStorage) SaveSnapshot(graphID string, seqNum int64, data []byte) error {
	_, err := s.db.Exec(`
		INSERT INTO snapshots (graph_id, sequence_num, snapshot_data)
		VALUES (?, ?, ?)
		ON CONFLICT(graph_id) DO UPDATE SET
			sequence_num = excluded.sequence_num,
			snapshot_data = excluded.snapshot_data,
			created_at = CURRENT_TIMESTAMP
	`, graphID, seqNum, data)

	if err == nil {
		log.Printf("[Storage] Saved snapshot for graph %s at sequence %d", graphID, seqNum)
	}

	return err
}

// LoadSnapshot retrieves the latest snapshot for a graph.
func (s *SQLiteStorage) LoadSnapshot(graphID string) (*Snapshot, error) {
	var snapshot Snapshot
	err := s.db.QueryRow(`
		SELECT graph_id, sequence_num, snapshot_data
		FROM snapshots
		WHERE graph_id = ?
	`, graphID).Scan(&snapshot.GraphID, &snapshot.SequenceNum, &snapshot.Data)

	if err == sql.ErrNoRows {
		return nil, nil // No snapshot exists
	}

	return &snapshot, err
}

// decodeWALPayload decodes the JSON payload based on mutation type.
func decodeWALPayload(mutationType MutationType, payloadJSON string) (interface{}, error) {
	var payload interface{}

	switch mutationType {
	case MutationCreateGraph:
		payload = &CreateGraphPayload{}
	case MutationUpdateGraphStatus:
		payload = &UpdateGraphStatusPayload{}
	case MutationAddNode:
		payload = &AddNodePayload{}
	case MutationUpdateNodeStatus:
		payload = &UpdateNodeStatusPayload{}
	case MutationAddEdge:
		payload = &AddEdgePayload{}
	case MutationSignalReceived:
		payload = &SignalReceivedPayload{}
	default:
		return nil, fmt.Errorf("unknown mutation type: %s", mutationType)
	}

	if err := json.Unmarshal([]byte(payloadJSON), payload); err != nil {
		return nil, err
	}

	return payload, nil
}

// LogMutation is a convenience method to log a mutation with automatic sequence numbering.
func (s *SQLiteStorage) LogMutation(graphID string, mutationType MutationType, payload interface{}) error {
	seqNum := s.getNextSeqNum(graphID)
	
	entry := &WALEntry{
		GraphID:      graphID,
		MutationType: mutationType,
		Payload:      payload,
		SequenceNum:  seqNum,
	}

	return s.AppendWAL(entry)
}
