from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import html
from pathlib import Path
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

CROSSREF_URL = "https://api.crossref.org/works"
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _clean_text(value: str | None) -> str:
    """Bo the HTML/XML (vd `<jats:p>`), decode entity va chuan hoa khoang trang."""
    if not value:
        return ""
    text = TAG_PATTERN.sub(" ", value)
    return normalize_whitespace(html.unescape(text))


def _first(values: list | None) -> str:
    return _clean_text(values[0]) if values else ""


def _date_from_parts(field: dict | None) -> str:
    """Chuyen `{"date-parts": [[y, m, d]]}` thanh ISO date (thieu thang/ngay -> 1)."""
    if not field:
        return ""
    parts = (field.get("date-parts") or [[]])[0]
    if not parts or parts[0] is None:
        return ""
    year, month, day = (list(parts) + [1, 1])[:3]
    try:
        return date(int(year), int(month or 1), int(day or 1)).isoformat()
    except (TypeError, ValueError):
        return ""


def _date_from_datetime(field: dict | None) -> str:
    if not field or not field.get("date-time"):
        return ""
    return str(field["date-time"])[:10]


def _parse_authors(authors: list[dict] | None) -> list[str]:
    names: list[str] = []
    for author in authors or []:
        name = " ".join(part for part in (author.get("given"), author.get("family")) if part)
        name = _clean_text(name or author.get("name"))
        if name:
            names.append(name)
    return names


def _parse_item(item: dict) -> PaperRecord | None:
    doi = normalize_whitespace(item.get("DOI") or "").lower()
    title = _first(item.get("title"))
    summary = _clean_text(item.get("abstract"))
    if not doi or not title or not summary:
        return None

    published = (
        _date_from_parts(item.get("published"))
        or _date_from_parts(item.get("published-online"))
        or _date_from_parts(item.get("published-print"))
        or _date_from_parts(item.get("issued"))
        or _date_from_datetime(item.get("created"))
    )
    if not published:
        return None
    updated = (
        _date_from_datetime(item.get("indexed"))
        or _date_from_datetime(item.get("deposited"))
        or published
    )

    categories = [_clean_text(subject) for subject in item.get("subject") or []]
    categories = [category for category in categories if category]
    abs_url = item.get("URL") or f"https://doi.org/{doi}"
    pdf_url = next(
        (link.get("URL") for link in item.get("link") or [] if link.get("content-type") == "application/pdf"),
        abs_url,
    )

    return PaperRecord(
        paper_id=doi,
        title=title,
        summary=summary,
        authors=_parse_authors(item.get("author")),
        categories=categories,
        primary_category=categories[0] if categories else "",
        published=published,
        updated=updated,
        abs_url=abs_url,
        pdf_url=pdf_url,
        comment=f"Crossref record {doi}",
    )


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thanh list PaperRecord, bo qua record khong hop le."""
    items = (payload.get("message") or {}).get("items") or []
    records: list[PaperRecord] = []
    for item in items:
        record = _parse_item(item)
        if record is not None:
            records.append(record)
    return records


def _request_crossref(settings: Settings) -> dict:
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "sort": "published",
        "order": "desc",
    }
    headers = {"User-Agent": "day10-data-observability-lab/0.1 (educational use)"}
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(CROSSREF_URL, params=params, headers=headers, timeout=30)
            if response.status_code in RETRY_STATUS_CODES:
                raise requests.HTTPError(f"Crossref returned {response.status_code}", response=response)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(2**attempt)
    raise RuntimeError(f"Crossref request failed after {MAX_ATTEMPTS} attempts: {last_error}")


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Goi Crossref API (hoac fallback snapshot), luu raw response + records.

    - Mac dinh (REFRESH_SOURCE tat) va da co snapshot: doc snapshot, khong goi API (tranh rate limit).
    - REFRESH_SOURCE=1 hoac chua co snapshot: goi API voi retry; loi mang/429 -> fallback ve snapshot.
    """
    snapshot_path = settings.paths.raw_api_response
    payload: dict | None = None

    if settings.refresh_source or not snapshot_path.exists():
        try:
            payload = _request_crossref(settings)
            if not parse_crossref_payload(payload):
                raise RuntimeError("Crossref returned no valid records")
        except RuntimeError as exc:
            if not snapshot_path.exists():
                raise
            print(f"[crossref] API unavailable ({exc}); falling back to snapshot {snapshot_path}")
            payload = None

    if payload is None:
        payload = read_json(snapshot_path)
    else:
        write_json(snapshot_path, payload)

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh `PaperRecord`."""
    return [PaperRecord(**row) for row in read_json(path)]
