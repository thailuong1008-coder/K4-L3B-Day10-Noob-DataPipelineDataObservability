from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json

MIN_DOCUMENTS = 10

# (question_type, so cau hoi) -> tong 10 cau, phu du 4 nhom nghiep vu.
QUESTION_PLAN = [("summary", 3), ("authors", 3), ("date", 2), ("categories", 2)]

QUESTION_TEMPLATES = {
    "summary": "What is the main contribution of the paper '{title}'?",
    "authors": "Who authored the paper '{title}'?",
    "date": "When was the paper '{title}' published?",
    "categories": "What categories does the paper '{title}' belong to?",
}


def _ground_truth(question_type: str, row: pd.Series) -> str:
    if question_type == "summary":
        return first_sentence(row["summary"])
    if question_type == "authors":
        return row["authors_joined"]
    if question_type == "date":
        return row["published"]
    return row["categories_joined"]


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Tao bo evaluation set 10 cau hoi tu cleaned dataframe va ghi ra JSON."""
    unique_df = df.drop_duplicates(subset="paper_id")
    if len(unique_df) < MIN_DOCUMENTS:
        raise ValueError(f"Need at least {MIN_DOCUMENTS} documents to build a test set, got {len(unique_df)}.")

    # Chon paper dai dien, trai deu theo thu tu paper_id -> deterministic giua cac lan chay.
    ordered = unique_df.sort_values("paper_id").reset_index(drop=True)
    total_questions = sum(count for _, count in QUESTION_PLAN)
    step = len(ordered) / total_questions
    picks = [ordered.iloc[int(i * step)] for i in range(total_questions)]

    test_set: list[dict[str, Any]] = []
    cursor = 0
    for question_type, count in QUESTION_PLAN:
        for _ in range(count):
            row = picks[cursor]
            cursor += 1
            test_set.append(
                {
                    "id": f"q{cursor:02d}-{question_type}",
                    "question_type": question_type,
                    "question": QUESTION_TEMPLATES[question_type].format(title=row["title"]),
                    "ground_truth": _ground_truth(question_type, row),
                    "ground_truth_doc_ids": [row["paper_id"]],
                }
            )

    write_json(output_path, test_set)
    return test_set
