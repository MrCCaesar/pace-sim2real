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
