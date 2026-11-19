# SPDX-License-Identifier: Apache-2.0
"""CPU regressions for the offline filter CLI, including the CR5 research signals."""

import hashlib
import re
import runpy
import tomllib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from scipy import signal
from scipy.signal.windows import hann

ROOT = Path(__file__).resolve().parents[1]
script = runpy.run_path(str(ROOT / "scripts/pace/filter_chirp_data.py"))
main = script["main"]
load_reference_data = runpy.run_path(str(ROOT / "src/pace_sim2real/utils/collection_contracts.py"))[
    "load_reference_data"
]
X5 = ROOT / "data/Isaac-Pace-Sevnce-X5-v0/mujoco_0.1_10Hz_kp1500_kd30_chirp_data.pt"
X5_SHA256 = "8ab1ca9e3a430c0b4ad7fa951cf53dbc352d8e45263b6ee085bc300aa25732d8"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(legs=2, wheels=None):
    # Distinct columns and sample rate exercise axis selection and frequency units.
    time = torch.arange(160, dtype=torch.float64) / 160
    data = {"time": time}
    for key, width, dtype in (("dof_pos", legs, torch.float64), ("dof_vel", wheels, torch.float32)):
        if width is not None:
            phase = 2 * torch.pi * time[:, None] * torch.arange(1, width + 1)
            data[key] = (phase.sin() + (33 * phase).cos()).to(dtype)
            data["des_" + key] = phase.sin().to(dtype)
    return data


def assert_contract(original, path, cfg, dt):
    filtered = torch.load(path, map_location="cpu", weights_only=True)
    assert list(filtered) == list(original)
    loaded = load_reference_data(path, cfg, dt)
    for key, value in filtered.items():
        assert value.shape == original[key].shape and value.dtype == original[key].dtype
        if key not in ("dof_pos", "dof_vel"):
            assert torch.equal(value, original[key])
        assert torch.equal(loaded[key], value.to(loaded[key].dtype))
    return filtered


@pytest.mark.parametrize(
    "legs,wheels,order,cutoff", [(2, None, 4, 20), (None, 1, 4, 25), (2, 3, 3, 17), (0, 2, 2, 20), (1, 0, 1, 20)]
)
def test_cli_preserves_contract_and_filters_columns_independently(tmp_path, legs, wheels, order, cutoff):
    path = tmp_path / "input.pt"
    data = record(legs, wheels)
    torch.save(data, path)
    before = digest(path)
    assert main([str(path), "--order", str(order), "--cutoff_hz", str(cutoff)]) == 0
    cfg = SimpleNamespace(
        leg_order=[f"L{i}" for i in range(legs or 0)], wheel_order=[f"W{i}" for i in range(wheels or 0)]
    )
    output = assert_contract(data, tmp_path / "input_filtered.pt", cfg, 1 / 160)
    sos = signal.butter(order, cutoff, fs=160, output="sos")
    for key in ("dof_pos", "dof_vel"):
        if key in data:
            for col, values in enumerate(data[key].T):
                expected = signal.sosfiltfilt(sos, values.double().numpy()).copy()
                torch.testing.assert_close(output[key][:, col], torch.from_numpy(expected).to(values.dtype))
    assert before == digest(path)


@pytest.mark.parametrize(
    "change,args,error",
    [
        ({}, ["--order", "0"], "order"),
        ({}, ["--cutoff_hz", "80"], "Nyquist"),
        ({}, ["--cutoff_hz", "nan"], "Nyquist"),
        ({"extra": torch.zeros(1)}, [], "dictionary"),
        ({"des_dof_vel": torch.zeros(160, 1)}, [], "both"),
        ({"des_dof_pos": torch.zeros(160)}, [], "shapes"),
        ({"dof_pos": torch.ones(160, 2, dtype=torch.int32)}, [], "floating"),
        ({"des_dof_pos": torch.full((160, 2), torch.inf)}, [], "finite"),
        ({"dof_pos": torch.empty(160, 0), "des_dof_pos": torch.empty(160, 0)}, [], "one recorded"),
        ({"time": torch.zeros(160)}, [], "strictly increasing"),
        ({"time": torch.arange(160).double().square() / 1e4}, [], "uniformly"),
        ({"time": torch.arange(15).double() / 160}, [], "too short"),
    ],
)
def test_invalid_record_or_design_leaves_no_output(tmp_path, capsys, change, args, error):
    path = tmp_path / "input.pt"
    torch.save(record() | change, path)
    with pytest.raises(SystemExit) as exc:
        main([str(path), *args])
    assert exc.value.code != 0 and error in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("alias", ["existing", "input", "symlink", "hardlink"])
def test_existing_outputs_are_preserved(tmp_path, alias):
    source, output = tmp_path / "record.pt", tmp_path / "out.pt"
    torch.save(record(), source)
    if alias == "input":
        output = source
    elif alias == "symlink":
        output.symlink_to(source)
    elif alias == "hardlink":
        output.hardlink_to(source)
    else:
        output.write_bytes(b"existing")
    before = digest(source), digest(output)
    with pytest.raises(SystemExit):
        main([str(source), "--output", str(output)])
    assert (digest(source), digest(output)) == before


def test_interrupted_save_removes_partial_file(tmp_path, monkeypatch):
    path = tmp_path / "record.pt"
    torch.save(record(), path)
    before = digest(path)

    def fail(data, stream):
        stream.write(b"partial")
        raise OSError("simulated write failure")

    monkeypatch.setattr(torch, "save", fail)
    with pytest.raises(SystemExit):
        main([str(path)])
    assert list(tmp_path.iterdir()) == [path] and digest(path) == before


def test_synthetic_passband_delay_and_rmse(tmp_path):
    fs = 400
    time = np.arange(32000) / fs
    frequencies = np.array([0.1, 1.0, 4.0, 8.0, 10.0])
    command = np.sin(2 * np.pi * time[:, None] * frequencies)
    clean = np.sin(2 * np.pi * (time[:, None] - 0.01) * frequencies)
    rng = np.random.default_rng(42)
    noisy = (
        clean + 0.12 * rng.standard_normal(clean.shape) + 0.15 * np.sin(2 * np.pi * 70 * time[:, None] + np.arange(5))
    )
    source = tmp_path / "tones.pt"
    # Process the clean and noisy copies independently in a single CLI invocation.
    torch.save(
        {
            "time": torch.from_numpy(time),
            "dof_pos": torch.from_numpy(noisy),
            "des_dof_pos": torch.from_numpy(command),
            "dof_vel": torch.from_numpy(clean),
            "des_dof_vel": torch.from_numpy(command),
        },
        source,
    )
    assert main([str(source)]) == 0
    output = torch.load(tmp_path / "tones_filtered.pt", weights_only=True)
    filtered = output["dof_pos"].numpy()
    middle = slice(4000, -4000)
    ends = np.r_[0:100, len(time) - 100 : len(time)]
    basis = np.exp(-2j * np.pi * time[middle, None] * frequencies)

    def phasor(x):
        return np.mean(x[middle] * basis, axis=0)

    gain = abs(phasor(output["dof_vel"].numpy()) / phasor(clean))
    delta_ms = np.angle(phasor(filtered) / phasor(noisy)) * 1000 / (2 * np.pi * frequencies)
    assert np.all(abs(gain - 1) <= 0.01)
    assert np.all(abs(delta_ms) <= 0.1)
    for window in (middle, ends):
        before = np.sqrt(np.mean((noisy[window] - clean[window]) ** 2))
        after = np.sqrt(np.mean((filtered[window] - clean[window]) ** 2))
        assert after <= 0.35 * before


@pytest.mark.skipif(not X5.is_file(), reason="CR5 real X5 recording is not available")
def test_real_x5_file(tmp_path):
    assert digest(X5) == X5_SHA256, "CR5-A3 requires the original research capture"
    original = torch.load(X5, map_location="cpu", weights_only=True)
    path = tmp_path / "x5_filtered.pt"
    assert main([str(X5), "--output", str(path)]) == 0
    channels = tomllib.loads((ROOT / "config/x5_collection.toml").read_text())["channels"]
    cfg = SimpleNamespace(leg_order=channels["position_joints"], wheel_order=channels["velocity_joints"])
    output = assert_contract(original, path, cfg, 0.0025)
    assert digest(X5) == X5_SHA256

    count = len(original["time"])
    window = hann(count, sym=False)[:, None]
    f = np.fft.rfftfreq(count, 0.0025)
    band = (f >= 0.1) & (f <= 10)
    high = f >= 30

    def spectrum(values):
        x = values.double().numpy()
        return abs(np.fft.rfft((x - x.mean(axis=0)) * window, axis=0))

    for key, unit in (("dof_pos", "rad"), ("dof_vel", "rad/s")):
        raw, filtered = spectrum(original[key]), spectrum(output[key])
        target = spectrum(original["des_" + key])
        active = band[:, None] & (target >= 0.1 * target[band].max(axis=0)) & (raw >= 0.1 * raw[band].max(axis=0))
        assert active.any(axis=0).all()
        gain_change = np.max(abs(filtered[active] / raw[active] - 1))
        attenuation = 10 * np.log10((raw[high] ** 2).sum(axis=0) / (filtered[high] ** 2).sum(axis=0))
        assert gain_change <= 0.01
        assert np.all(attenuation >= 40)
        first, last = (output[key][[0, -1]] - original[key][[0, -1]]).abs().amax(dim=1)
        print(
            f"{key}: max gain change {gain_change:.3%}, min attenuation {attenuation.min():.2f} dB,"
            f" first/last max change {first:.5f}/{last:.5f} {unit}"
        )


def metrics(raw, filtered, target, fs=256, band=(8, 8)):
    columns = [np.asarray(x, dtype=float).reshape(len(raw), -1) for x in (raw, filtered, target)]
    rows, _, _ = script["_group_diagnostics"](*columns, fs, band)
    return [metric for _, _, metric in rows]


def test_group_metrics_with_known_gain_tracking_and_wrapped_phase():
    phase = 2 * np.pi * 8 * np.arange(256) / 256
    tone = np.sin(phase)
    raw = np.column_stack((tone, 2 * tone))
    filtered = np.column_stack((0.5 * tone, 1.5 * tone))
    peak, delay, tracking, amplitude, high = metrics(raw, filtered, raw * 2)
    assert [m.value for m in (peak, delay, tracking, amplitude)] == pytest.approx([50, 0, 100 * np.sqrt(8.5 / 5), 50])
    assert all(m.joints == 2 for m in (peak, delay, tracking, amplitude))
    assert high.value is None
    _, delay, *_ = metrics(np.sin(phase + np.deg2rad(179)), np.sin(phase - np.deg2rad(179)), tone)
    assert delay.value == pytest.approx(1000 * 2 / (360 * 8))


def test_resolution_and_undefined_metrics():
    tone = np.sin(2 * np.pi * 8 * np.arange(256) / 256)
    zero = np.zeros_like(tone)
    peak, delay, tracking, amplitude, high = metrics(tone, zero, tone)
    assert peak.value == amplitude.value == pytest.approx(100)
    assert delay.value is tracking.value is high.value is None
    assert metrics(tone, tone * 1e-12, tone)[1].value is None
    assert all(m.value is None for m in metrics(zero, zero, zero))
    mixed = np.column_stack((tone, zero))
    assert metrics(mixed, mixed, mixed)[3].joints == 1
    assert metrics(tone, tone, zero)[3].value is None
    assert metrics(tone, tone, tone, band=(0.1, 0.2))[3].value is None
    alternating = (-1.0) ** np.arange(256)
    assert metrics(alternating, alternating, alternating, fs=50)[4].value is None
    for scale, expected in ((0.5, 20 * np.log10(2)), (2, -20 * np.log10(2)), (0, np.inf), (1e-18, None)):
        _, delay, _, _, high = metrics(alternating, scale * alternating, alternating, fs=60, band=(30, 30))
        assert delay.value is None
        if expected is None:
            assert high.value is None and "below resolution" in high.detail
        else:
            assert high.value == pytest.approx(expected)


@pytest.mark.parametrize("limits", [[], ["4"], ["5", "4"], ["0", "4"], ["nan", "4"], ["4", "inf"]])
def test_invalid_analysis_band_protects_files(tmp_path, limits):
    path = tmp_path / "record.pt"
    torch.save(record(), path)
    with pytest.raises(SystemExit) as exc:
        main([str(path), "--analysis_band_hz", *limits])
    assert exc.value.code and list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("legs,wheels", [(2, None), (None, 1), (1, 2), (0, 2), (1, 0)])
def test_band_changes_only_spectral_selection(tmp_path, capsys, legs, wheels):
    path = tmp_path / "record.pt"
    torch.save(record(legs, wheels), path)
    reports, saved = [], []
    for hz in [("0.1", "10"), ("1000", "2000")]:
        out = tmp_path / f"band-{hz[0]}.pt"
        assert main([str(path), "--output", str(out), "--analysis_band_hz", *hz]) == 0
        report = capsys.readouterr().out
        assert report.splitlines()[0] == str(out)
        assert ("Position (dof_pos)" in report) == bool(legs)
        assert ("Velocity (dof_vel)" in report) == bool(wheels)
        reports.append(report)
        saved.append(torch.load(out, weights_only=True))
    assert all(torch.equal(saved[0][key], saved[1][key]) for key in saved[0])
    assert "no bins in requested band" in reports[1]
    for label in ("Max peak-to-peak change", "Tracking RMSE ratio", "Min energy drop"):
        assert [line for line in reports[0].splitlines() if label in line] == [
            line for line in reports[1].splitlines() if label in line
        ]


@pytest.mark.skipif(not X5.is_file(), reason="CR6 real X5 recording is not available")
@pytest.mark.parametrize(
    "hz,expected",
    [
        (20, [[29.0142, 0.000880, 99.3993, 0.15919, 47.659], [17.0088, 0.002802, 99.2187, 0.15130, 47.856]]),
        (25, [[28.0478, 0.000140, 99.4235, 0.02576, 32.803], [15.8793, 0.000453, 99.2696, 0.02448, 32.991]]),
    ],
)
def test_x5_diagnostics_in_cli_report(tmp_path, capsys, hz, expected):
    assert digest(X5) == X5_SHA256
    assert main([str(X5), "--output", str(tmp_path / "out.pt"), "--cutoff_hz", str(hz)]) == 0
    text = capsys.readouterr().out
    assert text.count("1643 joint-frequency pairs, 1.15–8.95 Hz") == 2
    assert text.count("613 joint-frequency pairs, 1.15–8.95 Hz") == 2
    numbers = re.findall(r"^  [^:]+: ([.\deE+\-]+) (?:%|ms|dB) ", text, flags=re.MULTILINE)
    actual = np.asarray(numbers, dtype=float).reshape(2, 5)
    assert np.all(abs(actual - expected) <= [0.001, 0.00001, 0.001, 0.001, 0.01])


@pytest.mark.parametrize("length", [159, 160])
def test_plot_uses_recorded_columns_and_one_sided_raw_spectrum(tmp_path, capsys, monkeypatch, length):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = {key: x[:length] for key, x in record(legs=1, wheels=2).items()}
    path = tmp_path / "raw.pt"
    torch.save(data, path)
    first, second = tmp_path / "off.pt", tmp_path / "on.pt"
    assert main([str(path), "--output", str(first)]) == 0
    plain = capsys.readouterr().out.splitlines()[1:]
    shown = []
    monkeypatch.setattr(plt, "show", lambda: shown.extend(plt.get_fignums()))
    try:
        assert main([str(path), "--output", str(second), "--plot"]) == 0
        assert capsys.readouterr().out.splitlines()[1:] == plain
        filtered = torch.load(second, weights_only=True)
        for key, value in torch.load(first, weights_only=True).items():
            assert torch.equal(filtered[key], value)
        assert len(shown) == 3
        window = hann(length, sym=False)
        for fig_id, (key, col, group, unit) in zip(
            shown,
            [
                ("dof_pos", 0, "Position", "rad"),
                ("dof_vel", 0, "Velocity", "rad/s"),
                ("dof_vel", 1, "Velocity", "rad/s"),
            ],
            strict=True,
        ):
            fig = plt.figure(fig_id)
            assert fig.get_suptitle() == f"{group} · column {col + 1}"
            series, spectrum = fig.axes
            assert [line.get_label() for line in series.lines] == ["Target", "Raw", "Filtered"]
            for line, source in zip(series.lines, [data["des_" + key], data[key], filtered[key]], strict=True):
                np.testing.assert_array_equal(line.get_xdata(), data["time"].numpy())
                np.testing.assert_array_equal(line.get_ydata(), source[:, col].numpy())
            assert series.get_ylabel() == f"{group} ({unit})" and series.get_xlabel() == "Time (s)"
            assert spectrum.get_ylabel() == f"Raw amplitude ({unit})" and spectrum.get_xlabel() == "Frequency (Hz)"
            raw = data[key][:, col].double().numpy()
            # Fold the two-sided DFT explicitly, including the unpaired DC and even-length Nyquist bins.
            two_sided = abs(np.fft.fft((raw - raw.mean()) * window)) / window.sum()
            expected = two_sided[: length // 2 + 1].copy()
            for k in range(1, (length + 1) // 2):
                expected[k] += two_sided[-k]
            (line,) = spectrum.lines
            np.testing.assert_allclose(np.asarray(line.get_xdata()), np.fft.rfftfreq(length, 1 / 160))
            np.testing.assert_allclose(np.asarray(line.get_ydata()), expected, atol=1e-12)
    finally:
        plt.close("all")


def test_display_failure_reports_saved_output(tmp_path, capsys, monkeypatch):
    import matplotlib.pyplot as plt

    def fail():
        raise RuntimeError("display unavailable")

    monkeypatch.setattr(plt, "show", fail)
    path = tmp_path / "input.pt"
    torch.save(record(), path)
    try:
        with pytest.raises(SystemExit) as exc:
            main([str(path), "--plot"])
        output = path.with_stem("input_filtered")
        assert exc.value.code and output.exists()
        error = capsys.readouterr().err
        assert str(output) in error and "display unavailable" in error
    finally:
        plt.close("all")
