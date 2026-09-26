from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from core.utils import compact_join, now_utc, write_json
from ingestion.cleaning import build_embedding_text

SEED = 42
DROP_LATEST_RATIO = 0.20
BLANK_SUMMARY_ROWS = 3
NOISE_ROWS = 3
TRUNCATE_TITLE_ROWS = 3
TRUNCATED_TITLE_CHARS = 6
STALE_DATE_ROWS = 6
STALE_SHIFT_DAYS = 3 * 365
DUPLICATE_ROWS = 3
NOISE_TOKENS = ["#@!", "~~~", "<?>", "%%", "��", "NULL", "0xDEADBEEF", "&&&"]


def _inject_noise(text: str, rng: np.random.Generator) -> str:
    words = text.split()
    noisy: list[str] = []
    for position, word in enumerate(words):
        if position % 2 == 0:
            noisy.append(str(rng.choice(NOISE_TOKENS)))
        noisy.append(word[::-1] if position % 3 == 0 else word)
    return " ".join(noisy)


def _log_entry(corruption_type: str, description: str, paper_ids: list[str], **extra: Any) -> dict[str, Any]:
    return {
        "corruption_type": corruption_type,
        "description": description,
        "affected_rows": len(paper_ids),
        "affected_paper_ids": paper_ids,
        **extra,
    }


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Gia lap 6 dang data corruption (deterministic voi SEED) va ghi corruption log."""
    rng = np.random.default_rng(SEED)
    corrupted = df.copy(deep=True).reset_index(drop=True)
    log: list[dict[str, Any]] = []

    # 1. Drop latest records: mat 20% ban ghi moi nhat (mo phong ingestion bi dut giua chung).
    drop_count = math.ceil(len(corrupted) * DROP_LATEST_RATIO)
    latest = corrupted.sort_values("published", ascending=False).head(drop_count)
    log.append(
        _log_entry(
            "drop_latest_records",
            f"Removed the {drop_count} most recently published records ({DROP_LATEST_RATIO:.0%}).",
            latest["paper_id"].tolist(),
        )
    )
    corrupted = corrupted.drop(index=latest.index).reset_index(drop=True)

    # Chia cac nhom row roi nhau de moi loai loi tac dong doc lap.
    order = rng.permutation(len(corrupted)).tolist()
    groups: dict[str, list[int]] = {}
    for name, size in [
        ("blank", BLANK_SUMMARY_ROWS),
        ("noise", NOISE_ROWS),
        ("truncate", TRUNCATE_TITLE_ROWS),
        ("stale", STALE_DATE_ROWS),
    ]:
        groups[name], order = order[:size], order[size:]

    # 2. Blank summary.
    rows = groups["blank"]
    corrupted.loc[rows, "summary"] = ""
    log.append(_log_entry("blank_summary", "Replaced summary with an empty string.", corrupted.loc[rows, "paper_id"].tolist()))

    # 3. Inject noise vao summary.
    rows = groups["noise"]
    corrupted.loc[rows, "summary"] = [_inject_noise(text, rng) for text in corrupted.loc[rows, "summary"]]
    log.append(
        _log_entry(
            "inject_noise",
            "Interleaved garbage tokens and reversed words inside the summary.",
            corrupted.loc[rows, "paper_id"].tolist(),
        )
    )

    # 4. Truncate title < 8 ky tu.
    rows = groups["truncate"]
    original_titles = corrupted.loc[rows, "title"].tolist()
    corrupted.loc[rows, "title"] = [title[:TRUNCATED_TITLE_CHARS] for title in original_titles]
    log.append(
        _log_entry(
            "truncate_title",
            f"Cut title down to {TRUNCATED_TITLE_CHARS} characters.",
            corrupted.loc[rows, "paper_id"].tolist(),
            examples=[{"before": b, "after": b[:TRUNCATED_TITLE_CHARS]} for b in original_titles],
        )
    )

    # 5. Stale date: lui ngay xuat ban ve qua khu, cap nhat age_days tuong ung.
    rows = groups["stale"]
    old_dates = pd.to_datetime(corrupted.loc[rows, "published"])
    corrupted.loc[rows, "published"] = (old_dates - pd.Timedelta(days=STALE_SHIFT_DAYS)).dt.strftime("%Y-%m-%d").tolist()
    corrupted.loc[rows, "age_days"] = corrupted.loc[rows, "age_days"].astype(int) + STALE_SHIFT_DAYS
    log.append(
        _log_entry(
            "stale_date",
            f"Shifted published date back by {STALE_SHIFT_DAYS} days.",
            corrupted.loc[rows, "paper_id"].tolist(),
        )
    )

    # 6. Duplicate rows.
    dup_rows = rng.choice(len(corrupted), size=DUPLICATE_ROWS, replace=False).tolist()
    duplicates = corrupted.loc[dup_rows]
    corrupted = pd.concat([corrupted, duplicates], ignore_index=True)
    log.append(_log_entry("duplicate_rows", "Appended exact duplicate rows.", duplicates["paper_id"].tolist()))

    # 7. Rebuild cot phai sinh de corruption lan vao text_for_embedding.
    corrupted["authors_joined"] = corrupted["authors"].apply(compact_join)
    corrupted["categories_joined"] = corrupted["categories"].apply(compact_join)
    corrupted["summary_chars"] = corrupted["summary"].str.len()
    corrupted["age_days"] = corrupted["age_days"].astype(int)
    corrupted["text_for_embedding"] = corrupted.apply(build_embedding_text, axis=1)

    # 8. Ghi corruption log.
    write_json(
        output_log_path,
        {
            "generated_at": now_utc().isoformat(),
            "seed": SEED,
            "input_rows": int(len(df)),
            "output_rows": int(len(corrupted)),
            "corruptions": log,
        },
    )
    return corrupted
