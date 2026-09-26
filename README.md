# codex-ping

在 Linux 或 Windows 11 上，按 Codex 的重置时间自动发送轻量 ping。
Linux 使用 systemd；Windows 在后台运行，并支持当前用户登录后自动启动。

## 工作原理

1. 查询服务端下次重置时间。
2. 在该时间后 1 分钟发送 ping。
3. ping 完成后等待 2 分钟，再次查询。
4. 按新的重置时间安排下一次，循环执行。

## 安装

### Windows 11

需要 Python 3.8+（含 `pythonw.exe`）和已登录的原生 `codex.exe`。在 PowerShell 中执行：

```powershell
git clone https://github.com/xiexi51/codex-ping.git
cd codex-ping
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Start
& "$HOME\.local\bin\codex-ping.cmd" run
```

找不到 Python 或 Codex 时，安装参数可指定 `-PythonBin C:\路径\python.exe`
和 `-CodexBin C:\路径\codex.exe`。详细说明见 [Windows 11 安装与管理](docs/windows.md)。

```powershell
& "$HOME\.local\bin\codex-ping.cmd" status
& "$HOME\.local\bin\codex-ping.cmd" logs
& "$HOME\.local\bin\codex-ping.cmd" stop
& "$HOME\.local\bin\codex-ping.cmd" start
& "$HOME\.local\bin\codex-ping.cmd" restart
& "$HOME\.local\bin\codex-ping.cmd" uninstall
```

Windows 关闭终端或锁屏后继续运行；重启后需要登录当前用户才会启动。
注销、关机或睡眠期间不会发送 ping。

### Linux

需要 Linux、systemd 用户服务、Python 3.8+，以及已登录的 Codex CLI。
安装前请确认 [CLI 兼容性](https://github.com/xiexi51/codex-ping/blob/main/docs/usage.md#安装要求)。

```bash
git clone https://github.com/xiexi51/codex-ping.git
cd codex-ping
./install.sh --start
```

安装后会自动启动并开启开机自启。找不到 Codex 或遇到权限问题，见 [安装说明](https://github.com/xiexi51/codex-ping/blob/main/docs/usage.md)。

## 常用命令

```bash
~/.local/bin/codex-ping status     # 查看状态和下次 ping 时间
~/.local/bin/codex-ping logs       # 实时查看日志，Ctrl-C 退出查看
~/.local/bin/codex-ping run        # 立即 ping 一次
~/.local/bin/codex-ping stop       # 停止并关闭开机自启
~/.local/bin/codex-ping start      # 启动并开启开机自启
~/.local/bin/codex-ping restart    # 重启
~/.local/bin/codex-ping uninstall  # 删除任务、配置和日志
```

`status` 显示上次查询到的重置时间，不会现场查询。`run` 在任务停止时也会启动后台循环。

## 日志

运行 `~/.local/bin/codex-ping logs` 即可看到：

```text
本次 ping：日期 时间 时区（成功）
检查时间：日期 时间 时区
下次重置：日期 时间 时区
距重置还剩：X小时 X分钟 X秒
下次 ping：日期 时间 时区
```

重置信息在每次 ping 完成两分钟后更新。日志保存在 `~/.local/state/codex-ping/summary.log`。

[安装与配置](https://github.com/xiexi51/codex-ping/blob/main/docs/usage.md) · [工作原理与开发](https://github.com/xiexi51/codex-ping/blob/main/docs/design.md) · [MIT License](https://github.com/xiexi51/codex-ping/blob/main/LICENSE)
