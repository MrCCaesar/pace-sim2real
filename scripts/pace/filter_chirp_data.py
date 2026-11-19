# SPDX-License-Identifier: Apache-2.0
"""Filter recorded PACE measurements along the time axis on CPU."""

import argparse
import math
import os
import pickle
from pathlib import Path

import torch
from scipy import signal


def _sample_rate(time: torch.Tensor) -> float:
    if time.ndim != 1 or len(time) < 2:
        raise ValueError("time must be a vector of at least two timestamps in seconds")
    time = time.double()
    intervals = time.diff()
    dt = (time[-1] - time[0]).item() / (len(time) - 1)
    if not math.isfinite(dt) or not (intervals > 0).all():
        raise ValueError("time must be strictly increasing")
    if ((intervals - dt).abs() > 1e-7 + 0.001 * dt).any():
        raise ValueError("time must be uniformly sampled")
    return 1 / dt


def _filter_record(data: dict, order: int, cutoff_hz: float) -> dict:
    fields = {"time", "dof_pos", "des_dof_pos", "dof_vel", "des_dof_vel"}
    if not isinstance(data, dict) or "time" not in data or data.keys() - fields:
        raise ValueError("Expected a PACE tensor dictionary with time and paired joint fields")
    for key, value in data.items():
        if not isinstance(value, torch.Tensor) or not value.is_floating_point() or not torch.isfinite(value).all():
            raise ValueError(f"{key} must be a finite floating-point tensor")

    time = data["time"]
    fs = _sample_rate(time)
    if not 0 < cutoff_hz < fs / 2 or not math.isfinite(fs):
        raise ValueError(f"cutoff_hz must be positive and below Nyquist ({fs / 2:g} Hz)")
    if order < 1:
        raise ValueError("order must be a positive integer")
    # For a Butterworth low-pass, SciPy's default SOS padding is 3 * (order + 1).
    if len(time) <= 3 * (order + 1):
        raise ValueError(f"Record too short for order {order}: need more than {3 * (order + 1)} samples")

    measured = []
    for key in ("dof_pos", "dof_vel"):
        target = "des_" + key
        if (key in data) != (target in data):
            raise ValueError(f"Expected both {key} and {target}")
        if key in data:
            values = data[key]
            if values.ndim != 2 or values.shape[0] != len(time) or values.shape != data[target].shape:
                raise ValueError(f"{key} and {target} must have matching [time, joint] shapes")
            if values.shape[1]:
                measured.append(key)
    if not measured:
        raise ValueError("Expected at least one recorded joint")

    sos = signal.butter(order, cutoff_hz, fs=fs, btype="lowpass", output="sos")
    result = data.copy()
    for key in measured:
        values = data[key]
        filtered = signal.sosfiltfilt(sos, values.detach().double().numpy(), axis=0, padtype="odd")
        # The backward pass returns a reversed-stride view, which PyTorch cannot wrap.
        result[key] = torch.from_numpy(filtered.copy()).to(values.dtype)
        if not torch.isfinite(result[key]).all():
            raise ValueError(f"Filtered {key} exceeds its original dtype range")
    return result


def _save_new(path: Path, data: dict) -> None:
    # Open exclusively before the cleanup block, so a competing writer's file can never be removed.
    output = path.open("xb")
    try:
        with output:
            torch.save(data, output)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Input PACE .pt recording")
    parser.add_argument("--output", type=Path, help="New output file (default: INPUT stem + _filtered.pt)")
    parser.add_argument("--cutoff_hz", type=float, default=20.0, help="Single-pass cutoff in Hz (default: 20)")
    parser.add_argument("--order", type=int, default=4, help="Single-pass Butterworth order (default: 4)")
    args = parser.parse_args(argv)
    output = args.output or args.input.with_name(args.input.stem + "_filtered.pt")
    try:
        if os.path.lexists(output):
            raise FileExistsError(f"Output already exists: {output}")
        data = torch.load(args.input, map_location="cpu", weights_only=True)
        _save_new(output, _filter_record(data, args.order, args.cutoff_hz))
    except (OSError, ValueError, RuntimeError, EOFError, pickle.UnpicklingError) as exc:
        parser.exit(1, f"{parser.prog}: {exc}\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
