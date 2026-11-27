"""Verify 0/0 -> 3/3 -> ctx.abort -> 0/3 -> 1/4 on the same object."""
import sys
import time

from common import (COUNTER_NAME, options, parser, print_snapshot, request_json,
                    timestamp, validate_snapshot, write_json)


def run(base_url, token, output_dir):
    result = dict(base_url=base_url, recorded_at=timestamp(), counter_name=COUNTER_NAME,
                  passed=False, checks={}, increments=[], polls=[])

    def read():
        return validate_snapshot(request_json(base_url, '/api/state', token))

    def post(action):
        return validate_snapshot(request_json(base_url, f'/api/state/{action}', token, 'POST'))

    def require(name, condition):
        result['checks'][name] = bool(condition)
        if not condition:
            raise ValueError(f'Check failed: {name}')

    def values(data, memory, durable):
        return (data['memory_value'], data['durable_value']) == (memory, durable)

    try:
        reset = post('reset')
        result['after_reset'] = reset
        print_snapshot('After reset', reset)
        require('reset_zero_zero', values(reset, 0, 0))
        for step in range(1, 4):
            snapshot = post('increment')
            result['increments'].append(snapshot)
            require(f'increment_{step}', values(snapshot, step, step))
            require(f'identity_stable_{step}',
                    snapshot['object_id'] == reset['object_id'] and snapshot['instance_id'] == reset['instance_id'])
        before = read()
        result['before_restart'] = before
        require('before_three_three', values(before, 3, 3))
        require('read_does_not_mutate', before == read())
        print_snapshot('Before restart', before)
        result['restart_request'] = {'attempts': 1}
        try:
            response = request_json(base_url, '/api/state/restart', token, 'POST')
            result['restart_request']['response'] = response
        except Exception as error:
            # A broken restart response is expected, but is NOT proof of restart.
            result['restart_request']['error'] = f'{type(error).__name__}: {error}'
        for attempt in range(1, 11):
            if attempt > 1:
                time.sleep(0.5)
            try:
                observed = read()
            except Exception as error:
                result['polls'].append(dict(attempt=attempt, error=f'{type(error).__name__}: {error}'))
                continue
            result['polls'].append(dict(attempt=attempt, snapshot=observed))
            require('same_object_id', observed['object_id'] == before['object_id'])
            require('same_counter_name', observed['counter_name'] == before['counter_name'])
            if observed['instance_id'] != before['instance_id']:
                result['after_restart'] = observed
                break
        require('new_instance', 'after_restart' in result)
        after = result['after_restart']
        print_snapshot('After restart', after)
        require('after_zero_three', values(after, 0, 3))
        updated = post('increment')
        result['after_increment'] = updated
        require('after_one_four', values(updated, 1, 4))
        require('final_identity_stable', updated['object_id'] == before['object_id']
                and updated['instance_id'] == after['instance_id'])
        result['final_read'] = read()
        require('final_get_unchanged', result['final_read'] == updated)
        print_snapshot('After one more increment', updated)
        result['passed'] = all(result['checks'].values())
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
    write_json(output_dir / 'state_run.json', result)
    print('STATE ' + ('PASS' if result['passed'] else f"FAIL: {result.get('error', 'checks failed')}"), flush=True)
    print(f'Artifact: {(output_dir / "state_run.json").resolve()}', flush=True)
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
