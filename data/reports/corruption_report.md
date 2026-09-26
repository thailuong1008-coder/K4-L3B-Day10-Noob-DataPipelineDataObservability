# Data Corruption and Recovery Report

## Three-state comparison

| Metric | Baseline | Corrupted | Repaired | Corruption delta | Recovery delta |
|---|---:|---:|---:|---:|---:|
| Retrieval Hit Rate | 100.00% | 50.00% | 100.00% | -50.00% | +50.00% |
| Mean Token F1 | 1.0000 | 0.7788 | 1.0000 | -22.12% | +22.12% |
| Judge Accuracy | 100.00% | 80.00% | 100.00% | -20.00% | +20.00% |
| Quality Gate | PASS | FAIL | PASS | - | - |
| Freshness SLA | Recorded in Phase 1 | FAIL | PASS | - | - |

## Freshness evidence

| State | Stale rows | Total rows | Stale ratio | Threshold | Status |
|---|---:|---:|---:|---:|---|
| Corrupted | 7 | 21 | 33.33% | 25.00% | FAIL |
| Repaired | 1 | 24 | 4.17% | 25.00% | PASS |

## Interpretation

Corruption changed retrieval Hit Rate by -50.00% and Mean Token F1 by -22.12% relative to baseline. This is a silent failure: the pipeline can still return answers while data quality and retrieval performance degrade.

Rebuilding from the raw snapshot changed Hit Rate by +50.00% and Mean Token F1 by +22.12% relative to the corrupted state. The repaired quality gate is PASS.
