# SPDX-License-Identifier: Apache-2.0
"""Shared PACE data and action contracts; no simulator imports at module load."""

from __future__ import annotations

import argparse
from dataclasses import MISSING
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    import torch


class ActionMapping(TypedDict):
    """Joint measurement IDs and command columns; transforms belong to task config."""

    leg_ids: list[int]
    wheel_ids: list[int]
    columns: list[int]
    num_legs: int
    num_wheels: int


def add_runtime_args(parser: argparse.ArgumentParser) -> None:
    """Register PACE runtime flags without importing any backend implementation.

    Selectors registered by Isaac Lab remain with its preset parser.
    Kit-only options are inert until launch_simulation selects a Kit runtime.
    """
    from isaaclab_tasks.utils.hydra import PresetTarget

    group = parser.add_argument_group("runtime")
    if not hasattr(PresetTarget, "VISUALIZER"):
        # v3.0.0 accepts the visualizer on the launcher namespace. Newer preset parsers own this selector.
        from isaaclab.app.sim_launcher import _parse_visualizer_csv

        group.add_argument("--visualizer", "--viz", type=_parse_visualizer_csv, help="Comma-separated viewer names.")
    group.add_argument("--device", default=None, help="Simulation device; default comes from the task config.")
    group.add_argument("--max_visible_envs", type=int, default=None, help="Limit the number of visible environments.")
    group.add_argument("--deterministic", action="store_true", help="Request deterministic simulation/rendering.")
    group.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    group.add_argument("--info", action="store_true", help="Enable info logging.")
    kit = parser.add_argument_group("Kit runtime (used only when selected)")
    kit.add_argument("--livestream", type=int, choices=(0, 1, 2), default=-1)
    kit.add_argument("--xr", action="store_true")
    kit.add_argument("--experience", default="")
    kit.add_argument("--kit_args", default="", help="Arguments forwarded to Kit when a Kit runtime is selected.")
    kit.add_argument("--anim_recording_enabled", action="store_true")
    kit.add_argument("--anim_recording_start_time", type=float, default=0.0)
    kit.add_argument("--anim_recording_stop_time", type=float, default=10.0)


def resolve_joint_groups(cfg):
    """Return canonical position/velocity names, accepting legacy pure-leg tasks."""
    legs = getattr(cfg, "leg_order", None)
    wheels = getattr(cfg, "wheel_order", None) or ()
    combined = getattr(cfg, "joint_order", None)
    if legs is None or isinstance(legs, type(MISSING)):
        if wheels:
            raise ValueError("Mixed tasks require leg_order")
        legs = combined
    if not isinstance(legs, (list, tuple)) or not isinstance(wheels, (list, tuple)) or not (legs or wheels):
        raise ValueError("Require a nonempty joint selection")
    names = tuple(legs) + tuple(wheels)
    if any(not isinstance(n, str) or not n for n in names) or len(set(names)) != len(names):
        raise ValueError("Joint groups must contain unique, disjoint names")
    if combined is not None and not isinstance(combined, type(MISSING)) and tuple(combined) != names:
        raise ValueError("joint_order must equal leg_order + wheel_order")
    return tuple(legs), tuple(wheels)


def reference_groups(cfg):
    """Resolve each file group independently in its declared column order."""
    groups = []
    for field, full in zip(("reference_leg_order", "reference_wheel_order"), resolve_joint_groups(cfg), strict=True):
        names = getattr(cfg, field, None)
        if names is None:
            names = full
        if not isinstance(names, (list, tuple)) or any(not isinstance(name, str) or name not in full for name in names):
            raise ValueError(f"{field} contains unknown or wrong-type joints: {names}")
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate joint in {field}")
        groups.append(tuple(names))
    if not any(groups):
        raise ValueError("Reference requires at least one recorded joint")
    return groups[0], groups[1]


def selected_fit_config(cfg, legs, wheels):
    """Project each physical parameter block and both scales to file order."""
    full_legs, full_wheels = resolve_joint_groups(cfg)
    full = full_legs + full_wheels
    selected = [full.index(name) for name in (*legs, *wheels)]
    width = len(full)
    delay = 3 * width + len(full_legs)
    rows = [block * width + i for block in range(3) for i in selected]
    rows.extend(3 * width + full_legs.index(name) for name in legs)
    rows.append(delay)
    if cfg.separate_dynamic_friction:
        rows.extend(delay + 1 + i for i in selected)
    expected = delay + 1 + (width if cfg.separate_dynamic_friction else 0)
    if tuple(cfg.bounds_params.shape) != (expected, 2):
        raise ValueError(f"Expected {expected} task parameter bounds")

    def scale(value, names, group):
        if not isinstance(value, list):
            return value
        if len(value) != len(group):
            raise ValueError(f"Expected {len(group)} task joint error scales")
        return [value[group.index(name)] for name in names]

    return (
        cfg.bounds_params[rows],
        scale(cfg.cmaes.position_error_scale, legs, full_legs),
        scale(cfg.cmaes.velocity_error_scale, wheels, full_wheels),
    )


def resolve_action_mapping(env, leg_order, wheel_order) -> ActionMapping:
    """Resolve installed absolute joint action terms without importing a simulator."""
    names = tuple(leg_order) + tuple(wheel_order)
    robot = env.scene["robot"]
    if any(robot.joint_names.count(n) != 1 for n in names):
        raise ValueError("Each controlled joint must exist exactly once in articulation")
    columns = {}
    start = 0
    for key in env.action_manager.active_terms:
        term = env.action_manager.get_term(key)
        kind = type(term).__name__
        if type(term).__module__ != "isaaclab.envs.mdp.actions.joint_actions" or kind not in (
            "JointPositionAction",
            "JointVelocityAction",
        ):
            raise ValueError(f"Unsupported action type: {type(term).__name__}")
        expected = leg_order if kind == "JointPositionAction" else wheel_order
        if term.cfg.asset_name != "robot" or len(term._joint_names) != term.action_dim:
            raise ValueError("Unsupported action asset or dimensions")
        for index, name in enumerate(term._joint_names):
            if name not in expected or name in columns:
                raise ValueError(f"Ambiguous or wrong-type action joint: {name}")
            columns[name] = start + index
        start += term.action_dim
    if set(columns) != set(names):
        raise ValueError("Action terms must cover all declared joint groups exactly once")
    return {
        "leg_ids": [robot.joint_names.index(n) for n in leg_order],
        "wheel_ids": [robot.joint_names.index(n) for n in wheel_order],
        "columns": [columns[n] for n in names],
        "num_legs": len(leg_order),
        "num_wheels": len(wheel_order),
    }


def pack_actions(
    mapping: ActionMapping, desired_pos: torch.Tensor, desired_vel: torch.Tensor | None = None
) -> torch.Tensor:
    """Reorder a batch of targets into action columns without changing values.

    Task configuration owns scale, offset and clipping. PACE tasks use absolute
    targets (unit scale, zero offset, no clipping). The batch can represent
    environments or trajectory samples, allowing packing outside the step loop.
    """
    if desired_pos.ndim != 2 or desired_pos.shape[1] != mapping["num_legs"]:
        raise ValueError("Position target shape does not match declared leg group")
    batch = desired_pos.shape[0]
    if mapping["num_wheels"]:
        if desired_vel is None or desired_vel.shape != (batch, mapping["num_wheels"]):
            raise ValueError("Velocity target shape does not match declared wheel group")
    elif desired_vel is not None and desired_vel.shape != (batch, 0):
        raise ValueError("Pure-leg tasks cannot have velocity targets")
    if desired_vel is not None and (desired_vel.device != desired_pos.device or desired_vel.dtype != desired_pos.dtype):
        raise ValueError("Position and velocity targets must share dtype/device")

    actions = desired_pos.new_empty((batch, len(mapping["columns"])))
    actions[:, mapping["columns"][: mapping["num_legs"]]] = desired_pos
    if desired_vel is not None:
        actions[:, mapping["columns"][mapping["num_legs"] :]] = desired_vel
    return actions


def load_reference_data(path, cfg, step_dt):
    """Load declared reference measurements without inferring physical provenance."""
    import math

    import torch

    legs, wheels = reference_groups(cfg)
    if getattr(cfg, "reference_bias_model", "feedback_and_measurement") != "feedback_and_measurement":
        raise ValueError("Unsupported reference bias model: recollect data with feedback_and_measurement")
    if getattr(cfg, "reference_delay_mode", "command") not in ("command", "effort"):
        raise ValueError("Invalid reference delay mode")
    data = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(data, dict):
        raise ValueError("Reference must be a tensor dictionary")
    fields = {"time", "dof_pos", "des_dof_pos", "dof_vel", "des_dof_vel"}
    if "time" not in data or data.keys() - fields:
        raise ValueError("Reference fields must match recorded position and velocity groups")
    for field, group in (("dof_pos", legs), ("dof_vel", wheels)):
        measured, desired = field in data, "des_" + field in data
        if measured != desired or (group and not measured):
            raise ValueError(f"Reference requires paired {field} and des_{field} for recorded channels")
    for key, value in data.items():
        if not isinstance(value, torch.Tensor) or not value.is_floating_point() or not torch.isfinite(value).all():
            raise ValueError(f"{key} must be a finite floating tensor")
    time = data["time"].double()
    if time.ndim != 1 or len(time) < 2 or not (time.diff() > 0).all():
        raise ValueError("time must be increasing with at least two samples")
    for key in data.keys() - {"time"}:
        width = len(wheels) if key.endswith("vel") else len(legs)
        if data[key].shape != (len(time), width):
            raise ValueError(f"{key} shape does not match sample count and declared groups")
        data[key] = data[key].float()
        if not torch.isfinite(data[key]).all():
            raise ValueError(f"{key} exceeds float32 range")
    if not math.isfinite(step_dt) or step_dt <= 0:
        raise ValueError("Control timestep must be positive")
    mode = getattr(cfg, "time_mode", "strict")
    legacy = getattr(cfg, "legacy_sample_dt", None)
    expected = torch.arange(len(time), dtype=torch.float64) * step_dt
    if mode == "strict":
        if legacy is not None or not torch.allclose(time - time[0], expected, rtol=1e-5, atol=1e-7):
            raise ValueError(
                "Reference time does not match control interval; declare legacy_index and real interval if appropriate"
            )
        effective = time - time[0]
    elif mode == "legacy_index":
        if (
            legacy is None
            or not math.isfinite(legacy)
            or legacy <= 0
            or not math.isclose(legacy, step_dt, rel_tol=1e-5, abs_tol=1e-7)
        ):
            raise ValueError("legacy_sample_dt must match the real control interval")
        effective = torch.arange(len(time), dtype=torch.float64) * legacy
    else:
        raise ValueError("Unknown time_mode")
    return {**data, "time": effective, "original_time": time}
