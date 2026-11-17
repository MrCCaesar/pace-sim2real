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

from pace_sim2real import CMAESOptimizer
from pace_sim2real.utils import project_root
from pace_sim2real.utils.collection_contracts import (
    add_runtime_args,
    load_reference_data,
    pack_actions,
    resolve_action_mapping,
    resolve_joint_groups,
)

_SEED = 42


def main(argv: list[str] | None = None):
    """Zero actions agent with Isaac Lab environment."""
    # parse configuration
    load_external_tasks()
    args_cli = _parse_args(argv)
    torch.manual_seed(_SEED)
    env_cfg: Any
    env_cfg, _ = resolve_task_config(args_cli.task, "")
    legs, wheels = resolve_joint_groups(env_cfg.sim2real)
    env_cfg.sim2real.leg_order = list(legs)
    env_cfg.sim2real.wheel_order = list(wheels)
    env_cfg.sim2real.joint_order = list(legs + wheels)
    apply_env_overrides(args_cli, env_cfg)
    args_cli.device = env_cfg.sim.device

    pre_launch_video_config(env_cfg, args_cli)
    # create environment
    try:
        validate(env_cfg)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"Invalid environment configuration: {exc}") from None
    log_dir = os.path.abspath(os.path.join("logs", "pace-sim2real", normalize_task_name(args_cli.task)))
    with launch_simulation(env_cfg, args_cli), contextlib.ExitStack() as cleanup:
        apply_video_recording(env_cfg, log_dir, args_cli, subdir="play")
        # create environment
        env: Any = gym.make(args_cli.task, cfg=env_cfg)
        cleanup.callback(lambda: close_env(env))

        # print info (this is vectorized environment)
        print(f"[INFO]: Gym observation space: {env.observation_space}")
        print(f"[INFO]: Gym action space: {env.action_space}")

        legs, wheels = resolve_joint_groups(env_cfg.sim2real)
        cfg = env_cfg.sim2real
        data = load_reference_data(project_root() / "data" / cfg.data_dir, cfg, env.unwrapped.step_dt)
        settings = {
            key: getattr(cfg, key)
            for key in (
                "reference_leg_order",
                "reference_wheel_order",
                "reference_bias_model",
                "reference_delay_mode",
                "time_mode",
                "legacy_sample_dt",
            )
        }
        settings.update(
            physics_dt=env_cfg.sim.dt,
            control_dt=env.unwrapped.step_dt,
            backend=type(env_cfg.sim.physics).__name__,
            solver=repr(env_cfg.sim.physics),
        )
        opt = CMAESOptimizer(
            cfg.bounds_params,
            env.unwrapped.num_envs,
            log_dir,
            legs + wheels,
            cfg.cmaes.max_iteration,
            data,
            env.unwrapped.device,
            epsilon=cfg.cmaes.epsilon,
            sigma=cfg.cmaes.sigma,
            save_interval=cfg.cmaes.save_interval,
            save_optimization_process=cfg.cmaes.save_optimization_process,
            separate_dynamic_friction=cfg.separate_dynamic_friction,
            leg_order=legs,
            wheel_order=wheels,
            reference_settings=settings,
            position_error_scale=cfg.cmaes.position_error_scale,
            velocity_error_scale=cfg.cmaes.velocity_error_scale,
            position_weight=cfg.cmaes.position_weight,
            velocity_weight=cfg.cmaes.velocity_weight,
        )
        cleanup.callback(opt.close)
        fit_reference(env, data, opt)


def fit_reference(env, data, opt):
    """Replay validated reference data and evaluate candidates through ActionManager."""
    base = getattr(env, "unwrapped", env)
    if base.cfg.sim.use_newton_actuators:
        raise ValueError("Fitting requires Python PACE actuators")
    legs, wheels = resolve_joint_groups(base.cfg.sim2real)
    mapping = resolve_action_mapping(base, legs, wheels)
    robot = base.scene["robot"]
    device = base.device
    reference = {key: value.to(device) for key, value in data.items()}
    batch = base.num_envs
    initial = reference["dof_pos"][0].expand(batch, -1)
    velocity = reference["dof_vel"][0].expand(batch, -1) if wheels else None
    actions = pack_actions(mapping, reference["des_dof_pos"], reference.get("des_dof_vel"))
    actions = actions.unsqueeze(1).expand(-1, batch, -1)
    while True:
        env.reset()
        opt.update_simulator(robot, mapping["leg_ids"] + mapping["wheel_ids"], initial, initial_wheel_velocity=velocity)
        origin = base._sim_step_counter
        for k in range(len(reference["time"])):
            if not base.sim.is_running():
                raise RuntimeError("Simulation closed before fitting completed")
            elapsed = (base._sim_step_counter - origin) * base.physics_dt
            if abs(elapsed - float(reference["time"][k])) > 1e-7 + 1e-5 * abs(elapsed):
                raise ValueError("Reference time does not match actual simulation time")
            with torch.inference_mode():
                opt.tell(
                    robot.data.joint_pos.torch[:, mapping["leg_ids"]],
                    reference["dof_pos"][k].expand(batch, -1),
                    sim_dof_vel=robot.data.joint_vel.torch[:, mapping["wheel_ids"]] if wheels else None,
                    real_dof_vel=reference["dof_vel"][k].expand(batch, -1) if wheels else None,
                )
                result = env.step(actions[k])
            if len(result) == 5 and (torch.as_tensor(result[2]).any() or torch.as_tensor(result[3]).any()):
                raise RuntimeError("Environment terminated/reset during fitting")
            if (
                not torch.isfinite(robot.data.joint_pos.torch).all()
                or not torch.isfinite(robot.data.joint_vel.torch).all()
            ):
                raise RuntimeError("Nonfinite fitting state")
        opt.evolve()
        if opt.finished():
            break
    return opt.get_best_sim_params()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the command line of a checkpoint-free agent and hand the remainder to Hydra."""
    parser = argparse.ArgumentParser(description="Pace fit agent for Isaac Lab environments.")
    parser.add_argument("--num_envs", type=int, default=2, help="Number of environments to simulate.")
    parser.add_argument("--task", type=str, default=None, help="Name of the task.")

    add_video_args(parser, action="the diffdrive agent run")
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
