import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import limits
import platform_support as platform
import scheduler
import run


class PipeTests(unittest.TestCase):
    def query(self, program, timeout=2):
        popen = subprocess.Popen
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'fake_server.py'
            script.write_text(program, encoding='utf-8')
            children = []

            def launch(command, **kwargs):
                if command[0] != str(limits.CODEX):
                    return popen(command, **kwargs)
                kwargs['cwd'] = directory
                child = popen([sys.executable, '-u', str(script)], **kwargs)
                children.append(child)
                return child

            with patch.object(limits.subprocess, 'Popen', side_effect=launch), \
                 patch.object(limits, 'TIMEOUT_SECONDS', timeout):
                try:
                    return limits.read_limits(os.environ.copy())
                finally:
                    self.assertTrue(children)
                    self.assertIsNotNone(children[0].poll(), 'RPC child must be reaped')

    def test_partial_lines_and_notifications_during_both_rpcs(self):
        result = self.query('''import sys, json, time
for line in sys.stdin:
    request = json.loads(line)
    if 'id' not in request:
        continue
    print(json.dumps({'method': 'notification'}), flush=True)
    response = json.dumps({'id': request['id'], 'result': {'ok': True}})
    sys.stdout.write(response[:8]); sys.stdout.flush()
    time.sleep(0.01)
    print(response[8:], flush=True)
''')
        self.assertEqual(result, {'ok': True})

    def test_hung_server_has_a_deadline(self):
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            self.query('import time; time.sleep(60)', timeout=0.2)
        self.assertLess(time.monotonic() - started, 10)

    def test_eof_is_reported(self):
        with self.assertRaisesRegex(RuntimeError, 'closed before responding'):
            self.query('pass')

    def test_rpc_errors_do_not_expose_payload(self):
        with self.assertRaisesRegex(RuntimeError, '^rate-limit RPC error code=401$'):
            self.query('''import sys, json
request = json.loads(sys.stdin.readline())
print(json.dumps({'id': request['id'], 'error': {'code': 401, 'message': 'secret'}}), flush=True)
''')


class PlatformTests(unittest.TestCase):
    def test_lock_rejects_second_process_and_releases_on_close(self):
        source = str(Path(platform.__file__).parent)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'lock'
            command = [sys.executable, '-c',
                       'import sys; sys.path.insert(0, sys.argv[1]); '
                       'from platform_support import lock_file; '
                       'f=open(sys.argv[2], "a"); lock_file(f)', source, str(path)]
            with path.open('a') as handle:
                platform.lock_file(handle)
                self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)

    @unittest.skipUnless(platform.WINDOWS, 'Windows file wakeups')
    def test_windows_manual_request_is_consumed_once_and_stop_is_detected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(scheduler, 'STATE', Path(directory)):
            wakeup = scheduler.Wakeup()
            (Path(directory) / 'run.request').touch()
            wakeup.wait(0)
            self.assertTrue(wakeup.manual)
            self.assertFalse((Path(directory) / 'run.request').exists())
            wakeup.manual = False
            wakeup.wait(0)
            self.assertFalse(wakeup.manual)
            (Path(directory) / 'stop.request').touch()
            wakeup.wait(0)
            self.assertTrue(wakeup.stopping)
            wakeup.close()

    def test_logging_with_no_console(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(run, 'STATE', Path(directory)), \
             patch.object(run.sys, 'stdout', None):
            run.log('测试')
            self.assertIn('测试', (Path(directory) / 'run.log').read_text(encoding='utf-8'))

    @unittest.skipUnless(platform.WINDOWS, 'Windows sharing violations')
    def test_open_request_is_retried_after_writer_closes(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(scheduler, 'STATE', Path(directory)):
            wakeup = scheduler.Wakeup()
            request = Path(directory) / 'run.request'
            with request.open('w'):
                wakeup.wait(0)
                self.assertFalse(wakeup.manual)
                self.assertTrue(request.exists())
            wakeup.wait(0)
            self.assertTrue(wakeup.manual)
            self.assertFalse(request.exists())
            wakeup.close()

    @unittest.skipUnless(platform.WINDOWS, 'Windows manager')
    def test_manager_handles_missing_empty_invalid_and_valid_pid(self):
        script = Path(__file__).with_name('test_windows_manager.ps1')
        result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy',
                                 'Bypass', '-File', str(script)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
