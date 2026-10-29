"""Synthetic elastic/static massless-node feasibility probe, not production.

SI units, world z up, anchor at origin, chain length 2 m.
No hook mass, no damping or time integration. Test tolerances are numerical
probe criteria only, not approved physical accuracy requirements.
"""
import json
import numpy as np
from scipy.optimize import root

points = np.array([[-.5, -.3, -3], [-.5, .3, -3], [.5, -.3, -3], [.5, .3, -3]])


def solve(lengths):
    def residual(y):
        hook, reaction = y[:3], y[3]
        delta = points - hook
        distances = np.linalg.norm(delta, axis=1)
        forces = 100 * np.maximum(distances-lengths, 0)
        return np.r_[np.sum(forces[:, None] * delta / distances[:, None], axis=0)
                     - reaction * hook / 2, (hook @ hook - 4)/2]

    sol = root(residual, [0, 0, -2, 40], tol=1e-11)
    y = sol.x
    eps = 1e-5
    jac = np.column_stack([(residual(y+eps*np.eye(4)[i])-residual(y-eps*np.eye(4)[i]))/(2*eps)
                           for i in range(4)])
    singular = np.linalg.svd(jac, compute_uv=False)
    tension = 100*np.maximum(np.linalg.norm(points-y[:3], axis=1)-lengths, 0)
    all_slack = bool(np.max(tension) < 1e-8)
    return dict(lengths_m=lengths.tolist(), hook_position_m=y[:3].tolist(),
                short_tensions_N=tension.tolist(), chain_reaction_N=float(y[3]),
                residual_norm=float(np.linalg.norm(residual(y))),
                chain_length_error_m=abs(float(np.linalg.norm(y[:3]))-2),
                jacobian_min_singular_value=float(singular[-1]),
                numerical_solver_success=bool(sol.success),
                domain_status='all_slack_invalid' if all_slack else 'static_candidate')


results = {name: solve(np.array(lengths, dtype=float)) for name, lengths in {
    'four_taut': [1, 1, 1, 1], 'two_taut': [1, 3, 3, 1],
    'one_taut': [1, 3, 3, 3], 'all_slack': [3, 3, 3, 3]}.items()}
for name in ('four_taut', 'two_taut', 'one_taut'):
    r = results[name]
    assert r['residual_norm'] < 1e-7 and r['chain_length_error_m'] < 1e-8
    assert r['chain_reaction_N'] > 0 and r['jacobian_min_singular_value'] > 1e-6
assert results['all_slack']['domain_status'] == 'all_slack_invalid'
print(json.dumps(dict(synthetic=True, scope='local static elastic feasibility only', results=results), indent=2))
