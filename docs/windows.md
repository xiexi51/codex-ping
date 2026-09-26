# Windows 11 安装与管理

[返回 README](../README.md)

## 要求

- Windows 11、Windows PowerShell 5.1 或 PowerShell 7。
- Python 3.8+，安装目录含 `python.exe` 和 `pythonw.exe`，无需第三方 Python 包。
- 已通过 ChatGPT 账号登录的原生 Codex CLI。已在 Windows 11 上验证
  `0.155.0-alpha.16.3`；需要支持 `exec --ignore-user-config --ignore-rules`
  以及本项目用到的功能开关。
- 查询使用 [OpenAI Docs 的 app-server 接口](https://learn.chatgpt.com/docs/app-server)。
  账号必须返回 300 分钟配额窗口，否则每 60 秒重试查询，不会推测重置时间。

## 安装并立即执行

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Start
& "$HOME\.local\bin\codex-ping.cmd" run
```

Python 或 Codex 没有加入 PATH 时，指定实际路径，例如：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -PythonBin D:\anaconda3\python.exe `
  -CodexBin C:\工具\codex.exe -Start
```

安装器不下载 Python 或 Codex。npm 的 `.cmd` / `.ps1` 启动器不能直接作为
`-CodexBin`；请指定包内的原生 `codex.exe`。安装会固定复制 Codex 及同目录
`codex-*.exe` 辅助程序，避免编辑器扩展更新后旧路径失效。
再次安装保留配置、调度状态和登录目录，已有后台进程会在更新后恢复。

## 运行方式

使用 `pythonw.exe` 在后台运行，不弹出终端窗口，不需要管理员权限。
`start` 在当前用户的 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
下写入 `CodexPing`，用于登录后自启；`stop` 和 `uninstall` 删除该值。
不改动其他启动项或系统执行策略。

关闭终端、关闭编辑器或锁屏不会停止任务。重启后需登录安装时的用户；
注销、关机或睡眠期间不运行。睡眠恢复后会处理到期计划，重新启动进程时重新查询。
本版本不作为 Windows 系统服务运行，也没有进程崩溃后自动重启的监控服务。

调度仍为“服务端重置时间 + 60 秒 → ping → 等待 120 秒 → 查询”。
本地文件锁防止重复进程执行；`run` / `stop` 通过请求文件通知后台。
停止会等待当前调用结束或超时，然后保留状态退出。

## 管理命令

```powershell
& "$HOME\.local\bin\codex-ping.cmd" status     # 当前进程、登录自启和最近计划
& "$HOME\.local\bin\codex-ping.cmd" logs       # 实时日志；Ctrl-C 退出查看
& "$HOME\.local\bin\codex-ping.cmd" run        # 请求立即 ping，必要时启动后台
& "$HOME\.local\bin\codex-ping.cmd" stop       # 停止并关闭登录自启
& "$HOME\.local\bin\codex-ping.cmd" start      # 启动并开启登录自启
& "$HOME\.local\bin\codex-ping.cmd" restart    # 重启并开启登录自启
& "$HOME\.local\bin\codex-ping.cmd" uninstall  # 删除专属程序、配置、状态和日志
```

`run` 不改变登录自启设置，发送成功与否请查看日志。
ping 或之后两分钟检查等待期间的重复请求会合并或忽略。
`status` 的时间来自本地记录，不现场查询；停止时显示的计划不会执行。

## 配置与排查

| 位置（相对于用户目录） | 用途 |
| --- | --- |
| `.local\lib\codex-ping` | 程序和固定版本的 Codex |
| `.local\bin\codex-ping.cmd` | 命令入口 |
| `.config\codex-ping\settings.json` | 模型、prompt 和超时；下次 ping 生效 |
| `.config\codex-ping\runtime.json` | Python 路径及 Codex 登录目录 |
| `.local\state\codex-ping\summary.log` | UTF-8 简明日志 |
| `.local\state\codex-ping\run.log` | 详细调用日志 |
| `.local\state\codex-ping\scheduler-error.log` | 后台进程异常（发生时生成） |
| `.local\state\codex-ping\schedule.json` | 调度状态 |

首次安装沿用环境变量 `CODEX_HOME`，未设置时使用 `$HOME\.codex`。
安装与卸载不复制或删除账号凭据。运行时保留 Windows 必需的环境变量和代理变量。

```powershell
Get-Content "$HOME\.local\state\codex-ping\run.log" -Encoding UTF8 -Tail 30
```

## 开发验证

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
```

测试覆盖服务端时间调度、重复窗口、进程锁、Windows 控制请求、管道 RPC 分段读取、
超时和子进程清理。仓库的 GitHub Actions 配置同时测试 Windows 和 Linux。
