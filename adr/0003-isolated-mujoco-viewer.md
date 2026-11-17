# 原生 MuJoCo 采集的查看器隔离

Status: Accepted — user explicitly answered “8. yes” in CR1 Specify. User subsequently approved Q10/Q11 timing, state transfer and cleanup contracts.

## Context / problem

用户要求实时观察和相机操作，查看器不能改变采集物理过程；窗口关闭后继续采集，启动失败则明确退出并保留旧数据。MuJoCo 3.17.0 passive viewer 的 sync 会接收界面控制、扰动和物理选项，启动还可能在原生代码中失败。

## Alternatives

直接共享采集模型和状态最简单，但界面会影响物理。进程内独立模型可隔离状态，却难以隔离原生失败。自建只读渲染器可限制交互，但需要维护更多 UI。独立进程中的 passive viewer 增加生命周期和通信工作，同时隔离状态与原生失败。

## Decision and rationale

为查看器使用独立进程及独立模型/状态，由采集侧单向发布状态。采集侧独占物理推进、传感器处理和随机数生成。显示侧不返回物理修改；只返回生命周期状态。启动需要有界握手，结束需回收子进程。Q10/Q11 已确认：完整积分状态快照、30 Hz 显示发布上限、真实时间节奏，以及 10 秒启动和 2/1/1 秒退出等待上限。详细契约见 .scratch/issue_4/interfaces.md。

## Consequences / trade-offs

需要额外模型内存及进程管理，并测试关闭、故障、取消和资源清理。保留原生相机功能；原生 UI 即使修改显示副本也不能修改权威采集状态。独立进程并不自动保证视觉保真或实时性能，仍需明确快照与刷新策略。

## Evidence

.scratch/issue_4/research.md 的 CR1 源码调查和 E1/E2；E1 五个数组与基线完全一致，E2 无效显示导致子进程退出 1 且父进程可回收。超时路径及手动 GUI 操作尚未验证。

## Approval reference

用户在 Specify 明确答复“7. yes 8. yes 9. yes”，其中 Q8 批准独立查看器进程和单向状态传递架构。原 ADR 0001/0002 继续有效；本提案只扩展可选查看器的隔离边界。

Q10/Q11 批准引用：用户答复“10. yes 11. yes”。本 ADR 不代表实现已经完成，也不授权自动进入 Plan。
