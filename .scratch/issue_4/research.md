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
