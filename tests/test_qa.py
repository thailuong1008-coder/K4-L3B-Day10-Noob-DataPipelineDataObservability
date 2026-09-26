import unittest

from retrieval.index import SearchResult
from retrieval.qa import _extract_answer


class QaExtractionTests(unittest.TestCase):
    def setUp(self):
        self.result = SearchResult(
            paper_id="doi",
            title="Paper",
            score=1.0,
            content="content",
            metadata={
                "authors_joined": "Ada, Linus",
                "published": "2026-01-02",
                "categories_joined": "RAG, Evaluation",
                "summary": "First sentence. Second sentence.",
            },
        )

    def test_matches_benchmark_question_templates(self):
        self.assertEqual(_extract_answer("Who are the authors of the paper 'Paper'?", self.result), "Ada, Linus")
        self.assertEqual(_extract_answer("When was the paper 'Paper' published?", self.result), "2026-01-02")
        self.assertEqual(
            _extract_answer("What are the categories of the paper 'Paper'?", self.result), "RAG, Evaluation"
        )
        self.assertEqual(_extract_answer("What is the summary of the paper 'Paper'?", self.result), "First sentence.")


if __name__ == "__main__":
    unittest.main()
