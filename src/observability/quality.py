from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json

MIN_TITLE_CHARS = 8
MIN_SUMMARY_CHARS = 50
MAX_SUMMARY_CHARS = 5000
MAX_STALE_RATIO = 0.25


def quality_report_path(settings: Settings, report_name: str) -> Path:
    known = {
        "baseline": settings.paths.baseline_quality_report,
        "corrupted": settings.paths.corrupted_quality_report,
    }
    return known.get(report_name, settings.paths.quality_dir / f"{report_name}_quality_report.json")


def freshness_report_path(settings: Settings, report_name: str) -> Path:
    if report_name == "baseline":
        return settings.paths.freshness_report
    return settings.paths.quality_dir / f"{report_name}_freshness_report.json"


def _build_expectations(settings: Settings) -> list[gxe.Expectation]:
    min_rows = max(1, int(settings.max_results * 0.8))
    return [
        gxe.ExpectTableRowCountToBeBetween(min_value=min_rows, max_value=settings.max_results),
        gxe.ExpectColumnValuesToNotBeNull(column="paper_id"),
        gxe.ExpectColumnValuesToBeUnique(column="paper_id"),
        gxe.ExpectColumnValuesToNotBeNull(column="title"),
        gxe.ExpectColumnValueLengthsToBeBetween(column="title", min_value=MIN_TITLE_CHARS),
        gxe.ExpectColumnValuesToNotBeNull(column="summary"),
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="summary", min_value=MIN_SUMMARY_CHARS, max_value=MAX_SUMMARY_CHARS
        ),
        gxe.ExpectColumnValuesToNotBeNull(column="text_for_embedding"),
        # Freshness SLA: toi thieu 75% bai bao co age_days <= threshold.
        gxe.ExpectColumnValuesToBeBetween(
            column="age_days",
            min_value=0,
            max_value=settings.freshness_threshold_days,
            mostly=1 - MAX_STALE_RATIO,
        ),
    ]


def _summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    config = result.get("expectation_config", {})
    kwargs = {key: value for key, value in (config.get("kwargs") or {}).items() if key != "batch_id"}
    details = result.get("result", {})
    return {
        "expectation": config.get("type"),
        "kwargs": kwargs,
        "success": bool(result.get("success")),
        "observed_value": details.get("observed_value"),
        "unexpected_count": details.get("unexpected_count"),
        "unexpected_percent": details.get("unexpected_percent"),
        "partial_unexpected_list": (details.get("partial_unexpected_list") or [])[:5],
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Chay quality gate bang Great Expectations 1.x (ephemeral context) va ghi report JSON."""
    # GX khong hash duoc cot list (authors/categories) -> chi validate cac cot scalar.
    scalar_columns = [column for column in df.columns if column not in {"authors", "categories"}]
    frame = df[scalar_columns].copy()

    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": frame})

    suite = context.suites.add(gx.ExpectationSuite(name=f"papers_{report_name}_suite"))
    for expectation in _build_expectations(settings):
        suite.add_expectation(expectation)

    validation = batch.validate(suite).to_json_dict()
    checks = [_summarize_result(item) for item in validation.get("results", [])]
    failed = [check for check in checks if not check["success"]]

    report = {
        "report_name": report_name,
        "generated_at": now_utc().isoformat(),
        "engine": f"great_expectations {gx.__version__}",
        "suite_name": suite.name,
        "success": bool(validation.get("success")),
        "row_count": int(len(df)),
        "evaluated_expectations": len(checks),
        "successful_expectations": len(checks) - len(failed),
        "failed_expectations": [check["expectation"] + ":" + str(check["kwargs"].get("column", "table")) for check in failed],
        "checks": checks,
    }
    write_json(quality_report_path(settings, report_name), report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Tong hop Freshness SLA: is_fresh = False neu ty le bai `age_days > threshold` vuot 25%."""
    threshold = settings.freshness_threshold_days
    total_rows = int(len(df))
    published = pd.to_datetime(df["published"], errors="coerce") if total_rows else pd.Series(dtype="datetime64[ns]")
    ages = pd.to_numeric(df["age_days"], errors="coerce") if total_rows else pd.Series(dtype=float)

    stale_rows = int((ages > threshold).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 1.0
    payload = {
        "generated_at": now_utc().isoformat(),
        "threshold_days": threshold,
        "max_stale_ratio": MAX_STALE_RATIO,
        "latest_published": published.max().date().isoformat() if published.notna().any() else None,
        "oldest_published": published.min().date().isoformat() if published.notna().any() else None,
        "median_age_days": float(ages.median()) if ages.notna().any() else None,
        "max_age_days": int(ages.max()) if ages.notna().any() else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "is_fresh": total_rows > 0 and stale_ratio <= MAX_STALE_RATIO,
    }
    write_json(Path(report_path), payload)
    return payload
