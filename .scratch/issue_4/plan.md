# Issue #4 — Plan

Status: Approved and published. Approval reference: user “yes” to the three-ticket breakdown.
Stage approval: user invoked to-tickets and said “进入plan阶段，依据文档内容拆分任务”; spec.md and interfaces.md are the planning baseline.

## Scope and decomposition

Three vertical slices; no standalone schema/config/test/documentation layer tickets. No prefactor is required: the approved standalone helper avoids changing the existing package initialization. Each slice includes its own behavior tests and matching usage/error documentation.

| Ticket | End-to-end result | Blocked by | Acceptance trace |
| --- | --- | --- | --- |
| T1 | Configure and run native X5 mixed sweep; save correctly timed, biased/noisy five-field dataset | None | A1–A5, A6 successful save, A7, A8 |
| T2 | Reject unsupported/invalid collection attempts and preserve prior data through failure/interruption | T1 | A1,A2 negative cases; A6 failure paths; A7 numerical failures; A8 |
| T3 | Opt-in plotting of leg positions and wheel velocities after successful saving | T1 | A6 plotting; A8 |

T2 and T3 can start independently after T1; neither blocks the other. T1 must implement the intended native dynamics and atomic writer, not temporary approximations. T2 completes systematic negative-path validation and fault-injection coverage, not an excuse to write unsafe T1 behavior.

## Tests/documentation obligations

- T1: native minimal-model delay/history/timing and effort saturation; config/CLI and chirp assertions; sensor bias/noise repeatability and scaling; serialization round-trip; short headless X5 run. Documentation describes defaults, units, order, initial state and fitting incompatibility.
- T2: invalid config/channel/transmission/sensor timing errors; nonfinite dynamics/automatic reset; failed serialization/replacement and interruption; verify previous bytes unchanged and temporary cleanup. Document errors and replacement policy.
- T3: two figure groups, axes/labels/series match collected data; disabled plotting does not import matplotlib; saving precedes plotting. Use noninteractive backend for automated tests; do not require a GUI for routine checks. Document --plot.
- Parent Verify stage: consolidate evidence against A1–A8 once all tickets complete. No separate tests-only ticket. Respect explicit stage approval; publishing tickets does not authorize Implement.

## Physical boundary

No collision exclusion, geometry correction, trajectory clipping, Isaac Lab fitting changes, or physics certification. Contacts/poor tracking are user-owned evaluation matters; nonfinite states and invalid run contracts remain software errors.

## Published tickets

- T1: [完成 X5 原生 MuJoCo 混合扫频采集与数据保存](https://github.com/MrCCaesar/pace-sim2real/issues/5); parent #4; ready-for-agent; blocked by none.
- T2: [无效配置与采集失败时明确报错并保留已有数据](https://github.com/MrCCaesar/pace-sim2real/issues/6); parent #4; ready-for-agent; blocked by #5.
- T3: [可选绘制腿关节位置和轮关节速度响应](https://github.com/MrCCaesar/pace-sim2real/issues/7); parent #4; ready-for-agent; blocked by #5.

Parent/sub-issue links, native blocking relationships and labels were read back and verified. All three tasks were implemented in 87da096 and software-verified; see verification.md. GitHub Issue states were not changed.
