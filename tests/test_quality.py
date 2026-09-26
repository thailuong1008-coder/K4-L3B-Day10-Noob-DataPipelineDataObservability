import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from core.config import load_settings
from core.utils import read_json
from observability.quality import build_freshness_report, evaluate_freshness_sla, run_data_quality_checks


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        settings = load_settings()
        self.settings = replace(settings, paths=replace(settings.paths, quality_dir=Path(self.tmp.name)))
        self.df = pd.DataFrame({
            'paper_id': [f'paper-{i}' for i in range(8)],
            'title': ['A paper'] * 8,
            'summary': ['A sufficiently long summary for quality validation.'] * 8,
            'text_for_embedding': ['Title: A paper'] * 8,
            'age_days': [180] * 8,
            'published': ['2026-01-01'] * 8,
        })

    def test_valid_and_persisted_report(self):
        report = run_data_quality_checks(self.df, self.settings, 'baseline')
        self.assertTrue(report['success'])
        self.assertEqual(len(report['results']), 6)
        self.assertEqual(read_json(self.settings.paths.quality_dir / 'baseline_quality_report.json'), report)

    def test_each_required_rule_rejects_bad_data(self):
        cases = {'too_few': self.df.iloc[:4], 'too_many': pd.concat([self.df] * 626, ignore_index=True)}
        for column in ['paper_id', 'title', 'text_for_embedding']:
            bad = self.df.copy()
            bad.loc[0, column] = None
            cases[f'null_{column}'] = bad
        duplicate = self.df.copy()
        duplicate.loc[1, 'paper_id'] = duplicate.loc[0, 'paper_id']
        cases['duplicate'] = duplicate
        short = self.df.copy()
        short.loc[0, 'summary'] = 'x' * 29
        cases['short_summary'] = short
        cases['missing_column'] = self.df.drop(columns='title')
        cases['empty'] = self.df.iloc[:0]
        for name, df in cases.items():
            with self.subTest(name=name):
                self.assertFalse(run_data_quality_checks(df, self.settings, name)['success'])

    def test_freshness_boundaries_and_gate(self):
        self.assertEqual(evaluate_freshness_sla(self.df, self.settings)['stale_rows'], 0)
        self.df.loc[:1, 'age_days'] = 181
        self.df['summary'] = 'x' * 30
        self.assertTrue(run_data_quality_checks(self.df, self.settings, 'boundary')['success'])
        self.df.loc[2, 'age_days'] = 181
        report = run_data_quality_checks(self.df, self.settings, 'stale')
        self.assertTrue(report['gx_success'])
        self.assertFalse(report['success'])
        self.assertEqual(report['freshness']['stale_ratio'], 3 / 8)
        self.df.loc[0, 'age_days'] = None
        self.assertFalse(evaluate_freshness_sla(self.df, self.settings)['is_fresh'])
        self.assertFalse(evaluate_freshness_sla(self.df.iloc[:0], self.settings)['is_fresh'])

    def test_freshness_report_dates(self):
        path = self.settings.paths.quality_dir / 'freshness.json'
        report = build_freshness_report(self.df, self.settings, path)
        self.assertEqual(report['latest_published'], '2026-01-01')
        self.assertEqual(report['oldest_published'], '2026-01-01')
        self.assertEqual(read_json(path), report)


if __name__ == '__main__':
    unittest.main()
