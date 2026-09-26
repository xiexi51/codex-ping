"""Small OS boundary shared by the Linux and Windows runners."""
import os
from pathlib import Path
import signal
import subprocess

WINDOWS = os.name == 'nt'
ROOT = Path.home()
LIB = ROOT / '.local/lib/codex-ping'
STATE = ROOT / '.local/state/codex-ping'
CONFIG = ROOT / '.config/codex-ping'
CODEX = LIB / ('codex.exe' if WINDOWS else 'codex')


def lock_file(handle):
    if WINDOWS:
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


def process_options():
    if WINDOWS:
        return {'creationflags': subprocess.CREATE_NO_WINDOW}
    return {'start_new_session': True}


def terminate_tree(process):
    if WINDOWS:
        if process.poll() is None:
            subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
            if process.poll() is None:
                process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=10)
