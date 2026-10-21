#!/usr/bin/env python3
"""Collect public release asset counts and retain daily 30-day comparisons."""

import argparse
import json
import re
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def github_list(endpoint):
    output = subprocess.check_output(
        ['gh', 'api', '--paginate', '--jq', '.[] | tojson', endpoint], text=True,
    )
    return [json.loads(line) for line in output.splitlines() if line.strip()]


def check_assets(assets):
    if not isinstance(assets, dict) or not all(
        isinstance(key, str) and key.isdigit() and type(value) is int and value >= 0
        for key, value in assets.items()
    ):
        raise ValueError('Invalid release asset counters')


def collect_assets(repository):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Expected owner/repository')
    assets = {}
    for release in github_list('repos/' + repository + '/releases?per_page=100'):
        if release['draft']:
            continue
        release_id = release['id']
        if type(release_id) is not int or release_id <= 0:
            raise ValueError('Invalid release ID')
        endpoint = 'repos/{}/releases/{}/assets?per_page=100'.format(repository, release_id)
        for asset in github_list(endpoint):
            asset_id = asset['id']
            if type(asset_id) is not int or asset_id <= 0 or str(asset_id) in assets:
                raise ValueError('Invalid or duplicate asset ID')
            assets[str(asset_id)] = asset['download_count']
    check_assets(assets)
    return assets


def compact(value):
    for divisor, suffix in ((10**9, 'B'), (10**6, 'M'), (10**3, 'k')):
        if value >= divisor:
            return ('{:.1f}'.format(value / divisor).rstrip('0').rstrip('.')) + suffix
    return str(value)


def update_stats(previous, assets, now):
    check_assets(assets)
    today = now.date()
    cutoff = today - timedelta(days=30)
    if previous is None:
        history = []
    else:
        if previous['schema_version'] != 1 or not isinstance(previous['history'], list):
            raise ValueError('Invalid release statistics history')
        history = previous['history']
    last_date = None
    last_assets = {}
    for sample in history:
        sample_date = date.fromisoformat(sample['date'])
        check_assets(sample['assets'])
        if sample_date > today or (last_date is not None and sample_date <= last_date):
            raise ValueError('Release history must have unique ascending nonfuture dates')
        if any(sample['assets'].get(key, -1) < count for key, count in last_assets.items()):
            raise ValueError('Invalid decreasing counters in release history')
        last_date = sample_date
        last_assets = sample['assets']
    # Deleted/replaced assets or decreased counters invalidate cumulative deltas.
    # Restart collection rather than display negative or understated downloads.
    if history and any(assets.get(key, -1) < count for key, count in history[-1]['assets'].items()):
        history = []
    history = [sample for sample in history if cutoff <= date.fromisoformat(sample['date']) < today]
    baseline = next((sample['assets'] for sample in history if sample['date'] == cutoff.isoformat()), None)
    month = None if baseline is None else sum(assets.values()) - sum(baseline.values())
    history.append({'date': today.isoformat(), 'assets': dict(assets)})
    total = sum(assets.values())
    return {
        'schema_version': 1,
        'last_collected': now.isoformat(),
        'downloads': total,
        'downloads_compact': compact(total),
        'downloads_month': month,
        'downloads_month_compact': 'collecting' if month is None else compact(month),
        'history': history,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', default='janilahti/renyyt')
    parser.add_argument('--path', type=Path, default=Path('release-stats.json'))
    args = parser.parse_args()
    previous = json.loads(args.path.read_text()) if args.path.exists() else None
    stats = update_stats(previous, collect_assets(args.repository), datetime.now(timezone.utc))
    temporary = args.path.with_name(args.path.name + '.tmp')
    temporary.write_text(json.dumps(stats, indent=2, sort_keys=True) + '\n')
    temporary.replace(args.path)


if __name__ == '__main__':
    main()
