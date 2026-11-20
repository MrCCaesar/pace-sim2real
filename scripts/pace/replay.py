# © 2025 ETH Zurich, Robotic Systems Lab
# Author: Filip Bjelonic
# Licensed under the Apache License 2.0

# Warp captures ``enable_backward`` when a module is created, which happens at import
# time, so it has to be set before importing anything that defines Warp kernels.
# Isaac Lab does not use Warp autodiff; skipping adjoint codegen roughly halves the
# time spent building kernels on a cold kernel cache.
import warp as wp

wp.config.enable_backward = False

from pathlib import Path
from typing import Any

import torch

from isaaclab.app import launch_simulation
from isaaclab.cli import load_external_tasks

from isaaclab_tasks.utils import resolve_task_config

from pace_sim2real.utils import trajectory_simulation as trajectory
from pace_sim2real.utils.collection_contracts import load_reference_data, reference_groups, resolve_joint_groups
from pace_sim2real.utils.fit_replay import (
    compare_replay_conditions,
    latest_fit_result,
    prediction_rmse,
    read_replay_record,
    replay_parameters,
)
from pace_sim2real.utils.subset_control import SubsetControl


def _parse_args(argv):
    parser = trajectory.trajectory_parser("Replay a fitted candidate with a chirp or a measured trajectory.")
    parser.add_argument(
        "--fit_result", nargs="?", const="", metavar="PATH", help="Latest fit (default) or result path."
    )
    parser.add_argument("--trajectory_file", type=Path, help="Replay commands from this measured trajectory.")
    parser.add_argument("--output", type=Path, help="Save the replay response to a separate file.")
    args = trajectory.parse_runtime_args(parser, argv)
    if args.trajectory_file is not None:
        for name in ("min_frequency", "max_frequency", "duration"):
            if getattr(args, name) is not None:
                parser.error(f"--trajectory_file and --{name} cannot be used together")
    trajectory.set_chirp_defaults(args)
    return args


def main(argv: list[str] | None = None):
    load_external_tasks()
    args = _parse_args(argv)
    torch.manual_seed(42)
    env_cfg: Any
    env_cfg, _ = resolve_task_config(args.task, "")
    log_dir, default_output = trajectory.prepare_task(env_cfg, args)
    result_path = Path(args.fit_result) if args.fit_result else latest_fit_result(log_dir)
    output = args.output
    reference = None
    fit_reference = default_output.parent / env_cfg.sim2real.data_dir
    protected = [result_path, default_output, fit_reference]
    if default_output.parent.name == "Isaac-Pace-Sevnce-X5-v0":
        protected.append(default_output.with_name("mujoco_chirp_data.pt"))
    if args.trajectory_file is not None:
        protected.append(args.trajectory_file)
        reference = load_reference_data(args.trajectory_file, env_cfg.sim2real, env_cfg.sim.dt)
    if output is not None and any(
        output.resolve() == path.resolve() or (output.exists() and path.exists() and output.samefile(path))
        for path in protected
    ):
        raise ValueError(f"Replay output would replace protected input or collection: {output}")
    print(f"[INFO]: Replaying {result_path} using {args.trajectory_file or 'generated chirp'}")

    with launch_simulation(env_cfg, args):
        record = read_replay_record(result_path)
        legs, wheels = _replay_groups(record, env_cfg.sim2real, reference is not None)
        parameters = replay_parameters(record, env_cfg, legs, wheels, result_path)
        with trajectory.trajectory_environment(env_cfg, args, log_dir) as env:
            if record["schema_version"] == 3 or (legs, wheels) != resolve_joint_groups(env_cfg.sim2real):
                control = SubsetControl(env.unwrapped, legs, wheels)
                if record["schema_version"] == 3:
                    compare_replay_conditions(record["settings"], control.settings())
                try:
                    collected = trajectory.run_subset_trajectory(env, args, parameters, control, reference=reference)
                except trajectory.UnknownChirpJoints as exc:
                    raise ValueError(f"{exc}; supply --trajectory_file") from exc
            else:
                collected = trajectory.run_full_trajectory(
                    env,
                    args,
                    parameters,
                    legs,
                    wheels,
                    reference=reference,
                    delay_mode=env_cfg.sim2real.reference_delay_mode,
                )

        if reference is not None:
            errors = prediction_rmse(collected, reference)
            if legs:
                print(f"Position prediction RMSE: {errors['dof_pos']:.8g} rad")
            if wheels:
                print(f"Velocity prediction RMSE: {errors['dof_vel']:.8g} rad/s")
        if output is not None:
            trajectory.save_collection(collected, output)
        if args.plot:
            trajectory.plot_collection(collected, legs, wheels, replay=True, reference=reference)


def _replay_groups(record, cfg, has_file):
    task_groups = resolve_joint_groups(cfg)
    if has_file:
        groups = reference_groups(cfg)
    elif record["schema_version"] == 3:
        groups = (record.get("leg_order", ()), record.get("wheel_order", ()))
    else:
        groups = task_groups
    for names, full in zip(groups, task_groups, strict=True):
        if not isinstance(names, (list, tuple)) or any(n not in full for n in names) or len(set(names)) != len(names):
            raise ValueError("Invalid result joint names for this task")
        if record["schema_version"] == 2 and set(names) != set(full):
            raise ValueError("Incompatible full-result joint groups")
    if not any(groups):
        raise ValueError("Empty result joint groups")
    return tuple(groups[0]), tuple(groups[1])


if __name__ == "__main__":
    # run the main function
    raise SystemExit(main())
