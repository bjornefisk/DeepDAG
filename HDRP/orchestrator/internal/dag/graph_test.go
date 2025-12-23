package dag

import (
	"testing"
)

func TestGraph_Validate(t *testing.T) {
	tests := []struct {
		name    string
		graph   Graph
		wantErr bool
	}{
		{
			name: "Valid Simple DAG",
			graph: Graph{
				Nodes: []Node{
					{ID: "A", Type: "task"},
					{ID: "B", Type: "task"},
				},
				Edges: []Edge{
					{From: "A", To: "B"},
				},
			},
			wantErr: false,
		},
		{
			name: "Empty Graph",
			graph: Graph{
				Nodes: []Node{},
			},
			wantErr: true,
		},
		{
			name: "Duplicate Node IDs",
			graph: Graph{
				Nodes: []Node{
					{ID: "A", Type: "task"},
					{ID: "A", Type: "task"},
				},
			},
			wantErr: true,
		},
		{
			name: "Edge to Non-existent Node",
			graph: Graph{
				Nodes: []Node{
					{ID: "A", Type: "task"},
				},
				Edges: []Edge{
					{From: "A", To: "B"},
				},
			},
			wantErr: true,
		},
		{
			name: "Self Loop",
			graph: Graph{
				Nodes: []Node{
					{ID: "A", Type: "task"},
				},
				Edges: []Edge{
					{From: "A", To: "A"},
				},
			},
			wantErr: true,
		},
		{
			name: "Cycle A->B->A",
			graph: Graph{
				Nodes: []Node{
					{ID: "A", Type: "task"},
					{ID: "B", Type: "task"},
				},
				Edges: []Edge{
					{From: "A", To: "B"},
					{From: "B", To: "A"},
				},
			},
			wantErr: true,
		},
		{
			name: "Cycle A->B->C->A",
			graph: Graph{
				Nodes: []Node{
					{ID: "A", Type: "task"},
					{ID: "B", Type: "task"},
					{ID: "C", Type: "task"},
				},
				Edges: []Edge{
					{From: "A", To: "B"},
					{From: "B", To: "C"},
					{From: "C", To: "A"},
				},
			},
			wantErr: true,
		},
		{
			name: "Disconnected Valid DAG",
			graph: Graph{
				Nodes: []Node{
					{ID: "A", Type: "task"},
					{ID: "B", Type: "task"},
					{ID: "C", Type: "task"},
				},
				Edges: []Edge{
					{From: "A", To: "B"},
					// C is disconnected
				},
			},
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if err := tt.graph.Validate(); (err != nil) != tt.wantErr {
				t.Errorf("Graph.Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}
