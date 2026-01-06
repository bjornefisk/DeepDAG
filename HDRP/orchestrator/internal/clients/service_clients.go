package clients

import (
	"context"
	"fmt"
	"log"
	"time"

	pb "github.com/deepdag/hdrp/api/gen/services"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// ServiceClients manages gRPC connections to Python microservices.
type ServiceClients struct {
	Principal   pb.PrincipalServiceClient
	Researcher  pb.ResearcherServiceClient
	Critic      pb.CriticServiceClient
	Synthesizer pb.SynthesizerServiceClient

	principalConn   *grpc.ClientConn
	researcherConn  *grpc.ClientConn
	criticConn      *grpc.ClientConn
	synthesizerConn *grpc.ClientConn
}

// ServiceConfig specifies service network addresses.
type ServiceConfig struct {
	PrincipalAddr   string
	ResearcherAddr  string
	CriticAddr      string
	SynthesizerAddr string
}

// DefaultServiceConfig returns localhost addresses for all services.
func DefaultServiceConfig() *ServiceConfig {
	return &ServiceConfig{
		PrincipalAddr:   "localhost:50051",
		ResearcherAddr:  "localhost:50052",
		CriticAddr:      "localhost:50053",
		SynthesizerAddr: "localhost:50054",
	}
}

// NewServiceClients establishes gRPC connections to all Python services.
func NewServiceClients(config *ServiceConfig) (*ServiceClients, error) {
	if config == nil {
		config = DefaultServiceConfig()
	}

	clients := &ServiceClients{}

	principalConn, err := dialWithRetry(config.PrincipalAddr, "Principal")
	if err != nil {
		return nil, fmt.Errorf("failed to connect to Principal service: %w", err)
	}
	clients.principalConn = principalConn
	clients.Principal = pb.NewPrincipalServiceClient(principalConn)

	researcherConn, err := dialWithRetry(config.ResearcherAddr, "Researcher")
	if err != nil {
		clients.Close()
		return nil, fmt.Errorf("failed to connect to Researcher service: %w", err)
	}
	clients.researcherConn = researcherConn
	clients.Researcher = pb.NewResearcherServiceClient(researcherConn)

	criticConn, err := dialWithRetry(config.CriticAddr, "Critic")
	if err != nil {
		clients.Close()
		return nil, fmt.Errorf("failed to connect to Critic service: %w", err)
	}
	clients.criticConn = criticConn
	clients.Critic = pb.NewCriticServiceClient(criticConn)

	synthesizerConn, err := dialWithRetry(config.SynthesizerAddr, "Synthesizer")
	if err != nil {
		clients.Close()
		return nil, fmt.Errorf("failed to connect to Synthesizer service: %w", err)
	}
	clients.synthesizerConn = synthesizerConn
	clients.Synthesizer = pb.NewSynthesizerServiceClient(synthesizerConn)

	log.Printf("Successfully connected to all services")
	return clients, nil
}

// dialWithRetry establishes a gRPC connection with exponential backoff.
func dialWithRetry(addr string, serviceName string) (*grpc.ClientConn, error) {
	const maxRetries = 3
	const retryDelay = 2 * time.Second

	var conn *grpc.ClientConn
	var err error

	for i := 0; i < maxRetries; i++ {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		conn, err = grpc.DialContext(
			ctx,
			addr,
			grpc.WithTransportCredentials(insecure.NewCredentials()),
			grpc.WithBlock(),
		)

		if err == nil {
			log.Printf("Connected to %s service at %s", serviceName, addr)
			return conn, nil
		}

		log.Printf("Failed to connect to %s service (attempt %d/%d): %v", serviceName, i+1, maxRetries, err)
		if i < maxRetries-1 {
			time.Sleep(retryDelay)
		}
	}

	return nil, fmt.Errorf("failed to connect to %s service at %s after %d attempts: %w", serviceName, addr, maxRetries, err)
}

// Close terminates all gRPC connections.
func (c *ServiceClients) Close() error {
	var errs []error

	if c.principalConn != nil {
		if err := c.principalConn.Close(); err != nil {
			errs = append(errs, fmt.Errorf("failed to close Principal connection: %w", err))
		}
	}

	if c.researcherConn != nil {
		if err := c.researcherConn.Close(); err != nil {
			errs = append(errs, fmt.Errorf("failed to close Researcher connection: %w", err))
		}
	}

	if c.criticConn != nil {
		if err := c.criticConn.Close(); err != nil {
			errs = append(errs, fmt.Errorf("failed to close Critic connection: %w", err))
		}
	}

	if c.synthesizerConn != nil {
		if err := c.synthesizerConn.Close(); err != nil {
			errs = append(errs, fmt.Errorf("failed to close Synthesizer connection: %w", err))
		}
	}

	if len(errs) > 0 {
		return fmt.Errorf("errors closing connections: %v", errs)
	}

	return nil
}
