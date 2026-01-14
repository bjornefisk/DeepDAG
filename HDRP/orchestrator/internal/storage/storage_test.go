package storage

import (
	"os"
	"path/filepath"
	"testing"
)

func TestSQLiteStorage_BasicOperations(t *testing.T) {
	// Create temp directory for test database
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "test.db")
	os.Setenv("HDRP_DB_PATH", dbPath)
	defer os.Unsetenv("HDRP_DB_PATH")

	// Initialize storage
	store, err := NewSQLiteStorage()
	if err != nil {
		t.Fatalf("Failed to create storage: %v", err)
	}
	defer store.Close()

	// Test graph operations
	graphID := "test-graph-1"
	graph := &GraphState{
		ID:     graphID,
		Status: "CREATED",
		Metadata: map[string]string{
			"goal": "test research",
		},
	}

	// Save graph
	if err := store.SaveGraph(graph); err != nil {
		t.Fatalf("Failed to save graph: %v", err)
	}

	// Load graph
	loaded, err := store.LoadGraph(graphID)
	if err != nil {
		t.Fatalf("Failed to load graph: %v", err)
	}

	if loaded.ID != graph.ID || loaded.Status != graph.Status {
		t.Errorf("Loaded graph mismatch: got %+v, want %+v", loaded, graph)
	}

	// Test node operations
	node := &NodeState{
		NodeID: "node-1",
		Type:   "researcher",
		Config: map[string]string{
			"query": "test query",
		},
		Status:         "CREATED",
		RelevanceScore: 0.9,
		Depth:          0,
		RetryCount:     0,
	}

	if err := store.SaveNode(graphID, node); err != nil {
		t.Fatalf("Failed to save node: %v", err)
	}

	nodes, err := store.LoadNodes(graphID)
	if err != nil {
		t.Fatalf("Failed to load nodes: %v", err)
	}

	if len(nodes) != 1 {
		t.Fatalf("Expected 1 node, got %d", len(nodes))
	}

	if nodes[0].NodeID != node.NodeID {
		t.Errorf("Node ID mismatch: got %s, want %s", nodes[0].NodeID, node.NodeID)
	}

	// Test edge operations
	if err := store.SaveEdge(graphID, "node-1", "node-2"); err != nil {
		t.Fatalf("Failed to save edge: %v", err)
	}

	edges, err := store.LoadEdges(graphID)
	if err != nil {
		t.Fatalf("Failed to load edges: %v", err)
	}

	if len(edges) != 1 {
		t.Fatalf("Expected 1 edge, got %d", len(edges))
	}

	if edges[0].From != "node-1" || edges[0].To != "node-2" {
		t.Errorf("Edge mismatch: got %+v, want from=node-1 to=node-2", edges[0])
	}
}

func TestSQLiteStorage_WALOperations(t *testing.T) {
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "wal_test.db")
	os.Setenv("HDRP_DB_PATH", dbPath)
	defer os.Unsetenv("HDRP_DB_PATH")

	store, err := NewSQLiteStorage()
	if err != nil {
		t.Fatalf("Failed to create storage: %v", err)
	}
	defer store.Close()

	graphID := "wal-test-graph"

	// Log some mutations
	payload1 := &UpdateNodeStatusPayload{
		NodeID:    "node-1",
		OldStatus: "CREATED",
		NewStatus: "RUNNING",
	}
	if err := store.LogMutation(graphID, MutationUpdateNodeStatus, payload1); err != nil {
		t.Fatalf("Failed to log mutation: %v", err)
	}

	payload2 := &UpdateNodeStatusPayload{
		NodeID:    "node-1",
		OldStatus: "RUNNING",
		NewStatus: "SUCCEEDED",
	}
	if err := store.LogMutation(graphID, MutationUpdateNodeStatus, payload2); err != nil {
		t.Fatalf("Failed to log mutation: %v", err)
	}

	// Get unreplayed WAL
	entries, err := store.GetUnreplayedWAL(graphID)
	if err != nil {
		t.Fatalf("Failed to get WAL: %v", err)
	}

	if len(entries) != 2 {
		t.Fatalf("Expected 2 WAL entries, got %d", len(entries))
	}

	// Mark as replayed
	if err := store.MarkWALReplayed(graphID, entries[1].SequenceNum); err != nil {
		t.Fatalf("Failed to mark WAL replayed: %v", err)
	}

	// Verify no unreplayed entries
	entries, err = store.GetUnreplayedWAL(graphID)
	if err != nil {
		t.Fatalf("Failed to get WAL after replay: %v", err)
	}

	if len(entries) != 0 {
		t.Fatalf("Expected 0 unreplayed entries, got %d", len(entries))
	}
}

func TestSQLiteStorage_Snapshots(t *testing.T) {
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "snapshot_test.db")
	os.Setenv("HDRP_DB_PATH", dbPath)
	defer os.Unsetenv("HDRP_DB_PATH")

	store, err := NewSQLiteStorage()
	if err != nil {
		t.Fatalf("Failed to create storage: %v", err)
	}
	defer store.Close()

	graphID := "snapshot-test"

	// Create a graph
	graph := &GraphState{
		ID:       graphID,
		Status:   "RUNNING",
		Metadata: map[string]string{"test": "data"},
	}
	if err := store.SaveGraph(graph); err != nil {
		t.Fatalf("Failed to save graph: %v", err)
	}

	// Save snapshot
	snapshotData := []byte(`{"test":"snapshot"}`)
	if err := store.SaveSnapshot(graphID, 42, snapshotData); err != nil {
		t.Fatalf("Failed to save snapshot: %v", err)
	}

	// Load snapshot
	snapshot, err := store.LoadSnapshot(graphID)
	if err != nil {
		t.Fatalf("Failed to load snapshot: %v", err)
	}

	if snapshot == nil {
		t.Fatal("Expected snapshot, got nil")
	}

	if snapshot.SequenceNum != 42 {
		t.Errorf("Sequence number mismatch: got %d, want 42", snapshot.SequenceNum)
	}

	if string(snapshot.Data) != string(snapshotData) {
		t.Errorf("Snapshot data mismatch: got %s, want %s", string(snapshot.Data), string(snapshotData))
	}
}

func TestSQLiteStorage_Recovery(t *testing.T) {
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "recovery_test.db")
	os.Setenv("HDRP_DB_PATH", dbPath)
	defer os.Unsetenv("HDRP_DB_PATH")

	store, err := NewSQLiteStorage()
	if err != nil {
		t.Fatalf("Failed to create storage: %v", err)
	}

	graphID := "recovery-test"

	// Create initial graph state
	graph := &GraphState{
		ID:       graphID,
		Status:   "CREATED",
		Metadata: map[string]string{"goal": "test"},
	}
	if err := store.SaveGraph(graph); err != nil {
		t.Fatalf("Failed to save graph: %v", err)
	}

	// Add a node
	node := &NodeState{
		NodeID: "node-1",
		Type:   "researcher",
		Status: "CREATED",
		Config: map[string]string{"query": "test"},
	}
	if err := store.SaveNode(graphID, node); err != nil {
		t.Fatalf("Failed to save node: %v", err)
	}

	// Log some mutations
	store.LogMutation(graphID, MutationUpdateGraphStatus, &UpdateGraphStatusPayload{
		OldStatus: "CREATED",
		NewStatus: "RUNNING",
	})

	store.LogMutation(graphID, MutationUpdateNodeStatus, &UpdateNodeStatusPayload{
		NodeID:    "node-1",
		OldStatus: "CREATED",
		NewStatus: "RUNNING",
	})

	// Recover graph
	recovered, err := store.RecoverGraph(graphID)
	if err != nil {
		t.Fatalf("Failed to recover graph: %v", err)
	}

	if recovered == nil {
		t.Fatal("Expected recovered graph, got nil")
	}

	if recovered.Graph.Status != "RUNNING" {
		t.Errorf("Expected status RUNNING after WAL replay, got %s", recovered.Graph.Status)
	}

	if len(recovered.Nodes) != 1 {
		t.Fatalf("Expected 1 node, got %d", len(recovered.Nodes))
	}

	if recovered.Nodes["node-1"].Status != "RUNNING" {
		t.Errorf("Expected node status RUNNING, got %s", recovered.Nodes["node-1"].Status)
	}

	store.Close()
}

func TestSQLiteStorage_Transaction(t *testing.T) {
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "tx_test.db")
	os.Setenv("HDRP_DB_PATH", dbPath)
	defer os.Unsetenv("HDRP_DB_PATH")

	store, err := NewSQLiteStorage()
	if err != nil {
		t.Fatalf("Failed to create storage: %v", err)
	}
	defer store.Close()

	graphID := "tx-test"

	// Test successful transaction
	tx, err := store.BeginTx()
	if err != nil {
		t.Fatalf("Failed to begin transaction: %v", err)
	}

	graph := &GraphState{
		ID:       graphID,
		Status:   "CREATED",
		Metadata: make(map[string]string),
	}
	if err := tx.SaveGraph(graph); err != nil {
		t.Fatalf("Failed to save graph in transaction: %v", err)
	}

	if err := tx.Commit(); err != nil {
		t.Fatalf("Failed to commit transaction: %v", err)
	}

	// Verify graph was saved
	loaded, err := store.LoadGraph(graphID)
	if err != nil {
		t.Fatalf("Failed to load graph: %v", err)
	}

	if loaded.ID != graphID {
		t.Errorf("Graph ID mismatch: got %s, want %s", loaded.ID, graphID)
	}

	// Test rollback
	tx2, err := store.BeginTx()
	if err != nil {
		t.Fatalf("Failed to begin transaction: %v", err)
	}

	graph2 := &GraphState{
		ID:       "rollback-test",
		Status:   "CREATED",
		Metadata: make(map[string]string),
	}
	tx2.SaveGraph(graph2)
	tx2.Rollback()

	// Verify graph was not saved
	_, err = store.LoadGraph("rollback-test")
	if err == nil {
		t.Error("Expected error loading rolled-back graph, got nil")
	}
}
