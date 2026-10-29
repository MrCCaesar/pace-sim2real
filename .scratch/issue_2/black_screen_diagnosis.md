# 黑屏只读诊断

状态：Draft，2026-10-29；用户已授权查看系统、OOM、驱动日志，未授权重跑仿真。

## 时间确认后的补充结论

用户确认黑屏发生于今天 08:51–08:57 唤醒后。继续只读检查得出：

- 08:51:04 logind 明确记录 Lid opened；08:51:05 挂起操作结束，nvidia-resume.service 正常退出。服务成功不等于显示恢复完全正常。
- 08:57:29 内核记录 `traps: dbus-daemon[1068] general protection fault ... in libc.so.6`；systemd 同时记录系统 D-Bus 的 SIGSEGV。这是实际进程故障，不只是一般警告。故障指令位于 libc 并不能单独证明 libc 是根因。
- 同秒 GNOME X 连接断开、显示会话注销；Chrome 明确记录 D-Bus 连接断开后主动 abort。08:57:32 GDM 安排重启，08:57:55 login1/UPower 激活超时，GDM 无法完成相应 D-Bus 调用。
- 系统 D-Bus 崩溃与桌面会话失效的关联证据较强；但黑屏是否从 08:51 就开始、i915/电源恢复异常是否导致后续 D-Bus 故障，仍无法确定。08:55 的 Chrome 段错误亦不能直接归因于同一原因。
- `coredumpctl` 未安装；`/var/crash` 目录仅见 Chrome 报告，未见 D-Bus 报告。没有读取 Chrome 报告中的内存内容，未安装调试工具。因此没有 D-Bus 堆栈可继续定位其内部崩溃原因。

当前最稳妥的判断：故障发生于唤醒后的系统/桌面会话层，已有明确 D-Bus 崩溃证据；没有证据将其认定为仿真时内存/显存耗尽，也不能完全排除此前 GPU 使用与恢复问题有关。保持仿真实验停止。后续如修复系统，需独立评估系统/显示恢复与 D-Bus 问题，不依据本日志直接升级驱动、重启服务或修改内核参数。

追加查询：`journalctl -b -1 -u dbus.service -u systemd-logind.service -u gdm.service --since '2026-10-29 08:50:00' --until '2026-10-29 08:58:00' --no-pager -o short-iso`；挂起/恢复三个 systemd unit 日志；08:56:50–08:57:31 全日志关键词筛选；`coredumpctl list`（命令不存在）及 `ls -lh /var/crash`（成功）。没有执行 GPU 或仿真调用。

## 已确认事实

所有时间为 Asia/Shanghai。上一启动 ID 为 `1ad1d27ddcb54ce9b72d5b84365ad6f6`，日志覆盖 10-28 14:08 至 10-29 08:57:55；当前启动时间约 10-29 08:59:52。

| 时间 | 证据 |
| --- | --- |
| 10-28 17:42:49 | robot_smoke.log 最后修改；内容为 ModelBuilder.add_usd 不接受 allow_unsafe_torch_checkpoints，实验未进入动力学循环 |
| 10-28 17:44–17:47 | 内核记录 acpi_os_execute_deferred workqueue CPU 占用警告；没有足够信息归因到测试 |
| 10-28 18:09:27 | PM: suspend entry (s2idle) |
| 10-29 08:51:04 | i915 runtime PM cleanup 警告，调用栈包含 i915_drm_suspend_late；NVIDIA ACPI D-Notifier / power source change 处理失败；PM: suspend exit |
| 10-29 08:55:17 | Chrome segfault |
| 10-29 08:57:29 | 系统 dbus.service 主进程退出，code=killed, status=11/SEGV；同秒 GNOME X connection broken |
| 10-29 08:57:31–33 | GDM 停止并重启，图形会话关闭 |
| 10-29 08:59:52 左右 | 新一轮系统启动；无法仅据此判断用户主动还是故障触发重启 |

上一启动内核日志定向检索未匹配 `NVRM: Xid`、`Out of memory:`、`Killed process`、`oom-kill:`、`GPU has fallen`、`GPU HANG`、`Kernel panic`。systemd-oomd 日志仅显示服务启动。日志中的 OOM killer disabled/enabled 与挂起恢复相邻，不是 OOM 杀进程证据。不能用日志缺失证明从未发生资源耗尽或驱动故障。

当前启动也有 i915/显示及 NVIDIA 固件交互警告；不能把重启后的警告直接作为此前黑屏根因。当前 free -h 显示约 30 GiB RAM、25 GiB available、swap 未使用，仅为重启后的状态，不能推断黑屏时峰值。

## 推断、未知与下一步

08:57 的系统 D-Bus SIGSEGV 与图形会话断开是具体故障线索；08:51 的挂起恢复也有显示/电源管理异常。尚不能确定其因果链，更不能证明与昨天的机器人测试存在或不存在因果关系。

待用户确认黑屏时间与是否在唤醒/接拔显示设备后发生。若对应 08:57，应优先只读检查 D-Bus 崩溃元数据及该时段上下文；若是昨天测试期间，应按实际时间重新定位。保持仿真/GPU 测试停止，不修改驱动、服务或依赖。

## 已执行查询

- `date --iso-8601=seconds`、`uptime -s`、`journalctl --list-boots --no-pager`。
- `journalctl -b -1 -k --since '2026-10-28 17:00:00' --no-pager -o short-iso`，筛选 GPU、OOM、挂起恢复关键词。
- `journalctl -b -1 -k --no-pager -o short-iso`，定向检索上述 Xid/OOM/panic 表达式，无匹配。
- `journalctl -b -1 --since '2026-10-29 08:54:00' --until '2026-10-29 08:58:00' --no-pager -o short-iso`，筛选服务退出、段错误和图形会话关闭。
- `journalctl -b -1 --since '2026-10-28 17:35:00' --until '2026-10-28 17:50:00' --no-pager -o short-iso -p warning` 以及该时间窗内核记录。
- `journalctl -b -1 -u systemd-oomd --no-pager -o short-iso`；`stat` / `tail` 查看实验日志；`free -h`。

未启动仿真、未调用 CUDA/NVML/nvidia-smi、未读取 core 内存内容、未改系统配置。
