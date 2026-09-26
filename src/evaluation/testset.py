from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


QUESTION_TYPES = ["summary", "authors", "date", "categories"]


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Create a small deterministic evaluation set from the cleaned dataframe."""

    if len(df) < 4:
        raise ValueError("Need at least 4 documents to build the evaluation set.")

    required_columns = {
        "paper_id",
        "title",
        "summary",
        "authors_joined",
        "categories_joined",
        "published",
    }
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    # Chọn tối đa 10 paper đại diện, giữ thứ tự ổn định.
    selected = df.head(min(10, len(df))).copy()

    test_set: list[dict[str, Any]] = []

    for i, (_, row) in enumerate(selected.iterrows()):
        paper_id = str(row["paper_id"])

        questions = [
            (
                "summary",
                f"What is the summary of the paper titled '{row['title']}'?",
                str(row["summary"]),
            ),
            (
                "authors",
                f"Who are the authors of the paper titled '{row['title']}'?",
                str(row["authors_joined"]),
            ),
            (
                "date",
                f"When was the paper titled '{row['title']}' published?",
                str(row["published"]),
            ),
            (
                "categories",
                f"What are the categories of the paper titled '{row['title']}'?",
                str(row["categories_joined"]),
            ),
        ]

        question_type, question, ground_truth = questions[i % len(questions)]

        test_set.append(
            {
                "id": f"test-{i + 1:02d}",
                "question_type": question_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [paper_id],
            }
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(test_set, f, ensure_ascii=False, indent=2)

    return test_set