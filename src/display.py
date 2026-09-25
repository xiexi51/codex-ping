"""Chinese log containing the ping, reset and next scheduled ping times."""
import datetime
from pathlib import Path

STATE = Path.home() / '.local/state/codex-ping'


def date(epoch):
    return datetime.datetime.fromtimestamp(epoch).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z (%z)')


def duration(seconds):
    seconds = int(seconds)
    prefix = '已过期 ' if seconds < 0 else ''
    hours, remainder = divmod(abs(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{prefix}{hours}小时 {minutes}分钟 {seconds}秒'


def append(text):
    with (STATE / 'summary.log').open('a') as output:
        output.write(text + '\n')


def ping(at, success):
    append(f'\n本次 ping：{date(at)}（{"成功" if success else "失败"}）')


def checked(at, reset, next_ping):
    append(f'检查时间：{date(at)}\n下次重置：{date(reset)}\n'
           f'距重置还剩：{duration(reset - at)}\n'
           f'下次 ping：{date(next_ping) if next_ping is not None else "等待服务端更新重置时间；60秒后重查"}')
