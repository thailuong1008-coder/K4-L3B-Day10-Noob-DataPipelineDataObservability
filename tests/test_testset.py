import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from core.utils import read_json
from evaluation.testset import build_test_set


class TestSetTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame(
            [
                {
                    "paper_id": f"doi-{index}",
                    "title": f"Paper {index}",
                    "summary": f"First sentence for paper {index}. Second sentence is excluded.",
                    "authors": [f"Author {index}", "Coauthor"],
                    "categories": ["RAG", "Evaluation"],
                    "published": "2026-01-02",
                }
                for index in range(12)
            ]
        )

    def test_builds_balanced_deterministic_test_set(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "test_set.json"
            result = build_test_set(self.df, output)
            self.assertEqual(len(result), 10)
            self.assertEqual([item["id"] for item in result], [f"eval_{i:03d}" for i in range(1, 11)])
            counts = pd.Series(item["question_type"] for item in result).value_counts().to_dict()
            self.assertEqual(counts, {"summary": 3, "authors": 3, "date": 2, "categories": 2})
            self.assertEqual(result[0]["ground_truth"], "First sentence for paper 0.")
            self.assertEqual(len({item["ground_truth_doc_ids"][0] for item in result}), 10)
            self.assertEqual(read_json(output), result)

    def test_rejects_insufficient_or_incomplete_data(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "test_set.json"
            with self.assertRaisesRegex(ValueError, "At least 10"):
                build_test_set(self.df.iloc[:9], output)
            with self.assertRaisesRegex(ValueError, "Missing required columns"):
                build_test_set(self.df.drop(columns="authors"), output)


if __name__ == "__main__":
    unittest.main()
