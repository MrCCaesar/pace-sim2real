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

**Bounds and friction.** Preserve existing numeric bounds while correcting layout: X5 armature[1e-5,1], damping[0,7], friction[0,.5], leg bias[-.1,.1], delay[0,10]; optional ratio[0,1]. Resolve any actual actuator capacity mismatch explicitly in task configuration, not by clipping candidates. Bounds must be finite, lower<=upper, with nonnegative mechanical/delay quantities. Equal bounds fix a parameter; do not require it to be identified. Newton warns and disables separate dynamic/static ratio identification during configuration validation, removing the appended ratio bounds before CMA allocates variables; PhysX keeps the existing ratio parameterization. Do not claim equal physical friction units/models across backends; result provenance names the concrete backend/solver.

**Population and stopping.** Keep resource-safe fit default2 environments; reject population<2 before constructing CMA. Population2 remains a supported smoke/minimum setting with the Research warning caveat; controlled optimization acceptance uses4 as approved. Keep max_iteration and epsilon settings. Relative spread denominator is max(abs(best_score),1e-12); zero-score cases stay finite. Stop only after a completed generation, distinguish max-iteration/relative-spread reasons, and do not present spread stopping as an accuracy certificate. Nonfinite physics/response/score causes a contextual failure; do not save a partial rollout as best. An earlier complete best remains intact.

**Precise acceptance scope.** In Q22's controlled case vary two active mechanical parameters (one leg, one wheel), fixing the others to known values via equal bounds; use a fixed documented seed and a noise-free reference. Report both raw RMSEs and initial/final objective. This demonstrates a genuine mixed optimization without promising recovery of all61 parameters. Separate known-truth and perturbed checks must show both groups respond. Count their reference/baseline rollouts within the same120s backend watchdog. Resource floor remains4GiB available RAM, check VRAM before starting, stop on pressure, run backends sequentially. If50% improvement is not met, report failure; no repeated seed-search or threshold relaxation. Native minimal tests additionally verify biased feedback-equivalent force with nonzero history, force saturation, control-limit rejection and unchanged pre-delay saved targets.

**Acceptance traceability.** All R1–R10, ADR0004/0005 migration, negative input tests, permuted mappings, initial wheel motion, action transforms, decimation, zero-score behavior and paired-result error recomputation need executable tests. Existing pure-leg fixtures and the native GUI/lifecycle suite remain regressions. Manual CR1 GUI acceptance and physical X5 convergence remain separate user-owned items; neither blocks specifying this software change. Exact commands/results belong in verification.md only after execution.

All product choices Q11–Q22 are approved. Detailed symbols/schema/tolerances and the two necessary file additions above were explicitly approved in Q23: “批准最终契约及两个必要文件”. No Plan, implementation or new simulation is authorized by this approval.

### CR2 Specify completion

Q11–Q23 are explicitly resolved. Final consolidation and concrete interfaces are Approved; earlier Draft sections are retained as proposal history and are superseded wherever the final contract resolves them. Structural constraint: retain existing layout/classes, with only the approved shared helper and focused test file added for implementation. Next stage is Plan only after explicit user authorization. This stage changed documentation/ADRs only; no runtime tests, production implementation, commits, pushes or GitHub mutations. `git diff --check` passed after final document updates.

### Implement clarification — Approved (2026-11-17)

User explicitly clarified that Newton's automatic disablement is intentional: warn and disable dynamic-friction ratio identification, stripping its bounds so CMA does not allocate unused variables. This supersedes the earlier final-consolidation sentence requiring rejection. Direct optimizer calls that bypass configuration validation still reject unsupported ratio identification. PhysX behavior is unchanged.

### Implement performance and simplicity amendment — Approved by user

User requires collection throughput no worse than pre-implementation ecefbfe, readable/extensible functions and no scale/offset/clip processing in action mapping or packing. This supersedes the inverse-transform requirement in Q18 and the earlier final contract. Environment configs own these settings and explicitly use absolute-target defaults. Prepack commands outside both collection and fitting loops; preallocate device collection buffers and transfer completed data once. Validate all captured states plus final state before returning; termination remains immediate. Sample times use arange(N)*step_dt seconds, avoiding endpoint-inclusive linspace drift.

The exact ecefbfe collector cannot run (undefined trajectory and obsolete actuator command access). Benchmark its loop with these blockers adapted, preserve its allocation/recording pattern, disclose all adaptations and compare under identical headless task/device/environment count. Report this limitation instead of claiming an unmodified baseline pass.

### Kitless CLI fix — User authorized

After the installed Isaac Sim package triggered EULA during generic launcher argument registration, user explicitly prohibited Isaac Lab source changes and authorized a project-local fix. Collection/fit register CLI flags locally and never access KitLauncher just to parse them. Keep Isaac Lab's preset resolution and launch_simulation runtime selection. Do not set EULA acceptance automatically in production. Newton parsing must work with isaacsim imports forbidden; explicit PhysX/Kit selections must still parse, and runtime Kit import occurs only after selection.

### Fitting performance follow-up — User authorized

User requested the same ecefbfe-baseline throughput/readability requirements for fit.py and cma_es.py. Keep current physics, initialization, grouping, weighting, best-pair contract and standalone single-sample tell support. Execute simulation with contiguous state buffers and evaluate completed rollouts in batches; validate full states including the last step before evolution. Batch population and generation CPU/device transfers. Record exact benchmark workload/adaptations and avoid claiming universal or unmodified end-to-end performance from an adapted reference loop.

### Post-release plotting refactor — User requested

Refactor the current plot_trajectory.py around current task-named log directories and paired schema-v2 output, retaining existing plot/mean compatibility. Separate result validation, run discovery, numerical errors and rendering; add the matching --task selector while retaining --robot_name, skip runs without required outputs, and report malformed records before rendering. Preserve measured-frame positions, wheel velocity units and actual evaluated candidate identity. No simulator, optimizer, loss, physics or dataset changes; existing closed issue states are not changed by this follow-up.

## CR3 — 拟合结果回放 · Specify / Q4–Q7 已确认

CR3-R1–R4 是已确认需求。Q4 经用户修订，Q5、Q6 已确认，Q7 经用户确认仅用于软件验收。本节沿用 ADR 0005、0006、0008、0009、0010 的偏置、时间、关节分组和最佳候选语义。

### 范围与职责

采集入口负责区分固定参数采集与拟合回放，解析参数和轨迹来源，在首步前写入参数及初态。两种模式共用现有动作映射、执行器和采样循环。拟合器已有的配对结果足以作为输入。已确认的运行查找、错误行为和名称核对适用于纯腿及腿轮混合任务。

### Q4–Q6 · 已确认

- **Q4 · 结果兼容。** 用户指定“按照最新的单一dt格式皆可”。回放读取当前配对 v2 的 `settings.dt`，要求时步有限、为正，与任务物理时步一致，且任务 decimation=1。仅有旧 `physics_dt`、`control_dt` 的结果报告格式过时并停止。Research 中建议兼容历史 ANYmal 结果的方案已被此次决定取代。该决定按文件格式适用于所有任务；纯腿任务新生成的单一 dt 结果同样可回放。腿轮分组和物理参数按名称校验，后端、求解器、时步、反馈偏置语义及延迟模式按当前拟合输出核对。轨迹时间标签仍按任务声明解释。
- **Q5 · 验证输入与初态。** 默认由现有扫频参数生成命令，使用采集初态（首个腿目标加拟合偏置，关节速度置零）。给出采集格式的轨迹文件时采用其全部有效采样，腿物理位置取首帧实测加拟合偏置，轮速取首帧实测，其他初始自由度取任务配置。文件的无名列按当前任务声明解释。若同时显式指定文件和扫频参数，提示二选一。回放清空执行器延迟历史，并按命令发出时刻记录期望值。
- **Q6 · 输出。** 回放默认不写数据，显式输出时只保存本次模型响应及命令，沿用三／五字段格式；保护轨迹输入、拟合输入和常规采集路径。带实测文件时始终在终端报告物理 RMSE，打开已有绘图选项时叠加三条曲线。生成扫频时绘制期望与模型响应。命令和结果提示中给出实际使用的拟合文件及轨迹来源，便于复查。

### 验收条件

| 编号 | 可观测结果 |
| --- | --- |
| A1 / R1、R3 | 同一任务下有较早完整运行、较新未完成运行和录像目录时，自动回放报告较新的拟合目录及缺失文件；显式选择较早结果可运行。只传任务名仍执行固定参数采集。 |
| A2 / R2 | 物理值逐关节可辨时，独立打乱结果中的组内顺序和命名参数排列，写入同一关节的值一致。缺失、重复、多余或跨组的关节在写入前被报告。覆盖当前单一 dt 的纯腿／混合结果、两种摩擦模型，以及仅有旧双时步的结果被明确拒绝。 |
| A3 / R4 | 文件首帧腿实测与期望有差、首帧轮速非零时，第一条模型记录与首帧实测按组一致。用可手算的响应检验两个 RMSE；只含腿的任务只报告位置项。扫频与文件回放均保留步前命令/响应配对。 |
| A4 / R1–R4 | 在相同任务配置、后端与初态下，用原拟合输入与已配对的最佳响应逐样本比对；另用一条有实测的不同轨迹验证预测误差。记录运行条件与数值差异，同输入复现精度与模型在新数据上的预测质量分别评价。|
| A5 / R1、R4 | 覆盖三种命令行入口、裸选项紧跟 Hydra 预设、可选绘图与落盘。回放默认不生成采集文件，失败时输入和常规采集文件内容保持原样。 |

假设显式验证文件的来源及无名列顺序由使用者掌握。

**Q7 · 同轨迹数值验收（已确认）。** 在相同后端、任务配置、命令和初态下，将短程受控回放与配对结果中的模拟响应按采样时刻和关节名对齐。A4 的复现测试分别取全体样本与关节的最大绝对差，腿位置须 ≤ 0.0001 rad，有轮时轮速须 ≤ 0.001 rad/s。超限仅记为该项测试失败。这两个阈值只用于软件验收；普通回放通过输入兼容性校验后可完整播放、绘图并按需保存，即使拟合或跟踪误差较大。独立实测轨迹按 CR3-R4 报告分组预测 RMSE。

## CR4 · 任意关节子集拟合与回放 · Specify 已批准

批准依据：用户确认“批准最终契约并进入 Plan，按上述验收条件拆分任务”。

用户已批准进入 Specify。CR4-R1–R7 是已确认的需求，本节 Q7–Q9 已获确认，审批依据见下文。前述 CR2、CR3 记录仍描述已有全量数据语义。

### 范围与职责

仿真保留任务的完整位置与速度动作。用户声明文件各列的具体关节和未记录关节的恒定目标。拟合与文件回放应采用同一套名称映射、首帧工况与整组延迟规则。只有记录关节贡献评分；TensorBoard、配对结果和离线图只报告实际参与的关节和响应组。缺失的位置或速度组不贡献权重。任意单关节、单组、不对称混合组、完整组均属范围。

### 首轮设计建议（Q7–Q9 已确认）

| 问题 | 建议的可观察行为 | 备选及影响 |
| --- | --- | --- |
| Q7 未记录关节的首帧 | 假定采集开始前已施加恒定指令。未记录的位置关节每步接收编码器坐标的保持角，首帧物理角为保持角加任务默认偏置，初速为零。未记录的速度关节首帧取保持速度，初始角取任务默认角。每轮候选与回放都从相同工况开始。 | 沿用任务初态后再开始施加保持指令，会包含接近目标的启动过程，适用于采集时确实从该状态启动的记录。 |
| Q8 多执行器组的延迟 | 只要一个执行器组含有记录关节，整个组采用同一个候选延迟；完全没有记录关节的组沿用任务默认延迟。跨组选中时仍然只有一个优化变量。 | 对所有驱动统一写入候选延迟也可表达系统级延迟，但会改变完全未参与辨识的驱动。对当前单驱动组 X5 两者等效。 |
| Q9 结果兼容 | 已有有效的单一 dt 配对 v2 全量结果继续可读；现有全量任务沿用其输出格式。部分关节结果以及需表达纯速度的新结果使用可明确区分的 v3，保存参与关节、完整控制分组、保持目标和共享延迟作用范围。 | 在 v2 增加可选字段改动小，但部分旧读取器会接受子集文件并遗漏未记录关节的保持工况。 |

### 已批准的验收条件

- 文件列序、动作列和模型 ID 故意打乱时，指令、候选参数、测量、图例均对应同名关节；重复、跨组、未知名称或两个空组选取应在写入参数前报告错误。
- 单个速度关节的参考文件只有时间、期望速度和实测速度。每代评分等于该通道归一化均方误差，只记录速度 RMSE。单个位置关节、非对称混合及已有全量任务均须覆盖。
- 为未记录关节设置可区分的非零保持角、速度和默认偏置；跨两代候选及文件回放核对首帧、每步恒定指令、逐关节机械参数和整组延迟。使用下述四个逐腿驱动组验证 Q8。
- 结果读写覆盖旧全量、仅速度及不对称混合输入；独立回放允许同一集合更换列序和轨迹。重复原轨迹的误差与独立轨迹的预测误差分别报告。沿用已批准的完整输入回归和输出文件保护。

### 首轮暂缓事项（进展见 Q10–Q14）

首轮答复后细化关节选择及保持目标的配置类型、缺省值和错误行为，按名称投影参数边界与误差尺度，明确回放工况变化时的校验、扫频路径边界及结果字段。当前没有实施或验证结论。

### Q7–Q9 确认与逐腿验收

用户确认 Q7、Q8、Q9，并指定实际可能采用的驱动布局。验收任务将 FL、FR、RL、RR 分成四个独立的 PACE 执行器组。每组各含本腿的 hip、thigh、calf 三个位置关节及 foot 速度关节。此布局是验收场景，实际任务仍由配置决定其驱动分组。

- 每次输入一条腿的独立文件，依次切换四条腿；时间共用，位置期望和实测各三列，速度期望和实测各一列。默认无摩擦比例时有 16 个物理参数（12 个机械参数、3 个腿偏置、1 个延迟）。每次拟合、TensorBoard、离线绘图和指定轨迹回放均可按该腿名称核对。
- 对每个文件，用与组默认值有区别的候选延迟检查写入和回放。目标腿四个关节共用该值，其余三组沿用各自默认延迟；其余十二个关节从保持工况启动并持续接收配置的恒定目标。另用只记录单腿其中一个关节的样例验证同一组未记录通道也获得该延迟。
- Q7 的保持初态、Q8 的整组延迟、Q9 的 v2/v3 兼容分别记录于 ADR 0011–0013。下一轮配置契约见 interfaces.md 的 Q10–Q12。验收场景尚未执行。

### Q10–Q12 已确认

Q11 将保持目标来源统一为任务的 ArticulationCfg.init_state。对未记录位置关节，发送默认物理角减默认编码器偏置，首帧物理角恢复为任务默认物理角；未记录速度关节直接使用任务默认速度。该规则用于每个拟合候选和文件回放。Q12 沿用整机的参数边界及误差尺度配置，选中数据的列序变化时按名称取对应值。

Q10 讨论的是两层顺序。leg_order、wheel_order 声明任务完整控制分组，也是整机参数与尺度的基准。reference_leg_order、reference_wheel_order 按用户批准的语义声明当前无名数据文件的位置、速度列。以单腿实验为例，完整分组仍为 12+4，本次文件为 3+1。现有加载器仅允许显式参考顺序等于完整分组；Q10 已批准扩展为各组独立的有序子集：None 取该任务组全部，[] 取空组，非空列表按文件列序取名。

### 回放行为 · Q13–Q14 已确认

- Q13 以独立工况验证拟合参数。回放时按当前任务的 init_state 构造未记录关节的保持目标，若与 v3 所存拟合保持目标不同，列出关节名、原值和本次值，允许完成回放；同工况复现时使用原保持目标。记录成员、跟踪类型、延迟作用组、后端和时步等兼容性仍按相应契约核对。
- Q14 回放轨迹来源。给出 --trajectory_file 时使用配置声明的实际文件列；省略文件时，从部分结果取得已辨识关节的名称，按现有任务扫频配置为这些关节生成目标，其余关节保持。对缺少适用扫频系数的任务，提示提供轨迹文件；不根据名称猜测幅值、中心或方向。任意非空组合均可使用符合契约的文件轨迹。

### Specify 汇总与回放验收

Q1–Q14 均已确认。拟合与回放沿用同一关节选择、保持目标、首帧和共享延迟规则。已批准的配对结果字段布局见 interfaces.md。下列检查在 Verify 执行。

| 输入工况 | 可观测结果 |
| --- | --- |
| 同一单腿文件、相同任务工况和最佳候选 | 按名称还原每个通道；重放的步前响应与保存的最佳响应逐样本对照。短程软件复现沿用位置最大绝对差 0.0001 rad、速度最大绝对差 0.001 rad/s 的已有标准。 |
| 文件覆盖同一记录集合，未记录关节的保持目标发生变化 | 列出发生变化的关节及原值、当前值和单位，用当前任务的保持目标初始化并完成回放。带实测文件时报告有效组的预测 RMSE；独立工况的 RMSE 不设通过阈值。 |
| 指定单腿拟合结果，省略轨迹文件 | 从结果取得已辨识关节；按名称施加任务适用的扫频系数，其他关节每步保持。若缺少适用系数，明确提示提供轨迹文件。局部驱动组覆盖与 Q8 一致。 |

## CR5 · 离线采集数据滤波 · Specify（Approved）

**已确认范围。** CR5-R1–R4 要求单独保存实测通道的滤波结果，保持原文件的数据契约，支持命令行配置。研究已验证现有拟合加载器能读取样例的四份实验输出。[两项 CPU 实验](research.md#cr5-临时实验结果research已执行)

**Q3 · 滤波方法与参数。** 对所有实测列共用四阶 Butterworth 低通，默认单程截止 20 Hz。使用 SciPy 二阶节前后向滤波，沿时间轴逐列处理，采用默认奇对称端点延拓，保留包括首尾在内的所有输出样本。用户可调整单程阶数和截止频率。400 Hz 是样例的采样率；工具按各文件的时间戳计算。将 SciPy 声明为脚本的直接项目依赖，沿用项目锁文件中的版本。技术选择及对拟合首帧的影响见 [ADR 0014](../../adr/0014-offline-measurement-filter.md)。

**Q4 · 文件与接口。** 增加一个独立 CPU 命令行入口，按既有采集格式识别位置和速度字段，兼容全量和部分关节数据。默认在输入所在目录生成带 `_filtered` 后缀的文件，也可显式选择新路径。输入记录、输出路径冲突和写入失败的行为见 [CLI 与张量契约](interfaces.md#cr5--离线滤波接口approved)。用户通过拟合任务现有的 `data_dir` 选择结果，并沿用输入文件对应的列序配置。采集及拟合无需新增接口。

**Q5 · 可测量的验收条件。** 以下阈值仅用于默认参数和指定测试工况。它们不参与脚本运行时的保存决策。

| ID | 工况 | 验收 |
| --- | --- | --- |
| CR5-A1（R1、R2） | 全量 X5、纯位置、纯速度、含不同列数的混合记录 | 输入输出字段顺序、形状、dtype、样本数一致；时间和指令逐元素相等。各实测输出对照相同参数下的逐列 SciPy 结果（转换为原 dtype 后按该精度比较），单列变化只影响对应列。拟合加载器按原列序声明成功读取。原始文件摘要一致。 |
| CR5-A2（R3） | Research 中的 400 Hz、固定种子与已知 10 ms 延迟的五列合成信号 | 五个干净测试频点的中段幅值损失均 ≤1%；含噪输入滤前与滤后的中段相位折算时差变化均 ≤0.1 ms；对干净真值的中段及首尾 RMSE 各自 ≤ 滤前对应 RMSE 的 35%。沿用原实验的时间窗。 |
| CR5-A3（R3） | Research 中同一 SHA-256 的真实 X5 样例 | 按研究中的逐列选频方法，入选频点幅值相对变化 ≤1%，每列 ≥30 Hz 能量降幅 ≥40 dB。分别报告首末帧腿位置及轮速的最大绝对改变量；无干净真值，端点用于观察。 |
| CR5-A4（R4） | 默认 CLI、显式四阶 25 Hz、不同阶数、无效输入 | 显式参数产生对应单程设计的前后向输出；路径冲突、非法参数、非均匀时间、不可用的短记录等按接口报错并保护文件。中文 README 给出默认和显式参数示例及拟合文件选择方式。 |

**审批状态。** 用户已明确批准 Q3–Q5 作为最终 Specify 契约，包括 CR5-A1–A4 及 ADR 0014。

## CR6 滤波诊断与可视化（Specify · Approved）

**已确认。** Q1–Q6 确定五项诊断全部来自本次采集文件及实际保存的滤后测量。按存在的位置组、速度组各报一份；开启绘图时，每个记录关节均可查看期望、滤前、滤后三条时间曲线及滤前带噪测量频谱。[需求](requirements.md#q4q6-已确认的指标含义)

**已批准的设计。**

- Q7 · 频带与入口。扩展既有滤波 CLI，新增 `--analysis_band_hz LOW HIGH`（默认 0.1–10 Hz）和 `--plot`（默认关闭）。分析频带只用于两项有效频点指标；≥30 Hz 能量使用整个可观测高频段。对其他工况可显式设置，例如 4 Hz 扫频使用 `--analysis_band_hz 0.1 4`。用户指定的合法频带与离散正频率取交集。
- Q8 · 指标与覆盖。沿用 Research 的逐关节选频、双精度数值底限和相位条件。按指标报告有效关节数；两项频域极值另报有效的“关节、频点”组合数与频率范围。部分有效时汇总有效部分并标出覆盖，完全不可计算时显示 N/A 和原因。诊断值用于选参，无阈值阻止保存。[算法与候选方案](../../adr/0015-filter-diagnostics-spectrum.md)
- Q9 · 展示与兼容。在保存成功后打印原有输出路径和分组指标，再按选项交互绘图。图按组与文件列号标识关节，时间曲线沿用原始单位，频谱为覆盖整个可观测频段的滤前单边幅值谱。绘图分支按需加载 Matplotlib。继续使用原脚本、原张量文件结构和原拟合加载入口；共享的数据处理、命令行与回归职责分别体现在现有脚本、README 与滤波测试内。[接口](interfaces.md#cr6-滤波诊断命令行与输出契约)

**已批准的验收条件。**

| 编号 | 工况与可观测结果 |
| --- | --- |
| CR6-A1 | 完整、纯位置、纯速度及缺省/显式空列组：默认不绘图；有效组各有五项及其单位，报告输出路径，结果仍满足 CR5 张量和文件保护契约。两次不同分析频带产生一致的滤后张量。 |
| CR6-A2 | 对 Research 指定 SHA-256 的 X5 文件分别运行四阶 20、25 Hz。两组各五项均对照研究结果，允许与研究表的绝对差分别为 0.001 个百分点（峰峰值、RMSE、谱幅），0.00001 ms（时差），0.01 dB（能量）。默认分析频带下有效频率并集两组均为 1.15–8.95 Hz，幅值与相位组合数位置组各 1643、速度组各 613。 |
| CR6-A3 | 手算两列案例应得到 50% 峰峰值和谱幅变化，跟踪 RMSE 比例为 `100 × √(8.5/5)`%；8 Hz 跨 ±179° 的时差变化约 0.694444 ms。覆盖零分母、部分常量列、滤后幅值消失与过弱、无有效频点以及 50/60 Hz 采样。显示 N/A 或正无穷按接口区分，其他可用指标正常报告。 |
| CR6-A4 | 开启绘图时逐列核对三条时间曲线与滤前单边幅值谱的数据、标签、单位以及奇偶长度的频率端点；关闭绘图时可在无图形环境运行，两个模式的五项指标和保存张量一致。README 给出默认诊断、自定义分析带与绘图示例。 |

用户已明确批准 Q7–Q9 为最终 Specify 契约，包括接口、ADR 0015 和 CR6-A1–A4 验收条件，本阶段核对依据为 [Research 实验](research.md#cr6-两项临时-cpu-实验已执行)。
