from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from core.config import load_settings
from core.utils import read_json
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records, parse_crossref_payload
from observability.quality import build_freshness_report, run_data_quality_checks

RUN_DATE = datetime(2026, 9, 26, tzinfo=UTC)


@pytest.fixture(scope="module")
def settings(tmp_path_factory):
    base = load_settings()
    tmp = tmp_path_factory.mktemp("quality")
    # Ghi report ra thu muc tam de test khong dung vao artifact that.
    paths = replace(
        base.paths,
        quality_dir=tmp,
        baseline_quality_report=tmp / "baseline.json",
        corrupted_quality_report=tmp / "corrupted.json",
    )
    return replace(base, paths=paths)


@pytest.fixture(scope="module")
def clean_df(settings) -> pd.DataFrame:
    return build_clean_dataframe(load_raw_records(settings.paths.raw_records_json), RUN_DATE)


def test_parse_strips_jats_and_skips_invalid_items():
    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1/ABC",
                    "title": ["  A   Title "],
                    "abstract": "<jats:p>Hello &amp; <jats:italic>world</jats:italic></jats:p>",
                    "author": [{"given": "Ada", "family": "Lovelace"}],
                    "subject": ["AI"],
                    "published": {"date-parts": [[2026, 5]]},
                },
                {"DOI": "10.1/no-abstract", "title": ["x"], "published": {"date-parts": [[2026, 1, 1]]}},
            ]
        }
    }
    records = parse_crossref_payload(payload)
    assert len(records) == 1
    record = records[0]
    assert record.paper_id == "10.1/abc"
    assert record.title == "A Title"
    assert record.summary == "Hello & world"
    assert record.authors == ["Ada Lovelace"]
    assert record.published == "2026-05-01"


def test_snapshot_parses_24_records(settings):
    payload = read_json(settings.paths.raw_api_response)
    assert len(parse_crossref_payload(payload)) == 24


def test_clean_dataframe_schema_and_dedup(clean_df, settings):
    assert len(clean_df) == 24
    assert clean_df["paper_id"].is_unique
    assert (clean_df["age_days"] >= 0).all()
    first = clean_df.iloc[0]
    assert first["text_for_embedding"].splitlines()[0] == f"Title: {first['title']}"
    assert [line.split(":")[0] for line in first["text_for_embedding"].splitlines()] == [
        "Title", "Authors", "Published", "Categories", "Summary",
    ]

    records = load_raw_records(settings.paths.raw_records_json)
    doubled = build_clean_dataframe(records + records, RUN_DATE)
    assert len(doubled) == 24


def test_quality_gate_passes_on_clean_data(clean_df, settings):
    report = run_data_quality_checks(clean_df, settings, "baseline")
    assert report["success"] is True
    assert report["evaluated_expectations"] >= 4


def test_corruption_is_detected(clean_df, settings, tmp_path: Path):
    corrupted = corrupt_clean_dataframe(clean_df, tmp_path / "log.json")
    log = read_json(tmp_path / "log.json")
    assert len(log["corruptions"]) == 6

    report = run_data_quality_checks(corrupted, settings, "corrupted")
    assert report["success"] is False
    failed = " ".join(report["failed_expectations"])
    assert "unique:paper_id" in failed
    assert "lengths_to_be_between:title" in failed

    freshness = build_freshness_report(corrupted, settings, tmp_path / "fresh.json")
    assert freshness["is_fresh"] is False


def test_repair_is_idempotent(settings):
    records = load_raw_records(settings.paths.raw_records_json)
    first = build_clean_dataframe(records, RUN_DATE)
    second = build_clean_dataframe(records, RUN_DATE)
    pd.testing.assert_frame_equal(first, second)


def test_test_set_covers_four_types(clean_df, tmp_path: Path):
    test_set = build_test_set(clean_df, tmp_path / "test_set.json")
    assert len(test_set) == 10
    assert {item["question_type"] for item in test_set} == {"summary", "authors", "date", "categories"}
    ids = set(clean_df["paper_id"])
    assert all(item["ground_truth_doc_ids"][0] in ids for item in test_set)
