"""One approved load/reset attempt. Verify cgroup limits BEFORE runtime imports."""
import json
from pathlib import Path
import time
import traceback

out = Path(__file__).with_name('bounded_reset_result.json')
result = {'completed': False, 'explicit_env_steps': 0, 'events': []}
start = time.monotonic()

def mark(stage):
    result['events'].append({'stage': stage, 'elapsed_s': time.monotonic()-start})
    out.write_text(json.dumps(result, indent=2)+'\n')
    print('PROBE_STAGE', stage, flush=True)

try:
    mark('preflight')
    group = next(line.split(':', 2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines()
                 if line.startswith('0::'))
    cg = Path('/sys/fs/cgroup')/group.lstrip('/')
    limits = {name: (cg/name).read_text().strip() for name in ['memory.max','memory.swap.max','cpu.max']}
    result.update(cgroup=group, limits=limits)
    assert int(limits['memory.max']) == 8*1024**3, limits
    assert limits['memory.swap.max'] == '0', limits
    quota, period = map(int, limits['cpu.max'].split())
    assert quota/period <= 2, limits
    mark('limits_verified_runtime_imports_begin')
    from isaaclab.app import launch_simulation
    from isaaclab.envs import ManagerBasedRLEnv
    from pace_sim2real.tasks.manager_based.pace.anymal_pace_env_cfg import AnymalDPaceEnvCfg
    cfg = AnymalDPaceEnvCfg()
    cfg.scene.num_envs = 1
    cfg.scene.ground = None
    cfg.scene.sky_light = None
    cfg.scene.robot.spawn.fix_root_link = False
    for prop in cfg.scene.robot.spawn.articulation_props:
        if hasattr(prop, 'enabled_self_collisions'):
            prop.enabled_self_collisions = False
    cfg.seed = 42
    mark('config_ready')
    with launch_simulation(cfg, {'physics':'newton_mjwarp','headless':True,'device':'cuda:0'}):
        mark('environment_construction_begin')
        env = ManagerBasedRLEnv(cfg=cfg)
        try:
            mark('environment_constructed')
            env.reset()
            robot = env.scene['robot']
            result.update(floating_base=not robot.is_fixed_base, num_envs=env.num_envs,
                          actuator_types={k:type(v).__name__ for k,v in robot.actuators.items()})
            mark('reset_complete')
        finally:
            env.close()
            mark('environment_closed')
    result['completed'] = True
    mark('success')
except BaseException:
    result['error'] = traceback.format_exc()
    mark('failed')
    raise
