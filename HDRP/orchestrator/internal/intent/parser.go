package intent

import (
	"strings"
	"time"

	"github.com/google/uuid"
)

// IntentType represents the classification of a user's goal.
type IntentType string

const (
	IntentResearch IntentType = "RESEARCH"
	IntentCodeGen  IntentType = "CODE_GEN"
	IntentAnalysis IntentType = "ANALYSIS"
	IntentGeneral  IntentType = "GENERAL"
)

// Objective represents the high-level goal parsed from a user query.
type Objective struct {
	ID          string            `json:"id"`
	Description string            `json:"description"`
	Type        IntentType        `json:"type"`
	Constraints []string          `json:"constraints"`
	Metadata    map[string]string `json:"metadata"`
	CreatedAt   time.Time         `json:"created_at"`
}

// Parser defines the interface for converting raw queries into structured objectives.
type Parser interface {
	Parse(query string) (*Objective, error)
}

// BasicParser implements a simple heuristic-based parser for the MVP.
type BasicParser struct{}

// NewBasicParser creates a new instance of BasicParser.
func NewBasicParser() *BasicParser {
	return &BasicParser{}
}

// Parse converts a user query string into an Objective using keyword heuristics.
func (p *BasicParser) Parse(query string) (*Objective, error) {
	if strings.TrimSpace(query) == "" {
		return nil, ErrEmptyQuery
	}


trimmedQuery := strings.TrimSpace(query)
	lowerQuery := strings.ToLower(trimmedQuery)

	intentType := detectIntent(lowerQuery)
	constraints := extractConstraints(trimmedQuery)

	return &Objective{
		ID:          uuid.New().String(),
		Description: trimmedQuery,
		Type:        intentType,
		Constraints: constraints,
		Metadata: map[string]string{
			"parser_version": "mvp-v1",
			"original_len":   string(rune(len(query))), // simple metadata example
		},
		CreatedAt: time.Now(),
	}, nil
}

func detectIntent(query string) IntentType {
	switch {
	case strings.Contains(query, "research"), strings.Contains(query, "find out"), strings.Contains(query, "investigate"):
		return IntentResearch
	case strings.Contains(query, "code"), strings.Contains(query, "implement"), strings.Contains(query, "function"), strings.Contains(query, "class"):
		return IntentCodeGen
	case strings.Contains(query, "analyze"), strings.Contains(query, "evaluate"), strings.Contains(query, "review"):
		return IntentAnalysis
	default:
		return IntentGeneral
	}
}

// extractConstraints is a placeholder for extraction logic.
// In a real system, this might use NER or dependency parsing.
func extractConstraints(query string) []string {
	var constraints []string
	// Simple heuristic: phrases in quotes are constraints
	parts := strings.Split(query, "\"")
	for i := 1; i < len(parts); i += 2 {
		constraints = append(constraints, parts[i])
	}
	return constraints
}
