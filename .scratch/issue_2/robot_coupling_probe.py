"""Research-only synthetic suspension probe. No production interfaces.

Massless hook: force balance on a 2 m sphere, backward-difference velocity.
Synthetic unilateral Kelvin-Voigt trial law, k=10000 N/m, c=100 Ns/m.
This is an experimental constitutive law, not calibrated nylon data.
"""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--dt', type=float, default=.0025)
parser.add_argument('--settle', type=float, default=10)
parser.add_argument('--excite', type=float, default=2)
parser.add_argument('--observe', type=float, default=60)
parser.add_argument('--amplitude', type=float, default=.1)
parser.add_argument('--tag', default='pilot')
parser.add_argument('--max-steps', type=int, required=True)
args = parser.parse_args()
out = Path(__file__).parent
assert args.dt > 0 and min(args.settle, args.excite, args.observe) >= 0
planned_steps = round((args.settle+args.excite+args.observe)/args.dt)
assert 0 < planned_steps <= args.max_steps <= 20
group = next(line.split(':',2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines()
             if line.startswith('0::'))
cg = Path('/sys/fs/cgroup')/group.lstrip('/')
limits = {name:(cg/name).read_text().strip() for name in ['memory.max','memory.swap.max','cpu.max']}
assert int(limits['memory.max']) == 8*1024**3 and limits['memory.swap.max'] == '0'
quota, period = map(int,limits['cpu.max'].split())
assert quota/period <= 2
print('LIMITS_VERIFIED', json.dumps(limits), flush=True)
import numpy as np
from scipy.optimize import root
from scipy.spatial.transform import Rotation
import torch
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
cfg.sim.dt = args.dt
cfg.decimation = 1
cfg.seed = 42

def arr(proxy):
    return proxy.torch.detach().cpu().numpy().copy()

with launch_simulation(cfg, {'physics': 'newton_mjwarp', 'headless': True, 'device': 'cuda:0'}):
    env = ManagerBasedRLEnv(cfg=cfg)
    rows = []
    try:
        env.reset()
        robot = env.scene['robot']
        base = robot.body_names.index('base')
        mass = arr(robot.data.body_mass)[0]
        com = np.sum(arr(robot.data.body_com_pos_w)[0] * mass[:, None], axis=0) / mass.sum()
        pos = arr(robot.data.body_link_pos_w)[0, base]
        quat = arr(robot.data.body_link_quat_w)[0, base]
        rot = Rotation.from_quat(quat[[1, 2, 3, 0]])
        # Synthetic attachment rectangle centered above the initial total COM.
        mounts = np.array([[-.3,-.18,.2],[-.3,.18,.2],[.3,-.18,.2],[.3,.18,.2]])
        mounts[:, :2] += rot.inv().apply(com-pos)[:2]
        points = pos+rot.apply(mounts)
        hook = np.array([com[0], com[1], points[:, 2].mean()+1])
        anchor = hook+np.array([0,0,2])
        distance = np.linalg.norm(hook-points, axis=1)
        uz = (hook[2]-points[:,2])/distance
        lengths = distance-mass.sum()*9.81/(4*uz*10000)
        previous = hook.copy()
        reaction = mass.sum()*9.81
        target = robot.data.default_joint_pos.torch.clone()
        joint = robot.joint_names.index('LF_HFE')
        total = args.settle+args.excite+args.observe
        metadata = dict(synthetic=True, args=vars(args), backend='newton_mjwarp',
                        mass_kg=float(mass.sum()), mounts_body_m=mounts.tolist(),
                        anchor_world_m=anchor.tolist(), free_lengths_m=lengths.tolist(),
                        actuator_types={k:type(v).__name__ for k,v in robot.actuators.items()},
                        joint_names=robot.joint_names, floating_base=not robot.is_fixed_base,
                        cgroup=group, limits=limits, completed_steps=0,
                        initial_state_note='Default joint pose, gravity-balanced synthetic ropes; no settling performed',
                        columns=['time_s','base_xyz[3]','base_quaternion_wxyz[4]',
                                 'base_com_velocity_world[6]','tensions_N[4]','hook_xyz[3]',
                                 'scaled_balance_residual_norm','joint_positions_rad[12]','targets_rad[12]'])
        assert not robot.is_fixed_base
        for step in range(round(total/args.dt)):
            time = step*args.dt
            pos = arr(robot.data.body_link_pos_w)[0,base]
            quat = arr(robot.data.body_link_quat_w)[0,base]
            rot = Rotation.from_quat(quat[[1,2,3,0]])
            points = pos+rot.apply(mounts)
            velocity = arr(robot.data.body_com_vel_w)[0,base]
            base_com = arr(robot.data.body_com_pos_w)[0,base]
            pv = velocity[:3]+np.cross(velocity[3:], points-base_com)

            def evaluate(y):
                h = y[:3]
                delta = points-h
                dist = np.linalg.norm(delta, axis=1)
                directions = delta/dist[:,None]
                rate = np.sum(directions*(pv-(h-previous)/args.dt),axis=1)
                extension = dist-lengths
                tension = np.where(extension>0, np.maximum(10000*extension+100*rate,0),0)
                force = tension[:,None]*directions
                balance = force.sum(axis=0)+y[3]*(anchor-h)/2
                residual = np.r_[balance/metadata['mass_kg']/9.81, (np.linalg.norm(h-anchor)-2)]
                return residual,tension,force

            sol = root(lambda y:evaluate(y)[0], np.r_[previous,reaction], tol=1e-9)
            residual,tension,force_on_hook = evaluate(sol.x)
            if not np.isfinite(np.r_[sol.x,residual,tension]).all():
                raise RuntimeError('nonfinite hook solve')
            if np.max(tension)<1e-8:
                raise RuntimeError('all_slack_invalid')
            if np.linalg.norm(residual)>1e-6 or sol.x[3]<0:
                raise RuntimeError(f'hook balance invalid: {residual}, reaction={sol.x[3]}')
            previous,reaction = sol.x[:3].copy(),float(sol.x[3])
            wrench = robot.instantaneous_wrench_composer
            wrench.reset()
            for i in range(4):
                wrench.add_forces_and_torques_index(
                    forces=torch.tensor(-force_on_hook[i],device=env.device,dtype=torch.float32).reshape(1,1,3),
                    positions=torch.tensor(points[i],device=env.device,dtype=torch.float32).reshape(1,1,3),
                    body_ids=[base],is_global=True)
            action = target.clone()
            phase = time-args.settle
            if 0<=phase<args.excite:
                action[0,joint] += args.amplitude*np.sin(2*np.pi*phase)*np.sin(np.pi*phase/args.excite)**2
            rows.append(np.r_[time,pos,quat,velocity,tension,previous,np.linalg.norm(residual),
                              arr(robot.data.joint_pos)[0],action[0].cpu().numpy()])
            obs,reward,terminated,truncated,info = env.step(action)
            metadata['completed_steps'] += 1
            if bool(terminated.any() or truncated.any()):
                raise RuntimeError('unexpected environment reset')
            if not np.isfinite(rows[-1]).all():
                raise RuntimeError('nonfinite state')
            if not np.isfinite(arr(robot.data.body_link_pos_w)).all() or not np.isfinite(arr(robot.data.body_com_vel_w)).all():
                raise RuntimeError('nonfinite post-step state')
            if step % 2000 == 0:
                print(f'PROGRESS t={time:.3f} tension={tension.tolist()}',flush=True)
        metadata.update(completed=True, simulated_duration_s=metadata['completed_steps']*args.dt,
                        final_base_position_m=arr(robot.data.body_link_pos_w)[0,base].tolist(),
                        final_base_com_velocity=arr(robot.data.body_com_vel_w)[0,base].tolist(),
                        final_joint_positions_rad=arr(robot.data.joint_pos)[0].tolist())
    except Exception as exc:
        metadata = locals().get('metadata', {'args':vars(args)})
        metadata.update(completed=False,error=repr(exc))
        raise
    finally:
        np.save(out/f'robot_{args.tag}_timeseries.npy',np.array(rows))
        (out/f'robot_{args.tag}_summary.json').write_text(json.dumps(metadata,indent=2)+'\n')
        env.close()
