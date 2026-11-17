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
