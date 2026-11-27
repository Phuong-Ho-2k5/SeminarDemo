"""Shared Python standard-library HTTP helpers. No implicit request retries."""
import argparse
from datetime import datetime, timezone
import getpass
import http.client
import json
import os
from pathlib import Path
from queue import Empty, Queue
import socket
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
COUNTER_NAME = 'seminar-demo-2'


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def parser(description):
    result = argparse.ArgumentParser(description=description)
    result.add_argument('--base-url', default='http://127.0.0.1:8787')
    result.add_argument('--output-dir', type=Path)
    result.add_argument('--local-token', action='store_true',
                        help='Read ignored .dev.vars; accepted only for loopback URLs')
    return result


def normalize_url(value):
    value = value.rstrip('/')
    parts = urlsplit(value)
    if (parts.scheme not in ('http', 'https') or not parts.netloc or parts.path
            or parts.query or parts.fragment or parts.username or parts.password):
        raise ValueError('--base-url must be an HTTP(S) origin without credentials/path/query/fragment')
    if parts.scheme != 'https' and parts.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('Use HTTPS for a remote deployment')
    return value


def is_local(base_url):
    return urlsplit(base_url).hostname in ('localhost', '127.0.0.1', '::1')


def options(args):
    base_url = normalize_url(args.base_url)
    if args.local_token:
        if not is_local(base_url):
            raise ValueError('--local-token is allowed only with a loopback URL')
        token = ''
        path = ROOT / '.dev.vars'
        if not path.exists():
            raise ValueError('Run npm run setup:local first')
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.startswith('DEMO_TOKEN='):
                token = line.split('=', 1)[1].strip().strip('"').strip("'")
    else:
        token = os.environ.get('DEMO_TOKEN') or getpass.getpass('DEMO_TOKEN (hidden): ')
    if not token or '\n' in token or '\r' in token:
        raise ValueError('DEMO_TOKEN must be nonempty and contain no newlines')
    output = args.output_dir or ROOT / 'results' / ('local' if is_local(base_url) else 'cloud')
    return base_url, token, output


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def request_raw(base_url, route, token=None, method='GET', timeout=15):
    headers = {'Cache-Control': 'no-cache', 'User-Agent': 'NEON-Seminar-Client/1.0'}
    if token is not None:
        headers['Authorization'] = 'Bearer ' + token
    started = time.perf_counter()
    parts = urlsplit(base_url)
    connection_type = http.client.HTTPSConnection if parts.scheme == 'https' else http.client.HTTPConnection
    connection = connection_type(parts.hostname, parts.port, timeout=timeout)
    completed = Queue(maxsize=1)
    cancelled = threading.Event()
    active_socket = [None]

    def shutdown_transport():
        transport = connection.sock or active_socket[0]
        if transport is not None:
            try:
                transport.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def dispatch_once():
        try:
            # http.client neither follows redirects nor retries an HTTP request.
            connection.request(method, route, headers=headers)
            active_socket[0] = connection.sock
            if cancelled.is_set():
                shutdown_transport()
                return
            with connection.getresponse() as response:
                body = response.read()
                elapsed_ms = (time.perf_counter() - started) * 1000
                completed.put((response.status, body, elapsed_ms,
                               {key.lower(): value for key, value in response.headers.items()}))
        except Exception as error:
            completed.put(error)
        finally:
            connection.close()

    # A daemon transport thread lets the caller enforce a total deadline, also
    # during DNS/TLS and a trickling response. Shutdown interrupts body reads;
    # the transport closes itself, without a blocking cross-thread response.close.
    threading.Thread(target=dispatch_once, daemon=True).start()
    try:
        result = completed.get(timeout=max(0, timeout - (time.perf_counter() - started)))
    except Empty:
        cancelled.set()
        shutdown_transport()
        raise TimeoutError(f'Total request deadline {timeout}s exceeded; no retry performed') from None
    if isinstance(result, Exception):
        raise result
    return result


def request_text(base_url, route, token):
    status, body, elapsed_ms, _ = request_raw(base_url, route, token)
    return status, body, elapsed_ms


def request_json(base_url, route, token, method='GET'):
    status, body, _, _ = request_raw(base_url, route, token, method)
    if status != 200:
        raise ValueError(f'{method} {route}: HTTP {status}, {body[:300]!r}')
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError(f'{route}: expected a JSON object')
    return data


def validate_snapshot(value):
    if not isinstance(value, dict):
        raise ValueError('Expected snapshot object')
    for key in ('memory_value', 'durable_value'):
        if type(value.get(key)) is not int or value[key] < 0:
            raise ValueError(f'Invalid {key}')
    for key in ('instance_id', 'object_id'):
        if not isinstance(value.get(key), str) or not value[key]:
            raise ValueError(f'Missing {key}')
    if value.get('counter_name') != COUNTER_NAME:
        raise ValueError('Unexpected object name')
    return value


def print_snapshot(label, value):
    print(f"{label}: RAM={value['memory_value']} SQLite={value['durable_value']} "
          f"instance_id={value['instance_id']} object_id={value['object_id']}", flush=True)
