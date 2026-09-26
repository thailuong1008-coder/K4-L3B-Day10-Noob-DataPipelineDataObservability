from __future__ import annotations

from datetime import datetime, timezone

from core.config import load_settings
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import (
    build_freshness_report,
    run_data_quality_checks,
)
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set


def main() -> None:
    settings = load_settings()

    # 1. Load or fetch raw records.
    raw_records = fetch_source_records(settings)

    # 2. Clean records into the canonical dataframe.
    run_date = datetime.now(timezone.utc)
    clean_df = build_clean_dataframe(
        raw_records,
        run_date,
    )

    # 3. Save clean baseline artifacts.
    settings.paths.clean_csv.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    clean_df.to_csv(
        settings.paths.clean_csv,
        index=False,
    )

    clean_df.to_json(
        settings.paths.clean_json,
        orient="records",
        force_ascii=False,
        indent=2,
    )

    # 4. Build baseline Chroma collection.
    index = LocalEmbeddingIndex(settings)

    index.build_from_dataframe(
        clean_df,
        settings.baseline_collection_name,
    )

    # 5. Create evaluation set if it does not exist.
    if not settings.paths.eval_testset.exists():
        settings.paths.eval_testset.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        build_test_set(
            clean_df,
            settings.paths.eval_testset,
        )

    # 6. Evaluate baseline retrieval and QA.
    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
        collection_name=settings.baseline_collection_name,
    )

    # 7. Run data-quality checks.
    quality = run_data_quality_checks(
        clean_df,
        settings,
        "baseline_quality_report",
    )

    # 8. Run freshness checks.
    freshness_path = (
        settings.paths.quality_dir / "baseline_freshness_report.json"
    )

    freshness = build_freshness_report(
        clean_df,
        settings,
        freshness_path,
    )

    # 9. Generate Phase 1 markdown report.
    source_summary = {
        "source": "Crossref REST API / snapshot",
        "query": settings.source_query,
        "total_rows": len(clean_df),
    }

    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary,
        evaluation.summary,
        quality,
        freshness,
    )

    # 10. Print a concise completion summary.
    print("Phase 1 baseline pipeline completed.")
    print(f"Rows: {len(clean_df)}")
    print(
        "Retrieval hit rate:",
        evaluation.summary["retrieval_hit_rate"],
    )
    print(
        "Mean token F1:",
        evaluation.summary["mean_token_f1"],
    )
    print(
        "Judge accuracy:",
        evaluation.summary["judge_accuracy"],
    )
    print(
        "Mean judge score:",
        evaluation.summary["mean_judge_score"],
    )
    print(f"Baseline metrics: {settings.paths.baseline_metrics}")
    print(f"Baseline answers: {settings.paths.baseline_answers}")
    print(f"Baseline report: {settings.paths.baseline_report}")


if __name__ == "__main__":
    main()