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
