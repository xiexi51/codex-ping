# codex-ping

在 Linux 服务器上持久运行的轻量 Codex ping 任务，由 systemd 用户服务托管。

调度流程：**查询服务端下次重置时间 → 重置时间后 1 分钟 ping → ping 完成后等 2 分钟再查询 → 安排下一次**。

默认 prompt 为 `Reply OK.`，使用 `gpt-6-luna`、最低推理档、独立临时会话和空工作目录。
服务端查询使用 `account/rateLimits/read`，读取 codex 额度桶中 300 分钟窗口的重置时间，不创建模型对话。
调度依据服务端返回值；成功 ping 本身不保证会改变服务端重置周期。

## 安装

需要 Linux、systemd 用户服务、Python 3.8+、已安装并登录 ChatGPT 账号的 Codex CLI。
已验证 CLI 版本：`0.155.0-alpha.16.3`；其他版本需支持源码使用的 CLI 参数与 app-server 接口。
仓库不包含 Codex 二进制、账号凭据、运行日志或本机调度状态。

```bash
git clone git@github.com:xiexi51/codex-ping.git
cd codex-ping
./install.sh --codex-bin "$(command -v codex)" --start
```

若 Codex 没有加入 PATH，通过 `--codex-bin` 指定实际可执行文件路径。
默认只安装；`--start` 会开启当前用户的 linger、开机自启并启动服务。
如果系统不允许当前用户设置 linger，需要管理员执行 `loginctl enable-linger 用户名`。

安装到 `~/.local/lib/codex-ping`、`~/.config/codex-ping` 和 `~/.config/systemd/user`。
Codex 可执行文件优先使用硬链接固定版本，跨文件系统时复制；不会下载或上传二进制。
再次安装会保留已有配置、登录信息和调度状态；原本运行中的服务会在更新后恢复。

## 管理

```bash
~/.local/bin/codex-ping status     # 当前服务状态及保存的调度计划
~/.local/bin/codex-ping logs       # 实时查看中文简明日志
~/.local/bin/codex-ping start      # 启动并开启开机自启
~/.local/bin/codex-ping stop       # 停止并取消开机自启
~/.local/bin/codex-ping restart    # 重启并开启开机自启
~/.local/bin/codex-ping run        # 请求立即 ping，命令立即返回
~/.local/bin/codex-ping uninstall  # 删除服务、程序、配置和专属日志
```

`status` 只查看此服务。服务运行状态实时读取 systemd；重置时间和下次 ping 时间读取
本地 `schedule.json`，不会向服务端发起查询。“上次检查”表示这些数据的查询时刻。
服务停止时保存的计划不会执行。

`run` 会在服务停止时先启动循环（不改变开机自启设置）。
ping 或随后两分钟等待期间的重复手动请求会合并或忽略。

## 日志与配置

简明日志：`~/.local/state/codex-ping/summary.log`。

```text
本次 ping：日期 时间 时区（成功）
检查时间：日期 时间 时区
下次重置：日期 时间 时区
距重置还剩：X小时 X分钟 X秒
下次 ping：日期 时间 时区
```

本次 ping 在完成后记录，其他字段在两分钟后的查询完成时追加。
启动时也记录首次查询和计划。剩余时长按实际查询完成时刻计算。

| 文件 | 用途 |
| --- | --- |
| `~/.config/codex-ping/settings.json` | 模型、prompt、调用超时；下一次 ping 生效 |
| `~/.config/codex-ping/instructions.txt` | 此任务专用的精简模型指令 |
| `~/.local/state/codex-ping/schedule.json` | 当前计划与已处理窗口 |
| `~/.local/state/codex-ping/run.log` | 详细调用输出及执行状态 |
| `~/.config/systemd/user/codex-ping.service` | systemd 服务配置 |

## 持久化与异常处理

- 开启 linger 后，断开 SSH 或重启服务器不影响自动运行。
- 服务启动时通常重新查询；若正在等 ping 后的检查，则保留原检查时刻。
- 如果在 ping 期间异常退出，恢复后先等两分钟再查询，避免重复发送。
- 返回过去的重置时间时，尚未处理过的窗口立即补发一次。
- 查询失败、缺少五小时窗口或返回已处理过的重置时间时，每 60 秒重查，不额外 ping。
- ping 最多运行 120 秒，成功失败均在结束两分钟后检查。
- 进程异常退出后，systemd 等待 30 秒自动重启；日志不自动清理。

卸载不删除 `~/.codex` 登录信息、共享 systemd journal 或账号级 linger 设置。
卸载后如没有其他离线用户服务，可执行 `loginctl disable-linger "$(id -un)"`。

## 测试

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
bash -n install.sh bin/codex-ping
```

测试使用模拟时间与响应，不调用模型。覆盖动态调度、重启恢复、旧时间去重和查询失败重试。

接口参考：[Codex App Server](https://learn.chatgpt.com/docs/app-server)。

## 许可证

本项目采用 [MIT License](LICENSE)。
