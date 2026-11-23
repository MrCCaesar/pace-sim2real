# SPDX-License-Identifier: Apache-2.0
"""Public collection/fit contract tests; CPU cases need no simulator bootstrap."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def contracts():
    return load_module("pace_collection_contract_tests", "src/pace_sim2real/utils/collection_contracts.py")


def test_groups_preserve_declared_order_and_legacy_position_tasks():
    module = contracts()
    assert module.resolve_joint_groups(SimpleNamespace(joint_order=["b", "a"])) == (("b", "a"), ())
    assert module.resolve_joint_groups(SimpleNamespace(leg_order=["b", "a"], wheel_order=["w"])) == (("b", "a"), ("w",))
    with pytest.raises(ValueError, match="joint_order"):
        module.resolve_joint_groups(SimpleNamespace(leg_order=["a"], wheel_order=["w"], joint_order=["w", "a"]))


def test_action_mapping_only_reorders_targets_and_ignores_environment_transforms():
    module = contracts()
    # Exercise the installed action-term adapter without launching a runtime.
    position_type = type("JointPositionAction", (), {"__module__": "isaaclab.envs.mdp.actions.joint_actions"})
    velocity_type = type("JointVelocityAction", (), {"__module__": "isaaclab.envs.mdp.actions.joint_actions"})
    pos, vel = position_type(), velocity_type()
    for term, names, scale, offset in [(pos, ["b", "a"], -2.0, 0.5), (vel, ["w"], 4.0, -1.0)]:
        term._joint_names, term._scale, term._offset = names, scale, offset
        term.action_dim = len(names)
        term.cfg = SimpleNamespace(asset_name="robot", clip=None)
    manager = SimpleNamespace(active_terms=["v", "p"], get_term=lambda name: {"v": vel, "p": pos}[name])
    robot = SimpleNamespace(joint_names=["w", "a", "b"])
    env = SimpleNamespace(action_manager=manager, scene={"robot": robot}, num_envs=1, device="cpu")
    mapping = module.resolve_action_mapping(env, ("a", "b"), ("w",))
    actions = module.pack_actions(mapping, torch.tensor([[1.5, -1.5]]), torch.tensor([[7.0]]))
    torch.testing.assert_close(actions, torch.tensor([[7.0, -1.5, 1.5]]))
    assert mapping["leg_ids"] == [1, 2]
    assert mapping["wheel_ids"] == [0]
    with pytest.raises(ValueError, match="shape"):
        module.pack_actions(mapping, torch.ones(1, 3), torch.ones(1, 1))


def test_reference_loader_requires_explicit_legacy_time_and_bias_provenance(tmp_path):
    module = contracts()
    data = {
        "time": torch.tensor([0.0, 0.02, 0.04]),
        "dof_pos": torch.zeros(3, 1),
        "des_dof_pos": torch.ones(3, 1),
        "dof_vel": torch.full((3, 1), 2.0),
        "des_dof_vel": torch.ones(3, 1),
    }
    path = tmp_path / "reference.pt"
    torch.save(data, path)
    cfg = SimpleNamespace(leg_order=["a"], wheel_order=["w"], time_mode="strict")
    with pytest.raises(ValueError, match="time"):
        module.load_reference_data(path, cfg, 0.01)
    cfg.time_mode, cfg.legacy_sample_dt = "legacy_index", 0.01
    loaded = module.load_reference_data(path, cfg, 0.01)
    torch.testing.assert_close(loaded["time"], torch.tensor([0.0, 0.01, 0.02], dtype=torch.float64))
    torch.testing.assert_close(loaded["original_time"], data["time"].double())
    cfg.reference_bias_model = "measurement_only"
    with pytest.raises(ValueError, match="recollect"):
        module.load_reference_data(path, cfg, 0.01)


@pytest.mark.parametrize("separate_friction", [False, True])
def test_optimizer_scores_both_groups_and_saves_the_evaluated_candidate(tmp_path, separate_friction):
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    optimizer = load_module("pace_optimizer_contract_tests", "src/pace_sim2real/optim/cma_es.py")
    data = {
        "time": torch.tensor([0.0, 0.01], dtype=torch.float64),
        "dof_pos": torch.zeros(2, 1),
        "des_dof_pos": torch.zeros(2, 1),
        "dof_vel": torch.zeros(2, 1),
        "des_dof_vel": torch.zeros(2, 1),
    }
    bounds = torch.tensor(
        [[0.01, 0.1], [0.01, 0.1], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.1, 0.1], [2.5, 2.5]]
    )
    if separate_friction:
        bounds[4:6] = torch.tensor([[0.4, 0.4], [0.8, 0.8]])
        bounds = torch.cat((bounds, torch.tensor([[0.5, 0.5], [0.25, 0.25]])))
    opt = optimizer.CMAESOptimizer(
        bounds,
        2,
        str(tmp_path),
        ["leg", "wheel"],
        2,
        data,
        "cpu",
        leg_order=["leg"],
        wheel_order=["wheel"],
        velocity_error_scale=2.0,
        separate_dynamic_friction=separate_friction,
        reference_settings={"dt": 0.01},
    )
    for _ in range(2):
        opt.tell(
            torch.tensor([[1.1], [2.1]]),
            torch.zeros(2, 1),
            sim_dof_vel=torch.tensor([[2.0], [4.0]]),
            real_dof_vel=torch.zeros(2, 1),
        )
    opt.evolve()
    result_path = next(tmp_path.rglob("best_result.pt"))
    result = torch.load(result_path, weights_only=True)
    config = torch.load(result_path.parent / "config.pt", weights_only=True)
    for record in (config, result):
        assert (record["leg_order"], record["wheel_order"]) == (["leg"], ["wheel"])
    assert result["settings"]["dt"] == config["dt"] == 0.01
    assert {"physics_dt", "control_dt", "leg_order", "wheel_order"}.isdisjoint(result["settings"])
    assert result["delay_steps"] == 2 and result["delay_seconds"] == pytest.approx(0.02)
    assert result["score"] == pytest.approx(1.0)
    assert result["position_rmse"] == pytest.approx(1.0)
    assert result["velocity_rmse"] == pytest.approx(2.0)
    torch.testing.assert_close(result["sim_dof_pos"], torch.ones(2, 1))
    torch.testing.assert_close(opt.get_best_sim_params().cpu(), result["params"])
    for _ in range(2):
        opt.tell(
            torch.tensor([[4.1], [3.1]]),
            torch.zeros(2, 1),
            sim_dof_vel=torch.tensor([[8.0], [6.0]]),
            real_dof_vel=torch.zeros(2, 1),
        )
    armature = opt.sim_params[:, opt.armature_idx].clone()
    opt.evolve()
    opt.close()
    assert torch.load(result_path, weights_only=True)["generation"] == 0

    events = EventAccumulator(str(opt.log_dir), size_guidance={"histograms": 0}).Reload()
    means = events.Scalars("1_Armature/mean_wheel")
    assert [entry.step for entry in means] == [0, 1]
    saved_mean = torch.load(opt.log_dir / "mean_000.pt", weights_only=True)
    assert means[0].value == saved_mean[1].item()
    assert means[1].value == opt._params_to_sim_params(torch.as_tensor(opt.optimizer.mean))[1].item()
    assert events.Scalars("0_Delay/mean")[1].value == 2.5
    best = events.Scalars("1_Armature/best_wheel")
    assert [entry.step for entry in best] == [0, 1]
    assert best[1].value == pytest.approx(armature[1, 1].item())
    distribution = events.Histograms("1_Armature/distribution_wheel")[1].histogram_value
    assert distribution.num == 2 and distribution.sum == pytest.approx(armature[:, 1].sum().item())
    assert "4_Bias/distribution_leg" in events.Tags()["histograms"]
    assert "4_Bias/distribution_wheel" not in events.Tags()["histograms"]
    assert events.Scalars("0_Delay/best")[1].value == 2.5
    assert events.Scalars("0_Episode/score")[1].value == pytest.approx(9.0)
    assert events.Scalars("0_Episode/max_score")[1].value == pytest.approx(16.0)
    assert events.Scalars("0_Episode/diff_score")[1].value == pytest.approx(7 / 9)
    assert ("6_Dynamic_Friction_Ratio/distribution_wheel" in events.Tags()["histograms"]) == separate_friction
    if separate_friction:
        assert events.Scalars("6_Dynamic_Friction_Ratio/best_wheel")[1].value == 0.25
        assert events.Scalars("6_Dynamic_Friction/best_wheel")[1].value == pytest.approx(0.2)


def test_joint_scales_normalize_each_column_and_roundtrip_through_plotting(tmp_path):
    optimizer = load_module("pace_joint_scale_optimizer", "src/pace_sim2real/optim/cma_es.py")
    plotter = load_module("pace_joint_scale_plot", "scripts/pace/plot_trajectory.py")
    data = {"time": torch.tensor([0.0, 0.01], dtype=torch.float64)}
    for key in ("dof_pos", "des_dof_pos", "dof_vel", "des_dof_vel"):
        data[key] = torch.zeros(2, 2)
    args = (torch.zeros(15, 2), 2, str(tmp_path), ["a", "b", "c", "d"], 1, data, "cpu")
    groups = dict(leg_order=["a", "b"], wheel_order=["c", "d"], reference_settings={"dt": 0.01})
    for key, scale in [
        ("position_error_scale", [1.0]),
        ("velocity_error_scale", [1.0, 1.0, 1.0]),
        ("position_error_scale", [1.0, float("nan")]),
        ("velocity_error_scale", [0.0, 2.0]),
    ]:
        with pytest.raises(ValueError, match=key):
            optimizer.CMAESOptimizer(*args, **groups, **{key: scale})

    opt = optimizer.CMAESOptimizer(
        *args, **groups, position_error_scale=[2.0, 8.0], velocity_error_scale=[3.0, 4.0], position_weight=2.0
    )
    q = torch.tensor([[2.0, 4.0], [3.0, 5.0]])
    v = torch.tensor([[6.0, 8.0], [7.0, 9.0]])
    try:
        for _ in range(2):
            opt.tell(q, torch.zeros_like(q), sim_dof_vel=v, real_dof_vel=torch.zeros_like(v))
        opt.evolve()
    finally:
        opt.close()
    result = plotter.load_result(opt.log_dir / "best_result.pt")
    assert result["score"] == pytest.approx((2 * 0.625 + 4) / 3)
    assert result["position_rmse"] == pytest.approx(10**0.5)
    assert result["velocity_rmse"] == pytest.approx(50**0.5)


def run_backend_contract(backend, optimization, output, decimation=1):
    """Bounded real ActionManager collection/fit path, launched in an isolated process."""
    import argparse
    import json

    import warp as wp

    wp.config.enable_backward = False
    from isaaclab.app import add_launcher_args, launch_simulation
    from isaaclab.sim import SimulationCfg
    from isaaclab_newton.physics import NewtonCfg
    from isaaclab_physx.physics import PhysxCfg

    parser = argparse.ArgumentParser()
    add_launcher_args(parser)
    args = parser.parse_args(["--visualizer", "none", "--device", "cuda:0"])
    physics = NewtonCfg(use_cuda_graph=False) if backend == "newton" else PhysxCfg()
    sim_cfg = SimulationCfg(
        dt=0.0025, gravity=(0.0, 0.0, 0.0), device="cuda:0", physics=physics, use_newton_actuators=False
    )
    with launch_simulation(sim_cfg, args):
        from pxr import Gf, Usd, UsdGeom, UsdPhysics

        from isaaclab.assets import ArticulationCfg
        from isaaclab.envs import ManagerBasedEnv, ManagerBasedEnvCfg, mdp
        from isaaclab.managers import ObservationGroupCfg, ObservationTermCfg
        from isaaclab.scene import InteractiveSceneCfg
        from isaaclab.sim import UsdFileCfg

        from pace_sim2real.optim import CMAESOptimizer
        from pace_sim2real.utils import PaceDCMotorCfg
        from pace_sim2real.utils import trajectory_simulation as collection
        from pace_sim2real.utils.collection_contracts import (
            load_reference_data,
            resolve_action_mapping,
        )

        fitting = load_module("pace_runtime_fit", "scripts/pace/fit.py")
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        asset = output / "minimal.usda"
        stage = Usd.Stage.CreateNew(str(asset))
        assert stage is not None
        root = cast(Any, UsdGeom.Xform.Define(stage, "/Robot")).GetPrim()
        stage.SetDefaultPrim(root)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdPhysics.ArticulationRootAPI.Apply(root)
        for name in ("base", "leg", "wheel"):
            prim = cast(Any, UsdGeom.Xform.Define(stage, "/Robot/" + name)).GetPrim()
            UsdPhysics.RigidBodyAPI.Apply(prim)
            mass = UsdPhysics.MassAPI.Apply(prim)
            assert mass is not None
            mass.CreateMassAttr(1.0)
            mass.CreateCenterOfMassAttr(Gf.Vec3f(0.0))
            mass.CreateDiagonalInertiaAttr(Gf.Vec3f(0.01))
        fixed = UsdPhysics.FixedJoint.Define(stage, "/Robot/root_joint")
        assert fixed is not None
        fixed.CreateBody1Rel().SetTargets(["/Robot/base"])
        for name in ("leg", "wheel"):
            joint = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/" + name + "_joint")
            assert joint is not None
            joint.CreateBody0Rel().SetTargets(["/Robot/base"])
            joint.CreateBody1Rel().SetTargets(["/Robot/" + name])
            joint.CreateAxisAttr("Z")
        stage.GetRootLayer().Save()
        del stage
        batch = 4 if optimization else 2
        scene: Any = InteractiveSceneCfg(num_envs=batch, env_spacing=2.0)
        scene.robot = ArticulationCfg(
            prim_path="{ENV_REGEX_NS}/Robot",
            spawn=UsdFileCfg(usd_path=str(asset)),
            init_state=ArticulationCfg.InitialStateCfg(
                joint_pos={".*": 0.0}, joint_vel={"leg_joint": 0.0, "wheel_joint": 1.5}
            ),
            actuators={
                "joints": PaceDCMotorCfg(
                    joint_names_expr=[".*"],
                    stiffness={"leg_joint": 20.0, "wheel_joint": 0.0},
                    damping=2.0,
                    saturation_effort=100.0,
                    actuator_effort_limit=100.0,
                    actuator_velocity_limit=100.0,
                    armature=0.03,
                    friction=0.0,
                    dynamic_friction=0.0,
                    viscous_friction=0.0,
                    encoder_bias=0.0,
                    max_delay=4,
                )
            },
        )
        observation: Any = ObservationGroupCfg()
        observation.position = ObservationTermCfg(func=mdp.joint_pos)
        cfg: Any = ManagerBasedEnvCfg(
            sim=sim_cfg,
            scene=scene,
            decimation=decimation,
            observations=SimpleNamespace(policy=observation),
            actions=SimpleNamespace(
                wheel=mdp.JointVelocityActionCfg(
                    asset_name="robot", joint_names=["wheel_joint"], scale=1.0, offset=0.0, use_default_offset=False
                ),
                leg=mdp.JointPositionActionCfg(
                    asset_name="robot", joint_names=["leg_joint"], scale=1.0, offset=0.0, use_default_offset=False
                ),
            ),
            seed=0,
        )
        cfg.sim2real = SimpleNamespace(
            leg_order=["leg_joint"],
            wheel_order=["wheel_joint"],
            reference_bias_model="feedback_and_measurement",
            reference_delay_mode="command",
            time_mode="strict",
            legacy_sample_dt=None,
        )
        env = ManagerBasedEnv(cfg)
        try:
            env.reset()
            robot = env.scene["robot"]
            mapping = resolve_action_mapping(env, ("leg_joint",), ("wheel_joint",))
            ids = mapping["leg_ids"] + mapping["wheel_ids"]
            truth = torch.tensor([[0.03, 0.15]], device=env.device).expand(batch, -1).contiguous()
            robot.write_joint_armature_to_sim_index(armature=truth, joint_ids=ids)
            for motor in robot.actuators.values():
                motor.update_time_lags(0)
                motor.reset()
            compute_records = []
            if decimation > 1:
                motor = robot.actuators["joints"]
                original_compute = motor.compute

                def measured_compute(action, joint_pos, joint_vel):
                    q, v = joint_pos, joint_vel
                    issued = (action.joint_positions.clone(), action.joint_velocities.clone())
                    value = original_compute(action, q, v)
                    compute_records.append((issued, q.clone(), v.clone(), value.joint_efforts.clone()))
                    return value

                motor.compute = measured_compute
                motor.update_time_lags(2)
            count = 40 // decimation
            t = torch.arange(count, device=env.device) * env.step_dt
            leg_target = (0.5 * torch.sin(2 * torch.pi * 5 * t)).unsqueeze(1)
            wheel_target = (5 * torch.sin(2 * torch.pi * 5 * t)).unsqueeze(1)
            data = collection.collect_trajectory(
                env, leg_target, wheel_target, torch.zeros(batch, 1, device=env.device)
            )
            assert data["dof_vel"][0, 0].item() == pytest.approx(1.5)
            torch.testing.assert_close(data["des_dof_pos"], leg_target.cpu())
            torch.testing.assert_close(data["des_dof_vel"], wheel_target.cpu())
            torch.save(data, output / "reference.pt")
            data = load_reference_data(output / "reference.pt", cfg.sim2real, env.step_dt)
            if decimation > 1:
                assert len(compute_records) == 40
                motor = robot.actuators["joints"]
                lp, wv = motor.joint_names.index("leg_joint"), motor.joint_names.index("wheel_joint")
                for k, (_, q, v, efforts) in enumerate(compute_records):
                    delayed_p, delayed_v = compute_records[max(0, k - 2)][0]
                    expected_p = 20 * (delayed_p[:, lp] - q[:, lp]) - 2 * v[:, lp]
                    expected_v = 2 * (delayed_v[:, wv] - v[:, wv])
                    torch.testing.assert_close(efforts[:, lp], expected_p)
                    torch.testing.assert_close(efforts[:, wv], expected_v)
                (output / "result.json").write_text(
                    json.dumps({
                        "backend": backend,
                        "decimation": decimation,
                        "physics_steps": 40,
                        "compute_calls": len(compute_records),
                        "delay_steps": 2,
                    })
                    + "\n"
                )
                print("CR2_DECIMATION_PASS", backend, flush=True)
                return
            bounds = torch.tensor(
                [[0.01, 0.2], [0.01, 0.2], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]
            )
            if not optimization:
                bounds[:2] = torch.tensor([[0.03, 0.03], [0.15, 0.15]])
            checks = {}
            if optimization:
                for label, values in [("truth", [0.03, 0.15]), ("perturbed", [0.12, 0.05])]:
                    fixed_bounds = bounds.clone()
                    fixed_bounds[:2] = torch.tensor([[values[0], values[0]], [values[1], values[1]]])
                    check = CMAESOptimizer(
                        fixed_bounds,
                        batch,
                        str(output),
                        ["leg_joint", "wheel_joint"],
                        1,
                        data,
                        env.device,
                        leg_order=["leg_joint"],
                        wheel_order=["wheel_joint"],
                        reference_settings={"dt": cfg.sim.dt, "reference_delay_mode": "command"},
                    )
                    try:
                        fitting.fit_reference(env, data, check)
                        assert check.best_result is not None
                        checks[label] = {
                            key: check.best_result[key] for key in ("score", "position_rmse", "velocity_rmse")
                        }
                    finally:
                        check.close()
                assert checks["truth"]["score"] < checks["perturbed"]["score"]
                for group in ("position_rmse", "velocity_rmse"):
                    assert checks["truth"][group] < checks["perturbed"][group]
            opt = CMAESOptimizer(
                bounds,
                batch,
                str(output),
                ["leg_joint", "wheel_joint"],
                20 if optimization else 1,
                data,
                env.device,
                leg_order=["leg_joint"],
                wheel_order=["wheel_joint"],
                epsilon=None,
                reference_settings={
                    "dt": cfg.sim.dt,
                    "reference_delay_mode": "command",
                },
            )
            try:
                fitting.fit_reference(env, data, opt)
                result = opt.best_result
                assert result is not None
                initial = opt.scores_buffer[0].min().item()
                if optimization:
                    assert result["score"] <= 0.5 * initial, (initial, result["score"])
                else:
                    assert result["score"] < 1e-10, result["score"]
                q_error = result["sim_dof_pos"] - data["dof_pos"]
                v_error = result["sim_dof_vel"] - data["dof_vel"]
                assert result["position_rmse"] == pytest.approx(
                    q_error.double().square().mean().sqrt().item(), abs=1e-8
                )
                assert result["velocity_rmse"] == pytest.approx(
                    v_error.double().square().mean().sqrt().item(), abs=1e-8
                )
                record = {
                    "backend": backend,
                    "optimization": optimization,
                    "num_envs": batch,
                    "steps": 40,
                    "truth_checks": checks,
                    "initial_score": initial,
                    "best_score": result["score"],
                    "position_rmse": result["position_rmse"],
                    "velocity_rmse": result["velocity_rmse"],
                    "result": str(opt.log_dir / "best_result.pt"),
                }
                (output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
                print("CR2_BACKEND_PASS", json.dumps(record), flush=True)
            finally:
                opt.close()
        finally:
            env.close()


if __name__ == "__main__":
    run_backend_contract(sys.argv[1], sys.argv[2] == "optimize", sys.argv[3], 2 if sys.argv[2] == "decimation" else 1)


def test_plot_result_uses_paired_measurements_without_second_bias_subtraction(monkeypatch):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plotter = load_module("pace_plot_contract_tests", "scripts/pace/plot_trajectory.py")
    result = {
        "schema_version": 2,
        "leg_order": ["leg"],
        "wheel_order": ["wheel"],
        "time": torch.tensor([0.0, 0.01]),
        "sim_dof_pos": torch.tensor([[0.2], [0.3]]),
        "sim_dof_vel": torch.tensor([[1.0], [2.0]]),
        "reference": {
            "dof_pos": torch.tensor([[0.1], [0.2]]),
            "des_dof_pos": torch.zeros(2, 1),
            "dof_vel": torch.zeros(2, 1),
            "des_dof_vel": torch.ones(2, 1),
        },
        "settings": {
            "position_error_scale": 1.0,
            "velocity_error_scale": 1.0,
            "position_weight": 1.0,
            "velocity_weight": 1.0,
        },
    }
    figures = plotter.plot_result(result)
    assert len(figures) == 2
    torch.testing.assert_close(torch.tensor(figures[0].axes[0].lines[2].get_ydata()), result["sim_dof_pos"][:, 0])
    assert "rad/s" in figures[1].axes[0].get_ylabel()
    assert plotter.result_errors(result)["position_rmse"] == pytest.approx(0.1)
    for f in figures:
        plt.close(f)


@pytest.mark.parametrize("mutation", ["missing_velocity", "width", "nonfinite", "order", "samples", "nonuniform"])
def test_reference_loader_rejects_invalid_mixed_input(tmp_path, mutation):
    cfg = SimpleNamespace(leg_order=["a"], wheel_order=["w"])
    data = {
        "time": torch.tensor([0.0, 0.01, 0.02], dtype=torch.float64),
        "dof_pos": torch.zeros(3, 1),
        "des_dof_pos": torch.zeros(3, 1),
        "dof_vel": torch.zeros(3, 1),
        "des_dof_vel": torch.zeros(3, 1),
    }
    if mutation == "missing_velocity":
        del data["dof_vel"]
    elif mutation == "width":
        data["dof_vel"] = torch.zeros(3, 2)
    elif mutation == "nonfinite":
        data["dof_pos"][1] = float("nan")
    elif mutation == "order":
        cfg.reference_leg_order = ["wrong"]
    elif mutation == "samples":
        data["dof_pos"] = torch.zeros(2, 1)
    elif mutation == "nonuniform":
        data["time"][1] = 0.014
    path = tmp_path / "data.pt"
    torch.save(data, path)
    with pytest.raises(ValueError):
        contracts().load_reference_data(path, cfg, 0.01)


def test_legacy_pure_position_reference_and_zero_score_stopping(tmp_path):
    cfg = SimpleNamespace(joint_order=["leg"])
    data = {
        "time": torch.tensor([0.0, 0.01], dtype=torch.float64),
        "dof_pos": torch.zeros(2, 1),
        "des_dof_pos": torch.zeros(2, 1),
    }
    path = tmp_path / "data.pt"
    torch.save(data, path)
    loaded = contracts().load_reference_data(path, cfg, 0.01)
    optimizer = load_module("pace_zero_optimizer", "src/pace_sim2real/optim/cma_es.py")
    opt = optimizer.CMAESOptimizer(
        torch.zeros(5, 2), 2, str(tmp_path), ["leg"], 3, loaded, "cpu", epsilon=0.01, reference_settings={"dt": 0.01}
    )
    with pytest.raises(RuntimeError):
        opt.get_best_sim_params()
    with pytest.raises(ValueError, match="complete"):
        opt.evolve()
    for _ in range(2):
        opt.tell(torch.zeros(2, 1), torch.zeros(2, 1))
    opt.evolve()
    assert opt.finished() and opt.stop_reason == "relative_spread"
    assert opt.best_result["velocity_rmse"] is None
    assert opt.best_result["score"] == 0
    opt.close()


def test_optimizer_partial_failure_does_not_replace_completed_best(tmp_path):
    optimizer = load_module("pace_partial_optimizer", "src/pace_sim2real/optim/cma_es.py")
    data = {
        "time": torch.tensor([0.0, 0.01], dtype=torch.float64),
        "dof_pos": torch.zeros(2, 1),
        "des_dof_pos": torch.zeros(2, 1),
    }
    opt = optimizer.CMAESOptimizer(
        torch.zeros(5, 2), 2, str(tmp_path), ["leg"], 3, data, "cpu", reference_settings={"dt": 0.01}
    )
    for _ in range(2):
        opt.tell(torch.ones(2, 1), torch.zeros(2, 1))
    opt.evolve()
    previous = (opt.log_dir / "best_result.pt").read_bytes()
    opt.tell(torch.zeros(2, 1), torch.zeros(2, 1))
    with pytest.raises(ValueError, match="Nonfinite"):
        opt.tell(torch.full((2, 1), float("nan")), torch.zeros(2, 1))
    opt.close()
    # Re-serialization need not have byte-identical ZIP metadata; the evaluated record must remain identical.
    saved = torch.load(opt.log_dir / "best_result.pt", weights_only=True)
    assert previous and saved["score"] == 1 and saved["generation"] == 0


def test_plot_loader_rejects_unpaired_legacy_and_tampered_errors(tmp_path):
    plotter = load_module("pace_invalid_plot", "scripts/pace/plot_trajectory.py")
    path = tmp_path / "mean.pt"
    torch.save(torch.zeros(5), path)
    with pytest.raises(ValueError, match="pair"):
        plotter.load_result(path)


@pytest.mark.parametrize("drive_joints", [[], [[0]], [[0, 1], [1]]])
def test_optimizer_rejects_missing_or_duplicate_drives_before_writes(tmp_path, drive_joints):
    optimizer = load_module("pace_coverage_optimizer", "src/pace_sim2real/optim/cma_es.py")
    data = {
        "time": torch.tensor([0.0, 0.01], dtype=torch.float64),
        "dof_pos": torch.zeros(2, 1),
        "des_dof_pos": torch.zeros(2, 1),
        "dof_vel": torch.zeros(2, 1),
        "des_dof_vel": torch.zeros(2, 1),
    }
    opt = optimizer.CMAESOptimizer(
        torch.zeros(8, 2),
        2,
        str(tmp_path),
        ["leg", "wheel"],
        1,
        data,
        "cpu",
        leg_order=["leg"],
        wheel_order=["wheel"],
        reference_settings={"dt": 0.01},
    )
    # No writer methods: reaching a write instead of rejecting the mapping fails this test.
    robot = SimpleNamespace(
        num_joints=2,
        actuators={
            str(index): SimpleNamespace(
                joint_indices=ids,
                cfg=SimpleNamespace(delay_mode="command", max_delay=10),
                update_encoder_bias=lambda value: None,
                update_time_lags=lambda value: None,
            )
            for index, ids in enumerate(drive_joints)
        },
    )
    with pytest.raises(ValueError, match="exactly one PACE actuator"):
        opt.update_simulator(robot, [0, 1], torch.zeros(2, 1), initial_wheel_velocity=torch.zeros(2, 1))


def test_newton_config_warns_and_removes_ratio_variables():
    import os
    import subprocess

    script = """
import warnings
from types import SimpleNamespace
import torch
from pace_sim2real.tasks.pace.pace_sim2real_env_cfg import PaceCfg, PaceSim2realEnvCfg, NewtonCfg
for legs, wheels in [(12, 0), (12, 4)]:
    count = legs + wheels
    size = 3 * count + legs + 1
    cfg = PaceCfg()
    cfg.leg_order = [f"leg{i}" for i in range(legs)]
    cfg.wheel_order = [f"wheel{i}" for i in range(wheels)]
    cfg.joint_order = cfg.leg_order + cfg.wheel_order
    cfg.bounds_params = torch.arange(size * 2, dtype=torch.float32).reshape(size, 2)
    original = cfg.bounds_params.clone()
    cfg.separate_dynamic_friction = True
    cfg.apply_friction_ratio()
    assert cfg.bounds_params.shape == (size + count, 2)
    env_cfg = SimpleNamespace(sim=SimpleNamespace(physics=NewtonCfg()), sim2real=cfg)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        PaceSim2realEnvCfg.validate_config(env_cfg)
        assert len(caught) == 1 and "removing friction ratio" in str(caught[0].message)
        PaceSim2realEnvCfg.validate_config(env_cfg)
        assert len(caught) == 1
    assert not cfg.separate_dynamic_friction
    torch.testing.assert_close(cfg.bounds_params, original)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=dict(os.environ, OMNI_KIT_ACCEPT_EULA="YES"),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_collection_records_seconds_and_rejects_invalid_runs():
    """Exercise the collector against a deterministic environment boundary in isolation."""
    import os
    import subprocess

    script = """
import importlib.util
from types import SimpleNamespace as NS
import torch
from pace_sim2real.utils import trajectory_simulation as collection
for fault in (None, "nonfinite_sample", "nonfinite_final", "termination", "time_reset", "closed"):
    position_type = type("JointPositionAction", (), {"__module__": "isaaclab.envs.mdp.actions.joint_actions"})
    velocity_type = type("JointVelocityAction", (), {"__module__": "isaaclab.envs.mdp.actions.joint_actions"})
    pos, vel = position_type(), velocity_type()
    for term, name in ((pos, "leg"), (vel, "wheel")):
        term._joint_names, term.action_dim, term.cfg = [name], 1, NS(asset_name="robot")
    robot = NS(num_joints=2, joint_names=["wheel", "leg"], data=NS(
        joint_pos=NS(torch=torch.tensor([[8., 10.], [8., 10.]])),
        joint_vel=NS(torch=torch.tensor([[20., 30.], [20., 30.]]))))
    env = NS(num_envs=2, device="cpu", step_dt=.01, physics_dt=.005, _sim_step_counter=0,
             cfg=NS(sim2real=NS(leg_order=["leg"], wheel_order=["wheel"]), sim=NS(use_newton_actuators=False)),
             scene={"robot": robot},
             action_manager=NS(active_terms=["v", "p"], get_term=lambda name: {"v": vel, "p": pos}[name]))
    env.sim = NS(is_running=lambda: not (fault == "closed" and env._sim_step_counter == 2))
    commands = []
    def step(actions):
        commands.append(actions.clone())
        env._sim_step_counter += 2
        robot.data.joint_pos.torch.fill_(10 + len(commands))
        robot.data.joint_vel.torch.fill_(20 + 2 * len(commands))
        if fault == "nonfinite_sample" and len(commands) == 1:
            robot.data.joint_pos.torch[1, 0] = float("nan")
        if fault == "nonfinite_final" and len(commands) == 3:
            robot.data.joint_vel.torch[1, 1] = float("nan")
        if fault == "time_reset": env._sim_step_counter = 0
        done = torch.tensor([fault == "termination", False])
        return None, None, done, torch.zeros(2, dtype=torch.bool), None
    env.step = step
    try:
        data = collection.collect_trajectory(env, torch.tensor([[1.], [2.], [3.]]),
                                              torch.tensor([[4.], [5.], [6.]]), torch.full((2, 1), .25))
    except RuntimeError:
        assert fault is not None
        if fault == "termination": assert len(commands) == 1
    else:
        assert fault is None
        torch.testing.assert_close(data["time"], torch.tensor([0., .01, .02], dtype=torch.float64))
        torch.testing.assert_close(data["dof_pos"], torch.tensor([[9.75], [10.75], [11.75]]))
        torch.testing.assert_close(data["dof_vel"], torch.tensor([[20.], [22.], [24.]]))
        torch.testing.assert_close(commands[0], torch.tensor([[4., 1.], [4., 1.]]))
        assert set(data) == {"time", "dof_pos", "des_dof_pos", "dof_vel", "des_dof_vel"}
        assert all(value.device.type == "cpu" for value in data.values())
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=dict(os.environ, OMNI_KIT_ACCEPT_EULA="YES"),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_fixed_collection_parameters_follow_backend_friction_model():
    import subprocess

    script = """
import warnings
from types import SimpleNamespace as NS
from isaaclab_newton.physics import NewtonCfg
from isaaclab_physx.physics import PhysxCfg
from pace_sim2real.utils.fit_replay import JointParameters
from pace_sim2real.utils.trajectory_simulation import _dynamic_friction

params = JointParameters.collection_defaults(1, 1)
cfg = NS(physics=PhysxCfg())
env = NS(unwrapped=NS(sim=NS(cfg=cfg)))
assert _dynamic_friction(env, params) is params.dynamic_friction
assert params.dynamic_friction.equal(0.5 * params.friction)
cfg.physics = NewtonCfg()
with warnings.catch_warnings(record=True) as emitted:
    warnings.simplefilter("always")
    assert _dynamic_friction(env, params) is None
assert any("single" in str(item.message) or "dry-friction" in str(item.message) for item in emitted)
"""
    subprocess.run([sys.executable, "-c", script], cwd=ROOT, check=True, timeout=60)


def test_collection_and_fit_parse_without_importing_isaac_sim():
    import os
    import subprocess

    script = """
import importlib.util
import sys
class RejectIsaacSim:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "isaacsim" or fullname.startswith("isaacsim."):
            raise AssertionError("CLI parsing imported Isaac Sim")
sys.meta_path.insert(0, RejectIsaacSim())
for name in ("data_collection", "replay", "fit"):
    spec = importlib.util.spec_from_file_location(name, f"scripts/pace/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_external_tasks()
    for extra, expected in (([], "NewtonCfg"), (["physics=isaacsim_physx", "--visualizer", "kit"], "PhysxCfg")):
        args = module._parse_args(["--task", "Isaac-Pace-Anymal-D-v0", *extra])
        cfg, _ = module.resolve_task_config(args.task, "")
        assert type(cfg.sim.physics).__name__ == expected
    args = module._parse_args(["--task", "Isaac-Pace-Anymal-D-v0", "--device", "cpu",
                               "--kit_args", "--ext-folder=/tmp/extensions"])
    assert args.device == "cpu" and args.device_explicit
    assert args.kit_args == "--ext-folder=/tmp/extensions"
assert "isaaclab_physx.app.kit_launcher" not in sys.modules
"""
    environment = dict(os.environ)
    environment.pop("OMNI_KIT_ACCEPT_EULA", None)
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, env=environment, capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_optimizer_accepts_batched_rollouts_with_the_same_group_objective(tmp_path):
    optimizer = load_module("pace_batched_optimizer", "src/pace_sim2real/optim/cma_es.py")
    data = {
        "time": torch.tensor([0.0, 0.01], dtype=torch.float64),
        "dof_pos": torch.zeros(2, 1),
        "des_dof_pos": torch.zeros(2, 1),
        "dof_vel": torch.zeros(2, 1),
        "des_dof_vel": torch.zeros(2, 1),
    }
    bounds = torch.zeros(8, 2)
    bounds[6] = 0.1
    opt = optimizer.CMAESOptimizer(
        bounds,
        2,
        str(tmp_path),
        ["leg", "wheel"],
        2,
        data,
        "cpu",
        leg_order=["leg"],
        wheel_order=["wheel"],
        velocity_error_scale=2.0,
        reference_settings={"dt": 0.01},
    )
    q = torch.tensor([[[1.1], [3.1]], [[2.1], [4.1]]])
    v = torch.tensor([[[2.0], [4.0]], [[4.0], [6.0]]])
    opt.tell(q, torch.zeros_like(q), sim_dof_vel=v, real_dof_vel=torch.zeros_like(v))
    opt.evolve()
    result = torch.load(opt.log_dir / "best_result.pt", weights_only=True)
    assert result["score"] == pytest.approx(3.75)
    assert result["position_rmse"] == pytest.approx(5**0.5)
    assert result["velocity_rmse"] == pytest.approx(10**0.5)
    torch.testing.assert_close(result["sim_dof_pos"], torch.tensor([[1.0], [3.0]]))
    assert result["candidate_index"] == 0
    q[1, -1] = float("nan")
    with pytest.raises(ValueError, match="Nonfinite"):
        opt.tell(q, torch.zeros_like(q), sim_dof_vel=v, real_dof_vel=torch.zeros_like(v))
    assert opt.scores_counter == 0
    opt.close()
    assert torch.load(opt.log_dir / "best_result.pt", weights_only=True)["score"] == result["score"]


def test_batched_fitting_rejects_invalid_rollouts_before_evolution(tmp_path):
    import os
    import subprocess

    script = """
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import torch
from pace_sim2real.optim import CMAESOptimizer
spec = importlib.util.spec_from_file_location("fit", "scripts/pace/fit.py")
fit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fit)
for fault in (None, "decimation", "transient", "final", "termination", "clock"):
    action_type = type("JointPositionAction", (), {"__module__": "isaaclab.envs.mdp.actions.joint_actions"})
    action = action_type()
    action._joint_names, action.action_dim, action.cfg = ["leg"], 1, NS(asset_name="robot")
    q, v = torch.zeros(2, 1), torch.zeros(2, 1)
    drive = NS(joint_indices=slice(None), cfg=NS(delay_mode="command", max_delay=0),
               update_encoder_bias=lambda value: None, update_time_lags=lambda value: None, reset=lambda ids: None)
    robot = NS(num_joints=1, joint_names=["leg"], actuators={"leg": drive}, data=NS(
        joint_pos=NS(torch=q), joint_vel=NS(torch=v),
        default_joint_pos=NS(torch=torch.zeros_like(q)), default_joint_vel=NS(torch=torch.zeros_like(v))))
    robot.write_joint_armature_to_sim_index = lambda **kwargs: None
    robot.write_joint_friction_coefficient_to_sim_index = lambda **kwargs: None
    robot.write_joint_position_to_sim_index = lambda position, **kwargs: q.copy_(position)
    robot.write_joint_velocity_to_sim_index = lambda velocity, **kwargs: v.copy_(velocity)
    env = NS(device="cpu", num_envs=2, step_dt=.01, physics_dt=.01, _sim_step_counter=0,
        cfg=NS(decimation=2 if fault == "decimation" else 1, sim2real=NS(leg_order=["leg"], wheel_order=[]),
               sim=NS(dt=.01, use_newton_actuators=False)),
        scene={"robot": robot}, sim=NS(is_running=lambda: True),
        action_manager=NS(active_terms=["leg"], get_term=lambda name: action))
    def reset():
        env._sim_step_counter = 0
        q.zero_(); v.zero_()
    def step(actions):
        env._sim_step_counter += 1
        q.fill_(env._sim_step_counter)
        if (fault == "transient" and env._sim_step_counter == 1) or (fault == "final" and env._sim_step_counter == 2):
            q[1, 0] = float("nan")
        if fault == "clock": env._sim_step_counter = 0
        return None, None, torch.tensor([fault == "termination", False]), torch.zeros(2, dtype=torch.bool), None
    env.reset, env.step = reset, step
    data = {"time": torch.tensor([0., .01], dtype=torch.float64),
            "dof_pos": torch.zeros(2, 1), "des_dof_pos": torch.zeros(2, 1)}
    opt = CMAESOptimizer(torch.zeros(5, 2), 2, sys.argv[1], ["leg"], 1, data, "cpu", reference_settings={"dt": .01})
    try:
        fit.fit_reference(env, data, opt)
    except (ValueError, RuntimeError) as error:
        if fault == "decimation": assert "decimation=1" in str(error) and env._sim_step_counter == 0
        assert fault is not None
        assert opt.iteration_counter == 0 and opt.best_result is None
        assert not (opt.log_dir / "best_result.pt").exists()
        if fault == "termination": assert env._sim_step_counter == 1
    else:
        assert fault is None
        assert opt.best_result["score"] == .5
        torch.testing.assert_close(opt.best_result["sim_dof_pos"], torch.tensor([[0.], [1.]]))
    finally:
        opt.close()
"""
    environment = dict(os.environ)
    environment.pop("OMNI_KIT_ACCEPT_EULA", None)
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def paired_plot_record():
    """A complete one-leg record with independently known MSE=5."""
    return {
        "schema_version": 2,
        "leg_order": ["leg"],
        "wheel_order": [],
        "time": torch.tensor([0.0, 0.01], dtype=torch.float64),
        "reference": {"dof_pos": torch.zeros(2, 1), "des_dof_pos": torch.ones(2, 1)},
        "sim_dof_pos": torch.tensor([[1.0], [3.0]]),
        "params": torch.zeros(5),
        "parameter_names": ["armature:leg", "damping:leg", "friction:leg", "encoder_bias:leg", "delay"],
        "generation": 2,
        "candidate_index": 0,
        "delay_steps": 0,
        "delay_seconds": 0.0,
        "score": 5.0,
        "position_rmse": 5**0.5,
        "velocity_rmse": None,
        "settings": {
            "position_error_scale": 1.0,
            "position_weight": 1.0,
            "velocity_error_scale": 1.0,
            "velocity_weight": 1.0,
        },
    }


def test_plot_cli_uses_current_task_directory_and_skips_incomplete_runs(tmp_path, monkeypatch, capsys):
    plotter = load_module("pace_task_plot", "scripts/pace/plot_trajectory.py")
    monkeypatch.setenv("PACE_ROOT", str(tmp_path))
    task_root = tmp_path / "logs" / "pace-sim2real" / "Isaac-Pace-Anymal-D-v0"
    completed = task_root / "completed"
    completed.mkdir(parents=True)
    torch.save(paired_plot_record(), completed / "best_result.pt")
    (task_root / "incomplete").mkdir()
    assert plotter.main([]) == 0
    output = capsys.readouterr().out
    assert "generation=2" in output
    assert "score" in output


@pytest.mark.parametrize(
    "mutation", ["missing_desired", "nonfinite_time", "reversed_time", "missing_identity", "wrong_score"]
)
def test_plot_loader_reports_invalid_paired_records(tmp_path, mutation):
    plotter = load_module("pace_checked_plot", "scripts/pace/plot_trajectory.py")
    result = paired_plot_record()
    if mutation == "missing_desired":
        del result["reference"]["des_dof_pos"]
    elif mutation == "nonfinite_time":
        result["time"][1] = float("nan")
    elif mutation == "reversed_time":
        result["time"] = result["time"].flip(0)
    elif mutation == "missing_identity":
        del result["candidate_index"]
    elif mutation == "wrong_score":
        result["score"] = 4.0
    path = tmp_path / "best_result.pt"
    torch.save(result, path)
    with pytest.raises(ValueError):
        plotter.load_result(path)


def test_plot_cli_supports_task_namespace_legacy_run_and_score_curve(tmp_path, monkeypatch, capsys):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plotter = load_module("pace_legacy_run_plot", "scripts/pace/plot_trajectory.py")
    monkeypatch.setenv("PACE_ROOT", str(tmp_path))
    task = "Isaac-Pace-Anymal-D-v0"
    (tmp_path / "logs" / "pace-sim2real" / task).mkdir(parents=True)
    run = tmp_path / "logs" / "pace" / task / "saved"
    run.mkdir(parents=True)
    torch.save(paired_plot_record(), run / "best_result.pt")
    torch.save({"scores_buffer": torch.tensor([[9.0, 7.0], [5.0, 6.0]])}, run / "progress.pt")
    monkeypatch.setattr(plt, "show", lambda: None)
    try:
        assert (
            plotter.main(["--task", "namespace:" + task, "--folder_name", "saved", "--plot_trajectory", "--plot_score"])
            == 0
        )
        figures = [plt.figure(number) for number in plt.get_fignums()]
        assert len(figures) == 2
        torch.testing.assert_close(torch.tensor(figures[0].axes[0].lines[2].get_ydata()), torch.tensor([1.0, 3.0]))
        torch.testing.assert_close(torch.tensor(figures[1].axes[0].lines[0].get_ydata()), torch.tensor([7.0, 5.0]))
        assert plotter.main(["--robot_name", task, "--folder_name", "saved"]) == 0
        assert "generation=2" in capsys.readouterr().out
        with pytest.raises(SystemExit) as error:
            plotter.main(["--task", task, "--robot_name", task])
        assert error.value.code == 2
    finally:
        plt.close("all")


def test_plot_mean_diagnostics_do_not_require_or_invent_paired_response(tmp_path, monkeypatch, capsys):
    plotter = load_module("pace_mean_plot", "scripts/pace/plot_trajectory.py")
    monkeypatch.setenv("PACE_ROOT", str(tmp_path))
    run = tmp_path / "logs" / "pace-sim2real" / "Isaac-Pace-Anymal-D-v0" / "mean-only"
    run.mkdir(parents=True)
    torch.save(torch.tensor([0.1, 0.2]), run / "mean_000.pt")
    assert plotter.main(["--mean_name", "mean_000.pt"]) == 0
    assert "not an evaluated response" in capsys.readouterr().out
    with pytest.raises(SystemExit) as error:
        plotter.main(["--mean_name", "mean_000.pt", "--plot_trajectory"])
    assert error.value.code == 2


@pytest.mark.parametrize(
    "recorded, expected",
    [
        ((None, None), (("hip", "calf"), ("w1", "w2"))),
        (([], None), ((), ("w1", "w2"))),
        ((None, []), (("hip", "calf"), ())),
        ((["calf"], ["w2", "w1"]), (("calf",), ("w2", "w1"))),
        (([], ["w2"]), ((), ("w2",))),
    ],
)
def test_subset_selection_projects_each_parameter_block(tmp_path, recorded, expected):
    module = contracts()
    cfg = SimpleNamespace(
        leg_order=["hip", "calf"],
        wheel_order=["w1", "w2"],
        reference_leg_order=recorded[0],
        reference_wheel_order=recorded[1],
        separate_dynamic_friction=True,
        bounds_params=torch.arange(38).reshape(19, 2),
        cmaes=SimpleNamespace(position_error_scale=[11, 12], velocity_error_scale=[21, 22]),
    )
    assert module.reference_groups(cfg) == expected
    legs, wheels = expected
    bounds, pscale, vscale = module.selected_fit_config(cfg, legs, wheels)
    lookup = {"hip": 0, "calf": 1, "w1": 2, "w2": 3}
    selected = [lookup[n] for n in legs + wheels]
    row_ids = [offset + i for offset in (0, 4, 8) for i in selected] + [12 + lookup[n] for n in legs] + [14]
    row_ids += [15 + i for i in selected]
    torch.testing.assert_close(bounds, cfg.bounds_params[row_ids])
    assert pscale == [11 + lookup[n] for n in legs]
    assert vscale == [19 + lookup[n] for n in wheels]
    data = {"time": torch.tensor([0.0, 0.01])}
    for suffix, names in (("pos", legs), ("vel", wheels)):
        if names:
            data["dof_" + suffix] = data["des_dof_" + suffix] = torch.rand(2, len(names))
    path = tmp_path / "ref.pt"
    torch.save(data, path)
    loaded = module.load_reference_data(path, cfg, 0.01)
    for k in data.keys() - {"time"}:
        torch.testing.assert_close(loaded[k], data[k])


@pytest.mark.parametrize("legs,wheels", [([], []), (["w"], []), (["p", "p"], []), ([], ["unknown"])])
def test_invalid_recorded_groups(legs, wheels):
    cfg = SimpleNamespace(leg_order=["p"], wheel_order=["w"], reference_leg_order=legs, reference_wheel_order=wheels)
    with pytest.raises(ValueError):
        contracts().reference_groups(cfg)


def test_velocity_only_objective_and_diagnostics(tmp_path):
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    optimizer = load_module("velocity_subset_optimizer", "src/pace_sim2real/optim/cma_es.py")
    plot = load_module("velocity_subset_plot", "scripts/pace/plot_trajectory.py")
    data = {"time": torch.tensor([0.0, 0.01]), "dof_vel": torch.zeros(2, 1), "des_dof_vel": torch.ones(2, 1)}
    settings = dict(
        dt=0.01,
        task_leg_order=["p"],
        task_wheel_order=["w"],
        hold_positions={"p": 0.4},
        hold_velocities={},
        delay_actuator_groups={"drive": ["p", "w"]},
    )
    opt = optimizer.CMAESOptimizer(
        torch.zeros(4, 2),
        2,
        str(tmp_path),
        ["w"],
        1,
        data,
        "cpu",
        leg_order=[],
        wheel_order=["w"],
        reference_settings=settings,
        velocity_error_scale=[2.0],
        velocity_weight=3.0,
    )
    v = torch.tensor([[[2.0], [4.0]], [[6.0], [8.0]]])
    opt.tell(None, None, sim_dof_vel=v, real_dof_vel=torch.zeros_like(v))
    opt.evolve()
    opt.close()
    best = plot.load_result(opt.log_dir / "best_result.pt")
    assert best["schema_version"] == 3 and best["position_rmse"] is None and "sim_dof_pos" not in best
    assert best["parameter_names"] == ["armature:w", "damping:w", "friction:w", "delay"]
    assert best["score"] == pytest.approx(2.5)
    assert best["velocity_rmse"] == pytest.approx(10**0.5)
    tags = EventAccumulator(str(opt.log_dir)).Reload().Tags()["scalars"]
    assert "error/position_rmse_rad" not in tags and "error/velocity_rmse_rad_s" in tags
    assert not any(tag.startswith("4_Bias/") for tag in tags)


def test_subset_keeps_default_mechanics_and_restores_each_drive(monkeypatch):
    from unittest.mock import Mock

    module = contracts()
    monkeypatch.setitem(sys.modules, "drive_test.collection_contracts", module)
    subset = load_module("drive_test.subset_control", "src/pace_sim2real/utils/subset_control.py")
    monkeypatch.setattr(subset, "resolve_action_mapping", lambda *_: {"leg_ids": [0, 2], "wheel_ids": [1, 3]})
    names = ["p1", "w1", "p2", "w2"]
    robot = Mock(num_joints=4, joint_names=names)
    robot.data.default_joint_pos.torch = torch.tensor([[1.0, 2.0, 3.0, 4.0]]).repeat(2, 1)
    robot.data.default_joint_vel.torch = torch.tensor([[5.0, 6.0, 7.0, 8.0]]).repeat(2, 1)
    robot.actuators = {}
    for side, indices in (("A", [1, 0]), ("B", [2, 3])):
        drive = Mock(joint_indices=indices, encoder_bias=torch.tensor([[0.1, 0.25]]).repeat(2, 1))
        drive.cfg = SimpleNamespace(delay_mode="command", max_delay=4)
        robot.actuators[side] = drive
    cfg = SimpleNamespace(leg_order=["p1", "p2"], wheel_order=["w1", "w2"], reference_delay_mode="command")
    control = subset.SubsetControl(
        SimpleNamespace(scene={"robot": robot}, cfg=SimpleNamespace(sim2real=cfg), device="cpu", num_envs=2), [], ["w1"]
    )
    pos, vel = control.targets(torch.empty(3, 0), torch.tensor([[10.0], [11.0], [12.0]]))
    torch.testing.assert_close(pos, torch.tensor([[0.75, 2.9]]).repeat(3, 1))
    torch.testing.assert_close(vel, torch.tensor([[10.0, 8.0], [11.0, 8.0], [12.0, 8.0]]))
    assert control.settings()["delay_actuator_groups"] == {"A": ["w1", "p1"]}
    for candidate in (1, 3):
        values = torch.full((2, 1), float(candidate))
        delay = torch.tensor([candidate, candidate + 1])
        control.apply(values, values, values, None, torch.empty(2, 0), delay, torch.empty(2, 0), values)
        a, b = robot.actuators.values()
        torch.testing.assert_close(a.update_time_lags.call_args.args[0], delay)
        torch.testing.assert_close(a.update_encoder_bias.call_args.args[0], torch.tensor([[0.0, 0.25]]).repeat(2, 1))
        b.update_time_lags.assert_not_called()
        b.update_encoder_bias.assert_not_called()
        for writer in (robot.write_joint_armature_to_sim_index, robot.write_joint_friction_coefficient_to_sim_index):
            assert writer.call_args.kwargs["joint_ids"].tolist() == [1]
        q = robot.write_joint_position_to_sim_index.call_args.kwargs
        v = robot.write_joint_velocity_to_sim_index.call_args.kwargs
        assert q["joint_ids"].tolist() == [0, 2, 1, 3]
        torch.testing.assert_close(q["position"], torch.tensor([[1.0, 3.0, 2.0, 4.0]]).repeat(2, 1))
        torch.testing.assert_close(v["velocity"], torch.tensor([[0.0, 0.0, float(candidate), 8.0]]).repeat(2, 1))

    # Collection uses the drive's actual delay mode. Its fixed delay applies
    # to every member of a participating drive even when only one leg is swept.
    replay = load_module("collection_parameter_defaults", "src/pace_sim2real/utils/fit_replay.py")
    params = replay.JointParameters.collection_defaults(1, 0)
    env = SimpleNamespace(scene={"robot": robot}, cfg=SimpleNamespace(sim2real=cfg), device="cpu", num_envs=2)
    a, b = robot.actuators.values()
    a.cfg.delay_mode = "effort"
    control = subset.SubsetControl(env, ["p1"], [], check_delay_mode=False)
    with pytest.raises(ValueError, match="capacity"):
        control.check_delay(params.delay_steps)
    a.cfg.max_delay = 5
    control.check_delay(params.delay_steps)
    delay = torch.full((2,), params.delay_steps)
    control.apply(
        params.armature.expand(2, 1),
        params.damping.expand(2, 1),
        params.friction.expand(2, 1),
        params.dynamic_friction.expand(2, 1),
        params.bias.expand(2, 1),
        delay,
        torch.tensor([0.5]),
        None,
    )
    torch.testing.assert_close(a.update_time_lags.call_args.args[0], torch.tensor([5, 5]))
    b.update_time_lags.assert_not_called()
    torch.testing.assert_close(a.update_encoder_bias.call_args.args[0], torch.tensor([[0.1, 0.05]]).repeat(2, 1))
    mechanics = robot.write_joint_friction_coefficient_to_sim_index.call_args.kwargs
    assert mechanics["joint_ids"].tolist() == [0]
    torch.testing.assert_close(mechanics["joint_dynamic_friction_coeff"], torch.full((2, 1), 0.025))
    torch.testing.assert_close(
        robot.write_joint_velocity_to_sim_index.call_args.kwargs["velocity"],
        torch.tensor([[5.0, 0.0, 6.0, 8.0]]).repeat(2, 1),
    )
    torch.testing.assert_close(
        robot.write_joint_position_to_sim_index.call_args.kwargs["position"],
        torch.tensor([[0.55, 3.0, 2.0, 4.0]]).repeat(2, 1),
    )
