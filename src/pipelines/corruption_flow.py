from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records, parse_crossref_payload
from observability.quality import build_freshness_report, freshness_report_path, run_data_quality_checks
from observability.reporting import build_comparison_table, generate_corruption_report, per_type_breakdown
from pipelines import phase1
from retrieval.index import LocalEmbeddingIndex


def _evaluate(settings: Settings, df: pd.DataFrame, embeddings_path, metrics_path, answers_path):
    index = LocalEmbeddingIndex.build(df, settings, embeddings_path)
    bundle = evaluate_pipeline(settings, index, settings.paths.eval_testset, metrics_path, answers_path)
    return index, bundle


def _rebuild_from_raw(settings: Settings, run_date: datetime) -> tuple[pd.DataFrame, str]:
    """Rebuild clean data tu lineage anchor. Uu tien raw records, fallback ve raw API response."""
    try:
        records = load_raw_records(settings.paths.raw_records_json)
        source = "raw_records_json"
    except Exception:
        records = []
    if not records:
        records = parse_crossref_payload(read_json(settings.paths.raw_api_response))
        source = "raw_api_response"
    return build_clean_dataframe(records, run_date), source


def repair_dataset(settings: Settings, run_date: datetime) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Idempotent repair: rebuild tu raw snapshot bat bien, xac minh bang quality gate + chay lai lan 2."""
    repaired_df, source = _rebuild_from_raw(settings, run_date)
    second_pass, _ = _rebuild_from_raw(settings, run_date)
    idempotent = repaired_df.drop(columns=["authors", "categories"]).equals(
        second_pass.drop(columns=["authors", "categories"])
    )
    phase1.save_clean_artifacts(repaired_df, settings.paths.repaired_clean_csv, settings.paths.repaired_clean_json)
    return repaired_df, {"source": source, "rows": len(repaired_df), "idempotent_rerun_identical": idempotent}


def main() -> None:
    settings = load_settings()
    run_date = now_utc()

    if not settings.paths.baseline_metrics.exists() or not settings.paths.clean_json.exists():
        print("[corruption] baseline artifacts missing -> running phase 1 first")
        phase1.main()

    baseline_metrics = read_json(settings.paths.baseline_metrics)
    baseline_answers = read_json(settings.paths.baseline_answers)
    clean_df = phase1.load_clean_dataframe(settings.paths.clean_json)
    print(f"[corruption] baseline rows={len(clean_df)} hit_rate={baseline_metrics['retrieval_hit_rate']:.4f}")

    # --- Corrupt ---
    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    phase1.save_clean_artifacts(corrupted_df, settings.paths.corrupted_clean_csv, settings.paths.corrupted_clean_json)
    corruption_log = read_json(settings.paths.corruption_log)
    print(f"[corruption] injected {len(corruption_log['corruptions'])} corruption types -> {len(corrupted_df)} rows")

    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(corrupted_df, settings, freshness_report_path(settings, "corrupted"))
    print(
        f"[corruption] quality gate success={corrupted_quality['success']} "
        f"failed={corrupted_quality['failed_expectations']} fresh={corrupted_freshness['is_fresh']}"
    )

    # Evaluate corrupted data (serve it anyway) to measure the silent failure.
    _, corrupted_bundle = _evaluate(
        settings,
        corrupted_df,
        settings.paths.corrupted_embeddings_json,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_answers,
    )

    # --- Self-healing: quality gate do -> tu dong repair tu raw ---
    gate_failed = not corrupted_quality["success"] or not corrupted_freshness["is_fresh"]
    print(f"[repair] trigger={'auto (quality gate failed)' if gate_failed else 'manual'}")
    repaired_df, repair_summary = repair_dataset(settings, run_date)
    repair_summary["trigger"] = "auto: quality gate / freshness failed" if gate_failed else "manual"

    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(repaired_df, settings, freshness_report_path(settings, "repaired"))
    repair_summary["quality_gate_after_repair"] = repaired_quality["success"]
    if not repaired_quality["success"]:
        raise RuntimeError(f"Repair failed the quality gate: {repaired_quality['failed_expectations']}")

    _, repaired_bundle = _evaluate(
        settings,
        repaired_df,
        settings.paths.repaired_embeddings_json,
        settings.paths.repaired_metrics,
        settings.paths.repaired_answers,
    )

    per_type = {
        "baseline": per_type_breakdown(baseline_answers),
        "corrupted": per_type_breakdown(corrupted_bundle.answers),
        "repaired": per_type_breakdown(repaired_bundle.answers),
    }
    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics,
        corrupted_bundle.summary,
        repaired_bundle.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
        corruption_log=corruption_log,
        per_type=per_type,
        repair_summary=repair_summary,
    )

    print()
    print("\n".join(build_comparison_table(baseline_metrics, corrupted_bundle.summary, repaired_bundle.summary)))
    print()
    print(f"[repair] {repair_summary}")
    print(f"[report] -> {settings.paths.comparison_report.relative_to(settings.paths.project_dir).as_posix()}")


if __name__ == "__main__":
    main()
