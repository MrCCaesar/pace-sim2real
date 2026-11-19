# SPDX-License-Identifier: Apache-2.0
"""CPU regressions for the offline filter CLI, including the CR5 research signals."""

import hashlib
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
main = runpy.run_path(str(ROOT / "scripts/pace/filter_chirp_data.py"))["main"]
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
