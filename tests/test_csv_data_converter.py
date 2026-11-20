import csv
import importlib.util
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from pace_sim2real.utils.sample_period import resolve_sample_period

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pace/csv_data_converter.py"
spec = importlib.util.spec_from_file_location("csv_converter", SCRIPT)
converter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converter)
X3 = "Isaac-Pace-Sevnce-X3mini-v0"
SAMPLE = ROOT / "data/Isaac-Pace-Sevnce-X5-v0/motor_sweep_simulated/data.csv"


def run(path, *args, task=X3):
    return subprocess.run(
        [sys.executable, SCRIPT, path, "--task", task, *args],
        cwd=path.parent.parent,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize("legs,wheels", [(["b", "a"], ["speed"]), (["b", "a"], []), ([], ["speed"])])
def test_mapping(tmp_path, legs, wheels):
    names = legs + wheels
    cols = [(name, key) for name in reversed(names) for key in ("feedback_valid", "dq_des", "q_des", "dq", "q", "temp")]
    path = tmp_path / "frames.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s", *(f"{n}.{k}" for n, k in cols)])
        for i in range(5):
            writer.writerow(
                [
                    0.1 + i * 0.002,
                    *(
                        int(not (i in (0, 4) and n == names[i % len(names)]))
                        if k == "feedback_valid"
                        else 10 * names.index(n) + i + len(k)
                        for n, k in cols
                    ),
                ]
            )
    data, groups, lines, counts = converter._read(path, legs, wheels)
    assert groups == [legs, wheels] and lines == [3, 4, 5] and counts == (5, 1, 1)
    keys = {"time"}
    for group, field, suffix in ((legs, "pos", "q"), (wheels, "vel", "dq")):
        for prefix, k in (("", suffix), ("des_", suffix + "_des")):
            if group:
                key = prefix + "dof_" + field
                keys.add(key)
                expected = [[10 * names.index(n) + i + len(k) for n in group] for i in range(1, 4)]
                torch.testing.assert_close(data[key], torch.tensor(expected, dtype=torch.float32))
    assert set(data) == keys


HEADER = "time_s,p.feedback_valid,p.q,p.q_des"


@pytest.mark.parametrize(
    "header,rows,match",
    [
        (HEADER, ["0,1,0,0", "1,0,,0", "2,1,0,0"], "line 3.*p"),
        (HEADER, ["0,0,,0", "1,0,,0"], "two"),
        (HEADER, ["0,1,0,0"], "two"),
        (HEADER, ["0,1,,0"], "line 2.*p.q"),
        (HEADER, ["0,1,inf,0"], "line 2.*p.q"),
        (HEADER, ["0,1,1e39,0"], "line 2.*p.q"),
        (HEADER, ["0,2,0,0"], "feedback_valid"),
        (HEADER, ["0,1,0"], "fields"),
        (HEADER, ["nan,1,0,0"], "line 2.*time_s"),
        (HEADER, ["1,1,0,0", "1,1,0,0"], "line 3"),
        (HEADER, ["1,1,0,0", "0,1,0,0"], "line 3"),
        (HEADER + ",p.q", [], "duplicate"),
        (HEADER.replace("p.q_des", "p.temp"), [], "p.q_des"),
        (HEADER + ",bad.q", [], "bad"),
    ],
)
def test_bad_csv(tmp_path, header, rows, match):
    path = tmp_path / "bad.csv"
    path.write_text("\n".join([header, *rows]))
    with pytest.raises((KeyError, ValueError), match=match):
        converter._read(path, ["p"], [])


def test_grid():
    for dt in (0.002, 0.0025):
        time = 0.004 + torch.arange(20, dtype=torch.float64) * dt
        assert resolve_sample_period(time, 0.0025, range(2, 22)) == pytest.approx(dt)
    time[5] += 5e-8
    assert resolve_sample_period(time, 0.0025, range(2, 22)) == 0.0025
    time[5] += 0.0003
    with pytest.raises(ValueError, match="line 7"):
        resolve_sample_period(time, 0.0025, range(2, 22))


def test_feasible_grid_with_endpoint_jitter():
    steps = torch.arange(5, dtype=torch.float64)
    expected = steps * 0.003
    time = expected.clone()
    time[2] -= 9e-5
    time[-1] += 9e-5
    # The end-to-end average is too large for frame 2, but a common period exists.
    assert not torch.allclose(time, steps * (time[-1] / 4), rtol=1e-5, atol=1e-4)
    dt = resolve_sample_period(time, 0.0025, range(2, 7))
    torch.testing.assert_close(time, steps * dt, rtol=1e-5, atol=1e-4)


def test_competing_writes_and_failure(tmp_path, monkeypatch):
    dest = tmp_path / "same.pt"

    def save(i):
        try:
            converter._save(dest, torch.tensor(i))
            return i
        except ValueError:
            return None

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(save, [1, 2]))
    assert results.count(None) == 1
    assert torch.load(dest, weights_only=True).item() in results

    def fail(*_):
        raise OSError("simulated write failure")

    monkeypatch.setattr(torch, "save", fail)
    with pytest.raises(OSError):
        converter._save(tmp_path / "new.pt", {})
    assert list(tmp_path.iterdir()) == [dest]


def test_cli_paths_and_tasks(tmp_path):
    directory = tmp_path / "input"
    directory.mkdir()
    path = directory / "test.csv"
    path.write_text((HEADER + "\n0,1,2,3\n0.0025,1,4,5\n").replace("p.", "RF_HAA."))
    task = "Isaac-Pace-Anymal-D-v0"
    for args, name in (([], "chirp_data.pt"), (["--output", "other.pt"], "other.pt")):
        proc = run(path, *args, task=task)
        assert proc.returncode == 0, proc.stderr
        assert set(torch.load(directory / name, weights_only=True)) == {"time", "dof_pos", "des_dof_pos"}
    alias = directory / "alias.pt"
    os.link(path, alias)
    for dest in (directory / "chirp_data.pt", path, alias):
        before = dest.read_bytes()
        proc = run(path, "--output", dest, task=task)
        assert proc.returncode and "--output" in proc.stderr and dest.read_bytes() == before
    assert run(path, task="no-such-task-v0").returncode


@pytest.mark.skipif(not SAMPLE.exists(), reason="Local motor sweep CSV unavailable")
def test_supplied_sample(tmp_path):
    from pace_sim2real.utils.collection_contracts import load_reference_data

    dest = tmp_path / "converted.pt"
    proc = run(SAMPLE, "--output", dest)
    assert proc.returncode == 0, proc.stderr
    assert "retained=9998 trimmed_start=2 trimmed_end=0" in proc.stdout and "Control period: 0.002 s" in proc.stdout
    wheels = ["LF_WHEEL", "RF_WHEEL", "LH_WHEEL", "RH_WHEEL"]
    cfg = SimpleNamespace(leg_order=["leg"], wheel_order=wheels, reference_leg_order=[])
    with SAMPLE.open(newline="") as f:
        rows = list(csv.DictReader(f))[2:]
    data = torch.load(dest, weights_only=True)
    assert set(data) == {"time", "dof_vel", "des_dof_vel"}
    assert torch.equal(data["time"], torch.tensor([float(r["time_s"]) for r in rows], dtype=torch.float64))
    for key, suffix in (("dof_vel", "dq"), ("des_dof_vel", "dq_des")):
        expected = torch.tensor([[float(r[f"{n}.{suffix}"]) for n in wheels] for r in rows], dtype=torch.float32)
        torch.testing.assert_close(data[key], expected, atol=0, rtol=0)
    loaded = load_reference_data(dest, cfg, 0.002)
    assert loaded["time"][0] == 0 and torch.equal(loaded["original_time"], data["time"])
    with pytest.raises(ValueError, match="interval"):
        load_reference_data(dest, cfg, 0.0025)
    wrong = run(SAMPLE, "--output", tmp_path / "wrong.pt", task="Isaac-Pace-Sevnce-X5-v0")
    assert wrong.returncode and "LF_WHEEL" in wrong.stderr and not (tmp_path / "wrong.pt").exists()
