from __future__ import annotations

from pathlib import Path
import json

import pandas as pd


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Simulate multiple data corruption scenarios and rebuild embeddings text."""

    corrupted = df.copy()

    corruption_log = {
        "original_rows": int(len(corrupted)),
        "operations": [],
    }

    # 1. Drop latest 20% records.
    drop_count = max(1, int(len(corrupted) * 0.20))
    if drop_count < len(corrupted):
        corrupted = corrupted.iloc[drop_count:].copy()

    corruption_log["operations"].append(
        {
            "type": "drop_latest_20_percent",
            "dropped_rows": drop_count,
        }
    )

    # 2. Blank summary on one row.
    if len(corrupted) > 0:
        summary_idx = corrupted.index[0]
        corrupted.loc[summary_idx, "summary"] = ""

        corruption_log["operations"].append(
            {
                "type": "blank_summary",
                "rows": 1,
                "paper_id": str(corrupted.loc[summary_idx, "paper_id"]),
            }
        )

    # 3. Inject noise into title/summary text.
    if len(corrupted) > 0:
        noise_idx = corrupted.index[min(1, len(corrupted) - 1)]

        corrupted.loc[noise_idx, "summary"] = (
            str(corrupted.loc[noise_idx, "summary"])
            + " [CORRUPTED_NOISE]"
        )

        corruption_log["operations"].append(
            {
                "type": "noise",
                "rows": 1,
                "paper_id": str(corrupted.loc[noise_idx, "paper_id"]),
            }
        )

    # 4. Truncate one title to fewer than 8 characters.
    if len(corrupted) > 0:
        title_idx = corrupted.index[min(2, len(corrupted) - 1)]
        original_title = str(corrupted.loc[title_idx, "title"])
        corrupted.loc[title_idx, "title"] = original_title[:7]

        corruption_log["operations"].append(
            {
                "type": "truncate_title",
                "rows": 1,
                "paper_id": str(corrupted.loc[title_idx, "paper_id"]),
            }
        )

    # 5. Make one published date stale.
    if len(corrupted) > 0:
        date_idx = corrupted.index[min(3, len(corrupted) - 1)]
        corrupted.loc[date_idx, "published"] = "2000-01-01T00:00:00Z"

        corruption_log["operations"].append(
            {
                "type": "stale_date",
                "rows": 1,
                "paper_id": str(corrupted.loc[date_idx, "paper_id"]),
            }
        )

    # 6. Add duplicate rows.
    if len(corrupted) > 0:
        duplicate_row = corrupted.iloc[[0]].copy()
        corrupted = pd.concat(
            [corrupted, duplicate_row],
            ignore_index=True,
        )

        corruption_log["operations"].append(
            {
                "type": "duplicate_rows",
                "rows": 1,
                "paper_id": str(duplicate_row.iloc[0]["paper_id"]),
            }
        )

    # 7. Rebuild text_for_embedding.
    def rebuild_text(row: pd.Series) -> str:
        return (
            f"Title: {row.get('title', '')}\n"
            f"Summary: {row.get('summary', '')}\n"
            f"Authors: {row.get('authors_joined', '')}\n"
            f"Categories: {row.get('categories_joined', '')}\n"
            f"Published: {row.get('published', '')}"
        )

    corrupted["text_for_embedding"] = corrupted.apply(
        rebuild_text,
        axis=1,
    )

    # 8. Write corruption log.
    output_log_path = Path(output_log_path)
    output_log_path.parent.mkdir(parents=True, exist_ok=True)

    corruption_log["final_rows"] = int(len(corrupted))

    with output_log_path.open("w", encoding="utf-8") as f:
        json.dump(
            corruption_log,
            f,
            ensure_ascii=False,
            indent=2,
        )

    return corrupted