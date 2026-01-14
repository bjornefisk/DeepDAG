package storage

import (
	"encoding/json"
	"fmt"
	"log"
)

// RecoverGraph reconstructs a graph from its last snapshot and WAL replay.
// Returns the reconstructed graph state or nil if no recovery data exists.
func (s *SQLiteStorage) RecoverGraph(graphID string) (*RecoveredGraphState, error) {
	log.Printf("[Storage] Starting recovery for graph %s", graphID)

	// Try to load snapshot first
	snapshot, err := s.LoadSnapshot(graphID)
	if err != nil {
		return nil, fmt.Errorf("failed to load snapshot: %w", err)
	}

	var state *RecoveredGraphState
	var lastSeqNum int64

	if snapshot != nil {
		// Decode snapshot
		state, err = decodeSnapshot(snapshot.Data)
		if err != nil {
			return nil, fmt.Errorf("failed to decode snapshot: %w", err)
		}
		lastSeqNum = snapshot.SequenceNum
		log.Printf("[Storage] Loaded snapshot at sequence %d for graph %s", lastSeqNum, graphID)
	} else {
		// No snapshot, start from empty state
		state = &RecoveredGraphState{
			Graph: &GraphState{
				ID:       graphID,
				Metadata: make(map[string]string),
			},
			Nodes: make(map[string]*NodeState),
			Edges: []*EdgeState{},
		}
		lastSeqNum = 0
		log.Printf("[Storage] No snapshot found for graph %s, starting from empty state", graphID)
	}

	// Get unreplayed WAL entries
	walEntries, err := s.GetUnreplayedWAL(graphID)
	if err != nil {
		return nil, fmt.Errorf("failed to load WAL: %w", err)
	}

	if len(walEntries) == 0 {
		log.Printf("[Storage] No WAL entries to replay for graph %s", graphID)
		return state, nil
	}

	log.Printf("[Storage] Replaying %d WAL entries for graph %s", len(walEntries), graphID)

	// Replay WAL entries
	for _, entry := range walEntries {
		if err := applyWALEntry(state, entry); err != nil {
			return nil, fmt.Errorf("failed to apply WAL entry %d: %w", entry.ID, err)
		}
		lastSeqNum = entry.SequenceNum
	}

	// Mark entries as replayed
	if err := s.MarkWALReplayed(graphID, lastSeqNum); err != nil {
		log.Printf("[Storage] Warning: failed to mark WAL as replayed: %v", err)
	}

	log.Printf("[Storage] Successfully recovered graph %s up to sequence %d", graphID, lastSeqNum)
	return state, nil
}

// RecoveredGraphState represents a graph reconstructed from storage.
type RecoveredGraphState struct {
	Graph *GraphState
	Nodes map[string]*NodeState // nodeID -> NodeState
	Edges []*EdgeState
}

// applyWALEntry applies a single WAL mutation to the graph state.
func applyWALEntry(state *RecoveredGraphState, entry *WALEntry) error {
	switch entry.MutationType {
	case MutationCreateGraph:
		payload, ok := entry.Payload.(*CreateGraphPayload)
		if !ok {
			return fmt.Errorf("invalid payload type for CREATE_GRAPH")
		}
		state.Graph = &payload.Graph

	case MutationUpdateGraphStatus:
		payload, ok := entry.Payload.(*UpdateGraphStatusPayload)
		if !ok {
			return fmt.Errorf("invalid payload type for UPDATE_GRAPH_STATUS")
		}
		state.Graph.Status = payload.NewStatus

	case MutationAddNode:
		payload, ok := entry.Payload.(*AddNodePayload)
		if !ok {
			return fmt.Errorf("invalid payload type for ADD_NODE")
		}
		state.Nodes[payload.Node.NodeID] = &payload.Node

	case MutationUpdateNodeStatus:
		payload, ok := entry.Payload.(*UpdateNodeStatusPayload)
		if !ok {
			return fmt.Errorf("invalid payload type for UPDATE_NODE_STATUS")
		}
		node, exists := state.Nodes[payload.NodeID]
		if !exists {
			return fmt.Errorf("node %s not found for status update", payload.NodeID)
		}
		node.Status = payload.NewStatus
		node.RetryCount = payload.RetryCount
		node.LastError = payload.LastError

	case MutationAddEdge:
		payload, ok := entry.Payload.(*AddEdgePayload)
		if !ok {
			return fmt.Errorf("invalid payload type for ADD_EDGE")
		}
		state.Edges = append(state.Edges, &EdgeState{
			From: payload.From,
			To:   payload.To,
		})

	case MutationSignalReceived:
		// Signals are informational and don't modify core state during replay
		log.Printf("[Storage] Replayed signal: %s", entry.MutationType)

	default:
		return fmt.Errorf("unknown mutation type: %s", entry.MutationType)
	}

	return nil
}

// CreateSnapshot serializes the current graph state and saves it.
func (s *SQLiteStorage) CreateSnapshot(graphID string) error {
	// Load current state from database
	graph, err := s.LoadGraph(graphID)
	if err != nil {
		return fmt.Errorf("failed to load graph: %w", err)
	}

	nodes, err := s.LoadNodes(graphID)
	if err != nil {
		return fmt.Errorf("failed to load nodes: %w", err)
	}

	edges, err := s.LoadEdges(graphID)
	if err != nil {
		return fmt.Errorf("failed to load edges: %w", err)
	}

	// Build recovered state
	state := &RecoveredGraphState{
		Graph: graph,
		Nodes: make(map[string]*NodeState),
		Edges: edges,
	}

	for _, node := range nodes {
		state.Nodes[node.NodeID] = node
	}

	// Serialize
	data, err := json.Marshal(state)
	if err != nil {
		return fmt.Errorf("failed to serialize snapshot: %w", err)
	}

	// Get current sequence number
	s.mu.RLock()
	seqNum := s.seqNumbers[graphID] - 1 // Last written sequence
	s.mu.RUnlock()

	// Save snapshot
	if err := s.SaveSnapshot(graphID, seqNum, data); err != nil {
		return fmt.Errorf("failed to save snapshot: %w", err)
	}

	// Cleanup old WAL entries (keep last 100)
	cleanupBefore := seqNum - 100
	if cleanupBefore > 0 {
		if err := s.CleanupOldWAL(graphID, cleanupBefore); err != nil {
			log.Printf("[Storage] Warning: failed to cleanup old WAL: %v", err)
		}
	}

	return nil
}

// decodeSnapshot deserializes snapshot data.
func decodeSnapshot(data []byte) (*RecoveredGraphState, error) {
	var state RecoveredGraphState
	if err := json.Unmarshal(data, &state); err != nil {
		return nil, err
	}
	return &state, nil
}

// ShouldCreateSnapshot determines if a snapshot should be created based on WAL size.
// Creates snapshot every 100 transitions.
func (s *SQLiteStorage) ShouldCreateSnapshot(graphID string) (bool, error) {
	var unreplayedCount int
	err := s.db.QueryRow(`
		SELECT COUNT(*)
		FROM wal_log
		WHERE graph_id = ? AND replayed = 0
	`, graphID).Scan(&unreplayedCount)

	if err != nil {
		return false, err
	}

	return unreplayedCount >= 100, nil
}
