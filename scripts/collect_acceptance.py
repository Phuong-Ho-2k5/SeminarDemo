"""Reconcile saved real-run artifacts and scan deliverables for secret leakage."""
import csv
import hashlib
import json
from pathlib import Path
import re
import statistics

from common import ROOT, timestamp, write_json


def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def main():
    checks = {}
    evidence = {}
    for environment in ('local', 'cloud'):
        prefix = f'results/{environment}'
        async_result = load(f'{prefix}/async_summary.json')
        state = load(f'{prefix}/state_run.json')
        api = load(f'{prefix}/api_checks.json')
        ui = load(f'{prefix}/ui_checks.json')
        with (ROOT / prefix / 'async_samples.csv').open(encoding='utf-8', newline='') as input_file:
            rows = list(csv.DictReader(input_file))
        valid = len(rows) == 10 and all(row['status'] == '200' and row['body_ok'] == 'True' and not row['error'] for row in rows)
        expected_order = []
        for trial in range(1, 6):
            routes = ['/api/async/seq', '/api/async/parallel']
            expected_order.extend(routes if trial % 2 else reversed(routes))
        checks[f'{environment}_five_alternating_pairs'] = valid and [row['route'] for row in rows] == expected_order
        checks[f'{environment}_warmups'] = len(async_result['warmups']) == 2 and all(not row['error'] for row in async_result['warmups'])
        checks[f'{environment}_median_recalculated'] = all(
            statistics.median(float(row['total_ms']) for row in rows if row['route'] == route)
            == data['median_ms'] and data['valid_samples'] == 5
            for route, data in async_result['routes'].items())
        checks[f'{environment}_async_run'] = async_result['passed']
        checks[f'{environment}_api_contracts'] = api['passed'] and all(item['passed'] for item in api['checks'])
        checks[f'{environment}_ui_dom_http'] = ui['passed'] and all(item['passed'] for item in ui['checks'])
        expected_values = [(0, 0), (3, 3), (0, 3), (1, 4)]
        snapshots = [state[name] for name in ('after_reset', 'before_restart', 'after_restart', 'after_increment')]
        checks[f'{environment}_state_sequence'] = state['passed'] and [
            (value['memory_value'], value['durable_value']) for value in snapshots] == expected_values
        before, after = state['before_restart'], state['after_restart']
        checks[f'{environment}_same_object_new_instance'] = (
            before['object_id'] == after['object_id'] and before['instance_id'] != after['instance_id']
            and before['counter_name'] == after['counter_name'] == 'seminar-demo-2')
        checks[f'{environment}_restart_dispatched_once'] = state['restart_request']['attempts'] == 1
        evidence[environment] = dict(async_routes=async_result['routes'], median_speedup=async_result['median_speedup'],
                                     api_checks=len(api['checks']), ui_dom_checks=len(ui['checks']),
                                     state_before=before, state_after=after)
    checks['missing_secret_real_local_runtime'] = load('results/local/missing_secret.json')['passed']
    commands = load('results/check_commands.json')
    checks['unit_tests_passed'] = commands['npm_test']['exit_code'] == 0
    checks['dry_run_build_passed'] = commands['npm_run_check']['exit_code'] == 0
    checks['final_https_health'] = load('results/cloud/final_health.json')['passed']
    preflight = load('results/cloud/preflight.json')
    checks['no_paid_workers_subscription'] = preflight['subscriptions'] == [] and not preflight['paid_workers_subscription_found']
    tex = (ROOT / 'slides/demo-frames.tex').read_text(encoding='utf-8')
    checks['two_beamer_frames_supplied'] = tex.count('\\begin{frame}') == tex.count('\\end{frame}') == 2
    secrets = []
    local_file = ROOT / '.dev.vars'
    if local_file.exists():
        match = re.search(r'^DEMO_TOKEN="([^"]+)"', local_file.read_text(encoding='utf-8'), re.MULTILINE)
        if match:
            secrets.append(match[1].encode())
    cloud_file = ROOT / '.demo-token'
    if cloud_file.exists():
        secrets.append(cloud_file.read_text(encoding='utf-8').strip().encode())
    leaks = []
    hashes = {}
    for directory in ('src', 'public', 'scripts', 'tests', 'docs', 'slides', 'results', 'dist'):
        for file in (ROOT / directory).rglob('*'):
            if not file.is_file() or '__pycache__' in file.parts:
                continue
            contents = file.read_bytes()
            if any(secret and secret in contents for secret in secrets):
                leaks.append(str(file.relative_to(ROOT)))
            if directory in ('src', 'public'):
                hashes[file.relative_to(ROOT).as_posix()] = hashlib.sha256(contents).hexdigest()
    checks['deliverables_and_bundle_no_secret_leaks'] = not leaks and len(secrets) == 2
    report = dict(recorded_at=timestamp(), functional_checks_passed=all(checks.values()),
                  all_plan_criteria_verified=False, checks=checks, evidence=evidence,
                  source_sha256=hashes, secret_scan_leaked_paths=leaks,
                  blocked=[
                      'Real browser visual/CSP and second-browser checks: Browser runtime reports no connected browser.',
                      'Merge/render the original Beamer deck: no source deck and no TeX compiler supplied; two matching frames are provided.',
                  ])
    write_json(ROOT / 'results/acceptance.json', report)
    print(f"Saved-artifact acceptance: {sum(checks.values())}/{len(checks)} functional checks passed")
    print('Full plan sign-off remains pending the two explicitly blocked visual/deck checks.')
    return 0 if report['functional_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
