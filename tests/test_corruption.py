import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from core.utils import read_json
from ingestion.corruption import NOISE_SUFFIX, corrupt_clean_dataframe


class CorruptionTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame(
            [
                {
                    "paper_id": f"doi-{index}",
                    "title": f"A complete title {index}",
                    "summary": f"A complete summary for document number {index}.",
                    "published": (pd.Timestamp("2026-09-20") - pd.Timedelta(days=index)).date().isoformat(),
                    "age_days": index + 1,
                    "authors_joined": "Ada, Linus",
                    "categories_joined": "RAG, Evaluation",
                    "summary_chars": 40,
                    "text_for_embedding": "old embedding text",
                }
                for index in range(20)
            ]
        )

    def test_injects_all_six_corruption_types_and_logs_each_row(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "corruption_log.json"
            corrupted = corrupt_clean_dataframe(self.df, path)
            log = read_json(path)
            kinds = {event["corruption_type"] for event in log}
            self.assertEqual(
                kinds,
                {
                    "drop_latest_records",
                    "blank_summary",
                    "inject_noise",
                    "truncate_title",
                    "stale_date",
                    "duplicate_rows",
                },
            )
            self.assertEqual(len(corrupted), 18)  # 20 - 4 dropped + 2 duplicated
            self.assertFalse(set(self.df.iloc[:4].paper_id) & set(corrupted.paper_id))
            self.assertTrue(corrupted.summary.eq("").any())
            self.assertTrue(corrupted.summary.str.endswith(NOISE_SUFFIX).any())
            self.assertTrue(corrupted.title.str.len().lt(8).any())
            self.assertTrue(corrupted.paper_id.duplicated().any())
            self.assertTrue((corrupted.age_days > 365).any())
            self.assertTrue(
                all(f"Summary: {row.summary}" in row.text_for_embedding for row in corrupted.itertuples())
            )

    def test_is_deterministic_and_does_not_mutate_input(self):
        original = self.df.copy(deep=True)
        with TemporaryDirectory() as directory:
            first = corrupt_clean_dataframe(self.df, Path(directory) / "first.json")
            second = corrupt_clean_dataframe(self.df, Path(directory) / "second.json")
        pd.testing.assert_frame_equal(self.df, original)
        pd.testing.assert_frame_equal(first, second)

    def test_rejects_invalid_inputs(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "log.json"
            with self.assertRaisesRegex(ValueError, "At least two"):
                corrupt_clean_dataframe(self.df.iloc[:1], path)
            with self.assertRaisesRegex(ValueError, "Missing required columns"):
                corrupt_clean_dataframe(self.df.drop(columns="age_days"), path)


if __name__ == "__main__":
    unittest.main()
