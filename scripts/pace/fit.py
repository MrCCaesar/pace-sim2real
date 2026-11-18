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
import math
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


def _fit_dt(env_cfg) -> float:
    """One reference row advances one physics step during fitting."""
    if env_cfg.decimation != 1:
        raise ValueError(f"Fitting requires decimation=1, got {env_cfg.decimation}")
    dt = env_cfg.sim.dt
    if not math.isfinite(dt) or dt <= 0:
        raise ValueError("Fitting requires a finite positive dt")
    return dt


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
    env_cfg.sim.device = args_cli.device

    pre_launch_video_config(env_cfg, args_cli)
    # create environment
    try:
        validate(env_cfg)
        dt = _fit_dt(env_cfg)
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

        cfg = env_cfg.sim2real
        data = load_reference_data(project_root() / "data" / normalize_task_name(args_cli.task) / cfg.data_dir, cfg, dt)
        physics = env_cfg.sim.physics
        solver = getattr(physics, "solver_cfg", None)
        settings = {
            "dt": dt,
            "backend": type(physics).__name__,
            "solver": type(solver).__name__ if solver is not None else getattr(physics, "solver_type", None),
            "reference_bias_model": cfg.reference_bias_model,
            "reference_delay_mode": cfg.reference_delay_mode,
            "time_mode": cfg.time_mode,
            "legacy_sample_dt": cfg.legacy_sample_dt,
        }
        opt = CMAESOptimizer(
            bounds=cfg.bounds_params,
            population_size=env.unwrapped.num_envs,
            log_dir=log_dir,
            joint_order=legs + wheels,
            max_iteration=cfg.cmaes.max_iteration,
            data=data,
            device=env.unwrapped.device,
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


@contextlib.contextmanager
def _replay_joint_actions(base):
    """Capture the stock action manager's GPU writes for one rollout between resets."""
    from isaaclab.managers import ActionManager

    manager = base.action_manager
    if (
        torch.device(base.device).type != "cuda"
        or type(manager) is not ActionManager
        or not manager.is_graphable
        or base.scene.is_graphable
        or not type(base.sim.backend_manager).__module__.startswith("isaaclab_newton.")
        or "apply_action" in vars(manager)
        or "process_action" in vars(manager)
        or "interval" in base.event_manager.active_terms
        or base.recorder_manager.active_terms
    ):
        yield
        return

    # resolve_action_mapping restricts terms to absolute position and velocity actions.
    # Their processed buffers stay in place. Use separate graphs so env.step still
    # runs its recorder, counters, and all Python actuator/physics work in order.
    static_action = torch.empty_like(manager.action)
    process_graph = torch.cuda.CUDAGraph()
    try:
        # Scope capture to this stream. The higher-level torch.cuda.graph context
        # empties the process-wide allocator cache on every rollout.
        with torch.cuda.stream(torch.cuda.Stream(device=static_action.device)):
            process_graph.capture_begin()
            try:
                manager.process_action(static_action)
            finally:
                process_graph.capture_end()
        with wp.ScopedCapture(device=base.device) as capture:
            manager.apply_action()
    except torch.OutOfMemoryError:
        raise
    except RuntimeError as exc:
        # A CUDA runtime without graph support can still replay the original steps.
        if "captur" not in str(exc).lower() and "graph" not in str(exc).lower():
            raise
        yield
        return

    apply_graph = capture.graph
    assert apply_graph is not None

    def process_action(action):
        static_action.copy_(action)
        process_graph.replay()

    def apply_action():
        wp.capture_launch(apply_graph)

    manager.process_action = process_action
    manager.apply_action = apply_action
    try:
        yield
    finally:
        del manager.apply_action
        del manager.process_action


@torch.inference_mode()
def fit_reference(env, data, opt):
    """Replay prepacked commands and score each completed rollout as one batch."""
    base = getattr(env, "unwrapped", env)
    dt = _fit_dt(base.cfg)
    if base.cfg.sim.use_newton_actuators:
        raise ValueError("Fitting requires Python PACE actuators")
    legs, wheels = resolve_joint_groups(base.cfg.sim2real)
    mapping = resolve_action_mapping(base, legs, wheels)
    robot = base.scene["robot"]
    # Clock checks use host scalars; never read one timestamp from CUDA per step.
    timestamps = data["time"].detach().cpu().tolist()
    reference = {key: value.to(base.device) for key, value in data.items() if key not in ("time", "original_time")}
    batch, count = base.num_envs, len(timestamps)
    measured_positions = reference["dof_pos"].double().unsqueeze(0).expand(batch, -1, -1)
    measured_velocities = reference["dof_vel"].double().unsqueeze(0).expand(batch, -1, -1) if wheels else None
    initial = reference["dof_pos"][0].expand(batch, -1)
    initial_velocity = reference["dof_vel"][0].expand(batch, -1) if wheels else None
    actions = pack_actions(mapping, reference["des_dof_pos"], reference.get("des_dof_vel"))
    actions = actions.unsqueeze(1).expand(-1, batch, -1)
    # Reuse full-state buffers across generations; include the post-step final state.
    positions = torch.empty((count + 1, batch, robot.num_joints), device=base.device)
    velocities = torch.empty_like(positions)
    while True:
        env.reset()
        opt.update_simulator(
            robot, mapping["leg_ids"] + mapping["wheel_ids"], initial, initial_wheel_velocity=initial_velocity
        )
        origin = base._sim_step_counter
        with _replay_joint_actions(base):
            for step, timestamp in enumerate(timestamps):
                if not base.sim.is_running():
                    raise RuntimeError("Simulation closed before fitting completed")
                elapsed = (base._sim_step_counter - origin) * dt
                if abs(elapsed - timestamp) > 1e-7 + 1e-5 * abs(elapsed):
                    raise ValueError("Reference time does not match actual simulation time")
                positions[step].copy_(robot.data.joint_pos.torch)
                velocities[step].copy_(robot.data.joint_vel.torch)
                result = env.step(actions[step])
                if len(result) == 5 and (result[2] | result[3]).any():
                    raise RuntimeError("Environment terminated/reset during fitting")
        positions[-1].copy_(robot.data.joint_pos.torch)
        velocities[-1].copy_(robot.data.joint_vel.torch)
        if not (torch.isfinite(positions).all() & torch.isfinite(velocities).all()):
            raise RuntimeError("Nonfinite fitting state")
        opt.tell(
            positions[:-1, :, mapping["leg_ids"]].permute(1, 0, 2),
            measured_positions,
            sim_dof_vel=velocities[:-1, :, mapping["wheel_ids"]].permute(1, 0, 2) if wheels else None,
            real_dof_vel=measured_velocities,
        )
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
    # Fit on CUDA without a viewer unless explicitly overridden on the command line.
    parser.set_defaults(device="cuda", visualizer=[])
    arguments = fuse_kit_args(sys.argv[1:] if argv is None else argv)
    args_cli, hydra_args = setup_preset_cli(parser, arguments)
    args_cli.device_explicit = args_cli.device is not None
    enable_cameras_for_video(args_cli)
    sys.argv = [sys.argv[0]] + hydra_args
    return args_cli


if __name__ == "__main__":
    # run the main function
    raise SystemExit(main())
