# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Configuration for Sevnce robots.

The following configurations are available:

* :obj:`SEVNCE_X3MINI_DIFFDRIVE_CFG`: Sevnce X3Mini differential-drive configuration
* :obj:`SEVNCE_X5_DIFFDRIVE_CFG`: Sevnce X5 differential-drive configuration
"""

import isaaclab.sim as sim_utils
from isaaclab.actuators import IdealPDActuatorCfg, ImplicitActuatorCfg
from isaaclab.assets.articulation import ArticulationCfg
from isaaclab_newton.sim.schemas import NewtonArticulationCfg
from isaaclab_physx.sim.schemas import PhysxArticulationCfg, PhysxRigidBodyCfg
from X3Chatter.assets import CUSTOM_ROBOTS_ASSETS_DIR

HEALTHCARE_S3 = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/Healthcare/0.5.0/132c82d"

##
# Configuration - Actuators.
##


##
# Configuration
##


SEVNCE_X3MINI_DIFFDRIVE_CFG = ArticulationCfg(
    spawn=sim_utils.UsdFileCfg(
        usd_path=f"{CUSTOM_ROBOTS_ASSETS_DIR}/robots/sevnce/x3mini/usd/x3mini.usd",
        activate_contact_sensors=True,
        rigid_props=PhysxRigidBodyCfg(
            disable_gravity=False,
            retain_accelerations=False,
            linear_damping=0.0,
            angular_damping=0.0,
            max_linear_velocity=1000.0,
            max_angular_velocity=1000.0,
            max_depenetration_velocity=1.0,
        ),
        articulation_props=[
            PhysxArticulationCfg(
                enabled_self_collisions=False, solver_position_iteration_count=4, solver_velocity_iteration_count=1
            ),
            NewtonArticulationCfg(self_collision_enabled=False),
        ],
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 0.29),
        joint_pos={
            ".*HAA": 0.0,
            "[L,R]F_HFE": 1.46,
            "[L,R]H_HFE": -1.46,
            "[L,R]F_KFE": -2.51,
            "[L,R]H_KFE": 2.51,
            ".*_WHEEL": 0.0,
        },
        joint_vel={".*": 0.0},
    ),
    actuators={
        "legs": IdealPDActuatorCfg(
            joint_names_expr=[".*_HAA", ".*_HFE", ".*_KFE"],
            actuator_effort_limit={".*_HAA": 171.0, ".*_HFE": 171.0, ".*_KFE": 255.0},
            actuator_velocity_limit={".*_HAA": 5.1, ".*_HFE": 5.1, ".*_KFE": 6.8},
            joint_effort_limit={".*_HAA": 180.0, ".*_HFE": 180.0, ".*_KFE": 260.0},
            joint_velocity_limit={".*_HAA": 6.0, ".*_HFE": 6.0, ".*_KFE": 8.0},
            stiffness=1200.0,
            damping=10.0,
            friction=0.0,
            armature=0.0,
        ),
        # Integrate wheel velocity feedback inside the solver. Explicit Kd=20
        # feedback at 5 ms overshoots these low-inertia wheels and oscillates.
        "wheels": ImplicitActuatorCfg(
            joint_names_expr=[".*_WHEEL"],
            actuator_effort_limit={".*_WHEEL": 30.0},
            actuator_velocity_limit={".*_WHEEL": 25.5},
            joint_effort_limit={".*_WHEEL": 30.0},
            joint_velocity_limit={".*_WHEEL": 30.0},
            stiffness=0.0,
            damping=20.0,
            friction=0.0,
            armature=0.0,
        ),
    },
)

"""Sevnce X3mini with explicit leg PD and solver-integrated wheel velocity drives."""

SEVNCE_X5_CFG = ArticulationCfg(
    spawn=sim_utils.UsdFileCfg(
        usd_path=f"{CUSTOM_ROBOTS_ASSETS_DIR}/robots/sevnce/x5/usd/x5.usd",
        activate_contact_sensors=True,
        rigid_props=PhysxRigidBodyCfg(
            disable_gravity=False,
            retain_accelerations=False,
            linear_damping=0.0,
            angular_damping=0.0,
            max_linear_velocity=1000.0,
            max_angular_velocity=1000.0,
            max_depenetration_velocity=1.0,
        ),
        articulation_props=[
            PhysxArticulationCfg(
                enabled_self_collisions=False, solver_position_iteration_count=4, solver_velocity_iteration_count=1
            ),
            NewtonArticulationCfg(self_collision_enabled=False),
        ],
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 0.35),
        joint_pos={
            ".*_hip_joint": 0.0,
            ".*_thigh_joint": 1.14,
            ".*_calf_joint": -2.32,
            ".*_foot_joint": 0.0,
        },
        joint_vel={".*": 0.0},
    ),
    actuators={
        "legs": IdealPDActuatorCfg(
            joint_names_expr=[".*_hip_joint", ".*_thigh_joint", ".*_calf_joint"],
            actuator_effort_limit={".*_hip_joint": 300.0, ".*_thigh_joint": 250.0, ".*_calf_joint": 250.0},
            actuator_velocity_limit={".*_hip_joint": 5.1, ".*_thigh_joint": 5.1, ".*_calf_joint": 6.8},
            joint_effort_limit={".*_hip_joint": 300.0, ".*_thigh_joint": 250.0, ".*_calf_joint": 250.0},
            joint_velocity_limit={".*_hip_joint": 6.0, ".*_thigh_joint": 6.0, ".*_calf_joint": 8.0},
            stiffness=1500.0,
            damping=30.0,
            friction=0.0,
            armature=0.0,
        ),
        # Integrate wheel velocity feedback inside the solver. Explicit Kd=20
        # feedback at 5 ms overshoots these low-inertia wheels and oscillates.
        "wheels": ImplicitActuatorCfg(
            joint_names_expr=[".*_foot_joint"],
            actuator_effort_limit={".*_foot_joint": 30.0},
            actuator_velocity_limit={".*_foot_joint": 25.5},
            joint_effort_limit={".*_foot_joint": 30.0},
            joint_velocity_limit={".*_foot_joint": 30.0},
            stiffness=0.0,
            damping=20.0,
            friction=0.0,
            armature=0.0,
        ),
    },
)

"""Sevnce X5 with explicit leg PD and solver-integrated wheel velocity drives."""
