# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Package containing asset and sensor configurations."""

import importlib.metadata
import os
from pathlib import Path

from isaaclab.utils.module import lazy_export

CUSTOM_ROBOTS_ASSETS_DIR = Path(__file__).resolve().parent / "data"

lazy_export()
