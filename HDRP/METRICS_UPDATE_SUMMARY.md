# HDRP Metrics System Update Summary

## Overview
This update enhances the evaluation metrics for the HDRP vs ReAct comparison. The goal is to provide a fairer and more granular assessment of system performance, specifically by distinguishing between raw and verified claims and introducing quality-focused metrics.

## Key Changes

### 1. Metric Separation
- **Raw Claims (`raw_claims_extracted`)**: Total claims found by the agent before verification.
- **Verified Claims (`verified_claims_count`)**: Claims that pass the `CriticService` verification.
    - For HDRP: Claims passing the internal critic.
    - For ReAct: Claims retrospectively verified by the `CriticService` to measure "extraction accuracy".

### 2. New Quality Metrics
- **Completeness / Extraction Accuracy**:
    - Formula: `Verified Claims / Raw Claims` (per system).
    - Purpose: Measures the reliability of the extraction process.
- **Entailment Score**:
    - Formula: Average token overlap ratio between the verified claim and the original query.
    - Purpose: Quantifies how well the extracted claims support the user's question (relevance/support).
- **Comparative Precision**:
    - Formula: `HDRP Verified Claims / ReAct Raw Claims`.
    - Purpose: Measures HDRP's valid information yield relative to the ReAct baseline's total output (filtering accuracy relative to baseline volume).

### 3. Implementation Details

#### `HDRP/services/critic/service.py`
- Updated `verify` method to calculate `entailment_score` based on token intersection between claim and task.
- Exposed this score in `CritiqueResult`.

#### `HDRP/services/shared/claims.py`
- Added `entailment_score` field to `CritiqueResult`.

#### `HDRP/tools/eval/metrics.py`
- Updated `QualityMetrics` to store `raw_claims_extracted`, `completeness`, and `entailment_score`.
- Updated `MetricsCollector` to compute these values.
- Updated `ComparisonResult` to calculate `precision`.
- Updated `AggregateComparison` to aggregate and average all new metrics.

#### `HDRP/tools/eval/compare.py`
- Added retrospective verification step for ReAct agent runs using `CriticService`.
- Passed verification results to the metrics collector.

#### `HDRP/tools/eval/results_formatter.py`
- Updated summary table to display:
    - Avg Raw Claims
    - Avg Verified Claims
    - Avg Completeness/Accuracy
    - Avg Entailment Score
    - Avg Comparative Precision (HDRP specific)

## Usage
Run the comparison script as usual to see the new metrics:
```bash
python -m HDRP.tools.eval.compare --provider simulated
```
