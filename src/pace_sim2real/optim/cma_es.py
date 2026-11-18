# © 2025 ETH Zurich, Robotic Systems Lab
# Author: Filip Bjelonic
# Licensed under the Apache License 2.0

"""CMA-ES identification with paired, evaluated position/velocity responses."""

from __future__ import annotations

import math
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import cmaes
import numpy as np
import torch
from torch.utils.tensorboard import SummaryWriter


def _error_scale(value: float | list[float], width: int, name: str, device: torch.device) -> torch.Tensor:
    if isinstance(value, list) and len(value) != width:
        raise ValueError(f"{name} requires {width} joint scales, got {len(value)}")
    values = value if isinstance(value, list) else [value]
    if any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in values):
        raise ValueError(f"{name} must contain finite positive scales")
    return torch.tensor(value, dtype=torch.float64, device=device)


class CMAESOptimizer:
    def __init__(
        self,
        bounds,
        population_size,
        log_dir,
        joint_order,
        max_iteration,
        data,
        device,
        epsilon=None,
        sigma=0.5,
        save_interval=10,
        save_optimization_process=False,
        separate_dynamic_friction=False,
        *,
        leg_order=None,
        wheel_order=None,
        position_error_scale=1.0,
        velocity_error_scale=1.0,
        position_weight=1.0,
        velocity_weight=1.0,
        reference_settings=None,
    ):
        self.leg_order = list(joint_order if leg_order is None else leg_order)
        self.wheel_order = list(wheel_order or [])
        self.joint_order = self.leg_order + self.wheel_order
        if (
            list(joint_order) != self.joint_order
            or not self.leg_order
            or len(set(self.joint_order)) != len(self.joint_order)
        ):
            raise ValueError("joint_order must contain unique leg_order + wheel_order")
        if population_size < 2 or max_iteration < 1:
            raise ValueError("Require population_size >=2 and max_iteration >=1")
        self.device = torch.device(device)
        self.population_size = population_size
        self.max_iteration, self.epsilon = max_iteration, epsilon
        if epsilon is not None and (not math.isfinite(epsilon) or epsilon < 0):
            raise ValueError("epsilon must be finite and nonnegative")
        self.save_interval = save_interval
        self.save_optimization_process = save_optimization_process
        self.separate_dynamic_friction = separate_dynamic_friction
        self.position_scale = _error_scale(
            position_error_scale, len(self.leg_order), "position_error_scale", self.device
        )
        self.velocity_scale = _error_scale(
            velocity_error_scale, len(self.wheel_order), "velocity_error_scale", self.device
        )
        self.weights = (position_weight, velocity_weight)
        if any(not math.isfinite(x) or x <= 0 for x in self.weights):
            raise ValueError("Group weights must be finite and positive")
        num_joints, num_legs = len(self.joint_order), len(self.leg_order)
        self.armature_idx, self.damping_idx, self.friction_idx = (
            slice(0, num_joints),
            slice(num_joints, 2 * num_joints),
            slice(2 * num_joints, 3 * num_joints),
        )
        self.bias_idx, self.delay_idx = slice(3 * num_joints, 3 * num_joints + num_legs), 3 * num_joints + num_legs
        self.friction_ratio_idx = slice(3 * num_joints + num_legs + 1, 4 * num_joints + num_legs + 1)
        k = 3 * num_joints + num_legs + 1 + (num_joints if separate_dynamic_friction else 0)
        self.bounds = torch.as_tensor(bounds, dtype=torch.float32, device=self.device).clone()
        if (
            self.bounds.shape != (k, 2)
            or not torch.isfinite(self.bounds).all()
            or (self.bounds[:, 0] > self.bounds[:, 1]).any()
        ):
            raise ValueError(f"Expected {k} finite ordered parameter bounds")
        if (self.bounds[: 3 * num_joints] < 0).any() or (self.bounds[self.delay_idx] < 0).any():
            raise ValueError("Mechanical parameters and delay must be nonnegative")
        if separate_dynamic_friction and (
            (self.bounds[self.friction_ratio_idx] < 0).any() or (self.bounds[self.friction_ratio_idx] > 1).any()
        ):
            raise ValueError("Friction ratio bounds must be within [0,1]")
        self.data = {name: value.detach().cpu().clone() for name, value in data.items()}
        self.num_samples = len(data["time"])
        if self.num_samples < 2:
            raise ValueError("Require at least two samples")
        for field, width in [("dof_pos", num_legs), ("des_dof_pos", num_legs)] + (
            [("dof_vel", len(self.wheel_order)), ("des_dof_vel", len(self.wheel_order))] if self.wheel_order else []
        ):
            if (
                field not in data
                or data[field].shape != (self.num_samples, width)
                or not torch.isfinite(data[field]).all()
            ):
                raise ValueError(f"Invalid reference field {field}")
        self.settings = dict(reference_settings or {})

        dt = self.settings["dt"]
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError("Fitting requires a single finite positive dt")
        self.settings.update(
            position_error_scale=position_error_scale,
            velocity_error_scale=velocity_error_scale,
            position_weight=position_weight,
            velocity_weight=velocity_weight,
            bounds=self.bounds.cpu(),
        )
        self.active = self.bounds[:, 1] > self.bounds[:, 0]
        dimension = int(self.active.sum())
        self.optimizer = (
            cmaes.CMA(
                mean=torch.zeros(dimension).numpy(),
                sigma=sigma,
                bounds=torch.tensor([[-1.0, 1.0]]).repeat(dimension, 1).numpy(),
                seed=0,
                population_size=population_size,
            )
            if dimension
            else None
        )
        self.log_dir = Path(log_dir) / datetime.now().strftime("%y_%m_%d_%H-%M-%S-%f")
        self.log_dir.mkdir(parents=True, exist_ok=False)
        self.writer = SummaryWriter(str(self.log_dir))
        self.iteration_counter = 0
        self.scores_counter = 0
        self.best_result: dict[str, Any] | None = None
        self.stop_reason = None
        self.scores_buffer = torch.zeros((max_iteration, population_size), device=self.device)
        self.sim_params_buffer = []
        self.sim_dof_pos_buffer = torch.empty((population_size, self.num_samples, num_legs), device=self.device)
        self.sim_dof_vel_buffer = torch.empty(
            (population_size, self.num_samples, len(self.wheel_order)), device=self.device
        )
        self.squared_errors = torch.zeros((population_size, num_joints), device=self.device, dtype=torch.float64)
        self.scores = torch.zeros(population_size, device=self.device, dtype=torch.float64)
        self._reset_population()
        config = dict(schema_version=2, leg_order=self.leg_order, wheel_order=self.wheel_order)
        self._atomic_save({**config, **self.data, **self.settings}, self.log_dir / "config.pt")

    def ask(self):
        return self.optimizer.ask() if self.optimizer is not None else torch.empty(0).numpy()

    def _params_to_sim_params(self, params):
        values = self.bounds[:, 0].expand(len(params) if params.ndim > 1 else 1, -1).clone()
        values[:, self.active] += (
            (params.reshape(values.shape[0], -1) + 1) / 2 * (self.bounds[self.active, 1] - self.bounds[self.active, 0])
        )
        return values if params.ndim > 1 else values[0]

    def _reset_population(self):
        # CMA runs on CPU; transfer one population instead of each candidate separately.
        self.params = torch.as_tensor(
            np.stack([self.ask() for _ in range(self.population_size)]), device=self.device, dtype=torch.float32
        )
        self.sim_params = self._params_to_sim_params(self.params)

    @torch.inference_mode()
    def tell(self, sim_dof_pos, real_dof_pos, *, sim_dof_vel=None, real_dof_vel=None):
        """Accumulate a sample [P,J] or trajectory chunk [P,T,J].

        Validate the complete chunk before changing buffers. Batched input keeps
        host synchronization and double-precision reduction outside simulation loops.
        """
        if sim_dof_pos.ndim not in (2, 3):
            raise ValueError("Response shape must be [population, joints] or [population, samples, joints]")
        batched = sim_dof_pos.ndim == 3
        count = sim_dof_pos.shape[1] if batched else 1
        if count < 1 or self.scores_counter + count > self.num_samples:
            raise ValueError("More samples than reference trajectory or empty response")
        population, num_legs, num_wheels = self.population_size, len(self.leg_order), len(self.wheel_order)
        groups = [(sim_dof_pos, real_dof_pos, num_legs)]
        if num_wheels:
            groups.append((sim_dof_vel, real_dof_vel, num_wheels))
        elif any(x is not None and x.numel() for x in (sim_dof_vel, real_dof_vel)):
            raise ValueError("Pure-position task received wheel data")
        for simulated, measured, width in groups:
            expected = (population, count, width) if batched else (population, width)
            if simulated is None or measured is None or simulated.shape != expected or measured.shape != expected:
                raise ValueError("Response shape must match population and joint group")
            if simulated.device != self.device or measured.device != self.device:
                raise ValueError("Response device must match optimizer")
            if not (torch.isfinite(simulated).all() & torch.isfinite(measured).all()):
                raise ValueError("Nonfinite response")
        samples = slice(self.scores_counter, self.scores_counter + count)
        q = sim_dof_pos if batched else sim_dof_pos.unsqueeze(1)
        measured_q = real_dof_pos if batched else real_dof_pos.unsqueeze(1)
        q = q - self.sim_params[:, None, self.bias_idx]
        self.sim_dof_pos_buffer[:, samples] = q
        self.squared_errors[:, :num_legs] += (q.double() - measured_q.double()).square().sum(dim=1)
        if num_wheels:
            assert sim_dof_vel is not None and real_dof_vel is not None
            v = sim_dof_vel if batched else sim_dof_vel.unsqueeze(1)
            measured_v = real_dof_vel if batched else real_dof_vel.unsqueeze(1)
            self.sim_dof_vel_buffer[:, samples] = v
            self.squared_errors[:, num_legs:] += (v.double() - measured_v.double()).square().sum(dim=1)
        self.scores_counter += count

    def evolve(self):
        if self.scores_counter != self.num_samples:
            raise ValueError("Only a complete rollout can evolve or become best")
        joint_mse = self.squared_errors / self.num_samples
        position_mse = joint_mse[:, : len(self.leg_order)]
        means = joint_mse.new_zeros((self.population_size, 2))
        means[:, 0] = position_mse.mean(dim=1)
        score = (position_mse / self.position_scale.square()).mean(dim=1) * self.weights[0]
        weight = self.weights[0]
        if self.wheel_order:
            velocity_mse = joint_mse[:, len(self.leg_order) :]
            means[:, 1] = velocity_mse.mean(dim=1)
            score += (velocity_mse / self.velocity_scale.square()).mean(dim=1) * self.weights[1]
            weight += self.weights[1]
        self.scores = score / weight
        if not torch.isfinite(self.scores).all():
            raise ValueError("Nonfinite objective")
        self.scores_buffer[self.iteration_counter] = self.scores
        # Logging and the CPU CMA implementation share one completed-generation transfer.
        statistics = torch.cat((means, self.scores[:, None]), dim=1).cpu()
        host_means, host_scores = statistics[:, :2], statistics[:, 2]
        index = int(host_scores.argmin())
        best_score = float(host_scores[index])
        self._relative_spread = float(
            (host_scores.max() - host_scores.min()) / host_scores.min().abs().clamp_min(1e-12)
        )
        if self.best_result is None or best_score < self.best_result["score"]:
            self.best_result = self._result(index, host_means, best_score)
            self._atomic_save(self.best_result, self.log_dir / "best_result.pt")
        host_params = self.sim_params.detach().cpu()
        if self.save_optimization_process:
            self.sim_params_buffer.append(host_params)
        if self.optimizer is not None:
            self.optimizer.tell(list(zip(self.params.cpu().numpy(), host_scores.tolist(), strict=True)))
            normalized_mean = torch.as_tensor(self.optimizer.mean, device=self.device)
            physical_mean = self._params_to_sim_params(normalized_mean).cpu()
        else:
            physical_mean = host_params[0]
        generation = self.iteration_counter
        groups = [
            ("1_Armature", self.armature_idx, self.joint_order),
            ("2_Viscous_Friction", self.damping_idx, self.joint_order),
            ("3_Static_Dynamic_Friction", self.friction_idx, self.joint_order),
            ("4_Bias", self.bias_idx, self.leg_order),
        ]
        if self.separate_dynamic_friction:
            groups.append(("6_Dynamic_Friction_Ratio", self.friction_ratio_idx, self.joint_order))
            dynamic_friction = host_params[index, self.friction_idx] * host_params[index, self.friction_ratio_idx]
            for name, value in zip(self.joint_order, dynamic_friction, strict=True):
                self.writer.add_scalar(f"6_Dynamic_Friction/best_{name}", value, generation)
        for group, columns, names in groups:
            for name, values, mean in zip(
                names, host_params[:, columns].unbind(dim=1), physical_mean[columns], strict=True
            ):
                self.writer.add_scalar(f"{group}/mean_{name}", mean, generation)
                self.writer.add_histogram(f"{group}/distribution_{name}", values, generation)
                self.writer.add_scalar(f"{group}/best_{name}", values[index], generation)

        delay = host_params[:, self.delay_idx]
        self.writer.add_histogram("0_Delay/distribution", delay, generation)
        self.writer.add_scalar("0_Delay/best", delay[index], generation)
        self.writer.add_scalar("0_Delay/mean", physical_mean[self.delay_idx], generation)
        self.writer.add_scalar("0_Episode/score", best_score, generation)
        self.writer.add_scalar("0_Episode/max_score", host_scores.max(), generation)
        self.writer.add_scalar("0_Episode/diff_score", self._relative_spread, generation)
        self.writer.add_scalar("score/best", best_score, self.iteration_counter)
        self.writer.add_scalar("error/position_rmse_rad", host_means[index, 0].sqrt().item(), self.iteration_counter)
        if self.wheel_order:
            self.writer.add_scalar(
                "error/velocity_rmse_rad_s", host_means[index, 1].sqrt().item(), self.iteration_counter
            )
        if self.save_interval > 0 and generation % self.save_interval == 0:
            self._atomic_save(physical_mean, self.log_dir / f"mean_{generation:03d}.pt")
        print(
            f"Generation {self.iteration_counter}: best score={best_score:.6g}; position"
            f" RMSE={host_means[index, 0].sqrt().item():.6g} rad; velocity"
            f" RMSE={host_means[index, 1].sqrt().item():.6g} rad/s"
        )
        self.iteration_counter += 1
        self.scores_counter = 0
        self.squared_errors.zero_()
        self._reset_population()

    def _result(self, index, means, score):
        params = self.sim_params[index].detach().cpu().clone()
        delay = float(params[self.delay_idx])
        names = [f"{kind}:{n}" for kind in ("armature", "damping", "friction") for n in self.joint_order]
        names += [f"encoder_bias:{n}" for n in self.leg_order] + ["delay"]
        if self.separate_dynamic_friction:
            names += [f"friction_ratio:{n}" for n in self.joint_order]
        result = dict(
            schema_version=2,
            params=params,
            parameter_names=names,
            leg_order=self.leg_order,
            wheel_order=self.wheel_order,
            generation=self.iteration_counter,
            candidate_index=index,
            time=self.data["time"].double(),
            original_time=self.data.get("original_time", self.data["time"]).double(),
            reference={k: v for k, v in self.data.items() if k != "original_time"},
            sim_dof_pos=self.sim_dof_pos_buffer[index].detach().cpu().clone(),
            score=score,
            position_rmse=means[index, 0].sqrt().item(),
            velocity_rmse=means[index, 1].sqrt().item() if self.wheel_order else None,
            settings=dict(self.settings),
            delay_candidate=delay,
            delay_steps=math.floor(delay),
            delay_seconds=math.floor(delay) * self.settings["dt"],
        )
        if self.wheel_order:
            result["sim_dof_vel"] = self.sim_dof_vel_buffer[index].detach().cpu().clone()
        return result

    def finished(self):
        if not self.iteration_counter:
            return False
        if self.iteration_counter >= self.max_iteration:
            self.stop_reason = "max_iteration"
        elif self.epsilon is not None and self._relative_spread < self.epsilon:
            self.stop_reason = "relative_spread"
        return self.stop_reason is not None

    def get_best_sim_params(self):
        if self.best_result is None:
            raise RuntimeError("No completed candidate evaluation")
        return self.best_result["params"].to(self.device).clone()

    def dynamic_friction(self):
        friction = self.sim_params[:, self.friction_idx]
        return friction * self.sim_params[:, self.friction_ratio_idx] if self.separate_dynamic_friction else friction

    def update_simulator(self, articulation, joint_ids, initial_position, *, initial_wheel_velocity=None):
        num_joints, num_legs, num_wheels = len(self.joint_order), len(self.leg_order), len(self.wheel_order)
        ids = torch.as_tensor(joint_ids, device=self.device, dtype=torch.long)
        if ids.shape != (num_joints,) or initial_position.shape != (self.population_size, num_legs):
            raise ValueError("Initial state shape does not match groups/population")
        if num_wheels and (
            initial_wheel_velocity is None or initial_wheel_velocity.shape != (self.population_size, num_wheels)
        ):
            raise ValueError("Mixed task requires initial wheel velocity")
        newton = "newton" in type(articulation).__module__
        if newton and self.separate_dynamic_friction:
            raise ValueError("Newton does not support separate dynamic friction identification")
        drives = []
        coverage = torch.zeros(num_joints, device=self.device, dtype=torch.long)
        for name, drive in articulation.actuators.items():
            if not callable(getattr(drive, "update_encoder_bias", None)) or not callable(
                getattr(drive, "update_time_lags", None)
            ):
                raise ValueError(f"{name}: Python PACE actuator required")
            if drive.cfg.delay_mode != self.settings.get("reference_delay_mode", "command"):
                raise ValueError("Reference and actuator delay modes differ")
            if self.bounds[self.delay_idx, 1] > drive.cfg.max_delay:
                raise ValueError("Candidate delay exceeds actuator capacity")
            drive_ids = torch.arange(articulation.num_joints, device=self.device)[drive.joint_indices]
            matches = ids[:, None] == drive_ids[None, :]
            if not (matches.sum(dim=0) == 1).all():
                raise ValueError("Every actuator joint must occur in controlled joint order")
            coverage += matches.sum(dim=1)
            drives.append((drive, matches.long().argmax(dim=0)))
        if not (coverage == 1).all():
            raise ValueError("Every controlled joint must have exactly one PACE actuator")
        env_ids = torch.arange(self.population_size, device=self.device)
        articulation.write_joint_armature_to_sim_index(
            armature=self.sim_params[:, self.armature_idx], joint_ids=ids, env_ids=env_ids
        )
        articulation.write_joint_friction_coefficient_to_sim_index(
            joint_friction_coeff=self.sim_params[:, self.friction_idx],
            joint_dynamic_friction_coeff=None if newton else self.dynamic_friction(),
            joint_viscous_friction_coeff=self.sim_params[:, self.damping_idx],
            joint_ids=ids,
            env_ids=env_ids,
        )
        position = articulation.data.default_joint_pos.torch[:, ids].clone()
        velocity = articulation.data.default_joint_vel.torch[:, ids].clone()
        position[:, :num_legs] = initial_position + self.sim_params[:, self.bias_idx]
        if num_wheels:
            velocity[:, num_legs:] = initial_wheel_velocity
        if not torch.isfinite(position).all() or not torch.isfinite(velocity).all():
            raise ValueError("Nonfinite initial state")
        self.settings.update(
            initial_wheel_angles=position[:, num_legs:].cpu(),
            initial_leg_velocities=velocity[:, :num_legs].cpu(),
        )
        articulation.write_joint_position_to_sim_index(position=position, joint_ids=ids, env_ids=env_ids)
        articulation.write_joint_velocity_to_sim_index(velocity=velocity, joint_ids=ids, env_ids=env_ids)
        bias = torch.zeros((self.population_size, num_joints), device=self.device)
        bias[:, :num_legs] = self.sim_params[:, self.bias_idx]
        for drive, local in drives:
            drive.update_encoder_bias(bias[:, local])
            drive.update_time_lags(self.sim_params[:, self.delay_idx].floor().long())
            drive.reset(env_ids)

    @staticmethod
    def _atomic_save(value, path):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temporary = stream.name
                torch.save(value, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None and os.path.exists(temporary):
                os.unlink(temporary)

    def close(self):
        if self.best_result is not None:
            self._atomic_save(self.best_result, self.log_dir / "best_result.pt")
        if self.save_optimization_process:
            self._atomic_save(
                {
                    "scores_buffer": self.scores_buffer[: self.iteration_counter].cpu(),
                    "sim_params_buffer": self.sim_params_buffer,
                },
                self.log_dir / "progress.pt",
            )
        self.writer.close()
