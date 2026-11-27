"""Warm up once per route, then measure five alternating pairs, without retries."""
import csv
import platform
import statistics
import sys

from common import options, parser, request_text, timestamp, write_json

ROUTES = ('/api/async/seq', '/api/async/parallel')
EXPECTED_BODY = b'done\n'


def sample(base_url, route, token, trial):
    row = dict(trial=trial, route=route, status=None, total_ms=None, body_ok=False, error='')
    try:
        status, body, elapsed = request_text(base_url, route, token)
        row.update(status=status, total_ms=round(elapsed, 3), body_ok=body == EXPECTED_BODY)
        if status != 200 or not row['body_ok']:
            row['error'] = f'Expected HTTP 200 and done\\n; got HTTP {status}, body={body[:100]!r}'
    except Exception as error:
        row['error'] = f'{type(error).__name__}: {error}'
    return row


def run(base_url, token, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    warmups = [sample(base_url, route, token, 0) for route in ROUTES]
    for row in warmups:
        print(f"warm-up {row['route']}: {row['total_ms']} ms; {row['error'] or 'OK'}", flush=True)
    rows = []
    for trial in range(1, 6):
        order = ROUTES if trial % 2 else tuple(reversed(ROUTES))
        for route in order:
            row = sample(base_url, route, token, trial)
            rows.append(row)
            print(f"trial {trial} {route:20} HTTP {row['status']} {row['total_ms']} ms; "
                  f"{row['error'] or 'body OK'}", flush=True)
    with (output_dir / 'async_samples.csv').open('w', newline='', encoding='utf-8') as output:
        writer = csv.DictWriter(output, fieldnames=['trial', 'route', 'status', 'total_ms', 'body_ok', 'error'])
        writer.writeheader()
        writer.writerows(rows)
    result = {
        'recorded_at': timestamp(), 'base_url': base_url, 'python': platform.python_version(),
        'clock': 'time.perf_counter; includes full response.read()',
        'trials_per_route': 5, 'warmups': warmups,
        'passed': all(not row['error'] for row in warmups + rows), 'routes': {},
    }
    for route in ROUTES:
        valid = [row['total_ms'] for row in rows if row['route'] == route and not row['error']]
        result['routes'][route] = dict(valid_samples=len(valid), invalid_samples=5 - len(valid),
                                       median_ms=statistics.median(valid) if valid else None)
    seq, parallel = (result['routes'][route]['median_ms'] for route in ROUTES)
    result['median_speedup'] = seq / parallel if seq is not None and parallel else None
    result['parallel_faster_observed'] = parallel < seq if seq is not None and parallel is not None else None
    write_json(output_dir / 'async_summary.json', result)
    for route, data in result['routes'].items():
        print(f"{route}: median={data['median_ms']} ms; valid={data['valid_samples']}/5", flush=True)
    print(f"Median speedup: {result['median_speedup']}; {'PASS' if result['passed'] else 'FAIL'}", flush=True)
    print(f'Artifacts: {output_dir.resolve()}', flush=True)
    return result


def main():
    try:
        result = run(*options(parser(__doc__).parse_args()))
        return 0 if result['passed'] else 1
    except (ValueError, OSError, EOFError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
