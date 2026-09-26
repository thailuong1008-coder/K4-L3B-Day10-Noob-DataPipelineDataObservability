# Corruption Report — Baseline vs Corrupted vs Repaired

_Generated at 2026-09-26T04:42:19.983047+00:00_

All three states are evaluated on the same test set (`data/eval/test_set.json`).

## 1. Metrics comparison

| Metric | Baseline | Corrupted | Repaired | Δ Corrupted | Δ Repaired |
|---|---:|---:|---:|---:|---:|
| retrieval_hit_rate | 1.0000 | 0.8000 | 1.0000 | -0.2000 | +0.0000 |
| mean_token_f1 | 1.0000 | 0.8588 | 1.0000 | -0.1412 | +0.0000 |
| judge_accuracy | 1.0000 | 0.9000 | 1.0000 | -0.1000 | +0.0000 |
| mean_judge_score | 5.0000 | 4.5000 | 5.0000 | -0.5000 | +0.0000 |

### Token F1 by question type

| Type | Baseline | Corrupted | Repaired |
|---|---:|---:|---:|
| authors | 1.0000 | 1.0000 | 1.0000 |
| categories | 1.0000 | 1.0000 | 1.0000 |
| date | 1.0000 | 1.0000 | 1.0000 |
| summary | 1.0000 | 0.5294 | 1.0000 |

## 2. Injected corruptions

Seed `42` — rows 24 → 22.

| # | Type | Rows | Description |
|---:|---|---:|---|
| 1 | `drop_latest_records` | 5 | Removed the 5 most recently published records (20%). |
| 2 | `blank_summary` | 3 | Replaced summary with an empty string. |
| 3 | `inject_noise` | 3 | Interleaved garbage tokens and reversed words inside the summary. |
| 4 | `truncate_title` | 3 | Cut title down to 6 characters. |
| 5 | `stale_date` | 6 | Shifted published date back by 1095 days. |
| 6 | `duplicate_rows` | 3 | Appended exact duplicate rows. |

## 3. Data Quality Gate

| State | GX success | Passed | Failed expectations | Freshness | Stale ratio |
|---|:---:|---:|---|:---:|---:|
| Corrupted | FAIL | 5/9 | `expect_column_values_to_be_unique:paper_id`, `expect_column_value_lengths_to_be_between:title`, `expect_column_value_lengths_to_be_between:summary`, `expect_column_values_to_be_between:age_days` | STALE | 0.3636 |
| Repaired | PASS | 9/9 | — | FRESH | 0.0417 |

## 4. Repair

- **source**: raw_records_json
- **rows**: 24
- **idempotent_rerun_identical**: PASS
- **trigger**: auto: quality gate / freshness failed
- **quality_gate_after_repair**: PASS

## 5. Analysis

- **Silent failure:** the corrupted pipeline still ran end-to-end without any exception, yet mean token F1 fell by 0.1412 and retrieval hit rate by 0.2000. Nothing in the serving path would have alerted on this.
- Most damaged question type: `summary` (token F1 −0.4706).
- **Detection:** the GX quality gate caught the corrupted batch (4 failed expectations), so it can block the batch before it reaches the vector store.
- **Recovery:** rebuilding from the raw lineage anchor (`data/raw/crossref_records.json`) fully restored the baseline metrics and the quality gate is green. The repair is idempotent: it always rebuilds from the immutable raw snapshot, so running it again yields the same dataset.
