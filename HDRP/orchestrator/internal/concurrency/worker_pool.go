package concurrency

import (
	"context"
	"fmt"
	"sync"
)

// Task represents a unit of work to be executed by the worker pool.
type Task struct {
	ID      string
	Execute func(ctx context.Context) error
}

// WorkerPool manages a pool of goroutines for concurrent task execution.
type WorkerPool struct {
	maxWorkers   int
	taskQueue    chan Task
	resultQueue  chan TaskResult
	wg           sync.WaitGroup
	ctx          context.Context
	cancel       context.CancelFunc
	started      bool
	mu           sync.Mutex
}

// TaskResult contains the outcome of a task execution.
type TaskResult struct {
	TaskID string
	Error  error
}

// NewWorkerPool creates a worker pool with the specified number of workers.
func NewWorkerPool(maxWorkers int) *WorkerPool {
	if maxWorkers <= 0 {
		maxWorkers = 1
	}

	ctx, cancel := context.WithCancel(context.Background())
	
	return &WorkerPool{
		maxWorkers:  maxWorkers,
		taskQueue:   make(chan Task, maxWorkers*2), // Buffered to reduce blocking
		resultQueue: make(chan TaskResult, maxWorkers*2),
		ctx:         ctx,
		cancel:      cancel,
	}
}

// Start initializes the worker goroutines.
func (wp *WorkerPool) Start() error {
	wp.mu.Lock()
	defer wp.mu.Unlock()

	if wp.started {
		return fmt.Errorf("worker pool already started")
	}

	for i := 0; i < wp.maxWorkers; i++ {
		wp.wg.Add(1)
		go wp.worker(i)
	}

	wp.started = true
	return nil
}

// worker is the goroutine that processes tasks from the queue.
func (wp *WorkerPool) worker(id int) {
	defer wp.wg.Done()

	for {
		select {
		case <-wp.ctx.Done():
			return
		case task, ok := <-wp.taskQueue:
			if !ok {
				return
			}

			// Execute the task
			err := task.Execute(wp.ctx)
			
			// Send result
			select {
			case wp.resultQueue <- TaskResult{TaskID: task.ID, Error: err}:
			case <-wp.ctx.Done():
				return
			}
		}
	}
}

// Submit adds a task to the worker pool queue.
// Returns an error if the pool is not started or has been shut down.
func (wp *WorkerPool) Submit(task Task) error {
	wp.mu.Lock()
	if !wp.started {
		wp.mu.Unlock()
		return fmt.Errorf("worker pool not started")
	}
	wp.mu.Unlock()

	select {
	case wp.taskQueue <- task:
		return nil
	case <-wp.ctx.Done():
		return fmt.Errorf("worker pool shut down")
	}
}

// Results returns the result channel for task completion notifications.
func (wp *WorkerPool) Results() <-chan TaskResult {
	return wp.resultQueue
}

// Shutdown gracefully stops the worker pool.
// It waits for all in-flight tasks to complete.
func (wp *WorkerPool) Shutdown() {
	wp.mu.Lock()
	if !wp.started {
		wp.mu.Unlock()
		return
	}
	wp.mu.Unlock()

	close(wp.taskQueue)
	wp.wg.Wait()
	wp.cancel()
	close(wp.resultQueue)
}

// ShutdownNow immediately stops the worker pool without waiting for tasks.
func (wp *WorkerPool) ShutdownNow() {
	wp.cancel()
	close(wp.taskQueue)
	close(wp.resultQueue)
}
