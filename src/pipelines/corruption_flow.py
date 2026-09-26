from __future__ import annotations

from datetime import datetime, timezone
import json

from core.config import load_settings
from core.utils import write_json
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import (
    build_freshness_report,
    run_data_quality_checks,
)
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex
from evaluation.metrics import evaluate_pipeline


def main() -> None:
    settings = load_settings()

    # 1. Load raw records and rebuild the clean baseline dataframe.
    raw_records = load_raw_records(settings.paths.raw_records_json)
    run_date = datetime.now(timezone.utc)

    baseline_df = build_clean_dataframe(
        raw_records,
        run_date,
    )

    # 2. Create corrupted dataframe.
    corrupted_df = corrupt_clean_dataframe(
        baseline_df,
        settings.paths.corruption_log,
    )

    # 3. Save corrupted artifacts.
    settings.paths.corrupted_clean_csv.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    corrupted_df.to_csv(
        settings.paths.corrupted_clean_csv,
        index=False,
    )

    corrupted_df.to_json(
        settings.paths.corrupted_clean_json,
        orient="records",
        force_ascii=False,
        indent=2,
    )

    # 4. Build corrupted index and evaluate.
    index = LocalEmbeddingIndex(settings)

    index.build_from_dataframe(
        corrupted_df,
        settings.corrupted_collection_name,
    )

    corrupted_bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
        collection_name=settings.corrupted_collection_name,
    )

    # 5. Run quality and freshness checks on corrupted data.
    corrupted_quality = run_data_quality_checks(
        corrupted_df,
        settings,
        "corrupted_quality_report",
    )

    corrupted_freshness = build_freshness_report(
        corrupted_df,
        settings,
        settings.paths.freshness_report,
    )

    # 6. Repair from the original raw records.
    repaired_df = build_clean_dataframe(
        raw_records,
        run_date,
    )

    # 7. Save repaired artifacts.
    repaired_df.to_csv(
        settings.paths.repaired_clean_csv,
        index=False,
    )

    repaired_df.to_json(
        settings.paths.repaired_clean_json,
        orient="records",
        force_ascii=False,
        indent=2,
    )

    # 8. Build repaired index and evaluate.
    index.build_from_dataframe(
        repaired_df,
        settings.repaired_collection_name,
    )

    repaired_bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
        collection_name=settings.repaired_collection_name,
    )

    # 9. Run quality and freshness checks on repaired data.
    repaired_quality = run_data_quality_checks(
        repaired_df,
        settings,
        "repaired_quality_report",
    )

    repaired_freshness_path = (
        settings.paths.quality_dir / "repaired_freshness_report.json"
    )

    repaired_freshness = build_freshness_report(
        repaired_df,
        settings,
        repaired_freshness_path,
    )

    # 10. Load baseline metrics for the comparison report.
    if settings.paths.baseline_metrics.exists():
        with settings.paths.baseline_metrics.open(
            "r",
            encoding="utf-8",
        ) as f:
            baseline_metrics = json.load(f)
    else:
        baseline_metrics = {
            "samples": 0,
            "retrieval_hit_rate": 0.0,
            "mean_token_f1": 0.0,
            "judge_accuracy": 0.0,
            "mean_judge_score": 0.0,
        }

    # 11. Generate comparison report.
    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics,
        corrupted_bundle.summary,
        repaired_bundle.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
    )

    print("Corruption flow completed.")
    print(f"Baseline rows: {len(baseline_df)}")
    print(f"Corrupted rows: {len(corrupted_df)}")
    print(f"Repaired rows: {len(repaired_df)}")
    print(
        "Corrupted retrieval hit rate:",
        corrupted_bundle.summary["retrieval_hit_rate"],
    )
    print(
        "Repaired retrieval hit rate:",
        repaired_bundle.summary["retrieval_hit_rate"],
    )
    print(f"Corrupted metrics: {settings.paths.corrupted_metrics}")
    print(f"Repaired metrics: {settings.paths.repaired_metrics}")
    print(f"Comparison report: {settings.paths.comparison_report}")


if __name__ == "__main__":
    main()