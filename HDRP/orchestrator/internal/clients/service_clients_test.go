package clients

import (
	"net"
	"testing"

	"google.golang.org/grpc"
)

func startTestServer(t *testing.T) (string, func()) {
	t.Helper()
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	server := grpc.NewServer()
	go func() {
		_ = server.Serve(lis)
	}()
	stop := func() {
		server.Stop()
		_ = lis.Close()
	}
	return lis.Addr().String(), stop
}

func TestDialWithRetrySuccess(t *testing.T) {
	addr, stop := startTestServer(t)
	t.Cleanup(stop)

	conn, err := dialWithRetry(addr, "Test")
	if err != nil {
		t.Fatalf("dialWithRetry failed: %v", err)
	}
	_ = conn.Close()
}

func TestNewServiceClientsSuccess(t *testing.T) {
	principalAddr, stopPrincipal := startTestServer(t)
	researcherAddr, stopResearcher := startTestServer(t)
	criticAddr, stopCritic := startTestServer(t)
	synthAddr, stopSynth := startTestServer(t)
	t.Cleanup(stopPrincipal)
	t.Cleanup(stopResearcher)
	t.Cleanup(stopCritic)
	t.Cleanup(stopSynth)

	cfg := &ServiceConfig{
		PrincipalAddr:   principalAddr,
		ResearcherAddr:  researcherAddr,
		CriticAddr:      criticAddr,
		SynthesizerAddr: synthAddr,
	}

	clients, err := NewServiceClients(cfg)
	if err != nil {
		t.Fatalf("NewServiceClients failed: %v", err)
	}
	if err := clients.Close(); err != nil {
		t.Fatalf("Close failed: %v", err)
	}
}
