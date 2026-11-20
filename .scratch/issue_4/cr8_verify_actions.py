"""Observe CR8 commands and articulation state at the normal Newton CLI's step boundary.

Run in an isolated PACE_ROOT, using the same directory as cwd. Run x5 without an extra argument.
Pass a full same-task collection after x3 or anymal. For replay pass the X5 asymmetric v3 fit.
"""

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

import psutil

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/pace"))
case = sys.argv[1]
if case == "replay":
    import replay as entry
else:
    import data_collection as entry

import torch  # noqa: E402 - preserve the CLI's Warp initialization order.

model, pos_columns, vel_columns = {
    "x3": ("Sevnce-X3mini", {}, {"LF_WHEEL": 0}),
    "anymal": ("Anymal-D", {"RF_HAA": 3}, {}),
    "x5": ("Sevnce-X5", {"RR_calf_joint": 11, "FR_hip_joint": 3}, {"RL_foot_joint": 2}),
    "replay": ("Sevnce-X5", {"RR_calf_joint": 11, "FR_hip_joint": 3}, {"RL_foot_joint": 2}),
}[case]
task = f"Isaac-Pace-{model}-v0"
root = Path(os.environ["PACE_ROOT"]).resolve()
assert root == Path.cwd() and root != REPO
free = (psutil.virtual_memory().available, torch.cuda.mem_get_info()[0])
print("Available RAM / VRAM GiB:", *(round(n / 1024**3, 2) for n in free), flush=True)
assert min(free) >= 4 * 1024**3
full_path = Path(sys.argv[2]) if case in ("x3", "anymal") else REPO / ".scratch/issue_4/cr8-baseline.pt"
baseline = torch.load(full_path, weights_only=True)
resolve = entry.resolve_task_config
environment = entry.trajectory.trajectory_environment
steps = 0


def with_distinct_defaults(*args):
    cfg, agent = resolve(*args)
    drives = cfg.scene.robot.actuators
    if model == "Sevnce-X5":
        cfg.scene.robot.actuators = {
            side: drives["joints"].replace(joint_names_expr=[side + "_.*_joint"], encoder_bias=0.03)
            for side in ("FL", "FR", "RL", "RR")
        }
    else:
        for drive in drives.values():
            drive.encoder_bias = 0.03
    cfg.scene.robot.init_state.joint_vel = {".*": 0.2}
    if case == "replay":
        cfg.scene.robot.init_state.joint_vel = {".*_foot_joint": 0.4, ".*_(hip|thigh|calf)_joint": 0.0}
    return cfg, agent


def equal(actual, expected):
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)


@contextmanager
def observe(*args):
    with environment(*args) as env:
        base = env.unwrapped
        for name, column in pos_columns.items():
            assert base.cfg.sim2real.leg_order[column] == name
        for name, column in vel_columns.items():
            assert base.cfg.sim2real.wheel_order[column] == name
        robot = base.scene["robot"]
        selected = pos_columns.keys() | vel_columns.keys()
        names = robot.joint_names
        data = robot.data
        q, v = data.default_joint_pos.torch.clone(), data.default_joint_vel.torch.clone()
        initial_q, initial_v = q.clone(), v.clone()
        mechanics = {"joint_armature": 0.1, "joint_viscous_friction_coeff": 4.5, "joint_friction_coeff": 0.05}
        expected_mechanics = {key: getattr(data, key).torch.clone() for key in mechanics}
        for name in selected:
            for key, value in mechanics.items():
                expected_mechanics[key][:, names.index(name)] = value
        buffers = {}
        biases = {}
        for key, drive in robot.actuators.items():
            biases[key] = drive.encoder_bias.clone()
            for col, name in enumerate(drive.joint_names):
                if name in selected:
                    biases[key][:, col] = 0.05 if name in pos_columns else 0
            for signal, buffer in drive.delay_buffers.items():
                lag = buffer.time_lags.clone()
                if selected.intersection(drive.joint_names):
                    lag.fill_(5)
                buffers[key, signal] = lag
        targets = []
        for key in base.action_manager.active_terms:
            term = base.action_manager.get_term(key)
            position = type(term).__name__ == "JointPositionAction"
            columns = pos_columns if position else vel_columns
            full = baseline["des_dof_pos" if position else "des_dof_vel"]
            for name in term._joint_names:
                col = names.index(name)
                if name in columns:
                    curve = full[:, columns[name]].to(base.device)
                    if position:
                        initial_q[:, col] = curve[0] + 0.05
                    else:
                        initial_v[:, col] = 0
                elif position:
                    curve = (q[0, col] - 0.03).expand(len(full))
                    initial_v[:, col] = 0
                else:
                    curve = v[0, col].expand(len(full))
                targets.append(curve)
        expected = torch.stack(targets, 1)
        assert expected.shape == (40, len(names))
        step = env.step

        def checked_step(action):
            global steps
            if steps == 0 and case != "replay":
                equal(data.joint_pos.torch, initial_q)
                equal(data.joint_vel.torch, initial_v)
                for key, value in expected_mechanics.items():
                    equal(getattr(data, key).torch, value)
                for key, drive in robot.actuators.items():
                    equal(drive.encoder_bias, biases[key])
                    for signal, buffer in drive.delay_buffers.items():
                        equal(buffer.time_lags, buffers[key, signal])
            equal(action, expected[steps].expand(2, -1))
            steps += 1
            return step(action)

        env.step = checked_step
        yield env
        print(f"{case}: {steps} steps x 2 envs x {len(names)} action columns, drives={list(robot.actuators)}")


entry.resolve_task_config = with_distinct_defaults
entry.trajectory.trajectory_environment = observe
args = ["--task", task, "--num_envs", "2", "--visualizer", "none", "--duration", ".1"]
if case == "replay":
    result = Path(sys.argv[2]).resolve()
    best = torch.load(result, weights_only=True)
    assert best["leg_order"] == list(pos_columns) and best["wheel_order"] == list(vel_columns)
    args += ["--fit_result", str(result)]
    assert not list(root.rglob("*.pt"))
legs, wheels = ([], []) if case == "replay" else (list(pos_columns), list(vel_columns))
entry.main(
    args
    + [
        f"env.sim2real.reference_leg_order={json.dumps(legs)}",
        f"env.sim2real.reference_wheel_order={json.dumps(wheels)}",
    ]
)
assert steps == 40
if case == "replay":
    assert not list(root.rglob("*.pt"))
else:
    output = torch.load(root / "data" / task / "chirp_data.pt", weights_only=True)
    equal(output["time"], baseline["time"])
    fields = {"time"}
    for field, columns in (("pos", pos_columns), ("vel", vel_columns)):
        if columns:
            measured, desired = "dof_" + field, "des_dof_" + field
            fields.update((measured, desired))
            equal(output[desired], baseline[desired][:, list(columns.values())])
            assert output[measured].shape == (steps, len(columns))
    assert output.keys() == fields
print("PASS", case)
