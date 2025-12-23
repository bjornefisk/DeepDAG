package dag

import (
	"encoding/json"
	"fmt"
	"io"
)

// LoadJSON decodes a JSON-encoded DAG from the reader and validates it.
// It returns a pointer to the Graph or an error if decoding or validation fails.
//
// Example:
//
//	f, _ := os.Open("dag.json")
//	g, err := dag.LoadJSON(f)
func LoadJSON(r io.Reader) (*Graph, error) {
	if r == nil {
		return nil, fmt.Errorf("reader cannot be nil")
	}

	var g Graph
	dec := json.NewDecoder(r)
	dec.DisallowUnknownFields() // Strict parsing: fail if unknown fields are present

	if err := dec.Decode(&g); err != nil {
		return nil, fmt.Errorf("failed to decode graph JSON: %w", err)
	}

	if err := g.Validate(); err != nil {
		return nil, fmt.Errorf("decoded graph is invalid: %w", err)
	}

	return &g, nil
}

// WriteJSON encodes the DAG to the writer in JSON format.
// It validates the graph before writing to ensure only valid state is persisted.
func WriteJSON(w io.Writer, g *Graph) error {
	if w == nil {
		return fmt.Errorf("writer cannot be nil")
	}
	if g == nil {
		return fmt.Errorf("graph cannot be nil")
	}

	// Ensure we are writing a valid graph
	if err := g.Validate(); err != nil {
		return fmt.Errorf("cannot serialize invalid graph: %w", err)
	}

	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ") // Pretty print for readability

	if err := enc.Encode(g); err != nil {
		return fmt.Errorf("failed to encode graph to JSON: %w", err)
	}

	return nil
}
