package generator

import (
	"strings"
	"testing"

	"hdrp/internal/dag"
	"hdrp/internal/intent"
)

func TestTemplateGenerator_Generate(t *testing.T) {
	gen := NewTemplateGenerator()

	tests := []struct {
		name          string
		intentType    intent.IntentType
		desc          string
		wantNodeCount int
		wantEdgeCount int
		wantNodeTypes []string
	}{
		{
			name:          "Research Blueprint",
			intentType:    intent.IntentResearch,
			desc:          "Research LLM architectures",
			wantNodeCount: 3,
			wantEdgeCount: 2,
			wantNodeTypes: []string{"researcher_agent", "critic_agent", "synthesizer_agent"},
		},
		{
			name:          "CodeGen Blueprint",
			intentType:    intent.IntentCodeGen,
			desc:          "Write a python script",
			wantNodeCount: 3,
			wantEdgeCount: 2,
			wantNodeTypes: []string{"architect_agent", "coding_agent", "code_reviewer_agent"},
		},
		{
			name:          "General/Fallback Blueprint",
			intentType:    intent.IntentType("UNKNOWN_TYPE"),
			desc:          "Just say hi",
			wantNodeCount: 1,
			wantEdgeCount: 0,
			wantNodeTypes: []string{"generic_llm_agent"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			obj := &intent.Objective{
				Type:        tt.intentType,
				Description: tt.desc,
				Metadata:    map[string]string{"foo": "bar"},
			}

			g, err := gen.Generate(obj)
			if err != nil {
				t.Fatalf("Generate() error = %v", err)
			}

			if g.Status != dag.StatusCreated {
				t.Errorf("Graph status = %s, want %s", g.Status, dag.StatusCreated)
			}

			if len(g.Nodes) != tt.wantNodeCount {
				t.Errorf("Node count = %d, want %d", len(g.Nodes), tt.wantNodeCount)
			}
			if len(g.Edges) != tt.wantEdgeCount {
				t.Errorf("Edge count = %d, want %d", len(g.Edges), tt.wantEdgeCount)
			}

			// Validate Context Injection
			for _, n := range g.Nodes {
				if n.Config["goal"] != tt.desc {
					t.Errorf("Node %s missing injected goal config", n.ID)
				}
				if n.Config["meta_foo"] != "bar" {
					t.Errorf("Node %s missing injected metadata", n.ID)
				}
				// Verify unique IDs (not the template IDs)
				if !strings.Contains(n.ID, "-") {
					t.Errorf("Node ID %s appears to be raw template ID, expected UUID suffix", n.ID)
				}
			}

			// Validate Structure (Nodes present)
			typeMap := make(map[string]bool)
			for _, n := range g.Nodes {
				typeMap[n.Type] = true
			}
			for _, wantType := range tt.wantNodeTypes {
				if !typeMap[wantType] {
					t.Errorf("Missing expected node type: %s", wantType)
				}
			}

			// Sanity check: Run the graph validator
			if err := g.Validate(); err != nil {
				t.Errorf("Generated graph failed validation: %v", err)
			}
		})
	}
}

func TestTemplateGenerator_NilObjective(t *testing.T) {
	gen := NewTemplateGenerator()
	_, err := gen.Generate(nil)
	if err == nil {
		t.Error("Expected error when generating from nil objective")
	}
}
