import os, pathlib, subprocess, tempfile, shutil, json
repo=pathlib.Path(__file__).resolve().parents[3]
python=str(repo/'.venv/bin/python')
reports=repo/'.scratch/issue_01/implementation_evidence'
reports.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='pace_issue01_') as temp:
    root=pathlib.Path(temp)
    shutil.copytree(repo/'scripts',root/'scripts')
    env=dict(os.environ, PYTHONPATH=str(repo/'src'), PACE_ROOT=temp, MPLBACKEND='Agg', MPLCONFIGDIR=str(root/'mpl'), OMNI_KIT_ACCEPT_EULA='YES', PYTHONUNBUFFERED='1')
    def run(name,args):
        with (reports/f'{name}.log').open('w') as log:
            result=subprocess.run([python,*map(str,args)],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        print(name,result.returncode,flush=True)
        assert result.returncode==0, name
    run('environment',[reports/'gpu_probe.py'])
    run('collect',[root/'scripts/pace/data_collection.py','--headless','--num_envs','1','--duration','0.1','--device','cuda:0'])
    run('data_assert',['-c',"import torch;d=torch.load('data/anymal_d_sim/chirp_data.pt');assert {'time','dof_pos','des_dof_pos'}<=d.keys();assert d['dof_pos'].shape==d['des_dof_pos'].shape==(len(d['time']),12);assert all(torch.isfinite(v).all() for v in d.values());print({k:v.shape for k,v in d.items()})"])
    run('fit',[reports/'fit_driver.py',root/'scripts/pace/fit.py'])
    run('fit_assert',['-c',"from pathlib import Path;import torch;r=next(Path('logs/pace/anymal_d_sim').iterdir());c=torch.load(r/'config.pt');assert c['bounds'].shape==(61,2);assert len(c['joint_order'])==12;assert list(r.glob('events.out.tfevents*'));t=torch.load(r/'best_trajectory.pt');assert t.shape[1]==12 and torch.isfinite(t).all();m=torch.load(next(r.glob('mean_*.pt')));assert m.numel()==61 and torch.isfinite(m).all();print(r)"])
    run('plot',[root/'scripts/pace/plot_trajectory.py'])
    run('train',[root/'scripts/rsl_rl/train.py','--headless','--task','Isaac-Pace-Anymal-D-v0','--num_envs','1','--max_iterations','1','--device','cuda:0'])
    checkpoints=list(root.glob('logs/rsl_rl/**/model_*.pt'))
    assert checkpoints
    run('play',[root/'scripts/rsl_rl/play.py','--headless','--task','Isaac-Pace-Anymal-D-v0','--num_envs','1','--checkpoint',checkpoints[0],'--video','--video_length','1','--device','cuda:0'])
    run('play_assert',['-c',"from pathlib import Path;import torch;import imageio.v3 as iio;r=Path('logs/rsl_rl');assert list(r.rglob('events.out.tfevents*'));torch.load(next(r.rglob('model_*.pt')),weights_only=False);torch.jit.load(str(next(r.rglob('exported/policy.pt'))));assert next(r.rglob('policy.onnx')).stat().st_size>0;v=next(r.rglob('*.mp4'));assert sum(1 for _ in iio.imiter(v))==1;print(v)"])
print('ALL GPU SMOKES PASSED; temporary products cleaned',flush=True)
