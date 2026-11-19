"""Exercise the fitted-parameter file contract independently of simulator startup."""

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def replay_contract(monkeypatch):
    # Load the CPU-only file contract without registering simulation tasks in the pytest process.
    monkeypatch.syspath_prepend(str(ROOT / "src" / "pace_sim2real" / "utils"))
    return importlib.import_module("fit_replay")


def fit_file(tmp_path, backend="NewtonCfg", ratio=None, wheels=("w",)):
    params = {"delay": 2.9, "encoder_bias:b": -0.4, "encoder_bias:a": 0.1}
    for i, name in enumerate(("b", "a", *wheels), 1):
        params.update({f"armature:{name}": i, f"damping:{name}": i + 1, f"friction:{name}": i + 2})
        if ratio is not None:
            params[f"friction_ratio:{name}"] = ratio
    physics = type(backend, (), {"solver_type": 1})()
    cfg = SimpleNamespace(
        decimation=1,
        sim=SimpleNamespace(dt=0.01, physics=physics),
        sim2real=SimpleNamespace(reference_bias_model="feedback_and_measurement", reference_delay_mode="command"),
    )
    record: dict[str, Any] = dict(
        schema_version=2,
        generation=0,
        candidate_index=1,
        time=torch.tensor([0.0, 0.01]),
        sim_dof_pos=torch.zeros(2, 2),
        reference={"dof_pos": torch.zeros(2, 2), "des_dof_pos": torch.zeros(2, 2)},
        delay_candidate=2.9,
        leg_order=["b", "a"],
        wheel_order=list(wheels),
        params=torch.tensor(list(params.values())),
        parameter_names=list(params),
        delay_steps=2,
        delay_seconds=0.02,
        settings=dict(
            dt=0.01,
            backend=backend,
            solver=1,
            reference_delay_mode="command",
            reference_bias_model="feedback_and_measurement",
        ),
    )
    if wheels:
        record["sim_dof_vel"] = torch.zeros(2, len(wheels))
        record["reference"].update(dof_vel=torch.zeros(2, len(wheels)), des_dof_vel=torch.zeros(2, len(wheels)))
    path = tmp_path / "best_result.pt"
    torch.save(record, path)
    return path, cfg, record


def test_replay_reads_named_parameters_in_task_order(tmp_path, replay_contract):
    path, cfg, _ = fit_file(tmp_path)
    params = replay_contract.load_replay_parameters(path, cfg, ("a", "b"), ("w",))
    torch.testing.assert_close(params.armature, torch.tensor([2.0, 1.0, 3.0]))
    torch.testing.assert_close(params.damping, torch.tensor([3.0, 2.0, 4.0]))
    torch.testing.assert_close(params.friction, torch.tensor([4.0, 3.0, 5.0]))
    torch.testing.assert_close(params.bias, torch.tensor([0.1, -0.4, 0.0]))
    assert params.delay_steps == 2


@pytest.mark.parametrize("ratio, expected", [(None, [4.0, 3.0]), (0.25, [1.0, 0.75])])
def test_physx_friction_and_leg_only_replay(tmp_path, ratio, expected, replay_contract):
    path, cfg, _ = fit_file(tmp_path, backend="PhysxCfg", ratio=ratio, wheels=())
    params = replay_contract.load_replay_parameters(path, cfg, ("a", "b"), ())
    torch.testing.assert_close(params.dynamic_friction, torch.tensor(expected))


@pytest.mark.parametrize(
    "change,match",
    [
        ("old_dt", "settings.dt"),
        ("dt", "timestep"),
        ("backend", "backend"),
        ("solver", "solver"),
        ("delay_mode", "delay_mode"),
        ("bias_model", "bias_model"),
        ("leg_order", "leg_order"),
        ("wheel_order", "wheel_order"),
        ("duplicate", "duplicate.*encoder_bias:b"),
        ("negative", "nonnegative.*armature:a"),
        ("delay", "delay"),
        ("partial", "Missing parameters"),
        ("unpaired", "sim_dof_pos"),
        ("invalid_training_response", "sim_dof_pos"),
        ("invalid_clock", "time"),
    ],
)
def test_incompatible_result_identifies_the_problem(tmp_path, change, match, replay_contract):
    path, cfg, record = fit_file(tmp_path)
    if change == "old_dt":
        dt = record["settings"].pop("dt")
        record["settings"].update(physics_dt=dt, control_dt=dt)
    elif change in ("backend", "solver", "dt"):
        record["settings"][change] = 999
    elif change in ("bias_model", "delay_mode"):
        record["settings"]["reference_" + change] = "wrong"
    elif change in ("leg_order", "wheel_order"):
        record[change][0] = "w" if change == "leg_order" else "unknown"
    elif change == "duplicate":
        record["parameter_names"][0] = record["parameter_names"][1]
    elif change == "invalid_training_response":
        record["sim_dof_pos"][0, 0] = torch.nan
    elif change == "invalid_clock":
        record["time"].zero_()
    elif change == "unpaired":
        record.pop("sim_dof_pos")
    elif change == "negative":
        record["params"][record["parameter_names"].index("armature:a")] = -1
    elif change == "delay":
        record["delay_steps"] = 3
    else:
        record["parameter_names"][-1] = "unexpected"
    torch.save(record, path)
    with pytest.raises(ValueError, match=match):
        replay_contract.load_replay_parameters(path, cfg, ("a", "b"), ("w",))


def test_latest_run_is_selected_before_checking_for_the_result(tmp_path, replay_contract):
    old = tmp_path / "26_11_01_12-00-00-000000"
    recent = tmp_path / "26_11_02_12-00-00-000000"
    (tmp_path / "videos").mkdir()
    with pytest.raises(FileNotFoundError, match="No fitting run"):
        replay_contract.latest_fit_result(tmp_path)
    old.mkdir()
    (old / "best_result.pt").touch()
    recent.mkdir()
    with pytest.raises(FileNotFoundError, match=recent.name):
        replay_contract.latest_fit_result(tmp_path)
    result = recent / "best_result.pt"
    result.touch()
    old.touch()
    assert replay_contract.latest_fit_result(tmp_path) == result


def test_prediction_error_uses_measurements_and_physical_units(replay_contract):
    replay = {"dof_pos": torch.tensor([[0.0, 0.0], [0.0, 4.0]]), "dof_vel": torch.tensor([[6.0], [6.0]])}
    reference = {
        "dof_pos": torch.zeros(2, 2),
        "dof_vel": torch.ones(2, 1),
        "des_dof_pos": replay["dof_pos"],
        "des_dof_vel": replay["dof_vel"],
    }
    assert replay_contract.prediction_rmse(replay, reference) == {"dof_pos": 2.0, "dof_vel": 5.0}
    assert replay_contract.prediction_rmse({"dof_pos": replay["dof_pos"]}, reference) == {"dof_pos": 2.0}


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("PACE_RUN_REPLAY_INTEGRATION") != "1", reason="Opt in to the multi-launch X5 replay check"
)
def test_x5_short_fit_replays_its_response_and_checks_an_independent_chirp(tmp_path):
    """Exercise fixed collection, fitting, and both replay entry points in isolated task directories."""
    import psutil

    if not torch.cuda.is_available():
        pytest.skip("X5 Newton integration requires CUDA")
    scripts = ROOT / "scripts" / "pace"
    task = "Isaac-Pace-Sevnce-X5-v0"
    data_path = tmp_path / "data" / task / "chirp_data.pt"
    env = dict(os.environ, PACE_ROOT=str(tmp_path), MPLBACKEND="Agg", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2")

    def run(script, *args):
        if min(psutil.virtual_memory().available, torch.cuda.mem_get_info()[0]) < 4 * 1024**3:
            pytest.skip("Insufficient free RAM or VRAM for bounded X5 replay")
        command = [
            sys.executable,
            str(scripts / script),
            "--task",
            task,
            "--num_envs",
            "2",
            "--visualizer",
            "none",
            *map(str, args),
        ]
        result = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, (result.stdout + result.stderr)[-4500:]
        return result.stdout

    def read(path):
        return torch.load(path, map_location="cpu", weights_only=True)

    run("data_collection.py", "--duration", ".1")
    training_file = tmp_path / "moving.pt"
    training = {k: v[8:].clone() for k, v in read(data_path).items()}
    assert training["dof_vel"][0].abs().max() > 0
    torch.save(training, training_file)
    torch.save(training, data_path)
    run("fit.py", "env.sim2real.cmaes.max_iteration=1")
    (best_file,) = (tmp_path / "logs" / "pace-sim2real" / task).glob("*/best_result.pt")
    before_sweep = data_path.read_bytes()
    run("data_collection.py", "--fit_result", best_file, "--duration", ".025")
    assert data_path.read_bytes() == before_sweep
    replay_file = tmp_path / "replay.pt"
    # File replay accepts a nonzero initial wheel velocity and aligns timestamps relative to its first sample.
    run("data_collection.py", "--fit_result", best_file, "--trajectory_file", training_file, "--output", replay_file)
    best, replay = read(best_file), read(replay_file)
    torch.testing.assert_close(replay["time"], best["time"])
    for field, tolerance in (("dof_pos", 0.0001), ("dof_vel", 0.001)):
        error = (replay[field] - best["sim_" + field]).abs().max().item()
        print(f"Same-trajectory {field} max absolute error: {error:.9g}")
        assert error <= tolerance
        torch.testing.assert_close(replay["des_" + field], training["des_" + field])
        torch.testing.assert_close(replay[field][0], training[field][0], rtol=0, atol=1e-6)

    run("data_collection.py", "--duration", ".08", "--min_frequency", "4", "--max_frequency", "8")
    before = data_path.read_bytes()
    held_out = read(data_path)
    assert not torch.equal(held_out["des_dof_vel"], training["des_dof_vel"])
    stdout = run(
        "data_collection.py",
        "--fit_result",
        "physics=newton_mjwarp",
        "--trajectory_file",
        data_path,
        "--output",
        replay_file,
        "--plot",
    )
    response = read(replay_file)
    for field, group in (("dof_pos", "Position"), ("dof_vel", "Velocity")):
        rmse = (response[field].double() - held_out[field].double()).square().mean().sqrt().item()
        print(f"Independent-trajectory {field} RMSE: {rmse:.8g}")
        assert f"{group} prediction RMSE: {rmse:.8g}" in stdout

    # Inject an offset only into measurements after initialization. The commands and physical
    # initial state are identical, so even a perfect fit must now play through a large residual.
    outliers = tmp_path / "offset-measurements.pt"
    for field in ("dof_pos", "dof_vel"):
        held_out[field][1:, 0] = response[field][1:, 0] + 1.0
    torch.save(held_out, outliers)
    offset_replay = tmp_path / "offset-response.pt"
    run(
        "data_collection.py",
        "--fit_result",
        best_file,
        "--trajectory_file",
        outliers,
        "--output",
        offset_replay,
        "--plot",
    )
    for field in ("dof_pos", "dof_vel"):
        assert (read(offset_replay)[field][1:, 0] - held_out[field][1:, 0]).abs().max() > 0.5
    assert data_path.read_bytes() == before


def test_cli_protects_inputs_before_simulation(tmp_path):
    task = "Isaac-Pace-Sevnce-X5-v0"
    default = tmp_path / "data" / task / "chirp_data.pt"
    default.parent.mkdir(parents=True)
    trajectory = tmp_path / "trajectory.pt"
    zeros = torch.zeros(2, 12)
    wheels = torch.zeros(2, 4)
    torch.save(
        dict(time=torch.tensor([0.0, 0.0025]), dof_pos=zeros, des_dof_pos=zeros, dof_vel=wheels, des_dof_vel=wheels),
        trajectory,
    )
    result = tmp_path / "best_result.pt"
    result.write_bytes(b"preserve this result")
    default.write_bytes(b"preserve this collection")
    args = [
        sys.executable,
        str(ROOT / "scripts" / "pace" / "data_collection.py"),
        "--task",
        task,
        "--fit_result",
        str(result),
        "--trajectory_file",
        str(trajectory),
    ]
    env = dict(os.environ, PACE_ROOT=str(tmp_path))
    configured = default.with_name("training.pt")
    configured.write_bytes(b"preserve the configured fit reference")
    args.append("env.sim2real.data_dir=training.pt")
    native = default.with_name("mujoco_chirp_data.pt")
    native.write_bytes(b"preserve the native MuJoCo collection")
    for path in (result, trajectory, default, native, configured):
        before = path.read_bytes()
        completed = subprocess.run([*args, "--output", str(path)], env=env, capture_output=True, text=True, timeout=60)
        assert completed.returncode != 0 and "protected" in completed.stderr
        assert path.read_bytes() == before
    completed = subprocess.run([*args, "--duration", "20"], env=env, capture_output=True, text=True, timeout=60)
    assert completed.returncode == 2 and "--trajectory_file and --duration" in completed.stderr


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("PACE_RUN_SUBSET_INTEGRATION") != "1", reason="Opt in to the four-drive X5 checks")
@pytest.mark.parametrize("selection", ["FL", "FR", "RL", "RR", "wheel", "asymmetric", "position"])
def test_x5_subset_fit_and_replay(tmp_path, selection):
    """Each process runs the normal CLI with the four physical drive groups of the test robot."""
    import psutil
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    if not torch.cuda.is_available():
        pytest.skip("X5 Newton integration requires CUDA")
    task = "Isaac-Pace-Sevnce-X5-v0"
    legs = [f"{selection}_{kind}_joint" for kind in ("calf", "hip", "thigh")]
    wheels = [f"{selection}_foot_joint"]
    if selection == "wheel":
        legs, wheels = [], ["FL_foot_joint"]
    elif selection == "position":
        legs, wheels = ["FR_calf_joint"], []
    elif selection == "asymmetric":
        legs, wheels = ["RR_calf_joint", "FR_hip_joint"], ["RL_foot_joint"]

    runner = """
import importlib, os, sys
sys.path.insert(0, sys.argv.pop(1))
entry = importlib.import_module(sys.argv.pop(1))
resolve = entry.resolve_task_config
def four_drives(*args, **kwargs):
    cfg, agent = resolve(*args, **kwargs)
    source = cfg.scene.robot.actuators["joints"]
    cfg.scene.robot.actuators = {
        side: source.replace(joint_names_expr=[side + "_.*_joint"], encoder_bias=0.03)
        for side in ("FL", "FR", "RL", "RR")
    }
    cfg.scene.robot.init_state.joint_vel = {".*_foot_joint": 0.4, ".*_(hip|thigh|calf)_joint": 0.0}
    if os.environ.get("CHANGE_HOLD"):
        cfg.scene.robot.init_state.joint_vel[".*_foot_joint"] = 0.7
    return cfg, agent
entry.resolve_task_config = four_drives
entry.main()
"""

    def run(script, *args, pos=legs, vel=wheels, change_hold=False):
        if min(psutil.virtual_memory().available, torch.cuda.mem_get_info()[0]) < 4 * 1024**3:
            pytest.skip("Insufficient free RAM or VRAM for bounded X5 run")
        command = [
            sys.executable,
            "-c",
            runner,
            str(ROOT / "scripts/pace"),
            script,
            "--task",
            task,
            "--num_envs",
            "2",
            "--visualizer",
            "none",
            *map(str, args),
            f"env.sim2real.reference_leg_order={json.dumps(pos)}",
            f"env.sim2real.reference_wheel_order={json.dumps(vel)}",
        ]
        result = subprocess.run(
            command,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=120,
            env=dict(
                os.environ,
                PACE_ROOT=str(tmp_path),
                MPLBACKEND="Agg",
                CHANGE_HOLD="yes" if change_hold else "",
                OMP_NUM_THREADS="2",
                MKL_NUM_THREADS="2",
            ),
        )
        assert result.returncode == 0, (result.stdout + result.stderr)[-5000:]
        return result.stdout

    path = tmp_path / "input.pt"
    t = torch.arange(12, dtype=torch.float64) * 0.0025
    data = {"time": t}
    for group, names, factor in (("pos", legs, 0.03), ("vel", wheels, 1.3)):
        if names:
            wave = torch.stack([factor * (i + 1 + torch.sin(t.float() * 20)) for i in range(len(names))], dim=1)
            data["dof_" + group] = wave
            data["des_dof_" + group] = wave + factor
    torch.save(data, path)
    run("fit", f"env.sim2real.data_dir={path}", "env.sim2real.cmaes.max_iteration=2", "env.sim2real.cmaes.epsilon=0")
    (result_path,) = tmp_path.glob("logs/pace-sim2real/*/*/best_result.pt")
    best = torch.load(result_path, weights_only=True)
    assert best["schema_version"] == 3 and best["leg_order"] == legs and best["wheel_order"] == wheels
    assert len(best["params"]) == 3 * (len(legs) + len(wheels)) + len(legs) + 1
    settings = best["settings"]
    assert set(settings["delay_actuator_groups"]) == {n[:2] for n in legs + wheels}
    for side, names in settings["delay_actuator_groups"].items():
        assert set(names) == {f"{side}_{kind}_joint" for kind in ("hip", "thigh", "calf", "foot")}
    events = EventAccumulator(str(result_path.parent)).Reload()
    tags = events.Tags()["scalars"]
    assert ("error/position_rmse_rad" in tags) == bool(legs)
    assert ("error/velocity_rmse_rad_s" in tags) == bool(wheels)
    assert len(events.Scalars("0_Delay/mean")) == 2
    assert {name.removeprefix("1_Armature/best_") for name in tags if name.startswith("1_Armature/best_")} == set(
        legs + wheels
    )

    output = tmp_path / "played.pt"
    run("data_collection", "--fit_result", result_path, "--trajectory_file", path, "--output", output)
    response = torch.load(output, weights_only=True)
    assert response.keys() == data.keys()
    for group, names, atol in (("pos", legs, 0.0001), ("vel", wheels, 0.001)):
        if names:
            torch.testing.assert_close(response["dof_" + group], best["sim_dof_" + group], atol=atol, rtol=0)
            torch.testing.assert_close(response["des_dof_" + group], data["des_dof_" + group])
    process = subprocess.run(
        [sys.executable, str(ROOT / "scripts/pace/plot_trajectory.py"), "--task", task, "--plot_trajectory"],
        cwd=tmp_path,
        env=dict(os.environ, PACE_ROOT=str(tmp_path), MPLBACKEND="Agg"),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert process.returncode == 0, process.stderr
    if selection in ("wheel", "asymmetric"):
        run("data_collection", "--fit_result", result_path, "--duration", ".03", "--output", output, pos=[], vel=[])
        sweep = torch.load(output, weights_only=True)
        assert sweep.keys() == data.keys()
        torch.testing.assert_close(sweep["des_dof_vel"][0], torch.zeros(len(wheels)))
        for k in ("dof_pos", "des_dof_pos"):
            if k in data:
                data[k] = data[k].flip(1)
        torch.save(data, path)
        stdout = run(
            "data_collection",
            "--fit_result",
            result_path,
            "--trajectory_file",
            path,
            "--output",
            output,
            pos=list(reversed(legs)),
            change_hold=True,
        )
        assert "hold_velocities" in stdout and "rad/s" in stdout
        assert "Velocity prediction RMSE" in stdout


def test_named_subset_chirp_uses_the_full_task_coefficients():
    program = """
from types import SimpleNamespace
import torch
from data_collection import _named_chirp
args = SimpleNamespace(duration=.1, min_frequency=1., max_frequency=2.)
pos, vel = _named_chirp(args, .01, "cpu", ["RR_hip_joint","FL_calf_joint"], ["FR_foot_joint"])
t = torch.arange(10, dtype=torch.float64) * .01
signal = (2 * torch.pi * (t + 5 * t.square())).sin().float()
torch.testing.assert_close(pos[:, 0], -.25 * signal)
torch.testing.assert_close(pos[:, 1], .99 * (signal - 1.4))
torch.testing.assert_close(vel[:, 0], 10 * signal)
try:
    _named_chirp(args, .01, "cpu", ["custom_joint"], [])
except ValueError as error:
    assert "--trajectory_file" in str(error)
else:
    raise AssertionError("Expected an explicit file requirement for an unknown joint")
"""
    result = subprocess.run(
        [sys.executable, "-c", program], cwd=ROOT / "scripts/pace", text=True, capture_output=True, timeout=60
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "field,value",
    [
        ("task_leg_order", ["hip", "unknown"]),
        ("task_wheel_order", ["hip"]),
        ("hold_positions", {"calf": float("nan")}),
        ("hold_velocities", {}),
        ("delay_actuator_groups", {"front": ["hip"]}),
    ],
)
def test_partial_replay_rejects_incompatible_conditions(replay_contract, field, value):
    current = dict(
        task_leg_order=["hip", "calf"],
        task_wheel_order=["wheel"],
        hold_positions={"calf": 0.1},
        hold_velocities={"wheel": 0.5},
        delay_actuator_groups={"front": ["wheel", "hip"]},
    )
    with pytest.raises(ValueError, match=field):
        replay_contract.compare_replay_conditions({**current, field: value}, current)
