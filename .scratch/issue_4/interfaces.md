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
