"""Read the server reset time without starting a model turn."""
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time

ROOT = Path.home()
STATE = ROOT / '.local/state/codex-ping'
TIMEOUT_SECONDS = 15


def read_limits(environment):
    """One short-lived stdio connection, with a deadline covering both RPCs."""
    command = [str(ROOT / '.local/lib/codex-ping/codex'),
               '--disable', 'apps', '--disable', 'plugins', '--disable', 'hooks',
               'app-server', '--listen', 'stdio://']
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, env=environment,
                               cwd=STATE / 'work', start_new_session=True)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    buffer = b''
    deadline = time.monotonic() + TIMEOUT_SECONDS

    def send(message):
        process.stdin.write((json.dumps(message) + '\n').encode())
        process.stdin.flush()

    def receive(request_id):
        nonlocal buffer
        while True:
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                if not line.strip():
                    continue
                message = json.loads(line)
                if message.get('id') == request_id:
                    if 'error' in message:
                        # Record only the error code, never authentication payloads.
                        raise RuntimeError(f"rate-limit RPC error code={message['error'].get('code')}")
                    return message['result']
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise TimeoutError('rate-limit query exceeded 15 seconds')
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError('rate-limit app-server closed before responding')
            buffer += chunk
            if len(buffer) > 4 * 1024 * 1024:
                raise RuntimeError('rate-limit response exceeds size bound')

    try:
        send({'id': 1, 'method': 'initialize', 'params': {
            'clientInfo': {'name': 'codex_ping_probe', 'version': '1.0'}}})
        receive(1)
        send({'method': 'initialized'})
        send({'id': 2, 'method': 'account/rateLimits/read', 'params': {}})
        return receive(2)
    finally:
        selector.close()
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=1)
        process.stdin.close()
        process.stdout.close()



def next_reset(result):
    buckets = result.get('rateLimitsByLimitId') or {}
    bucket = buckets.get('codex') or result.get('rateLimits') or {}
    if bucket.get('limitId') not in (None, 'codex'):
        raise ValueError('codex quota bucket is missing')
    for slot in ('primary', 'secondary'):
        window = bucket.get(slot) or {}
        reset = window.get('resetsAt')
        if window.get('windowDurationMins') == 300 and isinstance(reset, (int, float)) and not isinstance(reset, bool):
            return reset
    raise ValueError('server did not return a valid five-hour reset time')
