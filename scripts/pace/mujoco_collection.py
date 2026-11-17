# SPDX-License-Identifier: Apache-2.0

"""Native MuJoCo collection, independent of Isaac Lab package initialization."""

from __future__ import annotations

import importlib
import math
import tomllib
from collections.abc import Sequence
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class CollectionConfig:
    """Run settings in SI units; physics and sensor noise belong to MJCF."""

    model_path: Path
    position_joints: tuple[str, ...]
    velocity_joints: tuple[str, ...]
    position_centers: tuple[float, ...]
    position_amplitudes: tuple[float, ...]
    velocity_amplitudes: tuple[float, ...]
    encoder_bias: float | tuple[float, ...]
    min_frequency: float
    max_frequency: float
    duration: float
    seed: int
    plot: bool
    position_directions: tuple[float, ...] = (1.0,) * 12
    velocity_directions: tuple[float, ...] = (1.0,) * 4
    visualize: bool = False


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _vector(value: object, name: str, size: int) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError(f"{name} must contain {size} numbers")
    return tuple(_number(v, name) for v in value)


def load_config(path: Path) -> CollectionConfig:
    """Load an explicit TOML configuration, resolving the model relative to it."""
    with path.open("rb") as stream:
        raw = tomllib.load(stream)
    schema = {
        "run": {"min_frequency", "max_frequency", "duration", "plot", "seed"},
        "model": {"path"},
        "trajectory": {"position_centers", "position_amplitudes", "velocity_amplitudes"},
        "measurement": {"encoder_bias"},
        "channels": {"position_joints", "velocity_joints"},
    }
    if raw.keys() != schema.keys():
        raise ValueError(f"Configuration sections must be {sorted(schema)}")
    optional = {"trajectory": {"position_directions", "velocity_directions"}, "run": {"visualize"}}
    for name, keys in schema.items():
        allowed = keys | optional.get(name, set())
        if not isinstance(raw[name], dict) or not keys <= raw[name].keys() <= allowed:
            raise ValueError(f"{name} requires {sorted(keys)}; allowed keys: {sorted(allowed)}")
    run, trajectory, channels = raw["run"], raw["trajectory"], raw["channels"]
    for name, count in [("position_joints", 12), ("velocity_joints", 4)]:
        values = channels[name]
        if not isinstance(values, list) or len(values) != count or any(not isinstance(v, str) or not v for v in values):
            raise ValueError(f"channels.{name} must contain {count} joint names")
    model_path = raw["model"]["path"]
    if not isinstance(model_path, str) or not model_path:
        raise ValueError("model.path must be a nonempty string")
    bias = raw["measurement"]["encoder_bias"]
    config = CollectionConfig(
        model_path=(path.resolve().parent / model_path).resolve(),
        position_joints=tuple(channels["position_joints"]),
        velocity_joints=tuple(channels["velocity_joints"]),
        position_centers=_vector(trajectory["position_centers"], "position_centers", 12),
        position_amplitudes=_vector(trajectory["position_amplitudes"], "position_amplitudes", 12),
        velocity_amplitudes=_vector(trajectory["velocity_amplitudes"], "velocity_amplitudes", 4),
        encoder_bias=_vector(bias, "encoder_bias", 12) if isinstance(bias, list) else _number(bias, "encoder_bias"),
        min_frequency=_number(run["min_frequency"], "min_frequency"),
        max_frequency=_number(run["max_frequency"], "max_frequency"),
        duration=_number(run["duration"], "duration"),
        seed=run["seed"],
        plot=run["plot"],
        visualize=run.get("visualize", False),
        position_directions=_vector(trajectory.get("position_directions", (1.0,) * 12), "position_directions", 12),
        velocity_directions=_vector(trajectory.get("velocity_directions", (1.0,) * 4), "velocity_directions", 4),
    )
    _validate_config(config)
    return config


def _validate_config(config: CollectionConfig) -> None:
    for name, size in [("position_directions", 12), ("velocity_directions", 4)]:
        if any(value not in (-1, 1) for value in _vector(getattr(config, name), name, size)):
            raise ValueError(f"{name} must contain only +1 or -1")
    for name, size in [("position_centers", 12), ("position_amplitudes", 12), ("velocity_amplitudes", 4)]:
        values = _vector(getattr(config, name), name, size)
        if name.endswith("amplitudes") and min(values) < 0:
            raise ValueError(f"{name} must be nonnegative")
    if isinstance(config.encoder_bias, tuple):
        _vector(config.encoder_bias, "encoder_bias", 12)
    else:
        _number(config.encoder_bias, "encoder_bias")
    f0 = _number(config.min_frequency, "min_frequency")
    f1 = _number(config.max_frequency, "max_frequency")
    if not 0 < f0 <= f1:
        raise ValueError("Require 0 < min_frequency <= max_frequency")
    if _number(config.duration, "duration") <= 0:
        raise ValueError("duration must be positive")
    if type(config.seed) is not int or config.seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if type(config.visualize) is not bool:
        raise ValueError("visualize must be a boolean")
    if type(config.plot) is not bool:
        raise ValueError("plot must be a boolean")
    names = config.position_joints + config.velocity_joints
    if len(config.position_joints) != 12 or len(config.velocity_joints) != 4:
        raise ValueError("Require 12 position joints and 4 velocity joints")
    if any(not isinstance(n, str) or not n for n in names) or len(set(names)) != 16:
        raise ValueError("Joint names must be nonempty and unique")


@dataclass(frozen=True)
class CollectionData:
    """Synchronous SI-valued measurements and un-delayed commands."""

    time: FloatArray
    dof_pos: FloatArray
    des_dof_pos: FloatArray
    dof_vel: FloatArray
    des_dof_vel: FloatArray


def _validate_channel(model: Any, joint: int, actuator: int, sensor: int, position: bool, name: str) -> None:
    mj: Any = importlib.import_module("mujoco")
    if model.jnt_type[joint] != mj.mjtJoint.mjJNT_HINGE:
        raise ValueError(f"{name}: require a scalar hinge joint")
    gain = model.actuator_gainprm[actuator]
    bias = model.actuator_biasprm[actuator]
    expected_bias = np.zeros(10)
    expected_bias[1] = -gain[0] if position else 0
    expected_bias[2] = bias[2] if position else -gain[0]
    if (
        model.actuator_trntype[actuator] != mj.mjtTrn.mjTRN_JOINT
        or not np.array_equal(model.actuator_gear[actuator], [1, 0, 0, 0, 0, 0])
        or model.actuator_ctrlnum[actuator] != 1
        or model.actuator_dyntype[actuator] != mj.mjtDyn.mjDYN_NONE
        or model.actuator_gaintype[actuator] != mj.mjtGain.mjGAIN_FIXED
        or model.actuator_biastype[actuator] != mj.mjtBias.mjBIAS_AFFINE
        or not np.isfinite(gain).all()
        or not np.isfinite(bias).all()
        or gain[0] <= 0
        or np.any(gain[1:] != 0)
        or bias[2] > 0
        or not np.array_equal(bias, expected_bias)
    ):
        raise ValueError(f"{name}: unsupported actuator; require unit-gear native position/velocity servo")
    delay = float(model.actuator_delay[actuator])
    samples = int(model.actuator_history[actuator, 0])
    if not math.isfinite(delay) or delay < 0 or delay > samples * model.opt.timestep + 1e-12:
        raise ValueError(f"{name}: actuator delay exceeds history capacity or is invalid")
    if model.sensor_dim[sensor] != 1 or model.sensor_delay[sensor] != 0 or np.any(model.sensor_interval[sensor] != 0):
        raise ValueError(f"{name}: require an instantaneous scalar sensor without delay/interval")
    noise = float(model.sensor_noise[sensor])
    if not math.isfinite(noise) or noise < 0:
        raise ValueError(f"{name}: sensor noise must be finite and nonnegative")


def collect(config: CollectionConfig) -> CollectionData:
    """Collect a complete run in memory without saving or plotting."""
    # MuJoCo exposes its C-extension API dynamically without complete type stubs.
    mujoco: Any = importlib.import_module("mujoco")

    _validate_config(config)
    model = mujoco.MjModel.from_xml_path(str(config.model_path))
    dt = float(model.opt.timestep)
    if not math.isfinite(dt) or dt <= 0:
        raise ValueError("model timestep must be finite and positive")
    if model.nu != 16 or model.nq != 16 or model.nv != 16:
        raise ValueError("Require a fixed-base model with exactly 16 scalar hinge joints and actuators")
    ratio = config.duration / dt
    if not math.isfinite(ratio):
        raise ValueError("duration/timestep must be finite")
    steps = round(ratio)
    if steps < 1 or abs(steps - ratio) > 1e-9:
        raise ValueError("duration must be a positive integer multiple of model timestep")
    if config.max_frequency >= 0.5 / dt:
        raise ValueError("max_frequency must be below the sampling Nyquist frequency")
    joint_ids, actuator_ids, sensor_ids = [], [], []
    for index, name in enumerate(config.position_joints + config.velocity_joints):
        joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if joint < 0:
            raise ValueError(f"Missing joint: {name}")
        actuators = np.flatnonzero(model.actuator_trnid[:, 0] == joint)
        sensor_type = mujoco.mjtSensor.mjSENS_JOINTPOS if index < 12 else mujoco.mjtSensor.mjSENS_JOINTVEL
        sensors = np.flatnonzero((model.sensor_objid == joint) & (model.sensor_type == sensor_type))
        if len(actuators) != 1 or len(sensors) != 1:
            raise ValueError(f"{name}: require one actuator and one matching joint sensor")
        _validate_channel(model, joint, int(actuators[0]), int(sensors[0]), index < 12, name)
        joint_ids.append(joint)
        actuator_ids.append(int(actuators[0]))
        sensor_ids.append(int(sensors[0]))
    data = mujoco.MjData(model)
    directions = np.array((*config.position_directions, *config.velocity_directions))
    centers = np.array((*config.position_centers, 0.0, 0.0, 0.0, 0.0)) * directions
    amplitudes = np.array((*config.position_amplitudes, *config.velocity_amplitudes))
    ctrl_ids = model.actuator_ctrladr[actuator_ids]
    data.qpos[model.jnt_qposadr[joint_ids]] = centers
    data.qvel[:] = 0
    data.ctrl[ctrl_ids] = centers
    for index, actuator in enumerate(actuator_ids):
        samples = int(model.actuator_history[actuator, 0])
        if samples:
            mujoco.mj_initCtrlHistory(model, data, actuator, None, np.full((samples, 1), centers[index]))
    time = np.arange(steps, dtype=np.float64) * dt
    phase = (
        2
        * np.pi
        * (
            config.min_frequency * time
            + (config.max_frequency - config.min_frequency) * time**2 / (2 * config.duration)
        )
    )
    desired = centers + np.sin(phase[:, None]) * amplitudes * directions
    measured = np.empty((steps, 16), dtype=np.float64)
    rng = np.random.default_rng(config.seed)
    noise = model.sensor_noise[sensor_ids]
    sensor_addresses = model.sensor_adr[sensor_ids]
    session = nullcontext()
    if config.visualize:
        from mujoco_viewer import ViewerSession

        session = ViewerSession(config.model_path, model, data)
    with session as viewer:
        for step in range(steps):
            data.ctrl[ctrl_ids] = desired[step]
            mujoco.mj_forward(model, data)
            _check_dynamics(data, time[step], step)
            measured[step] = data.sensordata[sensor_addresses] + rng.normal(0, noise)
            measured[step, :12] -= config.encoder_bias
            mujoco.mj_step(model, data)
            _check_dynamics(data, (step + 1) * dt, step)
            if not np.isfinite(measured[step]).all():
                raise RuntimeError(f"Nonfinite measurement at step {step}")
            if viewer is not None:
                viewer.update(data)
    return CollectionData(time, measured[:, :12], desired[:, :12], measured[:, 12:], desired[:, 12:])


def _check_dynamics(data: Any, expected_time: float, step: int) -> None:
    mj: Any = importlib.import_module("mujoco")
    warnings = [
        mj.mjtWarning.mjWARN_BADQPOS,
        mj.mjtWarning.mjWARN_BADQVEL,
        mj.mjtWarning.mjWARN_BADQACC,
        mj.mjtWarning.mjWARN_BADCTRL,
        mj.mjtWarning.mjWARN_INERTIA,
    ]
    if any(data.warning[int(w)].number for w in warnings):
        raise RuntimeError(f"Invalid dynamics warning at step {step}")
    if not math.isfinite(data.time) or not math.isclose(data.time, expected_time, rel_tol=1e-10, abs_tol=1e-12):
        raise RuntimeError(f"Simulation time reset or diverged at step {step}")
    if any(not np.isfinite(a).all() for a in (data.qpos, data.qvel, data.qacc, data.sensordata, data.actuator_force)):
        raise RuntimeError(f"Nonfinite dynamics or sensors at step {step}")


def _validate_data(data: CollectionData) -> None:
    if data.time.ndim != 1 or len(data.time) < 1 or not np.isfinite(data.time).all():
        raise ValueError("time must be a nonempty finite vector")
    if data.time[0] != 0 or np.any(np.diff(data.time) <= 0):
        raise ValueError("time must start at zero and increase")
    for name, width in [("dof_pos", 12), ("des_dof_pos", 12), ("dof_vel", 4), ("des_dof_vel", 4)]:
        values = getattr(data, name)
        if values.shape != (len(data.time), width) or not np.isfinite(values).all():
            raise ValueError(f"{name} requires finite shape {(len(data.time), width)}")
        if np.any(np.abs(values) > np.finfo(np.float32).max):
            raise ValueError(f"{name} exceeds saved float32 range")


def save_data(data: CollectionData, path: Path) -> None:
    """Atomically replace the output only after serializing a complete CPU dataset."""
    import os
    import tempfile

    import torch

    _validate_data(data)
    fields = ("time", "dof_pos", "des_dof_pos", "dof_vel", "des_dof_vel")
    tensors = {
        name: torch.tensor(getattr(data, name), dtype=torch.float64 if name == "time" else torch.float32, device="cpu")
        for name in fields
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            torch.save(tensors, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def plot_data(data: CollectionData, position_names: Sequence[str], velocity_names: Sequence[str]) -> None:
    """Display position and velocity separately, without resampling measurements."""
    _validate_data(data)
    if len(position_names) != 12 or len(velocity_names) != 4:
        raise ValueError("Plot names must match the 12 position and 4 velocity channels")
    import matplotlib.pyplot as plt

    for names, measured, desired, rows, columns, unit in (
        (position_names, data.dof_pos, data.des_dof_pos, 4, 3, "rad"),
        (velocity_names, data.dof_vel, data.des_dof_vel, 2, 2, "rad/s"),
    ):
        figure, axes = plt.subplots(rows, columns, figsize=(4 * columns, 2.5 * rows), squeeze=False)
        for index, axis in enumerate(axes.flat):
            axis.plot(data.time, measured[:, index], label="Measured")
            axis.plot(data.time, desired[:, index], "--", label="Desired (before delay)")
            axis.set_title(names[index])
            axis.set_xlabel("Time [s]")
            axis.set_ylabel(f"Joint [{unit}]")
            axis.grid(True)
            axis.legend()
        figure.tight_layout()
    plt.show()
