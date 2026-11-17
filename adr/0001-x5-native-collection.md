# X5 原生 MuJoCo 采集与混合数据边界

Status: Accepted. User-approved decisions implemented in 87da096; software acceptance recorded in .scratch/issue_4/verification.md.

## Context / problem

Issue #4 needs an independent MuJoCo reference dataset. Existing collection/fitting assumes leg positions and imports Isaac Lab; X5 additionally has velocity-controlled wheels.

## Alternatives

Use Isaac Lab/Newton for collection; flatten all channels into position fields; adapt mixed fitting in the same task; or separate native collection from later fitting work.

## Decision and rationale

Use native MuJoCo and user-supplied x5_calibration.xml. Keep physics (including single dry friction, native PD/limits/delay and collision settings) in MJCF. Collect 12 leg positions and 4 wheel velocities into separate measured/desired fields with shared time. Desired values precede actuator delay; position measurement subtracts encoder bias and receives XML-configured noise. Scope is collection/save/plot, not fitting integration. User owns collision/trajectory physical acceptance.

## Consequences / trade-offs

Data preserves distinct units and actuator delay information. Existing fitting cannot consume the new mixed experiment without later work. Known contacts can affect response and are retained intentionally; data-generation success does not certify model physics. Measurement noise/bias affects recorded readings, not native controller feedback.

## Evidence

See .scratch/issue_4/research.md, native delay and sensor timing probes, and scripts/pace/fit.py position-only read/action path.

## Approval references

User confirmed native MJCF/friction/control and sensor-side measurement in Explore; approved mixed saved fields and pre-delay commands; answered Q1 collection-only, Q3 initial state, Q4 starting history; rejected contact exclusion in Q6 and delegated model/trajectory acceptance to themselves in Q7. Module layout and interface details were subsequently approved in Q8–Q10 and the Plan handoff; see ADR 0002 and .scratch/issue_4/interfaces.md.
