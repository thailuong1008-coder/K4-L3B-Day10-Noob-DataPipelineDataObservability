from __future__ import annotations

from typing import Any

from core.utils import write_text


def _percent(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "N/A"


def _number(value: Any, decimals: int = 4) -> str:
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def _status(value: Any) -> str:
    return "PASS" if bool(value) else "FAIL"


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write a human-readable baseline report from pipeline artifacts."""
    gx_results = quality.get("results", [])
    expectation_rows = []
    for result in gx_results:
        config = result.get("expectation_config", {})
        expectation_type = result.get("expectation", config.get("type", "unknown"))
        kwargs = config.get("kwargs", {})
        column = result.get("column", kwargs.get("column", "table"))
        expectation_rows.append(
            f"| `{expectation_type}` | `{column}` | {_status(result.get('success'))} |"
        )
    if not expectation_rows:
        expectation_rows.append("| No expectation results | - | FAIL |")

    ragas = metrics.get("ragas", {})
    ragas_status = ragas.get("skipped") or ragas.get("error") or "Completed"
    lines = [
        "# Phase 1 — Baseline Pipeline Report",
        "",
        "## Source and dataset",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Run date (UTC) | `{source_summary.get('run_date', 'N/A')}` |",
        f"| Source | {source_summary.get('source_api', 'N/A')} |",
        f"| Query | {source_summary.get('source_query', 'N/A')} |",
        f"| Raw records | {source_summary.get('total_raw_records', 0)} |",
        f"| Clean rows | {source_summary.get('total_clean_rows', 0)} |",
        "",
        "## Baseline RAG metrics",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Evaluation samples | {metrics.get('samples', 0)} |",
        f"| Retrieval Hit Rate | {_percent(metrics.get('retrieval_hit_rate'))} |",
        f"| Mean Token F1 | {_number(metrics.get('mean_token_f1'))} |",
        f"| Judge Accuracy | {_percent(metrics.get('judge_accuracy'))} |",
        f"| Mean Judge Score | {_number(metrics.get('mean_judge_score'), 2)} / 5 |",
        f"| Ragas | {ragas_status} |",
        "",
        "## Great Expectations quality gate",
        "",
        f"Overall status: **{_status(quality.get('success'))}**",
        "",
        "| Expectation | Column | Status |",
        "|---|---|---|",
        *expectation_rows,
        "",
        "## Freshness SLA",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Status | {_status(freshness.get('is_fresh'))} |",
        f"| Threshold | {freshness.get('threshold_days', 'N/A')} days |",
        f"| Maximum stale ratio | {_percent(freshness.get('max_stale_ratio'))} |",
        f"| Stale rows | {freshness.get('stale_rows', 0)} / {freshness.get('total_rows', 0)} |",
        f"| Stale ratio | {_percent(freshness.get('stale_ratio'))} |",
        f"| Latest publication | {freshness.get('latest_published', 'N/A')} |",
        f"| Oldest publication | {freshness.get('oldest_published', 'N/A')} |",
        "",
    ]
    write_text(report_path, "\n".join(lines))


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    baseline_quality: dict[str, Any] | None = None,
) -> None:
    """Write the Baseline/Corrupted/Repaired comparison report."""
    baseline_quality = baseline_quality or {"success": True}

    def delta(before: Any, after: Any) -> str:
        try:
            return f"{float(after) - float(before):+.2%}"
        except (TypeError, ValueError):
            return "N/A"

    baseline_hit = baseline_metrics.get("retrieval_hit_rate")
    corrupted_hit = corrupted_metrics.get("retrieval_hit_rate")
    repaired_hit = repaired_metrics.get("retrieval_hit_rate")
    baseline_f1 = baseline_metrics.get("mean_token_f1")
    corrupted_f1 = corrupted_metrics.get("mean_token_f1")
    repaired_f1 = repaired_metrics.get("mean_token_f1")

    lines = [
        "# Data Corruption and Recovery Report",
        "",
        "## Three-state comparison",
        "",
        "| Metric | Baseline | Corrupted | Repaired | Corruption delta | Recovery delta |",
        "|---|---:|---:|---:|---:|---:|",
        (
            f"| Retrieval Hit Rate | {_percent(baseline_hit)} | {_percent(corrupted_hit)} | "
            f"{_percent(repaired_hit)} | {delta(baseline_hit, corrupted_hit)} | "
            f"{delta(corrupted_hit, repaired_hit)} |"
        ),
        (
            f"| Mean Token F1 | {_number(baseline_f1)} | {_number(corrupted_f1)} | "
            f"{_number(repaired_f1)} | {delta(baseline_f1, corrupted_f1)} | "
            f"{delta(corrupted_f1, repaired_f1)} |"
        ),
        (
            f"| Judge Accuracy | {_percent(baseline_metrics.get('judge_accuracy'))} | "
            f"{_percent(corrupted_metrics.get('judge_accuracy'))} | "
            f"{_percent(repaired_metrics.get('judge_accuracy'))} | "
            f"{delta(baseline_metrics.get('judge_accuracy'), corrupted_metrics.get('judge_accuracy'))} | "
            f"{delta(corrupted_metrics.get('judge_accuracy'), repaired_metrics.get('judge_accuracy'))} |"
        ),
        (
            f"| Quality Gate | {_status(baseline_quality.get('success'))} | "
            f"{_status(corrupted_quality.get('success'))} | {_status(repaired_quality.get('success'))} | - | - |"
        ),
        (
            f"| Freshness SLA | Recorded in Phase 1 | {_status(corrupted_freshness.get('is_fresh'))} | "
            f"{_status(repaired_freshness.get('is_fresh'))} | - | - |"
        ),
        "",
        "## Freshness evidence",
        "",
        "| State | Stale rows | Total rows | Stale ratio | Threshold | Status |",
        "|---|---:|---:|---:|---:|---|",
        (
            f"| Corrupted | {corrupted_freshness.get('stale_rows', 0)} | "
            f"{corrupted_freshness.get('total_rows', 0)} | "
            f"{_percent(corrupted_freshness.get('stale_ratio'))} | "
            f"{_percent(corrupted_freshness.get('max_stale_ratio'))} | "
            f"{_status(corrupted_freshness.get('is_fresh'))} |"
        ),
        (
            f"| Repaired | {repaired_freshness.get('stale_rows', 0)} | "
            f"{repaired_freshness.get('total_rows', 0)} | "
            f"{_percent(repaired_freshness.get('stale_ratio'))} | "
            f"{_percent(repaired_freshness.get('max_stale_ratio'))} | "
            f"{_status(repaired_freshness.get('is_fresh'))} |"
        ),
        "",
        "## Interpretation",
        "",
        (
            f"Corruption changed retrieval Hit Rate by {delta(baseline_hit, corrupted_hit)} and Mean Token F1 "
            f"by {delta(baseline_f1, corrupted_f1)} relative to baseline. This is a silent failure: the "
            "pipeline can still return answers while data quality and retrieval performance degrade."
        ),
        "",
        (
            f"Rebuilding from the raw snapshot changed Hit Rate by {delta(corrupted_hit, repaired_hit)} and "
            f"Mean Token F1 by {delta(corrupted_f1, repaired_f1)} relative to the corrupted state. The repaired "
            f"quality gate is {_status(repaired_quality.get('success'))}."
        ),
        "",
    ]
    write_text(report_path, "\n".join(lines))
