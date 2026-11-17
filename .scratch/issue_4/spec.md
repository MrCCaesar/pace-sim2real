# Issue #4 — Specification

Baseline status: Approved as planning baseline by user request to enter Plan and split tasks from these documents, following Q8–Q10 confirmations.
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


## CR1 — Approved specification; implemented, formal Verify pending

Stage approval: “进入 Specify 阶段”. User then explicitly approved Q7–Q9 and Q10–Q11. The CR1 contracts below amend baseline D1–D3 and the no-live-viewer scope; earlier sections retain the original delivery history. This does not authorize Plan or implementation.

### Confirmed requirements

CR1-R1: independent signs for all twelve position and four velocity channels. Leg target = direction * (center + amplitude * sin(phase)); wheel target = direction * amplitude * sin(phase). Directions affect commanded trajectories and signed leg initial centers/history, not measured coordinate conventions. Units, channel order, sensor bias/noise and five output tensors remain as defined in the baseline.

CR1-R2: optional observation-only live 3D view, camera adjustment, approximately real-time viewing, independent of post-run plots. Closing its window continues collection. Explicitly requested viewer startup failure aborts without replacing the output. Existing Ctrl+C cancellation remains.

### Approved decisions — Q7–Q9

CR1-D1 / Q7: add optional position_directions (12 signs) and velocity_directions (4 signs) in [trajectory], each element strictly numeric +1 or -1 (bool rejected). Missing arrays default to all +1, preserving old TOML and Python-config callers; wrong length/value is an error. Provided TOML lists both arrays explicitly, initially all +1. No inferred left/right pattern. Existing required fields and unknown-key rejection stay in force.

CR1-D2 / Q8: retain the standalone collector; isolate live viewing in a child process with its own model/data, receiving authoritative state one way. GUI-side control/physics edits never reach collection. See Accepted ADR 0003. The existing collect signature remains; viewer ownership/cleanup belongs to its run. Private helper boundaries, snapshots and timing are defined by Q10/Q11 below and interfaces.md.

CR1-D3 / Q9: optional run.visualize boolean defaults false when absent; CLI --visualize / --no-visualize override it. Existing plot behavior and user-owned plot=true setting are preserved. Normal window close disables visualization and wall-clock pacing, and collection completes headlessly. Unexpected viewer failure after startup aborts collection with an actionable error and preserves old output, matching startup failure rather than silently hiding faults. KeyboardInterrupt cancels and cleans up both processes.

### CR1 acceptance criteria

- CR1-A1: independently signed leg/wheel targets match the approved formula; signed leg initial positions/control history match; all +1 preserves baseline results with identical seed/config. Measurements stay in native joint coordinates.
- CR1-A2: invalid sign lengths/values/types fail before stepping; old configs retain baseline behavior; CLI override precedence is deterministic.
- CR1-A3: visualization disabled requires no viewer/display initialization; visualization enabled leaves time grid, all five data fields and physics unchanged for fixed seed/config.
- CR1-A4: window closure continues to N samples; startup failure, unexpected runtime failure and Ctrl+C clean up resources and preserve existing output.
- CR1-A5: bounded native-viewer smoke test plus controlled failure/lifecycle tests; manually inspect camera interaction/window close. Synthetic evidence must not be described as manual GUI acceptance.

### Q10–Q11 — Approved timing and process contracts

Approval reference: user answered “10. yes 11. yes”. Q7–Q9 were approved separately. No unresolved product-design questions remain for this change.

CR1-D4 / Q10 — Approved timing contract: limit display publication to 30 Hz; the first state is the initialized state before the first integration. Publish later snapshots after integration. Pace authoritative physics against a monotonic wall clock while the window is open. When behind, skip waits and stale display frames, never physics steps or measurements. Keep pending display data bounded to the latest snapshot and do not wait for a per-frame acknowledgment. Normal window close disables pacing. Approximately real time is best effort, not a performance guarantee. Render cadence is an internal constant initially, not an additional public configuration option.

CR1-D5 / Q11 — Approved process contract: child loads the same resolved MJCF and receives copied mjSTATE_INTEGRATION snapshots (MuJoCo 3.17 API, exercised in E1), never aliases of authoritative arrays. Child refreshes derived display state without stepping authoritative physics. Separate lifecycle messages distinguish ready, normal-close and error; unexpected exit without an acknowledged normal-close is an error. Start collection only after ready. Startup deadline 10 s; graceful shutdown deadline 2 s, then terminate and wait 1 s, then kill and wait 1 s. Failure to reap within this bounded sequence is an actionable error; no dataset replacement. These are internal constants initially. KeyboardInterrupt uses the same cleanup sequence and retains CLI exit 130. Headless mode starts no viewer process and performs no real-time waits.

Approved private module boundary (Q11): scripts/pace/mujoco_viewer.py owns the child entry point, lifecycle and state transport; mujoco_collection.py keeps all physics, measurements and data ownership. It is a private sibling helper, not a new public package API. No Isaac Lab import or package initialization is introduced. UI features that mutate physics are not exposed as collection controls; display-side edits never propagate back. Exact native rendering fidelity remains a manual acceptance check.

### Traceability and verification obligations

| Requirement | Design / interface | Required evidence |
| --- | --- | --- |
| CR1-R1 independent signs | CR1-D1; position_directions/velocity_directions | CR1-A1/A2: mixed-sign formula, signed initial state/history, invalid types/lengths, legacy-config and all-positive equivalence |
| CR1-R2 observation isolation | CR1-D2; Accepted ADR 0003; private viewer helper | CR1-A3: same-seed output equality and display-copy mutation isolation; no viewer initialization when disabled |
| CR1-R2 enable/close/failure | CR1-D3/D5; CLI flags and lifecycle | CR1-A4: normal close completes; startup error/timeout, unexpected exit and cancellation preserve output and reap child; escalation paths checked without long real-time sleeps |
| CR1-R2 approximate real time | CR1-D4; latest-state publication and monotonic pacing | CR1-A5: controlled clock/slow display verifies bounded pending data, skipped frames but N steps, and no pacing after close |
| Documentation and actual GUI | interfaces.md; examples and config | Bounded desktop smoke plus explicit manual camera/window-close result; clearly distinguish automated from human observation |

Existing baseline A1–A8 still apply, with trajectory formulas extended by directions. Production tests must cover timeout/escalation paths not exercised by Research E2. Existing research probes are feasibility evidence, not implementation acceptance. No full-sweep physical acceptance is inferred.

### Handoff

Specify decisions Q7–Q11 are approved; interfaces.md consolidates their contracts. Implementation details that do not alter these contracts (transport primitive, private symbol names) can be chosen during implementation. No new user-facing options are implied. Next: Plan only after explicit user approval. User-owned collision/trajectory validity and future manual GUI verification remain acceptance boundaries, not unresolved design decisions.

CR1 implementation update: #8/#9 implemented against approved contracts; automated and bounded native smoke evidence is in verification.md under implementation checks. Code review and formal Verify status are tracked in status.md.
