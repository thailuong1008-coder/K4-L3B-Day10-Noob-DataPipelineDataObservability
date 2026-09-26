from __future__ import annotations

from pathlib import Path
from typing import Any


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Generate markdown report for the baseline phase."""

    lines = [
        "# Phase 1 Baseline Report",
        "",
        "## Source Summary",
        "",
        f"- Source: {source_summary.get('source', 'N/A')}",
        f"- Query: {source_summary.get('query', 'N/A')}",
        f"- Total rows: {source_summary.get('total_rows', 'N/A')}",
        "",
        "## Retrieval and Evaluation Metrics",
        "",
        f"- Samples: {metrics.get('samples', 'N/A')}",
        f"- Retrieval hit rate: {metrics.get('retrieval_hit_rate', 'N/A')}",
        f"- Mean token F1: {metrics.get('mean_token_f1', 'N/A')}",
        f"- Judge accuracy: {metrics.get('judge_accuracy', 'N/A')}",
        f"- Mean judge score: {metrics.get('mean_judge_score', 'N/A')}",
        "",
        "## Data Quality",
        "",
        f"- Passed: {quality.get('passed', 'N/A')}",
        f"- Total rows: {quality.get('total_rows', 'N/A')}",
        "",
        "## Freshness",
        "",
        f"- Latest published: {freshness.get('latest_published', 'N/A')}",
        f"- Oldest published: {freshness.get('oldest_published', 'N/A')}",
        f"- Stale rows: {freshness.get('stale_rows', 'N/A')}",
        f"- Total rows: {freshness.get('total_rows', 'N/A')}",
        f"- Is fresh: {freshness.get('is_fresh', 'N/A')}",
        "",
    ]

    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Generate markdown comparison report."""

    lines = [
        "# Corruption Flow Report",
        "",
        "## Retrieval Evaluation Comparison",
        "",
        "| Metric | Baseline | Corrupted | Repaired |",
        "|---|---:|---:|---:|",
        (
            f"| Retrieval hit rate | "
            f"{baseline_metrics.get('retrieval_hit_rate', 'N/A')} | "
            f"{corrupted_metrics.get('retrieval_hit_rate', 'N/A')} | "
            f"{repaired_metrics.get('retrieval_hit_rate', 'N/A')} |"
        ),
        (
            f"| Mean token F1 | "
            f"{baseline_metrics.get('mean_token_f1', 'N/A')} | "
            f"{corrupted_metrics.get('mean_token_f1', 'N/A')} | "
            f"{repaired_metrics.get('mean_token_f1', 'N/A')} |"
        ),
        (
            f"| Judge accuracy | "
            f"{baseline_metrics.get('judge_accuracy', 'N/A')} | "
            f"{corrupted_metrics.get('judge_accuracy', 'N/A')} | "
            f"{repaired_metrics.get('judge_accuracy', 'N/A')} |"
        ),
        (
            f"| Mean judge score | "
            f"{baseline_metrics.get('mean_judge_score', 'N/A')} | "
            f"{corrupted_metrics.get('mean_judge_score', 'N/A')} | "
            f"{repaired_metrics.get('mean_judge_score', 'N/A')} |"
        ),
        "",
        "## Data Quality",
        "",
        "| Dataset | Passed | Total rows |",
        "|---|---|---:|",
        (
            f"| Corrupted | "
            f"{corrupted_quality.get('passed', 'N/A')} | "
            f"{corrupted_quality.get('total_rows', 'N/A')} |"
        ),
        (
            f"| Repaired | "
            f"{repaired_quality.get('passed', 'N/A')} | "
            f"{repaired_quality.get('total_rows', 'N/A')} |"
        ),
        "",
        "## Freshness",
        "",
        "| Dataset | Latest published | Oldest published | Stale rows | Is fresh |",
        "|---|---|---|---:|---|",
        (
            f"| Corrupted | "
            f"{corrupted_freshness.get('latest_published', 'N/A')} | "
            f"{corrupted_freshness.get('oldest_published', 'N/A')} | "
            f"{corrupted_freshness.get('stale_rows', 'N/A')} | "
            f"{corrupted_freshness.get('is_fresh', 'N/A')} |"
        ),
        (
            f"| Repaired | "
            f"{repaired_freshness.get('latest_published', 'N/A')} | "
            f"{repaired_freshness.get('oldest_published', 'N/A')} | "
            f"{repaired_freshness.get('stale_rows', 'N/A')} | "
            f"{repaired_freshness.get('is_fresh', 'N/A')} |"
        ),
        "",
    ]

    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")