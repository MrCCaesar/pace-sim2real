# See LICENSE and NOTICE.
"""Independent Issue 22 acceptance cases. All mutations are confined to temporary projects."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
results = []


def check(case, project, expected, evidence=()):
    run = subprocess.run(
        [str(ROOT / ".venv/bin/isaaclab-task-lint"), "--root", str(project)],
        capture_output=True,
        text=True,
    )
    output = (run.stdout + run.stderr).strip()
    results.append({
        "case": case,
        "expected_exit": expected,
        "actual_exit": run.returncode,
        "required_text": evidence,
        "output": output,
        "passed": run.returncode == expected and all(item in output for item in evidence),
    })


def synthetic(project):
    (project / "pyproject.toml").write_text('[project]\nname = "walk"\n')
    src = project / "src"
    task = src / "walk/tasks/gait"
    mdp = task / "mdp"
    terrain = src / "walk_isaaclabs/terrains"
    for directory in (mdp, terrain):
        directory.mkdir(parents=True)
    (mdp / "rewards.py").write_text(
        "from isaaclab.managers import ManagerTermBase\n"
        "class Tracking(ManagerTermBase):\n    def __call__(self, env): return env.value\n"
    )
    (mdp / "__init__.py").write_text("from .rewards import Tracking\n")
    cfg = task / "env_cfg.py"
    config = (
        "from isaaclab.envs.mdp import reset_scene_to_default\n"
        "from isaaclab.managers import RewardTermCfg as R, EventTermCfg\n"
        "from isaaclab.terrains import TerrainImporterCfg\n"
        "ground = TerrainImporterCfg(terrain_type='plane')\n"
        "event = EventTermCfg(func=reset_scene_to_default, mode='reset')\n"
        "reward = R(func='walk.tasks.gait.mdp:Tracking')\n"
    )
    cfg.write_text(config)
    (terrain / "generator.py").write_text("def surface(difficulty, cfg): return [], [0, 0, 0]\n")
    (terrain / "config.py").write_text(
        "from isaaclab.terrains import SubTerrainBaseCfg\nfrom .generator import surface\n"
        "class Custom(SubTerrainBaseCfg):\n    function = surface\n"
    )
    check("A2/A3 legal generator, stateful reward and official event", project, 0)
    (terrain / "generator.py").rename(task / "wrong.py")
    (terrain / "generator.py").write_text("from walk.tasks.gait.wrong import surface\n")
    check("A2 misplaced generator behind re-export", project, 1, ("ORG002", "wrong.py:1"))
    (task / "wrong.py").replace(terrain / "generator.py")
    cfg.write_text(config + (mdp / "rewards.py").read_text())
    (mdp / "rewards.py").write_text("from ..env_cfg import Tracking\n")
    check("A3 string and two re-exports of misplaced reward", project, 1, ("ORG004", "env_cfg.py"))
    cfg.write_text(config.replace("'walk.tasks.gait.mdp:Tracking'", "resolve_at_runtime()"))
    check("A4 runtime reward binding", project, 1, ("ORG005", "env_cfg.py:6:", "runtime factory"))


def pace_copy(project):
    shutil.copy(ROOT / "pyproject.toml", project)
    for package in ("pace_sim2real", "pace_sim2real_isaaclabs"):
        shutil.copytree(
            ROOT / "src" / package, project / "src" / package, ignore=shutil.ignore_patterns("data", "__pycache__")
        )
    assets = Path("src/pace_sim2real/assets/data")
    (project / assets).symlink_to(ROOT / assets, target_is_directory=True)
    variant = project / "src/pace_sim2real/tasks/pace/config/x5/env_cfg.py"
    original = variant.read_text()
    drive = 'actuators={"joints": SEVNCE_PACE_X5_ACTUATOR_CFG}'
    assert original.count(drive) == 1
    check("A7 shared PACE actuator class in X5 and X3mini", project, 0, ("registrations=4",))
    # Move only the implementation and register its new path. The expected config tree still exists.
    legacy = project / "src/pace_sim2real/tasks/manager_based/pace"
    legacy.mkdir(parents=True)
    moved = legacy / "env_cfg.py"
    variant.rename(moved)
    registration = variant.parent / "__init__.py"
    before = registration.read_text()
    registration.write_text(before.replace('f"{__name__}.env_cfg:', '"pace_sim2real.tasks.manager_based.pace.env_cfg:'))
    check(
        "A1 config directory remains but registered definition moved",
        project,
        1,
        ("ORG001", "tasks/manager_based/pace/env_cfg.py"),
    )
    moved.rename(variant)
    registration.write_text(before)
    variant.write_text(original.replace(drive, 'actuators={"joints": missing_drive_factory()}'))
    check(
        "A7/A8 unresolved X5 actuator in asset replacement",
        project,
        1,
        ("ORG005", "config/x5/env_cfg.py:", "missing_drive_factory"),
    )
    variant.write_text(
        original.replace(drive, 'actuators={"joints": UnclassifiedDrive()}').replace(
            "SEVNCE_PACE_X5_ACTUATOR_CFG =", "class UnclassifiedDrive:\n    pass\n\nSEVNCE_PACE_X5_ACTUATOR_CFG ="
        )
    )
    check("A8 resolvable component without ownership rule in same slot", project, 1, ("ORG008", "UnclassifiedDrive"))


if __name__ == "__main__":
    for exercise in (synthetic, pace_copy):
        with TemporaryDirectory() as workspace:
            exercise(Path(workspace))
    print(json.dumps(results, indent=2))
    sys.exit(int(any(not result["passed"] for result in results)))
