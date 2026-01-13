package concurrency

import (
	"context"
	"sync"
	"testing"
	"time"
)

func TestWorkerPool(t *testing.T) {
	t.Run("Basic Execution", func(t *testing.T) {
		wp := NewWorkerPool(2)
		if err := wp.Start(); err != nil {
			t.Fatalf("Failed to start worker pool: %v", err)
		}
		defer wp.Shutdown()

		executed := make(chan string, 3)
		tasks := []Task{
			{ID: "task1", Execute: func(ctx context.Context) error { executed <- "task1"; return nil }},
			{ID: "task2", Execute: func(ctx context.Context) error { executed <- "task2"; return nil }},
			{ID: "task3", Execute: func(ctx context.Context) error { executed <- "task3"; return nil }},
		}

		for _, task := range tasks {
			if err := wp.Submit(task); err != nil {
				t.Errorf("Failed to submit task %s: %v", task.ID, err)
			}
		}

		// Collect results
		results := make(map[string]bool)
		timeout := time.After(5 * time.Second)
		for i := 0; i < 3; i++ {
			select {
			case taskID := <-executed:
				results[taskID] = true
			case <-timeout:
				t.Fatal("Timeout waiting for task completion")
			}
		}

		if len(results) != 3 {
			t.Errorf("Expected 3 tasks to complete, got %d", len(results))
		}
	})

	t.Run("Concurrent Execution", func(t *testing.T) {
		wp := NewWorkerPool(5)
		if err := wp.Start(); err != nil {
			t.Fatalf("Failed to start worker pool: %v", err)
		}
		defer wp.Shutdown()

		var mu sync.Mutex
		concurrent := 0
		maxConcurrent := 0

		taskCount := 20
		done := make(chan bool, taskCount)

		for i := 0; i < taskCount; i++ {
			task := Task{
				ID: string(rune('A' + i)),
				Execute: func(ctx context.Context) error {
					mu.Lock()
					concurrent++
					if concurrent > maxConcurrent {
						maxConcurrent = concurrent
					}
					mu.Unlock()

					time.Sleep(10 * time.Millisecond)

					mu.Lock()
					concurrent--
					mu.Unlock()

					done <- true
					return nil
				},
			}

			if err := wp.Submit(task); err != nil {
				t.Errorf("Failed to submit task: %v", err)
			}
		}

		// Wait for all tasks
		timeout := time.After(5 * time.Second)
		for i := 0; i < taskCount; i++ {
			select {
			case <-done:
			case <-timeout:
				t.Fatal("Timeout waiting for tasks")
			}
		}

		if maxConcurrent > 5 {
			t.Errorf("Max concurrent workers exceeded: %d > 5", maxConcurrent)
		}
		if maxConcurrent < 2 {
			t.Errorf("Not enough concurrency: %d", maxConcurrent)
		}
	})
}

func TestRateLimiter(t *testing.T) {
	t.Run("Basic Limiting", func(t *testing.T) {
		rl := NewRateLimiter(3)

		// Acquire 3 tokens
		for i := 0; i < 3; i++ {
			if !rl.TryAcquire() {
				t.Errorf("Failed to acquire token %d", i)
			}
		}

		// 4th should fail
		if rl.TryAcquire() {
			t.Error("Should not acquire 4th token")
		}

		// Release one
		rl.Release()

		// Now should succeed
		if !rl.TryAcquire() {
			t.Error("Should acquire after release")
		}
	})

	t.Run("Context Cancellation", func(t *testing.T) {
		rl := NewRateLimiter(1)
		rl.TryAcquire() // Use up the token

		ctx, cancel := context.WithCancel(context.Background())
		cancel() // Cancel immediately

		err := rl.Acquire(ctx)
		if err == nil {
			t.Error("Expected error from cancelled context")
		}
	})

	t.Run("Concurrent Access", func(t *testing.T) {
		rl := NewRateLimiter(5)
		
		var wg sync.WaitGroup
		acquired := make(chan bool, 20)

		for i := 0; i < 20; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				ctx := context.Background()
				if err := rl.Acquire(ctx); err == nil {
					acquired <- true
					time.Sleep(10 * time.Millisecond)
					rl.Release()
				}
			}()
		}

		wg.Wait()
		close(acquired)

		count := 0
		for range acquired {
			count++
		}

		if count != 20 {
			t.Errorf("Expected 20 acquisitions, got %d", count)
		}
	})
}

func TestTopologicalSorter(t *testing.T) {
	t.Run("Simple Chain", func(t *testing.T) {
		nodes := []string{"A", "B", "C"}
		edges := [][2]string{{"A", "B"}, {"B", "C"}}
		
		ts := NewTopologicalSorter(nodes, edges)
		
		ready := ts.GetReadyNodes()
		if len(ready) != 1 || ready[0] != "A" {
			t.Errorf("Expected only A to be ready, got %v", ready)
		}

		newReady, _ := ts.MarkCompleted("A")
		if len(newReady) != 1 || newReady[0] != "B" {
			t.Errorf("Expected B to become ready, got %v", newReady)
		}
	})

	t.Run("Diamond DAG", func(t *testing.T) {
		// A -> B, A -> C, B -> D, C -> D
		nodes := []string{"A", "B", "C", "D"}
		edges := [][2]string{
			{"A", "B"},
			{"A", "C"},
			{"B", "D"},
			{"C", "D"},
		}

		ts := NewTopologicalSorter(nodes, edges)

		// Initially only A is ready
		ready := ts.GetReadyNodes()
		if len(ready) != 1 || ready[0] != "A" {
			t.Errorf("Expected A, got %v", ready)
		}

		// After A completes, both B and C should be ready
		newReady, _ := ts.MarkCompleted("A")
		if len(newReady) != 2 {
			t.Errorf("Expected B and C to be ready, got %v", newReady)
		}

		// Complete B
		ts.MarkCompleted("B")

		// D should not be ready yet (still waiting for C)
		ready = ts.GetReadyNodes()
		foundD := false
		for _, n := range ready {
			if n == "D" {
				foundD = true
			}
		}
		if foundD {
			t.Error("D should not be ready yet")
		}

		// Complete C
		newReady, _ = ts.MarkCompleted("C")
		if len(newReady) != 1 || newReady[0] != "D" {
			t.Errorf("Expected D to become ready, got %v", newReady)
		}
	})

	t.Run("Levels", func(t *testing.T) {
		nodes := []string{"A", "B", "C", "D"}
		edges := [][2]string{
			{"A", "B"},
			{"A", "C"},
			{"B", "D"},
			{"C", "D"},
		}

		ts := NewTopologicalSorter(nodes, edges)
		levels, err := ts.GetLevels()
		if err != nil {
			t.Fatalf("GetLevels failed: %v", err)
		}

		if len(levels) != 3 {
			t.Errorf("Expected 3 levels, got %d", len(levels))
		}

		// Level 0: A
		if len(levels[0]) != 1 || levels[0][0] != "A" {
			t.Errorf("Level 0 should be [A], got %v", levels[0])
		}

		// Level 1: B, C
		if len(levels[1]) != 2 {
			t.Errorf("Level 1 should have 2 nodes, got %v", levels[1])
		}

		// Level 2: D
		if len(levels[2]) != 1 || levels[2][0] != "D" {
			t.Errorf("Level 2 should be [D], got %v", levels[2])
		}
	})
}

func TestInMemoryLock(t *testing.T) {
	t.Run("Basic Acquire and Release", func(t *testing.T) {
		lock := NewInMemoryLock()
		ctx := context.Background()

		acquired, err := lock.AcquireNodeLock(ctx, "node1", 10*time.Second)
		if err != nil || !acquired {
			t.Error("Failed to acquire lock")
		}

		// Try to acquire again
		acquired, err = lock.AcquireNodeLock(ctx, "node1", 10*time.Second)
		if err != nil || acquired {
			t.Error("Should not acquire already-locked node")
		}

		// Release
		if err := lock.ReleaseNodeLock(ctx, "node1"); err != nil {
			t.Errorf("Failed to release lock: %v", err)
		}

		// Should be able to acquire again
		acquired, err = lock.AcquireNodeLock(ctx, "node1", 10*time.Second)
		if err != nil || !acquired {
			t.Error("Failed to re-acquire after release")
		}
	})

	t.Run("TTL Expiration", func(t *testing.T) {
		lock := NewInMemoryLock()
		ctx := context.Background()

		acquired, _ := lock.AcquireNodeLock(ctx, "node1", 100*time.Millisecond)
		if !acquired {
			t.Fatal("Failed to acquire lock")
		}

		// Wait for expiration
		time.Sleep(150 * time.Millisecond)

		// Should be able to acquire again
		acquired, _ = lock.AcquireNodeLock(ctx, "node1", 10*time.Second)
		if !acquired {
			t.Error("Lock should have expired")
		}
	})
}
