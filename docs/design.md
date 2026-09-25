# 工作原理与开发

[返回 README](../README.md)

## 调度流程

1. 查询服务端下次重置时间。
2. 在该时间后 1 分钟发送 ping。
3. ping 完成后等待 2 分钟，再次查询。
4. 按新的重置时间安排下一次，循环执行。

调度依据服务端返回值；成功 ping 本身不保证会改变服务端重置周期。

## 调用方式

模型请求通过 `codex exec` 发起，使用最低推理档、独立临时会话和空工作目录。
默认 prompt 为 `Reply OK.`。项目文档、用户配置以及额外的插件、hooks 等功能在调用时关闭，
以减少无关上下文。

重置时间通过 Codex app-server 的 `account/rateLimits/read` 读取，
选择 codex 额度桶中 300 分钟的窗口。这是只读查询，不创建模型对话。
接口参考：[Codex App Server](https://learn.chatgpt.com/docs/app-server)。

## 持久化与异常处理

- systemd 用户服务托管常驻进程；开启 linger 后，断开 SSH 或重启服务器仍可自动运行。
- 调度计划写入 `schedule.json`，通过临时文件和原子替换保存。
- 服务启动时通常重新查询；若正在等 ping 后的检查，则保留原检查时刻。
- 如果在 ping 期间异常退出，恢复后先等两分钟再查询，避免重复发送。
- 返回过去的重置时间时，尚未处理过的窗口立即补发一次。
- 查询失败、缺少五小时窗口或返回已处理过的重置时间时，每 60 秒重查，不额外 ping。
- 默认 ping 超时为 120 秒，成功失败均在结束两分钟后检查。
- 进程异常退出后，systemd 等待 30 秒自动重启。
- 文件锁避免运行多个调度实例；手动触发通过信号通知现有进程。

## 源码

| 文件 | 用途 |
| --- | --- |
| [scheduler.py](../src/scheduler.py) | 循环调度、状态持久化和信号处理 |
| [run.py](../src/run.py) | 轻量模型调用 |
| [limits.py](../src/limits.py) | 读取服务端重置时间 |
| [display.py](../src/display.py) | 简明日志 |
| [codex-ping](../bin/codex-ping) | 管理命令 |
| [服务配置](../systemd/codex-ping.service) | systemd 托管与自动恢复 |

## 测试

在仓库根目录运行：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
bash -n install.sh bin/codex-ping
```

测试使用模拟时间与响应，不调用模型。覆盖动态调度、重启恢复、旧时间去重和查询失败重试。
