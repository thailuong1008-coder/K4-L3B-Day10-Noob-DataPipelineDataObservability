from __future__ import annotations

import sys
from datetime import datetime
import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from ingestion.crossref import load_raw_records
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from retrieval.index import LocalEmbeddingIndex
from evaluation.metrics import evaluate_pipeline
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report


def log_flow_step(step_num: int, total_steps: int, title: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] >>> GIAI ĐOẠN {step_num}/{total_steps}: {title} <<<")


def print_comparison_table(
    baseline_metrics: dict,
    corrupted_metrics: dict,
    repaired_metrics: dict,
    baseline_quality: dict,
    corrupted_quality: dict,
    repaired_quality: dict,
) -> None:
    """Print clean comparison table across 3 states to terminal."""
    print("\n" + "=" * 80)
    print("           BẢNG ĐỐI CHIẾU HIỆU NĂNG 3 TRẠNG THÁI (BENCHMARK COMPARISON)")
    print("=" * 80)
    print(f"{'Chỉ số (Metric)':<30} | {'1. Baseline':<14} | {'2. Corrupted':<14} | {'3. Repaired':<14}")
    print("-" * 80)

    # Retrieval Hit Rate
    b_hr = baseline_metrics.get("retrieval_hit_rate", 0.0)
    c_hr = corrupted_metrics.get("retrieval_hit_rate", 0.0)
    r_hr = repaired_metrics.get("retrieval_hit_rate", 0.0)
    print(f"{'Retrieval Hit Rate':<30} | {b_hr:>13.2%} | {c_hr:>13.2%} | {r_hr:>13.2%}")

    # Mean Token F1
    b_f1 = baseline_metrics.get("mean_token_f1", 0.0)
    c_f1 = corrupted_metrics.get("mean_token_f1", 0.0)
    r_f1 = repaired_metrics.get("mean_token_f1", 0.0)
    print(f"{'Mean Token F1':<30} | {b_f1:>14.4f} | {c_f1:>14.4f} | {r_f1:>14.4f}")

    # Judge Accuracy
    b_ja = baseline_metrics.get("judge_accuracy", 0.0)
    c_ja = corrupted_metrics.get("judge_accuracy", 0.0)
    r_ja = repaired_metrics.get("judge_accuracy", 0.0)
    print(f"{'Judge Accuracy':<30} | {b_ja:>13.2%} | {c_ja:>13.2%} | {r_ja:>13.2%}")

    # Quality Gate (GX 1.x)
    b_qg = "PASSED" if baseline_quality.get("success", False) else "FAILED"
    c_qg = "PASSED" if corrupted_quality.get("success", False) else "FAILED (Alert)"
    r_qg = "PASSED" if repaired_quality.get("success", False) else "FAILED"
    print(f"{'Quality Gate (GX 1.x)':<30} | {b_qg:>14} | {c_qg:>14} | {r_qg:>14}")

    print("=" * 80)


def run_corruption_flow(settings: Settings | None = None) -> dict:
    """Full corruption, evaluation, idempotent repair, and comparison flow.
    
    Orchestrated by Member 1 (Pipeline Integrator).
    """
    total_steps = 8
    if settings is None:
        settings = load_settings()

    # 1. Load baseline metrics & clean dataset
    log_flow_step(1, total_steps, "Nạp dữ liệu sạch và chỉ số Baseline ban đầu")
    if not settings.paths.clean_json.exists() or not settings.paths.baseline_metrics.exists():
        raise RuntimeError(
            "Chưa tìm thấy kết quả Pha 1. Vui lòng chạy `python script/run_phase1.py` trước khi thực nghiệm corruption!"
        )
    clean_df = pd.read_json(settings.paths.clean_json)
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    baseline_quality = read_json(settings.paths.baseline_quality_report) if settings.paths.baseline_quality_report.exists() else {"success": True}
    print(f"  ✓ Đã nạp Baseline clean dataframe: {len(clean_df)} dòng.")
    print(f"  ✓ Baseline Hit Rate: {baseline_metrics.get('retrieval_hit_rate', 0.0):.2%}")

    # 2. Inject synthetic data corruptions
    log_flow_step(2, total_steps, "Tiêm 6 kịch bản lỗi giả lập vào dữ liệu (Synthetic Corruption)")
    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    print(f"  ✓ Đã tiêm lỗi thành công. Số lượng bản ghi sau tiêm lỗi: {len(corrupted_df)} dòng.")

    # 3. Save corrupted artifacts
    log_flow_step(3, total_steps, "Lưu trữ artifacts dữ liệu bẩn")
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    corrupted_df.to_json(settings.paths.corrupted_clean_json, orient="records", indent=2, force_ascii=False)
    print(f"  ✓ Đã lưu: {settings.paths.corrupted_clean_json}")

    # 4. Rebuild vector index on corrupted data & evaluate degradation
    log_flow_step(4, total_steps, "Tái tạo Vector Index trên dữ liệu lỗi và đo lường suy giảm")
    corrupted_index = LocalEmbeddingIndex.build(
        df=corrupted_df,
        settings=settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )
    corrupted_bundle = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    print(f"  🔻 Corrupted Hit Rate: {corrupted_bundle.summary.get('retrieval_hit_rate', 0.0):.2%}")
    print(f"  🔻 Corrupted Mean Token F1: {corrupted_bundle.summary.get('mean_token_f1', 0.0):.4f}")

    # 5. Run Quality Gate & Freshness on Corrupted Data
    log_flow_step(5, total_steps, "Kích hoạt Data Quality Gate trên dữ liệu lỗi (Phát hiện vi phạm)")
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, report_name="corrupted")
    corrupted_freshness = build_freshness_report(corrupted_df, settings, settings.paths.corrupted_quality_report)
    print(f"  🚨 GX 1.x Quality Check: {corrupted_quality.get('success', False)} (Kỳ vọng: False)")
    print(f"  🚨 Freshness Check: {corrupted_freshness.get('is_fresh', False)}")

    # 6. Idempotent Repair from raw snapshot
    log_flow_step(6, total_steps, "Kích hoạt cơ chế tự phục hồi an toàn (Idempotent Repair)")
    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, now_utc())
    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    repaired_df.to_json(settings.paths.repaired_clean_json, orient="records", indent=2, force_ascii=False)
    print(f"  ✓ Phục hồi thành công {len(repaired_df)} bản ghi từ snapshot gốc.")

    # 7. Re-index repaired dataset & evaluate recovery
    log_flow_step(7, total_steps, "Tái tạo Vector Index phục hồi & đo lường khôi phục hiệu năng")
    repaired_index = LocalEmbeddingIndex.build(
        df=repaired_df,
        settings=settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )
    repaired_bundle = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, report_name="repaired")
    repaired_freshness = build_freshness_report(repaired_df, settings, settings.paths.freshness_report)
    print(f"  🔺 Repaired Hit Rate: {repaired_bundle.summary.get('retrieval_hit_rate', 0.0):.2%}")
    print(f"  🔺 Repaired Mean Token F1: {repaired_bundle.summary.get('mean_token_f1', 0.0):.4f}")
    print(f"  ✓ GX 1.x Quality Check: {repaired_quality.get('success', False)} (Kỳ vọng: True)")

    # 8. Generate comparison report & display summary
    log_flow_step(8, total_steps, "Xuất báo cáo đối chiếu 3 trạng thái (Baseline vs Corrupted vs Repaired)")
    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_bundle.summary,
        repaired_metrics=repaired_bundle.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )
    print(f"  ✓ Báo cáo đối chiếu đã được ghi vào: {settings.paths.comparison_report}")

    # In bảng đối chiếu trực quan ra console
    print_comparison_table(
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_bundle.summary,
        repaired_metrics=repaired_bundle.summary,
        baseline_quality=baseline_quality,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
    )

    return {
        "baseline": baseline_metrics,
        "corrupted": corrupted_bundle.summary,
        "repaired": repaired_bundle.summary,
    }


def main() -> None:
    try:
        run_corruption_flow()
    except NotImplementedError as err:
        print("\n" + "!" * 60)
        print(f"[THÔNG BÁO TÍCH HỢP] Một thành phần đang được xây dựng: {err}")
        print("Vui lòng đợi thành viên phụ trách hoàn tất module tương ứng.")
        print("!" * 60)
        sys.exit(1)
    except Exception as exc:
        print(f"\n[LỖI THỰC THI CORRUPTION FLOW]: {exc}")
        raise exc


if __name__ == "__main__":
    main()
