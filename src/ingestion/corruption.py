from __future__ import annotations

from math import ceil
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import write_json


NOISE_SUFFIX = " [[NOISE::@@@###CORRUPTED###@@@]]"


def _json_value(value: Any) -> Any:
    """Convert pandas/numpy values used in the audit log to JSON-safe values."""
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    return value


def _embedding_text(row: pd.Series) -> str:
    return "\n".join(
        [
            f"Title: {row['title']}",
            f"Authors: {row['authors_joined']}",
            f"Published: {row['published']}",
            f"Categories: {row['categories_joined']}",
            f"Summary: {row['summary']}",
        ]
    )


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path) -> pd.DataFrame:
    """Inject six deterministic corruption scenarios and write a row-level audit log."""
    required = {
        "paper_id",
        "title",
        "summary",
        "published",
        "age_days",
        "authors_joined",
        "categories_joined",
        "summary_chars",
        "text_for_embedding",
    }
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    if len(df) < 2:
        raise ValueError("At least two clean rows are required for corruption testing.")

    corrupted = df.copy(deep=True)
    published = pd.to_datetime(corrupted["published"], errors="coerce")
    if published.isna().any():
        raise ValueError("Column 'published' contains invalid dates.")

    events: list[dict[str, Any]] = []

    def log_event(kind: str, index: Any, field: str, before: Any, after: Any) -> None:
        events.append(
            {
                "corruption_type": kind,
                "row_index": _json_value(index),
                "paper_id": str(corrupted.at[index, "paper_id"]),
                "field": field,
                "before": _json_value(before),
                "after": _json_value(after),
            }
        )

    # 1. Remove exactly ceil(20%) of the most recently published rows.
    drop_count = min(ceil(len(corrupted) * 0.20), len(corrupted) - 1)
    drop_indices = published.sort_values(ascending=False).index[:drop_count].tolist()
    for index in drop_indices:
        events.append(
            {
                "corruption_type": "drop_latest_records",
                "row_index": _json_value(index),
                "paper_id": str(corrupted.at[index, "paper_id"]),
                "field": "row",
                "before": corrupted.loc[index].to_dict(),
                "after": None,
            }
        )
    corrupted = corrupted.drop(index=drop_indices)

    remaining_indices = list(corrupted.index)
    small_count = max(1, ceil(len(remaining_indices) * 0.10))
    stale_count = max(1, ceil(len(remaining_indices) * 0.30))
    cursor = 0

    def take_indices(count: int) -> list[Any]:
        nonlocal cursor
        chosen = [remaining_indices[(cursor + offset) % len(remaining_indices)] for offset in range(count)]
        cursor = (cursor + count) % len(remaining_indices)
        return chosen

    # 2. Blank summaries.
    for index in take_indices(small_count):
        before = corrupted.at[index, "summary"]
        corrupted.at[index, "summary"] = ""
        log_event("blank_summary", index, "summary", before, "")

    # 3. Add a visible, deterministic noise marker to summaries.
    for index in take_indices(small_count):
        before = str(corrupted.at[index, "summary"])
        after = before + NOISE_SUFFIX
        corrupted.at[index, "summary"] = after
        log_event("inject_noise", index, "summary", before, after)

    # 4. Truncate titles to seven characters (strictly below eight).
    for index in take_indices(small_count):
        before = str(corrupted.at[index, "title"])
        after = before[:7]
        corrupted.at[index, "title"] = after
        log_event("truncate_title", index, "title", before, after)

    # 5. Move publication dates back by 365 days and keep age_days consistent.
    for index in take_indices(stale_count):
        before_date = pd.to_datetime(corrupted.at[index, "published"])
        after_date = before_date - pd.Timedelta(days=365)
        corrupted.at[index, "published"] = after_date.date().isoformat()
        log_event(
            "stale_date",
            index,
            "published",
            before_date.date().isoformat(),
            after_date.date().isoformat(),
        )
        before_age = corrupted.at[index, "age_days"]
        corrupted.at[index, "age_days"] = int(before_age) + 365
        log_event("stale_date", index, "age_days", before_age, int(before_age) + 365)

    # Rebuild all derived text fields after the mutations above.
    corrupted["summary_chars"] = corrupted["summary"].astype(str).str.len()
    corrupted["text_for_embedding"] = corrupted.apply(_embedding_text, axis=1)

    # 6. Duplicate rows, retaining paper_id so the uniqueness gate detects them.
    duplicate_count = max(1, ceil(len(corrupted) * 0.10))
    duplicate_indices = list(corrupted.index[:duplicate_count])
    duplicates = corrupted.loc[duplicate_indices].copy(deep=True)
    for index in duplicate_indices:
        events.append(
            {
                "corruption_type": "duplicate_rows",
                "row_index": _json_value(index),
                "paper_id": str(corrupted.at[index, "paper_id"]),
                "field": "row",
                "before": None,
                "after": corrupted.loc[index].to_dict(),
            }
        )
    corrupted = pd.concat([corrupted, duplicates], ignore_index=True)

    write_json(output_log_path, events)
    return corrupted
