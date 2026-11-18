# © 2025 ETH Zurich, Robotic Systems Lab
# Author: Filip Bjelonic
# Licensed under the Apache License 2.0

"""Inspect evaluated fit results using current task directories and paired records."""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import torch

if TYPE_CHECKING:
    from matplotlib.figure import Figure

# Group name, ordered-name field, response field, display unit.
_RESPONSE_GROUPS = (
    ("position", "leg_order", "dof_pos", "rad"),
    ("velocity", "wheel_order", "dof_vel", "rad/s"),
)
_DEFAULT_TASK = "Isaac-Pace-Anymal-D-v0"


def _validate_tensor(value: Any, shape: tuple[int, ...], name: str) -> None:
    if not isinstance(value, torch.Tensor) or value.shape != shape or not value.is_floating_point():
        raise ValueError(f"{name} must be a floating tensor with shape {shape}")
    if not torch.isfinite(value).all():
        raise ValueError(f"Nonfinite {name}")


def result_errors(result: dict[str, Any]) -> dict[str, float | None]:
    """Recompute RMSE and normalized objective without applying encoder bias again."""
    settings = result["settings"]
    errors: dict[str, float | None] = {}
    objective, weight = 0.0, 0.0
    for group, names_key, field, _ in _RESPONSE_GROUPS:
        names = result[names_key]
        if not names:
            errors[group + "_rmse"] = None
            continue
        measured, simulated = result["reference"][field], result["sim_" + field]
        shape = (len(result["time"]), len(names))
        _validate_tensor(measured, shape, field)
        _validate_tensor(simulated, shape, "sim_" + field)
        mean = (simulated.double() - measured.double()).square().mean().item()
        scale, group_weight = settings[group + "_error_scale"], settings[group + "_weight"]
        if any(not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0 for x in (scale, group_weight)):
            raise ValueError(f"Invalid stored {group} error normalization")
        if not math.isfinite(mean):
            raise ValueError(f"Nonfinite {group} error")
        errors[group + "_rmse"] = math.sqrt(mean)
        objective += group_weight * mean / scale**2
        weight += group_weight
    if not weight or not math.isfinite(objective / weight):
        raise ValueError("Result has no valid response objective")
    errors["score"] = objective / weight
    return errors


def load_result(path: str | Path) -> dict[str, Any]:
    """Load a CPU schema-v2 record and validate all data needed for inspection."""
    result = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(result, dict) or result.get("schema_version") != 2:
        raise ValueError("Legacy result has no verified parameter/trajectory pairing; generate a new paired fit result")
    required = {
        "time",
        "reference",
        "settings",
        "leg_order",
        "wheel_order",
        "params",
        "parameter_names",
        "generation",
        "candidate_index",
        "delay_steps",
        "delay_seconds",
        "score",
        "position_rmse",
        "velocity_rmse",
    }
    missing = required - result.keys()
    if missing:
        raise ValueError(f"Paired result is missing fields: {', '.join(sorted(missing))}")
    if not isinstance(result["reference"], dict) or not isinstance(result["settings"], dict):
        raise ValueError("Paired reference and settings must be dictionaries")
    time = result["time"]
    if not isinstance(time, torch.Tensor) or time.ndim != 1 or len(time) < 2:
        raise ValueError("time must contain at least two samples")
    _validate_tensor(time, (len(time),), "time")
    if not (time.diff() > 0).all():
        raise ValueError("time must be strictly increasing")
    all_names = []
    for group, names_key, field, _ in _RESPONSE_GROUPS:
        names = result[names_key]
        if not isinstance(names, (list, tuple)) or any(not isinstance(n, str) or not n for n in names):
            raise ValueError(f"Invalid {names_key}")
        if group == "position" and not names:
            raise ValueError("Result requires at least one leg joint")
        all_names.extend(names)
        if not names:
            continue
        for key in (field, "des_" + field):
            _validate_tensor(result["reference"].get(key), (len(time), len(names)), "reference." + key)
        _validate_tensor(result.get("sim_" + field), (len(time), len(names)), "sim_" + field)
        if any(group + suffix not in result["settings"] for suffix in ("_error_scale", "_weight")):
            raise ValueError(f"Missing {group} error normalization settings")
    if len(set(all_names)) != len(all_names):
        raise ValueError("Joint groups must have unique, disjoint names")
    names = result["parameter_names"]
    if not isinstance(names, (list, tuple)) or not names or any(not isinstance(n, str) or not n for n in names):
        raise ValueError("Invalid parameter_names")
    _validate_tensor(result["params"], (len(names),), "params")
    for key in ("generation", "candidate_index", "delay_steps"):
        if type(result[key]) is not int or result[key] < 0:
            raise ValueError(f"{key} must be a nonnegative integer")
    seconds = result["delay_seconds"]
    if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError("delay_seconds must be finite and nonnegative")
    for key, recomputed in result_errors(result).items():
        stored = result.get(key)
        if recomputed is None:
            if stored is not None:
                raise ValueError(f"Unexpected {key} for absent group")
        elif not isinstance(stored, (int, float)) or not math.isclose(stored, recomputed, rel_tol=1e-5, abs_tol=1e-8):
            raise ValueError(f"Stored {key} does not match paired responses")
    return result


def plot_result(result: dict[str, Any]) -> list[Figure]:
    """Plot measured, pre-delay desired and fitted values in joint coordinates."""
    import matplotlib.pyplot as plt

    figures = []
    for _, names_key, field, unit in _RESPONSE_GROUPS:
        names = result[names_key]
        if not names:
            continue
        figure, axes = plt.subplots(len(names), 1, squeeze=False, figsize=(9, max(3, 2 * len(names))))
        for index, name in enumerate(names):
            axis = axes[index, 0]
            axis.plot(result["time"], result["reference"][field][:, index], marker="o", markersize=6, label="Measured")
            axis.plot(
                result["time"],
                result["reference"]["des_" + field][:, index],
                label="Desired (before delay)",
            )
            axis.plot(result["time"], result["sim_" + field][:, index], marker="x", markersize=6, label="Fitted")
            axis.set(title=name, xlabel="Time [s]", ylabel=f"Joint [{unit}]")
            axis.grid(True)
            axis.legend()
        figure.tight_layout()
        figures.append(figure)
    return figures


def _resolve_run(root: Path, task: str, folder_name: str | None, required_files: tuple[str, ...]) -> Path:
    """Prefer current task logs, falling back to historical logs when necessary."""
    roots = (root / "logs" / "pace-sim2real" / task, root / "logs" / "pace" / task)
    for run_root in roots:
        if folder_name:
            folder = run_root / folder_name
            if all((folder / name).is_file() for name in required_files):
                return folder
        elif run_root.is_dir():
            complete = [
                folder
                for folder in run_root.iterdir()
                if folder.is_dir() and all((folder / name).is_file() for name in required_files)
            ]
            if complete:
                return max(complete, key=lambda folder: (folder.stat().st_mtime_ns, folder.name))
    searched = ", ".join(str(path / folder_name if folder_name else path) for path in roots)
    raise FileNotFoundError(
        f"No run containing {required_files} under {searched}. "
        "Use paired fitting results; progress.pt requires cmaes.save_optimization_process=True."
    )


def _plot_scores(path: Path) -> Figure:
    """Plot each completed generation's best normalized objective."""
    import matplotlib.pyplot as plt

    progress = torch.load(path, map_location="cpu", weights_only=True)
    scores = progress.get("scores_buffer") if isinstance(progress, dict) else None
    if not isinstance(scores, torch.Tensor) or scores.ndim != 2 or min(scores.shape) < 1:
        raise ValueError("progress.pt requires nonempty scores_buffer[generations, population]")
    _validate_tensor(scores, tuple(scores.shape), "scores_buffer")
    figure, axis = plt.subplots()
    axis.plot(scores.min(dim=1).values)
    axis.set(xlabel="Generation", ylabel="Normalized objective")
    axis.grid(True)
    figure.tight_layout()
    return figure


def _print_result(result: dict[str, Any]) -> None:
    print(f"Evaluated candidate: generation={result['generation']}, index={result['candidate_index']}")
    for name, value in zip(result["parameter_names"], result["params"], strict=True):
        print(f"{name}: {float(value):.8g}")
    print(f"Applied delay: {result['delay_steps']} physics steps = {result['delay_seconds']:.8g} s")
    print("Verified errors:", {key: result[key] for key in ("position_rmse", "velocity_rmse", "score")})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect a paired PACE identification result.")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--task", default=_DEFAULT_TASK, help="Task ID used by fit.py (namespace prefixes allowed).")
    selection.add_argument("--robot_name", help="Legacy alias selecting a task/robot log directory.")
    parser.add_argument("--folder_name", help="Run directory; otherwise select the latest run with the requested file.")
    parser.add_argument("--mean_name", help="Distribution mean diagnostics only; not an evaluated trajectory.")
    parser.add_argument("--result_name", help="Paired result filename; defaults to best_result.pt.")
    parser.add_argument("--plot_trajectory", action="store_true")
    parser.add_argument("--plot_score", action="store_true")
    args = parser.parse_args(argv)
    if args.mean_name and (args.result_name or args.plot_trajectory):
        parser.error("Mean diagnostics cannot be paired with a candidate trajectory; use --result_name")
    root = Path(os.environ.get("PACE_ROOT", Path(__file__).resolve().parents[2]))
    task = args.robot_name or args.task.split(":")[-1]
    required_file = args.mean_name or args.result_name or "best_result.pt"
    try:
        required_files = (required_file, "progress.pt") if args.plot_score else (required_file,)
        folder = _resolve_run(root, task, args.folder_name, required_files)
        print(f"Run: {folder}")
        if args.mean_name:
            mean = torch.load(folder / args.mean_name, map_location="cpu", weights_only=True)
            if not isinstance(mean, torch.Tensor) or mean.ndim != 1 or not len(mean):
                raise ValueError("Distribution mean must be a nonempty parameter vector")
            _validate_tensor(mean, (len(mean),), "distribution mean")
            print("Distribution mean (diagnostic, not an evaluated response):", mean)
        else:
            result = load_result(folder / required_file)
            _print_result(result)
            if args.plot_trajectory:
                plot_result(result)
        if args.plot_score:
            _plot_scores(folder / "progress.pt")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.plot_trajectory or args.plot_score:
        import matplotlib.pyplot as plt

        plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
