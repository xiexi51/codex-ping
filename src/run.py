"""One bounded minimal Codex call, used by the reset-driven scheduler."""
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess

ROOT = Path.home()
STATE = ROOT / '.local/state/codex-ping'
CONFIG = ROOT / '.config/codex-ping'


def environment():
    return {'HOME': str(ROOT), 'USER': ROOT.name, 'LOGNAME': ROOT.name,
            'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8',
            'CODEX_HOME': str(ROOT / '.codex')}


def log(message):
    stamp = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
    line = f'{stamp} {message}'
    with (STATE / 'run.log').open('a') as output:
        output.write(line + '\n')
    print(line, flush=True)


def ping():
    process = None
    try:
        settings = json.loads((CONFIG / 'settings.json').read_text())
        command = [str(ROOT / '.local/lib/codex-ping/codex'), 'exec',
                   '--ignore-user-config', '--ignore-rules', '--ephemeral',
                   '--skip-git-repo-check', '--sandbox', 'read-only',
                   '--color', 'never', '--json', '--cd', str(STATE / 'work'),
                   '--model', settings['model'],
                   '-c', 'approval_policy="never"',
                   '-c', 'model_reasoning_effort="low"',
                   '-c', 'model_verbosity="low"',
                   '-c', 'project_doc_max_bytes=0',
                   '-c', 'web_search="disabled"',
                   '-c', 'include_apps_instructions=false',
                   '-c', 'include_collaboration_mode_instructions=false',
                   '-c', 'suppress_unstable_features_warning=true',
                   '-c', 'model_instructions_file=' + json.dumps(str(CONFIG / 'instructions.txt'))]
        for feature in ['apps', 'plugins', 'hooks', 'shell_tool', 'shell_snapshot',
                        'multi_agent', 'skill_search', 'browser_use', 'computer_use',
                        'image_generation', 'memories', 'unbounded_connection_retries',
                        'view_image', 'sleep_tool', 'goals']:
            command.extend(['--disable', feature])
        command.extend(['--enable', 'skip_host_skill_discovery', settings['prompt']])
        log('PING_START model=' + settings['model'] + ' prompt=' + json.dumps(settings['prompt']))
        process = subprocess.Popen(command, env=environment(), stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, start_new_session=True)
        output, _ = process.communicate(timeout=settings['timeout_seconds'])
        completed = False
        for line in output.splitlines():
            log('CODEX ' + line)
            if line.startswith('{'):
                try:
                    completed |= json.loads(line).get('type') == 'turn.completed'
                except ValueError:
                    pass
        success = process.returncode == 0 and completed
        log(f'PING_{"SUCCESS" if success else "FAILURE"} exit={process.returncode}')
        return success
    except Exception as error:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
        log('PING_FAILURE ' + str(error))
        return False
