import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import measure_async
import verify_cloud_state as state
import common


def snapshot(memory, durable, instance='before', object_id='stable-object'):
    return dict(memory_value=memory, durable_value=durable, instance_id=instance,
                object_id=object_id, counter_name='seminar-demo-2')


class ScriptTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name)
        self.quiet = contextlib.redirect_stdout(io.StringIO())
        self.quiet.__enter__()
        self.addCleanup(self.quiet.__exit__, None, None, None)

    def test_measure_warmups_alternation_and_median(self):
        routes = []

        def request(base, route, token):
            routes.append(route)
            return 200, b'done\n', 3000.0 if route.endswith('/seq') else 1000.0

        with patch.object(measure_async, 'request_text', side_effect=request):
            result = measure_async.run('http://localhost:8787', 'test-only', self.output)
        self.assertTrue(result['passed'])
        self.assertEqual(len(routes), 12)
        self.assertEqual(routes[2:6], ['/api/async/seq', '/api/async/parallel',
                                      '/api/async/parallel', '/api/async/seq'])
        self.assertEqual(result['routes']['/api/async/seq']['valid_samples'], 5)
        self.assertEqual(result['routes']['/api/async/seq']['median_ms'], 3000.0)
        self.assertNotIn('test-only', (self.output / 'async_summary.json').read_text())

    def test_http_client_identifies_itself_to_cloudflare(self):
        with patch.object(common.http.client, 'HTTPSConnection') as connection:
            response = connection.return_value.getresponse.return_value.__enter__.return_value
            response.read.return_value = b'done\n'
            response.status = 200
            response.headers.items.return_value = [('Cache-Control', 'no-store')]
            common.request_raw('https://example.test', '/api/health')
            headers = connection.return_value.request.call_args.kwargs['headers']
            self.assertEqual(headers['User-Agent'], 'NEON-Seminar-Client/1.0')

    def test_total_deadline_interrupts_trickling_body_without_repeating_post(self):
        received = []

        class SlowHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(self.path)
                self.send_response(200)
                self.send_header('Content-Length', '20')
                self.end_headers()
                try:
                    for _ in range(20):
                        self.wfile.write(b'x')
                        self.wfile.flush()
                        time.sleep(0.04)  # Each byte arrives before socket inactivity timeout.
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), SlowHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            started = time.perf_counter()
            with self.assertRaises(TimeoutError):
                common.request_raw(f'http://127.0.0.1:{server.server_port}', '/slow',
                                   method='POST', timeout=0.15)
            self.assertLess(time.perf_counter() - started, 0.7)
            self.assertEqual(received, ['/slow'])
        finally:
            server.shutdown()
            server.server_close()

    def test_bad_samples_saved_without_retry_or_fake_median(self):
        with patch.object(measure_async, 'request_text', side_effect=TimeoutError('test timeout')) as request:
            result = measure_async.run('http://localhost:8787', 'test-only', self.output)
        self.assertFalse(result['passed'])
        self.assertEqual(request.call_count, 12)
        self.assertIsNone(result['routes']['/api/async/seq']['median_ms'])
        self.assertEqual(result['routes']['/api/async/seq']['invalid_samples'], 5)
        self.assertEqual(len((self.output / 'async_samples.csv').read_text().splitlines()), 11)

    def run_state(self, responder):
        with patch.object(state, 'request_json', side_effect=responder), patch.object(state.time, 'sleep'):
            return state.run('http://localhost:8787', 'test-only', self.output)

    def test_abort_error_then_real_snapshot_is_required_for_success(self):
        calls = []
        current = snapshot(0, 0)

        def respond(base, route, token, method='GET'):
            nonlocal current
            calls.append((route, method))
            if route.endswith('/reset'):
                current = snapshot(0, 0)
            elif route.endswith('/increment'):
                current = {**current, 'memory_value': current['memory_value'] + 1,
                           'durable_value': current['durable_value'] + 1}
            elif route.endswith('/restart'):
                current = snapshot(0, 3, 'after')
                raise RuntimeError('restart transport ended')
            return current.copy()

        result = self.run_state(respond)
        self.assertTrue(result['passed'])
        self.assertEqual(result['after_restart']['durable_value'], 3)
        self.assertEqual(result['after_increment']['durable_value'], 4)
        self.assertEqual(sum(route.endswith('/restart') for route, _ in calls), 1)
        self.assertEqual(sum(route.endswith('/increment') for route, _ in calls), 4)
        self.assertNotIn('test-only', json.dumps(result))

    def test_restart_error_alone_is_never_success(self):
        count = 0
        writes = []

        def respond(base, route, token, method='GET'):
            nonlocal count
            if method == 'POST':
                writes.append(route)
            if route.endswith('/increment'):
                count += 1
            if route.endswith('/restart'):
                raise RuntimeError('transport ended without restart')
            return snapshot(count, count)

        result = self.run_state(respond)
        self.assertFalse(result['passed'])
        self.assertEqual(len(result['polls']), 10)
        self.assertEqual(sum(route.endswith('/increment') for route in writes), 3)
        self.assertEqual(sum(route.endswith('/restart') for route in writes), 1)

    def test_failed_increment_is_not_retried_and_stops_before_restart(self):
        writes = []

        def respond(base, route, token, method='GET'):
            writes.append(route)
            if route.endswith('/increment'):
                raise TimeoutError('ambiguous write outcome')
            return snapshot(0, 0)

        result = self.run_state(respond)
        self.assertFalse(result['passed'])
        self.assertEqual(sum(route.endswith('/increment') for route in writes), 1)
        self.assertFalse(any(route.endswith('/restart') for route in writes))

    def test_new_instance_on_different_object_is_not_success(self):
        current = snapshot(0, 0)

        def respond(base, route, token, method='GET'):
            nonlocal current
            if route.endswith('/increment'):
                current = {**current, 'memory_value': current['memory_value'] + 1,
                           'durable_value': current['durable_value'] + 1}
            if route.endswith('/restart'):
                current = snapshot(0, 3, 'after', 'WRONG-object')
                raise RuntimeError('restart ended')
            return current.copy()

        result = self.run_state(respond)
        self.assertFalse(result['passed'])
        self.assertNotIn('after_increment', result)


if __name__ == '__main__':
    unittest.main()
