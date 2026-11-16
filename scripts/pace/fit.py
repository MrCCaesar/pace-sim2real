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
import torch
from tensordict import TensorDict

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
    video_playback_steps,
)

import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils import (
    resolve_task_config,
    setup_preset_cli,
)

"""Rest everything follows."""

import gymnasium as gym
import torch

import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils import parse_env_cfg

from pace_sim2real.utils import project_root
from pace_sim2real import CMAESOptimizer

_SEED = 42


def main(argv: list[str] | None = None):
    """Zero actions agent with Isaac Lab environment."""
    # parse configuration
    load_external_tasks()
    args_cli = _parse_args(argv)
    torch.manual_seed(_SEED)
    env_cfg, _ = resolve_task_config(args_cli.task, "")
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
        env = gym.make(args_cli.task, cfg=env_cfg)
        cleanup.callback(lambda: close_env(env))

        # print info (this is vectorized environment)
        print(f"[INFO]: Gym observation space: {env.observation_space}")
        print(f"[INFO]: Gym action space: {env.action_space}")

        # Create optimization
        bounds_params = env_cfg.sim2real.bounds_params.to(env.unwrapped.device)
        articulation = env.unwrapped.scene["robot"]
        joint_order = env_cfg.sim2real.joint_order
        sim_joint_ids = torch.tensor([articulation.joint_names.index(name) for name in joint_order], device=env.unwrapped.device)

        data_file = project_root() / "data" / env_cfg.sim2real.data_dir

        data = torch.load(data_file)
        time_data = data["time"].to(env.unwrapped.device)
        target_dof_pos = data["des_dof_pos"].to(env.unwrapped.device)
        measured_dof_pos = data["dof_pos"].to(env.unwrapped.device)

        initial_dof_pos = measured_dof_pos[0, :].unsqueeze(0).repeat(env.unwrapped.num_envs, 1)

        time_steps = time_data.shape[0]
        sim_dt = env.unwrapped.sim.cfg.dt

        opt = CMAESOptimizer(
            bounds=bounds_params,
            population_size=env.unwrapped.num_envs,
            log_dir=log_dir,
            joint_order=joint_order,
            max_iteration=env_cfg.sim2real.cmaes.max_iteration,
            data=data,
            device=env.unwrapped.device,
            epsilon=env_cfg.sim2real.cmaes.epsilon,
            sigma=env_cfg.sim2real.cmaes.sigma,
            save_interval=env_cfg.sim2real.cmaes.save_interval,
            save_optimization_process=env_cfg.sim2real.cmaes.save_optimization_process,
            separate_dynamic_friction=env_cfg.sim2real.separate_dynamic_friction,
        )

        env.reset()
        opt.update_simulator(articulation, sim_joint_ids, initial_dof_pos)

        counter = 0
        # simulate environment
        sim = env.unwrapped.sim
        while sim.is_running():
            # run everything in inference mode
            with torch.inference_mode():
                # compute zero actions
                opt.tell(articulation.data.joint_pos.torch[:, sim_joint_ids], measured_dof_pos[counter, :].unsqueeze(0).repeat(env.unwrapped.num_envs, 1))
                actions = torch.zeros(env.action_space.shape, device=env.unwrapped.device)
                actions[:, sim_joint_ids] = target_dof_pos[counter, :].unsqueeze(0).repeat(env.unwrapped.num_envs, 1)
                # apply actions
                env.step(actions)
                counter += 1
                if counter % 400 == 0:
                    print(f"[INFO]: Step {counter * sim_dt:.1f} / {time_data[-1]:.1f} seconds ({counter / time_steps * 100:.1f} %)")
                if counter >= time_steps:
                    print("[INFO]: Reached the end of the trajectory, exiting.")
                    counter = 0
                    opt.evolve()
                    if opt.finished():
                        break
                    env.reset()
                    opt.update_simulator(articulation, sim_joint_ids, initial_dof_pos)
        # close optimizer
        opt.close()

def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the command line of a checkpoint-free agent and hand the remainder to Hydra."""
    parser = argparse.ArgumentParser(description="Pace fit agent for Isaac Lab environments.")
    parser.add_argument("--num_envs", type=int, default=1, help="Number of environments to simulate.")
    parser.add_argument("--task", type=str, default=None, help="Name of the task.")

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
