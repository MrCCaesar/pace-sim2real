# SPDX-License-Identifier: Apache-2.0
"""Shared PACE data and action contracts; no simulator imports at module load."""

from __future__ import annotations

from dataclasses import MISSING


def resolve_joint_groups(cfg):
    """Return canonical position/velocity names, accepting legacy pure-leg tasks."""
    legs = getattr(cfg, "leg_order", None)
    wheels = getattr(cfg, "wheel_order", None) or ()
    combined = getattr(cfg, "joint_order", None)
    if legs is None or isinstance(legs, type(MISSING)):
        if wheels:
            raise ValueError("Mixed tasks require leg_order")
        legs = combined
    if not isinstance(legs, (list, tuple)) or not legs or not isinstance(wheels, (list, tuple)):
        raise ValueError("Require nonempty leg_order and a sequence wheel_order")
    names = tuple(legs) + tuple(wheels)
    if any(not isinstance(n, str) or not n for n in names) or len(set(names)) != len(names):
        raise ValueError("Joint groups must contain unique, disjoint names")
    if combined is not None and not isinstance(combined, type(MISSING)) and tuple(combined) != names:
        raise ValueError("joint_order must equal leg_order + wheel_order")
    return tuple(legs), tuple(wheels)


def resolve_action_mapping(env, leg_order, wheel_order):
    """Resolve installed absolute joint action terms without importing a simulator."""
    import torch

    names = tuple(leg_order) + tuple(wheel_order)
    robot = env.scene["robot"]
    if any(robot.joint_names.count(n) != 1 for n in names):
        raise ValueError("Each controlled joint must exist exactly once in articulation")
    columns, scales, offsets, clips = {}, [], [], []
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
        shape = (env.num_envs, term.action_dim)
        for value, destination in ((term._scale, scales), (term._offset, offsets)):
            tensor = torch.as_tensor(value, device=env.device, dtype=torch.float32).expand(shape).clone()
            if not torch.isfinite(tensor).all():
                raise ValueError("Action scale/offset must be finite")
            destination.append(tensor)
        clip = getattr(term, "_clip", None) if term.cfg.clip is not None else None
        clips.append(clip)
        start += term.action_dim
    if set(columns) != set(names):
        raise ValueError("Action terms must cover all declared joint groups exactly once")
    scale = torch.cat(scales, dim=1)
    if (scale == 0).any():
        raise ValueError("Action scale must be nonzero")
    return {
        "leg_ids": [robot.joint_names.index(n) for n in leg_order],
        "wheel_ids": [robot.joint_names.index(n) for n in wheel_order],
        "columns": [columns[n] for n in names],
        "scale": scale,
        "offset": torch.cat(offsets, dim=1),
        "clips": clips,
        "term_dims": [x.shape[1] for x in scales],
        "num_legs": len(leg_order),
        "num_wheels": len(wheel_order),
    }


def pack_actions(mapping, desired_pos, desired_vel=None):
    """Pack physical targets into action columns, rejecting lossy clipping."""
    import torch

    scale, offset = mapping["scale"], mapping["offset"]
    batch = scale.shape[0]
    for target, count in ((desired_pos, mapping["num_legs"]), (desired_vel, mapping["num_wheels"])):
        if count == 0 and target is None:
            continue
        if target is None or target.shape != (batch, count):
            raise ValueError("Physical target shape does not match declared groups")
        if target.device != scale.device or target.dtype != scale.dtype or not torch.isfinite(target).all():
            raise ValueError("Physical targets must be finite and match action dtype/device")
    desired = desired_pos if desired_vel is None else torch.cat((desired_pos, desired_vel), dim=1)
    physical = torch.empty_like(scale)
    physical[:, mapping["columns"]] = desired
    start = 0
    for size, clip in zip(mapping["term_dims"], mapping["clips"], strict=True):
        if clip is not None:
            values = physical[:, start : start + size]
            if ((values < clip[:, :, 0]) | (values > clip[:, :, 1])).any():
                raise ValueError("Action clipping would change physical targets")
        start += size
    actions = (physical - offset) / scale
    if not torch.isfinite(actions).all():
        raise ValueError("Action transform produced nonfinite values")
    return actions


def load_reference_data(path, cfg, step_dt):
    """Load declared reference measurements without inferring physical provenance."""
    import math

    import torch

    legs, wheels = resolve_joint_groups(cfg)
    for key, expected in (("reference_leg_order", legs), ("reference_wheel_order", wheels)):
        declared = getattr(cfg, key, None)
        if declared is not None and tuple(declared) != expected:
            raise ValueError(f"{key} must match task column order")
    if getattr(cfg, "reference_bias_model", "feedback_and_measurement") != "feedback_and_measurement":
        raise ValueError("Unsupported reference bias model: recollect data with feedback_and_measurement")
    if getattr(cfg, "reference_delay_mode", "command") not in ("command", "effort"):
        raise ValueError("Invalid reference delay mode")
    data = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(data, dict):
        raise ValueError("Reference must be a tensor dictionary")
    fields = {"time", "dof_pos", "des_dof_pos"}
    velocity_fields = {"dof_vel", "des_dof_vel"}
    if not fields <= data.keys() or data.keys() - (fields | velocity_fields):
        raise ValueError("Missing or unknown reference fields")
    if bool(data.keys() & velocity_fields) and not velocity_fields <= data.keys():
        raise ValueError("Both wheel velocity fields are required")
    if wheels and not velocity_fields <= data.keys():
        raise ValueError("Mixed task requires wheel velocity fields")
    for key, value in data.items():
        if not isinstance(value, torch.Tensor) or not value.is_floating_point() or not torch.isfinite(value).all():
            raise ValueError(f"{key} must be a finite floating tensor")
    time = data["time"].double()
    if time.ndim != 1 or len(time) < 2 or not (time.diff() > 0).all():
        raise ValueError("time must be increasing with at least two samples")
    for key in fields - {"time"} | (velocity_fields & data.keys()):
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
