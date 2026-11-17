# © 2025 ETH Zurich, Robotic Systems Lab
# Author: Filip Bjelonic
# Licensed under the Apache License 2.0

# Warp captures ``enable_backward`` when a module is created, which happens at import
# time, so it has to be set before importing anything that defines Warp kernels.
# Isaac Lab does not use Warp autodiff; skipping adjoint codegen roughly halves the
# time spent building kernels on a cold kernel cache.
import warp as wp

wp.config.enable_backward = False
"""Script to run an environment with zero action agent."""

"""Launch Isaac Sim Simulator first."""

import argparse
import contextlib
import os
import sys
import warnings

import gymnasium as gym
import isaaclab_tasks  # noqa: F401
import torch
from isaaclab.app import launch_simulation
from isaaclab.app.sim_launcher import fuse_kit_args
from isaaclab.cli import load_external_tasks
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
from isaaclab_tasks.utils import resolve_task_config, setup_preset_cli

"""Rest everything follows."""

from typing import Any

from torch import pi

from pace_sim2real.utils import project_root
from pace_sim2real.utils.collection_contracts import (
    add_runtime_args,
    pack_actions,
    resolve_action_mapping,
    resolve_joint_groups,
)

_SEED = 42


def main(argv: list[str] | None = None):
    load_external_tasks()
    args_cli = _parse_args(argv)
    torch.manual_seed(_SEED)

    # parse configuration
    env_cfg: Any
    env_cfg, _ = resolve_task_config(args_cli.task, "")
    legs, wheels = resolve_joint_groups(env_cfg.sim2real)
    env_cfg.sim2real.leg_order = list(legs)
    env_cfg.sim2real.wheel_order = list(wheels)
    env_cfg.sim2real.joint_order = list(legs + wheels)
    apply_env_overrides(args_cli, env_cfg)
    args_cli.device = env_cfg.sim.device

    pre_launch_video_config(env_cfg, args_cli)
    log_dir = os.path.abspath(os.path.join("logs", "pace-sim2real", normalize_task_name(args_cli.task)))
    try:
        validate(env_cfg)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"Invalid environment configuration: {exc}") from None

    with launch_simulation(env_cfg, args_cli), contextlib.ExitStack() as cleanup:
        apply_video_recording(env_cfg, log_dir, args_cli, subdir="play")
        # create environment
        env: Any = gym.make(args_cli.task, cfg=env_cfg)
        cleanup.callback(lambda: close_env(env))

        # print info (this is vectorized environment)
        print(f"[INFO]: Gym observation space: {env.observation_space}")
        print(f"[INFO]: Gym action space: {env.action_space}")

        # reset environment
        articulation = env.unwrapped.scene["robot"]

        legs_order, wheels_order = resolve_joint_groups(env_cfg.sim2real)
        mapping = resolve_action_mapping(env.unwrapped, legs_order, wheels_order)
        leg_ids, wheel_ids = mapping["leg_ids"], mapping["wheel_ids"]
        joint_ids = torch.tensor(leg_ids + wheel_ids, device=env.unwrapped.device)

        armature = torch.tensor([0.1] * len(joint_ids), device=env.unwrapped.device).unsqueeze(0)
        damping = torch.tensor([4.5] * len(joint_ids), device=env.unwrapped.device).unsqueeze(0)
        friction = torch.tensor([0.05] * len(joint_ids), device=env.unwrapped.device).unsqueeze(0)  # static friction
        dynamic_friction = 0.5 * friction  # dynamic friction (must not exceed static friction)
        bias = torch.full_like(armature, 0.05)
        bias[:, len(leg_ids) :].fill_(0.0)  # no bias for wheels
        env_ids = torch.arange(env.unwrapped.num_envs, device=env.unwrapped.device)
        time_lag = torch.full((len(env_ids),), 5, dtype=torch.long, device=env.unwrapped.device)
        drives = []
        coverage = torch.zeros(len(joint_ids), dtype=torch.long, device=joint_ids.device)
        for drive_type in articulation.actuators:
            actuator = articulation.actuators[drive_type]
            if not callable(getattr(actuator, "update_time_lags", None)) or not callable(
                getattr(actuator, "update_encoder_bias", None)
            ):
                raise TypeError(f"Actuator {drive_type!r} does not support PACE delay and encoder bias updates.")
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
            if (time_lag > actuator.cfg.max_delay).any():
                raise ValueError("Collection delay exceeds actuator capacity")
            drives.append((actuator, drive_joint_idx))
        if not (coverage == 1).all():
            raise ValueError("Every controlled joint must have exactly one PACE actuator")

        env.reset()

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

        # Index writers expect one row per selected environment and update the data buffers themselves.
        armature, damping, friction, dynamic_friction, bias = (
            value.expand(len(env_ids), len(joint_ids)).contiguous()
            for value in (armature, damping, friction, dynamic_friction, bias)
        )
        articulation.write_joint_armature_to_sim_index(armature=armature, joint_ids=joint_ids, env_ids=env_ids)
        if "isaaclab_newton" in physics_cfg_modules:
            # Newton exposes one dry-friction effort (MJWarp: dof_frictionloss), not two coefficients.
            if not torch.equal(friction, dynamic_friction):
                warnings.warn(
                    "Newton does not support separate static/dynamic joint friction. "
                    "Using friction as the dry-friction effort and ignoring dynamic_friction; "
                    "this is not equivalent to the PhysX friction model. "
                    "Support for this effort depends on the selected Newton solver.",
                    RuntimeWarning,
                    stacklevel=2,
                )
            articulation.write_joint_friction_coefficient_to_sim_index(
                joint_friction_coeff=friction,
                joint_viscous_friction_coeff=damping,
                joint_ids=joint_ids,
                env_ids=env_ids,
            )
        else:
            articulation.write_joint_friction_coefficient_to_sim_index(
                joint_friction_coeff=friction,
                joint_dynamic_friction_coeff=dynamic_friction,
                joint_viscous_friction_coeff=damping,
                joint_ids=joint_ids,
                env_ids=env_ids,
            )

        for actuator, drive_joint_idx in drives:
            actuator.update_time_lags(time_lag)
            actuator.update_encoder_bias(bias[:, drive_joint_idx])
            actuator.reset(env_ids)

        data_dir = project_root() / "data" / normalize_task_name(args_cli.task)

        # Create a chirp signal for each action dimension
        duration = args_cli.duration  # seconds
        import math

        dt = env.unwrapped.step_dt
        ratio = duration / dt
        if not math.isfinite(ratio) or ratio < 1 or abs(ratio - round(ratio)) > 1e-9:
            raise ValueError("duration must be a positive integer multiple of control dt")
        if not 0 < args_cli.min_frequency <= args_cli.max_frequency < 0.5 / dt:
            raise ValueError("Invalid chirp frequencies or Nyquist limit")
        num_steps = round(ratio)
        # Pre-step sample times in seconds: duration is the end of the last step.
        sample_times = torch.arange(num_steps, device=env.unwrapped.device, dtype=torch.float64) * dt
        f0 = args_cli.min_frequency  # Hz
        f1 = args_cli.max_frequency  # Hz

        # Linear chirp: phase = 2*pi*(f0*t + (f1-f0)/(2*duration)*t^2)
        phase = 2 * pi * (f0 * sample_times + ((f1 - f0) / (2 * duration)) * sample_times**2)
        chirp_signal = torch.sin(phase)

        leg_trajectory = torch.zeros((num_steps, len(leg_ids)), device=env.unwrapped.device)
        leg_trajectory[:, :] = chirp_signal.unsqueeze(-1)
        leg_trajectory_directions = torch.tensor(
            [1.0, 1.0, 1.0, -1.0, 1.0, 1.0, 1.0, 1.0, 1.0, -1.0, 1.0, 1.0], device=env.unwrapped.device
        )
        leg_trajectory_bias = torch.tensor([0.0, 0.4, -1.4] * 4, device=env.unwrapped.device)
        leg_trajectory_scale = torch.tensor([0.25, 0.5, 0.99] * 4, device=env.unwrapped.device)
        leg_trajectory[:, :] = (
            (leg_trajectory + leg_trajectory_bias.unsqueeze(0))
            * leg_trajectory_directions.unsqueeze(0)
            * leg_trajectory_scale.unsqueeze(0)
        )

        wheel_trajectory = None
        if wheels_order:
            wheel_trajectory = torch.zeros((num_steps, len(wheel_ids)), device=env.unwrapped.device)
            wheel_trajectory[:, :] = chirp_signal.unsqueeze(-1)
            wheel_trajectory_directions = torch.tensor([1.0, 1.0, 1.0, 1.0], device=env.unwrapped.device)
            wheel_trajectory_scale = torch.tensor([10.0, 10.0, 10.0, 10.0], device=env.unwrapped.device)
            wheel_trajectory[:, :] = (
                (wheel_trajectory + 0.0)
                * wheel_trajectory_directions.unsqueeze(0)
                * wheel_trajectory_scale.unsqueeze(0)
            )

        articulation.write_joint_position_to_sim_index(
            position=(leg_trajectory[0].unsqueeze(0) + bias[:, : len(leg_ids)]).contiguous(),
            joint_ids=leg_ids,
            env_ids=env_ids,
        )
        articulation.write_joint_velocity_to_sim_index(
            velocity=torch.zeros_like(bias),
            joint_ids=joint_ids,
            env_ids=env_ids,
        )
        collected = collect_trajectory(env, leg_trajectory, wheel_trajectory, bias[:, : len(leg_ids)])

    data_dir.mkdir(parents=True, exist_ok=True)
    # Serialize completely before replacing a previous successful collection.
    import tempfile

    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=data_dir, delete=False) as stream:
            temporary = stream.name
            torch.save(collected, stream)
        os.replace(temporary, data_dir / "chirp_data.pt")
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)
    if args_cli.plot:
        import matplotlib.pyplot as plt

        groups = [(legs_order, "dof_pos", "rad")]
        if wheels_order:
            groups.append((wheels_order, "dof_vel", "rad/s"))
        for names, field, unit in groups:
            for i, name in enumerate(names):
                _, axis = plt.subplots()
                axis.plot(collected["time"], collected[field][:, i], label="Measured")
                axis.plot(collected["time"], collected["des_" + field][:, i], label="Desired (before delay)")
                axis.set(title=name, xlabel="Time [s]", ylabel=f"Joint [{unit}]")
                axis.legend()
        plt.show()


@torch.inference_mode()
def collect_trajectory(env, leg_trajectory, wheel_trajectory, bias):
    """Collect pre-step measurements on-device, then transfer completed data once.

    Trajectories have shape [samples, joints]; bias is [environments, legs].
    Commands are packed once. Only environment zero is saved, while invalid
    state in any sample rejects the collection before saving; termination stops
    immediately. Full-state buffers use 8 * (samples + 1) * environments * joints bytes.
    """
    base = getattr(env, "unwrapped", env)
    legs, wheels = resolve_joint_groups(base.cfg.sim2real)
    mapping = resolve_action_mapping(base, legs, wheels)
    robot = base.scene["robot"]
    if base.cfg.sim.use_newton_actuators:
        raise ValueError("Collection requires Python PACE actuators")
    count = len(leg_trajectory)
    if count < 1:
        raise ValueError("Collection requires at least one trajectory sample")
    leg_targets = leg_trajectory.to(device=base.device, dtype=torch.float32)
    if wheels and wheel_trajectory is None:
        raise ValueError("Mixed collection requires wheel velocity targets")
    wheel_targets = (
        wheel_trajectory.to(device=base.device, dtype=torch.float32) if wheel_trajectory is not None else None
    )
    actions = pack_actions(mapping, leg_targets, wheel_targets)
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
    recorded = {
        "time": torch.tensor(timestamps, dtype=torch.float64),
        "dof_pos": (positions[:-1, 0, mapping["leg_ids"]] - bias[0]).cpu(),
        "des_dof_pos": leg_targets.cpu(),
    }
    if wheel_targets is not None:
        recorded.update(dof_vel=velocities[:-1, 0, mapping["wheel_ids"]].cpu(), des_dof_vel=wheel_targets.cpu())
    return recorded


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the command line of a checkpoint-free agent and hand the remainder to Hydra."""
    parser = argparse.ArgumentParser(description="diffdrive for wheeled robot")
    parser.add_argument(
        "--disable_fabric", action="store_true", default=False, help="Disable fabric and use USD I/O operations."
    )
    parser.add_argument("--num_envs", type=int, default=1, help="Number of environments to simulate.")
    parser.add_argument("--task", type=str, default=None, help="Name of the task.")
    parser.add_argument(
        "--max_steps", type=int, default=None, help="Number of environment steps to run. Runs unbounded when omitted."
    )
    parser.add_argument(
        "--min_frequency", type=float, default=0.1, help="Minimum frequency for the chirp signal in Hz."
    )
    parser.add_argument(
        "--max_frequency", type=float, default=10.0, help="Maximum frequency for the chirp signal in Hz."
    )
    parser.add_argument("--duration", type=float, default=20.0, help="Duration of the chirp signal in seconds.")

    parser.add_argument("--plot", action="store_true", help="Plot collected joint responses after saving.")
    add_video_args(parser, action="the collection run")
    add_runtime_args(parser)
    # let task configs select the simulation device and keep checkpoint-free agents on the kitless default path
    parser.set_defaults(device=None, visualizer=["newton_gl"])
    arguments = fuse_kit_args(sys.argv[1:] if argv is None else argv)
    args_cli, hydra_args = setup_preset_cli(parser, arguments)
    args_cli.device_explicit = args_cli.device is not None
    enable_cameras_for_video(args_cli)
    sys.argv = [sys.argv[0]] + hydra_args
    return args_cli


if __name__ == "__main__":
    # run the main function
    raise SystemExit(main())
