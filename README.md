# codex-ping

在 Linux 服务器上，按 Codex 的重置时间自动发送轻量 ping。断开 SSH、重启服务器后继续运行。

## 安装

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
