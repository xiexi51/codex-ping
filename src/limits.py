"""Read the server reset time without starting a model turn."""
import json
from pathlib import Path
import queue
import subprocess
import threading
import time

from platform_support import CODEX, process_options, terminate_tree

ROOT = Path.home()
STATE = ROOT / '.local/state/codex-ping'
TIMEOUT_SECONDS = 15


def read_limits(environment):
    """One short-lived stdio connection, with a deadline covering both RPCs."""
    command = [str(CODEX),
               '--disable', 'apps', '--disable', 'plugins', '--disable', 'hooks',
               'app-server', '--listen', 'stdio://']
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, env=environment,
                               cwd=STATE / 'work', **process_options())
    messages = queue.Queue(maxsize=64)
    finished = threading.Event()
    deadline = time.monotonic() + TIMEOUT_SECONDS

    def enqueue(item):
        while not finished.is_set():
            try:
                messages.put(item, timeout=0.1)
                return
            except queue.Full:
                pass

    def reader():
        try:
            while not finished.is_set():
                line = process.stdout.readline(4 * 1024 * 1024 + 1)
                if not line:
                    enqueue(RuntimeError('rate-limit app-server closed before responding'))
                    return
                if len(line) > 4 * 1024 * 1024:
                    enqueue(RuntimeError('rate-limit response exceeds size bound'))
                    return
                if line.strip():
                    enqueue(json.loads(line))
        except Exception as error:
            enqueue(error)

    # Windows selectors cannot wait on anonymous subprocess pipes.
    thread = threading.Thread(target=reader, daemon=True)
    thread.start()

    def send(message):
        process.stdin.write((json.dumps(message) + '\n').encode())
        process.stdin.flush()

    def receive(request_id):
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('rate-limit query exceeded 15 seconds')
            try:
                message = messages.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError('rate-limit query exceeded 15 seconds') from None
            if isinstance(message, Exception):
                raise message
            if message.get('id') == request_id:
                if 'error' in message:
                    # Never record authentication payloads.
                    raise RuntimeError(f"rate-limit RPC error code={message['error'].get('code')}")
                return message['result']

    try:
        send({'id': 1, 'method': 'initialize', 'params': {
            'clientInfo': {'name': 'codex_ping_probe', 'version': '1.0'}}})
        receive(1)
        send({'method': 'initialized'})
        send({'id': 2, 'method': 'account/rateLimits/read', 'params': {}})
        return receive(2)
    finally:
        finished.set()
        terminate_tree(process)
        thread.join(timeout=2)
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
