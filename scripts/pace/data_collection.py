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
from isaaclab.app import add_launcher_args, launch_simulation
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

from torch import pi

from pace_sim2real.utils import project_root

_SEED = 42


def main(argv: list[str] | None = None):
    load_external_tasks()
    args_cli = _parse_args(argv)
    torch.manual_seed(_SEED)

    # parse configuration
    env_cfg, _ = resolve_task_config(args_cli.task, "")
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
        env = gym.make(args_cli.task, cfg=env_cfg)
        cleanup.callback(lambda: close_env(env))

        # print info (this is vectorized environment)
        print(f"[INFO]: Gym observation space: {env.observation_space}")
        print(f"[INFO]: Gym action space: {env.action_space}")

        # reset environment
        articulation = env.unwrapped.scene["robot"]

        legs_order = env_cfg.sim2real.leg_order
        wheels_order = env_cfg.sim2real.wheel_order if env_cfg.sim2real.wheel_order is not None else []
        joint_order = env_cfg.sim2real.joint_order
        leg_ids = torch.tensor(
            [articulation.joint_names.index(name) for name in legs_order], device=env.unwrapped.device
        )
        wheel_ids = torch.tensor(
            [articulation.joint_names.index(name) for name in wheels_order], device=env.unwrapped.device
        )
        joint_ids = torch.tensor(
            [articulation.joint_names.index(name) for name in joint_order], device=env.unwrapped.device
        )

        armature = torch.tensor([0.1] * len(joint_ids), device=env.unwrapped.device).unsqueeze(0)
        damping = torch.tensor([4.5] * len(joint_ids), device=env.unwrapped.device).unsqueeze(0)
        friction = torch.tensor([0.05] * len(joint_ids), device=env.unwrapped.device).unsqueeze(0)  # static friction
        dynamic_friction = 0.5 * friction  # dynamic friction (must not exceed static friction)
        bias = torch.full_like(armature, 0.05)
        bias[wheel_ids].fill_(0.0)  # no bias for wheels
        env_ids = torch.arange(env.unwrapped.num_envs, device=env.unwrapped.device)
        time_lag = torch.full((len(env_ids),), 5, dtype=torch.long, device=env.unwrapped.device)
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
                warnings.warn(
                    "Each joint in actuator {drive_type!r} must occur exactly once in joint_order.",
                    RuntimeWarning,
                    stacklevel=2,
                )
            drive_joint_idx = torch.argmax(comparison_matrix.int(), dim=0)
            actuator.update_time_lags(time_lag)
            actuator.update_encoder_bias(bias[:, drive_joint_idx])
            actuator.reset(env_ids)

        data_dir = project_root() / "data" / env_cfg.sim2real.robot_name

        # Create a chirp signal for each action dimension
        duration = args_cli.duration  # seconds
        sample_rate = 1 / env.unwrapped.sim.get_physics_dt()  # Hz
        num_steps = int(duration * sample_rate)
        t = torch.linspace(0, duration, steps=num_steps, device=env.unwrapped.device)
        f0 = args_cli.min_frequency  # Hz
        f1 = args_cli.max_frequency  # Hz

        # Linear chirp: phase = 2*pi*(f0*t + (f1-f0)/(2*duration)*t^2)
        phase = 2 * pi * (f0 * t + ((f1 - f0) / (2 * duration)) * t**2)
        chirp_signal = torch.sin(phase)

        leg_trajectory = torch.zeros((num_steps, len(leg_ids)), device=env.unwrapped.device)
        leg_trajectory[:, :] = chirp_signal.unsqueeze(-1)
        leg_trajectory_directions = torch.tensor(
            [1.0, 1.0, 1.0, -1.0, 1.0, 1.0, 1.0, -1.0, -1.0, -1.0, -1.0, -1.0], device=env.unwrapped.device
        )
        leg_trajectory_bias = torch.tensor([0.0, 0.4, 0.8] * 4, device=env.unwrapped.device)
        leg_trajectory_scale = torch.tensor([0.25, 0.5, -2.0] * 4, device=env.unwrapped.device)
        leg_trajectory[:, :] = (
            (leg_trajectory + leg_trajectory_bias.unsqueeze(0))
            * leg_trajectory_directions.unsqueeze(0)
            * leg_trajectory_scale.unsqueeze(0)
        )

        if env_cfg.sim2real.wheel_order is not None:
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
            position=(leg_trajectory[0, leg_ids].unsqueeze(0) + bias[:, leg_ids]).contiguous(),
            joint_ids=leg_ids,
            env_ids=env_ids,
        )
        articulation.write_joint_velocity_to_sim_index(
            velocity=torch.zeros_like(bias), joint_ids=joint_ids, env_ids=env_ids
        )

        counter = 0
        # simulate environment
        dof_pos_buffer = torch.zeros(num_steps, len(joint_ids), device=env.unwrapped.device)
        dof_target_pos_buffer = torch.zeros(num_steps, len(joint_ids), device=env.unwrapped.device)
        time_data = t
        sim = env.unwrapped.sim
        while sim.is_running():
            # run everything in inference mode
            with torch.inference_mode():
                # compute actions
                dof_pos_buffer[counter, :] = articulation.data.joint_pos.torch[0, joint_ids] - bias[0]
                actions = torch.zeros(env.action_space.shape, device=env.unwrapped.device)
                actions = trajectory[counter % num_steps, :].unsqueeze(0).repeat(env.unwrapped.num_envs, 1)
                # apply actions
                obs, _, _, _, _ = env.step(actions)
                dof_target_pos_buffer[counter, :] = articulation.actuators.target_command.position.torch[0, joint_ids]
                counter += 1
                if counter % 400 == 0:
                    print(f"[INFO]: Step {counter / sample_rate} seconds")
                if counter >= num_steps:
                    break

    from time import sleep

    sleep(1)  # wait a bit for everything to settle

    (data_dir).mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "time": time_data.cpu(),
            "dof_pos": dof_pos_buffer.cpu(),
            "des_dof_pos": dof_target_pos_buffer.cpu(),
        },
        data_dir / "chirp_data.pt",
    )

    import matplotlib.pyplot as plt

    for i in range(len(joint_ids)):
        plt.figure()
        plt.plot(t.cpu().numpy(), dof_pos_buffer[:, i].cpu().numpy(), label=f"{joint_order[i]} pos")
        plt.plot(
            t.cpu().numpy(),
            dof_target_pos_buffer[:, i].cpu().numpy(),
            label=f"{joint_order[i]} target",
            linestyle="dashed",
        )
        plt.title(f"Joint {joint_order[i]} Trajectory")
        plt.xlabel("Time [s]")
        plt.ylabel("Joint position [rad]")
        plt.grid()
        plt.legend()
        plt.tight_layout()
        plt.show()


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

    add_video_args(parser, action="the diffdrive agent run")
    add_launcher_args(parser)
    # let task configs select the simulation device and keep checkpoint-free agents on the kitless default path
    parser.set_defaults(device=None, visualizer=["newton_gl"])
    args_cli, hydra_args = setup_preset_cli(parser, argv)
    enable_cameras_for_video(args_cli)
    sys.argv = [sys.argv[0]] + hydra_args
    return args_cli


if __name__ == "__main__":
    # run the main function
    raise SystemExit(main())
