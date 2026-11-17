# Issue #4 — Plan

Baseline status: Approved and published. Approval reference: user “yes” to the three-ticket breakdown.
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


## CR1 — Plan / Approved and published

Stage approval: user invoked to-tickets and requested “进入plan”. Source: approved CR1 Specify Q7–Q11, spec.md/interfaces.md and Accepted ADR 0003. The existing tickets #5–#7 above describe the delivered baseline; do not recreate or change their scope/state. The user approved the two-ticket breakdown and publication with “yes”. Publication completed on retry: CR1-T1 is #8 and CR1-T2 is #9. Earlier connection failures are retained in the attempt history below. Publishing does not authorize implementation.

### Decomposition and dependencies

Two end-to-end slices, each including configuration/CLI where relevant, runtime behavior, automated tests and user documentation. No prerequisite refactor is needed: extend the existing standalone collector and introduce only the approved private viewer helper. No separate schema, tests-only or documentation-only tickets.

| Local ID | Title | Blocked by | Demoable result | Trace |
| --- | --- | --- | --- | --- |
| CR1-T1 | 支持腿关节和轮关节独立方向符号的扫频采集 | None | Configure independent signs and save correctly signed desired trajectories with consistent initial states and unchanged measurement conventions | CR1-D1; CR1-A1/A2 |
| CR1-T2 | 支持隔离式实时查看器及完整关闭与故障处理 | None | Enable live observation, adjust camera, close window and finish collection; failures/cancellation preserve existing data and clean up the child | CR1-D2–D5; CR1-A2 CLI, A3–A5 |

These tickets are independent: T2 works with the existing all-positive trajectories; T1 requires no viewer. Their edits may overlap in config parsing and collection orchestration, which is a merge/integration concern rather than a functional blocking dependency. Suggested execution order T1 then T2 reduces overlapping edits but is not a tracker blocking edge. Final parent Verify covers the combined mixed-sign + viewer behavior and baseline regression.

### CR1-T1 draft issue

Parent: GitHub Issue #4. Label: ready-for-agent. Blocked by: None.

What to build: users can independently select the direction of each of twelve leg-position and four wheel-velocity sweep targets while continuing to collect the same five-field dataset. Whole leg trajectories, including their centers, are mirrored; physical measurement coordinates are unchanged.

Acceptance criteria:

- Independent position/velocity sign arrays accept only numeric +1/-1, reject booleans, nonfinite values and wrong lengths before stepping. Missing arrays default to all +1 for existing TOML and Python callers; unknown fields still fail.
- Default example config explicitly lists all-positive signs and preserves existing user settings. No inferred left/right values, amplitude rescaling, clipping or collision changes.
- Signed center and oscillation determine leg targets; signed oscillation determines wheel targets. Leg initial qpos/ctrl/native history match the signed centers; wheel initial angles/velocities/history remain zero.
- Measured positions/velocities retain native joint coordinates, existing encoder correction and XML noise. Desired fields store signed pre-delay commands; time, shapes, keys, dtypes and atomic-save behavior remain compatible.
- Meaningful tests cover mixed signs, signed initial state/history, invalid inputs, old-config/Python compatibility and same-seed all-positive equivalence. Tests must not simply duplicate the implementation formula without checking observable behavior.
- Usage documentation explains sign order/units, mirrored centers, unchanged sensor conventions and user-owned physical suitability. No Isaac Lab/fitting changes.

### CR1-T2 draft issue

Parent: GitHub Issue #4. Label: ready-for-agent. Blocked by: None.

What to build: users can opt into approximately real-time 3D observation during native collection without changing collected physics. Closing the window continues headlessly to completion; viewer failures or cancellation give explicit outcomes while preserving prior data.

Acceptance criteria:

- Optional visualize defaults false for existing config/Python callers. Mutually exclusive enable/disable CLI flags override the file value; omission preserves it. Plot remains independent. Disabled visualization initializes no viewer process/imports/display and adds no real-time waits.
- Separate viewer process/model/data receives copied complete native integration-state snapshots one way, including the initialized state. No GUI edits reach authoritative physics, sensor processing or RNG. Collect/save data signatures and five-field output remain compatible.
- Ready handshake precedes collection; startup limit 10 s. Live display publication is capped at 30 Hz with bounded latest-state pending data; subsequent snapshots are post-integration. Monotonic pacing is best effort. Late rendering skips frames/waits, never physics steps, measurements or random draws.
- Acknowledged normal window close stops display/pacing and completes N samples. Lifecycle notifications are handled before interpreting process exit to avoid falsely reporting normal closure as a crash. Unexpected startup/runtime failure aborts clearly without replacing prior data.
- Completion, error and Ctrl+C release resources and reap the child. Graceful wait 2 s, terminate wait 1 s, kill wait 1 s; cleanup failure is actionable and prevents saving. Ctrl+C retains exit 130. Final lifecycle/error checks and cleanup precede successful collection return.
- Tests cover disabled behavior, CLI precedence, same-seed data equivalence, display-copy mutation isolation, startup failure/timeout, unexpected exit, normal close, cancellation and cleanup escalation. Controlled clock/slow-display cases verify bounded publication and unchanged N/time grid; avoid long real sleeps in routine tests.
- Bounded real-viewer smoke evidence and manual camera/window-manager close results are recorded distinctly. Research probes alone do not satisfy production verification. Update usage/error documentation with observation/plot distinction, close policy, timeout limits and failure preservation.

### Integration and stage obligations

After implementation approval, execute each slice with its own tests and documentation. Parent Verify checks CR1-A1–A5 plus baseline A1–A8, combines nontrivial signs and visualization, and records exact commands/results. GUI-unavailable environments must report the unverified GUI checks rather than claim success. No full physical sweep or collision correction is included.

### Publication gate

User approved granularity, dependencies and publication (“yes”), satisfying to-tickets step 4. Publish two ready-for-agent GitHub issues under #4 and verify their native parent relationships; neither has blocking edges. Do not modify parent title/body/comments/state. Native sub-issue linkage is the association required by the invoked skill. Retain published IDs/URLs here. Do not enter Implement until explicitly approved.


### CR1 publication attempt — 2026-11-17

User authorization: “yes” to the two-ticket breakdown and creation as Issue #4 sub-issues. Authorization remains valid; no additional permission is required to resume publication.

Preflight issue list succeeded: latest existing issue was #7, with no matching CR1 titles. Label query confirmed ready-for-agent exists. Generated exact per-ticket issue bodies from the approved draft into /tmp/pace-cr1-ticket-1.md and /tmp/pace-cr1-ticket-2.md.

Attempted CR1-T1 creation with `gh issue create --repo MrCCaesar/pace-sim2real --title '支持腿关节和轮关节独立方向符号的扫频采集' --label ready-for-agent --body-file /tmp/pace-cr1-ticket-1.md`. It returned exit 1 with `Post https://api.github.com/graphql: EOF`, without an issue URL. Do not assume creation failed server-side.

Subsequent duplicate-check reads via GraphQL and REST all returned EOF, including an HTTP/1-only attempt. No proxy variables were configured. CR1-T1 existence cannot currently be confirmed; no blind create retry was made. CR1-T2 creation and native parent-link writes were not attempted. No parent issue body/state/comments were modified.

Resume: first list/search issues by exact CR1-T1 title and inspect its body/label; adopt any successfully created match. Create only missing approved tickets, attach both as native sub-issues of #4, verify labels/parents and absence of blockers, then record URLs here. Plan remains approved, publication incomplete. No implementation authorized.


### CR1 publication completed — 2026-11-17

User requested “继续尝试发布”. Read-only issue listing confirmed no CR1 duplicates. REST creation initially returned EOF; another successful read confirmed absence before retrying. The subsequent creates and native sub-issue links succeeded.

- CR1-T1: [支持腿关节和轮关节独立方向符号的扫频采集](https://github.com/MrCCaesar/pace-sim2real/issues/8). Parent #4; ready-for-agent; no blockers.
- CR1-T2: [支持隔离式实时查看器及完整关闭与故障处理](https://github.com/MrCCaesar/pace-sim2real/issues/9). Parent #4; ready-for-agent; no blockers.

Read-back verified exact body equality with approved ticket bodies, ready-for-agent labels, membership in #4's native sub-issue list and empty native blocked_by arrays for both tasks. Parent title/body/comments/state unchanged. This completion supersedes the earlier unresolved-publication status; no duplicate issues were created. Plan is complete. Next stage Implement requires explicit user approval; no production changes or runtime tests performed during publication.

CR1 implementation update: #8/#9 implemented against approved contracts; automated and bounded native smoke evidence is in verification.md under implementation checks. Code review and formal Verify status are tracked in status.md.

CR1 Implement complete: #8/#9 delivered in 2d1f78d with cleanup/review fixes in 3076912. Two-axis review has no remaining material findings. See verification.md implementation evidence; parent formal Verify remains separately gated. GitHub tasks remain open; no automatic tracker state changes.
