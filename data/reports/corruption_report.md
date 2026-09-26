# Corruption Flow Report

## Retrieval Evaluation Comparison

| Metric | Baseline | Corrupted | Repaired |
|---|---:|---:|---:|
| Retrieval hit rate | 1.0 | 0.6 | 1.0 |
| Mean token F1 | 0.3965341926244182 | 0.12292886146706744 | 0.3965341926244182 |
| Judge accuracy | 0.5 | 0.1 | 0.5 |
| Mean judge score | 2.4 | 1.2 | 2.4 |

## Data Quality

| Dataset | Passed | Total rows |
|---|---|---:|
| Corrupted | False | 21 |
| Repaired | False | 24 |

## Freshness

| Dataset | Latest published | Oldest published | Stale rows | Is fresh |
|---|---|---|---:|---|
| Corrupted | 2026-06-12T00:00:00+00:00 | 2026-03-28T00:00:00+00:00 | 1 | False |
| Repaired | 2026-07-22T00:00:00+00:00 | 2026-03-28T00:00:00+00:00 | 1 | False |
