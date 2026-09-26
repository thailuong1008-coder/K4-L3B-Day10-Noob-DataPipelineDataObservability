# Phase 1 Report — Baseline RAG Pipeline

_Generated at 2026-09-26T04:40:44.665428+00:00_

## 1. Source & Lineage

| Field | Value |
|---|---|
| source_api | Crossref REST API |
| query | agentic retrieval augmented generation large language model |
| filter | from-pub-date:2026-03-30,has-abstract:true |
| raw_response | data/raw/crossref_response.json |
| raw_records | data/raw/crossref_records.json |
| raw_record_count | 24 |
| clean_row_count | 24 |
| chroma_collection | papers-baseline |
| embedding_model | sentence-transformers/all-MiniLM-L6-v2 |
| llm_provider | gemini |
| agent_demo | ok |

## 2. Evaluation Metrics (baseline)

| Metric | Value |
|---|---|
| samples | 10 |
| retrieval_hit_rate | 1.0000 |
| mean_token_f1 | 1.0000 |
| judge_accuracy | 1.0000 |
| mean_judge_score | 5.0000 |

### By question type

| Type | Samples | Hit rate | Token F1 |
|---|---:|---:|---:|
| authors | 3 | 1.0000 | 1.0000 |
| categories | 2 | 1.0000 | 1.0000 |
| date | 2 | 1.0000 | 1.0000 |
| summary | 3 | 1.0000 | 1.0000 |

Ragas: `{'skipped': 'Set RUN_RAGAS=1 to enable the slower Ragas pass.'}`

## 3. Data Quality Gate (Great Expectations 1.x)

- Engine: `great_expectations 1.23.2` — suite `papers_baseline_suite`
- Overall: **PASS** (9/9 expectations passed, 24 rows)

| Expectation | Column | Result | Observed / Unexpected |
|---|---|:---:|---|
| `expect_table_row_count_to_be_between` | (table) | PASS | 24 |
| `expect_column_values_to_not_be_null` | paper_id | PASS | 0 unexpected (0.0%) |
| `expect_column_values_to_be_unique` | paper_id | PASS | 0 unexpected (0.0%) |
| `expect_column_values_to_not_be_null` | title | PASS | 0 unexpected (0.0%) |
| `expect_column_value_lengths_to_be_between` | title | PASS | 0 unexpected (0.0%) |
| `expect_column_values_to_not_be_null` | summary | PASS | 0 unexpected (0.0%) |
| `expect_column_value_lengths_to_be_between` | summary | PASS | 0 unexpected (0.0%) |
| `expect_column_values_to_not_be_null` | text_for_embedding | PASS | 0 unexpected (0.0%) |
| `expect_column_values_to_be_between` | age_days | PASS | 1 unexpected (4.2%) |

## 4. Freshness SLA

- SLA: at most 25% of papers older than 180 days
- Latest published: `2026-07-22` — oldest: `2026-03-28`
- Stale rows: 1/24 (ratio 0.0417)
- Status: **FRESH**

## 5. Conclusion

Baseline data passes the quality gate and freshness SLA; these numbers are the reference point for the corruption experiment.
