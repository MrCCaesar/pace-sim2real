# © 2025 ETH Zurich, Robotic Systems Lab
# Author: Filip Bjelonic
# Licensed under the Apache License 2.0

"""Shared Isaac Lab runtime and sampling routines for PACE trajectories."""

import argparse
import contextlib
import math
import os
import sys
import warnings
from pathlib import Path

import gymnasium as gym
import torch
from torch import pi

from isaaclab.app.sim_launcher import fuse_kit_args
from isaaclab.utils import validate

from isaaclab_rl.entrypoints.common import (
    add_video_args,
    apply_env_overrides,
    apply_video_recording,
    close_env,
    enable_cameras_for_video,
    normalize_task_name,
    pre_launch_video_config,
)

from isaaclab_tasks.utils import setup_preset_cli

from .collection_contracts import (
    add_runtime_args,
    pack_actions,
    resolve_action_mapping,
    resolve_joint_groups,
)
from .fit_replay import JointParameters
from .paths import ISAAC_COLLECTION_FILENAME, project_root


def prepare_task(env_cfg, args_cli):
    legs, wheels = resolve_joint_groups(env_cfg.sim2real)
    env_cfg.sim2real.leg_order = list(legs)
    env_cfg.sim2real.wheel_order = list(wheels)
    env_cfg.sim2real.joint_order = list(legs + wheels)
    apply_env_overrides(args_cli, env_cfg)
    args_cli.device = env_cfg.sim.device

    pre_launch_video_config(env_cfg, args_cli)
    task_name = normalize_task_name(args_cli.task)
    log_dir = os.path.abspath(os.path.join("logs", "pace-sim2real", task_name))
    try:
        validate(env_cfg)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"Invalid environment configuration: {exc}") from None

    default_output = project_root() / "data" / task_name / ISAAC_COLLECTION_FILENAME
    return Path(log_dir), default_output


@contextlib.contextmanager
def trajectory_environment(env_cfg, args_cli, log_dir):
    apply_video_recording(env_cfg, str(log_dir), args_cli, subdir="play")
    env = gym.make(args_cli.task, cfg=env_cfg)
    try:
        yield env
    finally:
        close_env(env)


def run_full_trajectory(env, args_cli, parameters, legs, wheels, *, reference=None, delay_mode=None, control=None):
    """Preserve the full collection and v2 initial-state conventions."""
    articulation = env.unwrapped.scene["robot"]
    mapping = resolve_action_mapping(env.unwrapped, legs, wheels)
    leg_ids, wheel_ids = mapping["leg_ids"], mapping["wheel_ids"]
    joint_ids = torch.tensor(leg_ids + wheel_ids, device=env.unwrapped.device)
    env_ids = torch.arange(env.unwrapped.num_envs, device=env.unwrapped.device)
    bias = _configure_joints(env, articulation, joint_ids, env_ids, parameters, delay_mode)
    if reference is None:
        leg_trajectory, wheel_trajectory = full_chirp(args_cli, env.unwrapped, legs, wheels)
        initial_leg_position = leg_trajectory[0]
        velocity = torch.zeros_like(bias)
    else:
        leg_trajectory = reference["des_dof_pos"]
        wheel_trajectory = reference["des_dof_vel"] if wheels else None
        initial_leg_position = reference["dof_pos"][0].to(joint_ids.device)
        velocity = articulation.data.default_joint_vel.torch[:, joint_ids].clone()
        if wheels:
            velocity[:, len(legs) :] = reference["dof_vel"][0].to(joint_ids.device)
            articulation.write_joint_position_to_sim_index(
                position=articulation.data.default_joint_pos.torch[:, wheel_ids].contiguous(),
                joint_ids=wheel_ids,
                env_ids=env_ids,
            )
    articulation.write_joint_position_to_sim_index(
        position=(initial_leg_position + bias[:, : len(legs)]).contiguous(),
        joint_ids=leg_ids,
        env_ids=env_ids,
    )
    articulation.write_joint_velocity_to_sim_index(velocity=velocity, joint_ids=joint_ids, env_ids=env_ids)
    return collect_trajectory(env, leg_trajectory, wheel_trajectory, bias[:, : len(leg_ids)], control=control)


def run_subset_trajectory(env, args, parameters, control, *, reference=None):
    base = env.unwrapped
    legs, wheels = control.legs, control.wheels
    control.check_delay(parameters.delay_steps)
    if reference is None:
        pos, vel = named_chirp(args, base.step_dt, base.device, legs, wheels)
        first_pos = pos[0]
        first_vel = None if vel is None else torch.zeros_like(vel[0])
    else:
        pos = reference.get("des_dof_pos", torch.empty((len(reference["time"]), 0))).to(base.device)
        vel = reference["des_dof_vel"].to(base.device) if wheels else None
        first_pos = reference["dof_pos"][0].to(base.device) if legs else pos[0]
        first_vel = reference["dof_vel"][0].to(base.device) if wheels else None

    def population(value):
        return value.to(base.device).expand(base.num_envs, -1)

    bias = population(parameters.bias[: len(legs)])
    delay = torch.full((base.num_envs,), parameters.delay_steps, device=base.device, dtype=torch.long)
    dynamic = _dynamic_friction(env, parameters)
    env.reset()
    control.apply(
        population(parameters.armature),
        population(parameters.damping),
        population(parameters.friction),
        population(dynamic) if dynamic is not None else None,
        bias,
        delay,
        first_pos,
        first_vel,
    )
    return collect_trajectory(env, pos, vel, bias, control=control)


def _dynamic_friction(env, parameters):
    """Resolve the backend after launch, before writing mechanical parameters."""
    physics_cfg = env.unwrapped.sim.cfg.physics
    physics_cfg_modules = {cls.__module__.split(".")[0] for cls in type(physics_cfg).__mro__}
    if "isaaclab_newton" in physics_cfg_modules:
        from isaaclab_newton.physics import NewtonCfg

        expected_cfg_type = NewtonCfg
    elif "isaaclab_ov" in physics_cfg_modules:
        from isaaclab_ov.physics import OvPhysxCfg

        expected_cfg_type = OvPhysxCfg
    elif "isaaclab_physx" in physics_cfg_modules:
        from isaaclab_physx.physics import PhysxCfg

        expected_cfg_type = PhysxCfg
    else:
        raise NotImplementedError(f"PACE parameter writes are unsupported for {type(physics_cfg).__name__}.")
    if not isinstance(physics_cfg, expected_cfg_type):
        raise NotImplementedError(f"PACE parameter writes are unsupported for {type(physics_cfg).__name__}.")

    if "isaaclab_newton" in physics_cfg_modules:
        if not torch.equal(parameters.friction, parameters.dynamic_friction):
            warnings.warn(
                "Newton does not support separate static/dynamic joint friction. "
                "Using friction as the dry-friction effort and ignoring dynamic_friction; "
                "this is not equivalent to the PhysX friction model. "
                "Support for this effort depends on the selected Newton solver.",
                RuntimeWarning,
                stacklevel=2,
            )
        return None
    return parameters.dynamic_friction


def _configure_joints(env, articulation, joint_ids, env_ids, parameters: JointParameters, delay_mode):
    drives = []
    coverage = torch.zeros(len(joint_ids), dtype=torch.long, device=joint_ids.device)
    for drive_type in articulation.actuators:
        actuator = articulation.actuators[drive_type]
        if not callable(getattr(actuator, "update_time_lags", None)) or not callable(
            getattr(actuator, "update_encoder_bias", None)
        ):
            raise TypeError(f"Actuator {drive_type!r} does not support PACE delay and encoder bias updates.")
        if delay_mode is not None and actuator.cfg.delay_mode != delay_mode:
            raise ValueError(f"Incompatible actuator delay mode for {drive_type}")
        drive_indices = actuator.joint_indices
        if isinstance(drive_indices, slice):
            all_idx = torch.arange(articulation.num_joints, device=joint_ids.device)
            drive_indices = all_idx[drive_indices]
        else:
            drive_indices = torch.as_tensor(drive_indices, dtype=torch.long, device=joint_ids.device)
        comparison_matrix = joint_ids.unsqueeze(1) == drive_indices.unsqueeze(0)
        if not torch.all(comparison_matrix.sum(dim=0) == 1):
            raise ValueError(f"Each joint in actuator {drive_type!r} must occur exactly once in joint_order.")
        drive_joint_idx = torch.argmax(comparison_matrix.int(), dim=0)
        coverage += comparison_matrix.sum(dim=1)
        if parameters.delay_steps > actuator.cfg.max_delay:
            raise ValueError("Collection delay exceeds actuator capacity")
        drives.append((actuator, drive_joint_idx))
    if not (coverage == 1).all():
        raise ValueError("Every controlled joint must have exactly one PACE actuator")

    env.reset()

    def rows(value):
        return value.to(joint_ids.device).expand(len(env_ids), len(joint_ids)).contiguous()

    dynamic = _dynamic_friction(env, parameters)
    bias = rows(parameters.bias)
    articulation.write_joint_armature_to_sim_index(
        armature=rows(parameters.armature), joint_ids=joint_ids, env_ids=env_ids
    )
    articulation.write_joint_friction_coefficient_to_sim_index(
        joint_friction_coeff=rows(parameters.friction),
        joint_dynamic_friction_coeff=rows(dynamic) if dynamic is not None else None,
        joint_viscous_friction_coeff=rows(parameters.damping),
        joint_ids=joint_ids,
        env_ids=env_ids,
    )

    time_lag = torch.full((len(env_ids),), parameters.delay_steps, dtype=torch.long, device=joint_ids.device)
    for actuator, drive_joint_idx in drives:
        actuator.update_time_lags(time_lag)
        actuator.update_encoder_bias(bias[:, drive_joint_idx])
        actuator.reset(env_ids)
    return bias


def full_chirp(args, base, legs, wheels):
    """Built-in robots use named coefficients; custom full sweeps retain task order."""
    if normalize_task_name(args.task) in (
        "Isaac-Pace-Sevnce-X5-v0",
        "Isaac-Pace-Sevnce-X3mini-v0",
        "Isaac-Pace-Anymal-D-v0",
    ):
        return named_chirp(args, base.step_dt, base.device, legs, wheels)
    task_legs, task_wheels = resolve_joint_groups(base.cfg.sim2real)
    pos, vel = _chirp_targets(args, base.step_dt, base.device, len(task_legs), len(task_wheels))
    return pos[:, [task_legs.index(n) for n in legs]], (
        vel[:, [task_wheels.index(n) for n in wheels]] if vel is not None else None
    )


class UnknownChirpJoints(ValueError):
    """The requested joints have no named sweep coefficients."""


def named_chirp(args, dt, device, legs, wheels):
    """Select from the supported task sweeps by exact joint name."""
    x5_legs = [f"{side}_{kind}_joint" for side in ("FL", "FR", "RL", "RR") for kind in ("hip", "thigh", "calf")]
    x5_wheels = [f"{side}_foot_joint" for side in ("FL", "FR", "RL", "RR")]
    anymal_legs = [f"{side}_{kind}" for side in ("LF", "RF", "LH", "RH") for kind in ("HAA", "HFE", "KFE")]
    x3_wheels = [f"{side}_WHEEL" for side in ("LF", "RF", "LH", "RH")]
    for leg_order, wheel_order in ((x5_legs, x5_wheels), (anymal_legs, x3_wheels)):
        if set(legs) <= set(leg_order) and set(wheels) <= set(wheel_order):
            pos, vel = _chirp_targets(args, dt, device, len(leg_order), len(wheel_order))
            return (
                pos[:, [leg_order.index(n) for n in legs]],
                vel[:, [wheel_order.index(n) for n in wheels]] if vel is not None and wheels else None,
            )
    raise UnknownChirpJoints(f"No named chirp coefficients for selection: {(*legs, *wheels)}")


def _chirp_targets(args_cli, dt, device, num_legs, num_wheels):
    # Create a chirp signal for each action dimension
    duration = args_cli.duration  # seconds

    ratio = duration / dt
    if not math.isfinite(ratio) or ratio < 1 or abs(ratio - round(ratio)) > 1e-9:
        raise ValueError("duration must be a positive integer multiple of control dt")
    if not 0 < args_cli.min_frequency <= args_cli.max_frequency < 0.5 / dt:
        raise ValueError("Invalid chirp frequencies or Nyquist limit")
    num_steps = round(ratio)
    # Pre-step sample times in seconds: duration is the end of the last step.
    sample_times = torch.arange(num_steps, device=device, dtype=torch.float64) * dt
    f0 = args_cli.min_frequency  # Hz
    f1 = args_cli.max_frequency  # Hz

    # Linear chirp: phase = 2*pi*(f0*t + (f1-f0)/(2*duration)*t^2)
    phase = 2 * pi * (f0 * sample_times + ((f1 - f0) / (2 * duration)) * sample_times**2)
    chirp_signal = torch.sin(phase)

    leg_trajectory = torch.zeros((num_steps, num_legs), device=device)
    leg_trajectory[:, :] = chirp_signal.unsqueeze(-1)
    leg_trajectory_directions = torch.tensor(
        [1.0, 1.0, 1.0, -1.0, 1.0, 1.0, 1.0, 1.0, 1.0, -1.0, 1.0, 1.0], device=device
    )
    leg_trajectory_bias = torch.tensor([0.0, 0.4, -1.4] * 4, device=device)
    leg_trajectory_scale = torch.tensor([0.25, 0.5, 0.99] * 4, device=device)
    leg_trajectory[:, :] = (
        (leg_trajectory + leg_trajectory_bias.unsqueeze(0))
        * leg_trajectory_directions.unsqueeze(0)
        * leg_trajectory_scale.unsqueeze(0)
    )

    wheel_trajectory = None
    if num_wheels:
        wheel_trajectory = torch.zeros((num_steps, num_wheels), device=device)
        wheel_trajectory[:, :] = chirp_signal.unsqueeze(-1)
        wheel_trajectory_directions = torch.tensor([1.0, 1.0, 1.0, 1.0], device=device)
        wheel_trajectory_scale = torch.tensor([10.0, 10.0, 10.0, 10.0], device=device)
        wheel_trajectory[:, :] = (
            (wheel_trajectory + 0.0) * wheel_trajectory_directions.unsqueeze(0) * wheel_trajectory_scale.unsqueeze(0)
        )
    return leg_trajectory, wheel_trajectory


def save_collection(collected, output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    # Serialize completely before replacing a previous successful collection.
    import tempfile

    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as stream:
            temporary = stream.name
            torch.save(collected, stream)
        os.replace(temporary, output)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def plot_collection(collected, legs, wheels, replay, reference):
    import matplotlib.pyplot as plt

    groups = [(legs, "dof_pos", "rad")]
    if wheels:
        groups.append((wheels, "dof_vel", "rad/s"))
    for names, field, unit in groups:
        for i, name in enumerate(names):
            _, axis = plt.subplots()
            axis.plot(collected["time"], collected[field][:, i], label="Model response" if replay else "Measured")
            axis.plot(collected["time"], collected["des_" + field][:, i], label="Desired (before delay)")
            if reference is not None:
                axis.plot(collected["time"], reference[field][:, i], label="Measured")
            axis.set(title=name, xlabel="Time [s]", ylabel=f"Joint [{unit}]")
            axis.legend()
    plt.show()


@torch.inference_mode()
def collect_trajectory(env, leg_trajectory, wheel_trajectory, bias, *, control=None):
    """Collect pre-step measurements on-device, then transfer completed data once.

    Trajectories have shape [samples, joints]; bias is [environments, legs].
    Commands are packed once. Only environment zero is saved, while invalid
    state in any sample rejects the collection before saving; termination stops
    immediately. Full-state buffers use 8 * (samples + 1) * environments * joints bytes.
    """
    base = getattr(env, "unwrapped", env)
    legs, wheels = resolve_joint_groups(base.cfg.sim2real)
    mapping = control.mapping if control else resolve_action_mapping(base, legs, wheels)
    leg_ids, wheel_ids = mapping["leg_ids"], mapping["wheel_ids"]
    if control:
        legs, wheels = control.legs, control.wheels
        leg_ids, wheel_ids = control.leg_ids, control.wheel_ids
    robot = base.scene["robot"]
    if base.cfg.sim.use_newton_actuators:
        raise ValueError("Collection requires Python PACE actuators")
    count = len(leg_trajectory)
    if count < 1:
        raise ValueError("Collection requires at least one trajectory sample")
    leg_targets = leg_trajectory.to(device=base.device, dtype=torch.float32)
    if leg_targets.shape != (count, len(legs)):
        raise ValueError("Position target shape must match sample count and recorded legs")
    if wheels and wheel_trajectory is None:
        raise ValueError("Mixed collection requires wheel velocity targets")
    wheel_targets = (
        wheel_trajectory.to(device=base.device, dtype=torch.float32) if wheel_trajectory is not None else None
    )
    if wheel_targets is not None and wheel_targets.shape != (count, len(wheels)):
        raise ValueError("Velocity target shape must match sample count and recorded wheels")
    pos, vel = control.targets(leg_targets, wheel_targets) if control else (leg_targets, wheel_targets)
    actions = pack_actions(mapping, pos, vel)
    if bias.shape != (base.num_envs, len(legs)) or bias.device != actions.device:
        raise ValueError("Encoder bias must match environment/leg dimensions and device")
    if not torch.isfinite(actions).all() or not torch.isfinite(bias).all():
        raise ValueError("Collection targets and bias must be finite")
    # Broadcasting shares identical commands across environments without repeated allocations.
    actions = actions.unsqueeze(1).expand(-1, base.num_envs, -1)
    # Copy contiguous states in the loop; gather named joints and check finiteness once.
    # Include every environment and the final post-step state so no invalid sample is missed.
    state_shape = (count + 1, base.num_envs, robot.num_joints)
    positions = torch.empty(state_shape, device=base.device, dtype=torch.float32)
    velocities = torch.empty_like(positions)
    timestamps = []
    origin = base._sim_step_counter
    for step in range(count):
        if not base.sim.is_running():
            raise RuntimeError("Simulation closed before collection completed")
        elapsed = (base._sim_step_counter - origin) * base.physics_dt
        if abs(elapsed - step * base.step_dt) > 1e-7 + 1e-5 * step * base.step_dt:
            raise RuntimeError("Simulation time reset or diverged")
        timestamps.append(elapsed)
        positions[step].copy_(robot.data.joint_pos.torch)
        velocities[step].copy_(robot.data.joint_vel.torch)
        result = env.step(actions[step])
        if len(result) == 5 and (result[2] | result[3]).any():
            raise RuntimeError("Environment terminated/reset during collection")

    positions[-1].copy_(robot.data.joint_pos.torch)
    velocities[-1].copy_(robot.data.joint_vel.torch)
    if not (torch.isfinite(positions).all() & torch.isfinite(velocities).all()):
        raise RuntimeError("Nonfinite collection state")
    recorded = {"time": torch.tensor(timestamps, dtype=torch.float64)}
    if legs:
        recorded.update(dof_pos=(positions[:-1, 0, leg_ids] - bias[0]).cpu(), des_dof_pos=leg_targets.cpu())
    if wheels and wheel_targets is not None:
        recorded.update(dof_vel=velocities[:-1, 0, wheel_ids].cpu(), des_dof_vel=wheel_targets.cpu())
    return recorded


def trajectory_parser(description):
    parser = argparse.ArgumentParser(description=description, allow_abbrev=False)
    parser.add_argument(
        "--disable_fabric", action="store_true", default=False, help="Disable fabric and use USD I/O operations."
    )
    parser.add_argument("--num_envs", type=int, default=1, help="Number of environments to simulate.")
    parser.add_argument("--task", type=str, default=None, help="Name of the task.")
    parser.add_argument(
        "--max_steps", type=int, default=None, help="Number of environment steps to run. Runs unbounded when omitted."
    )
    parser.add_argument("--min_frequency", type=float, help="Minimum frequency for the chirp signal in Hz.")
    parser.add_argument("--max_frequency", type=float, help="Maximum frequency for the chirp signal in Hz.")
    parser.add_argument("--duration", type=float, help="Duration of the chirp signal in seconds.")

    parser.add_argument("--plot", action="store_true", help="Plot collected joint responses after saving.")
    add_video_args(parser, action="the trajectory run")
    add_runtime_args(parser)
    parser.set_defaults(device=None, visualizer=["newton_gl"])
    return parser


def parse_runtime_args(parser, argv, *, removed_options=()):
    arguments = fuse_kit_args(sys.argv[1:] if argv is None else argv)
    args_cli, hydra_args = setup_preset_cli(parser, arguments)
    for token in hydra_args:
        if token.partition("=")[0] in removed_options:
            parser.error(f"{token} is a replay option; use scripts/pace/replay.py")
    args_cli.device_explicit = args_cli.device is not None
    enable_cameras_for_video(args_cli)
    sys.argv = [sys.argv[0]] + hydra_args
    return args_cli


def set_chirp_defaults(args_cli):
    for name, default in (("min_frequency", 0.1), ("max_frequency", 10.0), ("duration", 20.0)):
        if getattr(args_cli, name) is None:
            setattr(args_cli, name, default)
