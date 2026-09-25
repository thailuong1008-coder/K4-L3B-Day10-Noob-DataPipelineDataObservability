from __future__ import annotations

import sys
from datetime import datetime
import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, write_csv, write_json
from ingestion.crossref import fetch_source_records, load_raw_records
from ingestion.cleaning import build_clean_dataframe
from retrieval.index import LocalEmbeddingIndex
from evaluation.testset import build_test_set
from evaluation.metrics import evaluate_pipeline
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.qa import answer_question


def log_step(step_num: int, total_steps: int, title: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] === STEP {step_num}/{total_steps}: {title} ===")


def run_phase1_pipeline(settings: Settings | None = None) -> dict:
    """End-to-end baseline pipeline for Phase 1.
    
    Orchestrated by Member 1 (Pipeline Integrator).
    Coordinates ingestion, cleaning, vector indexing, evaluation, and observability.
    """
    total_steps = 10

    # 1. Load settings
    log_step(1, total_steps, "Nạp cấu hình hệ thống (Settings & Paths)")
    if settings is None:
        settings = load_settings()
    print(f"  - Project Root: {settings.paths.project_dir}")
    print(f"  - LLM Provider: {settings.llm_provider} (Model: {settings.model_name})")
    print(f"  - Embedding Model: {settings.embedding_model}")

    # 2. Ingestion: fetch or load raw records
    log_step(2, total_steps, "Thu thập / Đọc dữ liệu thô (Raw Ingestion)")
    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        print("  - Nguồn: Gọi trực tiếp API Crossref...")
        raw_records = fetch_source_records(settings)
    else:
        print(f"  - Nguồn: Tải snapshot offline từ {settings.paths.raw_records_json.name}")
        raw_records = load_raw_records(settings.paths.raw_records_json)
    print(f"  ✓ Đã nạp thành công {len(raw_records)} bài báo thô.")

    # 3. Cleaning & preprocessing
    log_step(3, total_steps, "Làm sạch và tiền xử lý dữ liệu (Data Cleaning)")
    run_date = now_utc()
    clean_df = build_clean_dataframe(raw_records, run_date)
    print(f"  ✓ Đã làm sạch và chuẩn hóa {len(clean_df)} bản ghi.")

    # 4. Save clean dataset
    log_step(4, total_steps, "Lưu trữ dữ liệu sạch (Clean Artifacts)")
    write_csv(clean_df, settings.paths.clean_csv)
    clean_df.to_json(settings.paths.clean_json, orient="records", indent=2, force_ascii=False)
    print(f"  ✓ Đã lưu CSV: {settings.paths.clean_csv}")
    print(f"  ✓ Đã lưu JSON: {settings.paths.clean_json}")

    # 5. Build ChromaDB Vector Index
    log_step(5, total_steps, "Đánh chỉ mục Vector Store (ChromaDB Indexing)")
    index = LocalEmbeddingIndex.build(
        df=clean_df,
        settings=settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )
    print(f"  ✓ Đã index {len(clean_df)} tài liệu vào collection '{settings.baseline_collection_name}'.")

    # 6. Build or load evaluation benchmark test set
    log_step(6, total_steps, "Khởi tạo bộ câu hỏi Benchmark (Evaluation Testset)")
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        test_set = build_test_set(clean_df, settings.paths.eval_testset)
        print(f"  ✓ Đã sinh mới {len(test_set)} câu hỏi benchmark.")
    else:
        print(f"  ✓ Tái sử dụng testset hiện có tại {settings.paths.eval_testset}")

    # 7. Evaluate RAG retrieval & QA performance
    log_step(7, total_steps, "Đánh giá hiệu năng RAG (Baseline Evaluation)")
    evaluation_bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    print(f"  ✓ Hit Rate: {evaluation_bundle.summary.get('retrieval_hit_rate', 0.0):.2%}")
    print(f"  ✓ Mean Token F1: {evaluation_bundle.summary.get('mean_token_f1', 0.0):.4f}")

    # 8. Run Data Quality Gate & Freshness SLA
    log_step(8, total_steps, "Kiểm định chất lượng dữ liệu (GX 1.x & Freshness SLA)")
    quality_report = run_data_quality_checks(clean_df, settings, report_name="baseline")
    freshness_report = build_freshness_report(clean_df, settings, settings.paths.freshness_report)
    print(f"  ✓ Quality Check Status: {quality_report.get('success', False)}")
    print(f"  ✓ Freshness Status: {freshness_report.get('is_fresh', False)}")

    # 9. Generate Phase 1 Markdown Report
    log_step(9, total_steps, "Xuất báo cáo tổng kết Pha 1 (Phase 1 Report)")
    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "total_raw_records": len(raw_records),
        "total_clean_rows": len(clean_df),
        "run_date": run_date.isoformat(),
    }
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=evaluation_bundle.summary,
        quality=quality_report,
        freshness=freshness_report,
    )
    print(f"  ✓ Báo cáo hoàn tất tại: {settings.paths.baseline_report}")

    # 10. Sample QA Agent Demonstration
    log_step(10, total_steps, "Thử nghiệm mẫu QA Agent (Sample Demonstration)")
    demo_answers = []
    if not clean_df.empty:
        sample_title = clean_df.iloc[0]["title"]
        sample_query = f"What is the summary of '{sample_title}'?"
        ans = answer_question(sample_query, settings=settings, index=index)
        demo_answers.append({"question": sample_query, "answer": ans.answer})
        write_json(settings.paths.demo_answers, demo_answers)
        print(f"  - Câu hỏi: {sample_query}")
        print(f"  - Trả lời: {ans.answer[:120]}...")

    print("\n" + "=" * 60)
    print("🎉 HOÀN THÀNH PHA 1: BASELINE PIPELINE SẴN SÀNG!")
    print("=" * 60)
    return {
        "clean_rows": len(clean_df),
        "metrics": evaluation_bundle.summary,
        "quality_success": quality_report.get("success", False),
    }


def main() -> None:
    try:
        run_phase1_pipeline()
    except NotImplementedError as err:
        print("\n" + "!" * 60)
        print(f"[THÔNG BÁO TÍCH HỢP] Một thành phần đang được xây dựng: {err}")
        print("Vui lòng đợi thành viên phụ trách hoàn tất module tương ứng.")
        print("!" * 60)
        sys.exit(1)
    except Exception as exc:
        print(f"\n[LỖI THỰC THI PIPELINE]: {exc}")
        raise exc


if __name__ == "__main__":
    main()
