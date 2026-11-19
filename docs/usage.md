# Basic Usage

This section provides a brief overview of the main PACE scripts and their most important command-line arguments. It is intended as a quick reference for running common workflows, without going into full implementation or theory details.

The typical workflow consists of:

1. Collecting excitation data from the robot or simulation
2. Running parameter identification using CMA-ES
3. Visualising and analysing the resulting trajectories and scores

---

## Overview of main scripts

| Script               | Purpose                                                                 |
| -------------------- | ----------------------------------------------------------------------- |
| `data_collection.py` | Collects excitation data using a chirp signal for system identification |
| `fit.py`             | Runs the PACE parameter identification using CMA-ES                     |
| `plot_trajectory.py` | Visualises the resulting trajectories and optimization progress         |

---

## 1. Data collection

```bash
python scripts/pace/data_collection.py
```

This script generates excitation trajectories using a chirp signal and records the corresponding robot states for later parameter identification.

### Common arguments

| Argument          | Description                                   |
| ----------------- | --------------------------------------------- |
| `--num_envs`      | Number of parallel simulation environments    |
| `--task`          | Name of the task / robot configuration        |
| `--min_frequency` | Minimum frequency of the chirp signal (Hz)    |
| `--max_frequency` | Maximum frequency of the chirp signal (Hz)    |
| `--duration`      | Duration of the chirp signal in seconds       |
| `--device`        | Simulation device: `cpu`, `cuda`, or `cuda:N` |
| `--visualizer none`      | Run without rendering                         |

### Example

```bash
python scripts/pace/data_collection.py \
  --task Isaac-Pace-Anymal-D-v0 \
  --num_envs 1 \
  --min_frequency 0.1 \
  --max_frequency 10 \
  --duration 20 \
  --device cuda
```

---

## 2. Parameter fitting

```bash
python scripts/pace/fit.py
```

This script performs system identification using CMA-ES to optimize physical parameters such as armature, damping, friction, bias, and delay.

### Common arguments

| Argument     | Description                            |
| ------------ | -------------------------------------- |
| `--num_envs` | Number of simulation environments      |
| `--task`     | Name of the task / robot               |
| `--device`   | Simulation device                      |
| `--visualizer none` | Disable rendering for faster execution |

### Example

```bash
python scripts/pace/fit.py \
  --task Isaac-Pace-Anymal-D-v0 \
  --num_envs 2 \
  --visualizer none
```

---

## 3. Plotting trajectories and scores

```bash
python scripts/pace/plot_trajectory.py
```

This utility inspects the paired best candidate and optionally plots trajectories or generation scores. It defaults to task `Isaac-Pace-Anymal-D-v0`. Without `--folder_name`, it selects the latest run containing all requested files, skipping incomplete runs. Current `logs/pace-sim2real/<task>/` directories take precedence; historical `logs/pace/<task>/` directories remain readable.

### Common arguments

| Argument            | Description                                     |
| ------------------- | ----------------------------------------------- |
| `--task` | Task ID, matching the fitting command; namespace prefixes accepted |
| `--folder_name`     | Explicit run directory, otherwise latest complete requested output |
| `--result_name` | Paired evaluated result (default `best_result.pt`) |
| `--mean_name` | Distribution mean diagnostics only; not a trajectory selector |
| `--robot_name`      | Legacy directory selector; mutually exclusive with `--task` |
| `--plot_trajectory` | Plot the optimized joint trajectories           |
| `--plot_score`      | Plot the score over iterations                  |

### Example

```bash
python scripts/pace/plot_trajectory.py \
  --folder_name 24_03_12_14-32-10 \
  --task Isaac-Pace-Anymal-D-v0 \
  --plot_trajectory
```

---

## Notes

* All scripts share common Isaac Lab launcher arguments such as `--visualizer none`, `--livestream`, and `--rendering_mode`.
* For full argument lists, run any script with:

```bash
python script_name.py --help
```

More advanced workflows and in-depth explanations are covered in the Examples and Guides sections.


## Mixed position/velocity identification

Use task `leg_order` for position channels and `wheel_order` for velocity channels. A legacy pure-leg `joint_order` is accepted. Collection saves CPU `time` (float64), `dof_pos`/`des_dof_pos` (float32 radians), plus `dof_vel`/`des_dof_vel` (float32 rad/s) for mixed tasks. Measurements and issued pre-delay targets share actual pre-step sample times. Simulation resets or nonfinite states abort the run. Use `--plot` to display collected responses; use `--visualizer none` for headless runs on the installed Isaac Lab version.

Reference declarations belong in PaceCfg: `reference_leg_order`/`reference_wheel_order` (each group independently uses None for full task order, [] for no columns, or exact joint names in file order), `reference_bias_model="feedback_and_measurement"`, `reference_delay_mode="command"` (must match the task), `time_mode="strict"`, and `legacy_sample_dt=None`. Fitting requires `decimation=1`. Each reference row advances one physics step, so strict time intervals must match `sim.dt` in seconds. Historical linspace files require `time_mode="legacy_index"` and an explicit true interval; no automatic resampling. Old native data using measurement-only bias is unsupported and must be recollected. No metadata sidecar is created. Declaring a file's semantics does not prove that declaration is correct.

For J=L+W joints, parameters are armature[J], damping[J], friction[J], leg encoder bias[L], one delay; optionally append PhysX friction ratios[J]. X5 has61 base parameters, a12-leg task49. Newton warns and disables separate dynamic-friction identification during configuration validation, removing its ratio bounds before constructing CMA. Delay is floored to integer physics steps; the configured drive capacities must cover its upper bound. Wheel initial speed comes from the first measurement; missing wheel angle/leg velocity comes from task defaults and is recorded in the result.

CMA settings `position_error_scale` and `velocity_error_scale` each accept a positive finite scalar (default 1 rad or 1 rad/s) or a list of positive finite values. A list must have one value per joint in `leg_order` or `wheel_order`, respectively. The group objective averages each joint’s MSE divided by its squared scale. Group weights default to 1 and are normalized across present groups. Raw group RMSE is reported in rad or rad/s. These scales are not accuracy thresholds. Population must be at least2 (the resource-safe default); small populations can produce upstream CMA warnings. Controlled validation uses4, not full-scale training.

The primary artifact is `best_result.pt`, (v2 for full tasks with position channels, v3 for partial or velocity-only fits): evaluated global-best parameters, matching measured-frame responses, group errors, candidate identity, reference tensors, original/effective time, configuration and actual delay. The joint orders appear at the top level. Settings record one `dt` in seconds and compact backend and solver identifiers for comparing runs. TensorBoard records the updated CMA distribution mean in physical parameter units at every generation, under tags such as `1_Armature/mean_<joint>` and `0_Delay/mean`. The shared delay is expressed in physics steps. The same mean is saved to `mean_*.pt` at the configured save interval. Plotting loads the paired record and recomputes errors; it does not subtract position bias twice or pair a historical mean with a latest trajectory. Older unpaired results cannot establish correspondence and are rejected for trajectory comparison. `--mean_name` can still inspect mean parameters alone. Select the run directory and the same task log name used by fitting when invoking the plot script.

Software tests establish behavior on bounded minimal models. Successful execution does not certify collision geometry, full-model physical fidelity or unique identification of all parameters.

PACE collection and fitting send absolute targets: configure actions with `scale=1.0`, `offset=0.0`, `clip=None`, and `use_default_offset=False`. Action mapping only reorders named columns; it does not inspect or undo task transforms. Collection timestamps are seconds (`sample_index * env.step_dt`), with samples before each step; the last sample precedes `duration` by one control interval. Commands and device buffers are prepared once, then completed measurements are transferred to CPU. Numerical validity is checked across all buffered states, including the final state, before saving.

Collection and fitting register their runtime CLI flags locally, without loading Isaac Sim. Newton therefore needs no Kit EULA variable merely to parse arguments or start a kitless run. `physics=...` and `--visualizer`/`--viz` remain Isaac Lab preset selectors; `launch_simulation` starts Kit only when the resolved physics, renderer or viewer requires it. Explicit Isaac Sim PhysX or Kit visualization still requires the installed runtime and its license acceptance.

Fitting prepares commands once, keeps timestamp checks on CPU and reuses device state buffers across generations. On Newton CUDA, compatible stock joint action terms replay their processing and target writes through CUDA graphs between resets. Python PACE actuators and environment stepping retain their normal ordering. Shared reference measurements are converted once for double-precision scoring. Scoring occurs after a complete valid rollout; automatic termination still stops immediately. `CMAESOptimizer.tell` accepts both individual `[population, joints]` samples and `[population, samples, joints]` chunks, with the same bias and group-loss semantics. Full-state fitting buffers require 8*(samples+1)*population*robot_joints bytes in addition to optimizer/reference storage.

Isaac Lab collection writes `data/<task-name>/chirp_data.pt`; fitting reads `data/<task-name>/<data_dir>`, with `data_dir` defaulting to `chirp_data.pt`. The native X5 collector writes `mujoco_chirp_data.pt` in the same task directory. Select it for fitting with `env.sim2real.data_dir=mujoco_chirp_data.pt`. Namespace prefixes are removed from task names. Existing files are not moved automatically. Fitting defaults to `--device cuda` and no visualizer; use `--device cpu` or `--visualizer newton_gl` to override. These defaults do not change the selected physics preset.

Plotting validates paired v2/v3 candidate metadata, joint groups, time, measured/desired/fitted tensor shapes and finite values, then recomputes stored errors. Invalid records produce a diagnostic instead of a late plotting failure. `--plot_score` requires a run containing `progress.pt`, generated with `cmaes.save_optimization_process=True`. `--mean_name` remains parameter-only diagnostics and cannot be combined with `--result_name` or `--plot_trajectory`; no bias is subtracted again from saved fitted positions.


## Replay a fitted candidate in Isaac Lab

Run these commands from the same working directory used for fitting. Set the task once:

```bash
task=Isaac-Pace-Sevnce-X5-v0
uv run python scripts/pace/data_collection.py --task "$task"                         # fixed-parameter collection
uv run python scripts/pace/data_collection.py --task "$task" --fit_result --plot     # latest fit, generated chirp
uv run python scripts/pace/data_collection.py --task "$task" --fit_result runs/x5/best_result.pt --duration 5 --max_frequency 4 --plot
```

The bare `--fit_result` selects the newest timestamped fitting run under `logs/pace-sim2real/<task>/`. If that run has no `best_result.pt`, the error identifies the run. An explicit result path selects that candidate directly. Replay requires a paired v2 or v3 result with a single `settings.dt`, compatible physics, and matching leg and wheel names. Within each group the fitted parameters are reordered by name.

Use a separately collected trajectory to evaluate prediction on different commands:

```bash
uv run python scripts/pace/data_collection.py --task "$task" --fit_result \
    --trajectory_file validation/x5_chirp.pt --output validation/x5_replay.pt --plot
```

The trajectory uses its declared reference leg and wheel column order and sampling interval. Supply either a trajectory file or explicit chirp settings. With a file, the simulation starts from its first measured leg positions and wheel speeds. The terminal reports position prediction RMSE in rad and wheel-speed prediction RMSE in rad/s for tasks with wheels. Each metric compares the new response to the supplied measurements. The plot adds the commanded trajectory for context.

Replay writes a three- or five-tensor response only when you give `--output`. To check reproduction, use the original fit trajectory and compare the output with the winning candidate's saved simulation response. The short reproduction test uses maximum absolute differences of 0.0001 rad and 0.001 rad/s. Playback, plotting, and saving remain available at any finite tracking error.

### Fitting and replaying selected joints

Keep the complete robot in `leg_order` and `wheel_order`. Bounds and list-valued scales follow full task order. The fitter selects them by name. A speed-only file contains `time`, `dof_vel` and `des_dof_vel`. For a single front-left wheel, use these commands.

```bash
task=Isaac-Pace-Sevnce-X5-v0
groups=('env.sim2real.reference_leg_order=[]' 'env.sim2real.reference_wheel_order=["FL_foot_joint"]')
uv run python scripts/pace/fit.py --task "$task" "${groups[@]}" env.sim2real.data_dir=wheel.pt
uv run python scripts/pace/data_collection.py --task "$task" --fit_result --trajectory_file "data/$task/wheel.pt" "${groups[@]}"
uv run python scripts/pace/data_collection.py --task "$task" --fit_result --duration 1 --plot
uv run python scripts/pace/plot_trajectory.py --task "$task" --plot_trajectory
```

Each actuator group containing a recorded joint receives the shared delay across its members. The other groups keep their default delay. Unrecorded position joints hold their default physical angles minus their default encoder biases. Unrecorded wheels hold their default velocities. A v3 record stores these targets and the participating drive membership. File replay reports changed holding targets and uses their current values. Supply the new file's column order when validating independent measurements. Generated sweeps use named coefficients and show command tracking. Joints without known coefficients require a trajectory file.
