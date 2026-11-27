"""Exercise real HTTP contracts, authentication and concurrent SQL increments."""
from concurrent.futures import ThreadPoolExecutor
import sys

from common import (options, parser, request_json, request_raw, timestamp,
                    validate_snapshot, write_json)


def run(base_url, token, output_dir):
    result = dict(base_url=base_url, recorded_at=timestamp(), passed=False, checks=[])

    def check(name, condition):
        result['checks'].append(dict(name=name, passed=bool(condition)))
        if not condition:
            raise ValueError(f'Check failed: {name}')

    try:
        status, body, _, headers = request_raw(base_url, '/api/health')
        check('public health', status == 200 and b'neon-workers-seminar' in body)
        check('health no-store', headers.get('cache-control') == 'no-store')
        for path in ('/', '/app.js', '/demo-client.js', '/style.css'):
            status, _, _, headers = request_raw(base_url, path)
            check(f'static {path}', status == 200)
            check(f'static CSP {path}', "script-src 'self'" in headers.get('content-security-policy', ''))
        protected = [('/api/async/seq', 'GET'), ('/api/async/parallel', 'GET'),
                     ('/api/state', 'GET'), ('/api/state/increment', 'POST'),
                     ('/api/state/reset', 'POST'), ('/api/state/restart', 'POST')]
        for route, method in protected:
            for credential, label in ((None, 'missing'), ('invalid-test-token', 'wrong')):
                status, _, _, headers = request_raw(base_url, route, credential, method)
                check(f'{label} token {method} {route}', status == 401)
                check(f'unauth no-store {label} {route}', headers.get('cache-control') == 'no-store')
        initial = validate_snapshot(request_json(base_url, '/api/state', token))
        for route, allowed in protected:
            wrong_method = 'POST' if allowed == 'GET' else 'GET'
            status, _, _, headers = request_raw(base_url, route, token, wrong_method)
            check(f'method guard {route}', status == 405 and headers.get('allow') == allowed)
        for route in ('/api/unknown', '/api/state/unknown', '/buffer', '/stream'):
            status, _, _, _ = request_raw(base_url, route, token)
            check(f'unknown {route}', status == 404)
        for index in range(3):
            check(f'GET invariance {index + 1}', request_json(base_url, '/api/state', token) == initial)
        for route in ('/api/async/seq', '/api/async/parallel'):
            status, body, _, headers = request_raw(base_url, route, token)
            check(f'body {route}', status == 200 and body == b'done\n')
            check(f'headers {route}', headers.get('cache-control') == 'no-store'
                  and headers.get('content-type') == 'text/plain; charset=utf-8'
                  and bool(headers.get('x-request-id')))
        reset = validate_snapshot(request_json(base_url, '/api/state/reset', token, 'POST'))
        check('reset 0/0', reset['memory_value'] == reset['durable_value'] == 0)

        def increment(_):
            return validate_snapshot(request_json(base_url, '/api/state/increment', token, 'POST'))

        count = 20
        with ThreadPoolExecutor(max_workers=5) as executor:
            writes = list(executor.map(increment, range(count)))
        result['concurrent_increments'] = writes
        check('atomic unique durable increments', sorted(item['durable_value'] for item in writes) == list(range(1, count + 1)))
        check('RAM and SQL same snapshot', all(item['memory_value'] == item['durable_value'] for item in writes))
        check('concurrent same instance', all(item['instance_id'] == reset['instance_id'] for item in writes))
        check('concurrent same object', all(item['object_id'] == reset['object_id'] for item in writes))
        final = request_json(base_url, '/api/state', token)
        check('concurrent final 20/20', final['memory_value'] == final['durable_value'] == count)
        request_json(base_url, '/api/state/reset', token, 'POST')
        result['passed'] = True
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
    write_json(output_dir / 'api_checks.json', result)
    print(f"API {'PASS' if result['passed'] else 'FAIL'}: "
          f"{sum(item['passed'] for item in result['checks'])}/{len(result['checks'])} assertions")
    if not result['passed']:
        print(result['error'])
    print(f'Artifact: {(output_dir / "api_checks.json").resolve()}')
    return result


def main():
    try:
        return 0 if run(*options(parser(__doc__).parse_args()))['passed'] else 1
    except (ValueError, OSError, EOFError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
