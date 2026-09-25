"""Persistent reset -> +60s ping -> +120s query loop, owned by systemd."""
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import socket
import sys
import tempfile
import time

import display
import limits
import run

STATE = Path.home() / '.local/state/codex-ping'
STATE_FILE = STATE / 'schedule.json'
OFFSET_SECONDS = 60
CHECK_DELAY_SECONDS = 120
RETRY_SECONDS = 60


def save(state):
    fd, name = tempfile.mkstemp(prefix='schedule.', dir=STATE)
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(state, output, ensure_ascii=False, indent=2)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, STATE_FILE)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def load():
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text())


def plan(reset, now, last_consumed_reset):
    if last_consumed_reset is not None and reset <= last_consumed_reset:
        return None
    return max(reset + OFFSET_SECONDS, now)


def queried(state, reset, now):
    target = plan(reset, now, state.get('last_consumed_reset'))
    state.update(reset_at=reset, queried_at=now, next_ping_at=target,
                 phase='waiting_ping' if target is not None else 'retry_query',
                 next_action_at=target if target is not None else now + RETRY_SECONDS,
                 error=None)
    return target


def recover(state, now):
    if state.get('phase') == 'ping_running':
        state.update(phase='waiting_check', next_action_at=now + CHECK_DELAY_SECONDS,
                     next_ping_at=None)
    elif state.get('phase') != 'waiting_check':
        state.update(phase='querying', next_action_at=now, next_ping_at=None)


class Wakeup:
    def __init__(self):
        self.stopping = False
        self.manual = False
        self.read_fd, self.write_fd = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
        signal.set_wakeup_fd(self.write_fd)
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGUSR1, self.trigger)

    def stop(self, *_):
        self.stopping = True

    def trigger(self, *_):
        self.manual = True

    def wait(self, seconds):
        if select.select([self.read_fd], [], [], max(0, seconds))[0]:
            try:
                while os.read(self.read_fd, 4096):
                    pass
            except BlockingIOError:
                pass

    def close(self):
        signal.set_wakeup_fd(-1)
        os.close(self.read_fd)
        os.close(self.write_fd)


def notify_ready():
    address = os.environ.get('NOTIFY_SOCKET')
    if address:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.connect('\0' + address[1:] if address.startswith('@') else address)
            client.sendall(b'READY=1')


def serve():
    os.umask(0o077)
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'scheduler.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        wakeup = Wakeup()
        state = load()
        recover(state, time.time())
        save(state)
        notify_ready()
        run.log('SCHEDULER_START reset+60s -> ping -> wait120s -> query')
        try:
            while not wakeup.stopping:
                now = time.time()
                manual = wakeup.manual
                wakeup.manual = False
                if manual and state['phase'] == 'waiting_check':
                    run.log('MANUAL_SKIPPED waiting for the current post-ping check')
                    manual = False
                if not manual and now < state['next_action_at']:
                    wakeup.wait(min(60, state['next_action_at'] - now))
                    continue
                if manual or state['phase'] == 'waiting_ping':
                    at = time.time()
                    reset = state.get('reset_at')
                    if reset is not None and reset + OFFSET_SECONDS <= at:
                        state['last_consumed_reset'] = reset
                    state.update(phase='ping_running', last_ping_at=at, next_ping_at=None,
                                 next_action_at=at + CHECK_DELAY_SECONDS)
                    save(state)
                    success = run.ping()
                    completed = time.time()
                    state.update(phase='waiting_check', last_ping_success=success,
                                 last_ping_completed_at=completed,
                                 next_action_at=completed + CHECK_DELAY_SECONDS)
                    save(state)
                    display.ping(at, success)
                    wakeup.manual = False
                    continue
                try:
                    reset = limits.next_reset(limits.read_limits(run.environment()))
                    checked_at = time.time()
                    target = queried(state, reset, checked_at)
                    save(state)
                    display.checked(checked_at, reset, target)
                    run.log(f'SCHEDULE reset_at={reset} next_ping_at={target}')
                except Exception as error:
                    state.update(phase='retry_query', next_action_at=time.time() + RETRY_SECONDS,
                                 next_ping_at=None, error=str(error))
                    save(state)
                    run.log('QUERY_FAILURE ' + str(error))
                    display.append(f'检查时间：{display.date(time.time())}（查询失败）\n'
                                   '下次重置：未知\n距重置还剩：未知\n下次 ping：待查询成功；60秒后重查')
        finally:
            run.log('SCHEDULER_STOP schedule retained for restart')
            wakeup.close()


def status():
    state = load()
    print('调度方式：服务端重置时间 + 1分钟 → ping → 2分钟后查询')
    print('当前阶段：' + state.get('phase', '尚未启动'))
    for key, label in [('last_ping_at', '上次 ping'), ('queried_at', '上次检查'),
                       ('reset_at', '服务端重置时间'), ('next_ping_at', '下次 ping')]:
        if state.get(key) is not None:
            print(label + '：' + display.date(state[key]))
    if state.get('phase') in ('waiting_check', 'retry_query'):
        print('下次检查：' + display.date(state['next_action_at']))
    if state.get('error'):
        print('查询错误：' + state['error'])


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        status()
    else:
        serve()
