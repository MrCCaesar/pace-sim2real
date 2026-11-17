# © 2025 ETH Zurich, Robotic Systems Lab
# Author: Filip Bjelonic
# Licensed under the Apache License 2.0

from typing import Any, cast

import torch
from isaaclab.assets import ArticulationCfg
from isaaclab.utils import configclass

from pace_sim2real import PaceCfg, PaceSim2realEnvCfg, PaceSim2realSceneCfg
from pace_sim2real.assets.assets import SEVNCE_X5_CFG
from pace_sim2real.utils import PaceDCMotorCfg

from . import mdp

SEVNCE_PACE_ACTUATOR_CFG = PaceDCMotorCfg(
    joint_names_expr=[".*_hip_joint", ".*_thigh_joint", ".*_calf_joint", ".*_foot_joint"],
    saturation_effort={".*_hip_joint": 350.0, ".*_thigh_joint": 300.0, ".*_calf_joint": 300.0, ".*_foot_joint": 45.0},
    actuator_effort_limit={
        ".*_hip_joint": 300.0,
        ".*_thigh_joint": 250.0,
        ".*_calf_joint": 250.0,
        ".*_foot_joint": 30.0,
    },
    actuator_velocity_limit={".*_hip_joint": 6.0, ".*_thigh_joint": 6.0, ".*_calf_joint": 8.0, ".*_foot_joint": 30.0},
    stiffness={".*_hip_joint": 1500.0, ".*_thigh_joint": 1500.0, ".*_calf_joint": 1500.0, ".*_foot_joint": 0.0},
    # P gain in Nm/rad
    damping={".*_hip_joint": 30.0, ".*_thigh_joint": 30.0, ".*_calf_joint": 30.0, ".*_foot_joint": 20.0},
    # D gain in Nm s/rad
    encoder_bias=0.0,  # encoder bias in radians
    # note: modeling coulomb friction if friction = dynamic_friction
    # > in newer Isaac Sim versions, friction is renamed to static_friction
    friction=0.0,  # static friction coefficient (Nm)
    dynamic_friction=0.0,  # dynamic friction coefficient (Nm)
    viscous_friction=0.0,  # viscous friction coefficient (Nm s/rad)
    max_delay=10,  # max delay in simulation steps
)


@configclass
class SevnceX5PaceActionCfg:
    """Action configuration for Sevnce X5 robot in Pace Sim2Real environment."""

    joint_pos = mdp.JointPositionActionCfg(
        asset_name="robot",
        joint_names=[".*_hip_joint", ".*_thigh_joint", ".*_calf_joint"],
        scale=1.0,
        use_default_offset=False,
        preserve_order=True,
    )  # actions = absolute joint position targets
    wheel_vel = mdp.JointVelocityActionCfg(
        asset_name="robot",
        joint_names=[".*_foot_joint"],
        scale=1.0,
        use_default_offset=False,
        preserve_order=True,
    )  # actions = absolute wheel velocity targets


@configclass
class SevnceX5PaceCfg(PaceCfg):
    """Pace configuration for Anymal-D robot."""

    robot_name: str = "sevnce_x5_sim"
    data_dir: str = "sevnce_x5_sim/chirp_data.pt"  # located in pace_sim2real/data/anymal_d_sim/chirp_data.pt
    bounds_params: torch.Tensor = torch.zeros((61, 2))  # 3 * 16 + 12 leg biases + shared delay
    separate_dynamic_friction: bool = False  # appends 16 dynamic/static friction ratios
    leg_order: list[str] = [
        "FL_hip_joint",
        "FL_thigh_joint",
        "FL_calf_joint",
        "FR_hip_joint",
        "FR_thigh_joint",
        "FR_calf_joint",
        "RL_hip_joint",
        "RL_thigh_joint",
        "RL_calf_joint",
        "RR_hip_joint",
        "RR_thigh_joint",
        "RR_calf_joint",
    ]
    wheel_order: list[str] = ["FL_foot_joint", "FR_foot_joint", "RL_foot_joint", "RR_foot_joint"]
    joint_order: list[str] = leg_order + wheel_order  # order of joints in the robot model

    def __post_init__(self):
        # set bounds for parameters
        self.bounds_params[:16, 0] = 1e-5
        self.bounds_params[:16, 1] = 1.0  # armature between 1e-5 - 1.0 [kgm2]
        self.bounds_params[16:32, 1] = 7.0  # dof_damping between 0.0 - 7.0 [Nm s/rad]
        self.bounds_params[32:48, 1] = 0.5  # friction between 0.0 - 0.5
        self.bounds_params[48:60, 0] = -0.1
        self.bounds_params[48:60, 1] = 0.1  # bias between -0.1 - 0.1 [rad]
        self.bounds_params[60, 1] = 10.0  # delay between 0.0 - 10.0 [sim steps]


@configclass
class SevnceX5PaceSceneCfg(PaceSim2realSceneCfg):
    """Configuration for Sevnce X5 robot in Pace Sim2Real environment."""

    robot: ArticulationCfg = cast(Any, SEVNCE_X5_CFG).replace(
        prim_path="{ENV_REGEX_NS}/Robot",
        init_state=cast(Any, SEVNCE_X5_CFG.init_state).replace(pos=(0.0, 0.0, 1.0)),
        actuators={"joints": SEVNCE_PACE_ACTUATOR_CFG},
    )
    cast(Any, robot.spawn).fix_root_link = True


@configclass
class SevnceX5PaceEnvCfg(PaceSim2realEnvCfg):
    scene: SevnceX5PaceSceneCfg = SevnceX5PaceSceneCfg(num_envs=4096, env_spacing=2.5)
    actions: SevnceX5PaceActionCfg = SevnceX5PaceActionCfg()
    sim2real: PaceCfg = SevnceX5PaceCfg()

    def __post_init__(self):
        # post init of parent
        super().__post_init__()

        # robot sim and control settings
        self.sim.dt = 0.0025  # 400Hz simulation
        self.decimation = 1  # 400Hz control
