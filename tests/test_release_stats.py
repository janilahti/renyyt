"""Check honest rolling counts without conflating release age with download age."""

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    'release_stats', Path(__file__).resolve().parents[1] / 'scripts/release_stats.py',
)
stats = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stats)


class ReleaseStatsTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2030, 2, 1, 3, 17, tzinfo=timezone.utc)

    def test_first_sample_is_not_a_month_of_downloads(self):
        result = stats.update_stats(None, {'1': 55, '2': 7}, self.now)
        self.assertEqual(result['downloads'], 62)
        self.assertIsNone(result['downloads_month'])
        self.assertEqual(result['downloads_month_compact'], 'collecting')

    def test_month_uses_download_deltas_including_new_assets(self):
        result = stats.update_stats(None, {'1': 100}, self.now - timedelta(days=30))
        result = stats.update_stats(result, {'1': 140, '2': 9}, self.now)
        self.assertEqual(result['downloads'], 149)
        self.assertEqual(result['downloads_month'], 49)

    def test_same_day_rerun_replaces_sample_and_keeps_baseline(self):
        result = stats.update_stats(None, {'1': 100}, self.now - timedelta(days=30))
        result = stats.update_stats(result, {'1': 110}, self.now)
        result = stats.update_stats(result, {'1': 115}, self.now + timedelta(hours=1))
        self.assertEqual(len(result['history']), 2)
        self.assertEqual(result['downloads_month'], 15)

    def test_history_is_bounded_and_zero_is_a_real_zero(self):
        result = None
        for day in range(65):
            result = stats.update_stats(result, {'1': 8}, self.now + timedelta(days=day))
        self.assertEqual(len(result['history']), 31)
        self.assertEqual(result['downloads_month'], 0)
        self.assertEqual(result['downloads_month_compact'], '0')

    def test_missing_cutoff_day_does_not_silently_extend_window(self):
        result = stats.update_stats(None, {'1': 100}, self.now - timedelta(days=31))
        result = stats.update_stats(result, {'1': 150}, self.now)
        self.assertIsNone(result['downloads_month'])

    def test_removed_replaced_or_reset_asset_restarts_history(self):
        for current in ({'1': 9}, {'2': 500}, {'1': 10, '3': 500}):
            with self.subTest(current=current):
                old = stats.update_stats(None, {'1': 10, '2': 50}, self.now - timedelta(days=30))
                result = stats.update_stats(old, current, self.now)
                self.assertIsNone(result['downloads_month'])
                self.assertEqual(len(result['history']), 1)
                self.assertEqual(result['downloads'], sum(current.values()))

    def test_invalid_values_and_malformed_history_fail(self):
        for assets in ({'1': True}, {'1': -1}, {'1': '9'}, {'bad': 9}, []):
            with self.subTest(assets=assets), self.assertRaises(ValueError):
                stats.update_stats(None, assets, self.now)
        future = stats.update_stats(None, {'1': 1}, self.now + timedelta(days=1))
        with self.assertRaises(ValueError):
            stats.update_stats(future, {'1': 2}, self.now)
        repeated = stats.update_stats(None, {'1': 1}, self.now)
        repeated['history'] *= 2
        with self.assertRaises(ValueError):
            stats.update_stats(repeated, {'1': 2}, self.now)

    def test_github_pages_are_all_read(self):
        output = '\n'.join(json.dumps({'id': number}) for number in (1, 2, 3)) + '\n'
        with patch.object(stats.subprocess, 'check_output', return_value=output) as call:
            self.assertEqual(stats.github_list('repos/example/project/releases'), [{'id': 1}, {'id': 2}, {'id': 3}])
            self.assertIn('--paginate', call.call_args[0][0])
            self.assertIn('.[] | tojson', call.call_args[0][0])

    def test_collects_all_public_assets_including_prereleases_not_drafts(self):
        pages = [
            [{'id': 1, 'draft': False}, {'id': 2, 'draft': True}, {'id': 3, 'draft': False}],
            [{'id': 10, 'download_count': 9}],
            [{'id': 11, 'download_count': 5}],
        ]
        with patch.object(stats, 'github_list', side_effect=pages) as call:
            self.assertEqual(stats.collect_assets('example/project'), {'10': 9, '11': 5})
            self.assertEqual(call.call_count, 3)
            self.assertIn('/releases/3/assets?', call.call_args[0][0])

    def test_network_errors_do_not_turn_into_zero_downloads(self):
        with patch.object(stats, 'github_list', side_effect=RuntimeError('network unavailable')):
            with self.assertRaises(RuntimeError):
                stats.collect_assets('example/project')

    def test_failed_collection_preserves_the_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'stats.json'
            original = json.dumps(stats.update_stats(None, {'1': 20}, self.now))
            path.write_text(original)
            with patch('sys.argv', ['release_stats.py', '--path', str(path)]), \
                    patch.object(stats, 'collect_assets', side_effect=RuntimeError('API failure')):
                with self.assertRaises(RuntimeError):
                    stats.main()
            self.assertEqual(path.read_text(), original)
            self.assertFalse(path.with_name('stats.json.tmp').exists())

    def test_compact_counts(self):
        for count, label in ((0, '0'), (11, '11'), (1200, '1.2k'), (2000000, '2M')):
            self.assertEqual(stats.compact(count), label)
