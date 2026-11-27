"""Start/reuse a local Worker, run one experiment, then stop only an owned Worker."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from types import SimpleNamespace

from common import ROOT, options, request_raw, timestamp, validate_snapshot, write_json
from measure_async import run as measure_async
from verify_cloud_state import run as verify_state
from terminal_report import print_async_report, print_state_report


def port_open(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.3):
            return True
    except OSError:
        return False


def check_ready(port, token):
    base = f'http://127.0.0.1:{port}'
    status, body, _, _ = request_raw(base, '/api/health', timeout=1)
    if status != 200 or json.loads(body).get('application') != 'neon-workers-seminar':
        raise RuntimeError('Port is occupied by another application')
    status, body, _, _ = request_raw(base, '/api/state', token, timeout=2)
    if status != 200:
        raise RuntimeError('Existing Worker does not accept the local demo token')
    validate_snapshot(json.loads(body))


def stop_worker(process):
    if process is None or process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        if process.poll() is None:
            process.kill()
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name == 'nt':
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def connect_or_start(port, token, log_path):
    if port_open(port):
        try:
            check_ready(port, token)
        except Exception:
            raise RuntimeError(f'Port {port} is occupied by another application or a Worker with a different token. '
                               'Stop it yourself or use --port with a free port.') from None
        print(f'Using existing local Worker on port {port}; it will be left running.', flush=True)
        return None

    node = shutil.which('node')
    wrangler = ROOT / 'node_modules' / 'wrangler' / 'bin' / 'wrangler.js'
    if not node or not wrangler.exists():
        raise RuntimeError('Node/Wrangler missing. Install Node.js and run npm ci first.')
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'CI': 'true', 'WRANGLER_SEND_METRICS': 'false', 'NO_COLOR': '1'}
    command = [node, str(wrangler), 'dev', '--local', '--ip', '127.0.0.1',
               '--port', str(port), '--persist-to', str(ROOT / 'local-state')]
    flags = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
             if os.name == 'nt' else {'start_new_session': True})
    with log_path.open('w', encoding='utf-8') as output:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=output,
                                   stderr=subprocess.STDOUT, **flags)
    print(f'Starting local Worker on port {port}...', flush=True)
    deadline = time.monotonic() + 40
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f'Wrangler exited with code {process.returncode}; see {log_path}')
            try:
                check_ready(port, token)
                return process
            except Exception:
                time.sleep(0.25)
        raise RuntimeError(f'Worker was not ready within 40 seconds; see {log_path}')
    except BaseException:
        stop_worker(process)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('demo', choices=('async', 'state'))
    parser.add_argument('--port', type=int, default=8787)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    number = 1 if args.demo == 'async' else 2
    output_dir = ROOT / 'results' / 'local' / f'demo{number}'
    record = {'started_at': timestamp(), 'demo': args.demo, 'passed': False,
              'base_url': f'http://127.0.0.1:{args.port}', 'owned_worker': False}
    process = None
    result = None
    exit_code = 1
    try:
        print(f'=== DEMO {number}: {"ASYNC WAITS" if number == 1 else "DISTRIBUTED STATE"} ===', flush=True)
        subprocess.run([sys.executable, str(ROOT / 'scripts' / 'setup_local.py')], check=True)
        base_url, token, _ = options(SimpleNamespace(base_url=record['base_url'], local_token=True, output_dir=output_dir))
        process = connect_or_start(args.port, token, output_dir / 'worker.log')
        record['owned_worker'] = process is not None
        if process is not None:
            record['worker_pid'] = process.pid
        result = (measure_async if args.demo == 'async' else verify_state)(base_url, token, output_dir)
        record['passed'] = result['passed']
        exit_code = 0 if result['passed'] else 1
    except KeyboardInterrupt:
        record['error'] = 'Interrupted by user'
        print('\nInterrupted; cleaning up local Worker...', flush=True)
        exit_code = 130
    except Exception as error:
        record['error'] = f'{type(error).__name__}: {error}'
        print(f'ERROR: {record["error"]}', file=sys.stderr)
    finally:
        try:
            if process is not None:
                stop_worker(process)
                record['owned_worker_stopped'] = process.poll() is not None
                print('Stopped the local Worker started by this demo.', flush=True)
        except Exception as error:
            record['cleanup_error'] = f'{type(error).__name__}: {error}'
            exit_code = 1
        record['finished_at'] = timestamp()
        record['exit_code'] = exit_code
        record['passed'] = record['passed'] and exit_code == 0
        write_json(output_dir / 'launcher_run.json', record)
        if result is not None:
            display = {**result, 'passed': record['passed']}
            if record.get('cleanup_error'):
                display['error'] = record['cleanup_error']
            (print_async_report if args.demo == 'async' else print_state_report)(display)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
