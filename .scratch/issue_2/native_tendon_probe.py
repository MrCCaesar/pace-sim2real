"""Synthetic MuJoCo CPU tendon capability probe; not IsaacLab integration.

Elastic zero-damping limiting case only. No claim of calibrated nylon behavior.
"""
import json
import mujoco

XML = '''<mujoco><option gravity="0 0 0" timestep="{dt}" integrator="RK4"/>
<worldbody><site name="anchor" pos="0 0 0"/>
<body pos="0.98963 0 0"><joint name="slide" type="slide" axis="1 0 0"/>
<geom type="sphere" size="0.01" mass="1" contype="0" conaffinity="0"/>
<site name="end"/></body></worldbody>
<tendon><spatial name="rope" stiffness="100" damping="0" springlength="0 1">
<site site="anchor"/><site site="end"/></spatial></tendon></mujoco>'''


def run(dt):
    model = mujoco.MjModel.from_xml_string(XML.format(dt=dt))
    data = mujoco.MjData(model)
    data.qvel[0] = 1
    peak, min_force, slack_force = 0.0, 0.0, 0.0
    for _ in range(round(0.4 / dt)):
        mujoco.mj_forward(model, data)
        tension = -float(data.qfrc_passive[0])
        peak, min_force = max(peak, tension), min(min_force, tension)
        if data.ten_length[0] <= 1:
            slack_force = max(slack_force, abs(tension))
        mujoco.mj_step(model, data)
    return dict(dt_s=dt, sampled_peak_N=peak,
                peak_relative_error=abs(peak-10)/10,
                minimum_tension_N=min_force, maximum_slack_force_N=slack_force)


rows = [run(dt) for dt in (0.01, 0.005, 0.0025, 0.00125, 0.000625)]
assert all(r['minimum_tension_N'] >= -1e-12 and r['maximum_slack_force_N'] < 1e-12 for r in rows)
assert rows[-1]['peak_relative_error'] < 1e-4
print(json.dumps(dict(synthetic=True, mujoco_version=mujoco.__version__,
                     analytic_peak_N=10, results=rows), indent=2))
