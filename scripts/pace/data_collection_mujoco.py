# SPDX-License-Identifier: Apache-2.0

"""Collect X5 position/velocity chirps using native MuJoCo."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import replace
from pathlib import Path

from mujoco_collection import collect, load_config, plot_data, save_data


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=str, default="Isaac-Pace-Sevnce-X5-v0")
    parser.add_argument("--config", type=Path, default=root / "config/x5_collection.toml")
    parser.add_argument("--min_frequency", type=float)
    parser.add_argument("--max_frequency", type=float)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--plot", action="store_true", default=None)
    viewer = parser.add_mutually_exclusive_group()
    viewer.add_argument("--visualize", action="store_true", default=None)
    viewer.add_argument("--no-visualize", dest="visualize", action="store_false")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        overrides = {
            name: getattr(args, name)
            for name in ("min_frequency", "max_frequency", "duration", "plot", "visualize")
            if getattr(args, name) is not None
        }
        config = replace(config, **overrides)
        data = collect(config)
        output_root = Path(os.environ.get("PACE_ROOT", str(root))).expanduser().resolve()
        output = (
            output_root / "data" / args.task / "mujoco_chirp_data.pt"
            if args.task
            else output_root / "data" / "mujoco_chirp_data.pt"
        )
        save_data(data, output)
        print(f"Saved {len(data.time)} samples to {output}")
        if config.plot:
            plot_data(data, config.position_joints, config.velocity_joints)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Collection failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Collection interrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
