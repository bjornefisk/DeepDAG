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
	flag.Parse()

	if *queryPtr == "" {
		fmt.Println("Please provide a query using -query=\"...\"")
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
	fmt.Println("--> Parsing Intent...")
	parser := intent.NewBasicParser()
	objective, err := parser.Parse(*queryPtr)
	if err != nil {
		logger.LogEvent(ctx, runID, "cli", "error", map[string]string{"phase": "intent", "error": err.Error()})
		fmt.Printf("Error parsing intent: %v\n", err)
		os.Exit(1)
	}
	
	fmt.Printf("    Identified Intent: %s\n", objective.Type)
	fmt.Printf("    Constraints: %v\n", objective.Constraints)

	// 2. Generate Plan (DAG)
	fmt.Println("--> Generating Execution Graph...")
	gen := generator.NewTemplateGenerator()
	graph, err := gen.Generate(objective)
	if err != nil {
		logger.LogEvent(ctx, runID, "cli", "error", map[string]string{"phase": "generation", "error": err.Error()})
		fmt.Printf("Error generating graph: %v\n", err)
		os.Exit(1)
	}

	// 3. Validate
	if err := graph.Validate(); err != nil {
		fmt.Printf("Generated graph is invalid: %v\n", err)
		os.Exit(1)
	}

	// 4. Log Plan
	dag.LogGraphPlan(ctx, runID, graph)
	fmt.Println("--> Plan Logged.")

	// 5. Output JSON to Stdout for user inspection
	fmt.Println("\n=== FINAL PLAN (JSON) ===")
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	enc.Encode(graph)
	
	fmt.Printf("\nCheck logs at HDRP/logs/%s.jsonl\n", runID)
}
