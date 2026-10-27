"""Only override max_iteration as permitted by TEST_PLAN I07-T01."""
import runpy
import sys
import os
from isaaclab_tasks import utils

fit = sys.argv[1]
original = utils.parse_env_cfg
def one_iteration(*args, **kwargs):
    cfg = original(*args, **kwargs)
    cfg.sim2real.cmaes.max_iteration = int(os.environ.get("PACE_REVIEW_MAX_ITER", "1"))
    return cfg
utils.parse_env_cfg = one_iteration
sys.argv = [fit, "--headless", "--num_envs", "2", "--task", "Isaac-Pace-Anymal-D-v0", "--device", "cuda:0"]
runpy.run_path(fit, run_name="__main__")
