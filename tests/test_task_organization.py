# See LICENSE and NOTICE.
"""Organization contracts for external Isaac Lab projects (no Isaac dependencies)."""

import shutil
from pathlib import Path

import pytest

from isaaclab_task_lint.__main__ import main


@pytest.fixture
def project(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "walker"\n')
    (tmp_path / "src/walker").mkdir(parents=True)
    return tmp_path


FAMILY = "src/walker/tasks/walk/"
VARIANT = FAMILY + "config/alpha/"
EXT = "src/walker_isaaclabs/"


def write(root, path, source):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source)
    return target


def scan(root, capsys, expected):
    assert main(["--root", str(root)]) == expected
    return capsys.readouterr().out


def test_registration_detects_misplaced_definition_and_deleted_resource(project, capsys):
    write(
        project,
        VARIANT + "__init__.py",
        """
import gymnasium as gym
gym.register(id="Walk", entry_point="isaaclab.envs:ManagerBasedRLEnv", kwargs={
    "env_cfg_entry_point": f"{__name__}.env_cfg:WalkCfg",
    "rl_games_cfg_entry_point": f"{__name__}:agents/trainer.yaml"})
""",
    )
    write(
        project,
        VARIANT + "env_cfg.py",
        "from isaaclab.envs import ManagerBasedRLEnvCfg\nclass WalkCfg(ManagerBasedRLEnvCfg): pass\n",
    )
    resource = write(project, VARIANT + "agents/trainer.yaml", "steps: 10\n")
    assert "registrations=1" in scan(project, capsys, 0)
    resource.unlink()
    assert "missing registered resource" in scan(project, capsys, 1)
    (project / VARIANT / "env_cfg.py").rename(project / "src/walker/wrong.py")
    write(project, VARIANT + "env_cfg.py", "from walker.wrong import WalkCfg\n")
    assert "ORG001" in scan(project, capsys, 1)


def test_mdp_source_and_runtime_resolution(project, capsys):
    cfg = FAMILY + "env_cfg.py"
    decl = "from isaaclab.managers import RewardTermCfg as R\nfrom . import mdp\n"
    write(project, cfg, decl + "reward = R(func=mdp.bonus)\n")
    write(project, FAMILY + "mdp/__init__.py", "from isaaclab.envs.mdp import *\n")
    write(project, FAMILY + "mdp/__init__.pyi", "from .rewards import bonus as bonus\n")
    write(project, FAMILY + "mdp/rewards.py", "def bonus(env): return 1\n")
    scan(project, capsys, 0)
    write(project, FAMILY + "mdp/rewards.py", "from ..env_cfg import bonus\n")
    write(project, cfg, decl + "def bonus(env): return 1\nreward = R(func=mdp.bonus)\n")
    assert "env_cfg.py:3" in scan(project, capsys, 1)
    write(project, cfg, decl + "reward = R(func=factory())\n")
    assert "env_cfg.py:3:" in scan(project, capsys, 1)
    write(project, cfg, decl + "reward = R(func=mdp.missing_reward)\n")
    assert "ORG005" in scan(project, capsys, 1)


@pytest.mark.parametrize(
    ("area", "base", "code"),
    [
        ("managers", "ManagerBase", "ORG003"),
        ("actuators", "DCMotor", "ORG007"),
        ("terrains", "TerrainGenerator", "ORG002"),
        ("sensors", "SensorBase", "ORG007"),
        ("controllers", "DifferentialIKController", "ORG007"),
    ],
)
def test_indirect_framework_extensions(project, capsys, area, base, code):
    write(project, EXT + area + "/device.py", f"from isaaclab.{area} import {base}\nclass Parent({base}): pass\n")
    path = write(
        project,
        EXT + area + "/derived.py",
        f"from walker_isaaclabs.{area}.device import Parent\nclass Child(Parent): pass\n",
    )
    scan(project, capsys, 0)
    path.rename(project / "src/walker/misplaced.py")
    assert code in scan(project, capsys, 1)


def test_unknown_component_vs_unresolved_nested_binding(project, capsys):
    decl = "from isaaclab.scene import InteractiveSceneCfg\nclass Novel: pass\nclass Scene(InteractiveSceneCfg):\n"
    write(project, FAMILY + "scene_cfg.py", decl + "    extra = Novel()\n")
    out = scan(project, capsys, 1)
    assert "ORG008" in out and "missing_rules=1" in out
    write(project, FAMILY + "scene_cfg.py", decl + "    extra = runtime_factory()\n")
    assert "ORG005" in scan(project, capsys, 1)


@pytest.mark.parametrize(("kind", "family"), [("DirectRLEnv", "walk_direct"), ("DirectMARLEnv", "walk_marl_direct")])
def test_direct_workflow_and_legacy_layout(project, capsys, kind, family):
    path = write(
        project,
        f"src/walker/tasks/{family}/config/alpha/env.py",
        f"from isaaclab.envs import {kind}\nclass Walk({kind}):\n    def _get_rewards(self): return 1\n",
    )
    scan(project, capsys, 0)
    for wrong in ("direct/walk", "walk"):
        old = project / f"src/walker/tasks/{wrong}/config/alpha/env.py"
        old.parent.mkdir(parents=True)
        path.rename(old)
        assert "ORG001" in scan(project, capsys, 1)
        old.rename(path)


def test_input_error_and_root_override(project, capsys):
    assert main(["--root", str(project), "--package", "absent"]) == 2
    assert "src/absent" in capsys.readouterr().err
    write(project, FAMILY + "broken.py", "def :\n")
    assert main(["--root", str(project)]) == 2
    assert "broken.py" in capsys.readouterr().err


def test_pinned_precommit_hook_scans_consumer_after_deletion(project, tmp_path, monkeypatch):
    import os
    import subprocess
    import sys

    repo = Path(__file__).resolve().parents[1]
    provider = tmp_path / "provider"
    provider.mkdir()
    for name in ("hooks", "src/isaaclab_task_lint"):
        shutil.copytree(repo / name, provider / name, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(repo / ".pre-commit-hooks.yaml", provider)
    monkeypatch.setenv("PRE_COMMIT_HOME", str(tmp_path / "pre-commit-cache"))
    monkeypatch.delenv("PYTHONPATH", raising=False)
    for key in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    ):
        monkeypatch.delenv(key, raising=False)

    def git(cwd, *args):
        return subprocess.check_output(["git", "-C", str(cwd), *args], text=True).strip()

    git(provider, "init", "-q")
    git(provider, "add", ".")

    def snapshot(directory):
        git(
            directory,
            "-c",
            "user.name=Hook Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgSign=false",
            "commit",
            "-qm",
            "Hook integration fixture",
        )

    snapshot(provider)
    rev = git(provider, "rev-parse", "HEAD")
    # The consumer and provider must have different roots.
    consumer = project / "consumer"
    consumer.mkdir()
    (project / "src").rename(consumer / "src")
    shutil.copy(project / "pyproject.toml", consumer)
    git(consumer, "init", "-q")
    write(
        consumer,
        ".pre-commit-config.yaml",
        f"repos:\n  - repo: {provider.as_uri()}\n    rev: {rev}\n    hooks:\n      - id: isaaclab-task-lint\n",
    )
    config = "from isaaclab.managers import RewardTermCfg as R\nfrom .mdp.rewards import bonus\nx = R(func=bonus)\n"
    write(consumer, FAMILY + "env_cfg.py", config)
    target = write(consumer, FAMILY + "mdp/rewards.py", "def bonus(env): return 1\n")
    git(consumer, "add", ".")
    snapshot(consumer)

    def run(*options):
        return subprocess.run(
            [sys.executable, "-m", "pre_commit", "run", "--verbose", *options],
            cwd=consumer,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )

    result = run("--all-files")
    assert result.returncode == 0, result.stdout + result.stderr
    write(consumer, FAMILY + "env_cfg.py", config.replace("from .mdp.rewards import bonus", "def bonus(env): return 1"))
    result = run("--all-files")
    assert result.returncode == 1 and "ORG004" in result.stdout
    write(consumer, FAMILY + "env_cfg.py", config)
    target.unlink()
    git(consumer, "add", "-u")
    assert git(consumer, "diff", "--cached", "--name-status") == "D\t" + FAMILY + "mdp/rewards.py"
    result = run()
    assert result.returncode == 1 and "ORG005" in result.stdout


def test_local_resources_and_runtime_bindings(project, capsys):
    decl = "from isaaclab.sim import UsdFileCfg\nfrom pathlib import Path\nDATA = Path(__file__).resolve().parent\n"
    write(project, FAMILY + "scene_cfg.py", decl + 'robot = UsdFileCfg(usd_path=f"{DATA}/robot.usd")\n')
    resource = write(project, FAMILY + "robot.usd", "fixture")
    scan(project, capsys, 0)
    resource.unlink()
    assert "missing resource" in scan(project, capsys, 1)


def test_outside_package_target_and_command_string(project, capsys):
    write(project, "plugins/reward.py", "def custom(env): return 1\n")
    write(
        project,
        FAMILY + "env_cfg.py",
        'from isaaclab.managers import RewardTermCfg\nr = RewardTermCfg(func="plugins.reward:custom")\n',
    )
    assert "plugins/reward.py:1" in scan(project, capsys, 1)
    write(project, FAMILY + "env_cfg.py", "")
    write(
        project,
        FAMILY + "mdp/commands/cfg.py",
        "from isaaclab.managers import CommandTermCfg\nclass CmdCfg(CommandTermCfg):\n"
        '    class_type = "{DIR}.implementation:Cmd"\n',
    )
    write(
        project,
        FAMILY + "mdp/commands/implementation.py",
        "from isaaclab.managers import CommandTerm\nclass Cmd(CommandTerm): pass\n",
    )
    scan(project, capsys, 0)


def test_local_alias_and_runtime_override(project, capsys):
    write(project, FAMILY + "mdp/rewards.py", "def bonus(env): return 1\n")
    source = """from isaaclab.managers import RewardTermCfg
def configure(cfg):
    from .mdp.rewards import bonus as local_bonus
    cfg.rewards.score.func = local_bonus
    return RewardTermCfg(func=local_bonus)
"""
    write(project, FAMILY + "env_cfg.py", source)
    scan(project, capsys, 0)
    write(project, FAMILY + "env_cfg.py", source.replace("= local_bonus\n", "= make_reward()\n"))
    assert "runtime factory make_reward" in scan(project, capsys, 1)


def test_missing_project_entry(project, capsys):
    with (project / "pyproject.toml").open("a") as stream:
        stream.write('[project.entry-points."isaaclab.tasks"]\nwalker = "walker.old_tasks"\n')
    assert "pyproject.toml:4:" in scan(project, capsys, 1)


def test_noise_function_and_scene_components_are_checked_by_ownership(project, capsys):
    write(project, EXT + "utils/noise/gain.py", "def calibrated(data, cfg): return data\n")
    src = """from isaaclab.utils.noise import NoiseCfg
from walker_isaaclabs.utils.noise.gain import calibrated
class CalibratedNoise(NoiseCfg):
    func = calibrated
"""
    write(project, EXT + "utils/noise/config.py", src)
    scan(project, capsys, 0)
    wrong = write(project, "src/walker/wrong.py", "def calibrated(data, cfg): return data\n")
    write(project, EXT + "utils/noise/config.py", src.replace("walker_isaaclabs.utils.noise.gain", "walker.wrong"))
    assert "ORG007" in scan(project, capsys, 1)
    wrong.unlink()
    assert "ORG005" in scan(project, capsys, 1)


def test_stub_alone_does_not_prove_an_implementation(project, capsys):
    write(project, FAMILY + "mdp/rewards.pyi", "def bonus(env): ...\n")
    write(
        project,
        FAMILY + "env_cfg.py",
        "from .mdp.rewards import bonus\nfrom isaaclab.managers import RewardTermCfg\nx=RewardTermCfg(func=bonus)\n",
    )
    assert "missing runtime definition" in scan(project, capsys, 1)


def test_ambiguous_exports_report_the_binding(project, capsys):
    for module in ("one", "two"):
        write(project, FAMILY + f"mdp/{module}.py", "def bonus(env): return 1\n")
    write(project, FAMILY + "mdp/__init__.py", "from .one import *\nfrom .two import *\n")
    write(
        project,
        FAMILY + "env_cfg.py",
        "from . import mdp\nfrom isaaclab.managers import RewardTermCfg\nx=RewardTermCfg(func=mdp.bonus)\n",
    )
    out = scan(project, capsys, 1)
    assert "env_cfg.py:3:" in out and "ambiguous exports" in out


@pytest.mark.parametrize(
    ("drive", "code", "counts"),
    [
        ("missing_drive_factory", "ORG005", "violations=0 unresolved=1 missing_rules=0"),
        ("UnclassifiedDrive", "ORG008", "violations=0 unresolved=0 missing_rules=1"),
    ],
)
def test_x5_nested_actuator_replacement(tmp_path, capsys, drive, code, counts):
    repo = Path(__file__).resolve().parents[1]
    shutil.copy(repo / "pyproject.toml", tmp_path)
    for package in ("pace_sim2real", "pace_sim2real_isaaclabs"):
        source = repo / "src" / package
        shutil.copytree(source, tmp_path / "src" / package, ignore=shutil.ignore_patterns("data", "__pycache__"))
    assets = Path("src/pace_sim2real/assets/data")
    (tmp_path / assets).symlink_to(repo / assets, target_is_directory=True)
    path = Path("src/pace_sim2real/tasks/pace/config/x5/env_cfg.py")
    config = tmp_path / path
    source = config.read_text()
    scan(tmp_path, capsys, 0)
    slot = 'actuators={"joints": SEVNCE_PACE_X5_ACTUATOR_CFG}'
    assert source.count(slot) == 1
    source = source.replace(slot, f'actuators={{"joints": {drive}()}}')
    if drive == "UnclassifiedDrive":
        declaration = "SEVNCE_PACE_X5_ACTUATOR_CFG ="
        source = source.replace(declaration, f"class UnclassifiedDrive: pass\n\n{declaration}")
    config.write_text(source)
    row, line = next((i, line) for i, line in enumerate(source.splitlines(), 1) if f"{drive}()" in line)
    output = scan(tmp_path, capsys, 1)
    assert f"{path}:{row}:{line.index(drive) + 1}: {code}" in output
    assert drive in output and counts in output


def test_chained_replacements_and_expanded_keywords(project, capsys):
    src = """from isaaclab.scene import InteractiveSceneCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.actuators import DCMotorCfg
from typing import Any, cast
base = ArticulationCfg()
fields = {"actuators": {"legs": DCMotorCfg()}}
class Scene(InteractiveSceneCfg):
    robot = cast(Any, base).replace(**fields).replace(prim_path=make_path())
"""
    write(project, FAMILY + "scene.py", src)
    scan(project, capsys, 0)
    write(project, FAMILY + "scene.py", src.replace("DCMotorCfg()", "lost_drive()"))
    assert "lost_drive: missing local module or definition" in scan(project, capsys, 1)
    write(project, FAMILY + "scene.py", src.replace("**fields", "**load_fields()"))
    assert "load_fields(): cannot determine expanded component fields" in scan(project, capsys, 1)
