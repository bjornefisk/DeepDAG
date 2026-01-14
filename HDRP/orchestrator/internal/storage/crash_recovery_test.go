package storage

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

// TestCrashRecovery simulates a crash and recovery scenario.
func TestCrashRecovery(t *testing.T) {
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "crash_recovery.db")
	os.Setenv("HDRP_DB_PATH", dbPath)
	defer os.Unsetenv("HDRP_DB_PATH")

	graphID := "crash-test-graph"

	// Phase 1: Initial execution (simulating what happens before crash)
	t.Log("Phase 1: Simulating execution before crash...")
	{
		store, err := NewSQLiteStorage()
		if err != nil {
			t.Fatalf("Failed to create storage: %v", err)
		}

		// Create initial graph
		graph := &GraphState{
			ID:     graphID,
			Status: "RUNNING",
			Metadata: map[string]string{
				"goal":       "Research quantum computing",
				"started_at": time.Now().Format(time.RFC3339),
			},
		}
		if err := store.SaveGraph(graph); err != nil {
			t.Fatalf("Failed to save graph: %v", err)
		}

		// Log graph creation
		store.LogMutation(graphID, MutationCreateGraph, &CreateGraphPayload{
			Graph: *graph,
		})

		// Add some nodes (researchers)
		nodes := []*NodeState{
			{
				NodeID:         "researcher-1",
				Type:           "researcher",
				Config:         map[string]string{"query": "quantum algorithms"},
				Status:         "RUNNING",
				RelevanceScore: 1.0,
				Depth:          0,
			},
			{
				NodeID:         "researcher-2",
				Type:           "researcher",
				Config:         map[string]string{"query": "quantum hardware"},
				Status:         "PENDING",
				RelevanceScore: 0.9,
				Depth:          0,
			},
			{
				NodeID:         "critic-1",
				Type:           "critic",
				Config:         map[string]string{"task": "verify claims"},
				Status:         "BLOCKED",
				RelevanceScore: 0.95,
				Depth:          1,
			},
		}

		for _, node := range nodes {
			if err := store.SaveNode(graphID, node); err != nil {
				t.Fatalf("Failed to save node %s: %v", node.NodeID, err)
			}
			store.LogMutation(graphID, MutationAddNode, &AddNodePayload{Node: *node})
		}

		// Add edges
		edges := []struct{ from, to string }{
			{"researcher-1", "critic-1"},
			{"researcher-2", "critic-1"},
		}

		for _, edge := range edges {
			if err := store.SaveEdge(graphID, edge.from, edge.to); err != nil {
				t.Fatalf("Failed to save edge: %v", err)
			}
			store.LogMutation(graphID, MutationAddEdge, &AddEdgePayload{
				From: edge.from,
				To:   edge.to,
			})
		}

		// Simulate some progress: researcher-1 completes
		store.UpdateNodeStatus(graphID, "researcher-1", "SUCCEEDED", 0, "")
		store.LogMutation(graphID, MutationUpdateNodeStatus, &UpdateNodeStatusPayload{
			NodeID:    "researcher-1",
			OldStatus: "RUNNING",
			NewStatus: "SUCCEEDED",
		})

		// researcher-2 starts
		store.UpdateNodeStatus(graphID, "researcher-2", "RUNNING", 0, "")
		store.LogMutation(graphID, MutationUpdateNodeStatus, &UpdateNodeStatusPayload{
			NodeID:    "researcher-2",
			OldStatus: "PENDING",
			NewStatus: "RUNNING",
		})

		t.Logf("Phase 1 complete. Graph has 3 nodes, 2 edges. Status: %s", graph.Status)
		t.Log("Simulating crash... (closing storage without cleanup)")

		// Close storage (simulates crash)
		store.Close()
	}

	// Phase 2: Recovery after crash
	t.Log("Phase 2: Recovering from crash...")
	{
		store, err := NewSQLiteStorage()
		if err != nil {
			t.Fatalf("Failed to create storage after crash: %v", err)
		}
		defer store.Close()

		// Attempt recovery
		recovered, err := store.RecoverGraph(graphID)
		if err != nil {
			t.Fatalf("Failed to recover graph: %v", err)
		}

		if recovered == nil {
			t.Fatal("Recovery returned nil graph")
		}

		// Verify graph state
		t.Logf("Successfully recovered graph: %s (status: %s)", recovered.Graph.ID, recovered.Graph.Status)

		if recovered.Graph.ID != graphID {
			t.Errorf("Graph ID mismatch: got %s, want %s", recovered.Graph.ID, graphID)
		}

		if recovered.Graph.Status != "RUNNING" {
			t.Errorf("Graph status mismatch: got %s, want RUNNING", recovered.Graph.Status)
		}

		// Verify nodes
		if len(recovered.Nodes) != 3 {
			t.Fatalf("Expected 3 nodes after recovery, got %d", len(recovered.Nodes))
		}

		// Check node statuses
		expectedStatuses := map[string]string{
			"researcher-1": "SUCCEEDED",
			"researcher-2": "RUNNING",
			"critic-1":     "BLOCKED",
		}

		for nodeID, expectedStatus := range expectedStatuses {
			node, exists := recovered.Nodes[nodeID]
			if !exists {
				t.Errorf("Node %s not found in recovered state", nodeID)
				continue
			}

			if node.Status != expectedStatus {
				t.Errorf("Node %s status mismatch: got %s, want %s", nodeID, node.Status, expectedStatus)
			}
		}

		// Verify edges
		if len(recovered.Edges) != 2 {
			t.Fatalf("Expected 2 edges after recovery, got %d", len(recovered.Edges))
		}

		edgeMap := make(map[string]bool)
		for _, edge := range recovered.Edges {
			edgeMap[edge.From+"->"+edge.To] = true
		}

		expectedEdges := []string{
			"researcher-1->critic-1",
			"researcher-2->critic-1",
		}

		for _, expectedEdge := range expectedEdges {
			if !edgeMap[expectedEdge] {
				t.Errorf("Expected edge %s not found in recovered state", expectedEdge)
			}
		}

		t.Log("Recovery verification complete! All state correctly restored.")
		t.Log("Testing continuation from checkpoint...")

		// Phase 3: Continue execution from recovered state
		// Simulate researcher-2 completing
		store.UpdateNodeStatus(graphID, "researcher-2", "SUCCEEDED", 0, "")
		store.LogMutation(graphID, MutationUpdateNodeStatus, &UpdateNodeStatusPayload{
			NodeID:    "researcher-2",
			OldStatus: "RUNNING",
			NewStatus: "SUCCEEDED",
		})

		// critic-1 can now start
		store.UpdateNodeStatus(graphID, "critic-1", "RUNNING", 0, "")
		store.LogMutation(graphID, MutationUpdateNodeStatus, &UpdateNodeStatusPayload{
			NodeID:    "critic-1",
			OldStatus: "BLOCKED",
			NewStatus: "RUNNING",
		})

		// Create a snapshot after some progress
		if err := store.CreateSnapshot(graphID); err != nil {
			t.Fatalf("Failed to create snapshot: %v", err)
		}

		t.Log("Snapshot created. Execution continued successfully from checkpoint!")

		// Verify snapshot exists
		snapshot, err := store.LoadSnapshot(graphID)
		if err != nil {
			t.Fatalf("Failed to load snapshot: %v", err)
		}

		if snapshot == nil {
			t.Error("Expected snapshot to exist")
		} else {
			t.Logf("Snapshot sequence number: %d", snapshot.SequenceNum)
		}
	}

	t.Log("✓ Crash recovery test passed!")
	t.Log("✓ System successfully resumed from checkpoint after simulated crash")
}

// TestWALPerformance benchmarks WAL write overhead.
func TestWALPerformance(t *testing.T) {
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "perf_test.db")
	os.Setenv("HDRP_DB_PATH", dbPath)
	defer os.Unsetenv("HDRP_DB_PATH")

	store, err := NewSQLiteStorage()
	if err != nil {
		t.Fatalf("Failed to create storage: %v", err)
	}
	defer store.Close()

	graphID := "perf-test"

	// Warm up
	for i := 0; i < 10; i++ {
		store.LogMutation(graphID, MutationUpdateNodeStatus, &UpdateNodeStatusPayload{
			NodeID:    "warmup",
			OldStatus: "PENDING",
			NewStatus: "RUNNING",
		})
	}

	// Benchmark WAL writes
	numWrites := 1000
	start := time.Now()

	for i := 0; i < numWrites; i++ {
		payload := &UpdateNodeStatusPayload{
			NodeID:    "node-1",
			OldStatus: "PENDING",
			NewStatus: "RUNNING",
		}
		if err := store.LogMutation(graphID, MutationUpdateNodeStatus, payload); err != nil {
			t.Fatalf("Failed to log mutation: %v", err)
		}
	}

	elapsed := time.Since(start)
	avgLatency := elapsed / time.Duration(numWrites)

	t.Logf("WAL Performance:")
	t.Logf("  Total mutations: %d", numWrites)
	t.Logf("  Total time: %v", elapsed)
	t.Logf("  Average latency: %v", avgLatency)
	t.Logf("  Throughput: %.2f mutations/sec", float64(numWrites)/elapsed.Seconds())

	// Target: <1ms average latency
	if avgLatency > time.Millisecond {
		t.Errorf("Average WAL latency too high: %v (target: <1ms)", avgLatency)
	} else {
		t.Logf("✓ WAL latency within target (<1ms)")
	}

	// Calculate overhead percentage
	// Baseline: in-memory map update ~100ns, so 1ms write = ~1000% overhead
	// But target is <5% overhead on total execution which includes RPC calls (100ms+)
	overheadPct := (avgLatency.Microseconds() * 100) / 100000 // assuming 100ms base latency
	t.Logf("  Estimated overhead on 100ms operation: ~%d%%", overheadPct)

	if overheadPct > 5 {
		t.Logf("Note: WAL overhead is %d%% (target: <5%% on full execution)", overheadPct)
	}
}
