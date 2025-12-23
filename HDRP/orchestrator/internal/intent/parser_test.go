package intent

import (
	"strings"
	"testing"
)

func TestBasicParser_Parse(t *testing.T) {
	parser := NewBasicParser()

	tests := []struct {
		name        string
		query       string
		wantType    IntentType
		wantConstr  int // number of constraints
		wantErr     bool
	}{
		{
			name:       "Research Query",
			query:      "Research the impact of quantum computing on cryptography",
			wantType:   IntentResearch,
			wantConstr: 0,
			wantErr:    false,
		},
		{
			name:       "Code Generation Query",
			query:      "Implement a binary search tree in Python",
			wantType:   IntentCodeGen,
			wantConstr: 0,
			wantErr:    false,
		},
		{
			name:       "Analysis Query",
			query:      "Analyze the performance of this database schema",
			wantType:   IntentAnalysis,
			wantConstr: 0,
			wantErr:    false,
		},
		{
			name:       "General Query",
			query:      "Hello world",
			wantType:   IntentGeneral,
			wantConstr: 0,
			wantErr:    false,
		},
		{
			name:       "Query with Constraints",
			query:      "Write a story about \"dragons\" and \"robots\"",
			wantType:   IntentGeneral, // defaults to general if keywords missing
			wantConstr: 2,
			wantErr:    false,
		},
		{
			name:       "Empty Query",
			query:      "   ",
			wantType:   IntentGeneral,
			wantConstr: 0,
			wantErr:    true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := parser.Parse(tt.query)
			if (err != nil) != tt.wantErr {
				t.Errorf("Parse() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if !tt.wantErr {
				if got.Type != tt.wantType {
					t.Errorf("Parse() gotType = %v, want %v", got.Type, tt.wantType)
				}
				if len(got.Constraints) != tt.wantConstr {
					t.Errorf("Parse() gotConstraints count = %d, want %d", len(got.Constraints), tt.wantConstr)
				}
				if got.ID == "" {
					t.Error("Parse() returned empty ID")
				}
				if got.Description != strings.TrimSpace(tt.query) {
					t.Errorf("Parse() description mismatch")
				}
			}
		})
	}
}

func TestConstraintExtraction(t *testing.T) {
	// Detailed check for the extraction logic
	query := `Find images of "cats" and "dogs" but not "birds"`
	expected := []string{"cats", "dogs", "birds"}

	parser := NewBasicParser()
	obj, _ := parser.Parse(query)

	if len(obj.Constraints) != len(expected) {
		t.Fatalf("Expected %d constraints, got %d", len(expected), len(obj.Constraints))
	}

	for i, c := range obj.Constraints {
		if c != expected[i] {
			t.Errorf("Constraint %d: got %s, want %s", i, c, expected[i])
		}
	}
}
