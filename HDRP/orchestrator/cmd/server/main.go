package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	_ "net/http/pprof"  // Enable pprof profiling endpoints
	"os"
	"os/signal"
	"syscall"
	"time"

	"hdrp/internal/clients"
	"hdrp/internal/dag"
	"hdrp/internal/executor"

	pb "github.com/deepdag/hdrp/api/gen/services"

	"github.com/google/uuid"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// ExecuteRequest is the HTTP payload for query execution.
type ExecuteRequest struct {
	Query    string            `json:"query"`
	RunID    string            `json:"run_id,omitempty"`
	Context  map[string]string `json:"context,omitempty"`
	Provider string            `json:"provider,omitempty"`
}

// ExecuteResponse contains the execution result and generated report.
type ExecuteResponse struct {
	RunID        string `json:"run_id"`
	Success      bool   `json:"success"`
	Report       string `json:"report,omitempty"`
	ArtifactURI  string `json:"artifact_uri,omitempty"`
	ErrorMessage string `json:"error_message,omitempty"`
}

type Server struct {
	clients  *clients.ServiceClients
	executor *executor.DAGExecutor
	port     int
}

func NewServer(port int) (*Server, error) {
	config := clients.DefaultServiceConfig()
	
	// Override defaults with environment variables.
	if addr := os.Getenv("HDRP_PRINCIPAL_ADDR"); addr != "" {
		config.PrincipalAddr = addr
	}
	if addr := os.Getenv("HDRP_RESEARCHER_ADDR"); addr != "" {
		config.ResearcherAddr = addr
	}
	if addr := os.Getenv("HDRP_CRITIC_ADDR"); addr != "" {
		config.CriticAddr = addr
	}
	if addr := os.Getenv("HDRP_SYNTHESIZER_ADDR"); addr != "" {
		config.SynthesizerAddr = addr
	}

	log.Printf("Connecting to services: Principal=%s, Researcher=%s, Critic=%s, Synthesizer=%s",
		config.PrincipalAddr, config.ResearcherAddr, config.CriticAddr, config.SynthesizerAddr)

	clients, err := clients.NewServiceClients(config)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize service clients: %w", err)
	}

	exec := executor.NewDAGExecutor(clients, 4)

	return &Server{
		clients:  clients,
		executor: exec,
		port:     port,
	}, nil
}

func (s *Server) handleExecute(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req ExecuteRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, fmt.Sprintf("Invalid request: %v", err), http.StatusBadRequest)
		return
	}

	if req.Query == "" {
		http.Error(w, "Query is required", http.StatusBadRequest)
		return
	}

	// Generate run ID if not provided
	runID := req.RunID
	if runID == "" {
		runID = uuid.New().String()
	}

	log.Printf("[Server] Received execute request: query='%s', run_id=%s", req.Query, runID)

	// Step 1: Decompose query using Principal service
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Minute)
	defer cancel()

	decompReq := &pb.QueryRequest{
		Query:   req.Query,
		Context: req.Context,
		RunId:   runID,
	}

	decompResp, err := s.clients.Principal.DecomposeQuery(ctx, decompReq)
	if err != nil {
		// Extract gRPC status code and convert to HTTP status
		if st, ok := status.FromError(err); ok {
			switch st.Code() {
			case codes.InvalidArgument:
				log.Printf("[Server] Invalid argument: %v", st.Message())
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(ExecuteResponse{
					RunID:        runID,
					Success:      false,
					ErrorMessage: fmt.Sprintf("Invalid query: %s", st.Message()),
				})
				return
			case codes.DeadlineExceeded:
				log.Printf("[Server] Deadline exceeded: %v", st.Message())
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusGatewayTimeout)
				json.NewEncoder(w).Encode(ExecuteResponse{
					RunID:        runID,
					Success:      false,
					ErrorMessage: fmt.Sprintf("Request timed out: %s", st.Message()),
				})
				return
			default:
				log.Printf("[Server] gRPC error: %v", st.Message())
				s.sendErrorResponse(w, runID, fmt.Sprintf("Service error: %s", st.Message()))
				return
			}
		}
		log.Printf("[Server] Principal decomposition failed: %v", err)
		s.sendErrorResponse(w, runID, fmt.Sprintf("Query decomposition failed: %v", err))
		return
	}

	// Convert protobuf Graph to internal dag.Graph
	graph := convertProtoGraph(decompResp.Graph)

	log.Printf("[Server] Graph created with %d nodes, %d edges", len(graph.Nodes), len(graph.Edges))

	// Step 2: Execute the DAG
	result, err := s.executor.Execute(ctx, graph, runID)
	if err != nil {
		log.Printf("[Server] Execution failed: %v", err)
		s.sendErrorResponse(w, runID, fmt.Sprintf("Execution failed: %v", err))
		return
	}

	// Step 3: Return response
	resp := ExecuteResponse{
		RunID:        runID,
		Success:      result.Success,
		Report:       result.FinalReport,
		ArtifactURI:  result.ArtifactURI,
		ErrorMessage: result.ErrorMessage,
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(resp); err != nil {
		log.Printf("[Server] Failed to encode response: %v", err)
	}

	log.Printf("[Server] Request completed: run_id=%s, success=%v", runID, result.Success)
}

func (s *Server) sendErrorResponse(w http.ResponseWriter, runID string, errMsg string) {
	resp := ExecuteResponse{
		RunID:        runID,
		Success:      false,
		ErrorMessage: errMsg,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusInternalServerError)
	json.NewEncoder(w).Encode(resp)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "healthy"})
}

func (s *Server) Start() error {
	mux := http.NewServeMux()
	mux.HandleFunc("/execute", s.handleExecute)
	mux.HandleFunc("/health", s.handleHealth)

	addr := fmt.Sprintf(":%d", s.port)
	server := &http.Server{
		Addr:    addr,
		Handler: mux,
	}

	log.Printf("Orchestrator server starting on %s", addr)
	log.Printf("Profiling endpoints available at http://localhost%s/debug/pprof/", addr)

	// Graceful shutdown
	go func() {
		sigChan := make(chan os.Signal, 1)
		signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
		<-sigChan

		log.Println("Shutting down orchestrator server...")

		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		if err := server.Shutdown(ctx); err != nil {
			log.Printf("Server shutdown error: %v", err)
		}

		s.clients.Close()
	}()

	return server.ListenAndServe()
}

func convertProtoGraph(pbGraph *pb.Graph) *dag.Graph {
	nodes := make([]dag.Node, len(pbGraph.Nodes))
	for i, pbNode := range pbGraph.Nodes {
		nodes[i] = dag.Node{
			ID:             pbNode.Id,
			Type:           pbNode.Type,
			Config:         pbNode.Config,
			Status:         dag.Status(pbNode.Status),
			RelevanceScore: pbNode.RelevanceScore,
			Depth:          int(pbNode.Depth),
		}
	}

	edges := make([]dag.Edge, len(pbGraph.Edges))
	for i, pbEdge := range pbGraph.Edges {
		edges[i] = dag.Edge{
			From: pbEdge.From,
			To:   pbEdge.To,
		}
	}

	return &dag.Graph{
		ID:       pbGraph.Id,
		Nodes:    nodes,
		Edges:    edges,
		Status:   dag.StatusCreated,
		Metadata: pbGraph.Metadata,
	}
}

func main() {
	port := flag.Int("port", 50055, "Orchestrator server port")
	flag.Parse()

	server, err := NewServer(*port)
	if err != nil {
		log.Fatalf("Failed to create server: %v", err)
	}

	if err := server.Start(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server error: %v", err)
	}
}
