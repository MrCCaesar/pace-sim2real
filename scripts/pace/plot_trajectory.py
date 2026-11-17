# © 2025 ETH Zurich, Robotic Systems Lab
# Author: Filip Bjelonic
# Licensed under the Apache License 2.0

"""Inspect evaluated fit results without pairing means with unrelated trajectories."""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path

import torch


def result_errors(result):
    """Recompute group RMSE and normalized objective from the paired record."""
    settings = result["settings"]
    errors = {}
    objective, weight = 0.0, 0.0
    for group, field, names in [
        ("position", "dof_pos", result["leg_order"]),
        ("velocity", "dof_vel", result["wheel_order"]),
    ]:
        if not names:
            errors[group + "_rmse"] = None
            continue
        measured = result["reference"][field]
        simulated = result["sim_" + field]
        if measured.shape != simulated.shape or measured.shape != (len(result["time"]), len(names)):
            raise ValueError("Paired response shape mismatch")
        if not torch.isfinite(measured).all() or not torch.isfinite(simulated).all():
            raise ValueError("Nonfinite paired response")
        mean = (simulated.double() - measured.double()).square().mean().item()
        scale, w = settings[group + "_error_scale"], settings[group + "_weight"]
        if not math.isfinite(scale) or scale <= 0 or not math.isfinite(w) or w <= 0:
            raise ValueError("Invalid stored error normalization")
        errors[group + "_rmse"] = math.sqrt(mean)
        objective += w * mean / scale**2
        weight += w
    if not weight:
        raise ValueError("Result has no response groups")
    errors["score"] = objective / weight
    return errors


def load_result(path):
    result = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(result, dict) or result.get("schema_version") != 2:
        raise ValueError("Legacy result has no verified parameter/trajectory pairing; generate a new paired fit result")
    for key, recomputed in result_errors(result).items():
        stored = result.get(key)
        if recomputed is None:
            if stored is not None:
                raise ValueError(f"Unexpected {key} for absent group")
        elif stored is None or not math.isclose(stored, recomputed, rel_tol=1e-5, abs_tol=1e-8):
            raise ValueError(f"Stored {key} does not match paired responses")
    if len(result["parameter_names"]) != len(result["params"]) or not torch.isfinite(result["params"]).all():
        raise ValueError("Invalid paired parameter vector")
    return result


def plot_result(result):
    """Return figures for measured, desired and simulated responses in joint coordinates."""
    import matplotlib.pyplot as plt

    figures = []
    for names, field, unit in [(result["leg_order"], "dof_pos", "rad"), (result["wheel_order"], "dof_vel", "rad/s")]:
        if not names:
            continue
        figure, axes = plt.subplots(len(names), 1, squeeze=False, figsize=(9, max(3, 2 * len(names))))
        for index, name in enumerate(names):
            axis = axes[index, 0]
            axis.plot(result["time"], result["reference"][field][:, index], label="Measured")
            axis.plot(
                result["time"], result["reference"]["des_" + field][:, index], "--", label="Desired (before delay)"
            )
            axis.plot(result["time"], result["sim_" + field][:, index], label="Fitted")
            axis.set(title=name, xlabel="Time [s]", ylabel=f"Joint [{unit}]")
            axis.grid(True)
            axis.legend()
        figure.tight_layout()
        figures.append(figure)
    return figures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect a paired PACE identification result.")
    parser.add_argument("--folder_name")
    parser.add_argument("--mean_name", help="Inspect distribution mean parameters only (not evaluated trajectories).")
    parser.add_argument("--result_name", help="Paired result filename; defaults to best_result.pt.")
    parser.add_argument("--robot_name", default="anymal_d_sim")
    parser.add_argument("--plot_trajectory", action="store_true")
    parser.add_argument("--plot_score", action="store_true")
    args = parser.parse_args(argv)
    if args.mean_name and (args.result_name or args.plot_trajectory):
        parser.error("Mean diagnostics cannot be paired with a candidate trajectory; use --result_name")
    root = Path(os.environ.get("PACE_ROOT", Path(__file__).resolve().parents[2]))
    # Current fit entry point and historical logs use these two locations.
    candidates = [root / "logs" / "pace-sim2real" / args.robot_name, root / "logs" / "pace" / args.robot_name]
    run_root = next((p for p in candidates if p.is_dir()), candidates[0])
    if args.folder_name:
        folder = run_root / args.folder_name
    else:
        folders = [p for p in run_root.iterdir() if p.is_dir()]
        if not folders:
            raise FileNotFoundError(f"No fit runs under {run_root}")
        folder = max(folders, key=lambda p: p.stat().st_mtime)
    if args.mean_name:
        print(
            "Distribution mean (diagnostic, not an evaluated response):",
            torch.load(folder / args.mean_name, weights_only=True, map_location="cpu"),
        )
    else:
        path = folder / (args.result_name or "best_result.pt")
        if not path.exists():
            raise ValueError(
                "No paired result found; legacy means/trajectories cannot be reliably paired. Run fitting again."
            )
        result = load_result(path)
        print(f"Evaluated candidate: generation={result['generation']}, index={result['candidate_index']}")
        for name, value in zip(result["parameter_names"], result["params"], strict=True):
            print(f"{name}: {float(value):.8g}")
        print(f"Applied delay: {result['delay_steps']} physics steps = {result['delay_seconds']:.8g} s")
        print("Recomputed errors:", result_errors(result))
        if args.plot_trajectory:
            plot_result(result)
    if args.plot_score:
        import matplotlib.pyplot as plt

        progress = torch.load(folder / "progress.pt", weights_only=True, map_location="cpu")
        _, axis = plt.subplots()
        axis.plot(progress["scores_buffer"].min(dim=1).values)
        axis.set(xlabel="Generation", ylabel="Normalized objective")
    if args.plot_trajectory or args.plot_score:
        import matplotlib.pyplot as plt

        plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
