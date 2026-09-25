# 安装与配置

[返回 README](../README.md)

## 安装要求

- Linux、systemd 用户服务、Python 3.8+。
- 已安装 Codex CLI，并通过 ChatGPT 账号登录。
- 当前已验证 CLI 版本为 `0.155.0-alpha.16.3`，来自 VS Code 插件内置的原生可执行文件。
  其他版本需要支持本项目使用的 CLI 参数与 app-server 接口。

当前安装器按原生可执行文件处理 `codex`。npm 安装的 `codex` 可能是 JavaScript 启动器，
依赖原有包目录，不能直接搬到任务目录；这种安装方式尚未适配。
请通过 `--codex-bin` 指定可用的原生 Codex 可执行文件。

仓库不包含 Codex 二进制、账号凭据、运行日志或本机调度状态。

## 安装选项

Codex 已在 PATH 中时：

```bash
./install.sh --start
```

否则指定路径：

```bash
./install.sh --codex-bin /实际路径/codex --start
```

省略 `--start` 只安装文件；如果已有服务正在运行，会在更新后恢复运行。
`--start` 会开启当前用户的 linger、开机自启并启动服务。

如果系统不允许当前用户设置 linger，需要管理员执行：

```bash
loginctl enable-linger 用户名
```

安装器需要能连接 `systemctl --user`。应在目标用户的正常登录会话中安装，
安装目录为该用户的 `~/.local/lib/codex-ping`、`~/.config/codex-ping` 和 `~/.config/systemd/user`。

## 更新

```bash
git pull --ff-only
./install.sh --codex-bin /实际路径/codex --start
```

再次安装会保留已有配置、登录信息和调度状态。
Codex 可执行文件优先使用硬链接固定版本，跨文件系统时复制；安装器不会下载二进制。

## 修改模型和 prompt

编辑 `~/.config/codex-ping/settings.json`：

```json
{
  "model": "gpt-6-luna",
  "prompt": "Reply OK.",
  "timeout_seconds": 120
}
```

更改在下一次 ping 生效，无需重启。使用当前账号和 CLI 支持的模型。

## 命令行为

- `status` 只查看此服务。运行状态实时读取 systemd；重置时间和下次 ping 时间来自本地记录，
  不向服务端查询。“上次检查”表示数据的查询时刻。服务停止时保存的计划不会执行。
- `run` 请求立即 ping，命令立即返回。如果服务停止，会先启动循环，不改变开机自启设置。
  ping 或随后两分钟等待期间的重复手动请求会合并或忽略。
- `restart` 重启服务，并开启开机自启。
- `logs` 持续显示新日志。按 Ctrl-C 只退出查看，不停止任务。

## 文件与日志

| 文件 | 用途 |
| --- | --- |
| `~/.config/codex-ping/settings.json` | 模型、prompt、调用超时 |
| `~/.config/codex-ping/instructions.txt` | 此任务专用的精简模型指令 |
| `~/.local/state/codex-ping/summary.log` | 供人查看的简明日志 |
| `~/.local/state/codex-ping/run.log` | 详细调用输出及执行状态 |
| `~/.local/state/codex-ping/schedule.json` | 当前计划与已处理窗口 |
| `~/.config/systemd/user/codex-ping.service` | systemd 服务配置 |

本次 ping 在完成后记录，其余字段在两分钟后的查询完成时追加。
启动时也记录首次查询和计划。剩余时长按实际查询完成时刻计算，日志不自动清理。

排查启动或运行错误：

```bash
tail -n 50 ~/.local/state/codex-ping/run.log
journalctl --user -u codex-ping.service -n 50
```

## 卸载

```bash
~/.local/bin/codex-ping uninstall
```

会删除服务、程序、配置和专属日志；保留 `~/.codex` 登录信息、共享 systemd journal 和账号级 linger 设置。
如果没有其他需要离线运行的用户服务，可再执行：

```bash
loginctl disable-linger "$(id -un)"
```
