# © 2025 ETH Zurich, Robotic Systems Lab
# Author: Filip Bjelonic
# Licensed under the Apache License 2.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import torch
import warp as wp
from isaaclab.actuators import DCMotor
from isaaclab.actuators.actuator_base import resolve_joint_parameter
from isaaclab.utils import DelayBuffer
from isaaclab.utils.types import ArticulationActions

if TYPE_CHECKING:
    # only for type checking
    from .pace_actuator_cfg import PaceDCMotorCfg


class PaceDCMotor(DCMotor):
    """Pace DC Motor actuator model with encoder bias and action delay.

    The actuator models a DC motor whose controller receives joint positions in the encoder
    frame by subtracting a per-joint encoder bias to the true joint positions. In other words,
    the controller operates on biased (encoder) positions rather than the true joint positions.

    A configurable delay (in simulation steps) represents the latency between command calculation and actuation.
    By default, the commanded targets are delayed and the PD controller acts on the current measurements
    (:attr:`PaceDCMotorCfg.delay_mode` = "command"). Alternatively, the computed torque is delayed ("effort").

    The software implementation is inspired by DelayedPDActuator.
    """

    cfg: PaceDCMotorCfg

    def __init__(self, cfg: PaceDCMotorCfg, *args, **kwargs):
        super().__init__(cfg, *args, **kwargs)
        if isinstance(cfg.encoder_bias, (list, tuple)):
            if len(cfg.encoder_bias) != self.num_joints:
                raise ValueError(
                    f"encoder_bias must have {self.num_joints} elements (one per joint), "
                    f"but got {len(cfg.encoder_bias)}: {cfg.encoder_bias}"
                )
        if isinstance(cfg.encoder_bias, (list, tuple)):
            self.encoder_bias = torch.tensor(cfg.encoder_bias, device=self._device, dtype=torch.float32).repeat(
                self._num_envs, 1
            )
        else:
            self.encoder_bias = resolve_joint_parameter(
                cfg.encoder_bias, 0.0, self.joint_names, self._num_envs, self._device
            )

        if cfg.delay_mode not in ("command", "effort"):
            raise ValueError(f"delay_mode must be 'command' or 'effort', but got '{cfg.delay_mode}'.")
        # one buffer for the torque ("effort") or one per command signal ("command")
        buffer_names = ("effort",) if cfg.delay_mode == "effort" else ("position", "velocity", "effort")
        self.delay_buffers = {
            name: DelayBuffer(cfg.max_delay + 1, self._num_envs, device=self._device) for name in buffer_names
        }
        for buffer in self.delay_buffers.values():
            buffer.set_time_lag(cfg.max_delay, list(range(self._num_envs)))

    def reset(self, env_ids: Sequence[int] | slice | None = None, env_mask: wp.array | None = None):
        super().reset(env_ids, env_mask)
        selected = wp.to_torch(env_mask) if env_mask is not None else env_ids
        if isinstance(selected, slice):
            selected = torch.arange(self._num_envs, device=self._device)[selected]
        # reset buffers
        for buffer in self.delay_buffers.values():
            buffer.reset(selected)

    def update_encoder_bias(self, encoder_bias: torch.Tensor):
        if encoder_bias.shape != self.encoder_bias.shape or not torch.isfinite(encoder_bias).all():
            raise ValueError("encoder_bias must match actuator population/joint shape and be finite")
        self.encoder_bias = encoder_bias

    def update_time_lags(self, delay: int | torch.Tensor, env_ids: Sequence[int] | torch.Tensor | None = None):
        values = torch.as_tensor(delay)
        if (
            not torch.isfinite(values).all()
            or (values < 0).any()
            or (values > self.cfg.max_delay).any()
            or (values != values.floor()).any()
        ):
            raise ValueError("Delay must be integer physics steps within actuator capacity")
        if env_ids is None:
            env_ids = list(range(self._num_envs))
        elif isinstance(env_ids, torch.Tensor):
            env_ids = env_ids.cpu().tolist()
        for buffer in self.delay_buffers.values():
            buffer.set_time_lag(delay, env_ids)

    def compute(
        self, control_action: ArticulationActions, joint_pos: torch.Tensor, joint_vel: torch.Tensor
    ) -> ArticulationActions:
        control_action = self._delay_command(control_action)
        # compute actuator model with encoder bias subtracted from joint positions (joint position in encoder frame, not simulation frame)
        control_action_sim = super().compute(control_action, joint_pos - self.encoder_bias, joint_vel)
        if control_action_sim.joint_efforts is not None:
            control_action_sim.joint_efforts = self._delay_effort(control_action_sim.joint_efforts)
        return control_action_sim

    """
    Helper functions.
    """

    def _delay_command(self, control_action: ArticulationActions) -> ArticulationActions:
        """Delay the commanded targets (delay_mode "command")."""
        if self.cfg.delay_mode == "command":
            if control_action.joint_positions is not None:
                control_action.joint_positions = self.delay_buffers["position"].compute(control_action.joint_positions)
            if control_action.joint_velocities is not None:
                control_action.joint_velocities = self.delay_buffers["velocity"].compute(
                    control_action.joint_velocities
                )
            if control_action.joint_efforts is not None:
                control_action.joint_efforts = self.delay_buffers["effort"].compute(control_action.joint_efforts)
        return control_action

    def _delay_effort(self, effort: torch.Tensor) -> torch.Tensor:
        """Delay the computed torque (delay_mode "effort")."""
        if self.cfg.delay_mode == "effort":
            return self.delay_buffers["effort"].compute(effort)
        return effort
