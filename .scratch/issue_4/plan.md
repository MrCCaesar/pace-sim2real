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

## CR2 — Plan / Approved and published

Stage authorization: user invoked `mattpocock-skills:to-tickets` and said “进入plan”. Source of truth: final Approved CR2 specification/interfaces, Q11–Q23 and ADR0004–0010. Code comparison checkpoint: ecefbfe (WIP;67 passed/3 failed and undefined trajectory). Earlier published #5–#9 are historical delivery tickets; do not reopen their scope, duplicate them or change their state.

### Vertical slices and genuine dependencies

| ID | Title | Blocked by | Independently verifiable outcome | Trace |
| --- | --- | --- | --- | --- |
| CR2-T1 | 统一原生 MuJoCo 扫频中心与反馈编码器偏置 | None | Run native collection with normalized centers and unified biased feedback; save unchanged five-field payload with correct pre-delay targets and consistent startup | ADR0004/0005; Q11,Q14; native regressions |
| CR2-T2 | 完成 Isaac Lab 腿位置与轮速度混合采集 | None | Run pure-leg or mixed collection through validated name/action mapping and save correctly aligned actual/desired groups | R1,R3,R6,R9; Q18,Q23 |
| CR2-T3 | 支持混合关节辨识并保存成对最佳结果 | CR2-T2 | Validate reference data, run mixed/pure-leg fitting on either backend, and persist the evaluated global-best parameters with matching responses and errors | R1–R10; Q12,Q13,Q15–Q22; ADR0006–0010 |
| CR2-T4 | 查看可追溯的腿轮辨识结果与误差曲线 | CR2-T3 | Open a paired result and inspect both response groups, parameters and recomputed errors; reject unverifiable legacy trajectory pairing | R8; Q19,Q23 |

T1 does not block T2 or T3: Isaac Lab/synthetic unified-model reference data can demonstrate those slices without waiting for native collection. Native-to-fit integration is checked after T1 and T3 at parent Verify. T4 does not depend on T1/T2 directly; T3 supplies its artifact. T2 genuinely gates T3 because it delivers approved shared group/action mapping and executable mixed task wiring. Editing a common test file is a sequencing concern, not an additional dependency.

Suggested execution order: T1, T2, T3, T4 to resolve native regression failures before broad checks. The available initial frontier is T1 and T2. No standalone prefactor: create the small approved shared helper as part of the executable T2 collection path; add its data-loading function in T3 when there is a consumer. Keep existing classes/entry points. Only two new implementation/test files are approved; T2 establishes them and later tickets extend them. No further structure changes, dataset sidecars or model changes are implied.

### CR2-T1 draft issue

**Parent:** #4. **Label:** ready-for-agent. **Blocked by:** None.

**What to build:** 用户可按统一的归一化扫频中心和编码器反馈语义重新采集原生 MuJoCo 数据，使后续统一模型拟合具有正确的参考物理语义。保留原生执行器、限幅、延迟、碰撞和既有可视化/保存行为。

**Acceptance criteria:**

- [ ] 采用已批准的归一化中心、幅度及独立方向语义，不修改用户当前数值、符号或碰撞设置。
- [ ] 原生位置执行器输入为期望位置加编码器偏置；初始物理角度、控制及历史输入与首个该输入一致。保留 XML 原生 PD、力限幅和延迟；轮关节不引入偏置。
- [ ] 验证标量关节传动和控制范围满足偏置等价条件；不支持的映射或会破坏等价关系的控制限幅在步进前明确报错，不能静默裁剪或改写 XML。
- [ ] 保存的位置为传感器位置减偏置再加既有噪声；随机噪声只影响测量。保存的期望位置仍为未加偏置、未施加执行器延迟的原期望。五字段、顺序、单位、采样和原子保存语义保持。
- [ ] 最小模型验证归一化中心/方向、非零偏置与历史的实际力响应、饱和和无效控制范围；既有查看器隔离、取消及失败保留输出回归通过。报告原先三项失败的实际修复结果，不能仅删除断言。
- [ ] 更新采集用法、中心系数含义、反馈偏置解释及旧 measurement-only 数据必须重新采集的说明。明确数值通过不代表物理模型有效。

### CR2-T2 draft issue

**Parent:** #4. **Label:** ready-for-agent. **Blocked by:** None.

**What to build:** 用户可在 Isaac Lab 对纯腿任务或包含轮速度跟踪的任务采集扫频响应；保存腿实际/期望位置、轮实际/期望速度和共同的实际采样时间，数据列与声明顺序一致。

**Acceptance criteria:**

- [ ] 保留 leg_order/wheel_order；纯腿旧 joint_order 归一化为腿组，混合 combined order 只拼接一次。重复、交叉、缺失名称及冲突声明明确失败。只修复必要的现有任务/资产接线，不重排目录或替换物理模型。
- [ ] 交付小型共用分组/映射模块并在实际采集使用：测量关节索引和动作列分别按名称解析，正确反算已支持绝对位置/速度动作的缩放及偏移；拒绝未知/相对/力矩动作、歧义覆盖和会改变目标的裁剪。
- [ ] 使用已批准归一化扫频轨迹、腿反馈与测量减偏置语义及轮无偏置规则。以控制周期确定样本数，在步进前记录实际时间、状态和当前发出的延迟前物理目标，修复未定义 trajectory 的实际执行路径。
- [ ] 纯腿保存三个 CPU 张量，混合保存五个；时间 float64、响应及目标 float32，单位和顺序符合契约。不生成元文件。非有限值、非整数采集时长或中途自动复位/终止明确失败，不拼接不同时段。
- [ ] 必要时修复混合任务边界数组和执行器容量配置，使任务可实例化；维数/数值遵守已批准布局和界限，不先行改造优化器或新增无用接口。
- [ ] CPU 测试覆盖纯腿兼容、动作列置换、缩放/偏移及非法配置；顺序 Newton/PhysX 各2环境、40步有界采集验证时间、两个响应组及保存读取。使用实际 ActionManager 路径，不能以旧直接关节目标探针替代。
- [ ] 同步采集命令、配置顺序、时序、数据字段和物理边界文档。共用测试文件按已批准范围新增，原生测试不因此需要启动 Isaac。

### CR2-T3 draft issue

**Parent:** #4. **Label:** ready-for-agent. **Blocked by:** CR2-T2.

**What to build:** 用户可声明并校验纯腿/混合参考数据，执行腿位置和轮速度的联合辨识，并获得实际评估过的全程最佳候选及其匹配响应、独立误差和可追溯配置。

**Acceptance criteria:**

- [ ] 复用共用分组/动作映射，增加安全数据读取和实际拟合接线。配置声明参考列顺序、偏置与延迟语义；缺字段、维数/顺序/模型/延迟模式冲突、非有限值和少于两个样本在候选评估前失败。旧 measurement-only 数据明确拒绝并提示重新采集。
- [ ] strict 模式检查实际时间网格匹配控制周期，容差采用已批准值；legacy_index 必须显式给出真实间隔，保留原始标签并用索引时间回放。无隐式重采样；纯腿历史三字段和可选空轮字段按契约处理。
- [ ] 参数分块采用机械量覆盖全部关节、位置偏置仅覆盖腿、一个共享延迟及可选末尾摩擦比例；X5基础61维、12腿49维。保留批准数值边界，支持固定边界；Newton拒绝无效动态摩擦比例辨识，PhysX保留已支持模型。
- [ ] 每次候选回放恢复腿测量初值加候选偏置、实测轮速、任务声明的轮角度/腿速度；偏置按执行器局部关节顺序映射且轮为零。状态、控制历史和缓冲每轮正确复位。
- [ ] 延迟候选非负向下取整，以物理步推进，记录候选值/实际步数/秒数；所有执行器容量覆盖上界。验证 decimation>1 时计算次数与延迟起效时刻；不静默切换任务延迟模式或启用忽略偏置的后端执行路径。
- [ ] 两组缩放后分别取时序/关节均方，按配置正权重加权，独立报告 rad/rad/s RMSE。纯腿只含位置项。默认2环境、拒绝小于2的种群；零分数停止统计有限；不把分数接近等同于物理准确。
- [ ] 每完成一个候选/完整代，按获批生命周期维护全程最佳及稳定并列规则；原子保存版本2的配对结果，包括候选身份、参数、两组测量坐标响应、参考数据/双时间、误差、声明、后端和实际延迟。均值仅诊断，未完成回放或异常不能替换已完成最佳。
- [ ] CPU 回归验证纯腿/混合布局、验证错误、评分与固定边界、零分数、跨代最佳身份及安全往返；顺序两后端最小回放各2环境40步。按Q22/Q23执行固定种子无噪声两活跃机械参数辨识：每后端至多4环境、20代、每次40步、120秒含参考检查；真值优于扰动，各组有限，最佳损失比初代最佳至少降低50%，保存轨迹可重算分组误差。检查RAM/VRAM，RAM低于4GiB或资源异常停止；失败如实报告，不搜索种子或放宽指标。
- [ ] 同步拟合配置、参数单位/后端差别、历史时间模式、数据重采集要求、结果格式和未验证物理边界文档。新增功能必须使用实际公开拟合路径，不以研究玩具实验代替验收。

### CR2-T4 draft issue

**Parent:** #4. **Label:** ready-for-agent. **Blocked by:** CR2-T3.

**What to build:** 用户可从成对最佳结果查看腿位置、轮速度及各组误差，核对选中的参数确实产生该响应；旧均值文件仍可作为诊断，但不能伪装成匹配的轨迹结果。

**Acceptance criteria:**

- [ ] 保留原有机器人/运行目录/绘图选择，提供已批准的结果选择选项，默认加载配对最佳结果；非法或冲突选择明确失败。
- [ ] 正确显示候选身份、参数块、实际延迟、关节名及单位；纯腿无虚构轮组，混合包含两组实测/期望/拟合响应。
- [ ] 使用保存的有效时间和已经减偏置的拟合位置，不重复减偏置；从选中记录重算组误差和目标函数以核对来源一致性，不混用不同代或不同文件的均值/轨迹。
- [ ] 均值诊断与候选响应明确区分；无法证明配对的旧结果不能执行误导性轨迹比较，提示原因及新结果生成方式。
- [ ] 非交互绘图测试验证纯腿/混合的系列、名称/单位、实际数值、结果选择和错误路径；使用T3产物完成一次保存到读取/查看的往返，无需再次执行优化。
- [ ] 更新结果读取与可视化用法、旧结果限制和误差解释；不调整损失、结果契约或物理验收标准。

### Ownership and integration boundaries

- T1 modifies native behavior/tests/examples in place; it adds no implementation module.
- T2 creates only the already approved shared contract helper and focused mixed tests, wiring the useful collection subset. Do not add an unused loader until T3 consumes it.
- T3 extends that helper/tests and existing fit/optimizer/actuator/task code; it owns data validation, normalized scoring, lifecycle and complete result persistence. T4 owns the existing consumer's display path and corresponding tests/docs. Shared edits do not authorize additional abstractions.
- Every ticket includes its own tests, error behavior and documentation. No separate generic schema/refactor/test/doc ticket. Each is intended to fit one fresh implementation context; if a concrete blocker requires reslicing, return to the approved boundaries rather than broaden scope silently.
- The starting checkpoint is already WIP. Verify affected slice behavior without pretending untouched known failures passed; T1 resolves native formula/bias regressions and T2 resolves the undefined collection variable. Broad combined acceptance is due after the frontier is complete.
- Parent Verify combines fresh native data from T1 with T3 fitting validation/replay, T2-generated data with T3, T3 paired results with T4, existing pure-leg coverage and native viewer regressions. Native-vs-Isaac physical convergence is not asserted. Do not rerun expensive controlled identification unless a later change or unresolved failure justifies it; preserve exact command/evidence.
- Formal Verify remains separately authorized. Planning/publication does not start production changes, runtime experiments or Implement. Preserve the pending CR1 manual GUI boundary.

### Publication review gate

Proposed breakdown is four tickets. Ask the user to confirm granularity, true blocking edges and whether to merge/split. No CR2 tracker writes have occurred. After approval, publish in dependency order as ready-for-agent sub-issues of #4; set native blocking links T3←T2 and T4←T3, verify labels/parents/edges and retain URLs here. Do not modify parent title/body/comments/state, earlier task states, or publish duplicates. If creation gives an ambiguous network result, read back by title/body before retrying.

This Plan draft changes documents only. No tests run; `git diff --check` is the document-format check, not software verification. No commit or push authorized by entering Plan.

CR2 breakdown approval: user answered “批准” to the four-ticket proposal, dependency graph and publication under #4 with ready-for-agent. This satisfies skill step4; publication is authorized without further confirmation. Prepared exact issue bodies and a temporary durable-per-step receipt; verify all parent/edge/body/label data after creation. No implementation approval.

### CR2 publication completed — 2026-11-17

User explicitly approved the four-ticket breakdown and publication (“批准”). All approved tickets were published with ready-for-agent and native parent #4.

- CR2-T1: [统一原生 MuJoCo 扫频中心与反馈编码器偏置](https://github.com/MrCCaesar/pace-sim2real/issues/10); blocked by: None.
- CR2-T2: [完成 Isaac Lab 腿位置与轮速度混合采集](https://github.com/MrCCaesar/pace-sim2real/issues/11); blocked by: None.
- CR2-T3: [支持混合关节辨识并保存成对最佳结果](https://github.com/MrCCaesar/pace-sim2real/issues/12); blocked by: #11.
- CR2-T4: [查看可追溯的腿轮辨识结果与误差曲线](https://github.com/MrCCaesar/pace-sim2real/issues/13); blocked by: #12.

Read-back assertions passed: exact approved bodies/titles, ready-for-agent labels, native parent lookup and parent sub-issue membership, and exact blocked_by lists. Parent title/body/state/comment count and comment bodies were unchanged; only the authorized native child relationships were added. No duplicate tickets, parent edits/comments, existing task-state changes, code changes, runtime tests, commits or pushes.

Plan complete. Initial implementation frontier: #10 and #11; #12 waits for #11, #13 waits for #12. Next stage Implement requires explicit user authorization. Earlier publication-gate paragraphs are historical and superseded by this completion record.

CR2 Implement clarification (user approved, 2026-11-17): the published T3 draft's Newton rejection requirement above is superseded. Newton configuration must warn, disable separate dynamic friction identification and remove its ratio bounds before optimizer creation. No tracker body edits were made; user-approved decisions take precedence. Both review findings are resolved: this clarification plus complete, unique actuator coverage preflight.

Post-implementation user amendment executed within existing files: config-owned action transforms; typed name/column mapping and pure reordering; prepacked commands; contiguous device buffers and one completed-data transfer; actual second timestamps clarified. Added regression at existing collector seam and bounded benchmark against a disclosed runnable ecefbfe loop adapter. No new ticket/file split or tracker writes; see verification.md for performance scope and results.

## CR3 — 拟合结果回放 · Plan / Approved and published

父 Issue 为 #4。任务依据是 CR3-R1–R4、Specify Q4–Q7 与验收 A1–A5。以下三个工单各自交付一个可从采集入口演示的行为，并随工单补充使用示例与对应测试。

### T1 · 用指定拟合结果回放扫频

前置：无。操作者可显式选择一份当前格式的最佳拟合结果，用已有扫频命令观察模型响应。

- [ ] 只传任务名继续固定参数采集。显式结果回放以单一 dt、分组关节名及命名参数为准；覆盖组内重排、缺失、多余、重复、跨组、旧双时步和物理设置冲突的情况。
- [ ] 用可区分的逐关节值检查惯量、阻尼、摩擦、腿偏置、轮零偏置及共享整数延迟。覆盖纯腿与混合任务、Newton 单一干摩擦和 PhysX 有／无动摩擦比例的情形。回放使用指定候选与扫频初态。
- [ ] 可以绘制期望和模型响应，报告参数与轨迹来源。回放默认不写数据；显式另存时保存命令、步前采样时间和模型响应，保护拟合输入与常规采集文件。播放与保存允许任意有限的跟踪误差。
- [ ] 给出显式回放和固定参数采集示例，以小规模受控输入检查现有采集与回放两条入口。对应 A1、A2、A5。

### T2 · 自动回放任务的最新拟合运行

前置：T1。操作者可以省略结果路径，直接播放当前任务最新运行，并能定位缺少结果的运行。

- [ ] 在当前任务日志根按拟合运行名中的启动时间选最新目录，排除录像等目录；自动选择与显式指定同一结果时，应用的候选和回放行为一致。
- [ ] 用“较早完整、较新未完成、另有录像目录”的组合验收；最新运行缺少最佳结果时报告所选路径并停止。覆盖没有拟合运行以及裸回放选项紧跟 Hydra 预设的情形。
- [ ] 文档示例并列展示无回放选项、无路径回放及显式路径三种用法。对应 A1、A5。

### T3 · 用采集轨迹验证预测响应

前置：T1。可显式选取最佳结果，再用任一符合契约的采集文件驱动回放。此路径足以完成本工单所有验收，故不依赖 T2。

- [ ] 按任务声明读取文件的分组、列和时间；覆盖显式扫频参数与文件互斥、首帧腿实测偏离期望、非零初始轮速，以及延迟历史复位。
- [ ] 用独立实测轨迹核对步前命令与响应。终端报告可手算核对的腿位置预测 RMSE（rad）和轮速度预测 RMSE（rad/s，仅有轮时）；绘图叠加期望、实测及模型响应。另存回放不能覆盖轨迹输入。
- [ ] 在相同配置、初态和命令下做短程复现，逐关节与最佳候选保存的模拟响应对照。软件验收采用全样本最大绝对差，腿位置 ≤ 0.0001 rad，轮速度 ≤ 0.001 rad/s。另用误差超限的有效输入验证正常回放、绘图、显式保存与正常退出。
- [ ] 使用说明分别展示同轨迹复现和独立轨迹预测，标注误差单位与阈值用途。对应 A3、A4、A5。

### 审批与交接

用户回复“批准”后，三个工单已发布为 #4 的子 Issue。已从 GitHub 核对正文、打开状态、ready-for-agent 标签、父 Issue 及原生阻塞关系。

- [#14 用指定拟合结果回放扫频](https://github.com/MrCCaesar/pace-sim2real/issues/14) 无前置依赖。
- [#15 自动回放任务的最新拟合运行](https://github.com/MrCCaesar/pace-sim2real/issues/15) 依赖 #14。
- [#16 用采集轨迹验证预测响应](https://github.com/MrCCaesar/pace-sim2real/issues/16) 依赖 #14。

进入 Implement 需另行批准，从 #14 开始。正式 Verify 按 A1–A5 汇总证据，分别记录同轨迹复现和独立轨迹验证的输入、运行条件与分组误差。Isaac Lab 的运行依仓库资源约束顺序执行。


### CR3 Implement · 测试与审查记录

已按 #14–#16 接通固定参数采集、显式／最新拟合回放与文件轨迹验证。基线为用户确认的 `912c7a6`，功能提交 `8b29bc1`，首轮审查修正 `1f5e88d`。使用示例见 [usage.md](../../docs/usage.md#replay-a-fitted-candidate-in-isaac-lab)。

- `PACE_RUN_REPLAY_INTEGRATION=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 .venv/bin/python -m pytest -q --tb=short`：126 项通过，4 条已有 CMA 运行警告。X5 多次启动的集成用例默认按需启用；测试先检查 RAM/VRAM，2 个环境，无实时查看器，单进程超时 120 秒。
- `uvx --offline pyright --pythonpath .venv/bin/python scripts/pace src/pace_sim2real/utils tests/test_fit_replay.py tests/test_mixed_collection_fit.py`：0 错误、0 警告。变更 Python 文件通过 Ruff。加严了重名和负值错误的断言，`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_fit_replay.py -k 'duplicate or negative'` 两项通过。
- X5 / Newton CUDA：取移动中的 32 帧做一代拟合，对同一候选逐样本复现，腿位置和轮速度最大绝对差均为 0。另一条单独采集的扫频得到腿位置预测 RMSE 0.020504419 rad、轮速度预测 RMSE 1.617103 rad/s。额外构造的超限测量仍可完整播放、以 Agg 绘图和保存。首次全量运行暴露测试进程污染了原生 MuJoCo 的导入隔离检查；将新增测试中的模拟器入口隔离到子进程后，全量通过。
- ANYmal / Isaac Sim PhysX：在临时目录依次执行固定参数采集（0.03 s）、一代拟合和指定结果的文件回放。三次使用 `--task Isaac-Pace-Anymal-D-v0 --num_envs 2 --visualizer none physics=isaacsim_physx`，拟合额外使用 `env.sim2real.cmaes.max_iteration=1`，回放使用 `--fit_result PATH --trajectory_file INPUT --output OUTPUT`。新结果含 61 个参数和 12 帧位置响应，复现的最大绝对差为 0 rad，保存三字段。测试发现 Kit 关闭可能结束 Python，已将保存、绘图和指标报告移入启动器生命周期。本机缺少独立 ovphysx 包；此项实测使用用户已授权的 Isaac Sim PhysX。
- 规范审查已复核资源预检、集成测试按需运行、配对时间和轨迹有限性。规格审查已复核自定义拟合参考文件保护、诊断中的参数名称和超限播放；独立轨迹的预测精度只报告，超限用例单独构造。本阶段检验自动绘图路径，人工 GUI 观察及正式 Verify 留待后续。
- 对提交 1f5e88d 单独解包后，使用其已提交的拟合器、采集器和任务代码重跑 X5 集成用例，仅共用本机机器人资产及依赖。1 项通过，复现最大差与独立 RMSE 均与上述结果一致，确认 CR3 功能可独立于工作区内此前的拟合性能改动运行。

## CR4 · 任意关节组合的拟合与回放 · Plan（已批准并发布）

依据为用户批准的 [CR4 规格](spec.md)、[接口](interfaces.md) 和 ADR 0011–0013。以下编号是本地任务编号。每项与对应测试及使用说明一起交付。

| 任务 | 前置 | 主要交付 | 需求与决策 |
| --- | --- | --- | --- |
| CR4-T1 | 无 | 由同一任务配置读取任意非空记录组合，按文件列序选取边界和尺度 | R1、R2、R6、R7；Q10、Q12 |
| CR4-T2 | T1 | 在完整机器人上执行部分关节拟合，写出与最佳候选配对的 v3 | R1–R5、R7、R8；Q7–Q9、Q11–Q12 |
| CR4-T3 | T2 | 在 TensorBoard 和离线图中检查候选、误差、收敛和分组响应 | R1、R3、R7、R8；Q9 |
| CR4-T4 | T2 | 用原文件复现拟合响应，或用独立文件和新保持工况回放 | R2–R8；Q7–Q11、Q13 |
| CR4-T5 | T4 | 省略轨迹文件时，仅对已辨识关节生成扫频并播放 | R2–R5、R7；Q14 |

### CR4-T1 · 选择并读取实际信号

主要涉及 `collection_contracts.py`、`PaceCfg` 和现有拟合契约测试。保留整机控制分组，用独立的两个 `reference_*` 字段解析实际信号。按关节名映射文件列、动作列、模型索引和整机参数块。

- [x] 使用可区分的通道值和上下界，检查单位置、单速度、非对称混合、两组默认全量及组内乱序。分别覆盖 `None`、`[]` 和显式列表，按名抽取逐关节尺度、偏置、可选摩擦比例，保留唯一的共享延迟。
- [x] 校验字段成对、时钟、形状、有限值、类型归属、重名和未知关节。解析后两组皆空时报告错误。原有三字段纯位置和五字段全量参考继续可读。
- [x] 在使用文档给出一份“单腿三位置加一轮速”配置和一份仅速度配置，标出文件实际列序。

### CR4-T2 · 拟合并保存配对结果

主要涉及 `fit.py`、`cma_es.py` 及 T1 的共享映射。预先组装完整动作序列。每轮依 Q7、Q11 恢复首帧，未记录关节跟踪任务的保持目标。仅按选中关节写机械参数、合成偏置与统计损失；候选延迟写入包含记录通道的每个完整驱动组。

- [x] X5 验收配置采用 FL、FR、RL、RR 四个驱动器组，每组含本腿 hip、thigh、calf、foot。逐腿切换四份文件，每份分别有 3 路位置、1 路速度和 16 项基础参数。另取单轮、跨腿不对称组合，检查相关组的全部通道使用同一候选延迟，其余组各自保留默认延迟。
- [x] 至少用两个可区分的候选或代核对状态恢复；未记录关节采用可区分的非零保持目标或默认偏置，确认每步命令、默认机械参数及组内偏置。仅速度时以速度误差计算有限评分；混合时按有效组的尺度和权重手算复核。
- [x] 输出批准的 v3 字段、具名参数与同一最佳候选的参考和响应，缺失组的 RMSE 为 None。现有单一 dt 全量任务继续读写 v2；覆盖 Newton 单一摩擦与 PhysX 可选比例的参数布局。文档说明结果中哪些值来自辨识，哪些描述试验工况。

### CR4-T3 · 检查优化过程与离线结果

主要涉及 `cma_es.py` 的日志、`plot_trajectory.py` 和现有拟合/绘图测试。

- [x] 实读 TensorBoard 事件文件。按名称核对所选参数的分布、均值和当代最佳值，共享延迟仅一项；终端和事件仅报告存在的响应组及其物理单位。
- [x] 离线读取有效全量 v2、部分及纯速度 v3；重新计算评分与 RMSE，检查配对候选一致性。绘图核对所选关节名称、输入和响应数据、图例及单位；进程分数曲线沿用现有开关。为使用文档补充两个版本的查看示例。

### CR4-T4 · 按文件回放和复现

主要涉及 `fit_replay.py`、`data_collection.py` 和现有回放测试。复用 T1–T2 的映射与物理规则，检查结果的完整控制范围、参与组、后端、求解器和时钟。按本次文件声明与结果逐组匹配并重排，按当前任务构造保持目标。

- [x] 对四份逐腿记录分别检查回放驱动组、输出列及诊断。控制工况相同时，对已保存的最佳响应做步前逐样本比较，位置最大绝对差 ≤ 0.0001 rad、速度最大绝对差 ≤ 0.001 rad/s。
- [x] 在独立轨迹上变更未记录关节的保持角或速度，核对旧值、新值、关节名及单位。确认新目标实际生效并完成回放；只报告有效组的独立预测 RMSE，允许任意有限误差。
- [x] 验证同集合乱序文件可回放，成员或跟踪类型变化会报错；实际另存的响应仅含选中通道，默认文件和输入受保护。用原全量 v2 及既有固定采集路径做回归。在使用文档区分原轨迹复现与新工况预测。

### CR4-T5 · 仅对已辨识关节生成扫频

在 `data_collection.py` 的无轨迹文件分支使用结果内的关节名，按任务既有系数生成选中关节的扫频，对其他关节发送保持目标。

- [x] 单腿、非对称及仅速度的例子均按名称核对中心、幅度、方向和实际动作列；同时检查未选关节每步的保持目标。
- [x] 缺少适用系数时指出需要提供轨迹文件。给出文件后按 T4 路径执行；原有显式文件与扫频参数互斥、显式或最新运行选取和输出保护继续有效。
- [x] 在 README 和现有使用说明中给出文件与自动扫频两种命令，说明无实测文件时展示的是命令跟踪效果。

### Verify 交接

各任务均带小规模自动化用例，优先扩充现有 `tests/test_mixed_collection_fit.py` 与 `tests/test_fit_replay.py`。正式 Verify 按任务编号登记命令、结果与偏差。四组逐腿场景贯穿拟合、日志、绘图和文件回放。用于物理复现的参考输入须来自相同保持工况；从全机同时扫频的数据裁列只用于映射检查。

先运行 CPU 契约、评分、事件文件和无窗口绘图检查，再串行执行短程 Isaac Lab 验证；启动前核对 RAM/VRAM，使用 2 个环境及无窗口模式。沿用现有全量回归用例，分别记录受控复现误差与独立预测误差。当前交付为任务拆分，验收结果在获准实施和验证后填写。

### CR4 发布记录

用户批准五项拆分并授权发布为 [#4](https://github.com/MrCCaesar/pace-sim2real/issues/4) 的子工单。GitHub 已回读核实正文、打开状态、ready-for-agent 标签、父子关系和下表所列前置依赖。

| 任务 | GitHub 子工单 | 前置工单 |
| --- | --- | --- |
| CR4-T1 | [#17 按文件列序读取任意位置与速度关节子集](https://github.com/MrCCaesar/pace-sim2real/issues/17) | 无 |
| CR4-T2 | [#18 在完整机器人上拟合部分关节并保存配对结果](https://github.com/MrCCaesar/pace-sim2real/issues/18) | #17 |
| CR4-T3 | [#19 在 TensorBoard 和离线图中查看部分关节拟合结果](https://github.com/MrCCaesar/pace-sim2real/issues/19) | #18 |
| CR4-T4 | [#20 用实测文件回放部分关节并验证独立工况](https://github.com/MrCCaesar/pace-sim2real/issues/20) | #18 |
| CR4-T5 | [#21 仅对已辨识关节生成并回放扫频](https://github.com/MrCCaesar/pace-sim2real/issues/21) | #20 |

### CR4 Implement 交接 · #17–#21

| 工单 | 已实现及实施检查 |
| --- | --- |
| #17 | `collection_contracts.py` 独立解析两组参考列并校验张量。全任务参数边界和逐关节尺度按名称投影到文件顺序。CPU 用例覆盖空组、乱序、重复、未知、错组和附加摩擦比例。 |
| #18 | `fit.py` 与 `subset_control.py` 在完整动作空间预组装保持目标。CMA 仅辨识选中通道，部分/纯速度结果写 v3。两组候选的定点测试检查实际写入的机械参数索引、全部初态、整组延迟和组内默认偏置。 |
| #19 | `cma_es.py` 与 `plot_trajectory.py` 按有效组记录事件和配对轨迹。纯速度手算例得到 score=2.5、速度 RMSE=√10 rad/s。独立绘图进程使用 Agg 检查已保存的记录。 |
| #20 | `fit_replay.py` 与 `data_collection.py` 按当前文件列序解析命令、测量及具名参数，核对整机与驱动组，报告保持目标变化。相同配置、合成输入的 X5 Newton 短程复现通过。 |
| #21 | 无文件回放根据结果中的名称选取任务已有中心、方向与幅度。CPU 核对跨腿数值和无系数报错，实际回放覆盖纯速度和非对称输入。README.md 与 docs/usage.md 有文件回放和扫频示例。 |

实施检查使用 2 个环境、无查看器，逐个启动仿真。四份单腿记录各使用 12 个步前样本、2 代和 4 个驱动组。逐腿核对输出与配对响应的最大绝对差如下。

| 逐腿记录 | 位置（rad） | 速度（rad/s） |
| --- | ---: | ---: |
| FL | 2.98e-8 | 1.19e-7 |
| FR | 1.49e-8 | 1.19e-7 |
| RL | 7.45e-9 | 1.19e-7 |
| RR | 2.98e-8 | 0 |

- 六种工况命令为 `PACE_RUN_SUBSET_INTEGRATION=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 MPLBACKEND=Agg OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 .venv/bin/python -m pytest -q tests/test_fit_replay.py -k x5_subset`。四份逐腿、仅轮和非对称混合均通过。加入仅位置用例后，用同一环境运行 `tests/test_fit_replay.py::test_x5_subset_fit_and_replay[position]` 和 `[FL]`，两项通过。
- 全量 v2 独立短程检查在临时目录依次运行 `data_collection.py --duration .04`、`fit.py env.sim2real.data_dir=chirp_data.pt env.sim2real.cmaes.max_iteration=1`、`data_collection.py --fit_result --trajectory_file data/Isaac-Pace-Sevnce-X5-v0/chirp_data.pt --output replay.pt`。三次均指定 `--task Isaac-Pace-Sevnce-X5-v0 --num_envs 2 --visualizer none`。确认 schema_version=2，配对位置与速度的最大绝对差均为零。
- 启用当时六项子集集成的全套运行得到 141 项通过、2 项失败、1 项跳过。两项失败都是原生 MuJoCo 输出路径断言。工作区既有脚本写入 `data/Isaac-Pace-Sevnce-X5-v0/mujoco_0.1_10Hz_kp1500_kd30_chirp_data.pt`，既有测试读取 `data/x5_sim/chirp_data.pt`。在独立临时目录用 `git archive HEAD` 的原脚本与原测试挂载同一模型，两项均通过。
- 变更的仿真入口、优化器及共享模块运行 `uvx --offline pyright --pythonpath .venv/bin/python` 的定向检查，零错误及警告。上述实现模块和回放测试通过 Ruff。既有混合测试文件原段落还有 1 项 I001 和 2 项 E501。 `git diff --check` 通过。
- 实际部分关节仿真使用 Newton MJWarp。PhysX 的摩擦比例布局和解码由 CPU 回归覆盖。正式 Verify 仍待批准。

CR4 正式 Verify 已完成。逐工单证据、数值、全量回归三项失败的归因见 [验证记录](verification.md)。

## CR5 · 离线采集数据滤波 · Plan（Approved）

本计划落实已批准的 [Q3–Q5 与 CR5-A1–A4](spec.md#cr5--离线采集数据滤波--specifyapproved)、[文件和命令行接口](interfaces.md#cr5--离线滤波接口approved)及 [ADR 0014](../../adr/0014-offline-measurement-filter.md)。建议按以下三项交付。

| 任务 | 前置 | 交付物与完成条件 |
| --- | --- | --- |
| CR5-T1 · 从采集文件生成滤波副本 | 无 | 实现 `scripts/pace/filter_chirp_data.py` 的完整命令行；在 `pyproject.toml` 中声明 SciPy 直接依赖并同步锁文件，沿用现有版本。覆盖默认四阶 20 Hz、显式阶数与截止频率、时间及张量校验、文件保护与失败退出。新增 `tests/test_filter_chirp_data.py`，通过 CLI 测试纯位置、纯速度、混合列、缺省或显式空列组。与逐列 SciPy 结果对照，核对原始文件摘要、字段顺序、形状、dtype、指令值以及拟合加载器读取结果。覆盖已有输出、输入别名、写入失败、异常时间和短记录。对应 A1、A4。 |
| CR5-T2 · 用已知真值验证幅值、时差及降噪 | T1 | 在同一测试文件固化 Research 的 400 Hz 五列合成信号、固定种子、10 ms 延迟及计算窗口。用默认 CLI 生成输出并逐频核对中段幅值损失 ≤1%、滤波前后的相位折算时差变化 ≤0.1 ms；中段及首尾 RMSE 分别 ≤ 滤前对应值的 35%。该回归应能仅依靠仓库内容在 CPU 上复现。对应 A2。 |
| CR5-T3 · 真实 X5 文件验收用例与中文用法 | T1；可与 T2 并行 | 在同一测试文件增加 X5 样例用例，对指定摘要的原始文件运行 CLI，将输出写到临时目录，再用现有拟合加载器读取。按 Research 的选频规则逐关节验证幅值变化 ≤1%、≥30 Hz 能量降幅 ≥40 dB，分别报告首末帧腿位置和轮速的最大绝对改变量。更新根目录 `README.md`，给出默认命令、四阶 25 Hz 加显式输出路径的示例，以及通过 `env.sim2real.data_dir` 选择结果的方法。对应 A1、A3、A4。 |

**验收资料与前提。** 已核实指定 X5 样例在本机可读，SHA-256 为 `8ab1ca9e3a430c0b4ad7fa951cf53dbc352d8e45263b6ee085bc300aa25732d8`，与 Research 一致；该文件未纳入 Git。T1、T2 的常规回归使用生成的张量。正式 Verify 须用匹配摘要的真实样例执行 T3；缺少样例时记录 A3 待验。[研究测量方法及基线](research.md#cr5-临时实验结果research已执行)

**Verify 交接。** 用户已批准三项任务并进入 Implement。三项实现完成并获准进入 Verify 后，执行 `.venv/bin/python -m pytest -q tests/test_filter_chirp_data.py`，确认真实样例用例实际运行，核对 README 中的默认和显式命令。将命令、逐项通过情况、数值和端点观察记入 `verification.md`。

### CR5 Implement 交接

- T1 已实现 `scripts/pace/filter_chirp_data.py`。现有锁文件中 SciPy 1.17.0 改为直接依赖，`uv lock --check --offline` 通过。输出文件以独占创建方式打开，同名并发写入、已有文件及输入别名均受保护；保存或关闭失败时清理本次创建的文件。
- T2、T3 的 CPU 用例位于 `tests/test_filter_chirp_data.py`。执行 `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_filter_chirp_data.py tests/test_mixed_collection_fit.py::test_reference_loader_requires_explicit_legacy_time_and_bias_provenance`，25 项通过，含真实 X5 样例。逐列统计的最大通带幅值变化为腿位置 0.159%、轮速 0.151%；≥30 Hz 最小能量降幅分别为 47.66、47.86 dB。首/末帧最大改变量分别为腿位置 0.00225/0.00986 rad，轮速 0.01093/0.35371 rad/s。
- README 已加入默认和显式参数示例。另在临时目录复制真实 X5 输入，分别执行 `uv run --no-sync python scripts/pace/filter_chirp_data.py "$record"` 及带 `--cutoff_hz 25 --order 4 --output "$out"` 的命令。两个进程均成功，`load_reference_data` 读回两份文件均为 8000 帧、12 列位置和 4 列速度，且两组参数产生的滤后位置有差异。
- 对上述新增脚本和测试执行 `.venv/bin/ruff check`、`.venv/bin/ruff format --check` 和 `uvx --offline pyright --pythonpath .venv/bin/python`，均通过。
