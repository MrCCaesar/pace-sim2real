# See LICENSE and NOTICE.
"""Default PACE variant."""

from isaaclab.utils import configclass

from ...pace_sim2real_env_cfg import PaceSim2realEnvCfg as BasePaceEnvCfg


@configclass
class PaceSim2realEnvCfg(BasePaceEnvCfg):
    """Template environment with the shared PACE defaults."""
