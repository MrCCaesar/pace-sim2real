"""Static compatibility check: stdlib only; never imports simulation packages."""
import ast
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
import tomllib

repo = Path(__file__).resolve().parents[2]
lab = repo.parent / 'IsaacLab'
project = tomllib.loads((repo/'pyproject.toml').read_text())
upstream = tomllib.loads((lab/'pyproject.toml').read_text())

def pin(config):
    return next(x.rsplit('@', 1)[1] for x in config['tool']['uv']['override-dependencies']
                if x.startswith('newton['))

dist = metadata.distribution('newton')
installed = json.loads(dist.read_text('direct_url.json'))['vcs_info']['commit_id']
lock = tomllib.loads((repo/'uv.lock').read_text())
locked = next(p['source']['git'].rsplit('#', 1)[1] for p in lock['package'] if p['name']=='newton')
builder = Path(dist.locate_file('newton/_src/sim/builder.py'))
tree = ast.parse(builder.read_text())
method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name=='add_usd')
accepted = {a.arg for a in method.args.args+method.args.kwonlyargs}
calls = []
for path in (lab/'source/isaaclab_newton').rglob('*.py'):
    for n in ast.walk(ast.parse(path.read_text())):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr=='add_usd':
            explicit = {k.arg for k in n.keywords if k.arg is not None}
            calls.append(dict(path=str(path.relative_to(lab)), line=n.lineno,
                              unsupported=sorted(explicit-accepted),
                              dynamic_kwargs=any(k.arg is None for k in n.keywords)))
result = dict(python=sys.executable, project_pin=pin(project), isaaclab_pin=pin(upstream),
              installed_commit=installed, locked_commit=locked, add_usd_calls=calls,
              unsafe_checkpoint_parameter_present='allow_unsafe_torch_checkpoints' in accepted,
              runtime_modules_loaded=sorted(set(sys.modules)&{'torch','warp','newton','isaaclab','mujoco'}),
              limitation='AST checks explicit keyword names only; no runtime or dynamic kwargs validation')
result['passed'] = (len({pin(project),pin(upstream),installed,locked})==1
                    and result['unsafe_checkpoint_parameter_present']
                    and not any(c['unsupported'] for c in calls)
                    and not result['runtime_modules_loaded'])
(Path(__file__).with_name('dependency_contract_results.json')).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
sys.exit(0 if result['passed'] else 1)
