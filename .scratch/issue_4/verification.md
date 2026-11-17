# Issue #4 — Verification

Status: Complete — software acceptance passed within the approved scope; tooling exception and physical limits below.
Stage authorization: user said “进入verify”.
Date: 2026-11-17. Commit: 87da0960473cc300fd54e6cbeb1945ee3faa47c4.

## Scope and evidence policy

Verify native X5 collection, serialization, failure handling and optional plotting for tasks #5–#7. Preserve the user-owned collision model. Physical model correctness, contact-free motion, tracking quality and fitting accuracy are outside software acceptance.

The implementation's final full suite (40 passed, 6.79 s), Pyright (0 errors/warnings), Ruff and two-axis review apply to the unchanged code at this commit. These checks were not redundantly rerun during this stage. Verify added an independent CLI smoke run and explicit saved-file/hash checks. Exact commands/results are retained in verify-results.json.

## Acceptance matrix

| Criterion | Result | Evidence |
| --- | --- | --- |
| A1 Named channel mapping and rejection | Pass | Reordered native-model collection test; unsupported-model sensor duplication/type, hinge and transmission cases; source inspection of missing/unique mapping errors |
| A2 Excitation/config/time contracts | Pass | Worked chirp phase assertions, configuration validation cases, CLI options; new CLI run produces 40 timestamps from 0 through 0.0975 s at 0.0025 s spacing |
| A3 Native delay/history/force limit | Pass | Native minimal-model regression observes original target/history and four-step delay; saturation-driving wheel test bounds acceleration by XML effort limit; no Python controller/delay implementation |
| A4 Bias/noise | Pass | Subtractive scalar/vector bias; zero-noise baseline; exact seeded repeatability and XML sigma scaling; measurement changes leave desired values and physical baseline unchanged |
| A5 Data schema/order/timing | Pass | Round-trip tests and new five-key CPU tensor readback; float64 time, float32 12-column position and 4-column velocity fields; finite values; pre-integration sensor and pre-delay target tests |
| A6 Failure preservation and plots | Pass (headless plot verification) | Serialization/replacement/interruption fault injection; invalid and final-step dynamics tests; new invalid-duration run leaves dataset hash unchanged; 12/4 figure axes and series tests; plot-disabled import guard; save-before-plot-failure test |
| A7 Bounded real X5 run | Pass | New 0.1 s / 40-step run with plotting enabled from /tmp, exit 0, finite data. Contacts/poor tracking are not rejection criteria |
| A8 Documentation/scope | Pass | Usage/config/schema match implementation; MkDocs navigation includes X5; independent review found 0 standards and 0 spec findings; existing fitting scripts unchanged |

## New end-to-end run

Working directory: /tmp. Environment: PACE_ROOT=/tmp/pace-issue4-verify-eqx13pl6, MPLBACKEND=Agg.

```bash
/home/sevnce-mr/pace-sim2real/.venv/bin/python /home/sevnce-mr/pace-sim2real/scripts/pace/data_collection_mujoco.py --duration 0.1 --plot
```

Exit 0. Saved 40 samples. Raw command/output and tensor summaries are in verify-results.json. Agg emitted its expected warning that an interactive window cannot be shown: this run validates plot construction/execution, not desktop GUI visibility.

Then ran the same entry point with `--duration 0.001` (no plot). Exit 1 with “duration must be a positive integer multiple of model timestep”. Previous dataset SHA-256 was unchanged, and no temporary save files remained.

- Dataset: /tmp/pace-issue4-verify-eqx13pl6/data/x5_sim/chirp_data.pt
- Dataset SHA-256: a1a726c91030e3d249b3c6918152c2ada1e45ccae8c22f374235435f4034aae7
- Calibration XML SHA-256: 370a5b9f1e83ca6a28baf635c497df7a4a6f5517d4bc14420c689e44a27d2249
- Model hash identifies the tested XML only, not all referenced mesh contents.

No production dataset was overwritten. Temporary output location is not durable storage.

## Exceptions / remaining limits

- Unsuppressed pre-commit is not fully green: the existing insert-license hook references missing `.github/LICENSE_HEADER.txt`. All other applicable changed-file hooks passed using `SKIP=insert-license`. New Python files carry Apache-2.0 SPDX headers; unrelated hook configuration was not changed.
- Unrelated system ROS pytest auto-discovery fails on missing lark; completed tests used PYTEST_DISABLE_PLUGIN_AUTOLOAD=1.
- Model assets are user-provided local inputs, not included in the code commit. Asset-dependent smoke tests skip if the calibration model is absent. This checkout had the model, so the reported 40-test run had no skips.
- No complete 20-second sweep, physical tracking acceptance or interactive desktop-window test was performed. Software verification does not assert those results.
- Current collision/trajectory validity remains for user acceptance, as explicitly agreed in Q6–Q7.

## Maintained checks and review

The approved public test boundaries are load_config, collect, save_data, plot_data and CLI. TDD red-to-green cycles covered configuration, collection, saving, CLI, invalid model handling, last-step errors and plotting. No internal helpers are directly tested.

Recorded commands:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q
uv tool run pyright --pythonpath .venv/bin/python scripts/pace/mujoco_collection.py scripts/pace/data_collection_mujoco.py tests/test_mujoco_collection.py
.venv/bin/ruff check scripts/pace/mujoco_collection.py scripts/pace/data_collection_mujoco.py tests/test_mujoco_collection.py
SKIP=insert-license .venv/bin/pre-commit run --files scripts/pace/mujoco_collection.py scripts/pace/data_collection_mujoco.py tests/test_mujoco_collection.py config/x5_collection.toml docs/examples/x5.md pyrightconfig.json mkdocs.yml
```

Review baseline 919afdc was confirmed by the user. Two independent read-only agents reviewed 7c48664; final 87da096 only adds two hook-generated MkDocs whitespace fixes.

- Standards: 0 actionable violations or baseline smells. Module/config separation matches ADR 0002; physics/measurement ownership matches ADR 0001.
- Spec: 0 substantive findings. Native history/delay, time alignment, noise/bias, CPU tensors, failure preservation and plotting match the contracts.

## Outcome

No implementation changes were needed during Verify. No new commits, pushes, GitHub comments or Issue status edits were made. Software work for #5–#7 is verified; closing/publishing issues requires a separate user instruction.


## CR1 implementation checks — 2026-11-17 (not formal Verify)

Implement explicitly authorized via implement skill for #8/#9. TDD seams: approved public load_config/collect/CLI/save interfaces; external native GUI and clock boundaries are substituted for deterministic faults. Confirmed review base: 3a02f00. No Isaac Lab simulation launched.

- Direction behavior test first failed on absent position_directions, then passed after target/initial-state/history changes. Invalid-sign/config compatibility tests failed before validation/schema support and then passed.
- Viewer configuration and explicit startup-failure tests failed before implementation and passed afterward. A ready/closed message race was reproduced and fixed; collection now completes after immediate post-ready close.
- Real X5 GUI smoke initially failed at process teardown with native exit -6; old output was preserved. An external GUI stub reproduced incomplete asynchronous renderer shutdown. Joining viewer-created threads before child interpreter shutdown fixed the regression and the native smoke. Parent deadline/escalation still bounds a stuck renderer.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`: 67 passed in 11.95 s (complete repository test set). Tests exercise independent directions, legacy compatibility, IPC/GUI isolation, deterministic output equality, normal close, startup error/timeout, runtime crash, forced cleanup, Ctrl+C preservation and monotonic pacing. No claim of manual GUI acceptance.
- `uv tool run pyright --pythonpath .venv/bin/python scripts/pace/mujoco_collection.py scripts/pace/mujoco_viewer.py scripts/pace/data_collection_mujoco.py tests/test_mujoco_collection.py`: 0 errors/warnings. Ruff check passed. Initial flake8 R506 was corrected; affected-file pre-commit rerun passed.
- Pre-commit uses SKIP=insert-license because the repository's configured .github/LICENSE_HEADER.txt template is absent (pre-existing baseline issue). Existing Apache SPDX headers retained. Other applicable hooks passed on affected code/docs. No push performed.

Real X5 resource preflight: 19,643 MiB available RAM, 22,617/24,564 MiB free GPU memory. Each CLI run used one model, 0.1 s / 40 steps, a 20 s external watchdog and /tmp output. Mixed signs were applied to selected hips and wheels in a temporary config, with plot=false.

```sh
PACE_ROOT=/tmp/pace-cr1-implementation/headless timeout --kill-after=2s 20s .venv/bin/python scripts/pace/data_collection_mujoco.py --config /tmp/pace-cr1-implementation/config.toml --duration .1 --no-visualize
PACE_ROOT=/tmp/pace-cr1-implementation/viewer timeout --kill-after=2s 20s .venv/bin/python scripts/pace/data_collection_mujoco.py --config /tmp/pace-cr1-implementation/config.toml --duration .1 --visualize
```

Both final runs exited 0 and saved 40 samples. torch.equal comparison was true for all five tensors; shapes [40], [40,12], [40,12], [40,4], [40,4]. Viewer startup, synchronization and shutdown ran against real MuJoCo 3.17.0. Camera appearance/manipulation and a human window-manager close action were not checked. Full-duration mirrored X5 physics acceptance remains user-owned. Formal Verify requires a separate stage approval.


### CR1 review follow-up checks

Initial Standards review: one handoff/documentation inconsistency (stale not-implemented/in-progress headings); corrected. Initial Spec review: one P2 cancellation-during-escalation cleanup gap and one missing direct timing/transport assertion; both addressed.

- Regression sent SIGINT at the terminate-wait boundary: initially returned 130 with a live child; after deferring SIGINT throughout cleanup, the child is reaped, output preserved and exit 130 retained.
- Slow external GUI fixture now logs displayed native times; native state-publication observations prove the 30 Hz cap, skipped stale display frames and all 160 samples retained in a 0.4 s synthetic run.
- Intermediate 69-test run passed but emitted two CPython resource-tracker reentrancy warnings. Neither named semaphore remained after process exit. A new test retained the failure traceback and demonstrated that IPC locks remained alive until GC. Explicit release of session IPC references fixed this; final suite emitted no warnings.
- Final `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`: **70 passed in 13.69 s**, no warnings. Final Pyright command above: 0 errors/warnings. Ruff formatting/check and all applicable affected-file pre-commit hooks passed (same pre-existing insert-license exception).

These checks belong to Implement; formal Verify and manual camera/window-close acceptance remain outstanding.


### CR1 two-axis review result

Fixed point explicitly approved by user: 3a02f00. Reviewed cumulative committed diff through 3076912, with initial implementation 2d1f78d. Independent fresh-context Standards and Spec agents performed read-only reviews, then re-reviewed the follow-up fixes.

- Standards: initial one minor current-status documentation inconsistency resolved; no remaining material findings. No additional code-smell refactoring warranted.
- Spec: initial one P2 cancellation cleanup gap and one timing-evidence gap resolved; no remaining material deviations. Explicit IPC release also has a regression test.

Reviewers did not execute tests; runtime evidence above was executed by the implementing agent. Manual camera/window-manager close and formal Verify remain pending, explicitly distinct from implementation findings. No push or GitHub issue-state changes were performed.


## CR1 formal Verify — 2026-11-17

Authorization: user explicitly requested “进入 Verify”. Target HEAD b41995b (implementation 2d1f78d plus cleanup fixes 3076912). User-owned unstaged edits remain outside this task; verification uses the current local model and preserves those inputs. Issue #4 title/body/comments re-read. No production code changes, commits, pushes or tracker writes performed in this stage.

### Executed checks

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`: **70 passed in 13.82 s**, no skips or warnings.
- `uv tool run pyright --pythonpath .venv/bin/python scripts/pace/mujoco_collection.py scripts/pace/mujoco_viewer.py scripts/pace/data_collection_mujoco.py tests/test_mujoco_collection.py`: **0 errors, 0 warnings**.
- `.venv/bin/ruff check scripts/pace/mujoco_collection.py scripts/pace/mujoco_viewer.py scripts/pace/data_collection_mujoco.py tests/test_mujoco_collection.py`: **All checks passed**.
- `.venv/bin/python /tmp/pace-cr1-verify/verify_cli.py`: **all independent CLI assertions passed**. Exact spawned commands/stdout/stderr and comparisons are retained in cr1-verify-results.json. The harness/config/datasets live under /tmp/pace-cr1-verify, outside production output.

Resource preflight: available RAM 20,054 MiB; GPU free 22,720 / 24,564 MiB. CLI cases ran sequentially, one model at a time, 0.1 simulation seconds each with a 20-second watchdog and isolated output roots. No Isaac Lab run or full-duration sweep.

### Independent CLI cases

1. Explicit --no-visualize overrides a TOML visualize=true setting: exited 0, saved 40 samples.
2. TOML visualize=true without CLI override: real MuJoCo window started, synchronized and shut down; exited 0 and saved 40 samples. All five tensors exactly equal to case 1 via torch.equal.
3. --no-visualize with invalid DISPLAY: exited 0 and saved all 40 samples, exactly equal to case 1. Confirms the disabled path does not require a functioning display.
4. --visualize with invalid DISPLAY: exited 1. A pre-existing valid dataset's SHA-256 was unchanged, and no temporary output remained in its directory. Native error diagnostics captured. No claim that failure runs produce a dataset.

Mixed signs were applied to selected hip and wheel channels in the temporary config. These short-run comparisons demonstrate data/physics isolation, not full-range mirrored trajectory safety. Saved shapes: time [40], leg measured/desired [40,12], wheel measured/desired [40,4].

### Acceptance reconciliation

| Criterion | Result | Evidence / boundary |
| --- | --- | --- |
| CR1-A1 direction formulas and signed initialization/history | Passed | independent_directions behavior test, native startup response/history assertions and mixed-sign CLI smoke |
| CR1-A2 validation and compatibility | Passed | invalid values/types/lengths, legacy TOML/Python callers, all-positive equivalence, CLI override/conflict tests |
| CR1-A3 observation isolation / disabled path | Passed | external-GUI mutation test, real-viewer exact five-tensor equality, invalid-display headless override |
| CR1-A4 close/failure/cancel and output preservation | Automated checks passed | normal/immediate-close events, real startup failure, controlled crash/timeout/escalation, SIGINT during escalation, retained-traceback IPC release; human close-button acceptance still pending |
| CR1-A5 bounded rendering and GUI evidence | Automated/real-launch portions passed; manual portion pending | 30 Hz publication observations, slow-display skipped-frame evidence with 160 samples, controlled-clock pacing, real X5 launch/sync/shutdown; no human camera/close-button observation yet |
| Baseline A1–A8 regression | Passed within existing software boundary | complete 70-test suite; physical contacts/trajectory suitability remain user-owned |

### Remaining acceptance and limitations

Manual GUI confirmation was requested during this stage: camera rotation/zoom and clicking the window close button while collection continues to a complete save. No human result has yet been supplied; programmatic/stub lifecycle tests are not substituted for that requirement. No desktop automation tool was available in this session. Software verification is complete, but **full CR1 acceptance remains pending this manual check**.

The pre-existing missing license-header template and isolated pytest-plugin environment remain as documented above; no unrelated tooling repairs were introduced. No new code-review findings arose from Verify. Formal Verify evidence does not certify collisions, physical model fidelity or a full 20-second sweep.


## User-requested WIP checkpoint checks — 2026-11-17

This is a comparison baseline during CR2 Research, not CR2 Verify acceptance. Current user-owned work was preserved and normalized after the requested retest.

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`: **67 passed,3 failed in14.28s**. Failing tests: `test_collect_preserves_sensor_time_and_native_delay_despite_reordered_model`, `test_independent_directions_mirror_centers_and_preserve_native_measurements`, `test_direction_config_and_legacy_defaults`. These expose the changed normalized-center formula/initialization and configuration expectations; no assertions were weakened to obtain a pass.
- Sequential installed-runtime probes: PhysX passed9.003s, Newton passed8.003s,2env/40steps each. Exact commands and limits in research.md; results in cr2-research-results.json. Full collection/optimization is not validated.
- AST parsing of14 modified/new Python files passed. Removed a dangling `from ` line from the user's new task file, unused/duplicate imports and trailing whitespace; applied repository Black/isort formatting. No new mixed-joint behavior implemented.
- `SKIP=insert-license .venv/bin/pre-commit run --files <14 changed/new Python files> config/x5_collection.toml .gitignore`: Black/isort and applicable hygiene checks passed. Flake8 remains failed on undefined `trajectory` in data_collection.py. Codespell flags the literal joint pattern `.*HAA`; preserve that identifier. License hook skipped because `.github/LICENSE_HEADER.txt` is absent (existing repository limitation).
- `git diff --check` passed after formatting. `git check-ignore` confirmed `.vscode/browse.vc.db`, its SHM/WAL files and lock are ignored. Editor configuration remains trackable.

Known WIP limitations also include unfinished task/assets wiring and mixed-group parameter layout described in Research. A local checkpoint commit is explicitly authorized by the user; it must not be described as a passing implementation. No push or GitHub state change.


## CR2 implementation checks — 2026-11-17 (review pending)

Implementation explicitly authorized through the implement skill; review base ecefbfe explicitly confirmed. These are implementation checks, not automatic entry into the formal Verify stage. Durable results: cr2-implement-results.json.

- TDD at approved seams: native amended center/bias/control-range tests first failed4/4, then native regression passed71; later physical spring response regression passed independently. Group resolution, action permutation/transform, legacy time/model validation, optimizer mixed scoring/paired global best and result plotting each had observed red-to-green cycles. Additional negative/compatibility regression cases were added around implemented contracts.
- Full suite: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q` →86 passed,2 upstream cmaes population2 warnings,15.59s. No simulator is implicitly launched by the CPU suite; runtime checks below are separate.
- `uvx --offline pyright --pythonpath .venv/bin/python scripts/pace src/pace_sim2real/optim/cma_es.py src/pace_sim2real/utils src/pace_sim2real/tasks/manager_based/pace/sevnce_pace_env_cfg.py tests/test_mixed_collection_fit.py` →0 errors/0 warnings. Targeted CPU suite rerun after necessary group-normalization fix; final result retained in handoff.
- Repository pre-commit checks on changed files: Black/flake8/isort and applicable hygiene checks pass. Codespell reports existing HAA joint-name false positives; license insertion skipped for the pre-existing missing template. No blanket suppression added to source or hook config.
- Runtime command form: `OMNI_KIT_ACCEPT_EULA=YES OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 .venv/bin/python tests/test_mixed_collection_fit.py <newton|physx> <smoke|optimize|decimation> /tmp/pace-cr2-implement-<backend>-<mode>`. Each ran via a120s process-group watchdog monitoring available RAM>=4GiB. Initial preflight15982MiB RAM/22569MiB GPU free; simulators sequential. EULA was already explicitly accepted by the user for test processes.
- Real ActionManager smoke:2env/40steps, shuffled position/velocity action columns and nonidentity scale/offset, initial wheel speed1.5rad/s; both backends collected, saved, loaded and replayed through the production collection/fit functions. Truth-candidate errors exactly0. Newton11.003s, PhysX10.003s.
- Controlled fixed-seed identification:4env,20 generations,40 steps per rollout, two active armatures with other parameters fixed; reference/truth/perturbed runs included inside each watchdog. Newton18.005s, best score0.0001487882206 versus initial0.008568803780 (98.26% lower); position RMSE0.00151166rad, velocity RMSE0.0171840rad/s. PhysX12.003s, best0.00007651021210 versus0.008567070588 (99.11% lower); RMSE0.00371112rad/0.0118003rad/s. Truth beats deliberately perturbed candidates in both groups. Formal result reader independently recomputed both stored objectives/errors. No seed search or threshold relaxation.
- Decimation2:2env/20 control samples=40 physics steps; observed40 public actuator compute calls and two-step delay through applied torque on both groups. Newton11.003s; PhysX8.003s. This does not claim equivalence of the physical models.
- Native X5 CLI: temporary config preserves user parameters but disables plotting and uses absolute local XML;4 samples at0.0025s, all five fields loaded by shared fit contract. Initial attempt used nonexistent --no-plot and failed argument parsing; corrected via temporary config, not new CLI behavior.
- Actual Isaac X5 collection CLI:2env/.1s with default Newton preset, exit0 in20.005s; saved40 samples under isolated PACE_ROOT. Actual fit CLI consumed that data with2env/max_iteration1, exit0 in28.009s; finite score0.821787, group RMSE0.480823rad/1.18844rad/s. This is an entry-point smoke, not a convergence claim.
- Integration startup fixes: minimal fixture now supplies valid action/observation configuration; base and wrapped env access supported; X5 task overrides only base height while preserving asset's existing legal joint defaults. Earlier task startup failed because replacement InitialStateCfg had reset calf defaults to zero outside limits. No numeric excitation, joint limits or collision geometry were changed.

No physical acceptance, full20s sweep, manual GUI validation, push or GitHub Issue closure. Two-axis review and final local commit handoff remain to complete this Implement stage.

### CR2 implementation review follow-up — 2026-11-17

User clarified that Newton automatic disablement is intentional. Configuration now warns before disabling separate dynamic friction and stripping ratio bounds; spec/ADR0008/usage and plan amendment record this approved supersession. Direct unsupported optimizer calls remain guarded. Collection and fitting validate exactly one actuator per controlled joint before parameter writes.

- Full suite: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q` — **90 passed, 2 upstream cmaes small-population warnings, 18.39 s**.
- Same targeted Pyright command recorded above — **0 errors, 0 warnings**.
- New regression coverage: empty/missing/duplicate actuator coverage; real Newton configuration warning, removal of ratio bounds for 49/61 base layouts and idempotent validation.
- Real X5 CLI: `.venv/bin/python scripts/pace/data_collection.py --task Isaac-Pace-Sevnce-X5-v0 --num_envs 2 --duration .1 --visualizer none physics=newton_mjwarp` — **exit0, 12.004 s**; isolated output root, headless, existing test-only EULA authorization and 120 s / 4 GiB watchdog. Preflight RAM15351MiB, GPU22633MiB free.
- Changed-file pre-commit: all applicable hooks passed after formatting; license hook skipped because the pre-existing template is absent. Direct `.venv/bin/python -m black` was unavailable; repository pre-commit supplied Black successfully.
- **Standards review:** no material findings; optional duplicated configuration assignments retained under the minimal-change constraint. Follow-up found no new problems.
- **Spec review:** initial two findings resolved. Newton rejection was superseded by explicit user clarification; aggregate actuator coverage was fixed. Independent reviewer confirmed no residual issue. Reviewers inspected code without running simulations.

These are Implement checks; formal Verify and user-owned physical/manual acceptance are not claimed complete.

Post-fix real Newton collection/fit smoke: `OMNI_KIT_ACCEPT_EULA=YES OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 .venv/bin/python tests/test_mixed_collection_fit.py newton smoke /tmp/pace-cr2-implement-newton-smoke` — exit0, 11.003 s, 2 environments/40 steps, both truth RMSEs zero. Same resource watchdog applied. Prior PhysX and optimization evidence remains unchanged; no need to repeat unchanged dynamics trials.

### User-requested collection simplification and throughput — Implement follow-up

**Changes:** `data_collection.py` names its chirp vector `sample_times`; values remain `arange(N)*step_dt` seconds, while recorded timestamps use the actual simulation counter. Endpoint-inclusive `linspace(0,duration,N)` has interval duration/(N-1), not the actual control dt. Mapping/packing only resolve named columns, with a typed record; task configs explicitly own unit scale, zero offset and no clip. Collection and fitting prepack commands; collection copies contiguous states into device buffers and gathers/transfers once. Finite checks include every environment, intermediate sample and final state before returning; termination stops immediately. Full-state buffers cost 8*(N+1)*B*J bytes, approximately 1.95 MiB for 8000 samples, 2 environments, 16 joints.

**Performance evidence:** original baseline commit `ecefbfe` cannot run unchanged (undefined `trajectory`, obsolete actuator target accessor). Temporary adapters preserve its preallocated buffers and per-step zeros/repeat commands while fixing these blockers. Same current X5 model/config/runtime is used for both loops. Timed scope includes command packing, buffer allocation, collection and final CPU transfer; excludes environment startup/reset, disk saving and plotting. Headless Newton, 2 environments, 400 samples, warm-up then 5 alternating repetitions; CUDA synchronized at timing boundaries. 120 s deadline / 4 GiB RAM watchdog; preflight 20026 MiB RAM / 22729 MiB GPU free.

| Comparison | Baseline median | Current median | Current / baseline | Data check |
| --- | --- | --- | --- | --- |
| Original three-field loop adapter, fewer outputs | 0.558168 s | 0.520894 s | 0.93322 | leg measurements match |
| Equivalent mixed five-field adapter | 0.572373 s | 0.526019 s | 0.91901 | all fields match |

Commands: `.venv/bin/python /tmp/pace-original-benchmark-runner.py newton perf-original` and `.venv/bin/python /tmp/pace-benchmark-runner.py newton perf2`. Full source, raw repetitions, assumptions and results are retained in `cr2-implement-results.json` for reproduction after temporary files disappear. Initial intermediate implementation was 4.8% slower in the mixed comparison; it was rejected and replaced by the contiguous-buffer implementation above. These measurements support no regression for the measured workload, **not** an unmodified baseline pass, arbitrary workloads, all-backend performance or end-to-end application speed.

**Regression checks:** `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q` — 91 passed, 2 existing upstream cmaes warnings, 20.87 s. Existing action-mapping test was first made to fail for old inverse-transform behavior, then passed with reordering-only behavior. New collector boundary test checks literal second timestamps, correct position/velocity/command alignment, another environment's transient/final NaN, clock reset, simulation close and immediate termination. Existing targeted Pyright command: 0 errors, 0 warnings. All applicable changed-file pre-commit hooks passed; license template exception unchanged.

Real backend smoke commands (with process-only EULA acceptance, OMP/MKL threads=2) use `tests/test_mixed_collection_fit.py <backend> smoke <output>`: Newton exit0/11.003 s; PhysX exit0/8.003 s; both 2 environments/40 steps and zero truth RMSE for both groups. Runtime fixture now uses the explicitly supported identity action configuration, preserving reordered action columns. Earlier nonidentity compensation tests are superseded by the user amendment.

**Review:** independent Standards and Spec reviewers found no remaining material issue. Spec reviewer inspected benchmark source/results and confirmed the limited performance claim above. Formal Verify remains a separate, user-authorized stage.

### Project-only Kitless CLI fix

User explicitly prohibited Isaac Lab source changes. The aborted external edit left that checkout clean on main; no external source was changed. Project collection and fit now use pure argparse registration in the existing shared helper, then existing preset resolution and launch_simulation. The fixed boundary is CLI parsing, not EULA acceptance; no production acceptance variable is injected.

- Red: isolated parser test rejected the old import of isaacsim from KitLauncher. Green: both scripts parse default Newton, explicit PhysX+Kit, device and option-like Kit arguments with isaacsim imports forbidden and EULA variable removed.
- `env -u OMNI_KIT_ACCEPT_EULA uv run python scripts/pace/data_collection.py --help`: exit0, no EULA prompt.
- `uv run python scripts/pace/data_collection.py --task Isaac-Pace-Anymal-D-v0 --num_envs 2 --duration .01 --visualizer none`, with EULA variable explicitly absent and temporary PACE_ROOT: exit0, 17.006s, four samples; default Newton used.
- Same short command plus `physics=isaacsim_physx`, using previously authorized process-only test EULA variable and separate temporary PACE_ROOT: exit0, 28.007s. Required Kit runtime still starts for this branch. Remote asset timeout fell back to local cache; not a startup-selection failure.
- Sequential runs, 120s/4GiB watchdog; preflight16164MiB RAM and22674MiB GPU free. GUI behavior and full-duration physical acceptance are not claimed.
- Full suite `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run python -m pytest -q`:92 passed,2 existing cmaes warnings,23.73s. Targeted Pyright0; applicable pre-commit hooks passed after formatting, pre-existing missing license-template skip unchanged.

Existing user edits to ANYmal/X5 configuration files were neither changed nor included in this fix.

Kitless fix two-axis review: Spec found no material compatibility issue; Standards found no material code issue and requested fuller helper-interface documentation. The shared-helper table now records defaults, in-place registration, return type and argparse duplicate-option behavior.

### fit.py / cma_es.py throughput follow-up

User requested the same pre-implementation ecefbfe comparison and readable/extensible code as collection. `fit_reference` now keeps timestamps on CPU, copies contiguous full states and calls `tell` on completed trajectory chunks. The optimizer retains single-sample calls, validates chunks before mutation, computes float64 group errors in bulk, transfers candidates/statistics in batches and snapshots best-result settings. Initialization, shared-delay cadence, group objective and paired-output rules remain unchanged. Extra full-state buffers require8*(N+1)*P*J bytes; all samples/environments and post-step final states are validated before scoring/evolution, while termination remains immediate.

Performance: CUDA, 12 position joints, 2 candidates, 400 samples, 3 generations, one warm-up pair followed by five alternating measured pairs. Synchronization occurs at timing boundaries. Exact scripts and raw durations are retained in cr2-implement-results.json.

| Workload | Baseline median | Current median | Current / baseline |
| --- | --- | --- | --- |
| Exact ecefbfe CMA class vs current class | .200980 s | .032495 s | .161683 |
| ANYmal Newton fit replay adapter | 1.430824 s | 1.296856 s | .906370 |

CMA measurement includes tell/evolve/finished/close, real TensorBoard logging and saves, excluding constructors. Original summed-joint scores are divided by12 only for comparison to the approved current mean objective; all generation scores match within declared tolerance. Raw timings have noticeable host/I/O variation, so the median improvement is workload-specific, not a guaranteed speedup factor.

The real fit adapter uses the original ecefbfe step loop and unmodified old tell, but shares current parameter initialization and evolve with the new path to support installed writer APIs and maintain approved normalized/measured-frame paired results. It includes reset, parameter writes, simulation, scoring, generation evolution and close/saves; excludes environment/optimizer construction and reference collection. Scores (rtol5e-5/atol1e-6), best parameters and best trajectories match. This is **not** an unchanged ecefbfe complete application benchmark or a universal all-backend claim. The actual original CMA class is evaluated separately above.

Commands: `uv run python /tmp/pace-cma-benchmark.py`; `uv run python /tmp/pace-fit-benchmark-runner.py newton fit-perf`. Real fit experiment exit0 in31.008s, two environments,120s/4GiB watchdog. GPU-only CMA test completed normally without simulator launch. Preflight RAM15533MiB/GPU22659MiB free; no concurrent simulations.

Two-backend mixed regression: existing bounded runtime `tests/test_mixed_collection_fit.py <backend> optimize <output>` invoked sequentially,4candidates/20generations/40steps and120s/4GiB watchdog. Newton exit0/16.005s, score .00856880378→.00014878822 (98.26% lower); PhysX exit0/11.003s, .00856707059→.00007651021 (99.11% lower). Truth beats perturbation in both groups and saved response errors recompute correctly. Process-only EULA setting remains explicitly authorized for these tests.

New public-boundary tests: hand-computed batched mixed loss and matching best trajectory, invalid batch rejection before mutation; real optimizer with deterministic external environment verifies pre-step scoring and rejects transient/final NaN in another environment, immediate termination and clock resets before evolution or output creation. Existing single-step and partial-failure tests remain.

Independent Standards and Spec reviewers found no material issue. They requested explicit batch/memory documentation and bounded benchmark claims, recorded above. User changes to collection, task configs and the fit data path are preserved and excluded from the performance patch.

Final checks: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run python -m pytest -q` —94passed,2 existing upstream cmaes warnings,26.60s; targeted Pyright0. Formatting hooks corrected test formatting on the first pass; applicable changed-file hooks passed on recheck (existing missing license-template skip remains).
