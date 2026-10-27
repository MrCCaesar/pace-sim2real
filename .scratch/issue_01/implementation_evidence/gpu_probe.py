"""One reset/step on each public task, with schema-neutral finite checks."""
import argparse
import json
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
app = AppLauncher(parser.parse_args([])).app
import torch
import gymnasium as gym
import pace_sim2real
import pace_sim2real.tasks
from pace_sim2real.tasks.manager_based.pace.anymal_pace_env_cfg import AnymalDPaceEnvCfg

def finite(value):
    if isinstance(value, dict):
        return all(finite(v) for v in value.values())
    return bool(torch.isfinite(value).all())

results = []
try:
    for task in ("Isaac-Pace-Anymal-D-v0", "Template-Pace-Sim2real-v0"):
        cfg = AnymalDPaceEnvCfg()
        cfg.scene.num_envs = 1
        cfg.seed = 42
        env = gym.make(task, cfg=cfg)
        try:
            obs, _ = env.reset()
            assert finite(obs)
            action = torch.zeros(env.action_space.shape, device=env.unwrapped.device)
            step = env.step(action)
            assert len(step) == 5 and finite(step[0]) and finite(step[1])
            assert action.shape == (1, 12)
            policy = obs["policy"]
            schema = ({k: list(v.shape) for k, v in policy.items()} if isinstance(policy, dict)
                      else list(policy.shape))
            results.append({"task": task, "pass": True, "policy_schema": schema,
                            "action_shape": list(action.shape)})
        finally:
            env.close()
    print("GPU_REVIEW_JSON " + json.dumps({"source": pace_sim2real.__file__, "results": results}), flush=True)
finally:
    app.close()
