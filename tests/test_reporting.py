import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from observability.reporting import generate_phase1_report


class ReportingTests(unittest.TestCase):
    def test_phase1_report_contains_required_sections_and_metrics(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "phase1.md"
            generate_phase1_report(
                output,
                source_summary={
                    "run_date": "2026-09-26T00:00:00+00:00",
                    "source_api": "Crossref",
                    "source_query": "RAG",
                    "total_raw_records": 24,
                    "total_clean_rows": 24,
                },
                metrics={
                    "samples": 10,
                    "retrieval_hit_rate": 1.0,
                    "mean_token_f1": 0.75,
                    "judge_accuracy": 0.8,
                    "mean_judge_score": 4.0,
                    "ragas": {"skipped": "disabled"},
                },
                quality={
                    "success": True,
                    "results": [
                        {
                            "success": True,
                            "expectation_config": {
                                "type": "expect_column_values_to_not_be_null",
                                "kwargs": {"column": "paper_id"},
                            },
                        }
                    ],
                },
                freshness={
                    "is_fresh": True,
                    "threshold_days": 180,
                    "max_stale_ratio": 0.25,
                    "stale_rows": 1,
                    "total_rows": 24,
                    "stale_ratio": 1 / 24,
                    "latest_published": "2026-07-22",
                    "oldest_published": "2026-01-01",
                },
            )
            report = output.read_text(encoding="utf-8")
            self.assertIn("Retrieval Hit Rate | 100.00%", report)
            self.assertIn("Mean Token F1 | 0.7500", report)
            self.assertIn("Overall status: **PASS**", report)
            self.assertIn("Stale rows | 1 / 24", report)

    def test_corruption_report_compares_three_states(self):
        from observability.reporting import generate_corruption_report

        with TemporaryDirectory() as directory:
            output = Path(directory) / "corruption.md"
            generate_corruption_report(
                output,
                baseline_metrics={"retrieval_hit_rate": 1.0, "mean_token_f1": 1.0, "judge_accuracy": 1.0},
                corrupted_metrics={"retrieval_hit_rate": 0.5, "mean_token_f1": 0.4, "judge_accuracy": 0.5},
                repaired_metrics={"retrieval_hit_rate": 1.0, "mean_token_f1": 1.0, "judge_accuracy": 1.0},
                corrupted_quality={"success": False},
                repaired_quality={"success": True},
                corrupted_freshness={
                    "is_fresh": False, "stale_rows": 8, "total_rows": 21,
                    "stale_ratio": 8 / 21, "max_stale_ratio": 0.25,
                },
                repaired_freshness={
                    "is_fresh": True, "stale_rows": 1, "total_rows": 24,
                    "stale_ratio": 1 / 24, "max_stale_ratio": 0.25,
                },
                baseline_quality={"success": True},
            )
            report = output.read_text(encoding="utf-8")
            self.assertIn("| Metric | Baseline | Corrupted | Repaired |", report)
            self.assertIn("| Retrieval Hit Rate | 100.00% | 50.00% | 100.00%", report)
            self.assertIn("| Quality Gate | PASS | FAIL | PASS", report)
            self.assertIn("silent failure", report)


if __name__ == "__main__":
    unittest.main()
