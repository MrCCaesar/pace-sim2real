"""Task configuration and fixed-period selection for offline PACE recordings."""

import math
from collections.abc import Sequence
from typing import Any, cast

import torch

_ABS_TOL = 1e-4
_REL_TOL = 1e-5


def load_recording_task(task: str) -> Any:
    from isaaclab.cli import load_external_tasks

    from isaaclab_tasks.utils.parse_cfg import load_cfg_from_registry

    load_external_tasks()
    cfg = cast(Any, load_cfg_from_registry(task, "env_cfg_entry_point"))
    if not (hasattr(cfg, "sim2real") and hasattr(cfg, "sim") and hasattr(cfg, "decimation")):
        raise ValueError(f"{task} does not provide a PACE environment configuration")
    return cfg


def resolve_sample_period(time: torch.Tensor, task_dt: float, csv_lines: Sequence[int] | None = None) -> float:
    """Select a fixed period in seconds, preferring the registered task's control period."""
    if time.ndim != 1 or len(time) < 2 or not time.is_floating_point():
        raise ValueError("time must be a floating-point vector of at least two timestamps in seconds")
    time = time.double()
    if not torch.isfinite(time).all() or not (time.diff() > 0).all():
        raise ValueError("time must be finite and strictly increasing")

    def location(i: int) -> str:
        return f"CSV line {csv_lines[i]}" if csv_lines is not None else f"time[{i}]"

    if not math.isfinite(task_dt) or task_dt <= 0:
        raise ValueError("Invalid task control period")
    elapsed = time - time[0]
    steps = torch.arange(len(time), dtype=torch.float64)

    def matches(dt):
        return torch.isclose(elapsed, steps * dt, atol=_ABS_TOL, rtol=_REL_TOL)

    if matches(task_dt).all():
        return task_dt
    low, high = 0.0, math.inf
    for i, t in enumerate(elapsed.tolist()[1:], 1):
        prior = (
            i * low * (1 - _REL_TOL) - _ABS_TOL,
            i * high * (1 + _REL_TOL) + _ABS_TOL,
        )
        low = max(low, (t - _ABS_TOL) / (i * (1 + _REL_TOL)))
        high = min(high, (t + _ABS_TOL) / (i * (1 - _REL_TOL)))
        if low > high or not math.isfinite(t):
            raise ValueError(f"{location(i)}: elapsed time {t} s outside fixed grid {prior} s")
    period = min(max(elapsed[-1].item() / (len(time) - 1), low), high)
    for dt in (period, math.nextafter(period, (low + high) / 2), (low + high) / 2):
        valid = matches(dt)
        if valid.all():
            return dt
    i = int((~valid).nonzero()[0].item())
    raise ValueError(f"{location(i)}: elapsed time {elapsed[i].item()} s exceeds grid at {i * dt} s")
