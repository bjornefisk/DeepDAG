package storage

import (
	"database/sql"
	"fmt"
	"log"
)

const currentSchemaVersion = 1

// InitSchema creates all required tables and indexes.
// It's idempotent - safe to call multiple times.
func InitSchema(db *sql.DB) error {
	// Check current version
	version, err := getSchemaVersion(db)
	if err != nil {
		return fmt.Errorf("failed to get schema version: %w", err)
	}

	if version >= currentSchemaVersion {
		log.Printf("[Storage] Schema already at version %d, skipping initialization", version)
		return nil
	}

	log.Printf("[Storage] Initializing schema from version %d to %d", version, currentSchemaVersion)

	tx, err := db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// Create tables
	if err := createTables(tx); err != nil {
		return fmt.Errorf("failed to create tables: %w", err)
	}

	// Create indexes
	if err := createIndexes(tx); err != nil {
		return fmt.Errorf("failed to create indexes: %w", err)
	}

	// Update schema version
	if err := setSchemaVersion(tx, currentSchemaVersion); err != nil {
		return fmt.Errorf("failed to set schema version: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit schema initialization: %w", err)
	}

	log.Printf("[Storage] Schema initialized successfully to version %d", currentSchemaVersion)
	return nil
}

func createTables(tx *sql.Tx) error {
	// Schema version tracking table
	if _, err := tx.Exec(`
		CREATE TABLE IF NOT EXISTS schema_version (
			version INTEGER PRIMARY KEY,
			applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)
	`); err != nil {
		return fmt.Errorf("failed to create schema_version table: %w", err)
	}

	// Graphs table - stores graph metadata and status
	if _, err := tx.Exec(`
		CREATE TABLE IF NOT EXISTS graphs (
			id TEXT PRIMARY KEY,
			status TEXT NOT NULL,
			metadata TEXT,  -- JSON encoded map[string]string
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)
	`); err != nil {
		return fmt.Errorf("failed to create graphs table: %w", err)
	}

	// Nodes table - stores node state
	if _, err := tx.Exec(`
		CREATE TABLE IF NOT EXISTS nodes (
			graph_id TEXT NOT NULL,
			node_id TEXT NOT NULL,
			type TEXT NOT NULL,
			config TEXT,  -- JSON encoded map[string]string
			status TEXT NOT NULL,
			relevance_score REAL DEFAULT 0.0,
			depth INTEGER DEFAULT 0,
			retry_count INTEGER DEFAULT 0,
			last_error TEXT,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			PRIMARY KEY (graph_id, node_id),
			FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE
		)
	`); err != nil {
		return fmt.Errorf("failed to create nodes table: %w", err)
	}

	// Edges table - stores node dependencies
	if _, err := tx.Exec(`
		CREATE TABLE IF NOT EXISTS edges (
			graph_id TEXT NOT NULL,
			from_node TEXT NOT NULL,
			to_node TEXT NOT NULL,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			PRIMARY KEY (graph_id, from_node, to_node),
			FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE
		)
	`); err != nil {
		return fmt.Errorf("failed to create edges table: %w", err)
	}

	// WAL (Write-Ahead Log) table - logs all mutations for crash recovery
	if _, err := tx.Exec(`
		CREATE TABLE IF NOT EXISTS wal_log (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			graph_id TEXT NOT NULL,
			mutation_type TEXT NOT NULL,
			payload TEXT NOT NULL,  -- JSON encoded mutation data
			sequence_num INTEGER NOT NULL,  -- For ordering within a graph
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			replayed BOOLEAN DEFAULT 0
		)
	`); err != nil {
		return fmt.Errorf("failed to create wal_log table: %w", err)
	}

	// Snapshots table - periodic state snapshots for fast recovery
	if _, err := tx.Exec(`
		CREATE TABLE IF NOT EXISTS snapshots (
			graph_id TEXT PRIMARY KEY,
			sequence_num INTEGER NOT NULL,  -- Last WAL sequence included in snapshot
			snapshot_data TEXT NOT NULL,  -- JSON encoded full graph state
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE
		)
	`); err != nil {
		return fmt.Errorf("failed to create snapshots table: %w", err)
	}

	return nil
}

func createIndexes(tx *sql.Tx) error {
	indexes := []string{
		`CREATE INDEX IF NOT EXISTS idx_nodes_graph_status ON nodes(graph_id, status)`,
		`CREATE INDEX IF NOT EXISTS idx_edges_graph ON edges(graph_id)`,
		`CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(graph_id, from_node)`,
		`CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(graph_id, to_node)`,
		`CREATE INDEX IF NOT EXISTS idx_wal_graph_seq ON wal_log(graph_id, sequence_num)`,
		`CREATE INDEX IF NOT EXISTS idx_wal_replayed ON wal_log(replayed)`,
	}

	for _, idx := range indexes {
		if _, err := tx.Exec(idx); err != nil {
			return fmt.Errorf("failed to create index: %w", err)
		}
	}

	return nil
}

func getSchemaVersion(db *sql.DB) (int, error) {
	var version int
	err := db.QueryRow("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").Scan(&version)
	if err == sql.ErrNoRows {
		return 0, nil
	}
	if err != nil {
		// Table might not exist yet
		return 0, nil
	}
	return version, nil
}

func setSchemaVersion(tx *sql.Tx, version int) error {
	_, err := tx.Exec("INSERT INTO schema_version (version) VALUES (?)", version)
	return err
}
