# Issue #4 — Requirements

Status: Approved requirements; implemented and software-verified in commit 87da096.
Source: https://github.com/MrCCaesar/pace-sim2real/issues/4 and user confirmations in this conversation.

## Confirmed requirements

- R1: Collect excitation data in native MuJoCo as an independent simulation reference for PACE.
- R2: Use src/pace_sim2real/assets/data/robots/sevnce/x5/mjcf/x5_calibration.xml; fixed base at 1 m, floor and light, all 16 joints.
- R3: Twelve leg position channels ordered FL, FR, RL, RR, each hip/thigh/calf; four wheel velocity channels ordered FL, FR, RL, RR.
- R4: Leg chirp centers [0, 0.4, -1.4] rad, amplitudes [0.25, 0.5, 0.99] rad; wheel velocity chirp center zero, amplitude 10 rad/s. Center is additive, not multiplied by amplitude.
- R5: Expose min_frequency, max_frequency, duration, plot. Approved defaults are specified in spec.md.
- R6: MJCF defines native PD, effort limits, command delay, single dry friction, armature and passive damping. XML timing is in seconds: dt=0.0025, delay=0.010, nsample=4 as last verified.
- R7: Position measurement = sensor reading - encoder_bias + Gaussian noise. Configurable encoder_bias defaults to 0.05 rad. Velocity measurement adds Gaussian noise without position bias.
- R8: Noise standard deviations come from XML: position 0.01 rad, velocity 0.1 rad/s as last verified; replaces earlier 0.02 proposal. Independent zero-mean Gaussian noise and reproducible random seed were confirmed.
- R9: Save data/x5_sim/chirp_data.pt with shared time[N], dof_pos/des_dof_pos[N,12], dof_vel/des_dof_vel[N,4].
- R10: Keep model, simulation configuration, tests and docs reasonably separate. Important architecture decisions require user confirmation. No unrequested functionality or physics simplification.

## Confirmed scope and startup

- Confirmed: collection, saving and plotting only; mixed-data fitting integration is outside Issue #4.
- Confirmed: desired signals are issued commands before native actuator delay.
- Confirmed: initial leg positions at chirp centers, wheel angles and all joint velocities zero; record startup transient without settling; initialize historical commands to those starting targets.

## Superseded decisions

- ANYmal model and all-position 16-column data were superseded by X5 mixed position/velocity collection.
- Additive encoder bias was corrected to subtractive bias.
- Earlier calf centers/amplitudes were superseded by R4.
- Millisecond wording was corrected: XML second values are authoritative.

## Approved design

Final interfaces and configuration are recorded in interfaces.md; architecture and acceptance criteria are in spec.md. User approved this baseline when entering Plan.

## Evaluation boundary — Confirmed

User owns collision-model and trajectory physical-suitability acceptance. No requirement for contact-free initial state or contact-free sweep is imposed by this issue. Do not exclude contacts or correct collision geometry as part of the collector work. Preserve the known contact findings; do not claim physical validity from numerical execution success. User intends to revise trajectory centers/amplitudes later; no revised numbers beyond R4 are currently approved.
