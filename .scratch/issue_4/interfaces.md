# Issue #4 — Interfaces

Baseline status: Approved as planning baseline by user request to enter Plan based on these documents. Project APIs below are implemented in commit 87da096.

## Configuration input

TOML has [run], [model], [trajectory], [measurement], [channels].

- run.min_frequency/max_frequency: finite float Hz, 0 < min <= max < 1/(2*dt); defaults 0.1/10. Equal frequencies allowed as constant-frequency case.
- run.duration: finite positive float seconds, default 20; positive integer number of dt steps, ratio tolerance 1e-9.
- run.plot: bool, default false. run.seed: nonnegative integer, default 42.
- model.path: path to supplied X5 calibration XML. XML is authoritative for simulation/actuator properties and sensor noise.
- trajectory.position_centers/position_amplitudes: finite arrays length 12 in position-channel order, rad; amplitudes nonnegative. Defaults repeat [0,.4,-1.4]/[.25,.5,.99] four times.
- trajectory.velocity_amplitudes: finite array length 4, rad/s, nonnegative, default [10,10,10,10]. Wheel center zero.
- measurement.encoder_bias: finite scalar broadcast to 12 channels, or finite array length 12; rad, default .05. XML noise standard deviations must be finite/nonnegative.
- channels.position_joints: FL/FR/RL/RR each hip_joint, thigh_joint, calf_joint (12 explicit names).
- channels.velocity_joints: FL/FR/RL/RR foot_joint (4 explicit names).

Map actuator and sensor IDs by associated joint, never assume IDs equal qpos/qvel offsets. Require unique scalar hinge channels, appropriate scalar direct-joint position/velocity actuator semantics (unit gear and expected gain/bias signature), and unique jointpos/jointvel sensor respectively. Unsupported mappings fail instead of silently converting units. Current scope is X5, not arbitrary transmissions. No world-frame Cartesian quantities are exposed: angles/velocities follow each MJCF joint's positive axis convention.

CLI: --config PATH; --min_frequency FLOAT; --max_frequency FLOAT; --duration FLOAT; --plot. Overrides apply after TOML load. Omitted overrides preserve file settings; --plot enables plotting. Invalid arguments/config yield a nonzero exit and actionable error. No simulator launcher or Isaac Lab flags.

## Project public Python interfaces

Defined in scripts/pace/mujoco_collection.py:

- CollectionConfig: validated run/model/trajectory/measurement/channel settings above. Validation depending on dt and model mapping occurs at collection start.
- load_config(path: Path) -> CollectionConfig: parse TOML, resolve model path relative to file, reject unknown/missing required settings and invalid types. CLI defaults are represented in the provided TOML, not duplicated in parser defaults.
- collect(config: CollectionConfig) -> CollectionData: load one native MuJoCo model, validate mapping/config, execute N steps and return data; no save/plot side effects. Invalid config/model raises ValueError with context; I/O errors remain actionable; nonfinite dynamics or automatic-reset evidence raises RuntimeError. KeyboardInterrupt propagates.
- CollectionData: time ndarray float64 [N]; dof_pos/des_dof_pos float64 [N,12]; dof_vel/des_dof_vel float64 [N,4]. Internal values in SI units; measured fields include configured bias/noise, desired fields are pre-delay commands.
- save_data(data: CollectionData, path: Path) -> None: validate consistent shapes/finiteness, create parent if necessary, serialize CPU tensors via a temporary sibling file and atomic replace. Clean up temporary on error; do not damage prior output.
- plot_data(data: CollectionData, position_names: Sequence[str], velocity_names: Sequence[str]) -> None: validate name lengths, lazily import matplotlib, display separate position and velocity subplot figures.

Default output: project_root/data/x5_sim/chirp_data.pt, honoring PACE_ROOT as existing collection does. Root resolution must not trigger pace_sim2real package initialization/Isaac Lab import.

## Saved data contract

| Key | Type/shape | Unit | Meaning |
| --- | --- | --- | --- |
| time | CPU torch.float64 [N] | s | k*dt, endpoint excluded |
| dof_pos | CPU torch.float32 [N,12] | rad | position sensor minus encoder bias plus noise |
| des_dof_pos | CPU torch.float32 [N,12] | rad | issued leg target before native delay |
| dof_vel | CPU torch.float32 [N,4] | rad/s | wheel velocity sensor plus noise |
| des_dof_vel | CPU torch.float32 [N,4] | rad/s | issued wheel velocity target before native delay |

No extra metadata keys are saved. Channel order is documented and fixed by approved X5 configuration. Existing fit.py cannot consume the mixed model correctly without a later adaptation; preserving position key names does not imply end-to-end compatibility.

## Existing MuJoCo APIs (not project inventions)

MjModel.from_xml_path, MjData, mj_forward, mj_step and mj_initCtrlHistory. Version tested in Research: 3.17.0. Use XML/native structures for dt, noise, forces and history; do not independently implement actuator physics.

## Approval and delivery

User approved this planning baseline, then authorized Implement and Verify. The interfaces are implemented in 87da096; verification.md records the software acceptance results.


## CR1 contracts — Approved Q7–Q11; implemented, formal Verify pending

The baseline contracts above describe the existing implementation. User approved configuration/architecture/policy in Q7–Q9 and timing/state-transfer/cleanup in Q10–Q11. These CR1 amendments take precedence for the forthcoming change.

| Approved input | Type / shape / unit | Default and semantics | Errors / compatibility |
| --- | --- | --- | --- |
| trajectory.position_directions / CollectionConfig.position_directions | tuple of numeric signs [12], dimensionless | All +1; follows position_joints order; multiplies both center and oscillation | Only -1 or +1, reject bool/nonfinite/wrong length; absent TOML field and omitted Python argument use default |
| trajectory.velocity_directions / CollectionConfig.velocity_directions | tuple of numeric signs [4], dimensionless | All +1; follows velocity_joints order; multiplies wheel velocity target | Same constraints; no sign change to sensor measurements |
| run.visualize / CollectionConfig.visualize | bool scalar | false; optional live observation window | Non-bool rejected; missing field preserves headless behavior |
| --visualize / --no-visualize | mutually exclusive CLI flags | Omission keeps TOML value | Conflicting flags fail argument parsing; independent of --plot |

Existing center/amplitude units and XML joint coordinates remain unchanged. Initial leg qpos/ctrl/history use direction*center; wheel qpos/qvel and historical wheel targets remain zero. Targets stored in des_dof_pos/des_dof_vel are signed, pre-delay commands. Measurements are not multiplied by direction. No new saved tensor keys.

collect(config) keeps its return type and save-free behavior; when visualize=true it additionally owns the optional viewer lifecycle. Errors: RuntimeError on viewer startup or unexpected runtime failure with context; normal window close completes normally; KeyboardInterrupt propagates after cleanup. No viewer imports/processes when disabled. Public function signatures for load_config/save_data/plot_data remain unchanged. Unknown config fields continue to be errors; only the three CR1 additions gain missing-field defaults.

### Private viewer integration contract

Module: scripts/pace/mujoco_viewer.py, a private sibling helper. The following are responsibilities, not new public APIs or mandatory symbol names. Collector owns all authoritative physics, RNG, sampling and data; helper owns viewer process, bounded latest-state delivery and lifecycle notifications. No shared authoritative model/data or GUI-to-physics updates.

- Start: input resolved model Path and an owned copy of initial native integration state; load the same MJCF in child. Output ready or contextual RuntimeError within 10 s plus bounded cleanup. Ready precedes sampling and the wall-clock pacing origin. Initial state includes the signed centers and initialized native command history.
- Publish: input copied float64 vector [S], where S=mj_stateSize(model, mjSTATE_INTEGRATION). Preserve native field ordering/units and model layout; this vector is transient, not a saved data field. Apply via mj_setState on display data and refresh derived state for rendering. No authoritative mj_step in the helper. Pending data bounded to latest state; no per-frame acknowledgment blocking physics. Native model options remain owned independently in each process.
- Poll: output running, acknowledged normal-close, or error. Lifecycle delivery is distinct from replaceable display frames. Drain available lifecycle notifications when interpreting process exit so normal-close is not misclassified just because the child exited before polling. Unexpected death without normal-close is a RuntimeError. On normal-close, stop publication/pacing and complete the original N samples.
- Pace: monotonic clock, best-effort real-time while open, display publication at most 30 Hz; first snapshot is pre-integration, later snapshots post-integration. If behind, skip waits/stale display frames; never discard physics steps, measurements or random draws. dt/time grid are always simulation quantities. No headless sleeps.
- Close: request graceful exit and wait at most 2 s; if needed terminate/wait 1 s, then kill/wait 1 s. Reap child and release IPC resources. Failure to clean up is reported; successful collection cannot be returned for saving before final lifecycle/error checks and cleanup. Cancellation uses the same cleanup and preserves CLI exit 130; retain diagnostics if cleanup also fails.

The 30 Hz and 10/2/1/1 s values are internal constants, not new config fields. Child start/error/close handling must work for early failures before a viewer handle exists. Parent startup watchdog contains the native failure or blocked startup; an in-process try/except around launch_passive alone is insufficient.

MuJoCo launch_passive/sync/is_running/close and mj_stateSize/mj_getState/mj_setState with mjSTATE_INTEGRATION are existing library APIs. Research verified version 3.17.0 on Linux; no cross-platform GUI compatibility claim is made. Native UI operations may affect display-owned objects but cannot change the collected physics. Camera/visual fidelity and manual window-manager close remain explicit GUI verification items.

CR1 implementation update: #8/#9 implemented against approved contracts; automated and bounded native smoke evidence is in verification.md under implementation checks. Code review and formal Verify status are tracked in status.md.

## CR2 interface amendments — Proposal history (2026-11-17)

These are proposed project contracts, not claims about existing implemented APIs. Specify was authorized after `ecefbfe`; approved Q11–Q13 are recorded in spec.md. Original interfaces above retain their historical status. ADR0004 already approves normalized-center formula semantics, but startup migration is pending.

### Dataset and group contract

Let L be position-channel count, W velocity-channel count, N sample count. Ordered names follow task `leg_order` and `wheel_order`; they refer to simulator joint coordinates, not a world/body frame. Proposed canonical data:

| Field | Type / shape | Units / meaning |
| --- | --- | --- |
| time | CPU floating Tensor[N] | seconds, actual shared pre-step sampling instants for new data |
| dof_pos | CPU floating Tensor[N,L] | rad, recorded position including the chosen measurement bias |
| des_dof_pos | CPU floating Tensor[N,L] | rad, issued leg targets before delay |
| dof_vel | CPU floating Tensor[N,W], required when W>0 | rad/s, recorded wheel velocities |
| des_dof_vel | CPU floating Tensor[N,W], required when W>0 | rad/s, issued wheel targets before delay |

New output is proposed to match native dtypes: float64 time and float32 responses/targets. Loader accepts historical floating tensor dtypes and normalizes computational dtype/device explicitly. All values must be finite, sample lengths agree and channel widths match task declarations. Both wheel fields are required together. A mixed task must not consume three-field data or infer wheel speeds by differentiation. Policy for empty wheel tensors on pure-position tasks, minimum N and timing tolerance remains open; existing native five-tensor payload is not silently changed.

Three-field files contain no source/bias-model declaration. Their source cannot be identified from keys alone. Pure-leg compatibility does not grant permission to guess missing real sampling intervals. Missing or ambiguous configuration must produce a contextual error before candidate evaluation.

### Proposed fit configuration (names provisional)

| Setting | Type / defaults | Constraints / semantics |
| --- | --- | --- |
| leg_order | ordered sequence[str] | unique existing position-controlled joint names; legacy joint_order-only migration pending |
| wheel_order | ordered sequence[str] or None | unique velocity-controlled joint names, disjoint from leg_order; empty/None means no wheels |
| encoder bias semantics (Q11, Approved; not a mode option) | leg-only subtractive bias in feedback and measurement | unified for future native/Isaac collection and fit; former two-mode proposal rejected; historical native data provenance remains to resolve |
| time_mode (Q12) | enum: strict / legacy_index; approved default strict | strict validates measured cadence; legacy_index explicitly changes replay time interpretation |
| legacy_sample_dt (Q12) | optional float seconds, default None | required finite >0 in legacy_index; must match env control interval |
| position_error_scale (Q13) | float rad, approved default1 | finite >0; numerical normalization, not acceptance tolerance |
| velocity_error_scale (Q13) | float rad/s, approved default1 | finite >0, used when wheels exist |
| position_weight / velocity_weight (Q13) | float, approved default1 each | finite >0 for present groups; combine normalized group means |

Configuration ownership is PaceCfg/CMA settings, not extra mandatory CLI flags. Exact nesting and public callable signatures follow these decisions. No configuration or behavior above is implemented by this document. Q11–Q13 semantic choices are approved; exact names/nesting remain Draft.

### Trajectory and state amendment

`position_centers` and Isaac `trajectory_bias` are dimensionless center coefficients; amplitudes retain rad for position or rad/s for velocity. Full desired trajectory is `(center + sin(phase))*amplitude*direction`. This supersedes prior physical-radian center wording for the amended behavior. Keep current numeric coefficients, amplitudes and signs; do not silently rescale configuration to preserve an old physical center. Approved native startup (Q14) uses the first generated leg target plus encoder bias consistently for physical qpos/ctrl/history; saved desired position remains unshifted. Fitting reconstructs candidate initial physical leg position from measured position plus candidate bias; first measured wheel velocity initializes wheel qvel. Q15 approves task-configured initial values for unrecorded wheel qpos and leg qvel, restored each rollout and recorded in results.

### Library versus project interfaces

Installed Isaac Lab `env.step_dt`, ActionManager term slicing, articulation state setters and actuator target commands are library APIs, as recorded in Research. Canonical group mapping, data validation and mixed result records are project responsibilities. An articulation joint ID is not an action-column ID. Integration must honor action scale/offset and target type; exact adapter shape/error contract and whether unsupported terms are rejected remain to specify.

Pending public contracts: CMA parameter blocks and bounds, score/update inputs, shared-delay cadence/rounding, paired-result format/reader compatibility and test acceptance thresholds. These remain explicitly Draft; do not implement against unfinished signatures or treat stage entry as approval.


### Q16 parameter indexing — Approved

For J=L+W: armature `[0:J]`, damping `[J:2J]`, friction `[2J:3J]`, leg bias `[3J:3J+L]`, shared delay index `3J+L`, optional friction ratios `[3J+L+1:4J+L+1]`. Base count `3J+L+1`; bounds shape `[parameter_count,2]`. All bounds finite and ordered; exact fixed-parameter treatment, physical units per backend and delay quantization remain open. User approved this layout in Q16; it is not yet implemented.


### Approved ownership and data provenance — Q17/Q18

No dataset metadata file or additional dataset keys. Reference names, timing interpretation and bias semantics are declared in fit configuration and copied into fit results. This is a declaration by the operator, not an automatic proof of the file's physical provenance. Do not infer semantics from its path or tensor count. A false declaration cannot be detected solely from the tensor payload.

Proposed concrete helper: `src/pace_sim2real/utils/collection_contracts.py`, importable without launching a simulator. Group/data validation has no Isaac runtime dependency; runtime mapping consumes the existing environment after launch. Native collection continues standalone and does not import this package helper. This path and signatures remain for final detailed review; the shared responsibility boundary is approved.

### Approved result identity — Q19

The primary result is the globally lowest-score evaluated candidate with its own parameters and measured-frame trajectories (leg q-b, wheel v). Store its generation and candidate index, ordered group names, effective time vector, raw group RMSE, scalar normalized objective and the fit configuration. On equal scores retain the earlier best for deterministic provenance. Save to a versioned paired record; exact filename/schema follows in the final contract. Legacy distribution means remain diagnostics only; absence of demonstrable response pairing must produce a clear plotting diagnostic.


## CR2 final concrete interfaces — Approved in Q23

This section resolves earlier provisional names and defaults; it takes precedence over the earlier Draft recommendations. Q11–Q23 are approved; user explicitly answered “批准最终契约及两个必要文件”. No new public installed CLI entry points or package restructuring.

### PaceCfg declarations

Existing leg_order/wheel_order/joint_order remain the task group contract. A legacy pure-leg task with only joint_order normalizes that list into leg_order. When groups are supplied, joint_order is derived as their concatenation; an explicitly conflicting value fails. Require L>=1, W>=0, unique/disjoint existing names. Wheel-only tasks are outside the approved extension. Measured data columns are not silently permuted.

Add the following flat fields to existing PaceCfg (avoid a new configuration class):

| Field | Type and default | Meaning / validation |
| --- | --- | --- |
| reference_leg_order | list[str] or None, None | declaration of file position-column order; None explicitly adopts resolved task leg_order; otherwise must exactly match it |
| reference_wheel_order | list[str] or None, None | same declaration for wheel columns; defaults to task wheel_order |
| reference_bias_model | str, feedback_and_measurement | only supported model; measurement_only fails with recollection instruction; no source guessing |
| reference_delay_mode | str, command | command or effort; must match every controlled task actuator's mode |
| time_mode | str, strict | strict or legacy_index |
| legacy_sample_dt | float or None, None | required finite positive seconds in legacy_index; reject unused non-None value in strict mode |

These defaults are explicit project model assumptions, not automatic detection of legacy-file provenance. Operators must select an accurate declaration. Any known old measurement-only dataset is unsupported even if its tensor shapes match.

Add to existing CMAESOptimizerCfg: position_error_scale=1.0 rad, velocity_error_scale=1.0 rad/s, position_weight=1.0, velocity_weight=1.0. Each finite and >0; velocity settings have no loss contribution on a pure-leg task. Keep existing iteration/sigma/save settings and numeric bounds except necessary group-layout/capacity corrections.

### Shared helper boundary (one new module)

`utils/collection_contracts.py` owns the following project functions. It imports no simulator runtime at module import; any Isaac-specific inspection happens after launch. Internal helper symbols may vary without expanding this contract.

| Function | Input → output | Behavior / errors |
| --- | --- | --- |
| add_runtime_args(parser) | argparse.ArgumentParser → None | register options in place without backend imports; device/max_visible_envs=None, boolean flags=False, livestream=-1, experience/kit_args empty, animation times=0/10 seconds; duplicate flags raise argparse.ArgumentError |
| resolve_joint_groups(cfg) | PaceCfg → tuple[tuple[str,...], tuple[str,...]] | normalize legacy pure-leg declaration; validate uniqueness/disjointness/combined order; ValueError on conflict |
| load_reference_data(path, cfg, step_dt) | Path, resolved PaceCfg, float seconds → dict | safe tensor load, shape/finite/order/time/model checks; returns canonical data keys plus internal original_time and resolved declarations; FileNotFoundError/OSError for IO, ValueError for invalid contract |
| resolve_action_mapping(env, leg_order, wheel_order) | launched environment and name sequences → mapping record | independently resolve articulation IDs and action term columns; reject missing/duplicate/type-incompatible/unknown action terms and ambiguous coverage |
| pack_actions(mapping, desired_pos, desired_vel) | record; float Tensor[B,L], optional Tensor[B,W] → float Tensor[B,A] | reorder targets into action columns only; B may represent environments or trajectory samples; preserve values/device/dtype and reject shape/device mismatch; task configuration owns scale, offset and clipping (user amendment below) |

Mapping record is internal, containing ordered articulation IDs, action columns and group widths; no simulator state copies are exposed as a public model. Only supported absolute position and velocity action terms are accepted. Relative/delta-position, effort or unknown terms in the covered action vector fail explicitly. Native data collection does not import this helper.

### Tensor and timing rules

New pure-leg collection saves exactly time/dof_pos/des_dof_pos; new mixed collection saves the same five fields as native. Time=float64[N], other fields=float32[N,L or W], all CPU. Loader accepts floating tensors of either precision; converts working responses to the optimizer device/dtype, retains float64 canonical time. For W=0, absent wheel fields or both [N,0] fields are accepted; nonempty wheel fields fail. Missing one wheel field always fails. Extra non-tensor metadata is not accepted as a substitute for configuration declarations.

N>=2 for fitting; shared lengths and finite values required. Strict time check: elapsed time against arange(N)*step_dt with rtol1e-5/atol1e-7 seconds. Legacy mode retains original_time but uses arange(N)*declared_dt. Sample/reset/target semantics and delay cadence are specified in spec.md. Loader validation occurs before any candidate evaluation; checks requiring live mapping occur immediately after environment creation.

### CMAESOptimizer extension in place

Retain the existing class and existing constructor arguments. Add keyword-only `leg_order=None`, `wheel_order=None`, `position_error_scale=1.0`, `velocity_error_scale=1.0`, `position_weight=1.0`, `velocity_weight=1.0`, `reference_settings=None`. Legacy joint_order-only construction means all-position; mixed construction must supply groups whose concatenation equals joint_order. Validated data contains the required groups, N>=2 and canonical time. `reference_settings` is the resolved declaration/initial-state/backend record, with primitive values/CPU tensors suitable for safe persistence.

- `tell(sim_dof_pos, real_dof_pos, *, sim_dof_vel=None, real_dof_vel=None)`: physical leg positions and measured reference positions [P,L]; wheel velocities [P,W] when W>0. Subtract each candidate's leg bias exactly once, accumulate per-group squared errors and retain measured-frame candidate responses. Reject missing velocity inputs for mixed tasks, unexpected nonempty wheel inputs for pure-leg tasks, incorrect shapes/nonfinite values or more than N samples. Keep physical wheel position out of the residual.
- `update_simulator(articulation, joint_ids, initial_position, *, initial_wheel_velocity=None)`: ordered joint_ids[J]; initial_position[P,L] is measured leg position; initial_wheel_velocity[P,W] required for mixed tasks. Restore task defaults for absent leg velocity/wheel angle; add candidate bias only to leg physical positions. Map candidate leg bias to actuator-local joint order, zero for wheels. Apply parameters and validated floor-delay; reset all buffers/states per rollout. Validate covered actuators, device and capacities before writing.
- `evolve()`: require exactly N samples, compute normalized weighted objective and raw group RMSE, evaluate/persist global best before resetting buffers, then perform CMA tell/ask lifecycle. Stable tie rule retains earlier candidate. Never pair distribution mean with candidate buffers.
- `get_best_sim_params()`: returns a copy of the globally best evaluated physical-parameter vector [K]; RuntimeError before any completed evaluation. This replaces the misleading existing mean-return behavior in accordance with Q19.
- `finished()`/`close()`: use finite relative-spread semantics from spec.md, save only completed evaluated records. No new successful result from an interrupted partial generation.

Parameter bounds [K,2] follow approved Q16 slices. Physical rotational armature is kg*m^2; damping N*m*s/rad; bias rad; delay physics steps; ratios dimensionless. Friction's concrete backend convention is recorded, not assumed interchangeable. Full vector, applied integer delay and effective seconds are all preserved. `initial_position` and `tell` remain source-code migration points; update all callers together.

### Paired result schema and consumer

Use `best_result.pt` within the existing run directory, atomically replaced only when a completed evaluated candidate improves the global best; final close flushes that same record. No new data sidecar. Safe-loadable dictionary `schema_version=2` contains:

- `params`: CPU floating Tensor[K]; `leg_order`, `wheel_order`, `parameter_names` lists; `generation` and `candidate_index` nonnegative integers.
- `time`: effective float64[N]; `original_time`: original reference float64[N]; `reference`: canonical original measured/desired tensor fields; `sim_dof_pos`: CPU float32[N,L] already in q-b measurement coordinates; `sim_dof_vel`: CPU float32[N,W] when W>0.
- `score`: finite float normalized objective; `position_rmse`: finite float rad; `velocity_rmse`: finite float rad/s or None for W=0; scales and weights in resolved fit settings.
- `settings`: serializable resolved task/reference declarations, known initial wheel angles/leg velocities, backend/solver, physics_dt, control_dt, delay_mode, parameter bounds; `delay_candidate`: float; `delay_steps`: nonnegative int; `delay_seconds`: float.

Save means/progress under existing names if already enabled, explicitly diagnostic. `plot_trajectory.py` keeps existing robot/folder/plot flags and adds optional `--result_name` (default best_result.pt); displays names and rad/rad/s, reads pre-corrected simulation measurements without subtracting bias again, and can recompute objective from the stored record. Existing `--mean_name` may still inspect mean parameters but cannot request trajectory comparison without an independently paired result; conflicting selectors fail. Old result files without demonstrable parameter/response pairing produce an explanatory error for trajectory plotting, not a guessed pairing. New collection file names/location remain unchanged.

### Necessary test addition

One new `tests/test_mixed_collection_fit.py` contains group/data/objective/result CPU tests and bounded backend integration tests, with runtime imports deferred and unavailable runtimes reported explicitly. Extend existing test_mujoco_collection.py for normalized centers and unified bias while preserving viewer/lifecycle tests. No production simulation runs during Specify; Q22 defines the later controlled verification budget.

CR2 interface approval: Q23 explicitly approved this final concrete section, including exact configuration/signature/schema contracts and the two necessary new code/test files. Earlier Draft proposals are historical and subordinate to this section. Implementation and Plan are not authorized by this specification approval.

### User-approved Implement amendment: action mapping and throughput

The user explicitly removed action scale/offset/clip handling from mapping/pack_actions. This supersedes the Q18 inverse-transform portion. PACE task configs explicitly use scale=1, offset=0, clip=None and use_default_offset=False; helper does not inspect or compensate these settings. pack_actions accepts any batch size, enabling trajectory packing before collection/fit loops. Target finiteness belongs to collection preflight/reference loader.

Collection uses contiguous full-state GPU buffers, gathers declared response columns after simulation and performs one completed-data transfer. Finiteness checks cover every environment, every sample and the final state before returning; automatic resets/termination still abort immediately. Buffer cost is 8*(N+1)*B*J bytes. Real timestamps remain pre-step seconds from the simulation counter.

### User-authorized kitless argument registration fix

`add_runtime_args(parser: argparse.ArgumentParser) -> None` in the existing shared helper registers device/logging/determinism/viewer-capacity flags and inert Kit options without importing backend implementations. Physics and visualizer selectors remain owned by installed `setup_preset_cli`; explicit device selection is marked after parsing. Both collection and fitting retain `launch_simulation`, which resolves runtime requirements after configuration selection. Isaac Lab source is explicitly out of scope and remains unchanged. No new files or backend fallback are introduced.

### User-authorized fitting throughput follow-up

`tell(sim_dof_pos, real_dof_pos, *, sim_dof_vel=None, real_dof_vel=None)` additionally accepts complete trajectory chunks `[P,T,L]` / `[P,T,W]`, while preserving `[P,L]` / `[P,W]` calls. All inputs in a call use the same dimensionality, population, sample count and optimizer device. Require T>=1 and cumulative samples<=N; unsupported shapes/device or nonfinite values raise ValueError before changing counters, response buffers or errors. Inputs are physical simulated positions and measured-frame references; candidate bias is still subtracted exactly once. Each chunk accumulates float64 per-joint mean squared errors summed over time; evolve divides by total N and applies unchanged scales/weights. Reduction order may cause floating-point roundoff differences relative to stepwise summation.

`fit_reference` retains CPU timestamp scalars and prepacked commands; preallocates `[N+1,P,J]` full position/velocity buffers reused across generations. Additional state storage is 8*(N+1)*P*J bytes, excluding existing optimizer response/reference buffers and temporary scoring arrays. It validates every recorded state and final state before calling batched tell/evolve. Termination/reset signals stop immediately; invalid or incomplete runs never become best results. No caller may score the final post-step state as a reference sample.

CMA candidate arrays and completed generation statistics cross CPU/device boundaries in batches. Best-result identity, strict tie handling, parameter ordering, persisted formats and stopping rules are unchanged; saved settings are a dictionary snapshot belonging to that candidate.

### User-requested plot_trajectory refactor

Existing `load_result(path: str|Path)->dict` now validates every field consumed by plotting and summary: schema-v2 metadata, finite increasing time (N>=2), unique/disjoint nonempty leg group and optional wheel group, measured/desired/fitted floating tensors with matching [N,J], finite 1-D parameters and matching names, nonnegative candidate/delay identity, positive normalization, and agreement of persisted/recomputed errors. It loads onto CPU with weights_only=True; invalid records raise ValueError and IO failures retain OSError semantics. `result_errors` and `plot_result` retain their existing contracts; the latter returns position/velocity figures without applying bias twice.

`main(argv)->int` adds --task (default Isaac-Pace-Anymal-D-v0, strips namespace prefix). --robot_name remains a mutually exclusive legacy directory selector. --folder_name chooses a named run; otherwise choose the latest directory by mtime/name with all required files. Search current logs/pace-sim2real/<task> before historical logs/pace/<task>; explicit folders can fall back to the historical root even if the current root exists. --plot_score also requires progress.pt with nonempty finite floating scores_buffer[G,P]. Means remain unpaired parameter diagnostics. CLI validation/IO errors exit2 with argparse diagnostics; successful inspection exits0. No Isaac runtime import or simulation launch is required.

### Fitting timestep and result settings

The user's fitting-settings follow-up supersedes the two timestep fields above. Fitting requires `env_cfg.decimation == 1` and a finite positive `env_cfg.sim.dt` (seconds). Reference validation, rollout timing and conversion of applied delay steps to seconds use this interval. Collection retains its control interval. Each saved artifact carries the canonical leg and wheel orders at its top level. Optional reference order declarations are checked at load time. Settings contain `dt`, the resolved backend config class name and a compact solver identifier (Newton solver config class or PhysX solver type).

### Joint-specific fit scales and CMA distribution means

Each error scale accepts a float or list of floats, strictly positive and finite. Lists follow the corresponding leg or wheel order with exact group length, including zero for an empty wheel group. Group scores average joint MSE divided by squared joint scale. Saved raw RMSE uses physical units. The fitter and plotter use the same objective for scalar and list configurations. Every generation records the post-update CMA parameter mean in physical units to TensorBoard, using the generation index shared with the histogram and best-candidate tags.

## CR3 — 采集入口的回放契约 · Q4–Q7 已确认

三个入口模式、关节名称校验、最新运行缺文件时停止及分组误差来自 CR3-R1–R4。用户已确认 spec.md 的 Q4 修订及 Q5、Q6。回放拟合结果必须包含当前格式的 `settings.dt`（秒，有限正数），并匹配 decimation=1 的任务时步。仅提供旧双时步字段的文件报格式过时。该限制只针对拟合结果，外部轨迹文件的时间解释仍采用任务声明。

| 输入 | 默认值与行为 |
| --- | --- |
| `--task X` | 使用原固定参数采集及原输出路径。 |
| `--task X --fit_result` | 在与拟合入口相同的日志根 `logs/pace-sim2real/<规范化任务名>/` 选择启动时间最新的拟合运行。仅识别拟合器生成的时间戳子目录，先选目录再查 `best_result.pt`。无运行、文件缺失或不可读时报告路径并结束。 |
| `--task X --fit_result PATH` | 读取指定的配对结果并执行同一套名称与物理语义检查。选择结果不改变任务。 |
| `--trajectory_file PATH` | 可选的回放轨迹。省略时沿用现有扫频命令。文件模式的关节列按任务顺序，时间按任务 strict 或显式 legacy_index 规则解释。仅在回放模式接受，与显式扫频参数互斥。 |
| `--output PATH`、`--plot` | 前者仅在回放时使用，按需原子保存已完成的响应，输出不可指向受保护的输入或常规采集文件。后者沿用现有绘图开关。 |

**参数数据。** 在 CPU 读取的配对结果含 `leg_order`、`wheel_order`、一维有限物理参数 `params[P]` 和一一对应的 `parameter_names[P]`。以两个任务分组核对名称，再按种类与关节名恢复 armature、damping、friction（每个受控关节各一项，非负），encoder_bias（每条腿关节一项，rad，轮补零）及一个共享 delay。应用整数 `delay_steps`，须等于连续候选值向下取整，且 `delay_seconds` 与步数乘时步一致并满足执行器延迟容量。Newton 写单一干摩擦；PhysX 可选的完整 friction_ratio 块限于 [0,1]，有比例时动摩擦取静摩擦乘比例，无比例时取静摩擦。报告不一致的字段、关节组或参数名。

**轨迹与测量。** T 为样本数，L、W 分别为腿和轮关节数。文件包含 `time[T]`、`dof_pos[T,L]`、`des_dof_pos[T,L]`；W>0 时另含 `dof_vel[T,W]`、`des_dof_vel[T,W]`。沿用现有参考加载器的有限性、列宽和时钟校验。回放输出采用同样字段，time 为以秒计的相对步前时刻，位置为测量坐标的 rad，轮速为 rad/s。拟合结果参数的按名重排只作用于具名结果，验证文件列仍遵循任务声明。模型腿位置按 q−bias 记录一次，输出 des 字段取延迟前命令。

**指标。** 对每个存在的响应组计算 `sqrt(mean((replay - measured)^2))`，平均覆盖时间和该组全部关节。仅命令输入时没有实测预测误差。图例区分期望、实测、模型响应；同轨迹复现另行比较 `best_result.pt` 中成对保存的模拟响应。

**播放行为。** Q7 的两项容差仅由短程复现验收测试使用。对于有效输入，误差超限时 CLI 仍完整播放，按请求绘图、保存并正常退出。有实测轨迹时照常报告预测 RMSE。

## CR4 · 部分关节参考与结果接口 · Specify 已批准

批准依据：用户确认“批准最终契约并进入 Plan，按上述验收条件拆分任务”。

**角色。** 任务的完整控制分组、参考文件的有序分组和执行器组各有独立含义。可从任意非空的位置或速度子集构造参考。任务中的每个选中名称必须唯一，并属于相应跟踪类型；无名张量列由用户按文件实际顺序声明。拟合记录的具名参数、结果内的响应及文件回放的误差均须按名称对齐。动作列按环境已有名称映射填充。

**参考文件契约。** 输入仍为浮点张量字典。T 为至少两个采样点，P 和 V 分别为选中的位置和速度关节数，P+V>0。时间为 time[T]，单位秒，沿用 strict 或显式声明真实时间间隔的旧索引模式。P>0 时成对提供 dof_pos[T,P]、des_dof_pos[T,P]（rad）；V>0 时成对提供 dof_vel[T,V]、des_dof_vel[T,V]（rad/s）。缺失组可以省略相应字段。测量及期望均要求有限，期望值对应延迟前命令。独立轨迹按组名集合与当前结果匹配，并按文件声明的顺序读取。

**参数与输出契约。** 设 J=P+V，基础物理参数向量按所选关节排列，含 3J 项机械量、P 项编码器偏置和 1 项共享延迟；启用 PhysX 单独动摩擦比例时另有 J 项。未记录关节沿用任务加载后的逐关节参数，延迟以执行器组为单位。对于纯速度输入，保存的物理误差为 rad/s，位置组指标不适用。已有单一 dt 配对结果的读取、子集输出格式和未记录状态的具体表示分别以 spec.md 中 Q7–Q9 的答复为准。

### CR4 配置契约 · Q10–Q12 已确认

Q7–Q9 已确认。未记录位置关节取物理初角等于编码器保持角加默认偏置、初速零；未记录速度关节取任务默认角和保持速度。共享候选延迟写入每个含记录关节的完整执行器组，其余组保持默认延迟。现有全量输入的配对结果继续使用单一 dt 的 v2；部分或纯速度结果使用 v3，记录选中关节、完整分组、保持目标及延迟作用范围。

- Q10 文件列（用户已确认）。独立解释 PaceCfg.reference_leg_order、reference_wheel_order（各为 list[str] 或 None）。每组的 None 表示该组按任务全序读取，空列表表示文件没有该组，非空列表按文件实际列序列出完整关节名。两组都为空、名称重复、未知或所属类型错误时给出诊断。旧任务无额外配置时沿用原组序。
- Q11 保持目标（按用户修订确认）。直接使用 ArticulationCfg.init_state 经任务解析的逐关节值。对未记录位置关节，恒定的编码器坐标目标为默认物理角减默认偏置，首帧物理角按 Q7 加回同一偏置，首速为零。对未记录速度关节，恒定速度目标及首速均取默认关节速度，首角取默认物理角。调整保持工况时修改该任务的 init_state，共用同一来源。此前单列保持目标字典的提案已由该决定取代。
- Q12 参数边界与尺度（已确认）。bounds_params 按完整任务分组布局，逐关节误差尺度按相应完整分组顺序配置，标量尺度继续广播。对每个块按记录名称抽取并重排，共享延迟单列保留，摩擦比例块依后端配置处理。

**Q10 验收示例（X5）。** 当两个字段依次为 `[]` 和 `None`，文件为全四轮速度；依次为 `None` 和 `[]`，文件为全十二腿位置。依次为 `["RR_calf_joint", "FL_hip_joint"]` 和 `["FR_foot_joint"]`，位置列 0 对应右后小腿、列 1 对应左前髋，速度列 0 对应右前轮。两个字段各自解析后再检查总记录关节数大于零；任务本身没有轮时，速度侧的 `None` 自然展开为空。

### 回放与配对结果汇总

**轨迹来源（Q13–Q14 已确认）。** 提供轨迹文件时按本次 reference_* 声明解析两组，并与结果中的选中集合逐组核对。省略轨迹文件时以具名结果中的选中集合作为扫频对象。两条路径均从当前任务已解析的 init_state 与默认偏置计算其余关节的保持目标，与拟合时记录的目标按名称比较；有变化时输出旧值、新值和单位并使用新值。后端、求解器、时步、延迟模式、延迟作用组及关节跟踪类型继续校验。显式另存时只输出选中通道的期望与预测张量，时间和列顺序与本次轨迹相符；有实测才输出预测 RMSE。

**v3 字段布局（已批准）。** best_result.pt 保留配对候选的 parameter_names、params、generation、candidate_index、time、reference、score 及已有延迟字段。顶层 leg_order、wheel_order 为本次选中通道的列序；sim_dof_pos 和 sim_dof_vel 仅保存有效组的 [T,P] 或 [T,V] 张量。有效组的 RMSE 为原单位标量，缺失组的 RMSE 为 None。settings 沿用 dt、物理配置标识和有效评分尺度，并增加下列字段：

| 字段 | 内容 |
| --- | --- |
| task_leg_order、task_wheel_order | list[str]，任务完整位置与速度控制分组，用于名称和类型核对。 |
| hold_positions、hold_velocities | dict[str, float]，按未记录关节名记录拟合时实际发出的保持目标，单位分别为 rad（编码器坐标）与 rad/s。 |
| delay_actuator_groups | dict[str, list[str]]，列出应用候选延迟的执行器组名及每组全部成员。单组内的成员用名称核对；不同执行器组之间仍共享一个候选延迟。 |

已有单一 dt 的全量配对结果沿用 v2。v3 应允许同一集合按文件列序重排，并继续保护拟合结果、参考文件与默认采集输出。

### 采集与拟合默认文件名（Verify 后用户确认）

两个来源共用项目根或 `PACE_ROOT` 下的 `data/<规范化任务名>/` 目录。Isaac Lab 固定采集写入 `chirp_data.pt`，也是 `PaceCfg.data_dir` 的默认值。原生 X5 MuJoCo 写入 `data/Isaac-Pace-Sevnce-X5-v0/mujoco_chirp_data.pt`。从该记录拟合时给出 `env.sim2real.data_dir=mujoco_chirp_data.pt`。频率、增益和时长变化时文件名保持稳定，成功采集替换同来源的默认记录。回放另存时保护对应任务的默认采集文件和显式输入。此前按实验命名的文件仍可通过相对或绝对路径选择。
