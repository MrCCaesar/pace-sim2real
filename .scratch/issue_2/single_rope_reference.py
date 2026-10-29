"""Synthetic CPU reference, not a production model or calibrated nylon model.

One-dimensional slack-to-taut event, unit mass, unit engagement speed,
zero gravity, elastic limiting case k=100 N/m and zero damping.
Analytic first peak: v*sqrt(k*m)=10 N; impulse to first peak: m*v=1 Ns.
The half-step slack interval deliberately puts engagement between samples.
"""
import json
import math


def run(dt):
    x, v, impulse, peak = -0.01037, 1.0, 0.0, 0.0

    def derivative(state):
        position, velocity, _ = state
        tension = 100.0 * max(position, 0.0)
        return velocity, -tension, tension

    for _ in range(math.ceil(0.4 / dt)):
        s = (x, v, impulse)
        a = derivative(s)
        b = derivative(tuple(y + dt * z / 2 for y, z in zip(s, a)))
        c = derivative(tuple(y + dt * z / 2 for y, z in zip(s, b)))
        d = derivative(tuple(y + dt * z for y, z in zip(s, c)))
        x, v, impulse = tuple(y + dt * (aa + 2*bb + 2*cc + dd)/6
                              for y, aa, bb, cc, dd in zip(s, a, b, c, d))
        peak = max(peak, 100 * max(x, 0))
        if v <= 0:
            break
    return {"dt_s": dt, "sampled_peak_N": peak,
            "peak_relative_error": abs(peak - 10) / 10,
            "impulse_to_first_nonpositive_velocity_Ns": impulse,
            "velocity_m_s": v, "momentum_residual": abs(v + impulse - 1)}


if __name__ == "__main__":
    rows = [run(dt) for dt in (0.01, 0.005, 0.0025, 0.00125, 0.000625)]
    assert all(r["momentum_residual"] < 1e-10 for r in rows)
    assert rows[-1]["peak_relative_error"] < 1e-4
    print(json.dumps({"synthetic": True, "backend": "stdlib RK4 reference only",
                      "analytic_peak_N": 10, "results": rows}, indent=2))
