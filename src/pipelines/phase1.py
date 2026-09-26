from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, freshness_report_path, run_data_quality_checks
from observability.reporting import generate_phase1_report, per_type_breakdown
from retrieval.index import LocalEmbeddingIndex

DEMO_QUESTIONS_LIMIT = 2


def save_clean_artifacts(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    write_csv(df, csv_path)
    # to_json -> json.loads de ep kieu numpy ve kieu Python chuan.
    write_json(json_path, json.loads(df.to_json(orient="records", force_ascii=False)))


def load_clean_dataframe(json_path: Path) -> pd.DataFrame:
    return pd.DataFrame(read_json(json_path))


def _load_or_fetch_records(settings: Settings):
    if settings.paths.raw_records_json.exists() and not settings.refresh_source:
        return load_raw_records(settings.paths.raw_records_json)
    return fetch_source_records(settings)


def _run_agent_demo(settings: Settings, index: LocalEmbeddingIndex, test_set: list[dict[str, Any]]) -> dict[str, Any]:
    questions = [item["question"] for item in test_set[:DEMO_QUESTIONS_LIMIT]]
    try:
        from retrieval.agent import build_agent, run_agent_question

        agent = build_agent(settings, index)
        answers = [{"question": q, "answer": run_agent_question(agent, q)} for q in questions]
        payload = {"status": "ok", "provider": settings.llm_provider, "answers": answers}
    except Exception as exc:  # LLM key thieu / provider khong ho tro tool-calling -> khong chan pipeline.
        payload = {"status": "skipped", "provider": settings.llm_provider, "reason": str(exc), "questions": questions}
    write_json(settings.paths.demo_answers, payload)
    return payload


def main() -> None:
    settings = load_settings()
    run_date = now_utc()
    print(f"[phase1] run_date={run_date.isoformat()} provider={settings.llm_provider}")

    records = _load_or_fetch_records(settings)
    print(f"[phase1] raw records: {len(records)}")

    clean_df = build_clean_dataframe(records, run_date)
    save_clean_artifacts(clean_df, settings.paths.clean_csv, settings.paths.clean_json)
    print(f"[phase1] clean rows: {len(clean_df)} -> {settings.paths.clean_csv.name}, {settings.paths.clean_json.name}")

    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, freshness_report_path(settings, "baseline"))
    print(f"[phase1] quality success={quality['success']} fresh={freshness['is_fresh']}")
    if not quality["success"]:
        print(f"[phase1] WARNING failed expectations: {quality['failed_expectations']}")

    index = LocalEmbeddingIndex.build(clean_df, settings, settings.paths.embeddings_json)
    print(f"[phase1] chroma collection '{index.collection_name}' indexed {index.collection.count()} docs")

    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        test_set = build_test_set(clean_df, settings.paths.eval_testset)
    else:
        test_set = read_json(settings.paths.eval_testset)
    print(f"[phase1] test set: {len(test_set)} questions")

    bundle = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
    )
    metrics = bundle.summary
    print(
        f"[phase1] hit_rate={metrics['retrieval_hit_rate']:.4f} token_f1={metrics['mean_token_f1']:.4f} "
        f"judge_acc={metrics['judge_accuracy']:.4f}"
    )

    demo = _run_agent_demo(settings, index, test_set)
    print(f"[phase1] agent demo: {demo['status']}")

    source_summary = {
        "source_api": settings.source_api,
        "query": settings.source_query,
        "filter": settings.source_filter,
        "raw_response": settings.paths.raw_api_response.relative_to(settings.paths.project_dir).as_posix(),
        "raw_records": settings.paths.raw_records_json.relative_to(settings.paths.project_dir).as_posix(),
        "raw_record_count": len(records),
        "clean_row_count": len(clean_df),
        "chroma_collection": index.collection_name,
        "embedding_model": settings.embedding_model,
        "llm_provider": settings.llm_provider,
        "agent_demo": demo["status"],
    }
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary,
        metrics,
        quality,
        freshness,
        per_type=per_type_breakdown(bundle.answers),
    )
    print(f"[phase1] report -> {settings.paths.baseline_report.relative_to(settings.paths.project_dir).as_posix()}")


if __name__ == "__main__":
    main()
