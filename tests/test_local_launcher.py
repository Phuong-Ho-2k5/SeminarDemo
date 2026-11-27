import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from run_local_demo import connect_or_start, stop_worker


class LauncherTests(unittest.TestCase):
    def server(self, application):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                body = json.dumps({'application': application, 'status': 'ok'} if self.path == '/api/health'
                                  else {'memory_value': 0, 'durable_value': 4, 'instance_id': 'existing',
                                        'object_id': 'same-object', 'counter_name': 'seminar-demo-2'}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server, requests

    def test_other_application_is_refused_and_left_running(self):
        server, requests = self.server('some-other-app')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, 'another application'):
                connect_or_start(server.server_port, 'test-token', Path(folder) / 'worker.log')
        self.assertEqual(requests, ['/api/health'])
        self.assertTrue(server.fileno() >= 0)

    def test_existing_seminar_worker_is_reused_with_read_only_checks(self):
        server, requests = self.server('neon-workers-seminar')
        with tempfile.TemporaryDirectory() as folder:
            process = connect_or_start(server.server_port, 'test-token', Path(folder) / 'worker.log')
        self.assertIsNone(process, 'A reused worker must not become an owned process to kill')
        self.assertEqual(requests, ['/api/health', '/api/state'])

    def test_cleanup_terminates_an_owned_process(self):
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        stop_worker(process)
        self.assertIsNotNone(process.poll())


if __name__ == '__main__':
    unittest.main()
