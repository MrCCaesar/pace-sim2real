"""Exercise the fitted-parameter file contract independently of simulator startup."""

from types import SimpleNamespace
from typing import Any

import pytest
import torch


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


def test_replay_reads_named_parameters_in_task_order(tmp_path):
    from pace_sim2real.utils.fit_replay import load_replay_parameters

    path, cfg, _ = fit_file(tmp_path)
    params = load_replay_parameters(path, cfg, ("a", "b"), ("w",))
    torch.testing.assert_close(params.armature, torch.tensor([2.0, 1.0, 3.0]))
    torch.testing.assert_close(params.damping, torch.tensor([3.0, 2.0, 4.0]))
    torch.testing.assert_close(params.friction, torch.tensor([4.0, 3.0, 5.0]))
    torch.testing.assert_close(params.bias, torch.tensor([0.1, -0.4, 0.0]))
    assert params.delay_steps == 2


@pytest.mark.parametrize("ratio, expected", [(None, [4.0, 3.0]), (0.25, [1.0, 0.75])])
def test_physx_friction_and_leg_only_replay(tmp_path, ratio, expected):
    from pace_sim2real.utils.fit_replay import load_replay_parameters

    path, cfg, _ = fit_file(tmp_path, backend="PhysxCfg", ratio=ratio, wheels=())
    params = load_replay_parameters(path, cfg, ("a", "b"), ())
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
        ("duplicate", "duplicate"),
        ("negative", "nonnegative"),
        ("delay", "delay"),
        ("partial", "Missing parameters"),
        ("unpaired", "sim_dof_pos"),
    ],
)
def test_incompatible_result_identifies_the_problem(tmp_path, change, match):
    from pace_sim2real.utils.fit_replay import load_replay_parameters

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
        load_replay_parameters(path, cfg, ("a", "b"), ("w",))


def test_latest_run_is_selected_before_checking_for_the_result(tmp_path):
    from pace_sim2real.utils.fit_replay import latest_fit_result

    old = tmp_path / "26_11_01_12-00-00-000000"
    recent = tmp_path / "26_11_02_12-00-00-000000"
    (tmp_path / "videos").mkdir()
    with pytest.raises(FileNotFoundError, match="No fitting run"):
        latest_fit_result(tmp_path)
    old.mkdir()
    (old / "best_result.pt").touch()
    recent.mkdir()
    with pytest.raises(FileNotFoundError, match=recent.name):
        latest_fit_result(tmp_path)
    result = recent / "best_result.pt"
    result.touch()
    old.touch()
    assert latest_fit_result(tmp_path) == result


def test_prediction_error_uses_measurements_and_physical_units():
    from pace_sim2real.utils.fit_replay import prediction_rmse

    replay = {"dof_pos": torch.tensor([[0.0, 0.0], [0.0, 4.0]]), "dof_vel": torch.tensor([[6.0], [6.0]])}
    reference = {
        "dof_pos": torch.zeros(2, 2),
        "dof_vel": torch.ones(2, 1),
        "des_dof_pos": replay["dof_pos"],
        "des_dof_vel": replay["dof_vel"],
    }
    assert prediction_rmse(replay, reference) == {"dof_pos": 2.0, "dof_vel": 5.0}
    assert prediction_rmse({"dof_pos": replay["dof_pos"]}, reference) == {"dof_pos": 2.0}


@pytest.mark.integration
def test_x5_short_fit_replays_its_response_and_checks_an_independent_chirp(tmp_path):
    """Exercise fixed collection, fitting, and both replay entry points in isolated task directories."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    if not torch.cuda.is_available() or torch.cuda.mem_get_info()[0] < 4 * 1024**3:
        pytest.skip("X5 Newton integration requires an available CUDA device")
    scripts = Path(__file__).resolve().parents[1] / "scripts" / "pace"
    task = "Isaac-Pace-Sevnce-X5-v0"
    data_path = tmp_path / "data" / task / "chirp_data.pt"
    env = dict(os.environ, PACE_ROOT=str(tmp_path), MPLBACKEND="Agg", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2")

    def run(script, *args):
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
    for field, group, tol in (("dof_pos", "Position", 0.0001), ("dof_vel", "Velocity", 0.001)):
        rmse = (response[field].double() - held_out[field].double()).square().mean().sqrt().item()
        print(f"Independent-trajectory {field} RMSE: {rmse:.8g}")
        assert f"{group} prediction RMSE: {rmse:.8g}" in stdout
        assert rmse > tol  # The replay still plotted, saved, and exited successfully.
    assert data_path.read_bytes() == before


def test_cli_protects_inputs_before_simulation(tmp_path, monkeypatch):
    import sys

    monkeypatch.setattr(sys, "argv", [sys.argv[0]])
    from scripts.pace import data_collection

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
    monkeypatch.setenv("PACE_ROOT", str(tmp_path))
    for path in (result, trajectory, default):
        before = path.read_bytes()
        with pytest.raises(ValueError, match="protected"):
            data_collection.main(
                [
                    "--task",
                    task,
                    "--fit_result",
                    str(result),
                    "--trajectory_file",
                    str(trajectory),
                    "--output",
                    str(path),
                ]
            )
        assert path.read_bytes() == before
    with pytest.raises(SystemExit) as exc:
        data_collection.main(["--task", task, "--fit_result", "--trajectory_file", str(trajectory), "--duration", "20"])
    assert exc.value.code == 2
