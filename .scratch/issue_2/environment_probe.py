"""Research environment/configuration probe; does not start a simulation."""
import json
import sys
import traceback
from pathlib import Path

result = {"python": sys.executable}
try:
    import torch
    from pace_sim2real.tasks.manager_based.pace.anymal_pace_env_cfg import AnymalDPaceEnvCfg

    cfg = AnymalDPaceEnvCfg()
    result.update(config_constructed=True, cuda_available=torch.cuda.is_available(),
                  fix_root_link=cfg.scene.robot.spawn.fix_root_link,
                  dt=cfg.sim.dt, decimation=cfg.decimation)
except Exception:
    result.update(config_constructed=False, traceback=traceback.format_exc())
Path(__file__).with_name("project_environment_probe_results.json").write_text(json.dumps(result, indent=2)+"\n")
print(json.dumps(result, indent=2))
if not result["config_constructed"]:
    raise SystemExit(1)
