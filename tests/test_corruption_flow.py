import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from core.config import load_settings
from ingestion.crossref import load_raw_records
from pipelines.corruption_flow import repair_from_raw_snapshot


class CorruptionFlowTests(unittest.TestCase):
    def test_repair_from_raw_snapshot_is_idempotent(self):
        settings = load_settings()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = replace(
                settings.paths,
                repaired_clean_csv=root / "repaired.csv",
                repaired_clean_json=root / "repaired.json",
            )
            test_settings = replace(settings, paths=paths)
            run_date = datetime(2026, 9, 26, tzinfo=UTC)
            first = repair_from_raw_snapshot(test_settings, run_date)
            second = repair_from_raw_snapshot(test_settings, run_date)
            self.assertEqual(len(first), len(load_raw_records(settings.paths.raw_records_json)))
            self.assertFalse(first.paper_id.duplicated().any())
            self.assertTrue(paths.repaired_clean_csv.exists())
            self.assertTrue(paths.repaired_clean_json.exists())
            self.assertEqual(first.to_json(orient="records"), second.to_json(orient="records"))


if __name__ == "__main__":
    unittest.main()
