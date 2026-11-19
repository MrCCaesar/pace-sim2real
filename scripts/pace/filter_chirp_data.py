# SPDX-License-Identifier: Apache-2.0
"""Filter recorded PACE measurements along the time axis on CPU."""

import argparse
import math
import os
import pickle
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from scipy import linalg, signal
from scipy.signal.windows import hann


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


@dataclass
class _Metric:
    value: float | None
    joints: int
    detail: str = ""

    def display(self, unit, total):
        if self.value is None:
            number = f"N/A {unit}"
        elif self.value == math.inf:
            number = f"+∞ {unit}"
        else:
            number = f"{self.value:.8g} {unit}"
        coverage = f"{self.joints}/{total} joints"
        if self.detail:
            coverage += f", {self.detail}"
        return f"{number} ({coverage})"


def _spectrum(values, window):
    return np.fft.rfft((values - values.mean(axis=0)) * window[:, None], axis=0)


def _spectral_max(values, mask, frequencies, missing):
    rows, columns = np.nonzero(mask)
    if not len(rows):
        return _Metric(None, 0, f"0 joint-frequency pairs, {missing}")
    detail = f"{len(rows)} joint-frequency pairs, {frequencies[rows[0]]:g}–{frequencies[rows[-1]]:g} Hz"
    return _Metric(float(values.max()), np.unique(columns).size, detail)


def _high_frequency_drop(raw_mag, filtered_mag, frequencies, floor):
    high = frequencies >= 30
    if not high.any():
        return _Metric(None, 0, "no bins at or above 30 Hz")
    # Norms give the square roots of the two band energies (CR5 FFT-bin weights).
    before = np.hypot.reduce(raw_mag[high], axis=0)
    after = np.hypot.reduce(filtered_mag[high], axis=0)
    threshold = floor * np.sqrt(high.sum())
    reference = before > threshold
    weak = reference & (after > 0) & (after <= threshold)
    valid = reference & ~weak
    reasons = []
    if not reference.all():
        reasons.append(f"{(~reference).sum()} raw bands below resolution")
    if weak.any():
        reasons.append(f"{weak.sum()} filtered bands below resolution")
    # A resolved input with strictly zero output gives +infinity.
    with np.errstate(divide="ignore"):
        drops = 20 * (np.log10(before[valid]) - np.log10(after[valid]))
    return _Metric(float(drops.min()) if drops.size else None, int(valid.sum()), ", ".join(reasons))


def _group_diagnostics(raw, filtered, target, fs, band):
    """Compute metrics on float64 views of the original and persisted-precision measurements."""
    count, joints = raw.shape
    window = hann(count, sym=False)
    freq = np.fft.rfftfreq(count, 1 / fs)
    raw_fft = _spectrum(raw, window)
    filtered_fft = _spectrum(filtered, window)
    raw_mag, filtered_mag = abs(raw_fft), abs(filtered_fft)
    target_mag = abs(_spectrum(target, window))
    roundoff = 64 * np.finfo(np.float64).eps
    raw_floor = roundoff * np.max(abs(raw), axis=0)
    spectral_floor = raw_floor * window.sum()
    target_floor = roundoff * window.sum() * np.max(abs(target), axis=0)

    raw_range = np.ptp(raw, axis=0)
    valid = raw_range > raw_floor
    change = abs(np.ptp(filtered, axis=0)[valid] / raw_range[valid] - 1)
    peak = _Metric(
        float(100 * change.max()) if change.size else None,
        int(valid.sum()),
        "" if valid.all() else "unresolved raw peak-to-peak range",
    )
    # Equal sample counts cancel the two RMS normalizers.
    baseline = linalg.norm((raw - target).ravel())
    tracking = (
        _Metric(float(linalg.norm((filtered - target).ravel()) / baseline * 100), joints)
        if baseline
        else _Metric(None, 0, "zero group tracking RMSE before filtering")
    )

    in_band = (freq >= band[0]) & (freq <= band[1]) & (freq > 0)
    active = np.zeros_like(raw_mag, dtype=bool)
    if in_band.any():
        raw_band, target_band = raw_mag[in_band], target_mag[in_band]
        active[in_band] = (
            (raw_band >= 0.1 * raw_band.max(axis=0))
            & (raw_band > spectral_floor)
            & (target_band >= 0.1 * target_band.max(axis=0))
            & (target_band > target_floor)
        )
    gain_change = 100 * abs(filtered_mag[active] / raw_mag[active] - 1)
    missing = "no excited bins" if in_band.any() else "no bins in requested band"
    amplitude = _spectral_max(gain_change, active, freq, missing)

    phase_valid = active & (filtered_mag > np.maximum(spectral_floor, 1e-8 * raw_mag))
    if count % 2 == 0:
        phase_valid[-1] = False
    # Both responses share the same target. Wrap their phase difference before converting to milliseconds.
    phase = np.angle(filtered_fft[phase_valid]) - np.angle(raw_fft[phase_valid])
    phase = np.arctan2(np.sin(phase), np.cos(phase))
    delay_ms = abs(phase) * 1000 / (2 * np.pi * freq[np.nonzero(phase_valid)[0]])
    delay = _spectral_max(delay_ms, phase_valid, freq, "no resolved phase bins" if active.any() else missing)
    attenuation = _high_frequency_drop(raw_mag, filtered_mag, freq, spectral_floor)
    metrics = [
        ("Max peak-to-peak change", "%", peak),
        ("Max delay change", "ms", delay),
        ("Tracking RMSE ratio", "%", tracking),
        ("Max in-band amplitude change", "%", amplitude),
        ("Min energy drop >=30 Hz", "dB", attenuation),
    ]
    # Convert the raw magnitude to a one-sided amplitude spectrum after computing the metrics.
    raw_mag /= window.sum()
    raw_mag[1 : (count + 1) // 2] *= 2
    return metrics, freq, raw_mag


def _plot_group(time, raw, filtered, target, freq, amplitude, group, unit):
    import matplotlib.pyplot as plt

    for col in range(raw.shape[1]):
        fig, (series, spectrum) = plt.subplots(2, 1, layout="constrained")
        fig.suptitle(f"{group} · column {col + 1}")
        series.plot(time, target[:, col], label="Target")
        series.plot(time, raw[:, col], label="Raw")
        series.plot(time, filtered[:, col], label="Filtered")
        series.set(xlabel="Time (s)", ylabel=f"{group} ({unit})")
        series.legend()
        spectrum.plot(freq, amplitude[:, col])
        spectrum.set(xlabel="Frequency (Hz)", ylabel=f"Raw amplitude ({unit})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Input PACE .pt recording")
    parser.add_argument("--output", type=Path, help="New output file (default: INPUT stem + _filtered.pt)")
    parser.add_argument("--cutoff_hz", type=float, default=20.0, help="Single-pass cutoff in Hz (default: 20)")
    parser.add_argument("--order", type=int, default=4, help="Single-pass Butterworth order (default: 4)")
    parser.add_argument(
        "--analysis_band_hz",
        type=float,
        nargs=2,
        metavar=("LOW", "HIGH"),
        default=(0.1, 10.0),
        help="Inclusive diagnostic frequency band in Hz (default: 0.1 10)",
    )
    parser.add_argument("--plot", action="store_true", help="Show per-joint time traces and raw amplitude spectra")
    args = parser.parse_args(argv)
    low, high = args.analysis_band_hz
    if not (0 < low <= high and math.isfinite(high)):
        parser.error("analysis_band_hz requires finite frequencies with 0 < LOW <= HIGH")
    output = args.output or args.input.with_name(args.input.stem + "_filtered.pt")
    try:
        if os.path.lexists(output):
            raise FileExistsError(f"Output already exists: {output}")
        data = torch.load(args.input, map_location="cpu", weights_only=True)
        result = _filter_record(data, args.order, args.cutoff_hz)
        _save_new(output, result)
    except (OSError, ValueError, RuntimeError, EOFError, pickle.UnpicklingError) as exc:
        parser.exit(1, f"{parser.prog}: {exc}\n")
    print(output)
    print(f"Analysis band: {low:g}–{high:g} Hz")
    fs = _sample_rate(data["time"])
    plots = []
    for key, group, unit in (("dof_pos", "Position", "rad"), ("dof_vel", "Velocity", "rad/s")):
        if key not in data or not data[key].shape[1]:
            continue
        raw, filtered, target = (x.detach().double().numpy() for x in (data[key], result[key], data["des_" + key]))
        metrics, freq, amplitude = _group_diagnostics(raw, filtered, target, fs, (low, high))
        print(f"{group} ({key}):")
        for label, metric_unit, metric in metrics:
            print(f"  {label}: {metric.display(metric_unit, raw.shape[1])}")
        if args.plot:
            plots.append((raw, filtered, target, freq, amplitude, group, unit))
    if args.plot:
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.registry import BackendFilter, backend_registry

            for plot in plots:
                _plot_group(data["time"].detach().double().numpy(), *plot)
            plt.show()
            if plt.get_backend().lower() in backend_registry.list_builtin(BackendFilter.NON_INTERACTIVE):
                print(
                    f"Backend {plt.get_backend()} cannot open a window. Filtered recording saved to {output}",
                    file=sys.stderr,
                )
        except Exception as exc:
            parser.exit(1, f"Plot failed: {exc}. Filtered recording saved to {output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
