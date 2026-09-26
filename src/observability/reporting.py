from __future__ import annotations

from statistics import mean
from typing import Any

from core.utils import now_utc, write_text

METRIC_KEYS = ["retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"]


def per_type_breakdown(answers: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Gom hit rate / token F1 theo question_type tu file answers cua evaluate_pipeline."""
    breakdown: dict[str, dict[str, float]] = {}
    for question_type in sorted({item["question_type"] for item in answers}):
        items = [item for item in answers if item["question_type"] == question_type]
        breakdown[question_type] = {
            "samples": len(items),
            "retrieval_hit_rate": mean(1.0 if item["retrieval_hit"] else 0.0 for item in items),
            "mean_token_f1": mean(item["token_f1"] for item in items),
        }
    return breakdown


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    if isinstance(value, float):
        return f"{value:.4f}"
    return "-" if value is None else str(value)


def _as_float(value: Any) -> Any:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else value


def _delta(new: Any, base: Any) -> str:
    if isinstance(new, (int, float)) and isinstance(base, (int, float)) and not isinstance(new, bool):
        return f"{new - base:+.4f}"
    return "-"


def _quality_lines(quality: dict[str, Any]) -> list[str]:
    lines = [
        f"- Engine: `{quality.get('engine')}` — suite `{quality.get('suite_name')}`",
        f"- Overall: **{_fmt(quality.get('success'))}** "
        f"({quality.get('successful_expectations')}/{quality.get('evaluated_expectations')} expectations passed, "
        f"{quality.get('row_count')} rows)",
        "",
        "| Expectation | Column | Result | Observed / Unexpected |",
        "|---|---|:---:|---|",
    ]
    for check in quality.get("checks", []):
        observed = check.get("observed_value")
        if observed is None and check.get("unexpected_count") is not None:
            observed = f"{check['unexpected_count']} unexpected ({(check.get('unexpected_percent') or 0):.1f}%)"
        lines.append(
            f"| `{check['expectation']}` | {check['kwargs'].get('column', '(table)')} | "
            f"{_fmt(check['success'])} | {_fmt(observed)} |"
        )
    return lines


def _freshness_lines(freshness: dict[str, Any]) -> list[str]:
    return [
        f"- SLA: at most {freshness.get('max_stale_ratio', 0.25):.0%} of papers older than "
        f"{freshness.get('threshold_days')} days",
        f"- Latest published: `{freshness.get('latest_published')}` — oldest: `{freshness.get('oldest_published')}`",
        f"- Stale rows: {freshness.get('stale_rows')}/{freshness.get('total_rows')} "
        f"(ratio {_fmt(freshness.get('stale_ratio'))})",
        f"- Status: **{'FRESH' if freshness.get('is_fresh') else 'STALE'}**",
    ]


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
    per_type: dict[str, dict[str, float]] | None = None,
) -> None:
    """Viet markdown report cho baseline phase."""
    lines = [
        "# Phase 1 Report — Baseline RAG Pipeline",
        "",
        f"_Generated at {now_utc().isoformat()}_",
        "",
        "## 1. Source & Lineage",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    lines += [f"| {key} | {_fmt(value)} |" for key, value in source_summary.items()]
    lines += [
        "",
        "## 2. Evaluation Metrics (baseline)",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    lines += [f"| samples | {_fmt(metrics.get('samples'))} |"]
    lines += [f"| {key} | {_fmt(_as_float(metrics.get(key)))} |" for key in METRIC_KEYS]
    if per_type:
        lines += ["", "### By question type", "", "| Type | Samples | Hit rate | Token F1 |", "|---|---:|---:|---:|"]
        lines += [
            f"| {name} | {row['samples']} | {row['retrieval_hit_rate']:.4f} | {row['mean_token_f1']:.4f} |"
            for name, row in per_type.items()
        ]
    ragas = metrics.get("ragas")
    if isinstance(ragas, dict) and ragas:
        lines += ["", f"Ragas: `{ragas}`"]
    lines += ["", "## 3. Data Quality Gate (Great Expectations 1.x)", "", *_quality_lines(quality)]
    lines += ["", "## 4. Freshness SLA", "", *_freshness_lines(freshness)]
    lines += [
        "",
        "## 5. Conclusion",
        "",
        (
            "Baseline data passes the quality gate and freshness SLA; these numbers are the reference "
            "point for the corruption experiment."
            if quality.get("success") and freshness.get("is_fresh")
            else "Baseline data does NOT fully pass the quality gate / freshness SLA — investigate before serving."
        ),
        "",
    ]
    write_text(report_path, "\n".join(lines))


def build_comparison_table(
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
) -> list[str]:
    lines = [
        "| Metric | Baseline | Corrupted | Repaired | Δ Corrupted | Δ Repaired |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key in METRIC_KEYS:
        base, bad, fixed = (_as_float(m.get(key)) for m in (baseline_metrics, corrupted_metrics, repaired_metrics))
        lines.append(
            f"| {key} | {_fmt(base)} | {_fmt(bad)} | {_fmt(fixed)} | {_delta(bad, base)} | {_delta(fixed, base)} |"
        )
    return lines


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    corruption_log: dict[str, Any] | None = None,
    per_type: dict[str, dict[str, dict[str, float]]] | None = None,
    repair_summary: dict[str, Any] | None = None,
) -> None:
    """Viet markdown report so sanh baseline/corrupted/repaired."""
    lines = [
        "# Corruption Report — Baseline vs Corrupted vs Repaired",
        "",
        f"_Generated at {now_utc().isoformat()}_",
        "",
        "All three states are evaluated on the same test set (`data/eval/test_set.json`).",
        "",
        "## 1. Metrics comparison",
        "",
        *build_comparison_table(baseline_metrics, corrupted_metrics, repaired_metrics),
    ]

    if per_type:
        lines += [
            "",
            "### Token F1 by question type",
            "",
            "| Type | Baseline | Corrupted | Repaired |",
            "|---|---:|---:|---:|",
        ]
        for question_type in per_type.get("baseline", {}):
            cells = [per_type.get(state, {}).get(question_type, {}).get("mean_token_f1") for state in ("baseline", "corrupted", "repaired")]
            lines.append(f"| {question_type} | " + " | ".join(_fmt(cell) for cell in cells) + " |")

    if corruption_log:
        lines += [
            "",
            "## 2. Injected corruptions",
            "",
            f"Seed `{corruption_log.get('seed')}` — rows {corruption_log.get('input_rows')} → {corruption_log.get('output_rows')}.",
            "",
            "| # | Type | Rows | Description |",
            "|---:|---|---:|---|",
        ]
        for number, entry in enumerate(corruption_log.get("corruptions", []), start=1):
            lines.append(f"| {number} | `{entry['corruption_type']}` | {entry['affected_rows']} | {entry['description']} |")

    lines += [
        "",
        "## 3. Data Quality Gate",
        "",
        "| State | GX success | Passed | Failed expectations | Freshness | Stale ratio |",
        "|---|:---:|---:|---|:---:|---:|",
    ]
    for state, quality, freshness in [
        ("Corrupted", corrupted_quality, corrupted_freshness),
        ("Repaired", repaired_quality, repaired_freshness),
    ]:
        failed = ", ".join(f"`{item}`" for item in quality.get("failed_expectations", [])) or "—"
        lines.append(
            f"| {state} | {_fmt(quality.get('success'))} | "
            f"{quality.get('successful_expectations')}/{quality.get('evaluated_expectations')} | {failed} | "
            f"{'FRESH' if freshness.get('is_fresh') else 'STALE'} | {_fmt(freshness.get('stale_ratio'))} |"
        )

    if repair_summary:
        lines += ["", "## 4. Repair", ""]
        lines += [f"- **{key}**: {_fmt(value)}" for key, value in repair_summary.items()]

    lines += ["", "## 5. Analysis", "", *_analysis(baseline_metrics, corrupted_metrics, repaired_metrics, corrupted_quality, repaired_quality, per_type), ""]
    write_text(report_path, "\n".join(lines))


def _analysis(
    baseline: dict[str, Any],
    corrupted: dict[str, Any],
    repaired: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    per_type: dict[str, dict[str, dict[str, float]]] | None,
) -> list[str]:
    notes: list[str] = []
    f1_drop = baseline.get("mean_token_f1", 0) - corrupted.get("mean_token_f1", 0)
    hit_drop = baseline.get("retrieval_hit_rate", 0) - corrupted.get("retrieval_hit_rate", 0)
    notes.append(
        f"- **Silent failure:** the corrupted pipeline still ran end-to-end without any exception, yet "
        f"mean token F1 fell by {f1_drop:.4f} and retrieval hit rate by {hit_drop:.4f}. "
        "Nothing in the serving path would have alerted on this."
    )
    if per_type and "corrupted" in per_type:
        worst = sorted(
            per_type["baseline"],
            key=lambda qt: per_type["baseline"][qt]["mean_token_f1"] - per_type["corrupted"].get(qt, {}).get("mean_token_f1", 0),
            reverse=True,
        )
        if worst:
            top = worst[0]
            drop = per_type["baseline"][top]["mean_token_f1"] - per_type["corrupted"].get(top, {}).get("mean_token_f1", 0)
            notes.append(f"- Most damaged question type: `{top}` (token F1 −{drop:.4f}).")
    failed = corrupted_quality.get("failed_expectations", [])
    notes.append(
        f"- **Detection:** the GX quality gate {'caught' if not corrupted_quality.get('success') else 'did NOT catch'} "
        f"the corrupted batch ({len(failed)} failed expectations), so it can block the batch before it reaches the vector store."
    )
    recovered = all(
        abs(repaired.get(key, 0) - baseline.get(key, 0)) < 1e-9 for key in ("retrieval_hit_rate", "mean_token_f1")
    )
    notes.append(
        f"- **Recovery:** rebuilding from the raw lineage anchor (`data/raw/crossref_records.json`) "
        f"{'fully restored' if recovered else 'partially restored'} the baseline metrics and the quality gate is "
        f"{'green' if repaired_quality.get('success') else 'still red'}. The repair is idempotent: it always rebuilds "
        "from the immutable raw snapshot, so running it again yields the same dataset."
    )
    return notes
