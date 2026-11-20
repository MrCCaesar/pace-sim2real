# Issue #4 — Research

Baseline status: Complete. Research was explicitly authorized after Explore; user subsequently approved entry into Specify. This record retains the findings and consequential decisions; transient interview prompts are omitted.

## API evidence

- Local MuJoCo version: 3.17.0. Updated X5 calibration MJCF compiled successfully after user supplied OBJ meshes.
- Sensor noise is metadata, not engine-injected noise: [3.17 changelog](https://mujoco.readthedocs.io/en/3.17.0/changelog.html#version-3-1-4-april-10th-2024).
- Reset initializes scalar command history with zeros at -n*dt through -dt. Assigning ctrl/keyframe does not populate prior commands: [engine_io.c](https://github.com/google-deepmind/mujoco/blob/3.17.0/src/engine/engine_io.c#L1350).
- mj_initCtrlHistory initializes native history; null timestamps retain the existing timestamps: [engine_support.c](https://github.com/google-deepmind/mujoco/blob/3.17.0/src/engine/engine_support.c#L926).
- Native delay reads at time-delay before adding the current sample. Four samples cover a 10 ms delay at 2.5 ms steps: [delay semantics](https://mujoco.readthedocs.io/en/3.17.0/modeling.html#delays).
- Sensors are evaluated before integration; immediately pairing their values with post-step time causes a one-step mismatch: [engine_forward.c](https://github.com/google-deepmind/mujoco/blob/3.17.0/src/engine/engine_forward.c#L1844).
- Existing fitting reads position fields and dispatches position actions only. Mixed wheel-velocity fitting needs separate work.

## Approved feasibility experiments

Approval: user said “允许执行两个临时实验”. A temporary native-MuJoCo probe exited 0; its checks are now covered by the maintained collection test suite. The disposable script was removed during user-requested cleanup.

1. Single hinge, eight steps: history value 0.2 and newly issued command 0.7. Applied force remained 0.2 at 0/2.5/5/7.5 ms and became 0.7 at 10 ms. Explicit forward evaluation matched current state; immediately after stepping, sensors retained pre-integration values.
2. X5, 40 steps / 0.1 s: probe-only 1 Hz sinusoid with confirmed centers/amplitudes. States/sensors finite, warnings zero, base fixed at [0,0,1]. Largest observed actuator effort about 138.474 Nm, wheel effort about 20.356 Nm, within limits. This probe did not drive saturation or validate a full chirp.
3. Initial-state contact diagnosis (no additional integration): 16 contact points, four between each hip and base, with 5.25 mm penetration. Hip movement was about 0.0005 rad in the short run; contact causality was not isolated experimentally.

## Decisions and approval provenance

- Q1 yes: collection/save/plot only; mixed fitting is outside scope.
- Q2 yes: desired fields retain issued commands before actuator delay.
- Q3 yes: legs start at configured centers, wheels/velocities at zero; record startup without settling.
- Q4 yes: initialize historical commands to starting leg targets and zero wheel speeds.
- Q6 no: rejected excluding base-to-hip contacts; retain the user-owned collision model.
- Q7 no: rejected contact-free acceptance. User owns physical collision/trajectory acceptance and may adjust trajectories later.

## Superseded recommendations

Contact exclusion and waiting for collision-model correction were considered, then rejected by the user. Contacts are a known physical limitation, not a blocker to software collection acceptance. Earlier additive encoder bias, all-position wheel data and conflicting calf ranges are superseded by requirements.md.

## Conclusion

Requested mechanisms are feasible in native MuJoCo 3.17. Detailed design is in spec.md/interfaces.md; final software evidence is in verification.md. Successful execution does not establish model fidelity, full-sweep stability or identification accuracy.


## CR1 — Research / Complete; awaiting Specify approval

Approval: user requested “进入 Research 阶段”. Scope: independent direction signs and optional observation-only live visualization. Baseline evidence above does not verify CR1.

### Confirmed facts

- Installed MuJoCo is 3.17.0 (local package METADATA). Re-read Issue #4 via `gh issue view 4 --repo MrCCaesar/pace-sim2real --json title,body,comments,url`; no comments. User-confirmed CR1 requirements supersede initial issue text.
- Current collector initializes qpos, ctrl and native history from centers before generating desired signals. Direction signs must consistently affect desired trajectories and initial leg centers/history. Wheel initial angles/velocities remain zero. Sensor coordinates and five saved tensor shapes need no change. This is source analysis, not a test.
- Official [3.17 passive-viewer documentation](https://mujoco.readthedocs.io/en/3.17.0/python.html#passive-viewer): both sync modes import GUI changes to controls, options and perturbations. Hidden panels can be reopened. Passive does not mean observation-only.
- Installed `mujoco/viewer.py:555–602`: launch_passive calls mj_forward, starts a Linux daemon worker, then waits on a handle queue without timeout. GLFW initialization failure is raised in the worker, so caller try/except alone does not establish bounded failure handling. Native initialization also has fatal-error paths ([versioned source](https://github.com/google-deepmind/mujoco/blob/3.17.0/simulate/glfw_adapter.cc)).
- Installed `viewer.py:208–236` exposes close/is_running; sync becomes a no-op after shutdown. Collection can be governed by sample count independently of viewer lifetime.
- DISPLAY is present, but usable desktop/GL context is unverified. No viewer was launched.

### Approaches / Proposed, not selected

| Approach | Benefits | Limitations |
| --- | --- | --- |
| Shared model/data passive viewer | Small integration | GUI edits can affect physics; startup failures may escape caller handling or hang. |
| Separate viewer model/data, same process | One-way copies can isolate GUI edits | Worker/native failure containment remains unresolved. |
| Separate viewer process and model/data | Isolates GUI edits; allows bounded startup handshake | Adds state transfer, lifecycle and resource overhead. |
| Custom renderer/camera UI | Can expose only observation controls | Larger implementation and maintenance scope. |

Recommendation: investigate a separate passive-viewer process receiving authoritative state one way. No architecture is accepted. A subprocess preflight followed by in-process launch leaves a second-launch failure race.

Wall-clock pacing can remain separate from fixed-step physics. Rendering need not occur at every sample; timestep, sample count, time grid and noise sequence remain authoritative. Slow rendering must not drop physics samples. State-transfer and scheduling contracts belong in Specify.

### Assumptions / open and deferred decisions

- Research targets the current Linux environment; other platforms are unverified.
- Actual GUI startup, failure mode, close behavior, visual fidelity and overhead require runtime evidence.
- Config keys/defaults/direction vectors, compatibility policy, render cadence, timeout and runtime-crash policy remain for Specify.
- Signed trajectories may encounter different limits/contacts; no clipping or collision changes are authorized. Physical acceptance remains user-owned.

### Experiment proposal — subsequently approved (see results below)

E1: temporary isolated viewer with one X5 model, at most 0.1 s / 40 authoritative simulation steps and a 15 s wall-clock limit. Open, sync and programmatically close the viewer; continue through all samples and compare against a deterministic headless baseline. Modify control/options only on the display copy to check authoritative-state isolation. No dataset output. Camera usability and actual visual appearance remain human checks; programmatic close does not prove a desktop close-button action.

E2: temporary subprocess with an invalid display environment and a 10 s wall-clock limit; observe startup error/timeout and cleanup. Only this subprocess gets the invalid environment. No production data/config writes.

Check resources first; run sequentially; probes under /tmp. Earlier baseline experiment approval does not authorize CR1 experiments. Neither has run. No CR1 tests or production implementation changes performed.


### CR1 experiment results — 2026-11-17

Approval: user explicitly said “允许执行两个临时实验”. This supersedes the pending-approval and not-run statements above. Experiments ran sequentially; no production code/config/model/dataset writes. Temporary harness: `/tmp/pace-cr1-probes/probe.py`. Durable raw results: `cr1-research-results.json`.

Resource preflight commands: `free -m` and `nvidia-smi --query-gpu=memory.free,memory.total --format=csv,noheader`. Available RAM 20,726 MiB; free GPU memory 22,502 MiB of 24,564 MiB. No Isaac Lab or training process was launched by these experiments.

E1 command:

```sh
timeout --kill-after=1s 15s .venv/bin/python /tmp/pace-cr1-probes/probe.py e1 > /tmp/pace-cr1-probes/e1.json
```

Result: all assertions completed; viewer child exited 0. Existing collector ran a deterministic baseline and an observed run, each 40 steps / 0.1 simulation seconds, with the current seed/config and no plotting/saving. A temporary in-memory wrapper around mj_step sent mjSTATE_INTEGRATION snapshots to a separate viewer process using its own X5 model/data. The wrapper was restored afterward; no source edits.

- Viewer started and synchronized successfully in this desktop environment.
- At step 5 the display copy's control values were set to 123 and its gravity to zero as a deliberate isolation probe. These values were never applied to the authoritative collector.
- Programmatic close at step 10 produced is_running=false; all remaining 30 physics steps completed, and later close checks remained false.
- time, dof_pos, des_dof_pos, dof_vel and des_dof_vel were exactly equal (np.array_equal) between the baseline and observed run.
- No screenshot/manual camera test was performed. Direct mutation of the display copy is not a mouse-interaction test; programmatic close is not a window-manager close-button test. This validates isolation/lifecycle feasibility, not finished product behavior or full visual fidelity. The harness used synchronous acknowledgments, not a proposed production scheduling contract.

E2 command:

```sh
timeout --kill-after=1s 10s .venv/bin/python /tmp/pace-cr1-probes/probe.py e2 > /tmp/pace-cr1-probes/e2.json
```

Result: child DISPLAY was set to invalid-display-cr1; parent environment unchanged. Child exited 1 after 1.099 s, emitted “X11: Failed to open display” and “ERROR: could not initialize GLFW”, and returned no ready message. Parent captured the failure and reaped the child. MuJoCo generated MUJOCO_LOG.TXT containing only this startup error in the repository root; it was moved to /tmp/pace-cr1-probes/MUJOCO_LOG.TXT. Process inspection found no remaining probe processes. The 7 s inner watchdog did not fire; this run proves containment of the observed native startup failure, not the untriggered timeout path. No save function was called in either experiment, so no dataset was replaced; future implementation still needs its own output-preservation tests.

### CR1 research conclusion / recommendations

Independent direction signs fit the existing mixed-channel contract, provided signed leg centers also initialize position and command history. Separate viewer-owned state in a child process is feasible for observation-only collection and startup-failure containment in this environment. Recommend this approach for Specify, subject to explicit architecture approval. It adds lifecycle/state-transfer complexity and duplicates model memory.

Remaining Specify decisions: direction keys/defaults and backward compatibility; viewer switch/CLI interaction with plot; snapshot fields and rendering cadence; approximate-real-time pacing; startup timeout; distinguish normal window close from later viewer failure; cleanup/error/output contracts. A minimal rendering snapshot versus full integration-state transfer remains a design choice; the probe does not mandate either. Signed trajectories still require user-owned physical acceptance. No implementation, full sweep, production regression suite or manual GUI acceptance has been performed for CR1. Next stage: Specify only after explicit user approval.


## CR2 — Research / In progress

Authorization: user explicitly requested “进入research” after confirming Explore Q1–Q10. Investigation below is read-only; no simulator import, simulation, optimization trial or production edit was performed. Existing user changes must be re-read before implementation. CR1 software verification remains historical evidence for its committed version, not for later user edits.

### Versions and primary evidence

Installed Isaac Lab checkout: /home/sevnce-mr/IsaacLab, VERSION 3.0.0, commit ae63302486bb92fc865f1fd8449b91a53728184c (clean at investigation). Installed metadata: cmaes 0.13.1; torch 2.11.0+cu130. Local source is authoritative for these installed APIs. The Isaac Lab commit-specific web URL could not be fetched; it is not substituted with a different release. [cmaes v0.13.1 upstream source](https://github.com/CyberAgentAILab/cmaes/blob/v0.13.1/cmaes/_cma.py) corroborates the installed optimizer source.

### Confirmed facts and feasibility

1. **Canonical channel order requires explicit mapping.** ActionManager slices actions in configured term order (installed source/isaaclab/isaaclab/managers/action_manager.py:423). Joint action terms resolve their own ordered joint IDs (envs/mdp/actions/joint_actions.py:64,198,251); preserve_order groups by regex-key order (utils/string.py:257–291). Current X5 hip/thigh/calf regexes therefore do not yield its per-leg leg_order. Explicit ordered action names or a validated name-to-action-column mapping are feasible alternatives; articulation IDs remain separate measurement/state-write indices.
2. **Moving wheels are supported by the APIs.** base_articulation.py:997,1051 accepts selected positions/velocities shaped [num_selected_envs,num_selected_joints], with cache invalidation. Current optimizer zeroes velocities and must be adapted for CR2-R7. Dataset wheel angles and initial leg velocities are absent; no claim that wheel-angle/contact effects are irrelevant is justified. Initial-state assumptions remain a design/physical question.
3. **Sample timing differs today.** ManagerBasedEnv.step_dt is physics dt times decimation (manager_based_env.py:295–300); env.step advances that interval (:581–598). Current collector counts physics steps but uses endpoint-inclusive linspace, reads measured positions before stepping and retrieves actuator targets afterward. fit advances one env.step per row while ignoring actual dataset intervals. Building new data from actual sampling intervals and pairing pre-step state with issued commands is feasible. Legacy linspace datasets require an explicit interpretation or conversion; rejecting them all conflicts with compatibility, while silently treating their timestamps as physical time is incorrect.
4. **Shared command delay already supports velocity commands.** PaceDCMotor uses position/velocity/effort DelayBuffers in command mode; effort mode delays torque (utils/pace_actuator.py:53–60,74–78,105–115). Installed DelayBuffer.compute returns oldest available data after reset until enough history exists (utils/buffers/delay_buffer.py:195–221). Candidate delay currently truncates to integer (cma_es.py:210). Actual delay cadence under backend-owned substeps/decimation needs bounded runtime evidence.
5. **Bias placement is not equivalent across collectors.** PaceDCMotor.compute supplies joint_pos minus encoder_bias to feedback; collection/scoring also subtract bias and initialization adds it (pace_actuator.py:86–94; cma_es.py:129,191–210). Its prose says adding but code subtracts. Native collection applies bias only to recorded positions. This changes closed-loop physics, not just tensor naming. Supporting both dataset sources requires a declared compatible bias model or explicit source-specific interpretation; no silent change to feedback is approved. Wheel bias is excluded by CR2-R4 regardless.
6. **Parameter count follows confirmed physical scope.** For J=L+W channels, three mechanical parameters per joint plus L leg biases and one delay gives 3J+L+1, before optional friction ratios. X5 yields 61; pure-leg ANYmal remains 49. This is dimensional accounting, not a chosen ordering/default. Existing optimizer assumes 4J+1; X5 user bounds allocate49 but access64, and friction helpers double-count wheels. Existing ANYmal sets joint_order only; compatibility needs normalization/migration while retaining leg_order/wheel_order.
7. **Backend friction is not interchangeable.** Newton articulation.py:2039–2102 treats friction as force/torque (MJWarp dof_frictionloss); nonzero dynamic-friction arguments are warned/ignored; viscous friction has its own write. Actual solver support is conditional. PhysX behavior depends on concrete implementation/version (isaaclab_physx articulation.py:1869 and isaaclab_ov articulation.py:1949). Existing presets include Isaac Sim PhysX/OV PhysX, Newton MJWarp and Kamino; requirements cover Newton and PhysX, not an unverified promise for every solver. No optimizer dimension should be presented as identifiable if its selected backend ignores that parameter.
8. **Existing result provenance is inconsistent.** CMA mean_NNN.pt is a distribution mean, but best_trajectory.pt stores a sampled candidate and is overwritten. plot_trajectory.py:93,119 subtracts mean bias from that candidate trajectory; selecting an older mean can still load the latest trajectory. Saving both response groups must associate parameters, trajectory and generation explicitly. The existing consumer is plot_trajectory.py; docs/usage.md and tutorials/basics.md,advanced.md also describe these artifacts. Exact versioning/legacy-read schema belongs in Specify.
9. **Population and stopping require care.** Installed cmaes _cma.py:92–103 permits positive population sizes but computes mu=population//2; size1 gives no positive-weight parents. Source-derived safe minimum candidate for a smoke test is2, not proof of robust optimization. Existing fit default is1. Current stop rule divides score spread by minimum score; zero score needs defined handling, and small spread is not an accuracy criterion.

### Approach comparisons — Proposed, not selected

| Question | Alternatives | Trade-offs / recommendation |
| --- | --- | --- |
| Mixed residual units | Scale by measurement noise, accepted physical tolerances, or reference excitation amplitude | Noise scaling needs noise assumptions; tolerance scaling needs approved targets; amplitude scaling needs zero-excitation safeguards. Report raw rad/rad/s errors separately in every case. Do not directly add unscaled position and velocity squares. |
| Group weighting | Per-channel sum or per-group mean plus weights | Channel sum favors larger groups; group mean removes count dominance. User has not approved a weighting policy. |
| Legacy timestamps | Explicit legacy index-based interpretation, explicit conversion, or resampling | Source cadence/provenance is necessary; arbitrary resampling changes commands/delay and is not automatically permitted. |
| Bias semantics | Preserve source-specific feedback models or deliberately harmonize future collection | Preserving requires explicit provenance/config; harmonizing changes existing physics and needs approval plus legacy treatment. |
| Output association | Save matched candidate/trajectory or evaluate/store the chosen mean with its own trajectory | Either can give truthful provenance; silently pairing current mean and sampled trajectory cannot. |

### Current workspace conflict — clarification pending

Since CR1 verification, user changed native desired from centers + sin(phase)*amplitudes*directions to (centers + sin(phase))*amplitudes*directions, while centers already includes directions and initializes state/history. This changes center scaling/sign behavior and can create a first-command/initial-state mismatch. An asynchronous clarification asks whether to retain approved physical-center semantics, intentionally redefine normalized centers, or exclude a temporary experiment. No code was reverted or tested. CR1 verified results must not be attributed to this edited formula.

### Inferences and remaining risks

Response matching does not prove unique parameter recovery. Armature needs acceleration excitation; damping/friction can correlate; feedback can mask mechanical changes; delay introduces discrete plateaus; contacts and symmetric excitation couple responses. Missing wheel angle or initial leg velocity can matter. Both-backend APIs exist, but runtime availability, model loading, property propagation and actuator cadence remain unverified in CR2.

### Proposed bounded experiments — not yet approved or run

E1: CPU-only isolated temporary probe using installed torch/cmaes and synthetic data; check pure/mixed dimensional accounting, two-candidate ask/tell and zero-score handling, group ordering/nonzero wheel-speed initialization contracts using a stub, and candidate/trajectory round-trip association. At most10 generations with2 candidates; 30 s wall limit; no simulator/GPU. This checks feasibility, not parameter recovery on a robot.

E2: sequential headless installed-backend probes with2 environments, a minimal position joint plus velocity joint, at most40 steps / 0.1 s simulated time per backend, at most120 s wall time each including initialization. Check resolved action mapping, nonzero initial wheel speed, pre-step samples/issued commands, shared command-delay cadence and selected mechanical-property writes. Check RAM/VRAM first and stop on resource pressure; no concurrent simulators, no full training/optimization. Use temporary isolated configuration to avoid executing the unfinished user X5 module, with no production edits. Backend initialization failure is reported, not silently substituted with another backend.

Both probes write only under /tmp; exact outcomes will be recorded here if approved. Approval of Research alone does not authorize them. Architecture, loss weights, parameter/default layouts and output schemas remain for Specify. Bias/legacy-time and trajectory-semantic conflicts must be resolved explicitly before dependent design decisions.


### Trajectory conflict resolved by user clarification

User explicitly selects normalized centers with (centers + sin)*amplitudes*directions and confirms removal of the earlier centers*directions preprocessing. Read-back confirms this in the current native source. The former clarification question is resolved; preserve this formula. Native qpos/ctrl/history still initialize to raw centers, so first-target consistency remains future work. Earlier CR1 tests/results refer to its committed physical-center version only and must not be claimed for the amended behavior.

### Experiment authorization

User said “允许两个临时实验”. E1/E2 are approved within the above limits. No production edits are authorized by this approval. CPU probe and sequential backend probes reside in /tmp/pace-cr2-probes.


### CR2 approved experiment results — 2026-11-17

User approval: “允许两个临时实验”. This supersedes earlier not-approved/not-run descriptions. Probe sources/logs/models are under /tmp/pace-cr2-probes; durable outputs and source hashes are in cr2-research-results.json. Only temporary probes and issue documentation were changed; no production code or environment dependency installation.

Resource preflight: available RAM19,880 MiB; GPU22,672/24,564 MiB free. Backend runner monitored available RAM against a4 GiB floor, enforced120 s per runtime and killed the process group on limit violations. No resource limit was reached. Simulators were sequential; no training or full X5 sweep.

**E1 CPU command:** `timeout --kill-after=2s 30s .venv/bin/python /tmp/pace-cr2-probes/cpu_probe.py` — exit0, CUDA was not initialized.

- Current optimizer accepted pure-position49 bounds with a2-candidate population. It rejected the confirmed mixed-scope61 bounds with “Expected65 ... got61”, experimentally confirming the layout gap rather than silently adding unused wheel biases.
- With zero candidate scores, current relative score-spread was nonfinite and finished() returned false before max iterations; zero-score stopping requires explicit handling.
- Installed cmaes completed8 generations of2 candidates on a two-coefficient synthetic position/velocity response objective, with finite scores. Best observed score0.1164526908 at generation2; the final generation's best was0.1631592606. This is not evidence of monotonic convergence or physical parameter recovery. Diagnostic scales in this toy are not approved production loss weights.
- cmaes emitted divide-by-zero RuntimeWarnings at _cma.py:117,119 with this tiny population. Finite output does not make population2 a recommended production optimizer setting; later design/validation must distinguish minimum-resource smoke tests from robust optimization.
- Stub name-based packing preserved shuffled joint order and nonzero wheel velocities1.5/-0.75 are tested in E2; the CPU stub itself used3/-2 rad/s. Candidate parameters, generation and both response arrays survived a paired torch round-trip. These checks demonstrate temporary-probe feasibility, not implemented project support.

**E2 commands:** `python3 /tmp/pace-cr2-probes/run_backend.py newton`, then `python3 /tmp/pace-cr2-probes/run_backend.py physx`. Each invokes the installed .venv Python and backend_probe.py with --device cuda:0 and --visualizer none. The installed launcher rejects --headless; an initial argument-only attempt exited2 without launching physics and was corrected to its documented no-visualizer selection. No production CLI was modified.

- Newton run exited0 in13.004 s. Installed NewtonCfg solver_cfg=None selects MJWarpSolverCfg (newton_manager_cfg.py:166). Two environments, one position-controlled revolute joint and one velocity-controlled revolute joint each, zero gravity/no contacts, dt0.0025 s,40 steps. Python PaceDCMotor loaded in isolation; CUDA graphs disabled; use_newton_actuators=False.
- Initial wheel speeds1.5 and-0.75 rad/s were written/read correctly. Armature and dry-friction property readbacks matched; viscous friction write was exercised but not independently read back or physically calibrated.
- Both issued commands changed at index4; the actual PaceDCMotor delayed-command hook observed their changes at index6, confirming shared lag2 for this one-compute-per-step setup. Exactly40 actuator compute calls; positions/velocities remained finite.
- The probe used direct articulation targets, so ActionManager permutation/mapping runtime behavior remains untested. It establishes neither X5 model validity nor identical physics across backends. Deprecation warnings for legacy target setters and a Newton shape-color warning were recorded; Specify should use current target_command APIs.
- Explicit Kit PhysX run exited1 in3.001 s before simulation: Isaac Sim was not installed/available. Follow-up metadata checks found neither isaacsim nor ovphysx nor physx-usd-schemas installed. No OV runtime was substituted and no dependencies were installed. **PhysX execution remains unverified due to missing runtime**, although its source/API path was inspected.

### Research conclusions and remaining decisions

The mixed control/measurement and shared-delay mechanisms are feasible on installed Newton/MJWarp in a minimal model. The existing optimizer/data/results path still requires the documented changes; the CPU probe confirms61-versus65 and zero-score issues. PhysX support can be designed against installed source but cannot be runtime-accepted in this environment until its runtime is provided. Two-backend equivalence is neither required nor demonstrated.

Confirmed user trajectory amendment resolves the formula question: normalized centers. Current native startup positions/history still need alignment with the resulting first targets; accepted amendment recorded in ADR0004. Prior CR1 physical-center evidence is not transferable to the edited formula.

Open design/physics decisions for Specify: source-dependent bias behavior; legacy timestamp interpretation; absent wheel-angle/leg-initial-velocity assumptions; mixed residual scaling/weighting; parameter layout and population/stopping policy; matched parameter/trajectory result provenance and compatibility. These must not be silently settled by experimental toy choices. No further runtime experiment is currently proposed without a concrete need. Research evidence is consolidated; next stage Specify requires explicit user approval.


## CR2 installed Isaac Sim retest — 2026-11-17 (Confirmed evidence)

This entry supersedes the earlier missing-Isaac-Sim execution limitation, retaining that attempt as history. User installed Isaac Sim 6.2.0.0 and explicitly requested a rerun. The user explicitly accepted the EULA and authorized `OMNI_KIT_ACCEPT_EULA=YES` for this test only; no persistent environment setting or dependency change was made.

The first accepted-EULA run exited127 in5.002s with mixed USD native-library errors. The probe had imported `pxr` and authored USD before Kit started. Installed Isaac Lab launcher documentation requires USD runtime imports after Kit initialization. Moving runtime imports/asset creation inside `launch_simulation` in the temporary probe resolved the failure without library-path overrides.

Commands (sequential, resource preflight:13869MiB available RAM,22553MiB free GPU):

```bash
OMNI_KIT_ACCEPT_EULA=YES python3 /tmp/pace-cr2-probes/run_backend.py physx
OMNI_KIT_ACCEPT_EULA=YES python3 /tmp/pace-cr2-probes/run_backend.py newton
```

Both returned0: PhysX9.003s; Newton8.003s. Each used2 environments,40 steps,dt0.0025s, headless, a120s watchdog and4GiB RAM floor. Assertions passed for nonzero initial wheel velocities, armature/static-friction readback, shared2-step leg/wheel command delay, and finite position/velocity samples. PhysX emitted protobuf/interface-version warnings; target setters emitted deprecation warnings; Newton emitted its shape-color workaround warning. No resource safety stop occurred.

Durable run records, samples and probe hashes: `cr2-research-results.json` → `installed_isaacsim_retest`. These are isolated articulation experiments, not complete X5 collection/fit tests. ActionManager mapping, parameter recovery and backend physical equivalence remain unverified. Research recommendations still require Specify approval.

## CR3 — 拟合结果回放与独立轨迹验证 · Research / Draft

范围为 [CR3-R1–R4](requirements.md#cr3--explore--draft--拟合结果回放与独立轨迹验证)。本轮只读核查仓库源码、已接受的 ADR 和现有结果文件；未执行测试、拟合或仿真。

### 已确认的事实

1. **运行目录。** 拟合入口用规范化任务名构建 `logs/pace-sim2real/<task>/`，优化器用本地时间 `%y_%m_%d_%H-%M-%S-%f` 创建直接子目录，先建目录，再写配置，至少一代评估完才有最佳文件。已有绘图工具先筛有所需文件的目录，再按目录修改时间选择，还会搜索历史根 `logs/pace/`。直接沿用会在最新运行失败时选中旧结果。录像也使用任务日志根。 [拟合入口](../../scripts/pace/fit.py#L91) · [目录与产物写入](../../src/pace_sim2real/optim/cma_es.py#L144) · [绘图查找规则](../../scripts/pace/plot_trajectory.py#L165)
2. **参数归属与名称。** `best_result.pt` 的 `params` 已转换为物理参数；记录只在获得更低的全程分数时更新，并保存同一候选的身份、命名参数、腿轮顺序、参考和仿真轨迹、误差、运行设置与延迟。惯量、阻尼、摩擦各有腿轮全组，偏置仅有腿，共享延迟一个；可选的动摩擦比例覆盖腿轮全组。实际延迟步数为候选值向下取整。均值文件不能替代已评估候选。现有读取器验证 v2 配对、轨迹及原训练误差，但未逐项验证参数名称唯一且完整，也未将参数名称与目标任务比对。 [产物构造](../../src/pace_sim2real/optim/cma_es.py#L319) · [候选选择](../../src/pace_sim2real/optim/cma_es.py#L242) · [读取器](../../scripts/pace/plot_trajectory.py#L69) · [ADR 0010](../../adr/0010-paired-evaluated-fit-results.md)
3. **已有两种 v2 设置。** 只读核查得到下表。两者均声明 `time_mode=strict`、`reference_bias_model=feedback_and_measurement`、`reference_delay_mode=command`。格式版本相同，时钟和后端字段的表示仍有差异。当前拟合限定 `decimation=1`，输出单一 `dt`。 [设置写入](../../scripts/pace/fit.py#L61)

   | 已有结果 | 腿 + 轮 / 参数数 | 延迟 | 运行设置 |
   | --- | --- | --- | --- |
   | [ANYmal](../../logs/pace-sim2real/Isaac-Pace-Anymal-D-v0/26_11_17_19-42-16-084289/best_result.pt) | 12 + 0 / 49 | 9 步 | `physics_dt=control_dt=0.0025` s；backend 为 `isaaclab_newton.assets.articulation.articulation`，solver 是 NewtonCfg 的完整文本表示 |
   | [X5](../../logs/pace-sim2real/Isaac-Pace-Sevnce-X5-v0/26_11_18_14-42-36-908171/best_result.pt) | 12 + 4 / 61 | 5 步 | `dt=0.0025` s；backend 为 `NewtonCfg`，solver 为 `MJWarpSolverCfg` |

4. **参考数据没有关节名。** 原始文件按任务声明解释：纯腿有时间、期望和实测位置，混合任务另有期望和实测轮速。加载器检查有限性、形状和严格递增的至少两个样本。严格模式按相对首时刻与控制间隔匹配；历史索引模式需要显式声明真实间隔。两者均无自动重采样。文件本身无法证明列顺序、偏置语义或是否参加过拟合。旧的仅测量偏置数据须重采。现有加载器需要实测字段；仅生成期望扫频的路径可独立提供命令。 [加载器](../../src/pace_sim2real/utils/collection_contracts.py#L127) · [ADR 0006](../../adr/0006-explicit-reference-time.md) · [ADR 0009](../../adr/0009-reference-semantics-in-fit-config.md)
5. **采集和拟合的初态、摩擦有实质差异。** 固定采集把腿物理位置设为首条期望加偏置，所有受控关节速度置零；其 PhysX 动摩擦取静摩擦的一半。拟合把腿物理位置设为首条实测加候选偏置，轮速取首条实测（可以非零），轮角和腿速度取任务默认值，重置执行器历史。拟合时 Newton 写一个干摩擦量；PhysX 有比例则乘比例，无比例则动摩擦等于静摩擦。位置响应在测量坐标中减偏置一次。现有采集循环能执行预打包动作并按步前时间采样，且只保存环境零。 [固定采集](../../scripts/pace/data_collection.py#L97) · [采集初态](../../scripts/pace/data_collection.py#L235) · [采样](../../scripts/pace/data_collection.py#L313) · [拟合初态输入](../../scripts/pace/fit.py#L218) · [拟合参数写入](../../src/pace_sim2real/optim/cma_es.py#L364) · [ADR 0005](../../adr/0005-unified-feedback-encoder-bias.md)
6. **预测误差和输出。** 已有绘图按关节画三曲线，使用保存的训练响应，重算每组时间和关节上平方误差平均值的平方根；物理 RMSE 与拟合目标使用的权重和尺度分开。固定采集写文件时原子替换 `data/<task>/chirp_data.pt`。独立验证必须以新仿真响应和本次参考重算 RMSE，纯腿无轮速指标；只有期望时只能报告命令跟踪。当前 [X5 采集文件](../../data/Isaac-Pace-Sevnce-X5-v0/chirp_data.pt) 的五个张量与上表 X5 结果内的参考完全相同（8000 样本，首行实测轮速为零），适于检查同输入回放，不构成独立验证。ANYmal 结果仅含 4 个样本，当前采集文件有 8000 个，长度差异本身不能证明独立性。 [误差定义](../../scripts/pace/plot_trajectory.py#L35) · [拟合绘图](../../scripts/pace/plot_trajectory.py#L138) · [固定采集输出](../../scripts/pace/data_collection.py#L245) · [ANYmal 采集文件](../../data/Isaac-Pace-Anymal-D-v0/chirp_data.pt)

### 可行路径与假设（推断）

- 在当前任务根先按写入器的时间戳目录名识别并选择最新运行，随后检查 `best_result.pt`，可以同时排除录像、识别未完成运行并避免回退。按目录修改时间识别新旧会受事后复制或编辑影响。显式文件与自动选择均可先在 CPU 加载并校验。该判据假设拟合使用上述时间戳命名；非标准目录中的文件仍可显式指定。 [目录写入](../../src/pace_sim2real/optim/cma_es.py#L144)
- 结果含名，可先分别核对腿、轮两组，再按“参数种类 + 关节名”排列全部参数块，独立处理共享延迟。随后沿用任务现有的关节索引与动作列映射；这两种映射作用于不同对象。应同时校验缺、多、重、跨组名称，摩擦比例块完整性、有限值与物理范围，以及延迟候选、步数、秒数和任务时钟的一致性。 [参数布局](../../src/pace_sim2real/optim/cma_es.py#L87) · [任务动作与关节映射](../../src/pace_sim2real/utils/collection_contracts.py#L46) · [ADR 0008](../../adr/0008-canonical-joint-groups-and-layout.md)
- 按拟合语义直接应用已评估参数，复用采集的步前采样，与“实例化优化器再跑一次拟合”相比，可避免创建新训练目录或采样候选。直接套用固定采集常量会改变初态或摩擦。可复用分组绘图和物理 RMSE 计算；数据来源、图例和结果路径应能区分训练记录、独立实测与新回放。 [优化器初始化](../../src/pace_sim2real/optim/cma_es.py#L144) · [采集循环](../../scripts/pace/data_collection.py#L276) · [拟合绘图](../../scripts/pace/plot_trajectory.py#L138)

### 开放决策与建议（待 Specify 确认）

- 建议兼容上述两种有证据的配对 v2 表示：旧双时钟必须相等且匹配任务，历史后端/求解器只按可核实的标识归一化。优先保留候选原物理语义；遇到跨后端、求解器无法确认、时步/延迟模式冲突或无法证明配对的旧均值时，建议说明差异并停止。支持范围与拒绝条件待批准。 [设置写入](../../scripts/pace/fit.py#L103) · [后端写入差异](../../src/pace_sim2real/optim/cma_es.py#L377)
- 建议文件参考沿用任务声明的列顺序与时间解释；指定独立实测时采用其首样本，无实测的扫频沿用采集初态。另存回放时采用独立输出路径；具体选项、文件内容以及训练同轨迹时如何标示留给 Specify。安装版 `isaaclab_tasks/utils/hydra.py:802–812` 已处理带常量的可选值之后紧跟 `key=value` 的情形；后续可覆盖裸 `--fit_result physics=...`，确认预设仍然生效。 [采集命令行](../../scripts/pace/data_collection.py#L341) · [原始文件契约](../../adr/0009-reference-semantics-in-fit-config.md)
- 后续若需要实验证据，可先经批准用已有配对记录做有界同轨迹回放，再用另一条有实测的轨迹检查预测 RMSE，另覆盖非零首轮速、纯腿无轮项与最新运行缺文件。两种现有结果均来自 Newton，PhysX 和独立预测质量没有本轮执行证据；本阶段未选择最终接口或验收阈值。

## CR4 · 任意记录关节子集的拟合与回放 · Research / Draft（2026-11-19）

**范围与证据。** Q1–Q6 及后续澄清要求同一任务支持其受控关节中的任意非空组合。位置或速度跟踪类型由任务现有分组决定。单关节、非对称组合、跨组组合和不按任务顺序排列的文件均在范围内。X5 的四个输入是例子。以下是当前工作树（HEAD `6a1d8c9`，保留本地配置改动）与已安装 Isaac Lab 3.0.0 源码的只读研究，方案和实验均待审批。[需求记录](requirements.md#cr4-explore-结论q1q6-已确认) · [Issue #4](https://github.com/MrCCaesar/pace-sim2real/issues/4)

### 已确认的事实与边界

1. **同一套分组现在兼任三种职责。** `resolve_joint_groups` 要求位置组非空，并兼容只声明 `joint_order` 的历史纯位置任务。`resolve_action_mapping` 验证每个动作项恰好覆盖任务分组，分开返回 articulation 关节 ID 和 ActionManager 列。`load_reference_data` 又要求配置声明的文件列序等于这套分组，强制存在两项位置字段。直接把任务分组缩成文件宽度，会在完整环境上触发覆盖错误。拟合和回放还各自检查执行器的每列必须在所给关节列表中恰好出现一次。[分组与动作映射](../../src/pace_sim2real/utils/collection_contracts.py#L46) · [文件加载](../../src/pace_sim2real/utils/collection_contracts.py#L127) · [拟合执行器覆盖](../../src/pace_sim2real/optim/cma_es.py#L380) · [回放执行器覆盖](../../scripts/pace/data_collection.py#L170)
2. **文件能验证结构，列归属依赖用户声明。** 位置组用 `dof_pos/des_dof_pos`（rad），速度组用 `dof_vel/des_dof_vel`（rad/s），共用 `time`。现有加载器会检查字段成对、有限值、各列样本数和时间间隔。若两个等宽文件互换同类关节，如髋和大腿，数值及形状本身无法证实操作者给出的名称；即使只有一列也一样。独立轨迹应逐组核对与拟合结果的**名称集合**，再按该文件声明的顺序重排。只改变顺序可以精确对齐，改变成员或跟踪类型应报错。用户已选择配置声明，结果保存解析后的名称有助于复核。现有 X5 数据目录内 6 个文件经只读张量形状检查均为 8000 帧、12 个位置和 4 个速度通道。裁列可以检查映射；若原采集中其余关节同时扫频，裁列后的数据不能证明在恒定保持工况下的物理响应。[数据契约](../../src/pace_sim2real/utils/collection_contracts.py#L133) · [ADR 0009](../../adr/0009-reference-semantics-in-fit-config.md) · [X5 数据目录](../../data/Isaac-Pace-Sevnce-X5-v0)
3. **纯速度需要贯通整个流程。** 拟合入口从位置首帧取初态，CMA 构造和 `tell` 从位置数据确定宽度或批次；`evolve` 无条件用位置均方初始化分数和权重。位置宽度为零时会得到非有限评分。最佳结果、终端、TensorBoard 还会无条件生成位置响应或位置误差。离线重算和画图已按非空分组迭代，但读取器仍要求至少一个位置关节，回放入口也总是访问、输出位置数据。数据可以自然地只提供有效组的字段对，拟合损失仅对有效组按现有尺度求均方、按有效权重归一化。缺失组不产生误差、偏置或图，不应将其当作零误差。[拟合入口](../../scripts/pace/fit.py#L211) · [CMA 初始化](../../src/pace_sim2real/optim/cma_es.py#L56) · [评分](../../src/pace_sim2real/optim/cma_es.py#L181) · [日志及配对结果](../../src/pace_sim2real/optim/cma_es.py#L263) · [离线读取和绘图](../../scripts/pace/plot_trajectory.py#L102) · [回放](../../scripts/pace/data_collection.py#L131) · [ADR 0007](../../adr/0007-scaled-mixed-response-objective.md)
4. **逐关节写入和整组延迟的粒度不同。** 已安装的 Newton、Isaac Sim PhysX、OVPhysX 均提供带 `joint_ids` 的转子惯量和摩擦写入接口（黏性摩擦通过同一摩擦接口写）。Newton 只使用单一干摩擦量，PhysX 可按原配置使用摩擦比例。PACE 的偏置更新要求完整的「环境数 × 此执行器关节数」矩阵，延迟按环境设置，作用于该执行器缓冲的所有通道；复位会清空历史。当前 X5 的一个 PACE 驱动覆盖 16 个关节，初始编码器偏置为零。旧拟合从全零构造偏置矩阵，固定采集路径还另有 0.05 rad 等常量，两者均不能代表任意任务加载后的未选关节基线。[Newton 写入](https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab_newton/isaaclab_newton/assets/articulation/articulation.py#L1973-L2064) · [Isaac Sim PhysX 写入](https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab_physx/isaaclab_physx/assets/articulation/articulation.py#L1786-L1905) · [OVPhysX 写入](https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab_ov/isaaclab_ov/assets/articulation/articulation.py#L1850-L1985) · [PACE 驱动](../../src/pace_sim2real/utils/pace_actuator.py#L40) · [X5 驱动](../../src/pace_sim2real/tasks/manager_based/pace/sevnce_pace_env_cfg.py#L18) · [固定采集常量](../../src/pace_sim2real/utils/fit_replay.py#L26)

### 可行方案、代价与建议（Proposed）

| 思路 | 从采集工况到结果的影响 |
| --- | --- |
| 完整任务分组控制机器人，另按文件声明选出辨识关节 | 保留完整动作覆盖；已记录列填入对应动作列，其余列每帧填入配置的恒定目标。可在步循环外一次打包，按选中名称提取响应、参数边界和尺度。每个关节的机械参数只写选中 ID；在完整驱动基线偏置上覆盖选中的位置通道，并向约定的完整执行器组写共享延迟。推荐此方向，改动可集中在现有配置、契约、拟合器及结果读写入口。[动作预打包](../../src/pace_sim2real/utils/collection_contracts.py#L100) · [拟合循环](../../scripts/pace/fit.py#L222) · [参数写入](../../src/pace_sim2real/optim/cma_es.py#L399) |
| 保留完整参数向量，将未记录变量固定并对误差加掩码 | 现有 CMA 能剔除上下界相等的变量。要符合 Q1/Q4，仍需获得每个环境加载后的精确默认值，避免全量回写改变现状，另行过滤日志、参数名、响应和回放。给未观测通道补零或加零权重也会污染组均值、分母或初态。此路线可实现，但需要维护更多完整向量与子集间的转换。[固定边界与参数恢复](../../src/pace_sim2real/optim/cma_es.py#L129) · [评分](../../src/pace_sim2real/optim/cma_es.py#L221) · [结果写入](../../src/pace_sim2real/optim/cma_es.py#L319) |
| 按实验拆分任务、动作或执行器 | 简单缩减覆盖会遗漏未记录关节的控制，拆开原驱动也会改变延迟作用范围；为任意组合复制任务没有必要，且不满足本次复用同一任务的要求。[覆盖校验](../../src/pace_sim2real/utils/collection_contracts.py#L65) · [X5 动作与分组](../../src/pace_sim2real/tasks/manager_based/pace/sevnce_pace_env_cfg.py#L43) · [Q2、Q5](requirements.md#cr4-explore-结论q1q6-已确认) |

按推荐方向，需要区分文件的组内列、完整任务中按跟踪类型排列的关节、articulation ID、动作列、执行器组内列和结果参数名。可在启动时按名称解析，将重复、不存在、错组和保持目标覆盖缺漏或与已记录关节重叠的声明在写参数前报告。一次排序不能同时用作上述所有索引。独立验证文件可以采用与训练文件不同的组内顺序，误差计算、初态、命令及绘图必须采取同一对齐。现有命名参数读取器已能按种类和关节名重排。[动作/测量索引](../../src/pace_sim2real/utils/collection_contracts.py#L65) · [命名参数](../../src/pace_sim2real/utils/fit_replay.py#L106) · [动作顺序回归样例](../../tests/test_mixed_collection_fit.py#L37)

**参数维度。** 设已记录位置关节数为 P、速度关节数为 V，J=P+V>0。沿用现有布局，基础向量宽度为 3J+P+1，启用 PhysX 独立摩擦比例时再加 J。分别代表三种机械量、位置偏置和一个共享延迟。等值上下界会继续缩减实际参与搜索的自由变量数。下表是举例，不限制任务、名称或组合。全量参数边界须按“参数种类、任务关节名”逐块抽取，不能简单截取前若干行；已有列表形式的误差尺度也需按原关节名投影，标量可继续广播。先按后端处理完整组的比例块，再提取选中行，可避免延迟行错位。[参数布局及活动维度](../../src/pace_sim2real/optim/cma_es.py#L84) · [任务对摩擦比例的处理](../../src/pace_sim2real/tasks/manager_based/pace/pace_sim2real_env_cfg.py#L206) · [X5 边界](../../src/pace_sim2real/tasks/manager_based/pace/sevnce_pace_env_cfg.py#L73) · [ADR 0008](../../adr/0008-canonical-joint-groups-and-layout.md)

| 记录关节示例 | P | V | 基础参数数 | 启用比例时 |
| --- | ---: | ---: | ---: | ---: |
| X5 四髋或四大腿（两种不同文件） | 4 | 0 | 17 | 21 |
| X5 四小腿和四轮 | 4 | 4 | 29 | 37 |
| X5 四轮 | 0 | 4 | 13 | 17 |
| 任一位置关节 / 任一速度关节 | 1 / 0 | 0 / 1 | 5 / 4 | 6 / 5 |
| 任意一个位置关节和两个速度关节 | 1 | 2 | 11 | 14 |

**回放及版本。** 当前配对 v2 记录有组名、具名参数、候选身份和同一次评估的响应。回放仅接受当前单一 `settings.dt` 形式并核验后端、求解器、偏置和延迟模式，旧双时步 v2 已由 CR3 明确排除。对既有有效全量结果，可沿用原全量语义。对子集结果，一条路径是继续使用 v2 并为新写入结果增加可区分范围的设置；另一条路径是升级子集记录版本并保留独立的现行 v2 读路径。前者改动较少，但旧离线读取器可能将部分新结果当作完整记录，旧回放读取器则要求与任务分组严格相等；后者明确隔离语义，需同步更新写入器和所有读取器。两种方案都应只报告选中关节的配对参数、响应和有效组指标，并记录足以核对的完整控制范围、恒定目标、列声明和延迟作用范围。新记录与回放任务工况冲突时的处理、版本号及字段留待 Specify。已有不配对均值不能用作物理回放输入。[配对结果](../../src/pace_sim2real/optim/cma_es.py#L319) · [回放兼容性](../../src/pace_sim2real/utils/fit_replay.py#L35) · [绘图读取器](../../scripts/pace/plot_trajectory.py#L69) · [CR3 已批准契约](spec.md#q4q6--已确认) · [ADR 0010](../../adr/0010-paired-evaluated-fit-results.md)

**回放入口范围。** 文件轨迹已提供被记录关节的期望值，可同拟合复用完整动作组装、选中响应及名称核对。生成扫频路径则写死 12 个位置系数和 4 个速度系数，直接以选中数调用会造成形状错误，某些可广播形状也无法保证名称对应。对已有支持的完整任务，可按其原有通道生成后抽取选中列，再对其余列发保持目标。若还要求为任意新任务生成扫频，必须先有该任务逐关节的幅度、中心与方向依据，不能按 X5 关节名猜测。是否扩展扫频配置与任意子集文件回放的可行性是两个不同问题。[生成与文件分支](../../scripts/pace/data_collection.py#L125) · [扫频系数](../../scripts/pace/data_collection.py#L284) · [采集输出](../../scripts/pace/data_collection.py#L398)

### 假设、开放决策与可选检验

- **工况与初态。** 未记录关节的恒定目标在整个运行期间都应发送。位置控制反馈使用 q−b，有非零默认偏置时，同一数值用作物理初始角度或编码器坐标目标会导致不同的启动误差。速度保持也可能非零。应明确未记录关节的首帧物理状态从任务初态取得，还是依保持工况建立，以及用什么工况核对独立回放。已记录通道沿用文件首帧实测位置加候选偏置、首帧实测速率。仿真能保存默认参数并不证明真实采集工况和仿真完全吻合。[现有初态](../../src/pace_sim2real/optim/cma_es.py#L410) · [偏置物理语义](../../adr/0005-unified-feedback-encoder-bias.md)
- **多执行器。** X5 的单组覆盖边界已经明确。若任务含多个驱动，共享候选必须覆盖所涉执行器的所有关节；若某个驱动完全没有授予辨识的通道，这个驱动是否也使用同一延迟，需明确再实现。两种规则在 X5 上相同，单组测试无法判别。需在写入前校验适用组的覆盖、模式和延迟容量，并在每轮从同一份任务基线组装偏置，防止候选或轮次间串值。[按组写入](../../src/pace_sim2real/optim/cma_es.py#L380) · [延迟 API](../../src/pace_sim2real/utils/pace_actuator.py#L79)
- **可选检验，未执行。** 先用 CPU 合成名称和可手算的互异数值，覆盖单位置、单速度、非对称乱序混合、原有纯位置/全混合、两组均空和错组/重复声明；分别核对命令、参数行、误差、事件标签、配对结果与独立回放重排。若需要确认后端行为，可经另行批准后逐个后端串行运行无窗口、2 个环境、短轨迹和 1 代；为未选关节设置非零且可区分的任务默认值，对照所选参数生效、未选参数保持、整组延迟及各状态/命令。短程结果只能检验软件行为，不能验证物理辨识质量。现有测试提供全组回归参照。[已有误差与尺度测试](../../tests/test_mixed_collection_fit.py#L171) · [已有执行器覆盖测试](../../tests/test_mixed_collection_fit.py#L593) · [已有回放测试](../../tests/test_fit_replay.py#L166)

本阶段未运行 CR4 实验、仿真或拟合。具体配置语法、版本与兼容策略、初态及多驱动约定留给获准后的 Specify。

## CR5 · X5 离线测量滤波 · Research（Draft）

**已确认的输入与约束。** 样例按 400 Hz 等间隔采集，测量矩阵按行存放 8000 个时刻，按列存放 12 路腿位置或 4 路轮速。因此逐关节滤波对应时间轴 `axis=0`。直接沿 SciPy 的默认末轴处理会把不同关节当成连续样本。输出须保留全部时间行，维持测量张量的原始形状、dtype 和列序，逐元素保留时间、期望指令，并写入独立文件。拟合以首帧测量建立腿位置和轮速初态，首帧变化会传入后续仿真。[CR5-R1–R4](requirements.md#cr5--离线采集数据滤波--explore需求已确认) · [拟合初态约定](../../adr/0005-unified-feedback-encoder-bias.md) · [SciPy 1.17.0 的 SOS 时间轴与返回值](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.signal.sosfiltfilt.html)

### 候选方法和适用条件（均未选为默认）

| 方法 | 有效频带内的幅值与时差 | 有限记录上的代价 |
| --- | --- | --- |
| Butterworth 低通，二阶节（SOS）前后向各一次 | 对理想稳态分量，合成响应为单程幅频响应的平方，通带零相移。可用通带损失与阻带衰减约束带内幅值。SOS 形式降低高阶多项式系数的数值风险。 | 需要未来样本。端点延拓影响首尾，短记录可能无法容纳指定延拓长度。[butter](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.signal.butter.html) · [filtfilt](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.signal.filtfilt.html) · [sosfiltfilt](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.signal.sosfiltfilt.html) |
| 同一 Butterworth 单程因果滤波 | 单程幅值衰减较小，但通常增加随频率变化的群延迟。仅滤测量时，新增延迟会混入测量相对指令的时差，统一平移若干样本不能校正所有扫频频率。 | 可逐样本处理，起始过渡取决于初始滤波状态。CR5 已允许离线读取整段，实时性没有额外收益。[sosfilt](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.signal.sosfilt.html) · [SciPy 对照示例](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.signal.sosfiltfilt.html) |
| 居中对称 FIR 低通 / Savitzky–Golay 平滑 | 奇数长度对称 FIR 居中一次可消除其固定群延迟，在增益为正的通带内保持相位。窗函数 FIR 可按过渡带设计；`firwin` 标量截止为约半幅点。SG 以局部多项式保留平滑趋势，须从窗口长度、阶数对应的频响另行核对 10 Hz 幅值与阻带衰减。 | 长度为 L 的奇数窗需要前后各 (L−1)/2 帧。两端缺少完整窗口，SG 的 `interp` 模式用单侧窗口拟合多项式估计端部。[firwin](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.signal.firwin.html) · [savgol_filter](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.signal.savgol_filter.html) |

**通带与截止的解析示例。** 400 Hz 采样的奈奎斯特频率为 200 Hz。若将 Butterworth 单程临界频率设为 10 Hz，稳态 10 Hz 正弦的幅值比例为 1/√2，前后向合成为 1/2，即约 −6.02 dB。此例说明即使相位为零，扫频上端仍可损失一半幅值。若把 10 Hz 作为通带上限，可另选更高的阻带起点，并根据允许的通带损失与最低阻带衰减求阶数和单程临界频率。前后向的 dB 衰减是单程的两倍，传给单程设计器的两项 dB 指标均应折半。上述数值仅为解析说明。[butter 临界频率定义](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.signal.butter.html) · [buttord 通带和阻带指标](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.signal.buttord.html)

**假设与边界。** 低通方案的前提是需要压制的噪声有足够能量位于保留频带以上。带内噪声与同频真实响应会受到相同增益。有限长扫频的峰值和估计出的时差还受频率成分重新加权、首尾延拓及瞬态影响。SciPy 的 `sosfiltfilt` 默认使用奇对称延拓，文档要求指定的 `padlen` 小于时间轴长度减一；满足长度条件仅说明该设置可用。保留全部帧时，适合分别核对首帧、末端扫频和记录内部。以上未经过样例滤波验证。[sosfiltfilt 端点参数](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.signal.sosfiltfilt.html) · [filtfilt 端点瞬态说明](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.signal.filtfilt.html)

**建议与待决问题。** 建议优先评估 SOS 前后向低通。Specify 需确认允许的 0.1–10 Hz 幅值损失、目标阻带及抑制量、允许的时差偏移与端点误差，再确定截止、阶数和命令行契约。若另行批准小型实验，可在有干净参考、已知延迟和带外扰动的信号上分别检查带内幅值、延迟误差（样本或毫秒）和干扰衰减，并检查逐列独立与首尾误差。在现有带噪记录上只能观察滤波前后的变化，真实响应误差需有独立参考。本轮仅核对资料，未运行候选滤波或生成数据。

**与现有代码衔接。** 当前环境和锁文件的 SciPy 版本为 1.17.0。拟合加载器会转换测量精度并派生 `original_time` 字段，适合用来验证输出能否被拟合读取。为了满足 CR5-R2，写出时宜以原始字典为基础，仅替换已存在的测量张量，并保留其原始 dtype。计算采样率前宜核对输入时间间隔是否均匀，400 Hz 是本样例的实测值。[依赖版本](../../uv.lock#L5392) · [拟合数据加载器](../../src/pace_sim2real/utils/collection_contracts.py#L198) · [首帧初始化](../../scripts/pace/fit.py#L237)

**拟议的两项临时 CPU 实验（待批准）。**

1. 构造含已知延迟、已知带内幅值和可重复噪声的多列信号。对少量阶数和截止频率，逐列对照干净响应，量化通带幅值损失、时差变化和降噪幅度，分开报告首尾和中段。
2. 在 X5 原始记录的副本上应用候选设置，逐关节比较带外能量、信号足够强处的带内幅值和相位，以及首帧位置（rad）和速度（rad/s）的改变量。检查原始文件、时间和指令完整性、输出结构与拟合加载兼容性。只在临时目录写出实验数据，无须启动仿真。样例缺少无噪声测量基准，指令和测量之间的跟踪误差包含真实动力学差异，不能当作噪声误差。

### CR5 临时实验结果（Research，已执行）

用户在 Research 阶段明确批准执行上述两项实验。使用 SciPy 1.17.0、PyTorch 2.11.0，在 CPU 上按时间轴用 Butterworth SOS 前后向滤波，采用 SciPy 默认奇对称端点延拓。以下频率均为单程截止频率，阶数为单程阶数。本次命令为 `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python /tmp/pace-cr5-dRGuxMbm/trial.py > /tmp/pace-cr5-dRGuxMbm/results.txt`，退出码 0。脚本、逐关节输出及四份临时样例均位于该临时目录。

**实验一，已知真值。** 400 Hz 采样，时长 80 s，五列分别为 0.1、1、4、8、10 Hz 的单位幅值正弦，共同延迟 10 ms。每列叠加标准差 0.12 的独立高斯噪声（NumPy 默认随机数生成器，种子 42）和幅值 0.15、相位按列错开的 70 Hz 扰动。用无噪声副本测量增益；对含噪结果，按全部通道统计相对干净响应的 RMSE。中段取中央 60 s，首尾取最前及最后各 0.25 s。相位由中央 60 s 的正弦投影求得。各次多列处理与单列逐一处理结果逐元素一致。

| 单程设置 | 10 Hz 幅值保留 | 中段 RMSE | 首尾 RMSE |
| --- | ---: | ---: | ---: |
| 原始含噪输入 | — | 0.16079 | 0.16222 |
| 四阶，10 Hz | 50.00% | 0.16652 | 0.16120 |
| 二阶，20 Hz | 94.25% | 0.03980 | 0.04299 |
| 四阶，20 Hz | 99.63% | 0.03580 | 0.04327 |
| 四阶，25 Hz | 99.94% | 0.04009 | 0.04588 |

四阶 20 Hz 时，滤波前后五个频点的相位折算时差最多改变 0.0165 ms。相对于已知的 10 ms 延迟，滤后估计误差按频率递增分别为 −1.972、+0.240、+0.037、+0.027、−0.008 ms；在低频，即使很小的相位误差也能折算成毫秒级差异。上述结果来自一次固定噪声实现。

**实验二，真实 X5 记录。** 复制需求指定的 8000 帧 X5 文件，从时间戳确认均匀采样率为 400 Hz。对每列去均值、加 Hann 窗后求整段频谱。按列比较滤前滤后 ≥30 Hz 的累计能量；另在 0.1–10 Hz 内，仅取该列指令和原始测量的幅值分别达到各自带内峰值 10% 的频点。实际入选频点分布在 1.15–8.95 Hz，各列覆盖范围不同。用滤后与滤前测量的复谱比计算幅值变化及相位折算时差；两者共用原始指令。此指标反映整段加窗信号的变化，无法推断单帧延迟或完整扫频端点的响应。

| 单程设置 | 16 列中 ≥30 Hz 能量降幅范围 | 入选频点最大相对幅值变化 | 最大相位折算时差变化 | 末帧轮速最大绝对变化 |
| --- | ---: | ---: | ---: | ---: |
| 四阶，10 Hz | 96.05–97.34 dB | 30.03% | 0.575 ms | 2.326 rad/s |
| 二阶，20 Hz | 30.83–31.92 dB | 3.84% | 0.040 ms | 0.175 rad/s |
| 四阶，20 Hz | 47.66–48.94 dB | 0.160% | 0.00281 ms | 0.354 rad/s |
| 四阶，25 Hz | 32.80–34.04 dB | 0.026% | 0.00046 ms | 0.0661 rad/s |

四阶 20 Hz 时，首帧腿位置与轮速的最大绝对改变量分别为 0.00225 rad 和 0.01093 rad/s，末帧分别为 0.00986 rad 和 0.354 rad/s。四阶 25 Hz 的首帧改变量分别为 0.00305 rad 和 0.02250 rad/s，故提高截止频率在此例中主要改善了末帧。每份临时输出均重新读盘，验证五个字段及顺序、各张量形状、数据类型和有限性，并验证时间及两组指令逐元素相等。四份文件均通过 `fit.py` 使用的 `load_reference_data`（X5 完整关节顺序、严格时间模式、dt = 0.0025 s）。原始文件与工作副本在前后校验中 SHA-256 均为 `8ab1ca9e3a430c0b4ad7fa951cf53dbc352d8e45263b6ee085bc300aa25732d8`。

**建议与边界。** 当前样例可将四阶 20 Hz 作为默认候选；它在合成实验中取得最低中段 RMSE，同时保留 99.63% 的 10 Hz 真值幅值。若更看重本次 X5 扫频的末端轮速，四阶 25 Hz 是有实测依据的另一选择。真实数据的高频能量包含噪声和可能的真实动力学成分，尚无干净真值，也未执行拟合或仿真。默认设置、可配参数与验收阈值留待 Specify 确认。

## CR6 滤波诊断与可视化研究

**状态：Draft。已确认事实。** CR6 按本次记录的位置组、速度组分别计算五项指标。CR5 真实记录测试逐列去整段均值、乘周期 Hann 窗、沿时间轴计算实数 FFT。通带比较采用 0.1–10 Hz 内指令和滤前测量分别达到各自带内峰值 10% 的频点；高频比较直接累计 ≥30 Hz 频点的模平方。现有真实记录测试检查幅值、能量和端点，时差另在合成正弦测试中检查。[CR6 需求](requirements.md#q4q6-已确认的指标含义) · [CR5 回归测试](../../tests/test_filter_chirp_data.py)

**相位和时差。** 设同一关节、同一频点的指令、滤前、滤后复谱依次为 C、R、F。两次相对指令的相位分别来自 R·conj(C) 和 F·conj(C)。由复数乘法可得，二者相位差的主值为 arg(F·conj(R))，因为公共因子 |C|² 为正。建议在指令和两次测量均可靠的正频点上，取 |arg(F·conj(R))| × 1000/(2πf) 的最大值（ms）。这样可处理跨越 ±π 的两次相位，避免把很小的差算作近一整周。结果具有 1/f 周期歧义，仅能表示按最短相位差折算的变化；无法由单频点恢复绝对物理延迟。低频会放大相位误差。展开相位并拟合斜率可研究近似恒定延迟，但需要连续激励频带和模型假设。[NumPy 相角定义及零幅值行为](https://numpy.org/doc/stable/reference/generated/numpy.angle.html)

**有效频点与覆盖。** 建议以 CR5 逐关节指令和滤前幅值规则为基础，先确认诊断频带内有实际频点、两个峰值都超过数值底限，再应用相对门槛。否则常值通道去均值后可能以零门槛选中全部频点，接近舍入误差的信号也可能被误判为激励。幅值指标应保留滤后幅值为零的有效点（衰减 100%）；相位指标还须排除滤后幅值为零或过弱的点。若只相对于滤后自身微小峰值设阈值，仍会选中已接近数值噪声的相位。宜分别报告两个指标的有效覆盖。频点间隔为 fs/N，频带应取与实际频轴的交集。偶数 N 的 Nyquist 系数为实数，不宜估计连续相位时差；奇数 N 的最高频点低于 fs/2。短记录可能缺少通带频点或 ≥30 Hz 频点。0.1–10 Hz 来自 CR5 的扫频工况，其他记录的激励频带、弱信号底限及阈值仍待确定。[NumPy 实数 FFT 的奇偶端点](https://numpy.org/doc/stable/reference/generated/numpy.fft.rfft.html) · [CR5 频带和活动频点](../../tests/test_filter_chirp_data.py)

**能量与频谱图方案。** 延续 CR5 可逐关节报告 10 log₁₀(Σ|R|²/Σ|F|²)，求和覆盖全部 ≥30 Hz 实际频点。标准单边功率谱密度（PSD）会合并正负频率功率，内部点加倍，直流和偶数长度的 Nyquist 点权重为一。如果高频带同时含 Nyquist 和内部频点，该权重会改变比值；单一常数归一化才会完全抵消。若希望直接比较 CR5，建议保留上述求和，并在绘图时单独标明所画的量。可复用整段加窗复谱绘制滤前单边幅度谱，幅度按窗系数之和归一，内部点加倍，位置和速度分标 rad、rad/s。峰值读数受泄漏和扫频持续时间影响。也可画 Welch PSD（rad²/Hz 或 (rad/s)²/Hz）显示宽带噪声，分段平均可减小随机起伏，但短段降低频率分辨力，且功率谱不保留相位。整段法可在同一频率栅格上计算相位与幅值、观察低频。图中频谱宜覆盖实际可观测频率，以便查看 ≥30 Hz 成分。[SciPy 单边功率与标度](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.signal.periodogram.html) · [SciPy Welch 分段与平均](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.signal.welch.html)

**可报告性建议与待决事项。** 滤前峰峰值为零时，该列变化率无基准；组内滤前跟踪 RMSE 为零时，该组比例无基准。高频带为空、两侧能量皆零时，降幅不可估；若仅滤后严格为零且滤前为正，理论降幅为 +∞ dB，反向为 −∞ dB。建议明确区别严格零和低于可分辨底限，按指标注明不可用原因及有效关节数，防止将部分关节的极值当作全组结果。分母规约、部分覆盖时是否给出极值、显示频谱的标度和诊断带宽待 Specify 决定。本轮依据文档及测试源码，未运行实验。

### 时域指标、可视化与验证建议

**时域指标的分组。** 用原始张量和实际写入输出文件的测量值计算，统一提升为双精度，输出 dtype 的舍入因此也反映在诊断里。对同一组的每个通道分别取全段最大值减最小值，再使用各自的滤前峰峰值计算相对变化，最后取最大绝对百分比。这个指标会响应单个尖峰，符合 Q4 关心整段运动范围的定义。Q6 则以期望为参考，对该组全部时间和列的残差先求平方均值并开方，分别得到滤前、滤后跟踪 RMSE，再求百分比；逐关节先求比值再平均会改变关节权重。降低跟踪 RMSE 既可能来自去除噪声，也可能来自削弱真实动态响应，需与有效频点的增益和时差共同阅读。[Q4–Q6](requirements.md#q4q6-已确认的指标含义) · [NumPy 峰峰值定义](https://numpy.org/doc/stable/reference/generated/numpy.ptp.html) · [保存时的数据类型转换](../../scripts/pace/filter_chirp_data.py#L62)

**扫频范围的来源。** 当前 X5 采集配置为 0.1–4 Hz，验收样例为 0.1–10 Hz。采集文件保存时间、测量与指令，无法从字段读取当次配置的频带。建议让用户能声明分析频带，并打印实际入选频点的范围；当前任务配置和文件名均不足以验证历史采集条件。[X5 采集配置](../../config/x5_collection.toml#L3) · [采集文件字段](../../scripts/pace/mujoco_collection.py#L308)

**交互图可行性。** 同一关节的三条时域曲线可直接共享文件的秒时间轴，并以 rad 或 rad/s 标注。输入文件只有列序；独立 CLI 可用“位置第 1 列”“速度第 1 列”等稳定标签对应指标和图形。仓库采集绘图已在绘图分支加载 Matplotlib、创建图后统一显示；同一方式支持关闭绘图时在无显示器环境打印报告。图形布局、纵轴口径待 Specify。[现有绘图入口](../../scripts/pace/data_collection.py#L414) · [SciPy 频谱标度](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.signal.periodogram.html) · [Matplotlib 交互显示](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.show.html)

**可选的两项临时 CPU 实验（待批准）。**

1. 使用研究中同一 SHA-256 的 X5 实测文件，临时目录内比较四阶 20 Hz 和 25 Hz 的五项诊断，分别记录位置和速度组的值与有效频率覆盖。用原 CR5 结果交叉核对频域指标，检查三条时间曲线和原始频谱的数据来源与单位。
2. 用可手算的短记录验证不同关节的增益、已知相位变化、常量列、原始跟踪误差为零、无有效频点、采样频率使 ≥30 Hz 为空或只余奈奎斯特点等情况。该实验仅用于测试估计方法。运行时报告始终取自当前实测文件。

本轮核对的是现有代码、依赖版本（NumPy 2.5.4、SciPy 1.17.0、Matplotlib 3.10.8）及一手文档。以上新诊断尚未在 X5 上运行；默认频带、适用性判据和不可报告时的呈现留待确认。

### CR6 两项临时 CPU 实验（已执行）

用户批准后，分别执行以下命令，两次退出码均为 0。临时脚本与两份日志位于 `/tmp/pace-cr6-research-cimIbTBu`。实验一从仓库根目录调用现有滤波 CLI，所有计算、渲染及输出均在 CPU 上完成。原始文件和临时输入副本的 SHA-256 均为 `8ab1ca9e3a430c0b4ad7fa951cf53dbc352d8e45263b6ee085bc300aa25732d8`。

```bash
p=/tmp/pace-cr6-research-cimIbTBu
export MPLBACKEND=Agg OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
MPLCONFIGDIR="$p/mpl-x5" .venv/bin/python "$p/trial.py" x5 > "$p/x5.txt"
MPLCONFIGDIR="$p/mpl-edges" .venv/bin/python "$p/trial.py" edges > "$p/edges.txt"
```

**实验一，真实 X5。** 8000 帧，400 Hz；单程四阶，分别设置 20、25 Hz。诊断读取实际写出的测量张量，按位置组和速度组独立汇总。频谱使用全段去均值、周期 Hann 窗、实数 FFT。沿用 CR5 的 0.1–10 Hz 分析带、逐列指令和滤前谱分别达到各自带内峰值 10% 的条件，以及 ≥30 Hz FFT 系数模平方求和口径。相位取滤后谱乘滤前谱共轭的主值，另以两者各自相对指令的相位差核对。

| 截止与测量组 | 峰峰值最大变化 | 最大相位折算时差变化 | 滤后/滤前跟踪 RMSE | 有效频点最大幅值变化 | ≥30 Hz 最小能量降幅 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 20 Hz · 腿位置 | 29.0142% | 0.000880 ms | 99.3993% | 0.15919% | 47.659 dB |
| 20 Hz · 轮速 | 17.0088% | 0.002802 ms | 99.2187% | 0.15130% | 47.856 dB |
| 25 Hz · 腿位置 | 28.0478% | 0.000140 ms | 99.4235% | 0.02576% | 32.803 dB |
| 25 Hz · 轮速 | 15.8793% | 0.000453 ms | 99.2696% | 0.02448% | 32.991 dB |

两个截止设置均覆盖 12/12 个腿位置通道、4/4 个轮速通道。有效的“关节、频点”组合分别为 1643、613 个，两组各自的频率并集从 1.15 到 8.95 Hz，幅值与相位在本例覆盖相同。各组的整体极值与 CR5 既有频域结果在其报告精度内吻合。20 Hz 下，位置第 7 列峰峰值由 1.07117 降至 0.76038 rad，轮速第 4 列由 16.96754 降至 14.08157 rad/s。整段峰峰值取决于两个极值样本，带内谱幅只衡量选中成分，二者可以相差两个数量级。跟踪 RMSE 的参考为期望指令，本次结果无法区分各项变化中真实动态响应和测量噪声的贡献。

**图形检查。** 两种截止分别为全部 16 个关节生成图，在 Agg 画布上内存渲染，共 32 张。逐一核对三条时域曲线的横坐标与原时间张量相同、纵坐标分别来自期望指令、滤前测量和实际写出的滤后测量。逐列独立重算滤前单边幅值谱并对照所绘数据，横轴覆盖 0–200 Hz，位置和速度纵轴分别标记 rad 和 rad/s。实验没有写出图片；GUI 窗口交互未测。

**实验二，手算与退化输入。** 使用 256 点多列信号，分别检查下列情形，断言全部通过。

| 情形 | 观察结果 |
| --- | --- |
| 两列已知 8 Hz 正弦，滤前幅值分别为 1、2，构造的滤后幅值分别为 0.5、1.5，指令幅值分别为 2、4 | 最大峰峰值与 8 Hz 幅值变化均为 50%，时差为零（浮点精度内）。先合并全组残差再计算出的 RMSE 比例符合手算的 `100 × √(8.5/5)`%，本例超过 100%。 |
| 8 Hz 由 +179° 跨到 −179° | 最短相位变化 2°，折算为 0.694444 ms。 |
| 常量关节、混合有效与常量列、零跟踪误差、恒定指令及频带内无 FFT 栅格点 | 全常量且跟踪完全一致时五项均无值；混合组的相关极值只覆盖 1/2 列。滤前跟踪误差为零时比例无值；无指令激励时带内幅值和时差无值。 |
| 滤后带内分量完全消失或只余极弱残量 | 完全消失计 100% 幅值变化，两种情形的相位均判不可用。 |
| 50 Hz 采样；60 Hz 采样且记录长度为偶数 | 前者没有 ≥30 Hz 频点。后者仅有 30 Hz 奈奎斯特点，幅值减半对应 6.0206 dB 能量降幅，相位时差无值；滤后能量严格为零、原始能量显著时可区别报告正无穷。 |

**实验假设与未决项。** 为识别双精度舍入残差，临时脚本使用逐列的数值底限（谱幅参考为 `64 × ε64 × Hann窗系数和 × 该列原信号最大绝对值`），时差还要求滤后谱幅超过对应滤前谱幅的 `1e−8`；高频谱范数与按实际频点数折算的底限比较。判据仅用于探索可报告性，无法据此推断传感器的物理信噪比。Specify 仍需确认分析频带的声明方式、有效覆盖与无值的显示、弱信号门槛及精确零能量的处理。两项实验未修改生产脚本或回归测试。

## CR8 独立回放与部分关节采集

**Research · Draft。** 用户已确认普通采集仅激励选中关节，其余关节沿用部分拟合的保持目标。本节据仓库源码与现有测试分析可行性，本轮未运行测试或仿真。[CR8 需求](requirements.md#cr8-独立回放入口与部分关节采集explore--draft)

### 采集与回放的数值条件

| 已确认事实 | 对迁移与部分采集的影响 |
| --- | --- |
| `reference_groups` 分别解析两个记录组，保留列序，拒绝两组均空、重复、未知或跨组名称。动作管理器仍要求覆盖任务全部受控关节。 | 可用完整任务名称构造动作映射，将选中轨迹填到对应列，其他列填保持值；测量再按声明顺序从 articulation 取列。仅轮速时内部位置命令可以是 `[T,0]`，输出只需时间与期望、实测轮速。[分组与动作映射](../../src/pace_sim2real/utils/collection_contracts.py) · [保持指令展开](../../src/pace_sim2real/utils/subset_control.py) |
| 旧全量采集先生成全宽轨迹。部分回放的 `_named_chirp` 用固定名称表选列，只识别 X5 和纯腿 ANYmal。已注册的 X3mini 有 12 个同 ANYmal 命名的腿关节与 4 个 `*_WHEEL`，其原全量宽度适用现有数组；选择任一该型轮会被现有名称表拒绝。 | 可按受支持任务既有完整系数顺序生成，再按关节名投影。比如 X5 的 `RR_hip_joint` 应取负方向髋系数，放在文件第 1 列也不改变此系数。对缺少已知系数的关节不推测幅度或方向。收集入口只支持扫频，其报错不能建议已迁出的文件轨迹参数。[生成与投影](../../scripts/pace/data_collection.py) · [任务注册](../../src/pace_sim2real/tasks/manager_based/__init__.py) · [X5/X3mini 分组](../../src/pace_sim2real/tasks/manager_based/pace/sevnce_pace_env_cfg.py) |
| 旧普通采集给全部关节写入转子惯量 0.1、黏性摩擦 4.5、静摩擦 0.05、动摩擦 0.025，腿偏置 0.05 rad、轮偏置 0，组延迟 5 个物理步。Newton 用单一干摩擦，旧路径在两种摩擦值不同时警告；PhysX 写入两种系数。PACE 驱动刚建立时将延迟设为各自的 `max_delay`。 | 部分拟合只覆盖选中关节的机械参数与偏置，对含选中关节的整组写延迟；独立的未参与组保留任务延迟。同一 X5 单驱动组选一轮时，组内 16 个关节均受该组延迟影响。全量施加采集常数后再截取动作或输出，会改变未选中关节的反馈和耦合响应。[采集常数](../../src/pace_sim2real/utils/fit_replay.py) · [后端写入](../../scripts/pace/data_collection.py) · [执行器初值](../../src/pace_sim2real/utils/pace_actuator.py) · [整组延迟契约](../../adr/0012-participating-actuator-delay.md) |
| 现有部分控制在参数写入前读取任务默认状态与驱动偏置。保持腿每步跟踪“默认物理角减默认偏置”，首帧取默认物理角、零速；保持轮取默认角与默认速度。环境 reset 后还会清除改写延迟的驱动组历史。 | 选中腿生成扫频时以首个期望位置加偏置起步；文件回放使用首帧实测位置加偏置及首帧实测轮速。还须区分旧全量生成扫频将所有初速置零，而现有部分路径保留选中腿的任务默认初速。若配置了非零初速，合并初始化会改变首帧以后的响应；采集若直接调用部分控制，也会新增参与组 `reference_delay_mode` 一致性检查。[普通与文件初始化](../../scripts/pace/data_collection.py) · [部分控制与延迟缓冲](../../src/pace_sim2real/utils/subset_control.py) · [保持工况](../../adr/0011-held-joint-initial-state.md) |
| `collect_trajectory` 在每次 step **前**读仿真时钟和状态，落盘环境 0 的位置 `q−b`、原始轮速以及延迟前的期望值。它检查所有环境、所有关节及最后一步之后的状态，遇到终止、截断或时间异常会中断。 | 普通采集和回放可直接共用此循环；选列应只影响导出的关节，保留完整状态检查和现有原子保存。拟合加载器要求至少两帧，采集器当前允许一帧；后续端到端验证需使用至少两帧。[循环与保存](../../scripts/pace/data_collection.py) · [参考文件加载](../../src/pace_sim2real/utils/collection_contracts.py) |

**待确认的物理范围。** Q1 已确定保持指令，尚未明确部分采集给哪些关节写入上述采集常数。建议选中关节沿用采集常数，其余沿用任务机械参数及默认偏置，按参与的驱动组写入五步延迟。这与现有部分拟合的参数作用范围一致；另一种可行方式是沿用全机采集常数，同时按原任务基线构造保持动作。两者会改变未选中关节的实际状态和载荷，需在 Specify 中确定。[CR8 Q1](requirements.md#cr8-独立回放入口与部分关节采集explore--draft) · [部分控制写入](../../src/pace_sim2real/utils/subset_control.py)

**已有覆盖与验证建议。** 现有测试覆盖乱序 X5 扫频系数、两个驱动组的非零偏置与保持速度、文件回放和独立扫频。部分关节 CLI 集成用手工构造的参考张量开始拟合，尚未检验普通采集入口生成的子集文件。建议核对纯位置、纯速度及乱序混合采集的字段、全机动作、首帧和同配置加载，再对比全量默认采集迁移前后的时间、命令和测量。X3mini 轮系数可先做纯张量检验，避免把任务注册与真实仿真通过混为一谈。[回放测试](../../tests/test_fit_replay.py) · [映射、保持与采集测试](../../tests/test_mixed_collection_fit.py)

### 入口拆分与迁移范围

**Q3 交接更新。** 用户在研究完成后确认采用上文建议的参数作用范围，并批准进入 Specify。[已确认的作用范围](../../adr/0017-partial-collection-parameters.md)

研究基线为项目 `d4f33f2` 和本地 editable Isaac Lab `ae6330248`。虚拟环境发行包为 `isaaclab 45.1.0`、`isaaclab_tasks 30.1.3`、`isaaclab_rl 5.3.1`。下列生命周期与命令行结论取自项目锁定路径所指的本地源码。[项目依赖来源](../../pyproject.toml#L87)

| 操作 | 决定关节及轨迹的来源 | 需要保留的文件行为 |
| --- | --- | --- |
| 固定参数采集 | CR8 使用配置中的两个参考分组，按所选名称取得扫频目标 | 成功时原子替换任务的 `chirp_data.pt` |
| 用拟合结果生成扫频 | v3 使用结果中已辨识的名称，v2 使用任务完整分组。此路径不依赖参考文件列序 | 默认仅运行，显式另存才写入 |
| 用原文件或独立文件回放 | 文件按当前配置解释列序，与拟合结果按名称集合匹配，从首帧实测初始化 | 对有记录的组计算预测 RMSE；另存保护拟合结果、轨迹文件、默认与配置的采集数据，以及 X5 的原生 MuJoCo 文件 |

依据为[结果与分组选择](https://github.com/MrCCaesar/pace-sim2real/blob/d4f33f25558f4566ae64f0a08401bbd605db4f4c/scripts/pace/data_collection.py#L97)、[配对结果按名校验](../../src/pace_sim2real/utils/fit_replay.py#L117)、[写出及误差](https://github.com/MrCCaesar/pace-sim2real/blob/d4f33f25558f4566ae64f0a08401bbd605db4f4c/scripts/pace/data_collection.py#L177)和[原子保存](https://github.com/MrCCaesar/pace-sim2real/blob/d4f33f25558f4566ae64f0a08401bbd605db4f4c/scripts/pace/data_collection.py#L398)。完整任务控制分组、采集选择和回放结果分组应分别保留；若在公用启动流程中一律调用 `reference_groups`，会误拒原本允许参考配置为空的 v3 生成扫频。[已有回归场景](../../tests/test_fit_replay.py#L425)

**可行路径与代价。** 方案一由两个入口各自处理参数来源、文件检查和输出行为，复用仿真生命周期、扫频、物理写入与采样例程。模式分支较少，可分别验证两个入口。方案二保留一个带模式分支的完整运行器，在两个薄入口中选择模式。移动较少，但新采集的分组及默认写入仍与回放的保护分支耦合。建议方案一，同时保留尚未证明等价的初态路径。模块放置与签名留待 Specify。[架构提议](../../adr/0016-separate-replay-entry.md)

**启动顺序与废弃选项。** 项目先设置 Warp 的 `enable_backward`，再导入定义内核的模块。任务配置和路径保护在仿真前完成，后端相关的结果兼容检查在 launcher 解析后端之后执行。采样完成后先关闭环境，再在 launcher 上下文内落盘，以适配 Kit 的关闭行为。本机 `setup_preset_cli` 使用 `parse_known_args`，未知选项会随 Hydra 剩余项向下传递。旧入口验收应覆盖旧回放命令在仿真前失败、已有采集文件完整，同时合法的 `env.sim2real.*` 覆盖仍可用。[现有顺序](https://github.com/MrCCaesar/pace-sim2real/blob/d4f33f25558f4566ae64f0a08401bbd605db4f4c/scripts/pace/data_collection.py#L5) · [项目 CLI](https://github.com/MrCCaesar/pace-sim2real/blob/d4f33f25558f4566ae64f0a08401bbd605db4f4c/scripts/pace/data_collection.py#L525) · [本机参数解析](../../../IsaacLab/source/isaaclab_tasks/isaaclab_tasks/utils/hydra.py#L734) · [本机启动上下文](../../../IsaacLab/source/isaaclab/isaaclab/app/sim_launcher.py#L411)

**迁移清单。** README 和使用手册含旧回放命令；纯采集示例保留原入口。回放测试同时包含采集命令、回放命令、对旧脚本的函数导入，以及测试工况用的任务解析替换；需按用途迁移。混合采集测试通过文件路径加载采样函数，其启动参数用例目前仅覆盖采集和拟合。离线绘图使用已保存结果，可继续维持独立入口。历史阶段文档保留其当时的命令。[README](../../README.md#L36) · [使用手册](../../docs/usage.md#L154) · [回放及路径保护](../../tests/test_fit_replay.py#L199) · [部分关节启动测试](../../tests/test_fit_replay.py#L322) · [按名扫频测试](../../tests/test_fit_replay.py#L448) · [采样与 CLI 测试](../../tests/test_mixed_collection_fit.py#L674) · [离线入口](../../scripts/pace/plot_trajectory.py#L263)

**验收边界。** “同配置可直接拟合”要满足现有加载契约。采集允许一个控制步，拟合加载器至少要求两个样本，且拟合入口要求 `decimation=1`。建议用满足这些条件的子集文件验证采集 → 拟合 → 两种回放；另以普通全量采集作为数值基线。Research 只做源码、配置、既有测试与安装源的静态核对，本轮没有运行实验、测试或仿真。[采集时长](https://github.com/MrCCaesar/pace-sim2real/blob/d4f33f25558f4566ae64f0a08401bbd605db4f4c/scripts/pace/data_collection.py#L358) · [参考时间校验](../../src/pace_sim2real/utils/collection_contracts.py#L199) · [拟合前置条件](../../scripts/pace/fit.py#L67)

## CR7 具名关节 CSV 转换为拟合参考文件（Research · Draft）

**范围与证据。** 用户已批准 Q6、Q7 和 Research。此次核对给定 CSV、采集者的字段说明、项目代码和项目使用的 Isaac Lab 源码。以下兼容性结论来自静态核对，尚未运行转换、加载实验、拟合或仿真。[CR7 需求](requirements.md#具名宽表与任务配置explore--draft) · [Issue #4](https://github.com/MrCCaesar/pace-sim2real/issues/4) · [本地 Isaac Lab 依赖](../../pyproject.toml#L86)

### 样例、反馈与字段

全表有 77 列、10,000 个控制周期。按十进制读取 `time_s`，9,999 个相邻间隔均为 0.002 s。四轮的 `feedback_valid` 在 `seq=1,2` 均为 0，之后全部为 1，保留段的四列 `dq` 和四列 `dq_des` 均为有限数。按 Q6 裁剪后，`seq=3…10000` 留下 9,998 帧，对应原始时间 0.004…19.998 s。样例 SHA-256 为 `3e3adb9ed7505d4c9b107f065d23d1989b30b5afda3034103737e3f0d6dd42e1`。采集者注明数值为人工生成，能用于格式验收。[样例数据](../../data/Isaac-Pace-Sevnce-X5-v0/motor_sweep_simulated/data.csv) · [字段与时序说明](../../data/Isaac-Pace-Sevnce-X5-v0/motor_sweep_simulated/README.md)

同一行包含本周期目标和发令前最近的反馈，和拟合中先记录状态、再执行该行命令的顺序相容。转换只读取选中量的实测、目标、有效标志和公共时间。以全部记录关节都标记有效的首末帧界定保留段，可处理多个关节先后上线或下线。段内任一关节无效须按 Q6 报告帧与关节并终止。标记有效但必需测量为空、非数或无穷，是数据矛盾，建议报告原行、关节和字段；同样应检查保留段的目标值。标准库 `csv.reader` 支持引号，按 `newline=''` 打开时默认返回字符串，便于在映射列前识别重复表头和区分空白、数值零；未用的纳秒字段可以保持原精度。[采集格式](../../data/Isaac-Pace-Sevnce-X5-v0/motor_sweep_simulated/README.md) · [拟合采样顺序](../../scripts/pace/fit.py#L268) · [Python 3.12 CSV](https://docs.python.org/3.12/library/csv.html#csv.reader)

### 任务配置的可行读取路径

| 途径 | 能取得的配置及代价 |
| --- | --- |
| 从注册表加载默认环境配置 | 项目通过 `isaaclab.tasks` 注册任务。发现任务后，`load_cfg_from_registry(task, "env_cfg_entry_point")` 按 Gym ID 导入并实例化注册的 Python 配置类，可从 `env_cfg.sim2real`、`sim.dt`、`decimation` 取值。适合仅传 `--task` 的请求。仍依赖项目与 Isaac Lab 的 Python 安装。 [任务发现](../../../IsaacLab/source/isaaclab/isaaclab/cli/__init__.py#L43) · [项目入口](../../pyproject.toml#L27) · [注册 ID](../../src/pace_sim2real/tasks/manager_based/__init__.py#L7) · [注册配置解析](../../../IsaacLab/source/isaaclab_tasks/isaaclab_tasks/utils/parse_cfg.py#L69) |
| 使用拟合入口的配置解析 | `resolve_task_config(task, "", overrides=[])` 支持在启动 Kit 前解析配置。显式的覆盖项可用于与拟合相同的 Hydra 组合，空列表避免将转换器自身参数当作 Hydra 参数。这条路径适合需要解释预设或用户覆盖的场景。两条途径都可在 `launch_simulation` 和 `gym.make` 前取得所需配置。 [Isaac Lab 解析器](../../../IsaacLab/source/isaaclab_tasks/isaaclab_tasks/utils/hydra.py#L461) · [拟合入口顺序](../../scripts/pace/fit.py#L75) |

建议按指定任务的 `resolve_joint_groups` 取得完整的两组名称，再按任务顺序与表头中实际记录的关节取交集；额外出现的未知关节应指明名称。该函数还支持仅有 `joint_order` 的旧纯位置任务。直接维护另一份机器人名称表会产生第二份配置，按目录猜任务则会把此样例的 `LF_WHEEL` 等名称交给 X5。X3mini 的速度组为 `LF_WHEEL, RF_WHEEL, LH_WHEEL, RH_WHEEL`，X5 的速度组为 `FL_foot_joint, FR_foot_joint, RL_foot_joint, RR_foot_joint`。两者均与历史的 `foot/wheel` 规则一致。若其他任务的显式分组与该规则冲突，建议在 Specify 明确处理方式。[完整关节分组](../../src/pace_sim2real/utils/collection_contracts.py#L46) · [X5 与 X3mini](../../src/pace_sim2real/tasks/manager_based/pace/sevnce_pace_env_cfg.py#L121) · [旧纯位置配置](../../src/pace_sim2real/tasks/manager_based/pace/anymal_pace_env_cfg.py#L40)

### 拟合读取、周期和路径

- **文件内容。** `load_reference_data` 以 CPU、`weights_only=True` 读取张量字典。文件共用 `time[T]`，位置用 `q/q_des → dof_pos/des_dof_pos[T,L]`（rad），速度用 `dq/dq_des → dof_vel/des_dof_vel[T,W]`（rad/s）。按需求仅写有记录的组。加载要求张量是有限浮点数，信号转为 float32 后也须有限，且 `T ≥ 2`、时间严格递增。额外字段会被拒绝；`original_time` 是加载后的派生字段。样例预计只有 `time[9998]` 和一对 `[9998,4]` 速度张量。[加载器](../../src/pace_sim2real/utils/collection_contracts.py#L174) · [参考语义 ADR](../../adr/0009-reference-semantics-in-fit-config.md)
- **列序。** 拟合分别用 `reference_leg_order` 和 `reference_wheel_order` 解释数据，`None` 取任务全组，空列表表示该组无记录。形状只能校验列数，不能发现相同列数但名称错位。样例适用 X3mini 的 `reference_leg_order=[]` 和 `reference_wheel_order=[LF_WHEEL,RF_WHEEL,LH_WHEEL,RH_WHEEL]`；建议导出时打印两个分组，尤其显示缺席组的空列表。[声明解析](../../src/pace_sim2real/utils/collection_contracts.py#L65) · [任务默认值](../../src/pace_sim2real/tasks/manager_based/pace/pace_sim2real_env_cfg.py#L184)
- **固定周期不匹配。** Isaac Lab 控制周期是 `sim.dt × decimation`，当前拟合另要求 `decimation=1`。严格加载逐个比较 `time[i] - time[0]` 与 `i × dt`，容差为 `atol=1e-7 s, rtol=1e-5`。Q7 允许以原 `time_s` 导出，样例应提示观测 0.002 s（500 Hz）、任务默认 0.0025 s（400 Hz），以及严格拟合需 `env.sim.dt=0.002`、`decimation=1`。在此配置下，加载器有效时间从 0 开始并保留原始首帧 0.004 s。建议保存双精度时间以保留 CSV 秒值的有效精度。[控制周期](../../../IsaacLab/source/isaaclab/isaaclab/envs/manager_based_env.py#L295) · [两任务默认值](../../src/pace_sim2real/tasks/manager_based/pace/sevnce_pace_env_cfg.py#L208) · [拟合约束](../../scripts/pace/fit.py#L65) · [严格校验](../../src/pace_sim2real/utils/collection_contracts.py#L198)
- **非均匀时间。** 重复、倒退、非有限时间不符合现有加载条件。时间虽递增，若在拟用的固定网格上逐帧偏差超出容差，只改为平均或中位周期也不能保证严格拟合。建议将整段相对时间对固定网格核查，同时定位首个偏离帧；警告中区分“等间隔但任务周期不同”与“本记录含抖动或缺帧”。对于后一种，超容差时是否仍导出原时间由用户决定。`legacy_index` 会重建有效时刻，其适用前提是已知真实固定间隔的历史错误标签。[加载器两种模式](../../src/pace_sim2real/utils/collection_contracts.py#L210) · [时间 ADR](../../adr/0006-explicit-reference-time.md)
- **导出与拟合路径。** 转换结果按需求放在 CSV 旁，默认文件名暂按 `chirp_data.pt` 理解。拟合从项目 `data/<规范化任务名>/` 拼接 `env.sim2real.data_dir`。样例位于名称含 X5 的目录，拟合使用 X3mini 时可将 `env.sim2real.data_dir` 指向实际输出的绝对路径；单给默认文件名将查找 X3mini 任务目录。同名文件已有两种先例，滤波器排他创建，采集器完成临时文件后原子替换。转换器需要在 Specify 确认已有输出如何处理。[文件名](../../src/pace_sim2real/utils/paths.py#L10) · [拟合路径](../../scripts/pace/fit.py#L108) · [任务名规范化](../../../IsaacLab/source/isaaclab_rl/isaaclab_rl/entrypoints/common.py#L325) · [滤波写入](../../scripts/pace/filter_chirp_data.py#L75) · [采集写入](../../src/pace_sim2real/utils/trajectory_simulation.py#L309)

**建议与待确认事项（Proposed）。** 对仅传 `--task` 的转换，优先考虑直接读取注册配置。以该任务的默认控制周期作为提示的参照，以录制的秒值作为文件时间。建议将下列两项带入 Specify。

- Q8：若有效段的时间戳偏离录制自身的固定时间网格，超出严格拟合可接受的误差，建议停止并指出首个偏离帧。均匀但与任务默认周期不同的情形继续按已批准的 Q7 导出。
- Q9：建议已有同名输出时保留原文件，提示用可选输出名另存。这样同目录的多份 CSV 可各自保留转换结果。

**核对范围。** 核对环境为 Python 3.12.16、PyTorch 2.11.0+cu130、Isaac Lab 45.1.0、isaaclab-tasks 30.1.3 和 Gymnasium 1.4.0，Isaac Lab 源码为 `ae6330248`。本轮逐行读取样例并核对配置、消费端源码及现有测试。拟议的 CPU 往返验收可在独立临时目录对照 CSV 原行、两种固定周期的加载结果、内部失效和未知关节的诊断；转换器端到端结果留待后续验证。

**Research 交接。** 用户答复“同意 Q8、Q9，并批准 CR7 进入 Specify”。上文 Q8、Q9 的建议现为 Approved。[Specify 草案](spec.md#cr7-实机-csv-转换规格)
