package metrics

import (
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	// DAG execution latency histogram with percentile-friendly buckets
	dagExecutionDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "hdrp_dag_execution_seconds",
			Help:    "DAG execution duration in seconds",
			Buckets: []float64{0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300},
		},
		[]string{"status"}, // success, partial_success, failed
	)

	// Claims extracted counter
	claimsExtracted = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "hdrp_claims_extracted_total",
			Help: "Total number of claims extracted by researcher service",
		},
		[]string{"run_id", "node_id"},
	)

	// Claims verified counter
	claimsVerified = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "hdrp_claims_verified_total",
			Help: "Total number of claims verified by critic service",
		},
		[]string{"run_id", "node_id"},
	)

	// Claims rejected counter
	claimsRejected = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "hdrp_claims_rejected_total",
			Help: "Total number of claims rejected by critic service",
		},
		[]string{"run_id", "node_id"},
	)

	// Service RPC latency histogram
	rpcLatency = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "hdrp_rpc_latency_seconds",
			Help:    "RPC call latency in seconds by service",
			Buckets: []float64{0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10},
		},
		[]string{"service", "method", "status"},
	)

	// Error rate counter
	errorCount = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "hdrp_errors_total",
			Help: "Total number of errors by service and type",
		},
		[]string{"service", "error_type"},
	)

	// Node execution counter for throughput tracking
	nodeExecutions = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "hdrp_node_executions_total",
			Help: "Total number of node executions by type and status",
		},
		[]string{"node_type", "status"},
	)

	// Current active DAG executions gauge
	activeDagExecutions = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "hdrp_active_dag_executions",
			Help: "Current number of active DAG executions",
		},
	)
)

// RecordDAGExecution records DAG execution metrics
func RecordDAGExecution(durationSeconds float64, status string) {
	dagExecutionDuration.WithLabelValues(status).Observe(durationSeconds)
}

// RecordClaimExtracted increments the claims extracted counter
func RecordClaimExtracted(runID, nodeID string, count int) {
	claimsExtracted.WithLabelValues(runID, nodeID).Add(float64(count))
}

// RecordClaimVerified increments the claims verified counter
func RecordClaimVerified(runID, nodeID string, count int) {
	claimsVerified.WithLabelValues(runID, nodeID).Add(float64(count))
}

// RecordClaimRejected increments the claims rejected counter
func RecordClaimRejected(runID, nodeID string, count int) {
	claimsRejected.WithLabelValues(runID, nodeID).Add(float64(count))
}

// RecordRPCLatency records RPC call latency
func RecordRPCLatency(service, method string, durationSeconds float64, success bool) {
	status := "success"
	if !success {
		status = "error"
	}
	rpcLatency.WithLabelValues(service, method, status).Observe(durationSeconds)
}

// RecordError increments the error counter
func RecordError(service, errorType string) {
	errorCount.WithLabelValues(service, errorType).Inc()
}

// RecordNodeExecution increments the node execution counter
func RecordNodeExecution(nodeType, status string) {
	nodeExecutions.WithLabelValues(nodeType, status).Inc()
}

// IncrementActiveDagExecutions increments the active DAG executions gauge
func IncrementActiveDagExecutions() {
	activeDagExecutions.Inc()
}

// DecrementActiveDagExecutions decrements the active DAG executions gauge
func DecrementActiveDagExecutions() {
	activeDagExecutions.Dec()
}

// GetMetricsHandler returns the HTTP handler for the /metrics endpoint
func GetMetricsHandler() http.Handler {
	return promhttp.Handler()
}
