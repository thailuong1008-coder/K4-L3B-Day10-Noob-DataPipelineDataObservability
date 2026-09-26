from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import pandas as pd

from core.config import Settings


def run_data_quality_checks(
    df: pd.DataFrame,
    settings: Settings,
    report_name: str,
) -> dict[str, Any]:
    """Run basic data quality checks and save the report."""

    total_rows = int(len(df))

    paper_id_not_null = (
        bool(df["paper_id"].notna().all())
        if "paper_id" in df.columns
        else False
    )

    paper_id_unique = (
        bool(df["paper_id"].astype(str).is_unique)
        if "paper_id" in df.columns
        else False
    )

    title_not_null = (
        bool(df["title"].notna().all())
        if "title" in df.columns
        else False
    )

    if "summary" in df.columns:
        summary_lengths = df["summary"].fillna("").astype(str).str.len()
        summary_min_length = int(summary_lengths.min()) if len(summary_lengths) else 0
        summary_valid = bool((summary_lengths > 0).all())
    else:
        summary_min_length = 0
        summary_valid = False

    if "age_days" in df.columns:
        age_values = pd.to_numeric(df["age_days"], errors="coerce")
        stale_rows = int(
            (age_values > settings.freshness_threshold_days).sum()
        )
    elif "published" in df.columns:
        published = pd.to_datetime(
            df["published"],
            errors="coerce",
            utc=True,
        )
        now = pd.Timestamp.now(tz="UTC")
        age_days = (now - published).dt.total_seconds() / 86400
        stale_rows = int(
            (age_days > settings.freshness_threshold_days).sum()
        )
    else:
        stale_rows = total_rows

    checks = {
        "row_count": {
            "value": total_rows,
            "passed": total_rows > 0,
        },
        "paper_id_not_null": {
            "passed": paper_id_not_null,
        },
        "paper_id_unique": {
            "passed": paper_id_unique,
        },
        "title_not_null": {
            "passed": title_not_null,
        },
        "summary_valid": {
            "passed": summary_valid,
            "min_length": summary_min_length,
        },
        "freshness": {
            "stale_rows": stale_rows,
            "threshold_days": settings.freshness_threshold_days,
            "passed": stale_rows == 0,
        },
    }

    passed = all(
        bool(check.get("passed", False))
        for check in checks.values()
    )

    report = {
        "report_name": report_name,
        "total_rows": total_rows,
        "passed": passed,
        "checks": checks,
    }

    settings.paths.quality_dir.mkdir(parents=True, exist_ok=True)

    report_path = settings.paths.quality_dir / report_name
    if report_path.suffix.lower() != ".json":
        report_path = report_path.with_suffix(".json")

    with Path(report_path).open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report


def build_freshness_report(
    df: pd.DataFrame,
    settings: Settings,
    report_path,
) -> dict[str, Any]:
    """Build and save freshness information."""

    if "published" not in df.columns or len(df) == 0:
        payload = {
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": int(len(df)),
            "total_rows": int(len(df)),
            "is_fresh": False,
        }
    else:
        published = pd.to_datetime(
            df["published"],
            errors="coerce",
            utc=True,
        ).dropna()

        if len(published) == 0:
            payload = {
                "latest_published": None,
                "oldest_published": None,
                "stale_rows": int(len(df)),
                "total_rows": int(len(df)),
                "is_fresh": False,
            }
        else:
            now = pd.Timestamp.now(tz="UTC")
            age_days = (
                (now - published).dt.total_seconds() / 86400
            )

            stale_rows = int(
                (age_days > settings.freshness_threshold_days).sum()
            )

            payload = {
                "latest_published": published.max().isoformat(),
                "oldest_published": published.min().isoformat(),
                "stale_rows": stale_rows,
                "total_rows": int(len(df)),
                "is_fresh": stale_rows == 0,
            }

    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with report_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return payload