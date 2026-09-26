from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import compact_join, first_sentence, normalize_whitespace, write_json


QUESTION_TYPES = (
    "summary",
    "authors",
    "date",
    "categories",
    "summary",
    "authors",
    "date",
    "categories",
    "summary",
    "authors",
)


def _as_text_list(value: Any) -> list[str]:
    """Normalize a list-like dataframe value into non-empty strings."""
    if not isinstance(value, (list, tuple)):
        return []
    return [text for item in value if (text := normalize_whitespace(str(item)))]


def _question_and_answer(row: pd.Series, question_type: str) -> tuple[str, str]:
    title = normalize_whitespace(str(row["title"]))
    if question_type == "summary":
        return f"What is the summary of the paper '{title}'?", first_sentence(str(row["summary"]))
    if question_type == "authors":
        return f"Who are the authors of the paper '{title}'?", compact_join(_as_text_list(row["authors"]))
    if question_type == "date":
        published = pd.to_datetime(row["published"], errors="raise").date().isoformat()
        return f"When was the paper '{title}' published?", published
    if question_type == "categories":
        return f"What are the categories of the paper '{title}'?", compact_join(_as_text_list(row["categories"]))
    raise ValueError(f"Unsupported question type: {question_type}")


def build_test_set(df: pd.DataFrame, output_path: Path) -> list[dict[str, Any]]:
    """Build and persist a deterministic ten-question benchmark."""
    required = {"paper_id", "title", "summary", "authors", "categories", "published"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    candidates = df.drop_duplicates(subset="paper_id", keep="first")
    candidates = candidates[
        candidates["paper_id"].notna()
        & candidates["title"].notna()
        & candidates["summary"].notna()
        & candidates["published"].notna()
        & candidates["authors"].apply(lambda value: bool(_as_text_list(value)))
        & candidates["categories"].apply(lambda value: bool(_as_text_list(value)))
    ]
    if len(candidates) < len(QUESTION_TYPES):
        raise ValueError(
            f"At least {len(QUESTION_TYPES)} complete, unique papers are required; found {len(candidates)}."
        )

    test_set: list[dict[str, Any]] = []
    for index, (question_type, (_, row)) in enumerate(
        zip(QUESTION_TYPES, candidates.iloc[: len(QUESTION_TYPES)].iterrows()), start=1
    ):
        question, ground_truth = _question_and_answer(row, question_type)
        if not ground_truth:
            raise ValueError(f"Paper {row['paper_id']} produced an empty ground truth.")
        test_set.append(
            {
                "id": f"eval_{index:03d}",
                "question_type": question_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [normalize_whitespace(str(row["paper_id"]))],
            }
        )

    write_json(output_path, test_set)
    return test_set
