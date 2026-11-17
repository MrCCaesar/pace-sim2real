# SPDX-License-Identifier: Apache-2.0

"""Behavior tests for the standalone native MuJoCo collector."""

import importlib
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "pace"))
from mujoco_collection import collect, load_config, save_data  # noqa: E402


def test_load_default_config_without_isaaclab():
    cfg = load_config(ROOT / "config" / "x5_collection.toml")
    assert cfg.duration == 20.0
    assert (cfg.min_frequency, cfg.max_frequency, cfg.seed, cfg.plot) == (0.1, 10.0, 42, False)
    assert cfg.position_joints[:3] == ("FL_hip_joint", "FL_thigh_joint", "FL_calf_joint")
    assert cfg.velocity_joints[-1] == "RR_foot_joint"
    np.testing.assert_array_equal(cfg.position_centers[:3], [0, 0.4, -1.4])
    assert cfg.model_path.name == "x5_calibration.xml"
    assert "isaaclab" not in sys.modules


@pytest.fixture
def native_config(tmp_path):
    cfg = load_config(ROOT / "config" / "x5_collection.toml")
    names = cfg.position_joints + cfg.velocity_joints
    bodies = "".join(
        f'<body pos="{i} 0 0"><joint name="{n}"/><geom type="sphere" size="0.1" mass="1" '
        'contype="0" conaffinity="0"/></body>'
        for i, n in enumerate(reversed(names))
    )
    actuators = "".join(
        (
            f'<position joint="{n}" kp="10" kv="1" delay="0.01" nsample="4" forcerange="-1 1"/>'
            if n in cfg.position_joints
            else f'<velocity joint="{n}" kv="1" delay="0.01" nsample="4" forcerange="-1 1"/>'
        )
        for n in reversed(names)
    )
    sensors = "".join(
        f'<jointpos joint="{n}"/>' if n in cfg.position_joints else f'<jointvel joint="{n}"/>' for n in reversed(names)
    )
    path = tmp_path / "model.xml"
    path.write_text(
        '<mujoco><option timestep="0.0025" gravity="0 0 0" integrator="implicitfast"/>'
        f"<worldbody>{bodies}</worldbody><actuator>{actuators}</actuator>"
        f"<sensor>{sensors}</sensor></mujoco>"
    )
    return replace(cfg, model_path=path, min_frequency=1.0, max_frequency=1.0, duration=0.02)


def test_collect_preserves_sensor_time_and_native_delay_despite_reordered_model(native_config):
    data = collect(native_config)
    np.testing.assert_allclose(data.time, [0, 0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.0175])
    np.testing.assert_allclose(data.dof_pos[:6], np.tile(np.array([-0.05, 0.35, -1.45] * 4), (6, 1)))
    assert np.all(data.dof_pos[6] > data.dof_pos[5])
    np.testing.assert_array_equal(data.dof_vel[:6], 0)
    assert np.all(data.dof_vel[6] > 0)
    np.testing.assert_allclose(data.des_dof_pos[0], [0, 0.4, -1.4] * 4)
    assert data.des_dof_pos[1, 0] == pytest.approx(0.003926829327955169)
    assert data.des_dof_vel[1, 0] == pytest.approx(0.15707317311820676)


def test_save_roundtrip_replaces_old_file(native_config, tmp_path):
    import torch

    data = collect(native_config)
    path = tmp_path / "dataset.pt"
    path.write_bytes(b"old data")
    save_data(data, path)
    saved = torch.load(path, weights_only=True)
    assert set(saved) == {"time", "dof_pos", "des_dof_pos", "dof_vel", "des_dof_vel"}
    for name, tensor in saved.items():
        expected = getattr(data, name)
        assert tensor.shape == expected.shape
        assert tensor.device.type == "cpu"
        assert tensor.dtype == (torch.float64 if name == "time" else torch.float32)
        np.testing.assert_allclose(tensor.numpy(), expected, atol=1e-7)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["dataset.pt", "model.xml"]


def test_linear_chirp_has_expected_phase_at_quarter_and_half_second(native_config):
    data = collect(replace(native_config, duration=1.0, max_frequency=3.0))
    assert data.des_dof_pos[100, 0] == pytest.approx(0.23096988312782168)
    assert data.des_dof_pos[200, 0] == pytest.approx(-0.25)
    assert data.des_dof_vel[200, 0] == pytest.approx(-10.0)


def test_noise_is_seeded_xml_scaled_and_does_not_change_physics(native_config):
    clean = collect(native_config)
    xml = native_config.model_path.read_text()
    native_config.model_path.write_text(
        xml.replace("<jointpos ", '<jointpos noise="0.01" ').replace("<jointvel ", '<jointvel noise="0.1" ')
    )
    noisy = collect(native_config)
    again = collect(native_config)
    np.testing.assert_array_equal(noisy.dof_pos, again.dof_pos)
    np.testing.assert_array_equal(noisy.dof_vel, again.dof_vel)
    assert not np.array_equal(noisy.dof_pos[:, 0] - clean.dof_pos[:, 0], noisy.dof_pos[:, 1] - clean.dof_pos[:, 1])
    native_config.model_path.write_text(
        native_config.model_path.read_text()
        .replace('noise="0.01"', 'noise="0.02"')
        .replace('noise="0.1"', 'noise="0.2"')
    )
    doubled = collect(native_config)
    np.testing.assert_allclose(doubled.dof_pos - clean.dof_pos, 2 * (noisy.dof_pos - clean.dof_pos), atol=1e-15)
    np.testing.assert_allclose(doubled.dof_vel - clean.dof_vel, 2 * (noisy.dof_vel - clean.dof_vel), atol=1e-15)
    np.testing.assert_array_equal(doubled.des_dof_pos, clean.des_dof_pos)
    shifted = collect(replace(native_config, encoder_bias=tuple([0.15] * 12)))
    np.testing.assert_allclose(shifted.dof_pos, doubled.dof_pos - 0.1, atol=1e-15)
    np.testing.assert_array_equal(shifted.dof_vel, doubled.dof_vel)


def test_native_effort_limit_bounds_wheel_acceleration(native_config):
    data = collect(replace(native_config, velocity_amplitudes=(1000.0,) * 4))
    # Solid sphere inertia: 2/5 * 1 kg * (0.1 m)^2 = .004 kg m².
    # Native force limit 1 Nm bounds each 2.5 ms velocity increment by .625 rad/s.
    delta = np.diff(data.dof_vel[:, 0])
    assert delta.max() <= 0.625 + 1e-12
    assert delta.max() > 0.3
    assert data.des_dof_vel[1, 0] > 15


@pytest.mark.skipif(
    not (ROOT / "src/pace_sim2real/assets/data/robots/sevnce/x5/mjcf/x5_calibration.xml").is_file(),
    reason="User-owned X5 model resources are not installed",
)
def test_cli_saves_short_run_from_foreign_cwd_without_isaaclab_or_plotting(tmp_path):
    import os
    import subprocess

    import torch

    output_root = tmp_path / "output"
    env = dict(os.environ, PACE_ROOT=str(output_root))
    command = [sys.executable, str(ROOT / "scripts/pace/data_collection_mujoco.py"), "--duration", "0.01"]
    completed = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    data = torch.load(output_root / "data/x5_sim/chirp_data.pt", weights_only=True)
    assert data["dof_pos"].shape == (4, 12)
    assert data["dof_vel"].shape == (4, 4)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('<jointpos joint="RR_calf_joint"/>', '<jointpos joint="RR_calf_joint" delay="0.0025" nsample="1"/>', "sensor"),
        ('<position joint="RR_calf_joint"', '<position gear="2" joint="RR_calf_joint"', "actuator"),
        ('nsample="4"', 'nsample="3"', "history"),
        ('<joint name="RR_calf_joint"/>', '<joint name="RR_calf_joint" type="slide"/>', "hinge"),
        (
            '<jointpos joint="RR_calf_joint"/>',
            '<jointpos joint="RR_calf_joint"/><jointpos joint="RR_calf_joint"/>',
            "sensor",
        ),
    ],
)
def test_unsupported_model_is_rejected_before_collecting(native_config, old, new, message):
    native_config.model_path.write_text(native_config.model_path.read_text().replace(old, new))
    with pytest.raises(ValueError, match=message):
        collect(native_config)


@pytest.mark.parametrize("fault", ["nan", "reset", "warning"])
def test_dynamics_failure_on_final_step_is_not_returned(native_config, monkeypatch, fault):
    mujoco: Any = importlib.import_module("mujoco")

    real_step = mujoco.mj_step

    def broken_step(model, state):
        real_step(model, state)
        if state.time >= 0.02 - 1e-12:
            if fault == "nan":
                state.qacc[0] = np.nan
            elif fault == "reset":
                state.time = 0
            else:
                state.warning[mujoco.mjtWarning.mjWARN_BADQACC].number += 1

    monkeypatch.setattr(mujoco, "mj_step", broken_step)
    with pytest.raises(RuntimeError):
        collect(native_config)


@pytest.mark.parametrize("fault", ["shape", "nan", "overflow"])
def test_bad_dataset_cannot_replace_old_output(native_config, tmp_path, fault):
    data = collect(native_config)
    if fault == "shape":
        data = replace(data, dof_vel=np.zeros((8, 3)))
    else:
        data.dof_pos[0, 0] = np.nan if fault == "nan" else 1e100
    path = tmp_path / "dataset.pt"
    path.write_bytes(b"old")
    with pytest.raises(ValueError):
        save_data(data, path)
    assert path.read_bytes() == b"old"


@pytest.mark.parametrize("fault", ["serialization", "replace", "interrupt"])
def test_save_failure_keeps_old_file_and_cleans_temporary(native_config, tmp_path, monkeypatch, fault):
    import os

    import torch

    data = collect(native_config)
    path = tmp_path / "dataset.pt"
    path.write_bytes(b"old")

    def fail(*args, **kwargs):
        if fault == "interrupt":
            raise KeyboardInterrupt
        raise OSError("injected storage failure")

    monkeypatch.setattr(os if fault == "replace" else torch, "replace" if fault == "replace" else "save", fail)
    with pytest.raises(KeyboardInterrupt if fault == "interrupt" else OSError):
        save_data(data, path)
    assert path.read_bytes() == b"old"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["dataset.pt", "model.xml"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"duration": 0.001}, "integer"),
        ({"duration": float("nan")}, "duration"),
        ({"max_frequency": 200.0}, "Nyquist"),
        ({"min_frequency": 0.0}, "frequency"),
        ({"seed": True}, "seed"),
        ({"plot": 1}, "plot"),
        ({"position_amplitudes": (-1.0,) * 12}, "amplitudes"),
        ({"encoder_bias": (0.0,) * 11}, "encoder_bias"),
        ({"position_joints": ("missing",) * 12}, "unique"),
    ],
)
def test_invalid_run_config_fails(native_config, change, message):
    with pytest.raises(ValueError, match=message):
        collect(replace(native_config, **change))


@pytest.mark.parametrize("mutation", ["unknown", "missing", "type"])
def test_toml_schema_errors_are_actionable(tmp_path, mutation):
    source = (ROOT / "config/x5_collection.toml").read_text()
    if mutation == "unknown":
        source += "\nunknown = 1\n"
    elif mutation == "missing":
        source = source.replace("duration = 20.0\n", "")
    else:
        source = source.replace("seed = 42", 'seed = "42"')
    path = tmp_path / "config.toml"
    path.write_text(source)
    with pytest.raises(ValueError):
        load_config(path)


@pytest.mark.parametrize("fault", ["interrupt", "numerical", "config"])
def test_cli_failure_does_not_touch_existing_data(native_config, tmp_path, monkeypatch, fault):
    mujoco: Any = importlib.import_module("mujoco")
    from data_collection_mujoco import main

    source = (ROOT / "config/x5_collection.toml").read_text()
    source = source.replace(
        "../src/pace_sim2real/assets/data/robots/sevnce/x5/mjcf/x5_calibration.xml", str(native_config.model_path)
    )
    path = tmp_path / "config.toml"
    path.write_text(source)
    output = tmp_path / "data/x5_sim/chirp_data.pt"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"old")
    monkeypatch.setenv("PACE_ROOT", str(tmp_path))

    def failure(model, state):
        if fault == "interrupt":
            raise KeyboardInterrupt
        state.qpos[0] = np.nan

    if fault != "config":
        monkeypatch.setattr(mujoco, "mj_step", failure)
    code = main(["--config", str(path), "--duration", ".001" if fault == "config" else ".01"])
    assert code == (130 if fault == "interrupt" else 1)
    assert output.read_bytes() == b"old"


def test_plot_groups_show_saved_measurements_and_targets(native_config, monkeypatch):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mujoco_collection import plot_data

    data = collect(native_config)
    monkeypatch.setattr(plt, "show", lambda: None)
    before = set(plt.get_fignums())
    try:
        plot_data(data, native_config.position_joints, native_config.velocity_joints)
        figures = [plt.figure(n) for n in plt.get_fignums() if n not in before]
        assert [len(f.axes) for f in figures] == [12, 4]
        for figure, names, measured, desired, unit in [
            (figures[0], native_config.position_joints, data.dof_pos, data.des_dof_pos, "rad"),
            (figures[1], native_config.velocity_joints, data.dof_vel, data.des_dof_vel, "rad/s"),
        ]:
            for index, axis in enumerate(figure.axes):
                assert axis.get_title() == names[index]
                assert unit in axis.get_ylabel()
                assert axis.get_xlabel() == "Time [s]"
                np.testing.assert_array_equal(axis.lines[0].get_xdata(), data.time)
                np.testing.assert_array_equal(axis.lines[0].get_ydata(), measured[:, index])
                np.testing.assert_array_equal(axis.lines[1].get_ydata(), desired[:, index])
    finally:
        for number in set(plt.get_fignums()) - before:
            plt.close(number)


@pytest.mark.skipif(
    not (ROOT / "src/pace_sim2real/assets/data/robots/sevnce/x5/mjcf/x5_calibration.xml").is_file(),
    reason="User-owned X5 model resources are not installed",
)
def test_disabled_plot_does_not_import_matplotlib_or_isaaclab(tmp_path):
    import os
    import subprocess

    program = """
import builtins, sys
real_import = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'matplotlib', 'isaaclab', 'pace_sim2real'}:
        raise AssertionError('Unexpected import: ' + name)
    return real_import(name, *args, **kwargs)
builtins.__import__ = guarded
sys.path.insert(0, sys.argv[1])
from data_collection_mujoco import main
raise SystemExit(main(['--duration', '0.0025']))
"""
    completed = subprocess.run(
        [sys.executable, "-c", program, str(ROOT / "scripts/pace")],
        env=dict(os.environ, PACE_ROOT=str(tmp_path)),
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(
    not (ROOT / "src/pace_sim2real/assets/data/robots/sevnce/x5/mjcf/x5_calibration.xml").is_file(),
    reason="User-owned X5 model resources are not installed",
)
def test_plot_failure_happens_after_save(tmp_path, monkeypatch):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import torch
    from data_collection_mujoco import main

    monkeypatch.setenv("PACE_ROOT", str(tmp_path))

    def fail_show():
        assert (tmp_path / "data/x5_sim/chirp_data.pt").exists()
        raise RuntimeError("injected display failure")

    monkeypatch.setattr(plt, "show", fail_show)
    try:
        assert main(["--duration", ".0025", "--plot"]) == 1
        saved = torch.load(tmp_path / "data/x5_sim/chirp_data.pt", weights_only=True)
        assert saved["dof_pos"].shape == (1, 12)
    finally:
        plt.close("all")


def test_save_remains_cpu_when_torch_default_device_changes(native_config, tmp_path):
    import torch

    data = collect(native_config)
    path = tmp_path / "dataset.pt"
    with torch.device("meta"):
        save_data(data, path)
    loaded = torch.load(path, weights_only=True)
    assert all(tensor.device.type == "cpu" for tensor in loaded.values())
