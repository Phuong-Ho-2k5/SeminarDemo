import contextlib
import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from terminal_report import print_async_report, print_state_report


class TerminalReportTests(unittest.TestCase):
    def capture(self, reporter, result):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            reporter(result)
        return output.getvalue()

    def test_async_prints_observed_medians_counts_and_verdict(self):
        result = {'passed': True, 'trials_per_route': 5, 'median_speedup': 2.5,
                  'parallel_faster_observed': True,
                  'routes': {'/api/async/seq': {'median_ms': 2500.125, 'valid_samples': 5},
                             '/api/async/parallel': {'median_ms': 1000.05, 'valid_samples': 4}}}
        text = self.capture(print_async_report, result)
        for expected in ('KẾT QUẢ DEMO 1', '2500.125', '1000.050', '5/5', '4/5', '2.50', 'PASS'):
            self.assertIn(expected, text)

    def test_async_without_valid_samples_does_not_invent_a_median(self):
        result = {'passed': False, 'trials_per_route': 5, 'median_speedup': None,
                  'parallel_faster_observed': None,
                  'routes': {'/api/async/seq': {'median_ms': None, 'valid_samples': 0},
                             '/api/async/parallel': {'median_ms': None, 'valid_samples': 0}}}
        text = self.capture(print_async_report, result)
        self.assertIn('0/5', text)
        self.assertIn('FAIL', text)
        self.assertNotIn('3000', text)
        self.assertNotIn('1000', text)

    def test_state_prints_actual_wrong_value_and_failure_instead_of_expected_values(self):
        result = {'passed': False, 'after_reset': {'memory_value': 0, 'durable_value': 0},
                  'before_restart': {'memory_value': 3, 'durable_value': 3,
                                     'instance_id': 'old', 'object_id': 'same'},
                  'after_restart': {'memory_value': 0, 'durable_value': 987,
                                    'instance_id': 'new', 'object_id': 'same'},
                  'checks': {'new_instance': True, 'same_object_id': True},
                  'error': 'Wrong durable value'}
        text = self.capture(print_state_report, result)
        for expected in ('KẾT QUẢ DEMO 2', '987', 'old', 'new', 'same', 'FAIL', 'Wrong durable value'):
            self.assertIn(expected, text)


if __name__ == '__main__':
    unittest.main()
