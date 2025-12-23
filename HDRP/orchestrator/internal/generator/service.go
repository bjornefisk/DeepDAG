package generator

import (
	"fmt"

	"github.com/google/uuid"

	"hdrp/internal/dag"
	"hdrp/internal/intent"
)

// Generator defines the interface for creating execution graphs from objectives.
type Generator interface {
	Generate(obj *intent.Objective) (*dag.Graph, error)
}

// TemplateGenerator creates graphs based on predefined blueprints for each intent type.
type TemplateGenerator struct {
	// In a real system, these might be loaded from YAML/JSON files
	blueprints map[intent.IntentType]blueprint
}

type blueprint struct {
	nodes []dag.Node
	edges []dag.Edge
}

// NewTemplateGenerator initializes the generator with standard intent blueprints.
func NewTemplateGenerator() *TemplateGenerator {
	return &TemplateGenerator{
		blueprints: loadStandardBlueprints(),
	}
}

func (g *TemplateGenerator) Generate(obj *intent.Objective) (*dag.Graph, error) {
	if obj == nil {
		return nil, fmt.Errorf("cannot generate graph from nil objective")
	}

	bp, ok := g.blueprints[obj.Type]
	if !ok {
		// Fallback to a generic single-step graph if intent is unknown
		bp = g.blueprints[intent.IntentGeneral]
	}

	// Hydrate the blueprint into a unique graph instance
	graphID := fmt.Sprintf("graph-%s", uuid.New().String()[:8])
	graph := &dag.Graph{
		ID:     graphID,
		Status: dag.StatusCreated,
		Nodes:  make([]dag.Node, len(bp.nodes)),
		Edges:  make([]dag.Edge, len(bp.edges)),
	}

	// Deep copy nodes and inject context from the objective
	for i, nodeTmpl := range bp.nodes {
		n := nodeTmpl // copy
		n.ID = fmt.Sprintf("%s-%s", nodeTmpl.ID, uuid.New().String()[:6])
		n.Status = dag.StatusCreated
		
		// Initialize config if nil
		if n.Config == nil {
			n.Config = make(map[string]string)
		}
		
		// Inject objective context
		n.Config["goal"] = obj.Description
		for k, v := range obj.Metadata {
			n.Config["meta_"+k] = v
		}

		graph.Nodes[i] = n
	}

	// Remap edges to the new unique Node IDs
	// We need a map from TemplateID -> InstanceID
	idMap := make(map[string]string)
	for i, tmplNode := range bp.nodes {
		idMap[tmplNode.ID] = graph.Nodes[i].ID
	}

	for i, edgeTmpl := range bp.edges {
		graph.Edges[i] = dag.Edge{
			From: idMap[edgeTmpl.From],
			To:   idMap[edgeTmpl.To],
		}
	}

	return graph, nil
}

func loadStandardBlueprints() map[intent.IntentType]blueprint {
	return map[intent.IntentType]blueprint{
		intent.IntentResearch: {
			nodes: []dag.Node{
				{ID: "researcher", Type: "researcher_agent"},
				{ID: "critic", Type: "critic_agent"},
				{ID: "synthesizer", Type: "synthesizer_agent"},
			},
			edges: []dag.Edge{
				{From: "researcher", To: "critic"},
				{From: "critic", To: "synthesizer"},
			},
		},
		intent.IntentCodeGen: {
			nodes: []dag.Node{
				{ID: "architect", Type: "architect_agent"},
				{ID: "coder", Type: "coding_agent"},
				{ID: "reviewer", Type: "code_reviewer_agent"},
			},
			edges: []dag.Edge{
				{From: "architect", To: "coder"},
				{From: "coder", To: "reviewer"},
			},
		},
		intent.IntentAnalysis: {
			nodes: []dag.Node{
				{ID: "loader", Type: "data_loader"},
				{ID: "analyzer", Type: "data_analyzer"},
				{ID: "reporter", Type: "report_generator"},
			},
			edges: []dag.Edge{
				{From: "loader", To: "analyzer"},
				{From: "analyzer", To: "reporter"},
			},
		},
		intent.IntentGeneral: {
			nodes: []dag.Node{
				{ID: "processor", Type: "generic_llm_agent"},
			},
			edges: []dag.Edge{},
		},
	}
}
