from __future__ import annotations

from datetime import datetime

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord

BASE_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "abs_url",
    "pdf_url",
    "comment",
]
CLEAN_COLUMNS = BASE_COLUMNS + [
    "age_days",
    "authors_joined",
    "categories_joined",
    "summary_chars",
    "text_for_embedding",
]


def _normalize_list(values: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    for value in values or []:
        item = normalize_whitespace(str(value))
        if item and item not in cleaned:
            cleaned.append(item)
    return cleaned


def build_embedding_text(row: pd.Series) -> str:
    return "\n".join(
        [
            f"Title: {row['title']}",
            f"Authors: {row['authors_joined']}",
            f"Published: {row['published']}",
            f"Categories: {row['categories_joined']}",
            f"Summary: {row['summary']}",
        ]
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed."""
    rows = [
        {
            "paper_id": normalize_whitespace(record.paper_id).lower(),
            "title": normalize_whitespace(record.title),
            "summary": normalize_whitespace(record.summary),
            "authors": _normalize_list(record.authors),
            "categories": _normalize_list(record.categories),
            "primary_category": normalize_whitespace(record.primary_category),
            "published": record.published,
            "updated": record.updated,
            "abs_url": normalize_whitespace(record.abs_url),
            "pdf_url": normalize_whitespace(record.pdf_url),
            "comment": normalize_whitespace(record.comment),
        }
        for record in records
    ]
    df = pd.DataFrame(rows, columns=BASE_COLUMNS)
    if df.empty:
        return pd.DataFrame(columns=CLEAN_COLUMNS)

    # Parse ngay; row co published khong hop le se bi loc o buoc filter.
    published = pd.to_datetime(df["published"], errors="coerce", utc=True)
    updated = pd.to_datetime(df["updated"], errors="coerce", utc=True).fillna(published)
    df["published"] = published.dt.strftime("%Y-%m-%d")
    df["updated"] = updated.dt.strftime("%Y-%m-%d")

    run_ts = pd.Timestamp(run_date)
    run_ts = run_ts.tz_localize("UTC") if run_ts.tzinfo is None else run_ts.tz_convert("UTC")
    df["age_days"] = (run_ts.normalize() - published.dt.normalize()).dt.days

    df["primary_category"] = [
        primary or (categories[0] if categories else "")
        for primary, categories in zip(df["primary_category"], df["categories"])
    ]
    df["authors_joined"] = df["authors"].apply(compact_join)
    df["categories_joined"] = df["categories"].apply(compact_join)
    df["summary_chars"] = df["summary"].str.len()

    # Filter row xau: thieu khoa, title/summary rong, ngay khong parse duoc.
    valid = df["paper_id"].ne("") & df["title"].ne("") & df["summary"].ne("") & published.notna()
    df = df[valid].copy()
    df["age_days"] = df["age_days"].astype(int)
    df["text_for_embedding"] = df.apply(build_embedding_text, axis=1)

    # Khu trung lap theo paper_id, giu ban cap nhat moi nhat.
    df = df.sort_values(["paper_id", "updated"], ascending=[True, False])
    df = df.drop_duplicates(subset="paper_id", keep="first")

    df = df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    return df[CLEAN_COLUMNS]
