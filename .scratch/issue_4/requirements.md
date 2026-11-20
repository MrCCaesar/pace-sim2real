# Issue #4 — Requirements

Status: Approved requirements; implemented and software-verified in commit 87da096.
Source: https://github.com/MrCCaesar/pace-sim2real/issues/4 and user confirmations in this conversation.

## Confirmed requirements

- R1: Collect excitation data in native MuJoCo as an independent simulation reference for PACE.
- R2: Use src/pace_sim2real/assets/data/robots/sevnce/x5/mjcf/x5_calibration.xml; fixed base at 1 m, floor and light, all 16 joints.
- R3: Twelve leg position channels ordered FL, FR, RL, RR, each hip/thigh/calf; four wheel velocity channels ordered FL, FR, RL, RR.
- R4: Leg chirp centers [0, 0.4, -1.4] rad, amplitudes [0.25, 0.5, 0.99] rad; wheel velocity chirp center zero, amplitude 10 rad/s. Center is additive, not multiplied by amplitude.
- R5: Expose min_frequency, max_frequency, duration, plot. Approved defaults are specified in spec.md.
- R6: MJCF defines native PD, effort limits, command delay, single dry friction, armature and passive damping. XML timing is in seconds: dt=0.0025, delay=0.010, nsample=4 as last verified.
- R7: Position measurement = sensor reading - encoder_bias + Gaussian noise. Configurable encoder_bias defaults to 0.05 rad. Velocity measurement adds Gaussian noise without position bias.
- R8: Noise standard deviations come from XML: position 0.01 rad, velocity 0.1 rad/s as last verified; replaces earlier 0.02 proposal. Independent zero-mean Gaussian noise and reproducible random seed were confirmed.
- R9: Save data/x5_sim/chirp_data.pt with shared time[N], dof_pos/des_dof_pos[N,12], dof_vel/des_dof_vel[N,4].
- R10: Keep model, simulation configuration, tests and docs reasonably separate. Important architecture decisions require user confirmation. No unrequested functionality or physics simplification.

## Confirmed scope and startup

- Confirmed: collection, saving and plotting only; mixed-data fitting integration is outside Issue #4.
- Confirmed: desired signals are issued commands before native actuator delay.
- Confirmed: initial leg positions at chirp centers, wheel angles and all joint velocities zero; record startup transient without settling; initialize historical commands to those starting targets.

## Superseded decisions

- ANYmal model and all-position 16-column data were superseded by X5 mixed position/velocity collection.
- Additive encoder bias was corrected to subtractive bias.
- Earlier calf centers/amplitudes were superseded by R4.
- Millisecond wording was corrected: XML second values are authoritative.

## Approved design

Final interfaces and configuration are recorded in interfaces.md; architecture and acceptance criteria are in spec.md. User approved this baseline when entering Plan.

## Evaluation boundary — Confirmed

User owns collision-model and trajectory physical-suitability acceptance. No requirement for contact-free initial state or contact-free sweep is imposed by this issue. Do not exclude contacts or correct collision geometry as part of the collector work. Preserve the known contact findings; do not claim physical validity from numerical execution success. User intends to revise trajectory centers/amplitudes later; no revised numbers beyond R4 are currently approved.

## Change request CR1 — Draft / Explore

User invoked grill-with-docs to add configurable trajectory directions for symmetric joints and optional live MuJoCo visualization for debugging. Existing approved implementation and verification remain the baseline; CR1 is not yet specified or implemented.

Confirmed facts: Isaac Lab uses (sin(phase)+bias)*direction*scale; current native collector uses center+amplitude*sin(phase), with centers in physical radians. These bias conventions differ. Current local TOML has plot=true; preserve this user change.

Open frontier: whether direction mirrors center and oscillation together or oscillation only; whether wheels also need independent signs; whether visualization is an observation-only real-time 3D view independent of post-run plots. Exact APIs, direction vectors, viewer lifecycle and backend feasibility are deferred to later decisions/stages.

### CR1 round 1 confirmations

- Q1 confirmed: direction mirrors both center and oscillation; preserve physical center/amplitude semantics, desired = direction * (center + amplitude * sin(phase)).
- Q3 confirmed: observation-only live 3D visualization, approximately real-time playback and camera adjustment, independent of post-run plot switch. No force/control editing features requested.
- Q2 unresolved: user's wording “否为 12 个腿关节和 4 个轮关节分别提供独立的方向符号” is ambiguous. Clarify whether all sixteen channels have independent signs, only twelve leg channels do, or signs are grouped/shared. Do not infer a channel scope.

### CR1 direction scope — Confirmed

User clarified: “12 个腿关节和 4 个轮关节，各自配置独立的方向符号”. All sixteen channels therefore have independent direction signs. The prior Q2 ambiguity is resolved; shared/grouped signs and leg-only direction configuration are not selected.

The existing no-startup-jump requirement implies initial leg positions and historical position commands must match the signed center; wheel initial angles/velocities and zero historical wheel commands remain zero. Exact direction vectors and configuration defaults remain for Specify.

Remaining Explore questions: whether closing the observation window continues collection without visualization; whether an explicitly requested viewer that cannot start must fail visibly rather than silently fall back. No implementation choice or viewer API is approved by these questions.

### CR1 viewer lifecycle — Confirmed

User answered “4. 是 5. 是”. Closing the live observation window does not cancel collection: continue headlessly through the configured duration and save normally. Ctrl+C retains the existing cancellation behavior. If visualization is explicitly enabled but its window cannot start, report an error and exit without replacing existing output; do not silently fall back.

### CR1 Explore summary

Confirmed: independent direction signs for all 12 leg-position and 4 wheel-velocity channels; mirror the full desired trajectory (center and oscillation) while preserving physical units; keep sensor coordinate conventions unchanged. Observation-only live 3D display with approximately real-time viewing and camera adjustment is independent of post-run plots. Window-close continues collection; startup failure is explicit and preserves prior data.

Explore is complete for these requirements. Research transition awaits explicit approval. Research must establish native viewer availability/lifecycle, timing independence, close detection and startup-error handling. Exact configuration keys/defaults/sign vectors, APIs and implementation layout are deferred to Specify. Original software verification does not cover CR1.

### CR1 stage transition

User explicitly approved Research (“进入 Research 阶段”), superseding the earlier awaiting-approval statement. Confirmed Explore requirements remain authoritative.


## Change request CR2 — Explore complete / Confirmed requirements

User invoked grill-with-docs to extend the existing Isaac Lab data_collection and fit/CMA-ES flow to additional velocity-tracked wheel joints. Temporarily tracked as an amendment to Issue #4, continuing its established document location. No new issue creation or implementation authorized. CR1 manual GUI acceptance remains pending independently.

### Confirmed user requirements

- Preserve the intent of the user's PaceCfg changes: leg_order distinguishes position-tracked joints and wheel_order distinguishes velocity-tracked joints.
- Isaac Lab collection must save actual/desired wheel velocities separately, consistent with the native MuJoCo mixed-data convention: dof_pos/des_dof_pos for legs, dof_vel/des_dof_vel for wheels, shared time.
- fit.py and CMA-ES must recognize whether the task contains wheel data and consume that data for optimization. Exact recognition/validation mechanism is not yet selected.
- This explicitly extends the earlier collection-only scope: ADR 0001 remains the record of the original delivery, but its exclusion of fitting integration does not prohibit this newly requested work. Any new architecture/parameterization decision awaits the appropriate stage and approval.
- Existing uncommitted user changes, including robot/task/config changes, are inputs to preserve and reconcile, not discard.

### Confirmed code facts (read-only; not runtime verification)

- Collection reads leg_order/wheel_order and builds leg/wheel trajectories, but its loop still refers to the old trajectory variable and saves only time/dof_pos/des_dof_pos across joint_order. Several indexing expressions mix subset-local and articulation-global indices.
- fit currently loads only position fields, initializes from measured positions, sends position-derived actions and calls position-only optimizer scoring.
- CMA-ES scores squared position errors with per-joint encoder-bias correction, maintains only a position trajectory buffer and saves a single best-position trajectory. Its saved config omits wheel velocity fields.
- X5 joint_order already concatenates legs and wheels. PaceCfg friction-ratio helpers append wheel_order again when counting joints; X5 bounds allocate 49 rows while writing ranges through row 64. ANYmal currently supplies joint_order without leg_order. These are migration/integration concerns, not approved new APIs.

### Assumptions / recommendations

- Recommend retaining existing pure-position tasks and three-field historical datasets while accepting mixed datasets from both native MuJoCo and Isaac Lab. Await user confirmation.
- Recommend that a mixed task's fitting outcome covers both leg-position and wheel-velocity responses, with separately inspectable errors. Joint objective construction and relative weighting remain deferred.
- Recommend explicit rejection when task joint groups and supplied dataset disagree, instead of silently dropping a required response group. Await confirmation.

### Open requirement questions — round 1

Q1: Must existing pure-leg tasks and historical three-field position datasets continue to work, alongside mixed datasets from either collector?
Q2: Should a mixed-task fitting result identify both leg and wheel dynamics together and report the two tracking errors separately?
Q3: When the task declares wheel joints but data lacks either wheel velocity field or has incompatible channel counts, should fitting fail clearly rather than proceed with incomplete data?

### Deferred decisions

Which physical parameters to identify for wheels (including whether any wheel measurement bias is required); parameter sharing/delay scope; acceptable fitting quality and output/reporting expectations; time alignment and coordinate conventions. Once requirements settle, Research should investigate installed Isaac Lab action ordering, sensor/state access, delay/bias behavior and backend support. Loss normalization/weights, parameter-vector layout, checkpoint schema, task-detection algorithm, configuration defaults and implementation layout belong in Specify. No simulation or optimization experiments have been run for CR2.


CR2 independent read-only source cross-check: installed Isaac Lab ActionManager concatenates action terms in configuration order, while preserve_order regex matching groups X5 joints by hip/thigh/calf patterns rather than the configured per-leg leg_order. Articulation IDs therefore cannot be assumed to be action-vector column indices. The current X5 config also contains an incomplete import statement. These are present working-tree integration gaps; user may still be editing them. Re-read before future edits. Existing optimizer has one shared delay, per-joint position bias, zero initial velocities and position-only saved configuration/best trajectory. Whether these semantics extend to wheels remains an explicit requirement/design frontier, not an inferred approval.


### CR2 round 1 — Confirmed

User answered “1. 是，三字段历史数据是指？2. 是的 3. 是”. Clarified that historical three-field datasets contain time, dof_pos and des_dof_pos only: they represent position responses and position targets, without wheel velocity measurements/targets. Compatibility applies to pure-position tasks; it does not authorize inferring missing wheel velocities from position data or ignoring configured wheels.

- CR2-R1: support existing pure-leg tasks and their historical position-only data, plus mixed datasets from native MuJoCo and Isaac Lab.
- CR2-R2: one mixed-task fitting outcome covers both leg and wheel dynamics; report leg-position and wheel-velocity errors separately. Objective normalization/weighting remains deferred.
- CR2-R3: task/data group mismatch, missing required measured/desired wheel-velocity fields, or incompatible channel counts must fail explicitly before fitting.

### CR2 next requirement frontier — Proposed / unanswered

Q4: identify wheel armature, damping and friction alongside leg dynamics; retain position-encoder-bias identification for position joints only, without adding wheel position bias or velocity-measurement bias identification. Friction model selection and backend feasibility remain later decisions, not a new approval here.
Q5: whether a single shared control delay for legs and wheels, as in the existing optimizer, satisfies the requirement or whether separate group delays must be identified. Recommendation: retain shared delay unless the physical system requires separate delays. No numeric bounds, step units or parameter layout selected in Explore.

Next frontier after these answers: required backends, moving-wheel initial conditions and acceptance/output expectations. Existing user collision/physical-suitability ownership remains unchanged. No CR2 runtime experiments or implementation performed.


### CR2 round 2 — Confirmed

User answered “4. 是 5. 是”.

- CR2-R4: wheel dynamics identification covers armature, damping and friction. Position encoder bias is identified for leg-position channels only; no wheel position-bias or velocity-measurement-bias identification is added in this change. Specific friction parameterization and bounds remain for Research/Specify.
- CR2-R5: one shared control delay across leg and wheel groups satisfies the requirement; no independently identified group delays. Exact units, rounding, bounds and parameter-vector layout are not yet decided.

### CR2 round 3 — Open requirement frontier

Q6: must this extension retain support for both currently handled Newton and PhysX backends? Recommendation: yes, preserving existing backend distinctions rather than claiming identical friction physics.
Q7: must fitting accept reference data whose wheels are already moving at the first recorded sample? Recommendation: yes; zero initial wheel speed should not be an unstated restriction. State initialization details and unavailable wheel-angle handling are deferred.
Q8: must saved fitting results and trajectory comparisons include both leg-position and wheel-velocity responses, with group labels/units, rather than only the current position trajectory? Recommendation: yes. Exact checkpoint formats and legacy-reader compatibility remain for Specify.

These questions define scope/observable behavior only. Loss construction, normalization, parameter indexing, action mapping and code layout remain deferred. Acceptance quality and physical evaluation boundaries will be finalized once scope is confirmed. No production changes or simulations performed.


### CR2 round 3 — Confirmed

User answered “6. 是 7. 是 8. 是”.

- CR2-R6: retain support for the existing Newton and PhysX backends, preserving documented physical-model differences; do not imply backend equivalence.
- CR2-R7: support reference datasets with nonzero measured wheel speed at the first sample. Exact initialization from measurements, handling of unrecorded wheel angles, and simulator API feasibility remain Research/Specify concerns.
- CR2-R8: persisted fitting results and trajectory comparisons cover both leg-position and wheel-velocity groups, with distinguishable joint names and units. Checkpoint schema, existing result-reader migration and layout remain deferred.

### CR2 round 4 — Final Explore questions / unanswered

Q9: should consistency with native MuJoCo collection include temporal/command semantics, not just tensor key names: shared time denotes actual sample instants, measured and desired data correspond to the same instant, and desired values denote issued commands before actuator delay? Recommendation: yes. Step/control-rate mapping, time-grid validation, resampling policy and concrete collection sequence remain deferred.
Q10: should software acceptance include a small controlled identification case demonstrating the mixed fitting loop works and separately checks position/velocity errors, with real-robot/model convergence quality and physical parameter plausibility retained for user acceptance? Recommendation: yes. No numerical convergence threshold, loss normalization/weight, experiment workload or budget is approved by this proposal; these need later stage evidence/design. No guarantee to recover every parameter uniquely is implied.

After these answers, consolidate Explore and request explicit Research transition. Outstanding technical decisions include action-space ordering, backend APIs, mixed residual scaling, parameter layout, initialized wheel states, time-grid compatibility, persisted results and compatibility of existing consumers. No production edits, runtime simulations or optimization trials were performed for CR2.


### CR2 round 4 — Confirmed / Explore conclusion

User answered “9. yes 10. yes”.

- CR2-R9: consistency between native MuJoCo and Isaac Lab collection includes semantics: shared time represents actual sampling instants, measured and desired channels align at those instants, and desired values are issued commands before actuator delay. Matching key names alone is insufficient.
- CR2-R10: software acceptance includes a bounded controlled identification case demonstrating the mixed fitting loop and separate position/velocity error evaluation. Real-model convergence quality and physical parameter plausibility remain user-owned acceptance. Numerical thresholds, workload and experiment approval are deferred; no particular parameter-identifiability guarantee is made.

Explore is complete. The open requirement questions from rounds 1–4 are resolved by the user confirmations recorded above. Confirmed scope: preserve leg_order/wheel_order grouping; keep pure-position task/data compatibility; accept mixed native/Isaac Lab data; identify leg and wheel dynamics with a shared delay and leg-only position bias; retain Newton/PhysX support; handle initially moving wheels; validate task/data consistency; save/show both response groups; align sampling/command semantics; distinguish software acceptance from physical fitting quality.

### Research handoff — not yet authorized

Investigate installed versions and current working-tree changes before selecting approaches:

1. Action-term/channel ordering versus articulation joint IDs; mixed position/velocity command application and measurement access on both backends.
2. Existing encoder-bias and delay behavior, first-sample/initial-wheel-state handling and effects of unrecorded wheel angles.
3. Sampling/control intervals, dataset time-grid compatibility and feasible alignment approaches.
4. Parameter bounds/layout and friction options compatible with both backends; mixed-unit residual scaling approaches and observability limitations.
5. Existing optimizer result consumers, checkpoint/reporting compatibility and separate leg/wheel response outputs.
6. Design a small, bounded controlled identification experiment and propose measurable software acceptance criteria. Obtain specific approval before Research runtime experiments; stage transition alone is not experiment approval.

No technical approach, new default, parameter layout, loss formula, checkpoint schema or production implementation is approved by Explore completion. Next stage requires explicit Research authorization. CR1 manual GUI acceptance remains pending independently.

CR2 stage transition: user explicitly approved Research (“进入research”). This supersedes the earlier awaiting-stage-approval statements; no runtime experiment or final design is implied.


### CR2 trajectory clarification — Confirmed user amendment

User clarified: “centers单独乘的direction已经去除，按照现在的(centers + np.sin(phase[:, None])) * amplitudes * directions，这样与data_collection.py中轨迹的生成保持一致”. The normalized-center formula is now authoritative for this requested alignment; it supersedes CR1's physical-center interpretation for forthcoming changes. Do not revert the user's native formula.

The physical center equals centers * amplitudes * directions. The current native initialization/history still uses centers directly; this is a confirmed remaining inconsistency, not an approved startup jump. With current values, a thigh center coefficient0.4 and amplitude0.5 imply a physical center0.2 rad, while current initial qpos is0.4 rad. Aligning initial state/history, config descriptions, tests and examples must be carried into Specify/Implement. No revised numeric center coefficients/amplitudes were requested.

## CR3 — Explore / Draft · 拟合结果回放与独立轨迹验证

### 已确认

- 用户批准进入 Explore，并同意上一轮的回放方案。原有固定参数采集仍有独立用途。
- 在 Isaac Lab 中使用一次拟合全程最佳已评估候选的惯量、阻尼、摩擦、腿编码器偏置和共享延迟，观察其在另一条期望轨迹上的响应。适用已有纯腿、腿轮混合任务及各自的摩擦物理语义。
- 回放默认从 `logs/pace-sim2real/<task>/` 的最新拟合 run 取 `best_result.pt`，任务由 `--task` 指定；也可明确选择结果文件。该规则针对参数来源，验证轨迹可以独立选择。
- 支持调整扫频激励，也支持用既有采集文件的期望轨迹回放。有独立实测时可对齐初态，比较期望、实测和模型响应。验证输出与原始采集数据隔离，回放可按需另存。

### 首轮问题与建议（已答复）

1. 固定参数采集和自动选择结果的触发条件。建议单独给出 `--task` 继续固定参数采集，给出无路径的 `--fit_result` 即回放最新 run。另一种需求解释是只给任务名即自动回放，由用户显式选择固定参数采集。
2. 最新拟合 run 缺少结果时的预期行为。建议提示所选 run 和缺少的文件并结束，由用户明确选择其他 run。
3. 独立实测数据的验收输出。建议除曲线外分别报告腿位置与轮速度的预测 RMSE；本轮不预设拟合质量通过阈值。仅有期望轨迹时只能评价对命令的跟踪。

### 首轮结论与 Explore 交接

用户确认 Q1–Q3，并在 Q1 补充了显式结果文件的关节名称检查。

- CR3-R1：只传 `--task X` 保留固定参数采集。`--task X --fit_result` 选择任务 X 的最新拟合 run。`--task X --fit_result PATH` 读取指定文件。
- CR3-R2：显式指定文件也须核对其关节名称与任务配置。沿用已同意的按名称对齐方案，分别核对腿、轮组；组内仅排列不同可对齐，缺失、多余、重名或跨组的关节应报告差异并终止回放。
- CR3-R3：选中最新拟合 run 后，若缺少 `best_result.pt`，提示所选目录和缺少的文件并停止。用户可以显式指定较早的结果。录像等非拟合目录不参与选择。
- CR3-R4：提供独立实测时，绘制期望、实测和回放响应，以回放响应减实测响应分别报告腿位置预测 RMSE（rad）、轮速度预测 RMSE（rad/s，仅有轮任务）。仅有期望轨迹时展示命令跟踪。无需预设拟合质量通过阈值。

当前 Explore 问题均已答复。待用户批准进入 Research 后，核对运行目录识别、结果兼容性、参考数据初态和现有绘图能力。阶段结论记录用户要求，具体实现和测试留待后续阶段。

## CR4 Explore · 使用部分关节的参考轨迹进行拟合（草案）

**已知需求。** 检查 X5 的四种输入：仅四个髋关节、仅四个大腿关节、四个小腿加四个轮关节、仅四个轮关节。每个被记录的关节都提供期望与实测量，共用时间列。用户希望通过任务配置选择关节。本轮限于 Explore。

**已核实的现状。** 当前 X5 配置声明 12 个位置通道、4 个速度通道、覆盖全部关节的动作和一个 16 关节执行器组。数据列必须与声明等宽，列名由配置按顺序声明。动作关节、执行器关节、辨识关节目前要求一致。含位置通道的部分数据可表达为专门配置的小任务，条件是同步调整分组、动作、执行器、参数边界和逐关节尺度；这会改变未选关节的控制条件。纯速度拟合还受到非空位置组、必需位置字段、位置首帧初始化和按位置组初始化评分等约束。当前检查依据工作区源码，未做仿真实验。

**首轮建议（已由下文答复取代）。** 一、在完整机器人上只辨识、评分、报告文件中记录的关节，延续共享延迟。二、未记录的关节按真实采集工况受控，所需目标由用户配置；具体是位置保持、零轮速、被动还是另有激励需要确认。三、本轮功能边界建议为已有文件的拟合及拟合诊断，改变采集与拟合结果回放另行确认。沿用 Issue #4 的本地变更记录，不更改 GitHub 状态。

**首轮暂缓事项（共享延迟范围见 Q5 决定）。** 保留现有数据字段和分组方式，四类文件正常时无需伪造空缺组的测量。具体配置语法、是否便利支持正则、执行器划分、延迟对未选组的作用范围和自动化验收应在需求确认后再定。尚无新 ADR 或实施决定。

### CR4 Explore 结论（Q1–Q6 已确认）

- CR4-R1（Q1 已确认）：仅辨识、评分和报告文件中有成对期望与测量的关节，根据这些关节的响应估计一个共享延迟，其作用范围见 Q5。
- CR4-R2（Q2 已确认）：复用同一机器人任务和环境配置。用户通过配置声明记录关节、未记录位置关节的恒定角度目标和未记录速度关节的恒定速度目标。保持目标是整个过程的控制工况；各组的记录通道和保持目标可以随实验切换。未记录关节的时变指令不在本轮范围。
- CR4-R3（Q3 已确认，取代上段对范围的建议）：fit.py、TensorBoard、离线绘图以及 data_collection.py 播放指定拟合结果和轨迹均须支持部分关节。回放中的其余关节使用任务默认的逐关节参数。四类输入沿用同一套需求，包含仅速度组的情况。

- CR4-R4（Q4 已确认）：拟合与回放中，未记录关节的逐关节参数沿用当前任务加载后的机器人模型和执行器默认值。例如，在当前 X5 任务中仅辨识轮关节时，腿编码器偏置沿用任务的 0 rad。共享延迟按 Q5 作用于整个执行器组。
- CR4-R5（Q5 已确认）：候选延迟在拟合时作用于整个执行器组，回放时将拟合所得延迟应用于同一整组，覆盖组内未记录的关节。当前 X5 的一个执行器组覆盖 16 个关节；即使仅四个轮关节有记录，全部 16 个关节也使用同一延迟。
- CR4-R6（Q6 已确认）：独立回放轨迹可以改变频率、时长及期望值，所记录的位置关节集合与速度关节集合分别与拟合结果一致。用户按文件列序声明关节名；未记录关节继续跟踪配置的恒定目标。

Explore 需求问题已答复。下一阶段经用户批准后，研究兼容原有完整数据的最小修改范围。

### Research 阶段收到的范围澄清（用户已确认）

- CR4-R7：由同一机器人任务已经配置的位置跟踪关节和速度跟踪关节中任意选择非空组合。两组可单独存在，也可同时存在。所选关节可以是一个、多个或全部，可以跨部位、左右不对称、在模型中不相邻。关节所属的跟踪组沿用任务声明，参考文件的列身份由配置按实际列序给出。
- Explore 列出的仅髋、仅大腿、小腿加轮、仅轮速均为示例。验收覆盖还应包含单关节及不对称混合组合，以便发现按后缀、肢体配对或固定列数实现造成的遗漏。

- CR4-R8（Specify Q8 补充，已确认）：验收覆盖每条腿四个关节共用一个驱动器、四腿共四组的布局；每次采集一条腿的数据，并使用相应的单腿记录拟合和回放。

## CR5 · 离线采集数据滤波 · Explore（需求已确认）

**已确认。** 用户要求在 `scripts/` 下编写脚本，对已有 X5 带噪声的采集记录进行滤波。输入样例为 `data/Isaac-Pace-Sevnce-X5-v0/mujoco_0.1_10Hz_kp1500_kd30_chirp_data.pt`。实际读取确认共有 8000 帧，时间从 0 到 19.9975 s，等间隔 0.0025 s（400 Hz）。位置测量及指令各 12 列，速度测量及指令各 4 列，全部为有限浮点值。

**用户确认（Q1、Q2）。**

- CR5-R1：仅对测量张量 `dof_pos`、`dof_vel` 的各关节时间序列做离线滤波，将结果另存为可供 `fit.py` 直接读取的文件。
- CR5-R2：输入与输出的字典字段、各张量形状和数据类型、样本数及关节列序完全一致。时间和期望指令逐元素保留原值。
- CR5-R3：降噪时尽量保留样例扫频范围 0.1–10 Hz 内的有效响应幅值和测量相对期望指令的时差，以支持后续延迟辨识。
- CR5-R4：滤波器参数可由用户通过脚本命令行设置。

**后续决策。** 滤波器类型、可配参数的具体名称、默认值和保真度的定量验收标准，留待 Research 和 Specify。样例的扫频范围不直接决定滤波器截止频率。

## CR6 · 滤波结果可视化与参数比较 · Explore（需求已确认）

**用户提出的需求。** 在现有离线滤波脚本中允许用户选择是否绘图，并打印五项验收指标以辅助比较滤波参数：最大幅值变化、最大时差变化、滤后 RMSE 占滤前的比例、有效频点最大幅值变化，以及 ≥30 Hz 能量的最小降幅。诊断沿用既有采集文件与滤波输出契约。

**已核对的事实。** 当前 CLI 成功后打印输出路径。CR5-A2 的最大幅值变化来自已知频点的干净正弦，最大时差变化来自含噪正弦滤前与滤后的相位差，RMSE 比例以干净响应为真值，分中段和首尾。CR5-A3 的另外两项直接从输入记录计算，按实测与指令均有足够能量的频点比较幅值，并在记录通道内取高频能量降幅的最小值。普通采集文件提供期望指令和带噪测量，指令到真实响应还包含动力学跟踪误差。[验收结果及口径](verification.md#cr5-离线采集数据滤波验收)

**首轮问题（答复见 Q1–Q3）。**

1. 是否希望每次使用当前滤波参数对统一的合成基准报告前三项，并对用户正在处理的文件报告后两项？若目标是观察真实记录的跟踪误差，可按期望指令计算并明确标为“跟踪 RMSE 比例”，其物理含义与 CR5-A2 不同。
2. 实际数据的指标是否按已有的位置组、速度组分别汇总（只记录一组时只报告该组），并在关闭绘图时照常打印？
3. 绘图是否只需交互查看，按记录关节叠加显示期望指令、滤前实测与滤后实测的时间曲线？是否还需要保存图片或观察频谱？

**暂缓决策。** 不同采样率和扫频范围下的指标适用条件、有效频点或高频能量不足时的输出语义、命令行参数与显示格式留待后续阶段。

### Q1–Q3 用户答复与实测指标范围

- CR6-R1（已确认）：五项运行时指标均取自本次输入文件及其滤波结果。可用参考信号为文件中的期望指令；CR5 合成信号的验收仍属于原有回归测试。
- CR6-R2（已确认）：按文件中实际存在的位置组和速度组分别汇总，关闭绘图时也打印指标。
- CR6-R3（已确认）：开启绘图时，按记录关节在同一时间轴叠加期望指令、滤前实测与滤后实测，并显示滤前带噪测量的频谱。图用于交互查看，无需自动保存。

### Q4–Q6 已确认的指标含义

下表每项均对实际记录的位置组和速度组分别报告。

| 指标 | 参考与汇总口径 | 单位 |
| --- | --- | --- |
| 最大峰峰值变化（Q4 选 A） | 对每个关节分别计算滤前、滤后整段测量的峰峰值（最大值减最小值），以滤前峰峰值为基准求相对变化，报告组内最大的绝对变化率。 | % |
| 最大时差变化（Q5） | 在有效频点比较滤前、滤后测量相对同一期望指令的时差，报告所有记录关节与有效频点中最大的绝对变化。 | ms |
| 跟踪 RMSE 比例（Q6） | 以各关节期望指令为参考，对组内全部关节和整段样本分别计算滤前、滤后跟踪 RMSE，报告滤后值除以滤前值的百分比。 | % |
| 有效频点最大幅值变化 | 对各关节的有效频点，以滤前实测频谱幅值为基准，报告滤后幅值的最大绝对相对变化。 | % |
| ≥30 Hz 能量最小降幅 | 对每个关节比较滤前、滤后在 ≥30 Hz 频带的总能量，报告组内最小降幅。 | dB |

**后续研究。** 频点有效性、相位与时差估计，以及峰峰值或跟踪误差分母为零、缺少有效频点或高频能量时的可报告性，留待 Research。

## CR8 独立回放入口与部分关节采集（Explore · Draft）

**用户提出的需求**

- CR8-R1：新增独立的 `replay.py` 入口，迁出 `data_collection.py` 中的回放逻辑，与采集共用仿真逻辑。迁移覆盖已有的全量与部分关节拟合结果、按原轨迹复现、按独立实测轨迹验证，以及生成新扫频的回放。
- CR8-R2：普通 Isaac Lab 采集使用任务配置中的 `reference_leg_order` 和 `reference_wheel_order` 选择记录关节。支持只采位置、只采速度和两组混合，输出列按各组声明顺序排列。

**已确认的现状。** 两个参考字段在拟合与文件回放中独立解析：每组的 `None` 取该组全部关节，`[]` 跳过该组，两组均空无效。现有普通采集按任务完整分组扫频；成功采集写入任务的 `chirp_data.pt`。详见 [CR4 配置契约](interfaces.md#cr4-配置契约--q10q12-已确认)。

**工作假设。** “同样使用”沿用现有参考字段语义和采集数据格式，使一份子集记录可直接用同一组配置拟合。例如 X5 配置 `reference_leg_order=[]`、`reference_wheel_order=None` 时，文件含时间与四列轮速的期望、实测值。

**Q1–Q2 用户已确认**

1. CR8-R3（Q1）：采集时只对选中关节施加扫频，其余关节沿用部分关节拟合时的保持目标。例如仅采四轮时，四轮跟踪扫频速度，腿关节持续跟踪各自的保持位置。[保持工况约定](../../adr/0011-held-joint-initial-state.md)
2. CR8-R4（Q2）：直接移除 `data_collection.py --fit_result` 回放入口，所有既有回放命令迁移到 `replay.py`。用户选择直接切换，此前的兼容转发提议已取代。

**暂缓决策。** 共用仿真逻辑的具体边界、新入口参数细节和验证方式留待后续阶段。CR7 的 CSV 同步与时间来源仍按其原有问题单独讨论。

**Q3 已确认（Research 交接）。** CR8-R5：部分采集仅对选中关节写入固定采集机械参数及编码器偏置。其余关节保留任务默认机械参数及偏置。每个含选中关节的执行器组整体使用 5 个物理步的延迟，完全未选中的组保留任务延迟。用户答复“同意上述参数作用范围，并批准 CR8 进入 Specify”。[物理决策](../../adr/0017-partial-collection-parameters.md)
