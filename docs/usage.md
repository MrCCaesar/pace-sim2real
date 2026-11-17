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

This utility visualises the optimized trajectory and/or the evolution of the score over iterations. If no `folder_name` argument is given, the script will use the most recent evolution.

### Common arguments

| Argument            | Description                                     |
| ------------------- | ----------------------------------------------- |
| `--folder_name`     | Name of the optimization output folder          |
| `--result_name` | Paired evaluated result (default `best_result.pt`) |
| `--mean_name` | Distribution mean diagnostics only; not a trajectory selector |
| `--robot_name`      | Name of the robot                               |
| `--plot_trajectory` | Plot the optimized joint trajectories           |
| `--plot_score`      | Plot the score over iterations                  |

### Example

```bash
python scripts/pace/plot_trajectory.py \
  --folder_name 24_03_12_14-32-10 \
  --robot_name anymal_d_sim \
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

Reference declarations belong in PaceCfg: `reference_leg_order`/`reference_wheel_order` (None adopts task order), `reference_bias_model="feedback_and_measurement"`, `reference_delay_mode="command"` (must match the task), `time_mode="strict"`, and `legacy_sample_dt=None`. Strict time intervals must match control dt. Historical linspace files require `time_mode="legacy_index"` and an explicit true interval; no automatic resampling. Old native data using measurement-only bias is unsupported and must be recollected. No metadata sidecar is created. Declaring a file's semantics does not prove that declaration is correct.

For J=L+W joints, parameters are armature[J], damping[J], friction[J], leg encoder bias[L], one delay; optionally append PhysX friction ratios[J]. X5 has61 base parameters, a12-leg task49. Newton warns and disables separate dynamic-friction identification during configuration validation, removing its ratio bounds before constructing CMA. Delay is floored to integer physics steps; the configured drive capacities must cover its upper bound, including control decimation. Wheel initial speed comes from the first measurement; missing wheel angle/leg velocity comes from task defaults and is recorded in the result.

CMA settings `position_error_scale`/`velocity_error_scale` default to1 rad/1 rad/s. `position_weight`/`velocity_weight` default to1. Each group contributes its normalized mean-square error, then weights are normalized across present groups. Raw group RMSE is reported separately. These scales are not accuracy thresholds. Population must be at least2 (the resource-safe default); small populations can produce upstream CMA warnings. Controlled validation uses4, not full-scale training.

The primary artifact is `best_result.pt`, schema_version2: evaluated global-best parameters, matching measured-frame responses, group errors, candidate identity, reference tensors, original/effective time, configuration and actual delay. Distribution `mean_*.pt` artifacts are diagnostic only. Plotting loads the paired record and recomputes errors; it does not subtract position bias twice or pair a historical mean with a latest trajectory. Older unpaired results cannot establish correspondence and are rejected for trajectory comparison. `--mean_name` can still inspect mean parameters alone. Select the run directory and the same task log name used by fitting when invoking the plot script.

Software tests establish behavior on bounded minimal models. Successful execution does not certify collision geometry, full-model physical fidelity or unique identification of all parameters.

PACE collection and fitting send absolute targets: configure actions with `scale=1.0`, `offset=0.0`, `clip=None`, and `use_default_offset=False`. Action mapping only reorders named columns; it does not inspect or undo task transforms. Collection timestamps are seconds (`sample_index * env.step_dt`), with samples before each step; the last sample precedes `duration` by one control interval. Commands and device buffers are prepared once, then completed measurements are transferred to CPU. Numerical validity is checked across all buffered states, including the final state, before saving.

Collection and fitting register their runtime CLI flags locally, without loading Isaac Sim. Newton therefore needs no Kit EULA variable merely to parse arguments or start a kitless run. `physics=...` and `--visualizer`/`--viz` remain Isaac Lab preset selectors; `launch_simulation` starts Kit only when the resolved physics, renderer or viewer requires it. Explicit Isaac Sim PhysX or Kit visualization still requires the installed runtime and its license acceptance.

Fitting prepares commands once, keeps timestamp checks on CPU and reuses device state buffers across generations. Scoring occurs after a complete valid rollout; automatic termination still stops immediately. `CMAESOptimizer.tell` accepts both individual `[population, joints]` samples and `[population, samples, joints]` chunks, with the same bias and group-loss semantics. Full-state fitting buffers require 8*(samples+1)*population*robot_joints bytes in addition to optimizer/reference storage.
