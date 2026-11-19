# SPDX-License-Identifier: Apache-2.0
"""Apply recorded commands and candidate parameters inside a fully controlled task."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch

from .collection_contracts import resolve_action_mapping, resolve_joint_groups


@dataclass
class _ParticipatingDrive:
    actuator: Any
    default_bias: torch.Tensor
    local_columns: list[int]
    candidate_columns: list[int]


class SubsetControl:
    """Name mappings and task baselines captured before the first candidate writes."""

    @classmethod
    def for_fit(cls, env, legs, wheels):
        """Full recordings with a position group retain the v2 rollout."""
        full_legs, full_wheels = resolve_joint_groups(env.cfg.sim2real)
        if legs and len(legs) == len(full_legs) and len(wheels) == len(full_wheels):
            return None
        return cls(env, legs, wheels)

    def __init__(self, env, legs, wheels):
        self.robot = robot = env.scene["robot"]
        self.legs, self.wheels = tuple(legs), tuple(wheels)
        self.task_legs, self.task_wheels = resolve_joint_groups(env.cfg.sim2real)
        self.mapping = resolve_action_mapping(env, self.task_legs, self.task_wheels)
        self.leg_columns = [self.task_legs.index(n) for n in legs]
        self.wheel_columns = [self.task_wheels.index(n) for n in wheels]
        selected = (*legs, *wheels)
        full = self.task_legs + self.task_wheels
        self.ids = torch.tensor([robot.joint_names.index(n) for n in selected], device=env.device)
        self.task_ids = torch.tensor([robot.joint_names.index(n) for n in full], device=env.device)
        self.env_ids = torch.arange(env.num_envs, device=env.device)
        self.initial_q = robot.data.default_joint_pos.torch[:, self.task_ids].clone()
        self.initial_v = robot.data.default_joint_vel.torch[:, self.task_ids].clone()
        self.hold_q = self.initial_q[0, : len(self.task_legs)].clone()
        self.hold_v = self.initial_v[0, len(self.task_legs) :].clone()
        self.drives = []
        self.delay_groups = {}
        self.leg_ids = [self.mapping["leg_ids"][i] for i in self.leg_columns]
        self.wheel_ids = [self.mapping["wheel_ids"][i] for i in self.wheel_columns]
        self.wheel_state_columns = [len(self.task_legs) + i for i in self.wheel_columns]
        self.held_leg_columns = [i for i, n in enumerate(self.task_legs) if n not in legs]
        covered = []
        for key, drive in robot.actuators.items():
            if not all(
                callable(getattr(drive, method, None)) for method in ("update_encoder_bias", "update_time_lags")
            ):
                raise ValueError(f"{key}: Python PACE actuator required")
            indices = torch.arange(robot.num_joints, device=env.device)[drive.joint_indices].tolist()
            names = [robot.joint_names[i] for i in indices]
            for local, name in enumerate(names):
                if name in self.task_legs:
                    self.hold_q[self.task_legs.index(name)] -= drive.encoder_bias[0, local]
            covered.extend(names)
            members = [n for n in names if n in selected]
            if members:
                if drive.cfg.delay_mode != env.cfg.sim2real.reference_delay_mode:
                    raise ValueError(f"Incompatible delay mode on {key}")
                self.delay_groups[key] = names
                self.drives.append(
                    _ParticipatingDrive(
                        drive,
                        drive.encoder_bias.clone(),
                        [names.index(n) for n in members],
                        [selected.index(n) for n in members],
                    )
                )
        if not (
            torch.isfinite(self.initial_q).all()
            & torch.isfinite(self.initial_v).all()
            & torch.isfinite(self.hold_q).all()
        ):
            raise ValueError("Nonfinite task initial state or encoder holding target")
        if sorted(covered) != sorted(full):
            raise ValueError("Each controlled joint requires exactly one PACE actuator")

    def settings(self):
        def held(names, selected, values):
            return {n: value for n, value in zip(names, values.tolist(), strict=True) if n not in selected}

        return dict(
            task_leg_order=list(self.task_legs),
            task_wheel_order=list(self.task_wheels),
            hold_positions=held(self.task_legs, self.legs, self.hold_q),
            hold_velocities=held(self.task_wheels, self.wheels, self.hold_v),
            delay_actuator_groups=self.delay_groups,
            initial_wheel_angles=self.initial_q[:, self.wheel_state_columns].cpu(),
            initial_leg_velocities=self.initial_v[:, self.leg_columns].cpu(),
        )

    def targets(self, pos, vel):
        """Expand file-order commands into task order before packing action columns."""
        count = len(pos)
        positions = self.hold_q.expand(count, -1).clone()
        velocities = self.hold_v.expand(count, -1).clone()
        positions[:, self.leg_columns] = pos
        if self.wheels:
            velocities[:, self.wheel_columns] = vel
        return positions, velocities if self.task_wheels else None

    def check_delay(self, maximum):
        for drive in self.drives:
            if maximum > drive.actuator.cfg.max_delay:
                raise ValueError("Candidate delay exceeds actuator capacity")

    def apply(self, armature, damping, friction, dynamic, leg_bias, delay, first_pos, first_vel):
        """Apply one population (or one broadcast replay candidate) after environment reset."""
        robot, ids, envs = self.robot, self.ids, self.env_ids
        robot.write_joint_armature_to_sim_index(armature=armature.contiguous(), joint_ids=ids, env_ids=envs)
        robot.write_joint_friction_coefficient_to_sim_index(
            joint_friction_coeff=friction.contiguous(),
            joint_dynamic_friction_coeff=None if dynamic is None else dynamic.contiguous(),
            joint_viscous_friction_coeff=damping.contiguous(),
            joint_ids=ids,
            env_ids=envs,
        )
        q, v = self.initial_q.clone(), self.initial_v.clone()
        q[:, self.leg_columns] = first_pos + leg_bias
        v[:, self.held_leg_columns] = 0
        if self.wheels:
            v[:, self.wheel_state_columns] = first_vel
        robot.write_joint_position_to_sim_index(position=q, joint_ids=self.task_ids, env_ids=envs)
        robot.write_joint_velocity_to_sim_index(velocity=v, joint_ids=self.task_ids, env_ids=envs)
        bias = torch.cat((leg_bias, leg_bias.new_zeros((len(envs), len(self.wheels)))), dim=1)
        for drive in self.drives:
            values = drive.default_bias.clone()
            values[:, drive.local_columns] = bias[:, drive.candidate_columns]
            drive.actuator.update_encoder_bias(values)
            drive.actuator.update_time_lags(delay)
            drive.actuator.reset(envs)
