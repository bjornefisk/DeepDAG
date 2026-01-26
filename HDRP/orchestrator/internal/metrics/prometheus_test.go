package metrics

import (
	"strings"
	"testing"

	"github.com/prometheus/client_golang/prometheus/testutil"
)

func TestMetricsCountersAndGauge(t *testing.T) {
	RecordNodeExecution("researcher", "success")
	if got := testutil.ToFloat64(nodeExecutions.WithLabelValues("researcher", "success")); got < 1 {
		t.Fatalf("expected node execution counter >= 1, got %v", got)
	}

	RecordError("principal", "test")
	if got := testutil.ToFloat64(errorCount.WithLabelValues("principal", "test")); got < 1 {
		t.Fatalf("expected error counter >= 1, got %v", got)
	}

	IncrementActiveDagExecutions()
	if got := testutil.ToFloat64(activeDagExecutions); got != 1 {
		t.Fatalf("expected active DAG executions 1, got %v", got)
	}
	DecrementActiveDagExecutions()
	if got := testutil.ToFloat64(activeDagExecutions); got != 0 {
		t.Fatalf("expected active DAG executions 0, got %v", got)
	}
}

func TestDagExecutionHistogramUpdates(t *testing.T) {
	RecordDAGExecution(1.2, "success")

	expected := `
# HELP hdrp_dag_execution_seconds DAG execution duration in seconds
# TYPE hdrp_dag_execution_seconds histogram
hdrp_dag_execution_seconds_bucket{status="success",le="0.1"} 0
hdrp_dag_execution_seconds_bucket{status="success",le="0.5"} 0
hdrp_dag_execution_seconds_bucket{status="success",le="1"} 0
hdrp_dag_execution_seconds_bucket{status="success",le="2"} 1
hdrp_dag_execution_seconds_bucket{status="success",le="5"} 1
hdrp_dag_execution_seconds_bucket{status="success",le="10"} 1
hdrp_dag_execution_seconds_bucket{status="success",le="30"} 1
hdrp_dag_execution_seconds_bucket{status="success",le="60"} 1
hdrp_dag_execution_seconds_bucket{status="success",le="120"} 1
hdrp_dag_execution_seconds_bucket{status="success",le="300"} 1
hdrp_dag_execution_seconds_bucket{status="success",le="+Inf"} 1
hdrp_dag_execution_seconds_sum{status="success"} 1.2
hdrp_dag_execution_seconds_count{status="success"} 1
`
	if err := testutil.CollectAndCompare(dagExecutionDuration, strings.NewReader(expected)); err != nil {
		t.Fatalf("unexpected histogram output: %v", err)
	}
}
