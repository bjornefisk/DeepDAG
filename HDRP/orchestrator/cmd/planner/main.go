package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"hdrp/internal/dag"
	"hdrp/internal/generator"
	"hdrp/internal/intent"
	"hdrp/internal/logger"
)

func main() {
	queryPtr := flag.String("query", "", "The research query or objective")
	jsonPtr := flag.Bool("json", false, "Output only the final structured JSON")
	flag.Parse()

	if *queryPtr == "" {
		fmt.Fprintln(os.Stderr, "Please provide a query using -query=\"...\"")
		os.Exit(1)
	}

	runID := logger.GenerateRunID()
	// Initialize logger (writes to ../../logs/<runID>.jsonl)
	if err := logger.InitLogger(runID); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to init logger: %v\n", err)
		os.Exit(1)
	}
	defer logger.Close()

	ctx := context.Background()
	logger.LogEvent(ctx, runID, "cli", "startup", map[string]string{"query": *queryPtr})

	// 1. Parse Intent
	if !*jsonPtr {
		fmt.Println("--> Parsing Intent...")
	}
	parser := intent.NewBasicParser()
	objective, err := parser.Parse(*queryPtr)
	if err != nil {
		logger.LogEvent(ctx, runID, "cli", "error", map[string]string{"phase": "intent", "error": err.Error()})
		fmt.Fprintf(os.Stderr, "Error parsing intent: %v\n", err)
		os.Exit(1)
	}
	
	if !*jsonPtr {
		fmt.Printf("    Identified Intent: %s\n", objective.Type)
		fmt.Printf("    Constraints: %v\n", objective.Constraints)
	}

	// 2. Generate Plan (DAG)
	if !*jsonPtr {
		fmt.Println("--> Generating Execution Graph...")
	}
	gen := generator.NewTemplateGenerator()
	graph, err := gen.Generate(objective)
	if err != nil {
		logger.LogEvent(ctx, runID, "cli", "error", map[string]string{"phase": "generation", "error": err.Error()})
		fmt.Fprintf(os.Stderr, "Error generating graph: %v\n", err)
		os.Exit(1)
	}

	// 3. Validate
	if err := graph.Validate(); err != nil {
		fmt.Fprintf(os.Stderr, "Generated graph is invalid: %v\n", err)
		os.Exit(1)
	}

	// 4. Log Plan
	dag.LogGraphPlan(ctx, runID, graph)
	if !*jsonPtr {
		fmt.Println("--> Plan Logged.")
	}

	// 5. Output JSON to Stdout for user inspection
	if !*jsonPtr {
		fmt.Println("\n=== FINAL PLAN (JSON) ===")
	}
	enc := json.NewEncoder(os.Stdout)
	if !*jsonPtr {
		enc.SetIndent("", "  ")
	}
	enc.Encode(graph)
	
	if !*jsonPtr {
		fmt.Printf("\nCheck logs at HDRP/logs/%s.jsonl\n", runID)
	}
}
