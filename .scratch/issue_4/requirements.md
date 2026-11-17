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


## Change request CR2 — Explore complete / Confirmed requirements

User invoked grill-with-docs to extend the existing Isaac Lab data_collection and fit/CMA-ES flow to additional velocity-tracked wheel joints. Temporarily tracked as an amendment to Issue #4, continuing its established document location. No new issue creation or implementation authorized. CR1 manual GUI acceptance remains pending independently.

### Confirmed user requirements

- Preserve the intent of the user's PaceCfg changes: leg_order distinguishes position-tracked joints and wheel_order distinguishes velocity-tracked joints.
- Isaac Lab collection must save actual/desired wheel velocities separately, consistent with the native MuJoCo mixed-data convention: dof_pos/des_dof_pos for legs, dof_vel/des_dof_vel for wheels, shared time.
- fit.py and CMA-ES must recognize whether the task contains wheel data and consume that data for optimization. Exact recognition/validation mechanism is not yet selected.
- This explicitly extends the earlier collection-only scope: ADR 0001 remains the record of the original delivery, but its exclusion of fitting integration does not prohibit this newly requested work. Any new architecture/parameterization decision awaits the appropriate stage and approval.
- Existing uncommitted user changes, including robot/task/config changes, are inputs to preserve and reconcile, not discard.

### Confirmed code facts (read-only; not runtime verification)

- Collection reads leg_order/wheel_order and builds leg/wheel trajectories, but its loop still refers to the old trajectory variable and saves only time/dof_pos/des_dof_pos across joint_order. Several indexing expressions mix subset-local and articulation-global indices.
- fit currently loads only position fields, initializes from measured positions, sends position-derived actions and calls position-only optimizer scoring.
- CMA-ES scores squared position errors with per-joint encoder-bias correction, maintains only a position trajectory buffer and saves a single best-position trajectory. Its saved config omits wheel velocity fields.
- X5 joint_order already concatenates legs and wheels. PaceCfg friction-ratio helpers append wheel_order again when counting joints; X5 bounds allocate 49 rows while writing ranges through row 64. ANYmal currently supplies joint_order without leg_order. These are migration/integration concerns, not approved new APIs.

### Assumptions / recommendations

- Recommend retaining existing pure-position tasks and three-field historical datasets while accepting mixed datasets from both native MuJoCo and Isaac Lab. Await user confirmation.
- Recommend that a mixed task's fitting outcome covers both leg-position and wheel-velocity responses, with separately inspectable errors. Joint objective construction and relative weighting remain deferred.
- Recommend explicit rejection when task joint groups and supplied dataset disagree, instead of silently dropping a required response group. Await confirmation.

### Open requirement questions — round 1

Q1: Must existing pure-leg tasks and historical three-field position datasets continue to work, alongside mixed datasets from either collector?
Q2: Should a mixed-task fitting result identify both leg and wheel dynamics together and report the two tracking errors separately?
Q3: When the task declares wheel joints but data lacks either wheel velocity field or has incompatible channel counts, should fitting fail clearly rather than proceed with incomplete data?

### Deferred decisions

Which physical parameters to identify for wheels (including whether any wheel measurement bias is required); parameter sharing/delay scope; acceptable fitting quality and output/reporting expectations; time alignment and coordinate conventions. Once requirements settle, Research should investigate installed Isaac Lab action ordering, sensor/state access, delay/bias behavior and backend support. Loss normalization/weights, parameter-vector layout, checkpoint schema, task-detection algorithm, configuration defaults and implementation layout belong in Specify. No simulation or optimization experiments have been run for CR2.


CR2 independent read-only source cross-check: installed Isaac Lab ActionManager concatenates action terms in configuration order, while preserve_order regex matching groups X5 joints by hip/thigh/calf patterns rather than the configured per-leg leg_order. Articulation IDs therefore cannot be assumed to be action-vector column indices. The current X5 config also contains an incomplete import statement. These are present working-tree integration gaps; user may still be editing them. Re-read before future edits. Existing optimizer has one shared delay, per-joint position bias, zero initial velocities and position-only saved configuration/best trajectory. Whether these semantics extend to wheels remains an explicit requirement/design frontier, not an inferred approval.


### CR2 round 1 — Confirmed

User answered “1. 是，三字段历史数据是指？2. 是的 3. 是”. Clarified that historical three-field datasets contain time, dof_pos and des_dof_pos only: they represent position responses and position targets, without wheel velocity measurements/targets. Compatibility applies to pure-position tasks; it does not authorize inferring missing wheel velocities from position data or ignoring configured wheels.

- CR2-R1: support existing pure-leg tasks and their historical position-only data, plus mixed datasets from native MuJoCo and Isaac Lab.
- CR2-R2: one mixed-task fitting outcome covers both leg and wheel dynamics; report leg-position and wheel-velocity errors separately. Objective normalization/weighting remains deferred.
- CR2-R3: task/data group mismatch, missing required measured/desired wheel-velocity fields, or incompatible channel counts must fail explicitly before fitting.

### CR2 next requirement frontier — Proposed / unanswered

Q4: identify wheel armature, damping and friction alongside leg dynamics; retain position-encoder-bias identification for position joints only, without adding wheel position bias or velocity-measurement bias identification. Friction model selection and backend feasibility remain later decisions, not a new approval here.
Q5: whether a single shared control delay for legs and wheels, as in the existing optimizer, satisfies the requirement or whether separate group delays must be identified. Recommendation: retain shared delay unless the physical system requires separate delays. No numeric bounds, step units or parameter layout selected in Explore.

Next frontier after these answers: required backends, moving-wheel initial conditions and acceptance/output expectations. Existing user collision/physical-suitability ownership remains unchanged. No CR2 runtime experiments or implementation performed.


### CR2 round 2 — Confirmed

User answered “4. 是 5. 是”.

- CR2-R4: wheel dynamics identification covers armature, damping and friction. Position encoder bias is identified for leg-position channels only; no wheel position-bias or velocity-measurement-bias identification is added in this change. Specific friction parameterization and bounds remain for Research/Specify.
- CR2-R5: one shared control delay across leg and wheel groups satisfies the requirement; no independently identified group delays. Exact units, rounding, bounds and parameter-vector layout are not yet decided.

### CR2 round 3 — Open requirement frontier

Q6: must this extension retain support for both currently handled Newton and PhysX backends? Recommendation: yes, preserving existing backend distinctions rather than claiming identical friction physics.
Q7: must fitting accept reference data whose wheels are already moving at the first recorded sample? Recommendation: yes; zero initial wheel speed should not be an unstated restriction. State initialization details and unavailable wheel-angle handling are deferred.
Q8: must saved fitting results and trajectory comparisons include both leg-position and wheel-velocity responses, with group labels/units, rather than only the current position trajectory? Recommendation: yes. Exact checkpoint formats and legacy-reader compatibility remain for Specify.

These questions define scope/observable behavior only. Loss construction, normalization, parameter indexing, action mapping and code layout remain deferred. Acceptance quality and physical evaluation boundaries will be finalized once scope is confirmed. No production changes or simulations performed.


### CR2 round 3 — Confirmed

User answered “6. 是 7. 是 8. 是”.

- CR2-R6: retain support for the existing Newton and PhysX backends, preserving documented physical-model differences; do not imply backend equivalence.
- CR2-R7: support reference datasets with nonzero measured wheel speed at the first sample. Exact initialization from measurements, handling of unrecorded wheel angles, and simulator API feasibility remain Research/Specify concerns.
- CR2-R8: persisted fitting results and trajectory comparisons cover both leg-position and wheel-velocity groups, with distinguishable joint names and units. Checkpoint schema, existing result-reader migration and layout remain deferred.

### CR2 round 4 — Final Explore questions / unanswered

Q9: should consistency with native MuJoCo collection include temporal/command semantics, not just tensor key names: shared time denotes actual sample instants, measured and desired data correspond to the same instant, and desired values denote issued commands before actuator delay? Recommendation: yes. Step/control-rate mapping, time-grid validation, resampling policy and concrete collection sequence remain deferred.
Q10: should software acceptance include a small controlled identification case demonstrating the mixed fitting loop works and separately checks position/velocity errors, with real-robot/model convergence quality and physical parameter plausibility retained for user acceptance? Recommendation: yes. No numerical convergence threshold, loss normalization/weight, experiment workload or budget is approved by this proposal; these need later stage evidence/design. No guarantee to recover every parameter uniquely is implied.

After these answers, consolidate Explore and request explicit Research transition. Outstanding technical decisions include action-space ordering, backend APIs, mixed residual scaling, parameter layout, initialized wheel states, time-grid compatibility, persisted results and compatibility of existing consumers. No production edits, runtime simulations or optimization trials were performed for CR2.


### CR2 round 4 — Confirmed / Explore conclusion

User answered “9. yes 10. yes”.

- CR2-R9: consistency between native MuJoCo and Isaac Lab collection includes semantics: shared time represents actual sampling instants, measured and desired channels align at those instants, and desired values are issued commands before actuator delay. Matching key names alone is insufficient.
- CR2-R10: software acceptance includes a bounded controlled identification case demonstrating the mixed fitting loop and separate position/velocity error evaluation. Real-model convergence quality and physical parameter plausibility remain user-owned acceptance. Numerical thresholds, workload and experiment approval are deferred; no particular parameter-identifiability guarantee is made.

Explore is complete. The open requirement questions from rounds 1–4 are resolved by the user confirmations recorded above. Confirmed scope: preserve leg_order/wheel_order grouping; keep pure-position task/data compatibility; accept mixed native/Isaac Lab data; identify leg and wheel dynamics with a shared delay and leg-only position bias; retain Newton/PhysX support; handle initially moving wheels; validate task/data consistency; save/show both response groups; align sampling/command semantics; distinguish software acceptance from physical fitting quality.

### Research handoff — not yet authorized

Investigate installed versions and current working-tree changes before selecting approaches:

1. Action-term/channel ordering versus articulation joint IDs; mixed position/velocity command application and measurement access on both backends.
2. Existing encoder-bias and delay behavior, first-sample/initial-wheel-state handling and effects of unrecorded wheel angles.
3. Sampling/control intervals, dataset time-grid compatibility and feasible alignment approaches.
4. Parameter bounds/layout and friction options compatible with both backends; mixed-unit residual scaling approaches and observability limitations.
5. Existing optimizer result consumers, checkpoint/reporting compatibility and separate leg/wheel response outputs.
6. Design a small, bounded controlled identification experiment and propose measurable software acceptance criteria. Obtain specific approval before Research runtime experiments; stage transition alone is not experiment approval.

No technical approach, new default, parameter layout, loss formula, checkpoint schema or production implementation is approved by Explore completion. Next stage requires explicit Research authorization. CR1 manual GUI acceptance remains pending independently.

CR2 stage transition: user explicitly approved Research (“进入research”). This supersedes the earlier awaiting-stage-approval statements; no runtime experiment or final design is implied.


### CR2 trajectory clarification — Confirmed user amendment

User clarified: “centers单独乘的direction已经去除，按照现在的(centers + np.sin(phase[:, None])) * amplitudes * directions，这样与data_collection.py中轨迹的生成保持一致”. The normalized-center formula is now authoritative for this requested alignment; it supersedes CR1's physical-center interpretation for forthcoming changes. Do not revert the user's native formula.

The physical center equals centers * amplitudes * directions. The current native initialization/history still uses centers directly; this is a confirmed remaining inconsistency, not an approved startup jump. With current values, a thigh center coefficient0.4 and amplitude0.5 imply a physical center0.2 rad, while current initial qpos is0.4 rad. Aligning initial state/history, config descriptions, tests and examples must be carried into Specify/Implement. No revised numeric center coefficients/amplitudes were requested.
