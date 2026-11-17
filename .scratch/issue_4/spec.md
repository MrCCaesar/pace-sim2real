# Issue #4 — Specification

Status: Approved as planning baseline by user request to enter Plan and split tasks from these documents, following Q8–Q10 confirmations.
Requirements: requirements.md. Evidence: research.md. Contracts: interfaces.md.

## Confirmed scope

Native MuJoCo X5 collection, saved data and plotting only. Twelve leg-position and four wheel-velocity channels; preserve user-owned MJCF physics/collision settings. Collision/trajectory physical validity is user-accepted, not an automated pass/fail criterion. No fitting pipeline changes.

## Approved architecture — D1

- scripts/pace/data_collection_mujoco.py: thin CLI entry, configuration overrides, collection/save/optional plot orchestration.
- scripts/pace/mujoco_collection.py: standalone configuration, named joint/actuator/sensor mapping, chirp generation, native simulation, measurement processing and data export. Internal helpers are private; public contract is in interfaces.md.
- config/x5_collection.toml: explicit ordered channel names and excitation/measurement/run settings. Standard-library tomllib; no additional configuration dependency.
- Existing x5_calibration.xml remains authority for dt, integrator, PD, limits, native delay/history, passive friction/damping, armature and sensor noise. No runtime physics overrides or collision exclusions.
- tests/test_mujoco_collection.py: behavior tests with minimal native models; bounded X5 smoke validation separately.
- docs/examples/x5.md: actual command, units, output order, known fitting incompatibility and model acceptance boundary.

Rationale: keep the collector independent of package initialization which currently imports Isaac Lab. A sibling script helper is sufficient for one collector, avoids expanding package __init__ behavior, and separates CLI from testable logic. Alternative: public package module plus lazy package imports; deferred unless reuse warrants that broader change. This is a source-checkout CLI, not a new installed entry point or generic robot framework.

## Approved sampling semantics — D2

N=round(duration/dt), require N>=1 and duration/dt within 1e-9 of an integer; otherwise report an error instead of silently changing requested duration. Sample interval [0,duration), t[k]=k*dt. Perform N physics steps; final integrated state at duration is not an additional sample.

Linear chirp phase: 2*pi*(f0*t+(f1-f0)*t*t/(2*duration)). Leg target=center+amplitude*sin(phase); wheel velocity target=amplitude*sin(phase). All channels share phase. No clipping or automatic recentering.

Initialize leg qpos at configured centers, wheel qpos zero, all qvel zero. Initialize ctrl and each enabled native command history with the same starting targets via mj_initCtrlHistory. No settling interval.

For each sample: set current un-delayed ctrl; call mj_forward to refresh instantaneous joint sensors; capture sensor readings and associated t[k]; apply measurement-only bias/noise; retain original desired commands; then mj_step. Check finite state and invalid-dynamics warnings, including after the last step. Native forward computation, not a Python controller, determines forces/delay. Current X5 sensors have no sensor delay/decimation; reject delayed/interval sensors rather than silently claiming synchronous measurements.

## Approved configuration and noise — D3

Use explicit configuration defaults with CLI overrides for min_frequency, max_frequency, duration and plot. Approved defaults inherited from existing collection where applicable: 0.1 Hz, 10 Hz, 20 s; plot=false; seed=42. Add --config to select the TOML file. Other settings edited in TOML, avoiding extra physics CLI flags.

Leg centers [0,0.4,-1.4], amplitudes [0.25,0.5,0.99] repeated for FL,FR,RL,RR; wheel amplitude 10. Encoder bias configurable as scalar or 12-entry vector, default 0.05 rad. Seed configurable integer. Use a local random generator; independent Gaussian draws per channel/sample using XML sensor_noise as standard deviation. Position=raw-bias+noise; velocity=raw+noise. Noise never changes ctrl, physical state or native feedback. Zero XML noise produces exactly zero added noise.

## Output and plotting

Exact five tensor keys defined in interfaces.md, CPU tensors readable with torch.load(weights_only=True). Save only on successful complete collection to data/x5_sim/chirp_data.pt. Approved replacement policy: successful runs replace the prior dataset atomically; failure/interruption leaves prior output intact. Respect existing PACE_ROOT override when resolving project output location. Resolve default model/config relative to source checkout, and model path within custom TOML relative to its config directory.

Plot only when requested, after saving: one figure of 12 leg position axes, another of 4 wheel velocity axes, each comparing measured versus pre-delay desired signals, seconds/rad/rad-per-second labels and names. No live simulator viewer is required.

## Software acceptance criteria

- A1/R2,R3: correct named mapping despite differing body/actuator/sensor storage order; missing, duplicate, wrong-type channels fail clearly before stepping.
- A2/R4,R5: exact configured center/amplitude and linear chirp phase; common time grid, shape and sample-count contracts; invalid/non-finite inputs rejected.
- A3/R6: native four-step delay and nonzero historical targets reproduced in a minimal-model regression test; actuator effort clipping tested with saturation-driving input. No Python PD/delay approximation.
- A4/R7,R8: subtractive bias, noise-free exactness, seeded repeatability, independent channels and XML noise scaling verified independently of model physics. Avoid fragile single-run statistical assertions.
- A5/R9: five keys, tensor dtypes/shapes/order/units, pre-delay target values and sensor time alignment verified by round-trip and minimal dynamics tests.
- A6: collection failure preserves old dataset; successful write replaces complete dataset. plot=false avoids plotting import/use; plot=true displays both groups from saved-equivalent data.
- A7: bounded X5 smoke run validates mapping, finite values and data serialization. Contacts/poor tracking do not fail acceptance; numerical divergence does. This does not certify physical accuracy.
- A8/R10: documented command/format/config match implementation. Existing Isaac Lab scripts and fitting behavior remain outside this change.

## Approval and delivery

Q8 approved module/TOML separation; Q9 approved defaults, pre-integration sampling and integer-step duration; Q10 approved successful atomic replacement and failure preservation. User then explicitly entered Plan, Implement and Verify in sequence. This specification was implemented in 87da096; software acceptance evidence and physical limits are in verification.md.
