# DAG Persistent Storage

This package implements durable storage for DAG state with write-ahead logging (WAL) for crash recovery.

## Overview

The storage layer provides:
- **SQLite-backed persistence** - Single-instance embedded database
- **Write-Ahead Logging (WAL)** - All mutations logged for crash recovery  
- **State snapshots** - Periodic snapshots for fast recovery
- **Automatic recovery** - Resume from last checkpoint on restart

## Architecture

```
┌─────────────────┐
│   DAG Executor  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   DAG Graph     │◄──── In-memory state
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Storage Layer   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│          SQLite Database            │
├─────────────────────────────────────┤
│  Tables:                            │
│  • graphs      - Graph metadata     │
│  • nodes       - Node state         │
│  • edges       - Dependencies       │
│  • wal_log     - Mutation log       │
│  • snapshots   - State snapshots    │
└─────────────────────────────────────┘
```

## Usage

### Initialize Storage

```go
import "hdrp/internal/storage"

// Storage is initialized automatically by DAGExecutor
executor := NewDAGExecutor(clients, maxWorkers)
// Storage is at ./data/orchestrator.db by default
```

### Configure Database Path

```bash
# Set custom database location
export HDRP_DB_PATH=/path/to/custom/location/db.sqlite

# Run orchestrator
./orchestrator
```

### Recover from Crash

```go
// Check for interrupted graphs on startup
graphID := "some-graph-id"

graph, err := executor.RecoverGraph(graphID)
if err != nil {
    log.Printf("No recovery needed or failed: %v", err)
} else {
    // Resume execution from checkpoint
    result, err := executor.Execute(ctx, graph, runID)
}
```

### Manual Operations

```go
store, err := storage.NewSQLiteStorage()
if err != nil {
    log.Fatal(err)
}
defer store.Close()

// Load graph state
graphState, err := store.LoadGraph("graph-123")

// Get nodes
nodes, err := store.LoadNodes("graph-123")

// Recover with WAL replay
recovered, err := store.RecoverGraph("graph-123")
```

## Write-Ahead Log (WAL)

Every mutation is logged before being applied:

1. **Graph creation** - Initial graph state
2. **Status changes** - Node and graph status transitions
3. **Node additions** - Dynamic graph expansion
4. **Edge additions** - New dependencies

### Mutation Types

| Type | Description |
|------|-------------|
| `CREATE_GRAPH` | New graph created |
| `UPDATE_GRAPH_STATUS` | Graph status changed |
| `ADD_NODE` | Node added to graph |
| `UPDATE_NODE_STATUS` | Node status changed |
| `ADD_EDGE` | Dependency added |
| `SIGNAL_RECEIVED` | External signal logged |

## Recovery Process

1. **Load latest snapshot** (if exists)
2. **Replay unreplayed WAL entries** since snapshot
3. **Reconstruct in-memory state**
4. **Mark WAL entries as replayed**
5. **Resume execution**

### Snapshot Strategy

- Snapshots created every **100 status transitions**
- Old WAL entries cleaned up after snapshot
- Keeps last 100 entries for safety

## Performance

### WAL Overhead

Target: **<5% latency increase** on total execution

- WAL write: ~0.5-1ms average
- Node execution: 100ms-10s (RPC calls)
- **Actual overhead: <1%** on typical workloads

### Optimization

- Connection pooling (10 max connections)
- SQLite WAL mode for concurrent reads
- Batch writes in transactions
- Async cleanup of old entries

## Database Schema

### Graphs Table

```sql
CREATE TABLE graphs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    metadata TEXT,  -- JSON
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Nodes Table

```sql
CREATE TABLE nodes (
    graph_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    type TEXT NOT NULL,
    config TEXT,  -- JSON
    status TEXT NOT NULL,
    relevance_score REAL,
    depth INTEGER,
    retry_count INTEGER,
    last_error TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    PRIMARY KEY (graph_id, node_id),
    FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE
);
```

### WAL Log Table

```sql
CREATE TABLE wal_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    graph_id TEXT NOT NULL,
    mutation_type TEXT NOT NULL,
    payload TEXT NOT NULL,  -- JSON
    sequence_num INTEGER NOT NULL,
    created_at TIMESTAMP,
    replayed BOOLEAN DEFAULT 0
);
```

## Testing

```bash
# Run all storage tests
go test ./internal/storage/... -v

# Run crash recovery test
go test ./internal/storage/... -v -run TestCrashRecovery

# Run performance benchmark
go test ./internal/storage/... -v -run TestWALPerformance

# Check for race conditions
go test ./internal/storage/... -race
```

## Troubleshooting

### Database Locked

```
Error: database is locked
```

**Solution**: Ensure only one orchestrator instance is running. SQLite supports concurrent reads but single writer.

### Recovery Failed

```
Error: recovery failed: no stored state found
```

**Cause**: Graph was never persisted or database was deleted.

**Solution**: Start new execution instead of recovery.

### High WAL Size

If `wal_log` table grows large:

```sql
-- Check WAL size
SELECT COUNT(*) FROM wal_log WHERE replayed = 0;

-- Manual cleanup (if needed)
DELETE FROM wal_log WHERE replayed = 1 AND sequence_num < (
    SELECT sequence_num FROM snapshots WHERE graph_id = 'your-graph'
);
```

## Migration from In-Memory

Existing in-memory graphs will be lost on first startup with persistence enabled. To preserve state:

1. Complete all in-flight executions
2. Upgrade to persistent version
3. New executions will be durable

## Future Enhancements

- [ ] PostgreSQL backend for multi-instance deployments
- [ ] Configurable snapshot frequency
- [ ] Compressed snapshots for large graphs
- [ ] Metrics export (WAL size, recovery time)
- [ ] Graph archival after completion

## See Also

- [DAG Package](../dag/README.md)
- [Executor Package](../executor/README.md)
- [Implementation Plan](../../../../docs/implementation_plan.md)
