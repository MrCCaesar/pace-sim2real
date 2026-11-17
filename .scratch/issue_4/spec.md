# Issue #4 — Specification

Baseline status: Approved as planning baseline by user request to enter Plan and split tasks from these documents, following Q8–Q10 confirmations.
Requirements: requirements.md. Evidence: research.md. Contracts: interfaces.md.

## Confirmed scope

Native MuJoCo X5 collection, saved data and plotting only. Twelve leg-position and four wheel-velocity channels; preserve user-owned MJCF physics/collision settings. Collision/trajectory physical validity is user-accepted, not an automated pass/fail criterion. No fitting pipeline changes.

## Approved architecture — D1

- scripts/pace/data_collection_mujoco.py: thin CLI entry, configuration overrides, collection/save/optional plot orchestration.
- scripts/pace/mujoco_collection.py: standalone configuration, named joint/actuator/sensor mapping, chirp generation, native simulation, measurement processing and data export. Internal helpers are private; public contract is in interfaces.md.
- config/x5_collection.toml: explicit ordered channel names and excitation/measurement/run settings. Standard-library tomllib; no additional configuration dependency.
- Existing x5_calibration.xml remains authority for dt, integrator, PD, limits, native delay/history, passive friction/damping, armature and sensor noise. No runtime physics overrides or collision exclusions.
- tests/test_mujoco_collection.py: behavior tests with minimal native models; bounded X5 smoke validation separately.
- docs/examples/x5.md: actual command, units, output order, known fitting incompatibility and model acceptance boundary.

Rationale: keep the collector independent of package initialization which currently imports Isaac Lab. A sibling script helper is sufficient for one collector, avoids expanding package __init__ behavior, and separates CLI from testable logic. Alternative: public package module plus lazy package imports; deferred unless reuse warrants that broader change. This is a source-checkout CLI, not a new installed entry point or generic robot framework.

## Approved sampling semantics — D2

N=round(duration/dt), require N>=1 and duration/dt within 1e-9 of an integer; otherwise report an error instead of silently changing requested duration. Sample interval [0,duration), t[k]=k*dt. Perform N physics steps; final integrated state at duration is not an additional sample.

Linear chirp phase: 2*pi*(f0*t+(f1-f0)*t*t/(2*duration)). Leg target=center+amplitude*sin(phase); wheel velocity target=amplitude*sin(phase). All channels share phase. No clipping or automatic recentering.

Initialize leg qpos at configured centers, wheel qpos zero, all qvel zero. Initialize ctrl and each enabled native command history with the same starting targets via mj_initCtrlHistory. No settling interval.

For each sample: set current un-delayed ctrl; call mj_forward to refresh instantaneous joint sensors; capture sensor readings and associated t[k]; apply measurement-only bias/noise; retain original desired commands; then mj_step. Check finite state and invalid-dynamics warnings, including after the last step. Native forward computation, not a Python controller, determines forces/delay. Current X5 sensors have no sensor delay/decimation; reject delayed/interval sensors rather than silently claiming synchronous measurements.

## Approved configuration and noise — D3

Use explicit configuration defaults with CLI overrides for min_frequency, max_frequency, duration and plot. Approved defaults inherited from existing collection where applicable: 0.1 Hz, 10 Hz, 20 s; plot=false; seed=42. Add --config to select the TOML file. Other settings edited in TOML, avoiding extra physics CLI flags.

Leg centers [0,0.4,-1.4], amplitudes [0.25,0.5,0.99] repeated for FL,FR,RL,RR; wheel amplitude 10. Encoder bias configurable as scalar or 12-entry vector, default 0.05 rad. Seed configurable integer. Use a local random generator; independent Gaussian draws per channel/sample using XML sensor_noise as standard deviation. Position=raw-bias+noise; velocity=raw+noise. Noise never changes ctrl, physical state or native feedback. Zero XML noise produces exactly zero added noise.

## Output and plotting

Exact five tensor keys defined in interfaces.md, CPU tensors readable with torch.load(weights_only=True). Save only on successful complete collection to data/x5_sim/chirp_data.pt. Approved replacement policy: successful runs replace the prior dataset atomically; failure/interruption leaves prior output intact. Respect existing PACE_ROOT override when resolving project output location. Resolve default model/config relative to source checkout, and model path within custom TOML relative to its config directory.

Plot only when requested, after saving: one figure of 12 leg position axes, another of 4 wheel velocity axes, each comparing measured versus pre-delay desired signals, seconds/rad/rad-per-second labels and names. No live simulator viewer is required.

## Software acceptance criteria

- A1/R2,R3: correct named mapping despite differing body/actuator/sensor storage order; missing, duplicate, wrong-type channels fail clearly before stepping.
- A2/R4,R5: exact configured center/amplitude and linear chirp phase; common time grid, shape and sample-count contracts; invalid/non-finite inputs rejected.
- A3/R6: native four-step delay and nonzero historical targets reproduced in a minimal-model regression test; actuator effort clipping tested with saturation-driving input. No Python PD/delay approximation.
- A4/R7,R8: subtractive bias, noise-free exactness, seeded repeatability, independent channels and XML noise scaling verified independently of model physics. Avoid fragile single-run statistical assertions.
- A5/R9: five keys, tensor dtypes/shapes/order/units, pre-delay target values and sensor time alignment verified by round-trip and minimal dynamics tests.
- A6: collection failure preserves old dataset; successful write replaces complete dataset. plot=false avoids plotting import/use; plot=true displays both groups from saved-equivalent data.
- A7: bounded X5 smoke run validates mapping, finite values and data serialization. Contacts/poor tracking do not fail acceptance; numerical divergence does. This does not certify physical accuracy.
- A8/R10: documented command/format/config match implementation. Existing Isaac Lab scripts and fitting behavior remain outside this change.

## Approval and delivery

Q8 approved module/TOML separation; Q9 approved defaults, pre-integration sampling and integer-step duration; Q10 approved successful atomic replacement and failure preservation. User then explicitly entered Plan, Implement and Verify in sequence. This specification was implemented in 87da096; software acceptance evidence and physical limits are in verification.md.


## CR1 — Approved specification; implemented, formal Verify pending

Stage approval: “进入 Specify 阶段”. User then explicitly approved Q7–Q9 and Q10–Q11. The CR1 contracts below amend baseline D1–D3 and the no-live-viewer scope; earlier sections retain the original delivery history. This does not authorize Plan or implementation.

### Confirmed requirements

CR1-R1: independent signs for all twelve position and four velocity channels. Leg target = direction * (center + amplitude * sin(phase)); wheel target = direction * amplitude * sin(phase). Directions affect commanded trajectories and signed leg initial centers/history, not measured coordinate conventions. Units, channel order, sensor bias/noise and five output tensors remain as defined in the baseline.

CR1-R2: optional observation-only live 3D view, camera adjustment, approximately real-time viewing, independent of post-run plots. Closing its window continues collection. Explicitly requested viewer startup failure aborts without replacing the output. Existing Ctrl+C cancellation remains.

### Approved decisions — Q7–Q9

CR1-D1 / Q7: add optional position_directions (12 signs) and velocity_directions (4 signs) in [trajectory], each element strictly numeric +1 or -1 (bool rejected). Missing arrays default to all +1, preserving old TOML and Python-config callers; wrong length/value is an error. Provided TOML lists both arrays explicitly, initially all +1. No inferred left/right pattern. Existing required fields and unknown-key rejection stay in force.

CR1-D2 / Q8: retain the standalone collector; isolate live viewing in a child process with its own model/data, receiving authoritative state one way. GUI-side control/physics edits never reach collection. See Accepted ADR 0003. The existing collect signature remains; viewer ownership/cleanup belongs to its run. Private helper boundaries, snapshots and timing are defined by Q10/Q11 below and interfaces.md.

CR1-D3 / Q9: optional run.visualize boolean defaults false when absent; CLI --visualize / --no-visualize override it. Existing plot behavior and user-owned plot=true setting are preserved. Normal window close disables visualization and wall-clock pacing, and collection completes headlessly. Unexpected viewer failure after startup aborts collection with an actionable error and preserves old output, matching startup failure rather than silently hiding faults. KeyboardInterrupt cancels and cleans up both processes.

### CR1 acceptance criteria

- CR1-A1: independently signed leg/wheel targets match the approved formula; signed leg initial positions/control history match; all +1 preserves baseline results with identical seed/config. Measurements stay in native joint coordinates.
- CR1-A2: invalid sign lengths/values/types fail before stepping; old configs retain baseline behavior; CLI override precedence is deterministic.
- CR1-A3: visualization disabled requires no viewer/display initialization; visualization enabled leaves time grid, all five data fields and physics unchanged for fixed seed/config.
- CR1-A4: window closure continues to N samples; startup failure, unexpected runtime failure and Ctrl+C clean up resources and preserve existing output.
- CR1-A5: bounded native-viewer smoke test plus controlled failure/lifecycle tests; manually inspect camera interaction/window close. Synthetic evidence must not be described as manual GUI acceptance.

### Q10–Q11 — Approved timing and process contracts

Approval reference: user answered “10. yes 11. yes”. Q7–Q9 were approved separately. No unresolved product-design questions remain for this change.

CR1-D4 / Q10 — Approved timing contract: limit display publication to 30 Hz; the first state is the initialized state before the first integration. Publish later snapshots after integration. Pace authoritative physics against a monotonic wall clock while the window is open. When behind, skip waits and stale display frames, never physics steps or measurements. Keep pending display data bounded to the latest snapshot and do not wait for a per-frame acknowledgment. Normal window close disables pacing. Approximately real time is best effort, not a performance guarantee. Render cadence is an internal constant initially, not an additional public configuration option.

CR1-D5 / Q11 — Approved process contract: child loads the same resolved MJCF and receives copied mjSTATE_INTEGRATION snapshots (MuJoCo 3.17 API, exercised in E1), never aliases of authoritative arrays. Child refreshes derived display state without stepping authoritative physics. Separate lifecycle messages distinguish ready, normal-close and error; unexpected exit without an acknowledged normal-close is an error. Start collection only after ready. Startup deadline 10 s; graceful shutdown deadline 2 s, then terminate and wait 1 s, then kill and wait 1 s. Failure to reap within this bounded sequence is an actionable error; no dataset replacement. These are internal constants initially. KeyboardInterrupt uses the same cleanup sequence and retains CLI exit 130. Headless mode starts no viewer process and performs no real-time waits.

Approved private module boundary (Q11): scripts/pace/mujoco_viewer.py owns the child entry point, lifecycle and state transport; mujoco_collection.py keeps all physics, measurements and data ownership. It is a private sibling helper, not a new public package API. No Isaac Lab import or package initialization is introduced. UI features that mutate physics are not exposed as collection controls; display-side edits never propagate back. Exact native rendering fidelity remains a manual acceptance check.

### Traceability and verification obligations

| Requirement | Design / interface | Required evidence |
| --- | --- | --- |
| CR1-R1 independent signs | CR1-D1; position_directions/velocity_directions | CR1-A1/A2: mixed-sign formula, signed initial state/history, invalid types/lengths, legacy-config and all-positive equivalence |
| CR1-R2 observation isolation | CR1-D2; Accepted ADR 0003; private viewer helper | CR1-A3: same-seed output equality and display-copy mutation isolation; no viewer initialization when disabled |
| CR1-R2 enable/close/failure | CR1-D3/D5; CLI flags and lifecycle | CR1-A4: normal close completes; startup error/timeout, unexpected exit and cancellation preserve output and reap child; escalation paths checked without long real-time sleeps |
| CR1-R2 approximate real time | CR1-D4; latest-state publication and monotonic pacing | CR1-A5: controlled clock/slow display verifies bounded pending data, skipped frames but N steps, and no pacing after close |
| Documentation and actual GUI | interfaces.md; examples and config | Bounded desktop smoke plus explicit manual camera/window-close result; clearly distinguish automated from human observation |

Existing baseline A1–A8 still apply, with trajectory formulas extended by directions. Production tests must cover timeout/escalation paths not exercised by Research E2. Existing research probes are feasibility evidence, not implementation acceptance. No full-sweep physical acceptance is inferred.

### Handoff

Specify decisions Q7–Q11 are approved; interfaces.md consolidates their contracts. Implementation details that do not alter these contracts (transport primitive, private symbol names) can be chosen during implementation. No new user-facing options are implied. Next: Plan only after explicit user approval. User-owned collision/trajectory validity and future manual GUI verification remain acceptance boundaries, not unresolved design decisions.

CR1 implementation update: #8/#9 implemented against approved contracts; automated and bounded native smoke evidence is in verification.md under implementation checks. Code review and formal Verify status are tracked in status.md.

## CR2 — Specify / Approved (2026-11-17)

Stage authorization: user said “进入 Specify” after checkpoint `ecefbfe`. This approves specification work only. Earlier baseline/CR1 sections describe their historical deliveries; CR2 expands fitting scope and ADR0004 supersedes physical-center trajectory semantics. This draft is not an implementation authorization. Requirements CR2-R1–R10 are confirmed; proposed choices below await explicit approval.

### Confirmed facts

- Position groups come from `leg_order`; velocity groups from `wheel_order`. Mixed datasets contain both groups, while historical pure-position datasets remain supported.
- Wheels identify armature, damping and friction, but no encoder/velocity bias. Legs retain encoder-bias identification. One delay is shared across groups.
- Newton and Kit PhysX minimal articulation experiments passed with initially moving wheels and shared command delay. They do not validate ActionManager packing, full X5 fitting or parameter recovery.
- The normalized trajectory formula is `(centers + sin(phase)) * amplitudes * directions` (Accepted ADR0004). Measurement coordinates are not multiplied by trajectory directions.
- Current checkpoint is WIP: 67 tests passed/3 failed, collection references undefined `trajectory`. It is a comparison base, not a verified CR2 implementation.

### First decision round — Approved Q11–Q13

Approval: user explicitly selected unified Isaac Lab bias semantics in Q11 and accepted Q12/Q13. Earlier two-mode proposal is rejected, retained here as decision history only; no source-selectable bias_mode is planned.

**CR2-D1 / Q11 — Unified feedback and measurement bias (Approved).** Both collectors and fitting use leg feedback position `q-b` and recorded/simulated measurement `q-b` (plus collection measurement noise where already configured). Wheels have no bias. Native collection's former measurement-only behavior is superseded for future collection; see Accepted ADR0005. Existing native datasets retain their old physical provenance and cannot be converted to the new closed-loop response by shifting saved values. Do not silently label them model-compatible. Implementation method, initial states and explicit legacy-data identification/migration policy remain to confirm. Random measurement noise is not thereby approved for feedback injection.

**CR2-D2 / Q12 — Explicit time interpretation (Approved).** New collection uses actual pre-step sampling instants and retains issued pre-delay commands for that instant. Strict fitting accepts a finite, strictly increasing uniform time grid whose interval matches `env.step_dt` (physics dt times decimation); compare elapsed time after subtracting the first timestamp. No implicit interpolation or resampling. Legacy endpoint-inclusive linspace data can use an explicit legacy-index mode plus a required real sample interval; retain original timestamps for provenance, but use `k*legacy_dt` for replay/scoring/plotting. Validate the declared interval against replay cadence. Reject unsupported timing before candidate evaluation with a corrective diagnostic. Tolerance and single-sample handling remain for the next contract round. This preserves readability without asserting that historical labels were actual sample times.

**CR2-D3 / Q13 — Mixed objective (Approved).** Let `e_pos=q_sim-b-q_ref` and `e_vel=v_sim-v_ref`. For each available group, average `(e/scale)^2` across samples and that group's joints. Combine group means using positive configurable weights, divided by the sum of weights for present groups. Approved default scales: 1 rad for legs and 1 rad/s for wheels; default group weights: 1 and 1. These scales are not acceptance tolerances. Pure-position tasks have only the position term. Report unnormalized per-group RMSE in rad/rad/s separately. Reject nonpositive/nonfinite scales or weights; prevent zero-score division in stopping. Alternatives: per-joint excitation-amplitude normalization or measurement-noise/tolerance normalization. Exact scoring API and stopping thresholds remain pending.

### Subsequent contract decisions — Draft recommendations, not approved

- **CR2-D4 groups/mapping:** normalize pure-position legacy task declarations into a leg group; require unique, disjoint ordered leg/wheel names. Derive combined order once as legs then wheels. Resolve articulation indices and action-term columns independently by joint name. Validate command type, scaling/offset semantics and complete coverage before simulation; never use articulation IDs as action columns.
- **CR2-D5 sampling/startup:** proposed native initial leg qpos, ctrl and history equal the first normalized target plus encoder bias (Q14 Approved); no settling or trajectory clipping. For fit, initialize wheel velocity from the first measured velocity and restore it for every candidate rollout. Wheel angle and initial leg velocity are absent from saved data and require explicit assumptions/approval. Collection initial state is not automatically the same as replay initial state.
- **CR2-D6 parameter layout:** dimensional consequence is `3*(L+W)+L+1` before optional friction ratios (X5=61, legacy 12-leg=49). Exact block order/bounds migration, backend-specific friction ratios, delay units/rounding and buffer limits remain to approve. Never allocate wheel-bias dimensions or duplicate wheels in friction counts.
- **CR2-D7 results:** persist each selected evaluated candidate together with its matching measured-frame leg and wheel trajectories, scores, parameter layout, group names, time interpretation and bias mode. Do not associate a sampled trajectory with an unevaluated distribution mean. Versioning, filenames and legacy-reader behavior remain to approve.
- **CR2-D8 acceptance:** CPU contract tests plus bounded sequential Newton/PhysX integration and a controlled mixed identification case. Population, runtime cap, known-solution construction and measurable response-error threshold remain to approve. Do not infer physical parameter recovery from finite output or a small population score spread.

### Responsibilities — Proposed boundaries

Retain the existing entry points: `data_collection.py` for Isaac collection, `fit.py` for replay/orchestration, `cma_es.py` for candidate parameters/objective/results. PaceCfg owns ordered groups and fit settings. Introduce a small shared Isaac collection/fit contract helper for validated groups, datasets and name-based action mapping only if approved with its interfaces; do not create a general robotics framework. Native collection remains independent of Isaac imports. `plot_trajectory.py` and result documentation must consume the same paired-result schema. Native startup/config/tests must migrate to ADR0004 without changing user numeric trajectories or collision settings. Precise helper paths and callable signatures remain Draft until the physical/data choices settle.

### Traceability and remaining approval frontier

| Confirmed requirements | Proposed decisions | Required future evidence |
| --- | --- | --- |
| R1,R3 group compatibility | D2,D4 | Legacy pure-leg data accepted; incomplete/mismatched wheel fields fail; permuted mappings preserved |
| R2,R4,R5,R6 mixed dynamics | D1,D3,D6 | Correct dimension/bias scope; both backend paths; shared delay; separate error reports |
| R7 initial wheel motion | D5 | Nonzero wheel speed restored for every rollout; absent state assumptions documented |
| R8 results | D7 | Candidate/trajectory association round-trip, names and physical units; legacy reader behavior |
| R9 time/commands | D2,D4,D5 | Pre-step pairing, actual interval, explicit legacy mode, action-column permutation |
| R10 software acceptance | D8 | Bounded controlled response-fit criterion, resource limits and physical acceptance boundary |
| ADR0004 | D5 | First target plus bias equals native initialized qpos/ctrl/history (Q14 Approved); signed normalized center regression |

Assumptions: current Linux/installed backend versions are the evidence base; real collision/model validity remains user-owned. Open questions: none for the finalized CR2 specification; Q23 is approved. Q11–Q19 are resolved within their explicit scopes. No production code, tests, commit or tracker mutation in this stage entry. Next step is resolving specification questions, not Plan.


### Second decision round — Q14–Q16 Approved

- **Q14 native bias realization (Approved: user “接受”):** for unit-gear scalar position actuators with compatible control limits, submit `desired+b` to the native servo, save unshifted `desired`, and initialize physical qpos/native control history to `desired[0]+b`. Native PD then computes `kp*(delayed_desired-(q-b))-kv*qvel` for constant b and equivalently initialized history. Retain native force limits/delay. Validate actuator mapping and control-limit semantics; unsupported mappings must not silently use this equivalence. Measurement noise remains measurement-only. Exact rejection checks remain to specify; no XML changes approved.
- **Q15 replay initial state (Approved: user “接受，采用任务配置初始值”):** initial physical leg position is first measured position plus candidate bias; initial wheel velocity is first measured wheel velocity. Missing wheel angles and leg velocities use task-configured initial values, recorded with fit provenance, restored for every candidate rollout. This is an explicit modeling assumption, not evidence that those states never affect dynamics.
- **Q16 parameter blocks (Approved: user “接受该布局”):** for J=L+W, use armature[J], damping[J], friction[J], encoder_bias[L], shared_delay[1], then optional dynamic/static-friction ratios[J]. Combined joint order is legs followed by wheels. Pure-leg layout remains compatible; no wheel bias dimensions. Ratio support remains backend-dependent; Newton must not optimize an ignored ratio. Delay units/quantization and numeric bounds are a later frontier.

Future round must resolve existing measurement-only native datasets: recommend recollection for unified-model fitting, with explicit data provenance so unmarked files are not guessed compatible. This recommendation is not yet an approved rejection/migration policy.


### Third decision round — Approved Q17–Q19

**Q17 / data declarations:** user selected “不增加元数据，全部由拟合配置声明”. Keep the original data tensor payload and create no JSON sidecar. Fitting configuration declares ordered reference groups, time interpretation and reference bias semantics; persist the resolved configuration with fitting results. The rejected sidecar proposal is not part of the design. The handling of old measurement-only data was not independently approved by this answer: Q20 asks it explicitly.

**Q18 / common contract module:** user accepted the shared module and compatibility rules. A small shared collection/fit helper owns validation of groups/data and separate name-based articulation/action mapping. It inverts supported action scales/offsets to deliver physical targets; unsupported action types fail explicitly. Legacy pure-leg joint_order becomes leg_order; mixed joint_order is derived once as legs+ wheels. Conflicting explicit declarations fail instead of silently reordering reference columns. This approves the boundary, not yet every public signature.

**Q19 / paired best result:** user selected the best actually evaluated candidate across the entire run as the primary fit outcome. Persist its parameters, both response groups, separate errors, generation and candidate identity together. Distribution means may remain diagnostic artifacts and cannot masquerade as evaluated responses. Plotting reads a matched record. Legacy results whose pairing cannot be established produce an explicit diagnostic rather than combining unrelated mean/trajectory files.

### Fourth decision round — Approved Q20–Q22

- Q20: reference bias semantics live in fit configuration; reject declared historical measurement-only native data for the newly unified feedback model and recommend recollection. User explicitly approved Q20 and stated old-model compatibility is not required.
- Q21: retain shared delay in physics-step units; floor nonnegative candidate values, record continuous candidate and applied integer/seconds; require every actuator buffer to cover the upper bound. With decimation, targets hold between control samples but delay advances each physics step. Runtime cadence tests must establish this; never multiply delay by control dt silently.
- Q22: two-backend mixed replay smoke uses2env/40steps. Controlled identification uses a deterministic noise-free minimal leg/wheel model, at most4env/20 generations/40 physics steps per rollout,120s per backend, sequential runs after RAM/VRAM preflight. Acceptance: finite separate errors, known-truth candidate beats a deliberate perturbation, best mixed loss improves at least50% relative to the initial generation's best, and saved errors reproduce from paired trajectories. No full-parameter uniqueness claim. Population4 avoids relying on the tiny-population warnings seen in Research. User approved this future verification budget in Q22; it is not an experiment run in Specify. If it cannot pass within the approved budget, report failure and revisit the design/criterion explicitly rather than quietly weakening it.


### Final consolidation — Approved detailed contract, Q23

Q20–Q22 approval reference: “20. 接受，旧模型数据需重新采集,不需要兼容 21. 接受 22接受”. New structural constraint: “仅在必须的情况下修改原代码/文件的结构，新增文件”. This supersedes any inference that the approved shared responsibility authorizes a broader redesign.

**Minimal file impact.** Keep current CLI entry points, actuator classes, optimizer class, task definitions and package structure. Modify their existing responsibilities in place. One small new shared module, `src/pace_sim2real/utils/collection_contracts.py`, is proposed only to implement the explicitly approved common validation/action mapping without duplicating it or importing one executable script from another; existing paths.py and actuator modules do not own dataset contracts. One focused new test file `tests/test_mixed_collection_fit.py` is justified because the existing test file specifically covers standalone MuJoCo and must remain runnable without Isaac startup. No new framework, package split, generalized plugin layer, dataset sidecars or unrelated cleanup. New ADR files record the separate significant decisions required by AGENTS.md. Q23 approval covers these two bounded code/test additions; implementer must explain any further necessary structural change before expanding scope.

Affected existing code: data_collection.py (groups/trajectory/sample pairing), fit.py (validated input/replay), cma_es.py (layout/objective/paired best), plot_trajectory.py (paired results), pace_actuator.py (leg-only mapped bias/verified delay capacity), PaceCfg and existing ANYmal/X5 tasks (compatibility/bounds), mujoco_collection.py (native bias/startup), config/example descriptions and current MuJoCo tests. Repair existing X5 asset/task import wiring only where necessary to execute the approved paths; do not reorganize asset directories, alter collision models or revise numeric excitation settings. XML remains authoritative and unchanged by this specification.

**Time contract details.** Require N>=2, finite strictly increasing original timestamps and consistent tensor lengths. Strict mode requires all elapsed timestamps to match k*env.step_dt using `rtol=1e-5, atol=1e-7 s`; reject gaps/nonuniform cadence without resampling. Legacy mode requires explicit finite positive legacy_sample_dt matching env.step_dt to the same tolerance, and substitutes index time only by this explicit request. Ignore the inaccurate old labels for replay but preserve them in results. New collection uses N=round(duration/env.step_dt), integral-duration tolerance1e-9 and the existing chirp duration/frequencies; save actual elapsed simulation time before each env.step. Reject an automatic reset/termination during a recording/replay instead of concatenating different episodes.

**Delay details.** All controlled joints use the already supported Python PaceDCMotor path for the selected backend. Shared delay is applied once per physics-step actuator evaluation, in command mode or the task's already declared effort mode; do not silently switch an existing task's mode. Native reference uses command delay. Fit configuration declares the reference delay mode and must match the task. DelayBuffer reset continues its verified first-command prehistory behavior, and every rollout issues its first commands before integrating. Validate upper bound against every drive's configured max_delay before sampling candidates; no auto-truncation or auto-resizing of capacities. A decimation>1 regression must observe compute calls and delay onset in physical steps. Unsupported backend-owned actuator execution fails clearly rather than ignoring bias or delay.

**Bounds and friction.** Preserve existing numeric bounds while correcting layout: X5 armature[1e-5,1], damping[0,7], friction[0,.5], leg bias[-.1,.1], delay[0,10]; optional ratio[0,1]. Resolve any actual actuator capacity mismatch explicitly in task configuration, not by clipping candidates. Bounds must be finite, lower<=upper, with nonnegative mechanical/delay quantities. Equal bounds fix a parameter; do not require it to be identified. Newton rejects requested separate dynamic/static ratio identification rather than allocating unused dimensions; PhysX keeps the existing ratio parameterization. Do not claim equal physical friction units/models across backends; result provenance names the concrete backend/solver.

**Population and stopping.** Keep resource-safe fit default2 environments; reject population<2 before constructing CMA. Population2 remains a supported smoke/minimum setting with the Research warning caveat; controlled optimization acceptance uses4 as approved. Keep max_iteration and epsilon settings. Relative spread denominator is max(abs(best_score),1e-12); zero-score cases stay finite. Stop only after a completed generation, distinguish max-iteration/relative-spread reasons, and do not present spread stopping as an accuracy certificate. Nonfinite physics/response/score causes a contextual failure; do not save a partial rollout as best. An earlier complete best remains intact.

**Precise acceptance scope.** In Q22's controlled case vary two active mechanical parameters (one leg, one wheel), fixing the others to known values via equal bounds; use a fixed documented seed and a noise-free reference. Report both raw RMSEs and initial/final objective. This demonstrates a genuine mixed optimization without promising recovery of all61 parameters. Separate known-truth and perturbed checks must show both groups respond. Count their reference/baseline rollouts within the same120s backend watchdog. Resource floor remains4GiB available RAM, check VRAM before starting, stop on pressure, run backends sequentially. If50% improvement is not met, report failure; no repeated seed-search or threshold relaxation. Native minimal tests additionally verify biased feedback-equivalent force with nonzero history, force saturation, control-limit rejection and unchanged pre-delay saved targets.

**Acceptance traceability.** All R1–R10, ADR0004/0005 migration, negative input tests, permuted mappings, initial wheel motion, action transforms, decimation, zero-score behavior and paired-result error recomputation need executable tests. Existing pure-leg fixtures and the native GUI/lifecycle suite remain regressions. Manual CR1 GUI acceptance and physical X5 convergence remain separate user-owned items; neither blocks specifying this software change. Exact commands/results belong in verification.md only after execution.

All product choices Q11–Q22 are approved. Detailed symbols/schema/tolerances and the two necessary file additions above were explicitly approved in Q23: “批准最终契约及两个必要文件”. No Plan, implementation or new simulation is authorized by this approval.

### CR2 Specify completion

Q11–Q23 are explicitly resolved. Final consolidation and concrete interfaces are Approved; earlier Draft sections are retained as proposal history and are superseded wherever the final contract resolves them. Structural constraint: retain existing layout/classes, with only the approved shared helper and focused test file added for implementation. Next stage is Plan only after explicit user authorization. This stage changed documentation/ADRs only; no runtime tests, production implementation, commits, pushes or GitHub mutations. `git diff --check` passed after final document updates.
