"""CPU regressions for the local Isaac Lab API migration."""

import ast
import dataclasses
import tempfile
from pathlib import Path
from unittest.mock import patch

import gymnasium as gym
import pytest
import torch

from isaaclab.actuators import DCMotor
from isaaclab.utils.types import ArticulationActions

from isaaclab_tasks.utils import resolve_task_config

import pace_sim2real.tasks  # noqa: F401
from pace_sim2real import PaceSim2realSceneCfg
from pace_sim2real.tasks.manager_based.pace.anymal_pace_env_cfg import AnymalDPaceEnvCfg, ANYmalDPaceSceneCfg
from pace_sim2real.utils import PaceDCMotor, PaceDCMotorCfg


def motor_case(mode, lag):
    cfg = PaceDCMotorCfg(
        joint_names_expr=[".*"],
        saturation_effort=140.0,
        actuator_effort_limit=1000.0,
        actuator_velocity_limit=8.5,
        stiffness=85.0,
        damping=0.6,
        encoder_bias=0.0,
        max_delay=lag,
        delay_mode=mode,
    )
    motor = PaceDCMotor(cfg, ["A", "B"], slice(0, 2), 2, "cpu")
    # Different lags per environment exercise per-environment lag state.
    motor.update_time_lags(torch.tensor([lag, 0]))
    seen, got = [], []

    def controller(self, action, joint_pos, joint_vel):
        seen.append(
            (
                action.joint_positions.clone(),
                action.joint_velocities.clone(),
                action.joint_efforts.clone(),
                joint_pos.clone(),
                joint_vel.clone(),
            )
        )
        return ArticulationActions(joint_efforts=torch.full((2, 2), 100.0 + len(seen)))

    motor.update_encoder_bias(torch.tensor([[0.1, -0.05], [0.1, -0.05]]))
    with patch.object(DCMotor, "compute", controller):
        for n in range(7):
            action = ArticulationActions(
                joint_positions=torch.full((2, 2), 1.0 + n),
                joint_velocities=torch.full((2, 2), 20.0 + 2 * n),
                joint_efforts=torch.full((2, 2), 70.0 + 3 * n),
            )
            got.append(
                motor.compute(action, torch.tensor([[0.4, -0.2]]).repeat(2, 1), torch.ones(2, 2)).joint_efforts.clone()
            )
    for n in range(7):
        for env in range(2):
            delayed = max(0, n - (lag if env == 0 else 0))
            cmd_n = delayed if mode == "command" else n
            for channel, target in enumerate((1.0 + cmd_n, 20.0 + 2 * cmd_n, 70.0 + 3 * cmd_n)):
                assert torch.equal(seen[n][channel][env], torch.full((2,), target))
            out_n = delayed if mode == "effort" else n
            assert torch.equal(got[n][env], torch.full((2,), 101.0 + out_n))
            assert torch.allclose(seen[n][3][env], torch.tensor([0.3, -0.15]))
    return True


@pytest.mark.parametrize("mode", ["command", "effort"])
@pytest.mark.parametrize("lag", [0, 3])
def test_motor_channels_bias_and_per_environment_delays(mode, lag):
    assert motor_case(mode, lag)


def test_template_isolation_and_environment_defaults():
    robot = ANYmalDPaceSceneCfg().robot
    a, b = PaceSim2realSceneCfg(robot=robot), PaceSim2realSceneCfg(robot=robot)
    original_path = robot.prim_path
    a.robot.prim_path = "/World/Mutation"
    assert b.robot.prim_path == robot.prim_path == original_path
    for copied in (a.copy(), a.replace()):
        copied.robot.prim_path = "/World/CopyMutation"
        assert a.robot.prim_path == "/World/Mutation"
    assert isinstance(PaceSim2realSceneCfg().robot, type(dataclasses.MISSING))
    cfg = AnymalDPaceEnvCfg()
    assert (cfg.sim.dt, cfg.decimation) == (0.0025, 1)
    assert len(cfg.sim2real.joint_order) == 12
    assert cfg.sim2real.bounds_params.shape == (61, 2)
    assert cfg.observations.policy.concatenate_terms is False
    assert cfg.sim.use_newton_actuators is False
    assert cfg.scene.robot.spawn.fix_root_link is True
    assert "Template-Pace-Sim2real-v0" in gym.registry


@pytest.mark.parametrize("script", ["train.py", "play.py"])
def test_rl_entrypoint_adapts_observations_locally(script):
    # Execute the actual entrypoint's config-resolution prefix without launching Kit.
    from types import SimpleNamespace

    from rsl_rl.models import MLPModel
    from tensordict import TensorDict

    path = Path(__file__).resolve().parents[1] / "scripts/rsl_rl" / script
    main = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == "main")
    prefix = ast.Module(body=main.body[:3], type_ignores=[])
    from isaaclab.envs import ManagerBasedRLEnvCfg

    scope = dict(
        resolve_task_config=resolve_task_config,
        ManagerBasedRLEnvCfg=ManagerBasedRLEnvCfg,
        args_cli=SimpleNamespace(task="Isaac-Pace-Anymal-D-v0", agent="rsl_rl_cfg_entry_point"),
        hydra_args=[],
    )
    exec(compile(prefix, str(path), "exec"), scope)
    cfg, agent = scope["env_cfg"], scope["agent_cfg"]
    assert cfg.observations.policy.concatenate_terms is True
    assert AnymalDPaceEnvCfg().observations.policy.concatenate_terms is False
    obs = TensorDict({"policy": torch.zeros(1, 36)}, batch_size=[1])
    model = MLPModel(obs, agent.obs_groups, "actor", 12, hidden_dims=agent.actor.hidden_dims)
    assert model(obs).shape == (1, 12)


def actuator_defaults_and_invalid():
    cfg = PaceDCMotorCfg(
        joint_names_expr=[".*"],
        saturation_effort=140.0,
        actuator_effort_limit=1000.0,
        actuator_velocity_limit=8.5,
        stiffness=0.0,
        damping=0.0,
    )
    assert (cfg.encoder_bias, cfg.max_delay, cfg.delay_mode) == (0.0, 0, "command")
    cfg.delay_mode = "invalid"
    try:
        PaceDCMotor(cfg, ["A", "B"], slice(0, 2), 1, "cpu")
    except ValueError as exc:
        assert "command" in str(exc) and "effort" in str(exc)
        return True
    return False


def test_actuator_defaults_and_invalid_delay():
    assert actuator_defaults_and_invalid()


def friction_case():
    from pace_sim2real import CMAESOptimizer

    for low, high in ((0.0, 1.0), (-0.1, 1.0), (0.0, 1.2)):
        bounds = torch.zeros(11, 2)
        bounds[:9, 1] = 1.0
        bounds[9:, 0], bounds[9:, 1] = low, high
        data = {"time": torch.zeros(4), "dof_pos": torch.zeros(4, 2), "des_dof_pos": torch.zeros(4, 2)}
        with tempfile.TemporaryDirectory(prefix="pace_review_friction_") as tmp:
            try:
                opt = CMAESOptimizer(
                    bounds=bounds,
                    population_size=4,
                    log_dir=tmp,
                    joint_order=["A", "B"],
                    max_iteration=1,
                    data=data,
                    device="cpu",
                    separate_dynamic_friction=True,
                )
            except ValueError as exc:
                assert low < 0 or high > 1
                assert "0 <= lower <= upper <= 1" in str(exc)
                continue
            try:
                assert (low, high) == (0.0, 1.0)
                opt.sim_params[:, opt.friction_idx] = torch.tensor([0.2, 0.4])
                opt.sim_params[:, opt.friction_ratio_idx] = torch.tensor([0.25, 0.5])
                expected = torch.tensor([[0.05, 0.2]]).repeat(4, 1)
                assert torch.allclose(opt.dynamic_friction(), expected)
                assert (opt.dynamic_friction() <= opt.sim_params[:, opt.friction_idx]).all()
            finally:
                opt.close()
    return True


def test_friction_formula_and_bounds():
    assert friction_case()
