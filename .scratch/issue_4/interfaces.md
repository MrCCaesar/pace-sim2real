# Issue #4 — Interfaces

Status: Approved as planning baseline by user request to enter Plan based on these documents. Project APIs below are implemented in commit 87da096.

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
