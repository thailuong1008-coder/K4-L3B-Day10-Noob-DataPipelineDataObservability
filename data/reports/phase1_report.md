# Phase 1 — Baseline Pipeline Report

## Source and dataset

| Field | Value |
|---|---|
| Run date (UTC) | `2026-09-26T04:00:56.311569+00:00` |
| Source | Crossref REST API |
| Query | agentic retrieval augmented generation large language model |
| Raw records | 24 |
| Clean rows | 24 |

## Baseline RAG metrics

| Metric | Result |
|---|---:|
| Evaluation samples | 10 |
| Retrieval Hit Rate | 100.00% |
| Mean Token F1 | 1.0000 |
| Judge Accuracy | 100.00% |
| Mean Judge Score | 5.00 / 5 |
| Ragas | Set RUN_RAGAS=1 to enable the slower Ragas pass. |

## Great Expectations quality gate

Overall status: **PASS**

| Expectation | Column | Status |
|---|---|---|
| `expect_table_row_count_to_be_between` | `table` | PASS |
| `expect_column_values_to_not_be_null` | `paper_id` | PASS |
| `expect_column_values_to_not_be_null` | `title` | PASS |
| `expect_column_values_to_not_be_null` | `text_for_embedding` | PASS |
| `expect_column_values_to_be_unique` | `paper_id` | PASS |
| `expect_column_value_lengths_to_be_between` | `summary` | PASS |

## Freshness SLA

| Metric | Result |
|---|---:|
| Status | PASS |
| Threshold | 180 days |
| Maximum stale ratio | 25.00% |
| Stale rows | 1 / 24 |
| Stale ratio | 4.17% |
| Latest publication | 2026-07-22 |
| Oldest publication | 2026-03-28 |
