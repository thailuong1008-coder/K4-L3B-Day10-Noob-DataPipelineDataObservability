from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import safe_slug, write_json


def evaluate_freshness_sla(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    """Fail freshness when over 25% of papers exceed the age threshold.

    Missing or invalid ages cannot establish freshness and fail the SLA.
    An empty dataset is not fresh.
    """
    ages = pd.to_numeric(df.get("age_days", pd.Series(index=df.index, dtype=float)), errors="coerce")
    total = len(df)
    stale = int((ages > settings.freshness_threshold_days).sum())
    invalid = int((ages.isna() | ages.isin([float("inf"), float("-inf")])).sum())
    ratio = stale / total if total else 0.0
    return {
        "threshold_days": settings.freshness_threshold_days,
        "max_stale_ratio": 0.25,
        "stale_rows": stale,
        "total_rows": total,
        "invalid_age_rows": invalid,
        "stale_ratio": ratio,
        "is_fresh": bool(total and invalid == 0 and ratio <= 0.25),
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Validate the four required GX rule types and freshness; persist a report."""
    context = gx.get_context(mode="ephemeral")
    context.enable_analytics(False)
    context.variables.progress_bars = {"globally": False}
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})
    expectations = [
        gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000),
        *[gx.expectations.ExpectColumnValuesToNotBeNull(column=column)
          for column in ("paper_id", "title", "text_for_embedding")],
        gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"),
        gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30),
    ]
    results = []
    for expectation in expectations:
        column = getattr(expectation, "column", None)
        if column is not None and column not in df.columns:
            results.append({"success": False, "expectation": expectation.expectation_type,
                            "column": column, "error": "Missing required column"})
        else:
            results.append(batch.validate(expectation).to_json_dict())
    freshness = evaluate_freshness_sla(df, settings)
    gx_success = all(result["success"] for result in results)
    report = {
        "stage": report_name,
        "success": bool(gx_success and freshness["is_fresh"]),
        "gx_success": gx_success,
        "results": results,
        "freshness": freshness,
    }
    write_json(settings.paths.quality_dir / f"{safe_slug(report_name)}_quality_report.json", report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path: Path) -> dict[str, Any]:
    """Persist freshness statistics and the publication date range."""
    dates = pd.to_datetime(df.get("published", pd.Series(dtype=str)), errors="coerce", utc=True)
    report = evaluate_freshness_sla(df, settings)
    report.update({
        "latest_published": dates.max().date().isoformat() if dates.notna().any() else None,
        "oldest_published": dates.min().date().isoformat() if dates.notna().any() else None,
    })
    write_json(report_path, report)
    return report
