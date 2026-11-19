# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

__all__ = [
    "DEEPROBOTICS_M20_CFG",
    "SEVNCE_X3MINI_CFG",
    "SEVNCE_X5_CFG",
]

# Path to project-owned asset data.
__version__: str

from .robots import DEEPROBOTICS_M20_CFG, SEVNCE_X3MINI_CFG, SEVNCE_X5_CFG
