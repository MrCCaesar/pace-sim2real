# © 2025 ETH Zurich, Robotic Systems Lab
# Author: Filip Bjelonic
# Licensed under the Apache License 2.0

# Warp captures ``enable_backward`` when a module is created, which happens at import
# time, so it has to be set before importing anything that defines Warp kernels.
# Isaac Lab does not use Warp autodiff; skipping adjoint codegen roughly halves the
# time spent building kernels on a cold kernel cache.
import warp as wp

wp.config.enable_backward = False

from typing import Any

import torch

from isaaclab.app import launch_simulation
from isaaclab.cli import load_external_tasks

from isaaclab_tasks.utils import resolve_task_config

from pace_sim2real.utils import trajectory_simulation as trajectory
from pace_sim2real.utils.collection_contracts import reference_groups, resolve_joint_groups
from pace_sim2real.utils.fit_replay import JointParameters
from pace_sim2real.utils.subset_control import SubsetControl


def _parse_args(argv):
    parser = trajectory.trajectory_parser("Collect PACE joint responses to a chirp.")
    args = trajectory.parse_runtime_args(
        parser, argv, removed_options=("--fit_result", "--trajectory_file", "--output")
    )
    trajectory.set_chirp_defaults(args)
    return args


def main(argv: list[str] | None = None):
    load_external_tasks()
    args = _parse_args(argv)
    torch.manual_seed(42)
    env_cfg: Any
    env_cfg, _ = resolve_task_config(args.task, "")
    log_dir, output = trajectory.prepare_task(env_cfg, args)
    task_legs, task_wheels = resolve_joint_groups(env_cfg.sim2real)
    legs, wheels = reference_groups(env_cfg.sim2real)
    parameters = JointParameters.collection_defaults(len(legs), len(wheels))

    with launch_simulation(env_cfg, args):
        with trajectory.trajectory_environment(env_cfg, args, log_dir) as env:
            control = None
            if (legs, wheels) != (task_legs, task_wheels):
                control = SubsetControl(env.unwrapped, legs, wheels, check_delay_mode=False)
            if len(legs) == len(task_legs) and len(wheels) == len(task_wheels):
                collected = trajectory.run_full_trajectory(env, args, parameters, legs, wheels, control=control)
            else:
                collected = trajectory.run_subset_trajectory(env, args, parameters, control)

        trajectory.save_collection(collected, output)
        if args.plot:
            trajectory.plot_collection(collected, legs, wheels, replay=False, reference=None)


if __name__ == "__main__":
    raise SystemExit(main())
