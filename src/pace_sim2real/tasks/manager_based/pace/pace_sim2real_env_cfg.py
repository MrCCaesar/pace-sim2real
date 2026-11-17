# © 2025 ETH Zurich, Robotic Systems Lab
# Author: Filip Bjelonic
# Licensed under the Apache License 2.0

# import math
import warnings
from dataclasses import MISSING

import isaaclab.sim as sim_utils
import torch
from isaaclab.assets import AssetBaseCfg
from isaaclab.envs import ManagerBasedRLEnvCfg

# from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import TerminationTermCfg as DoneTerm

# from isaaclab.managers import SceneEntityCfg
from isaaclab.physics import PhysxAutoCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sim import SimulationCfg
from isaaclab.terrains import TerrainImporterCfg
from isaaclab.utils import configclass
from isaaclab.utils.assets import ISAACLAB_NUCLEUS_DIR
from isaaclab.visualizers import VisualizerCfg
from isaaclab_newton.physics import (
    KaminoPADMMSolverCfg,
    MJWarpSolverCfg,
    NewtonCfg,
    NewtonCollisionPipelineCfg,
    NewtonShapeCfg,
)
from isaaclab_ov.physics import OvPhysxCfg
from isaaclab_physx.physics import PhysxCfg
from isaaclab_tasks.utils import PresetCfg

from . import mdp

##
# Physics backend presets
##


@configclass
class PhysicsCfg(PresetCfg):
    """Shared backend presets for locomotion velocity environments."""

    isaacsim_physx = PhysxCfg(gpu_max_rigid_patch_count=10 * 2**15)
    ovphysx = OvPhysxCfg(gpu_max_rigid_patch_count=10 * 2**15)
    physx = PhysxAutoCfg(isaacsim_physx=isaacsim_physx, ovphysx=ovphysx)
    newton_mjwarp = NewtonCfg(
        solver_cfg=MJWarpSolverCfg(
            njmax=1000,
            nconmax=300,
            cone="pyramidal",
            impratio=1.0,
            integrator="implicitfast",
            use_mujoco_contacts=False,
        ),
        collision_cfg=NewtonCollisionPipelineCfg(max_triangle_pairs=2_500_000),
        num_substeps=2,
        debug_mode=False,
        default_shape_cfg=NewtonShapeCfg(margin=0.0, ke=160000.0, kd=1100.0),
    )
    newton_kamino = NewtonCfg(solver_cfg=KaminoPADMMSolverCfg(max_contacts_per_world=64))
    default = newton_mjwarp


##
# Scene definition
##


@configclass
class PaceSim2realSceneCfg(InteractiveSceneCfg):
    """Configuration for the flat scene with a legged robot."""

    # ground plane
    ground = TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="plane",
        collision_group=-1,
        physics_material=sim_utils.PhysxRigidBodyMaterialCfg(
            friction_combine_mode="multiply",
            restitution_combine_mode="multiply",
            static_friction=1.0,
            dynamic_friction=1.0,
        ),
        visual_material=sim_utils.MdlFileCfg(
            mdl_path=f"{ISAACLAB_NUCLEUS_DIR}/Materials/TilesMarbleSpiderWhiteBrickBondHoned/TilesMarbleSpiderWhiteBrickBondHoned.mdl",
            project_uvw=True,
            texture_scale=(0.25, 0.25),
        ),
        debug_vis=False,
    )

    # lights
    sky_light = AssetBaseCfg(
        prim_path="/World/skyLight",
        spawn=sim_utils.DomeLightCfg(
            intensity=750.0,
            texture_file=(
                f"{ISAACLAB_NUCLEUS_DIR}/Materials/Textures/Skies/PolyHaven/kloofendal_43d_clear_puresky_4k.hdr"
            ),
        ),
    )


##
# MDP settings
##


@configclass
class ActionsCfg:
    """Action specifications for the MDP."""

    joint_pos = mdp.JointPositionActionCfg(
        asset_name="robot", joint_names=[".*"], scale=1.0, offset=0.0, clip=None, use_default_offset=False
    )  # actions = absolute joint position targets


@configclass
class ObservationsCfg:
    """Observation specifications for the MDP."""

    @configclass
    class PolicyCfg(ObsGroup):
        """Observations for policy group."""

        joint_pos = ObsTerm(func=mdp.joint_pos_rel)
        joint_vel = ObsTerm(func=mdp.joint_vel_rel)
        actions = ObsTerm(func=mdp.last_action)

        def __post_init__(self):
            self.enable_corruption = False
            self.concatenate_terms = False

    # observation groups
    policy: PolicyCfg = PolicyCfg()


@configclass
class RewardsCfg:
    """Reward terms for the MDP."""

    dof_pos_limits = RewTerm(func=mdp.joint_pos_limits, weight=0.0)


@configclass
class TerminationsCfg:
    """Termination terms for the MDP."""

    time_out = DoneTerm(func=mdp.time_out, time_out=False)


@configclass
class CMAESOptimizerCfg:
    """CMA-ES optimizer configuration."""

    position_error_scale: float = 1.0
    velocity_error_scale: float = 1.0
    position_weight: float = 1.0
    velocity_weight: float = 1.0
    max_iteration: int = 200
    epsilon: float = 1e-2
    sigma: float = 0.5
    save_interval: int = 10
    save_optimization_process: bool = (
        False  # consume more disk space if True, saves optimization process after finishing
    )


@configclass
class PaceCfg:
    """Overall configuration for Pace Sim2Real task."""

    cmaes: CMAESOptimizerCfg = CMAESOptimizerCfg()
    reference_leg_order: list[str] | None = None
    reference_wheel_order: list[str] | None = None
    reference_bias_model: str = "feedback_and_measurement"
    reference_delay_mode: str = "command"
    time_mode: str = "strict"
    legacy_sample_dt: float | None = None

    data_dir: str = MISSING
    joint_order: list = MISSING
    leg_order: list = MISSING
    wheel_order: list | None = None
    bounds_params: torch.Tensor = MISSING

    separate_dynamic_friction: bool = False
    """Identify static and dynamic friction separately. Defaults to False (static = dynamic / coulomb friction).

    The friction parameter is then the static friction, and n ratios r in :attr:`friction_ratio_bounds` are appended
    after all other parameters, with dynamic friction = r * static friction. This keeps dynamic <= static friction for
    every sample.
    """
    friction_ratio_bounds: tuple[float, float] = (0.0, 1.0)
    """Lower and upper bound of the ratio between dynamic and static friction."""

    def apply_friction_ratio(self):
        """Extend the parameter bounds by the dynamic to static friction ratios."""
        if not self.separate_dynamic_friction:
            return
        from pace_sim2real.utils.collection_contracts import resolve_joint_groups

        legs, wheels = resolve_joint_groups(self)
        self.leg_order, self.wheel_order = list(legs), list(wheels)
        self.joint_order = list(legs + wheels)
        num_joints = len(self.joint_order)
        num_params = self.bounds_params.shape[0]
        num_before = 3 * num_joints + len(legs) + 1
        if num_params == num_before:
            ratio_bounds = torch.tensor(self.friction_ratio_bounds, dtype=self.bounds_params.dtype).repeat(
                num_joints, 1
            )
            self.bounds_params = torch.cat([self.bounds_params, ratio_bounds], dim=0)
        elif num_params != num_before + num_joints:
            raise ValueError(
                f"Expected {num_before} or {num_before + num_joints} bounds "
                f"with separate dynamic friction, got {num_params}."
            )

    def undo_friction_ratio(self) -> None:
        """Remove appended friction ratios and disable separate dynamic friction."""
        if not self.separate_dynamic_friction:
            return
        from pace_sim2real.utils.collection_contracts import resolve_joint_groups

        legs, wheels = resolve_joint_groups(self)
        self.leg_order, self.wheel_order = list(legs), list(wheels)
        self.joint_order = list(legs + wheels)
        num_joints = len(self.joint_order)
        num_before = 3 * num_joints + len(legs) + 1
        num_params = self.bounds_params.shape[0]
        if num_params == num_before + num_joints:
            self.bounds_params = self.bounds_params[:num_before].clone()
        elif num_params != num_before:
            raise ValueError(
                f"Expected {num_before} or {num_before + num_joints} bounds "
                f"with separate dynamic friction, got {num_params}."
            )
        self.separate_dynamic_friction = False


##
# Environment configuration
##


@configclass
class PaceSim2realEnvCfg(ManagerBasedRLEnvCfg):
    # Simulation settings
    # PACE's custom delay and encoder bias run in the Python actuator model.
    sim: SimulationCfg = SimulationCfg(physics=PhysicsCfg(), use_newton_actuators=False)
    # Scene settings
    scene: PaceSim2realSceneCfg = PaceSim2realSceneCfg(num_envs=4096, env_spacing=2.5)
    # Basic settings
    actions: ActionsCfg = ActionsCfg()  # action = joint position targets (scale = 1.0 -> impedance control)

    observations: ObservationsCfg = ObservationsCfg()
    rewards: RewardsCfg = RewardsCfg()
    terminations: TerminationsCfg = TerminationsCfg()

    sim2real: PaceCfg = PaceCfg()

    # Post initialization
    def __post_init__(self) -> None:
        """Post initialization."""
        # general settings
        self.decimation = 1
        self.episode_length_s = 99999.0  # long episodes
        # viewer settings
        self.sim.visualizer_cfgs = VisualizerCfg(eye=(4.5, 0.0, 6.0), lookat=(0.0, 0.0, 0.8))
        # simulation settings
        self.sim.dt = 0.0025  # 400Hz simulation
        self.sim.render_interval = 4  # render at 100Hz

        self.sim2real.apply_friction_ratio()

    def validate_config(self) -> None:
        """Adapt friction bounds after the physics preset has been resolved."""
        if isinstance(self.sim.physics, NewtonCfg) and self.sim2real.separate_dynamic_friction:
            warnings.warn(
                "Newton does not support separate dynamic friction identification; "
                "disabling it and removing friction ratio optimization parameters.",
                RuntimeWarning,
                stacklevel=2,
            )
            self.sim2real.undo_friction_ratio()
