package storage

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sync"

	_ "github.com/mattn/go-sqlite3"
)

// Storage defines the interface for DAG persistence operations.
type Storage interface {
	// Graph operations
	SaveGraph(graph *GraphState) error
	LoadGraph(graphID string) (*GraphState, error)
	UpdateGraphStatus(graphID string, status string) error
	DeleteGraph(graphID string) error

	// Node operations
	SaveNode(graphID string, node *NodeState) error
	LoadNodes(graphID string) ([]*NodeState, error)
	UpdateNodeStatus(graphID string, nodeID string, status string, retryCount int, lastError string) error

	// Edge operations
	SaveEdge(graphID string, from, to string) error
	LoadEdges(graphID string) ([]*EdgeState, error)

	// WAL operations
	AppendWAL(entry *WALEntry) error
	GetUnreplayedWAL(graphID string) ([]*WALEntry, error)
	MarkWALReplayed(graphID string, upToSeqNum int64) error
	LogMutation(graphID string, mutationType MutationType, payload interface{}) error

	// Snapshot operations
	SaveSnapshot(graphID string, seqNum int64, data []byte) error
	LoadSnapshot(graphID string) (*Snapshot, error)
	ShouldCreateSnapshot(graphID string) (bool, error)
	CreateSnapshot(graphID string) error

	// Recovery
	RecoverGraph(graphID string) (*RecoveredGraphState, error)

	// Cleanup
	CleanupOldWAL(graphID string, beforeSeqNum int64) error

	// Transaction support
	BeginTx() (Transaction, error)

	// Lifecycle
	Close() error
}

// Transaction provides transactional storage operations.
type Transaction interface {
	SaveGraph(graph *GraphState) error
	SaveNode(graphID string, node *NodeState) error
	SaveEdge(graphID string, from, to string) error
	AppendWAL(entry *WALEntry) error
	Commit() error
	Rollback() error
}

// GraphState represents persisted graph metadata.
type GraphState struct {
	ID       string
	Status   string
	Metadata map[string]string
}

// NodeState represents persisted node state.
type NodeState struct {
	NodeID         string
	Type           string
	Config         map[string]string
	Status         string
	RelevanceScore float64
	Depth          int
	RetryCount     int
	LastError      string
}

// EdgeState represents persisted edge.
type EdgeState struct {
	From string
	To   string
}

// Snapshot represents a state snapshot.
type Snapshot struct {
	GraphID     string
	SequenceNum int64
	Data        []byte
}

// SQLiteStorage implements Storage using SQLite.
type SQLiteStorage struct {
	db         *sql.DB
	mu         sync.RWMutex
	seqNumbers map[string]int64 // graph_id -> next sequence number
}

// NewSQLiteStorage creates a new SQLite-backed storage.
// dbPath can be set via HDRP_DB_PATH env var, defaults to ./data/orchestrator.db
func NewSQLiteStorage() (*SQLiteStorage, error) {
	dbPath := os.Getenv("HDRP_DB_PATH")
	if dbPath == "" {
		dbPath = "./data/orchestrator.db"
	}

	// Ensure directory exists
	dir := filepath.Dir(dbPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create data directory: %w", err)
	}

	// Open database with WAL mode for better concurrency
	db, err := sql.Open("sqlite3", dbPath+"?cache=shared&mode=rwc&_journal_mode=WAL")
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Set connection pool limits
	db.SetMaxOpenConns(10)
	db.SetMaxIdleConns(5)

	// Test connection
	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	// Initialize schema
	if err := InitSchema(db); err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to initialize schema: %w", err)
	}

	store := &SQLiteStorage{
		db:         db,
		seqNumbers: make(map[string]int64),
	}

	// Load current sequence numbers
	if err := store.loadSequenceNumbers(); err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to load sequence numbers: %w", err)
	}

	log.Printf("[Storage] SQLite storage initialized at %s", dbPath)
	return store, nil
}

func (s *SQLiteStorage) loadSequenceNumbers() error {
	rows, err := s.db.Query("SELECT graph_id, MAX(sequence_num) FROM wal_log GROUP BY graph_id")
	if err != nil {
		return err
	}
	defer rows.Close()

	for rows.Next() {
		var graphID string
		var maxSeq int64
		if err := rows.Scan(&graphID, &maxSeq); err != nil {
			return err
		}
		s.seqNumbers[graphID] = maxSeq + 1
	}

	return rows.Err()
}

func (s *SQLiteStorage) getNextSeqNum(graphID string) int64 {
	s.mu.Lock()
	defer s.mu.Unlock()

	seq := s.seqNumbers[graphID]
	s.seqNumbers[graphID] = seq + 1
	return seq
}

// SaveGraph persists a graph's metadata.
func (s *SQLiteStorage) SaveGraph(graph *GraphState) error {
	metadataJSON, err := json.Marshal(graph.Metadata)
	if err != nil {
		return fmt.Errorf("failed to encode metadata: %w", err)
	}

	_, err = s.db.Exec(`
		INSERT INTO graphs (id, status, metadata)
		VALUES (?, ?, ?)
		ON CONFLICT(id) DO UPDATE SET
			status = excluded.status,
			metadata = excluded.metadata,
			updated_at = CURRENT_TIMESTAMP
	`, graph.ID, graph.Status, string(metadataJSON))

	return err
}

// LoadGraph retrieves a graph's metadata.
func (s *SQLiteStorage) LoadGraph(graphID string) (*GraphState, error) {
	var graph GraphState
	var metadataJSON string

	err := s.db.QueryRow(`
		SELECT id, status, metadata
		FROM graphs
		WHERE id = ?
	`, graphID).Scan(&graph.ID, &graph.Status, &metadataJSON)

	if err != nil {
		return nil, err
	}

	if err := json.Unmarshal([]byte(metadataJSON), &graph.Metadata); err != nil {
		return nil, fmt.Errorf("failed to decode metadata: %w", err)
	}

	return &graph, nil
}

// UpdateGraphStatus updates only the graph's status.
func (s *SQLiteStorage) UpdateGraphStatus(graphID string, status string) error {
	_, err := s.db.Exec(`
		UPDATE graphs
		SET status = ?, updated_at = CURRENT_TIMESTAMP
		WHERE id = ?
	`, status, graphID)
	return err
}

// DeleteGraph removes a graph and all related data (cascading).
func (s *SQLiteStorage) DeleteGraph(graphID string) error {
	_, err := s.db.Exec("DELETE FROM graphs WHERE id = ?", graphID)
	return err
}

// SaveNode persists a node's state.
func (s *SQLiteStorage) SaveNode(graphID string, node *NodeState) error {
	configJSON, err := json.Marshal(node.Config)
	if err != nil {
		return fmt.Errorf("failed to encode config: %w", err)
	}

	_, err = s.db.Exec(`
		INSERT INTO nodes (graph_id, node_id, type, config, status, relevance_score, depth, retry_count, last_error)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(graph_id, node_id) DO UPDATE SET
			type = excluded.type,
			config = excluded.config,
			status = excluded.status,
			relevance_score = excluded.relevance_score,
			depth = excluded.depth,
			retry_count = excluded.retry_count,
			last_error = excluded.last_error,
			updated_at = CURRENT_TIMESTAMP
	`, graphID, node.NodeID, node.Type, string(configJSON), node.Status,
		node.RelevanceScore, node.Depth, node.RetryCount, node.LastError)

	return err
}

// LoadNodes retrieves all nodes for a graph.
func (s *SQLiteStorage) LoadNodes(graphID string) ([]*NodeState, error) {
	rows, err := s.db.Query(`
		SELECT node_id, type, config, status, relevance_score, depth, retry_count, last_error
		FROM nodes
		WHERE graph_id = ?
		ORDER BY created_at
	`, graphID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var nodes []*NodeState
	for rows.Next() {
		var node NodeState
		var configJSON string
		var lastError sql.NullString

		err := rows.Scan(&node.NodeID, &node.Type, &configJSON, &node.Status,
			&node.RelevanceScore, &node.Depth, &node.RetryCount, &lastError)
		if err != nil {
			return nil, err
		}

		if err := json.Unmarshal([]byte(configJSON), &node.Config); err != nil {
			return nil, fmt.Errorf("failed to decode config for node %s: %w", node.NodeID, err)
		}

		if lastError.Valid {
			node.LastError = lastError.String
		}

		nodes = append(nodes, &node)
	}

	return nodes, rows.Err()
}

// UpdateNodeStatus updates a node's status and retry information.
func (s *SQLiteStorage) UpdateNodeStatus(graphID string, nodeID string, status string, retryCount int, lastError string) error {
	_, err := s.db.Exec(`
		UPDATE nodes
		SET status = ?, retry_count = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
		WHERE graph_id = ? AND node_id = ?
	`, status, retryCount, lastError, graphID, nodeID)
	return err
}

// SaveEdge persists an edge.
func (s *SQLiteStorage) SaveEdge(graphID string, from, to string) error {
	_, err := s.db.Exec(`
		INSERT OR IGNORE INTO edges (graph_id, from_node, to_node)
		VALUES (?, ?, ?)
	`, graphID, from, to)
	return err
}

// LoadEdges retrieves all edges for a graph.
func (s *SQLiteStorage) LoadEdges(graphID string) ([]*EdgeState, error) {
	rows, err := s.db.Query(`
		SELECT from_node, to_node
		FROM edges
		WHERE graph_id = ?
	`, graphID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var edges []*EdgeState
	for rows.Next() {
		var edge EdgeState
		if err := rows.Scan(&edge.From, &edge.To); err != nil {
			return nil, err
		}
		edges = append(edges, &edge)
	}

	return edges, rows.Err()
}

// BeginTx starts a new transaction.
func (s *SQLiteStorage) BeginTx() (Transaction, error) {
	tx, err := s.db.Begin()
	if err != nil {
		return nil, err
	}
	return &sqliteTx{tx: tx, storage: s}, nil
}

// Close closes the database connection.
func (s *SQLiteStorage) Close() error {
	return s.db.Close()
}

// sqliteTx implements Transaction.
type sqliteTx struct {
	tx      *sql.Tx
	storage *SQLiteStorage
}

func (t *sqliteTx) SaveGraph(graph *GraphState) error {
	metadataJSON, err := json.Marshal(graph.Metadata)
	if err != nil {
		return fmt.Errorf("failed to encode metadata: %w", err)
	}

	_, err = t.tx.Exec(`
		INSERT INTO graphs (id, status, metadata)
		VALUES (?, ?, ?)
		ON CONFLICT(id) DO UPDATE SET
			status = excluded.status,
			metadata = excluded.metadata,
			updated_at = CURRENT_TIMESTAMP
	`, graph.ID, graph.Status, string(metadataJSON))

	return err
}

func (t *sqliteTx) SaveNode(graphID string, node *NodeState) error {
	configJSON, err := json.Marshal(node.Config)
	if err != nil {
		return fmt.Errorf("failed to encode config: %w", err)
	}

	_, err = t.tx.Exec(`
		INSERT INTO nodes (graph_id, node_id, type, config, status, relevance_score, depth, retry_count, last_error)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(graph_id, node_id) DO UPDATE SET
			type = excluded.type,
			config = excluded.config,
			status = excluded.status,
			relevance_score = excluded.relevance_score,
			depth = excluded.depth,
			retry_count = excluded.retry_count,
			last_error = excluded.last_error,
			updated_at = CURRENT_TIMESTAMP
	`, graphID, node.NodeID, node.Type, string(configJSON), node.Status,
		node.RelevanceScore, node.Depth, node.RetryCount, node.LastError)

	return err
}

func (t *sqliteTx) SaveEdge(graphID string, from, to string) error {
	_, err := t.tx.Exec(`
		INSERT OR IGNORE INTO edges (graph_id, from_node, to_node)
		VALUES (?, ?, ?)
	`, graphID, from, to)
	return err
}

func (t *sqliteTx) AppendWAL(entry *WALEntry) error {
	payloadJSON, err := json.Marshal(entry.Payload)
	if err != nil {
		return fmt.Errorf("failed to encode WAL payload: %w", err)
	}

	_, err = t.tx.Exec(`
		INSERT INTO wal_log (graph_id, mutation_type, payload, sequence_num)
		VALUES (?, ?, ?, ?)
	`, entry.GraphID, entry.MutationType, string(payloadJSON), entry.SequenceNum)

	return err
}

func (t *sqliteTx) Commit() error {
	return t.tx.Commit()
}

func (t *sqliteTx) Rollback() error {
	return t.tx.Rollback()
}
