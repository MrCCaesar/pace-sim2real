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
