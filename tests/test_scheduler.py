import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import limits
import scheduler as s


class SchedulerTests(unittest.TestCase):
    def test_target_is_server_reset_plus_one_minute(self):
        self.assertEqual(s.plan(1000, 900, None), 1060)
        self.assertEqual(s.plan(1000, 1100, None), 1100)
        self.assertIsNone(s.plan(1000, 1100, 1000))
        self.assertIsNone(s.plan(900, 1100, 1000))

    def test_restart_preserves_pending_check_and_recovers_interrupted_ping(self):
        state = {'phase': 'waiting_check', 'next_action_at': 1120}
        s.recover(state, 1050)
        self.assertEqual(state['next_action_at'], 1120)
        state = {'phase': 'ping_running'}
        s.recover(state, 1050)
        self.assertEqual(state['phase'], 'waiting_check')
        self.assertEqual(state['next_action_at'], 1170)
        state = {'phase': 'waiting_ping', 'next_ping_at': 1120}
        s.recover(state, 1050)
        self.assertEqual(state['phase'], 'querying')
        self.assertIsNone(state['next_ping_at'])

    def test_codex_five_hour_window_only(self):
        data = {'rateLimitsByLimitId': {'codex': {'primary': {
            'windowDurationMins': 300, 'resetsAt': 1000},
            'secondary': {'windowDurationMins': 10080, 'resetsAt': 9999}}}}
        self.assertEqual(limits.next_reset(data), 1000)
        with self.assertRaises(ValueError):
            limits.next_reset({'rateLimits': {'primary': {'windowDurationMins': 10080, 'resetsAt': 9999}}})

    def simulate(self, responses):
        clock = [900]
        pings, checks = [], []

        class FakeWakeup:
            manual = False
            stopping = False
            def wait(self, seconds):
                clock[0] += seconds
            def close(self):
                pass

        wakeup = FakeWakeup()
        pending = list(responses)

        def read(_):
            checks.append(clock[0])
            value = pending.pop(0)
            if not pending:
                wakeup.stopping = True
            if isinstance(value, Exception):
                raise value
            return value

        def ping():
            pings.append(clock[0])
            clock[0] += 2
            return True

        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / 'schedule.json'
            with patch.object(s, 'STATE', Path(tmp)), patch.object(s, 'STATE_FILE', state_file), \
                 patch.object(s, 'Wakeup', return_value=wakeup), patch.object(s, 'notify_ready'), \
                 patch.object(s.time, 'time', side_effect=lambda: clock[0]), \
                 patch.object(s.limits, 'read_limits', side_effect=read), \
                 patch.object(s.limits, 'next_reset', side_effect=lambda value: value), \
                 patch.object(s.run, 'ping', side_effect=ping), patch.object(s.run, 'log'), \
                 patch.object(s.display, 'ping'), patch.object(s.display, 'checked'), \
                 patch.object(s.display, 'append'):
                s.serve()
            return pings, checks, json.loads(state_file.read_text())

    def test_two_automatic_cycles_use_reset_time_and_delayed_check(self):
        pings, checks, state = self.simulate([1000, 4600, 8200])
        self.assertEqual(pings, [1060, 4660])
        self.assertEqual(checks, [900, 1182, 4782])
        self.assertEqual(state['next_ping_at'], 8260)
        self.assertEqual(state['last_consumed_reset'], 4600)

    def test_stale_reset_requeries_without_duplicate_ping(self):
        pings, checks, state = self.simulate([1000, 1000, 4600])
        self.assertEqual(pings, [1060])
        self.assertEqual(checks, [900, 1182, 1242])
        self.assertEqual(state['next_ping_at'], 4660)

    def test_query_failure_retries_without_sending_a_ping(self):
        pings, checks, state = self.simulate([TimeoutError('test'), 1000])
        self.assertEqual(pings, [])
        self.assertEqual(checks, [900, 960])
        self.assertEqual(state['next_ping_at'], 1060)


if __name__ == '__main__':
    unittest.main()
