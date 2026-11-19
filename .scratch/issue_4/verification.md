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

### User-authorized final normalization and release

Included current user edits: task-name collection/fit directories, task data_dir=chirp_data.pt, current trajectory values/directions, removal of unused PaceCfg.robot_name, fitting defaults cuda/no viewer. Updated usage/tutorial examples; normalized task configuration formatting and annotated dynamic Isaac Lab configclass APIs without changing behavior. Added only the legitimate ANYmal joint abbreviation haa to codespell's word exceptions.

Final checks:94tests passed in25.70s with2 known upstream cmaes warnings. Pyright0 includes both task configs. All applicable changed-file hooks pass; pre-existing missing license template remains explicitly skipped. Both final review axes found no blocker.

New-directory real CLI roundtrip, with EULA variable absent and PACE_ROOT=/tmp/pace-kitless-anymal: ANYmal collection2env/.01s exit0/16.005s; fit2env/1generation with no device/viewer flags exit0/16.005s (CUDA/default no viewer). These are entry/path/default software checks, not convergence or physical acceptance. Full commands/results retained in cr2-implement-results.json.

User explicitly authorized commit, push and closure of corresponding issues. Closeout covers parent#4 and implementation children#5–#13 under the latest approved amendments, including config-owned action transforms and Newton warn/disable ratio semantics. Earlier issue wording is superseded by recorded user decisions. Manual GUI/camera/window-manager evidence and user-owned physical-model validation are not claimed by this release; historical status records remain intact.

Release receipt: code commit5ace954 successfully pushed to origin/main. GitHub parent#4 and children#5–#13 closed as completed per explicit user instruction; each CLOSED state and closedAt was read back and retained in cr2-implement-results.json.

### Post-release plot_trajectory refactor

User requested refactoring against current code. Updated only the plot consumer, its existing test file and documentation: task-based default/--task selection with legacy --robot_name compatibility; current/historical run discovery requiring requested result/progress files; clear paired-record validation; separated error calculation, summary, trajectory rendering and progress rendering. No simulator/optimizer/physical behavior changed; previous issue closure remains untouched.

Tests: the new current-task/latest-complete CLI test first exposed the old default-directory failure. Final `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run python -m pytest -q`:102passed,2 existing cmaes warnings,26.35s. Targeted Pyright for plot script/test file:0errors0warnings. Applicable changed-file pre-commit hooks passed after formatting; pre-existing absent license template remains skipped. Coverage includes current default/latest incomplete runs, explicit historical-folder fallback, namespaced task and legacy alias/conflict, pure-leg and mixed figure values, generation score curves, means-only diagnostics/conflicts, missing desired/candidate fields, invalid time and tampered score.

Actual artifacts: `MPLBACKEND=Agg uv run python scripts/pace/plot_trajectory.py --task Isaac-Pace-Anymal-D-v0 --plot_trajectory` exited0 using existing real fit output. Agg emits its expected noninteractive show warning. Existing Newton and PhysX controlled mixed best_result.pt records passed load_result and produced two figures each, with scores .00014878822058435735 and .00007651021209868479. Figures saved only under /tmp/pace-<backend>-refactored-plot-<group>.png. No simulations rerun. Changes remain uncommitted; no push or issue operations were requested/performed for this follow-up.

### Fitting performance against 912c7a6

The baseline uses the exact fit entry point and optimizer sources from 912c7a6. Both versions run the same X5 Newton MJWarp CUDA task, two environments, identical measured chirp data and seeds, headless, epsilon=0, default checkpoint interval, and full TensorBoard diagnostics. Each timing is the median of three fresh processes per variant, run sequentially with interleaved variants. The fit timer starts at fit_reference and ends after optimizer.close, with CUDA synchronized at these boundaries. The entry timer covers fit.main, including scene creation and teardown; Python imports before main are excluded.

| X5 workload | Scope | Baseline seconds | Optimized seconds | Time reduction |
| --- | --- | ---: | ---: | ---: |
| 400 samples, 11 generations | Fit through final persistence | 6.955 | 5.822 | 16.29% |
| 400 samples, 11 generations | Entry including scene startup | 14.150 | 14.119 | 0.22% |
| All 8,000 samples, 3 generations | Fit through final persistence | 29.680 | 24.755 | 16.59% |
| All 8,000 samples, 3 generations | Entry including scene startup | 35.207 | 30.464 | 13.47% |

For the short workload the observed scene creation times ranged from 2.81 to 9.80 seconds. The short-workload entry timer did not establish a 10% reduction. Every X5 run produced equal loaded fit configuration, evaluated best record and periodic means, and identical values and steps in all 61 histogram and 128 scalar tags. Timing raw data and the comparison driver are in the temporary experiment directory `/tmp/pace-opt-912c7a6-zmMWqiU9/`. The comparison covers loaded output values and steps on the same hardware. Each run has its own event wall times.

An additional ANYmal Newton run (two environments, 40 samples, two generations, position-action scale 0.75 and offset 0.1, progress saving enabled) produced matching configuration, best result, means, population history and all 152 TensorBoard tags. This was a pure-position compatibility check. The unchanged suite passed with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q --tb=short` (104 passed, four existing cmaes warnings). Targeted Pyright reported zero errors; the optimizer Ruff check, formatting of both changed Python files and `git diff --check` passed.

## CR3 Verify — 完成，2026-11-18

验收对象为提交 `d8e0480` 和 #14–#16。使用 `git archive d8e0480` 导出独立源码，仅共享本机机器人资产及项目虚拟环境。X5 使用 Newton、RTX A5000、2 个环境、无实时查看器，步长 0.0025 s。仿真串行执行，启动前可用 RAM 18175 MiB、显存 22618 MiB。

| 条件 | 结果与证据 |
| --- | --- |
| A1 · 入口与最新运行 | 通过。固定参数采集、显式回放及最新运行回放均成功。较早完整运行、较新缺文件运行和录像目录并存时，裸 `--fit_result` 退出码为 1，报告最新拟合运行缺失文件的完整路径。 |
| A2 · 参数兼容与映射 | 通过。分别逆序排列真实 X5 结果中的腿、轮关节及其配对轨迹，独立打乱 61 项具名参数后再回放，两组响应与原最佳候选逐样本最大差均为 0。契约测试覆盖名称和物理设置冲突、旧双时步、纯腿与混合、Newton 干摩擦及 PhysX 有／无摩擦比例。 |
| A3 · 初态、误差与曲线 | 通过。X5 首帧腿实测与期望最大差为 0.13273692 rad，实测轮速最大绝对值为 0.04865251 rad/s。回放首帧与实测一致。手算样例得到位置 RMSE 2 rad、轮速 RMSE 5 rad/s。Agg 下逐一核对 16 个具名关节的图例和全部横纵坐标，有实测时每关节三条曲线，仅命令时两条。 |
| A4 / Q7 · 原轨迹复现与独立预测 | 通过。取移动中的 32 帧做一代拟合，同轨迹最大绝对差为位置 0 rad、轮速 0 rad/s，分别满足 0.0001 rad、0.001 rad/s 的短程复现容差。独立采集 4–8 Hz 短扫频，得到腿位置预测 RMSE 0.020504419 rad、轮速预测 RMSE 1.617103 rad/s。另行注入测量偏差后，最大误差达到 1 rad 和 3.2122221 rad/s，仍正常播放、绘图和保存。 |
| A5 · CLI 与文件保护 | 通过。覆盖裸回放选项紧跟 Hydra 预设、显式另存、文件轨迹与扫频参数互斥。默认回放保留原采集文件字节。显式输出指向拟合结果、轨迹输入、自定义拟合参考文件和常规采集文件时均被拒绝。 |

**命令与结果。** 以下命令在导出的源码根目录执行，`$PY` 为项目虚拟环境的 Python，`$EVIDENCE` 为本机临时目录 `/tmp/pace-cr3-verify-fPGxka9T`。

```bash
PYTHONPATH="$PWD/src" PACE_RUN_REPLAY_INTEGRATION=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg timeout -k 5 340 "$PY" -m pytest -q -s --tb=short --basetemp="$EVIDENCE/test-data"
uvx --offline pyright --pythonpath "$PY" scripts/pace src/pace_sim2real/utils tests/test_fit_replay.py tests/test_mixed_collection_fit.py
ruff check scripts/pace/data_collection.py src/pace_sim2real/utils/fit_replay.py tests/test_fit_replay.py
ruff format --check scripts/pace/data_collection.py src/pace_sim2real/utils/fit_replay.py tests/test_fit_replay.py
```

pytest **126 passed**（110.11 s），4 条既有 cmaes 除零告警。Pyright 为 0 错误、0 警告，Ruff 检查与格式通过。补充探针及其日志在同一临时目录，分别为 `check_reordered.py` / `supplement.log` 和 `check_plots.py` / `plots.log`。

**证据边界。** 本轮从实施阶段保留的 ANYmal / Isaac Sim PhysX 单一 dt 结果及回放文件独立复算，61 项参数、12 帧、三字段输出，位置最大绝对差为 0 rad。本轮未重新启动 PhysX。独立预测结果为仿真数据；人工 GUI 体验及实机预测质量由用户验收。

## CR4 Verify · #17–#21 · 任意关节组合

用户批准进入 Verify。基点 `6a1d8c9`，验证对象为当前工作区。Issue #4 与 #17–#21 的正文及评论已回读，验收依据为已批准的 CR4 规格、接口、ADR 0011–0013 和子工单。实际测试使用 X5、Newton MJWarp、CUDA、2 个环境、无查看器，仿真串行执行。启动时约有 17 GiB 可用内存和 22,625 MiB 可用显存。软件复现误差与独立工况预测误差单独统计。

### 运行方法与证据

以下命令从项目根目录运行。临时证据目录为 `/tmp/pace-cr4-verify.p5l4Rpi6`，含运行日志、临时探针、七个 v3 结果、事件和轨迹文件。探针只在验证进程中读取运行状态。

```bash
EVIDENCE=/tmp/pace-cr4-verify.p5l4Rpi6
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 MPLBACKEND=Agg OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export PACE_RUN_REPLAY_INTEGRATION=1 PACE_RUN_SUBSET_INTEGRATION=1
.venv/bin/python -m pytest -q --tb=short -k 'not test_x5_subset_fit_and_replay and not test_x5_short_fit_replays'
.venv/bin/python -m pytest -q --tb=short --basetemp="$EVIDENCE/sim" tests/test_fit_replay.py -k 'test_x5_subset_fit_and_replay or test_x5_short_fit_replays'
.venv/bin/python "$EVIDENCE/all_subsets.py" "$PWD"
```

### 子工单验收证据

| 工单 | 已核对的行为 |
| --- | --- |
| #17 | 穷举 X5 的 65,535 个非空子集，每组内反序排列，用各不相同的界限和尺度逐列核对三项机械量、仅位置偏置、共享延迟和可选 PhysX 摩擦比例。全部通过。常规契约测试另覆盖 `None`、`[]`、声明与数据不符、缺字段、时钟和非有限输入。 |
| #18 | X5 默认完整机体上采用四个逐腿驱动组。七种 v3 场景分别为四份单腿、单轮、跨腿混合、单位置。部分通道参数和组内默认偏置通过实际仿真读回；跨腿两代的两环境候选延迟依次为 [6,4]、[4,6] 步。检查了全部关节的惯量、黏性和干摩擦、四个驱动组的延迟缓冲及各通道偏置。 |
| #19 | 对七份 v3 文件独立复算评分与原单位 RMSE，逐项检查两代 TensorBoard 直方图样本数、均值和最佳值标签，核对获胜代的参数与记录、代 0 均值与快照。离线图的关节标题、单位、图例、时间及期望/实测/预测三条曲线与文件逐点相符。纯速度记录有 4 项参数、纯位置单关节有 5 项，各自只报告有效误差。 |
| #20 | 同集合组内乱序的数据按本次文件列序回放。在一条有独立仿真测量值的 20 帧扫频上，将其余三轮保持目标从 0.4 改为 0.7 rad/s，并反转位置列序。检查到每个变动轮的名称、原值、新值和单位，初态、全部 16 个动作列逐步正确。离线复算位置 RMSE 为 0 rad，速度 RMSE 为 2.2367431e-8 rad/s，与终端一致。此处参考测量由同一候选在原保持工况仿真生成。 |
| #21 | 无文件回放用记录的关节名对 FL 生成 2–4 Hz 扫频。20 步的三路位置和一路轮速逐点符合独立计算的中心、幅度和方向，其他 12 路均取实际任务保持目标。非对称与仅速度回放通过；无对应系数、输出保护及文件与显式扫频参数互斥均有负例。 |

```bash
.venv/bin/python "$EVIDENCE/artifacts.py" "$PWD"
bash "$EVIDENCE/supplement.sh" "$EVIDENCE" "$PWD"
.venv/bin/python "$EVIDENCE/trajectory_check.py"
uvx --offline pyright --pythonpath .venv/bin/python scripts/pace/{data_collection,fit,plot_trajectory}.py src/pace_sim2real/{optim/cma_es,utils/{subset_control,collection_contracts,fit_replay}}.py
.venv/bin/ruff check scripts/pace/{data_collection,fit,plot_trajectory}.py src/pace_sim2real/{optim/cma_es,utils/{subset_control,collection_contracts,fit_replay}}.py tests/test_fit_replay.py
git diff --check
```

定向 Pyright 返回 0 错误、0 警告，定向 Ruff 通过。两组互斥的 pytest 命令合计 147 项通过、3 项失败。七个子集集成用例均通过。原生 MuJoCo 两项失败来自输出路径的工作区既有修改；在隔离目录用基点原脚本、原测试和同一机器人资产复跑，两项通过。另一个全量 v2 用例只生成 `chirp_data.pt`，当前 X5 任务配置读取 `lab_0.1_10Hz_kp600_kd10_chirp_data.pt`，因缺文件在拟合入口退出。

在隔离测试数据目录中增加一个从任务配置文件名到 `chirp_data.pt` 的符号链接，原样运行同一个全量 v2 用例，通过。32 帧、61 个参数，同轨迹位置和轮速最大绝对差均为 0；另一条独立全量轨迹的预测 RMSE 分别为 0.018491455 rad 和 1.6192978 rad/s。该结果亦通过离线加载和绘图，位置、速度分别有 12、4 幅关节子图。当前工作区原样运行的三项失败仍单列报告。

对原生 MuJoCo 进行隔离归因时，使用 `git archive HEAD scripts/pace config tests/test_mujoco_collection.py`、挂载当前 `src` 资产，再运行 `pytest -q tests/test_mujoco_collection.py -k 'cli_saves_short_run or plot_failure_happens_after_save'`。实施基点为 `6a1d8c9`。两项断言均要求旧路径 `data/x5_sim/chirp_data.pt`，工作区的原生入口写入 `data/Isaac-Pace-Sevnce-X5-v0/mujoco_0.1_10Hz_kp1500_kd30_chirp_data.pt`。

对 PhysX 的检查覆盖参数布局及解码。执行 `.venv/bin/python "$EVIDENCE/ratio.py" "$PWD"`，使用四份 v3 记录的关节与参数构成单腿、单轮、跨腿和单位置输入，在 CPU 上追加辨识用的摩擦比例并打乱参数顺序，逐关节核对动摩擦等于静摩擦乘对应比例。实际部分关节仿真采用 Newton MJWarp。所有轨迹来自合成输入或仿真采样，真实机器人跟踪精度与碰撞模型保留给实机验收。

### 四条腿独立采样、拟合与回放

命令为 `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg .venv/bin/python "$EVIDENCE/same_hold.py" "$PWD"`。每条腿分别用自己的候选参数在四驱动组 X5 上施加 2–4 Hz 扫频，保存 20 帧仿真测量，其他三条腿维持相同保持工况。随后用本腿的测量重新拟合两代，对新最佳候选做同轨迹回放。每份记录均有三列位置、一列速度、16 个辨识参数。表中比较相同候选、相同输入的步前响应，阈值分别为 0.0001 rad 和 0.001 rad/s。

| 独立记录 | 位置最大绝对差（rad） | 轮速最大绝对差（rad/s） |
| --- | ---: | ---: |
| FL | 0 | 5.9604645e-08 |
| FR | 1.8626451e-09 | 2.3841858e-07 |
| RL | 0 | 1.1920929e-07 |
| RR | 1.8626451e-09 | 1.1920929e-07 |

**结论。** #17–#21 的 CR4 软件验收通过。工作区全量回归仍有三项文件路径断言或输入配置失败，其归因与隔离复跑结果见上。Verify 交付仅更新本地阶段文档。

### Verify 后续 · 统一采集和拟合的文件名

用户选定按来源使用稳定文件名。Isaac Lab 固定采集与默认拟合共用 `data/<规范化任务名>/chirp_data.pt`，X5 原生入口写入同一任务目录的 `mujoco_chirp_data.pt`。拟合其他文件仍可覆盖 `env.sim2real.data_dir`。两种采集文件均纳入 X5 回放的输出保护。README、使用示例和原生回归断言已同步。

全套回归采用临时目录，启用原有及子集回放测试。补充检查在单独的 `PACE_ROOT` 采集 0.04 秒 MuJoCo 轨迹，并用明确指定的原生文件名运行一代 Newton 拟合。命令如下。

```bash
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 MPLBACKEND=Agg OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
PACE_RUN_REPLAY_INTEGRATION=1 PACE_RUN_SUBSET_INTEGRATION=1 .venv/bin/python -m pytest -q --tb=short
# 以下命令使用独立临时目录作为 PACE_ROOT 与工作目录，REPO 为源码绝对路径
"$REPO/.venv/bin/python" "$REPO/scripts/pace/data_collection_mujoco.py" --duration .04 --no-visualize
"$REPO/.venv/bin/python" "$REPO/scripts/pace/fit.py" --task Isaac-Pace-Sevnce-X5-v0 --num_envs 2 --visualizer none env.sim2real.data_dir=mujoco_chirp_data.pt env.sim2real.cmaes.max_iteration=1
```

结果：全套 150 项通过（317.43 秒，4 条既有 CMA 警告），含此前失败的三项。原生输出/绘图两项补测通过。临时目录下的 16 帧 X5 原生采集成功，以任务相对文件名拟合后，结果内的时间、实测与期望共五个张量和原文件一致。两种任务配置的默认输入均为 chirp_data.pt。六份原有实验文件的 SHA-256 检验通过。

本次涉及的 Python 文件通过 Ruff，采集、拟合入口及路径模块的 Pyright 检查为零错误。将共享任务配置纳入 Pyright 时有 5 项既有 Isaac Lab 类型诊断；用相同环境核对基点该文件为 6 项。

## CR5 离线采集数据滤波验收

**结论。** 用户批准进入 Verify 后，在当前工作区重新执行 CR5 专项 CPU 回归，24 项通过，0 项跳过（1.44 s）。[CR5-A1–A4](spec.md#cr5--离线采集数据滤波--specifyapproved) 全部通过。

| 条件 | 本轮证据 |
| --- | --- |
| A1 · 文件和关节列 | 纯位置、纯速度、混合及显式空列组用例通过。实际 X5 默认 20 Hz 与显式 25 Hz 输出经拟合加载器读回，均为 8000 帧、12 列腿位置和 4 列轮速。两份输出均与原始字典字段及顺序、形状、dtype 一致，时间与指令逐元素相等。全部 16 列测量在转换为原 dtype 后分别与独立逐列 SciPy 滤波结果逐元素相等。另在副本中仅改变一个腿关节的一个输入样本，只有对应输出列变化。 |
| A2 · 合成信号 | 对 0.1、1、4、8、10 Hz 五个频点，中段最大幅值损失为 0.37031%（限值 1%），最大相位折算时差变化为 0.01644 ms（限值 0.1 ms）。中段 RMSE 从 0.16079 降至 0.03580，为原值的 22.27%；首尾 RMSE 从 0.16222 降至 0.04327，为原值的 26.67%（分别要求 ≤35%）。以上数值从本轮 pytest 写出的输入和滤后文件按 Research 的时间窗重新计算。 |
| A3 · 指定 X5 记录 | 四阶 20 Hz 下，腿位置和轮速在入选频点的最大幅值变化分别为 0.159%、0.151%（限值 1%）。各组中 ≥30 Hz 能量的最小降幅分别为 47.66、47.86 dB（要求 ≥40 dB）。腿位置首帧、末帧的最大绝对变化分别为 0.00225、0.00986 rad；轮速分别为 0.01093、0.35371 rad/s。原件和临时输入副本校验均得到研究指定的 SHA-256 `8ab1ca9e3a430c0b4ad7fa951cf53dbc352d8e45263b6ee085bc300aa25732d8`。 |
| A4 · 命令与错误处理 | 两个独立进程执行 README 中默认参数和显式四阶 25 Hz 的滤波命令，分别生成同目录的 `*_filtered.pt` 和指定文件 `x5_25Hz.pt`。测试还覆盖一、二、三阶、截止频率及阶数错误、时间与张量无效、过短输入、已有文件及输入别名、模拟写入失败后的清理。 |

**执行命令。** 工作目录为项目根目录。命令行复验使用已安装的项目环境，将样例复制到临时目录。两个输出均调用 `load_reference_data`，按 X5 的完整关节序和 0.0025 s 间隔核对。

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q -s tests/test_filter_chirp_data.py
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 UV_NO_SYNC=1
task=Isaac-Pace-Sevnce-X5-v0
trial=/tmp/pace-cr5-verify-vhsouwsJ
record=$trial/mujoco_0.1_10Hz_kp1500_kd30_chirp_data.pt
cp data/$task/mujoco_0.1_10Hz_kp1500_kd30_chirp_data.pt "$record"
uv run python scripts/pace/filter_chirp_data.py "$record"
uv run python scripts/pace/filter_chirp_data.py "$record" --cutoff_hz 25 --order 4 --output "$trial/x5_25Hz.pt"
sha256sum "$record" "data/$task/mujoco_0.1_10Hz_kp1500_kd30_chirp_data.pt"
```

`uv lock --check --offline`、`.venv/bin/ruff check scripts/pace/filter_chirp_data.py tests/test_filter_chirp_data.py`、相同文件的 `.venv/bin/ruff format --check` 和 `uvx --offline pyright --pythonpath .venv/bin/python scripts/pace/filter_chirp_data.py tests/test_filter_chirp_data.py` 均通过。

**边界与交付。** 真实数据缺少无噪声参考，本轮核对到拟合数据加载入口，未运行参数优化或仿真。提交时已显式纳入 `tests/test_filter_chirp_data.py`，提交前复跑 24 项专项测试全部通过。
