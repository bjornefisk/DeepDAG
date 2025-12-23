package dag

import (
	"bytes"
	"strings"
	"testing"
)

func TestLoadJSON(t *testing.T) {
	tests := []struct {
		name      string
		jsonInput string
		wantErr   bool
		errCheck  func(error) bool
	}{
		{
			name: "Valid DAG",
			jsonInput: `{
				"id": "graph-1",
				"nodes": [
					{"id": "A", "type": "start"},
					{"id": "B", "type": "end"}
				],
				"edges": [
					{"from": "A", "to": "B"}
				]
			}`,
			wantErr: false,
		},
		{
			name: "Invalid JSON Syntax",
			jsonInput: `{ "id": "graph-1", "nodes": [ ... broken ... ] }`,
			wantErr:   true,
			errCheck: func(err error) bool {
				return strings.Contains(err.Error(), "failed to decode graph JSON")
			},
		},
		{
			name: "Structurally Valid JSON but Invalid DAG (Cycle)",
			jsonInput: `{
				"id": "graph-cycle",
				"nodes": [
					{"id": "A", "type": "t"},
					{"id": "B", "type": "t"}
				],
				"edges": [
					{"from": "A", "to": "B"},
					{"from": "B", "to": "A"}
				]
			}`,
			wantErr: true,
			errCheck: func(err error) bool {
				// Should fail in g.Validate()
				return strings.Contains(err.Error(), "decoded graph is invalid")
			},
		},
		{
			name: "Unknown Fields (Strict Parsing)",
			jsonInput: `{
				"id": "graph-1",
				"unknown_field": "surprise",
				"nodes": [{"id": "A", "type": "t"}]
			}`,
			wantErr: true,
			errCheck: func(err error) bool {
				return strings.Contains(err.Error(), "failed to decode graph JSON")
			},
		},
		{
			name:      "Nil Reader",
			jsonInput: "", // ignored
			wantErr:   true,
			errCheck: func(err error) bool {
				return err.Error() == "reader cannot be nil"
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var r *strings.Reader
			if tt.name == "Nil Reader" {
				// Special handling for nil reader test
				_, err := LoadJSON(nil)
				if (err != nil) != tt.wantErr {
					t.Errorf("LoadJSON() error = %v, wantErr %v", err, tt.wantErr)
				}
				if tt.wantErr && tt.errCheck != nil && !tt.errCheck(err) {
					t.Errorf("LoadJSON() error = %v, check failed", err)
				}
				return
			}

			r = strings.NewReader(tt.jsonInput)
			got, err := LoadJSON(r)
			if (err != nil) != tt.wantErr {
				t.Errorf("LoadJSON() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if tt.wantErr && tt.errCheck != nil {
				if !tt.errCheck(err) {
					t.Errorf("LoadJSON() unexpected error content: %v", err)
				}
			}
			if !tt.wantErr && got == nil {
				t.Error("LoadJSON() returned nil graph on success")
			}
		})
	}
}

func TestWriteJSON(t *testing.T) {
	// Construct a valid graph
	validGraph := &Graph{
		ID: "test-export",
		Nodes: []Node{
			{ID: "1", Type: "src", Config: map[string]string{"k": "v"}},
			{ID: "2", Type: "sink"},
		},
		Edges: []Edge{
			{From: "1", To: "2"},
		},
	}

	t.Run("Valid Write", func(t *testing.T) {
		var buf bytes.Buffer
		err := WriteJSON(&buf, validGraph)
		if err != nil {
			t.Fatalf("WriteJSON() failed: %v", err)
		}

		output := buf.String()
		if !strings.Contains(output, `"id": "test-export"`) {
			t.Errorf("Output missing graph ID: %s", output)
		}
		if !strings.Contains(output, `"k": "v"`) {
			t.Errorf("Output missing config: %s", output)
		}
	})

	t.Run("Write Invalid Graph", func(t *testing.T) {
		invalidGraph := &Graph{
			ID:    "bad",
			Nodes: []Node{}, // Empty nodes = invalid
		}
		var buf bytes.Buffer
		err := WriteJSON(&buf, invalidGraph)
		if err == nil {
			t.Error("WriteJSON() should have failed for invalid graph")
		}
		if !strings.Contains(err.Error(), "cannot serialize invalid graph") {
			t.Errorf("Unexpected error: %v", err)
		}
	})

	t.Run("Nil Writer", func(t *testing.T) {
		err := WriteJSON(nil, validGraph)
		if err == nil {
			t.Error("WriteJSON() should have failed for nil writer")
		}
	})

	t.Run("Nil Graph", func(t *testing.T) {
		var buf bytes.Buffer
		err := WriteJSON(&buf, nil)
		if err == nil {
			t.Error("WriteJSON() should have failed for nil graph")
		}
	})
}
