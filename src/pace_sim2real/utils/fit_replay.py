# SPDX-License-Identifier: Apache-2.0
"""Read physical joint parameters from a PACE evaluated candidate for replay."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import torch


@dataclass
class JointParameters:
    """One candidate in task joint order, before broadcasting to environments."""

    armature: torch.Tensor
    damping: torch.Tensor
    friction: torch.Tensor
    dynamic_friction: torch.Tensor
    bias: torch.Tensor
    delay_steps: int

    @classmethod
    def collection_defaults(cls, num_legs: int, num_wheels: int) -> JointParameters:
        shape = (num_legs + num_wheels,)
        friction = torch.full(shape, 0.05)
        bias = torch.full(shape, 0.05)
        bias[num_legs:] = 0
        return cls(torch.full(shape, 0.1), torch.full(shape, 4.5), friction, 0.5 * friction, bias, 5)


def load_replay_parameters(path: Path, cfg, legs, wheels) -> JointParameters:
    """Validate a current fit and reorder its named parameters into task order."""
    record = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(record, dict) or record.get("schema_version") != 2:
        raise ValueError(f"{path}: expected a paired v2 best_result.pt")
    _check_physics(record, path, cfg)
    _check_paired_response(record, legs, wheels)
    return _named_parameters(record, legs, wheels)


def _check_physics(record, path, cfg):
    settings = record.get("settings")
    if not isinstance(settings, dict) or "dt" not in settings:
        raise ValueError(f"{path}: outdated fit result; settings.dt is required")

    dt = settings["dt"]
    if (
        type(dt) not in (float, int)
        or not math.isfinite(dt)
        or dt <= 0
        or cfg.decimation != 1
        or not math.isclose(dt, cfg.sim.dt, rel_tol=1e-7)
    ):
        raise ValueError(
            f"Incompatible replay timestep: fit dt={dt}, task dt={cfg.sim.dt}, decimation={cfg.decimation}"
        )
    physics = cfg.sim.physics
    solver = getattr(physics, "solver_cfg", None)
    expected = {
        "backend": type(physics).__name__,
        "solver": type(solver).__name__ if solver is not None else getattr(physics, "solver_type", None),
        "reference_delay_mode": cfg.sim2real.reference_delay_mode,
        "reference_bias_model": "feedback_and_measurement",
    }
    if cfg.sim2real.reference_bias_model != expected["reference_bias_model"]:
        raise ValueError("Replay requires feedback_and_measurement encoder bias")
    for field, value in expected.items():
        if field not in settings or settings[field] != value:
            raise ValueError(f"Incompatible {field}: fit={settings.get(field)!r}, task={value!r}")


def _check_paired_response(record, legs, wheels):
    for field in ("generation", "candidate_index"):
        index = record.get(field)
        if type(index) is not int or index < 0:
            raise ValueError(f"Expected an evaluated candidate with a valid {field}")
    reference, time = record.get("reference"), record.get("time")
    if not isinstance(reference, dict) or not isinstance(time, torch.Tensor) or time.ndim != 1 or len(time) < 2:
        raise ValueError("Fit result is missing its paired reference trajectory")
    if not time.is_floating_point() or not torch.isfinite(time).all() or not (time.diff() > 0).all():
        raise ValueError("Invalid fit time: expected finite increasing sample times")
    for field, group in (("leg_order", legs), ("wheel_order", wheels)):
        names = record.get(field)
        if not isinstance(names, (list, tuple)) or not all(isinstance(n, str) for n in names):
            raise ValueError(f"Invalid {field} in fit result")
        if sorted(names) != sorted(group):
            raise ValueError(f"Incompatible {field}: fit={names}, task={list(group)}")

        response = "dof_pos" if field == "leg_order" else "dof_vel"
        if group:
            for key, source in ((response, reference), ("des_" + response, reference), ("sim_" + response, record)):
                tensor = source.get(key)
                if (
                    not isinstance(tensor, torch.Tensor)
                    or tensor.shape != (len(time), len(group))
                    or not tensor.is_floating_point()
                    or not torch.isfinite(tensor).all()
                ):
                    raise ValueError(f"Invalid or missing paired {key} trajectory for {field}")


def _named_parameters(record, legs, wheels) -> JointParameters:
    names, values = record.get("parameter_names"), record.get("params")
    if (
        not isinstance(names, (tuple, list))
        or not all(isinstance(n, str) for n in names)
        or not isinstance(values, torch.Tensor)
        or not values.is_floating_point()
        or values.shape != (len(names),)
    ):
        raise ValueError("Invalid named parameter vector in fit result")
    values = values.float()
    duplicates = [name for name, count in Counter(names).items() if count > 1]
    if duplicates:
        raise ValueError(f"Fit result contains duplicate parameters: {duplicates}")
    nonfinite = [names[i] for i in (~torch.isfinite(values)).nonzero().flatten().tolist()]
    if nonfinite:
        raise ValueError(f"Nonfinite fit parameters: {nonfinite}")
    indices = {name: i for i, name in enumerate(names)}
    joints = (*legs, *wheels)
    kinds = ["armature", "damping", "friction"]
    has_ratio = any(name.startswith("friction_ratio:") for name in names)
    if has_ratio:
        if record["settings"]["backend"] == "NewtonCfg":
            raise ValueError("Newton replay requires a single dry-friction parameter per joint")
        kinds.append("friction_ratio")
    required = {f"{kind}:{name}" for kind in kinds for name in joints}
    required.update(f"encoder_bias:{name}" for name in legs)
    required.add("delay")
    if required != indices.keys():
        raise ValueError(
            f"Missing parameters {sorted(required - indices.keys())}; extra {sorted(indices.keys() - required)}"
        )

    def block(kind, group):
        return values[[indices[f"{kind}:{name}"] for name in group]]

    armature, damping, friction = (block(kind, joints) for kind in kinds[:3])
    for kind, data in (("armature", armature), ("damping", damping), ("friction", friction)):
        invalid = [f"{kind}:{joints[i]}" for i in (data < 0).nonzero().flatten().tolist()]
        if invalid:
            raise ValueError(f"Expected nonnegative mechanical parameters: {invalid}")
    dynamic = friction
    if has_ratio:
        ratio = block("friction_ratio", joints)
        invalid = [joints[i] for i in ((ratio < 0) | (ratio > 1)).nonzero().flatten().tolist()]
        if invalid:
            raise ValueError(f"Expected friction_ratio in [0, 1] for {invalid}")
        dynamic = friction * ratio
    bias = torch.cat((block("encoder_bias", legs), values.new_zeros(len(wheels))))
    delay = values[indices["delay"]].item()
    candidate = record.get("delay_candidate")
    steps, seconds = record.get("delay_steps"), record.get("delay_seconds")
    if (
        type(steps) is not int
        or steps < 0
        or steps != math.floor(delay)
        or not isinstance(candidate, (float, int))
        or not math.isclose(candidate, delay, rel_tol=1e-7)
        or not isinstance(seconds, (float, int))
        or isinstance(seconds, bool)
        or not math.isclose(seconds, steps * record["settings"]["dt"], rel_tol=1e-7, abs_tol=1e-10)
    ):
        raise ValueError("Inconsistent applied delay in fit result")
    return JointParameters(armature, damping, friction, dynamic, bias, steps)


def latest_fit_result(task_log: Path) -> Path:
    """Select by fitting start time, including runs that have no best candidate yet."""
    runs = []
    for folder in task_log.iterdir() if task_log.is_dir() else ():
        if not folder.is_dir():
            continue
        try:
            started = datetime.strptime(folder.name, "%y_%m_%d_%H-%M-%S-%f")
        except ValueError:
            continue
        if started.strftime("%y_%m_%d_%H-%M-%S-%f") == folder.name:
            runs.append((started, folder))
    if not runs:
        raise FileNotFoundError(f"No fitting run in {task_log}")
    result = max(runs)[1] / "best_result.pt"
    if not result.is_file():
        raise FileNotFoundError(f"Latest fitting run is missing {result}")
    return result


def prediction_rmse(replay, reference) -> dict[str, float]:
    """Average physical squared prediction errors across samples and joints in each group."""
    return {
        field: (replay[field].double() - reference[field].double()).square().mean().sqrt().item()
        for field in ("dof_pos", "dof_vel")
        if field in replay
    }
