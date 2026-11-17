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

## Change request CR1 — Draft / Explore

User invoked grill-with-docs to add configurable trajectory directions for symmetric joints and optional live MuJoCo visualization for debugging. Existing approved implementation and verification remain the baseline; CR1 is not yet specified or implemented.

Confirmed facts: Isaac Lab uses (sin(phase)+bias)*direction*scale; current native collector uses center+amplitude*sin(phase), with centers in physical radians. These bias conventions differ. Current local TOML has plot=true; preserve this user change.

Open frontier: whether direction mirrors center and oscillation together or oscillation only; whether wheels also need independent signs; whether visualization is an observation-only real-time 3D view independent of post-run plots. Exact APIs, direction vectors, viewer lifecycle and backend feasibility are deferred to later decisions/stages.

### CR1 round 1 confirmations

- Q1 confirmed: direction mirrors both center and oscillation; preserve physical center/amplitude semantics, desired = direction * (center + amplitude * sin(phase)).
- Q3 confirmed: observation-only live 3D visualization, approximately real-time playback and camera adjustment, independent of post-run plot switch. No force/control editing features requested.
- Q2 unresolved: user's wording “否为 12 个腿关节和 4 个轮关节分别提供独立的方向符号” is ambiguous. Clarify whether all sixteen channels have independent signs, only twelve leg channels do, or signs are grouped/shared. Do not infer a channel scope.

### CR1 direction scope — Confirmed

User clarified: “12 个腿关节和 4 个轮关节，各自配置独立的方向符号”. All sixteen channels therefore have independent direction signs. The prior Q2 ambiguity is resolved; shared/grouped signs and leg-only direction configuration are not selected.

The existing no-startup-jump requirement implies initial leg positions and historical position commands must match the signed center; wheel initial angles/velocities and zero historical wheel commands remain zero. Exact direction vectors and configuration defaults remain for Specify.

Remaining Explore questions: whether closing the observation window continues collection without visualization; whether an explicitly requested viewer that cannot start must fail visibly rather than silently fall back. No implementation choice or viewer API is approved by these questions.

### CR1 viewer lifecycle — Confirmed

User answered “4. 是 5. 是”. Closing the live observation window does not cancel collection: continue headlessly through the configured duration and save normally. Ctrl+C retains the existing cancellation behavior. If visualization is explicitly enabled but its window cannot start, report an error and exit without replacing existing output; do not silently fall back.

### CR1 Explore summary

Confirmed: independent direction signs for all 12 leg-position and 4 wheel-velocity channels; mirror the full desired trajectory (center and oscillation) while preserving physical units; keep sensor coordinate conventions unchanged. Observation-only live 3D display with approximately real-time viewing and camera adjustment is independent of post-run plots. Window-close continues collection; startup failure is explicit and preserves prior data.

Explore is complete for these requirements. Research transition awaits explicit approval. Research must establish native viewer availability/lifecycle, timing independence, close detection and startup-error handling. Exact configuration keys/defaults/sign vectors, APIs and implementation layout are deferred to Specify. Original software verification does not cover CR1.

### CR1 stage transition

User explicitly approved Research (“进入 Research 阶段”), superseding the earlier awaiting-approval statement. Confirmed Explore requirements remain authoritative.
