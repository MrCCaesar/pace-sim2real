# PACE 机器人关节动力学辨识

PACE 用 CMA-ES 从期望轨迹和实测响应中辨识关节惯量、阻尼、摩擦、位置编码器偏置和执行器延迟。可以拟合整机，也可以只记录一条腿、一个轮或跨腿的关节组合。辨识后，可用原记录复现最佳候选的响应，再用另一条实测轨迹评估预测误差。

| 要完成的工作 | 入口 | 结果 |
| --- | --- | --- |
| 用固定参数采集腿部位置和轮速 | `scripts/pace/data_collection.py --task 任务名` | `data/<任务名>/chirp_data.pt` |
| 用原生 MuJoCo 采集 X5 传感器数据 | `scripts/pace/data_collection_mujoco.py` | `data/Isaac-Pace-Sevnce-X5-v0/mujoco_chirp_data.pt` |
| 对采集记录离线滤波 | `scripts/pace/filter_chirp_data.py 输入文件` | 默认在同目录保存 `<原文件主名>_filtered.pt` |
| 从采集或实机记录中辨识参数 | `scripts/pace/fit.py --task 任务名` | 运行目录中的 `best_result.pt` 和优化日志 |
| 把估计参数写回仿真，验证其他轨迹 | `scripts/pace/replay.py --task 任务名` | 仿真响应，可绘图或另存 |
| 查看已完成的拟合 | `scripts/pace/plot_trajectory.py`、TensorBoard | 逐关节响应、评分、参数分布和均值 |

## 安装与模型准备

当前项目依赖 **Isaac Lab 3.0 和 Python 3.12**。`uv` 从项目的同级目录 `../IsaacLab` 加载框架源码。默认物理后端 Newton MJWarp 可独立运行。选择基于 Kit 的 `isaacsim_physx` 时，Isaac Lab 3.0 对应 Isaac Sim 6.2。[依赖声明](pyproject.toml) · [锁定版本](uv.lock)

在两个仓库的共同父目录执行以下命令。示例中的 Isaac Lab 提交对应本项目当前使用的 3.0.0 源码。

```bash
git clone https://github.com/isaac-sim/IsaacLab.git IsaacLab
git -C IsaacLab checkout ae63302486bb92fc865f1fd8449b91a53728184c
git clone https://github.com/MrCCaesar/pace-sim2real.git
cd pace-sim2real
uv sync --locked --python 3.12
cat ../IsaacLab/VERSION
```

以下示例均在项目根目录执行。选择可选后端时，可用 `uv run --extra isaacsim …` 或 `uv run --extra ovphysx …` 为该命令启用对应依赖。

| Isaac Lab 任务名 | 辨识通道 | 模型准备 |
| --- | --- | --- |
| `Isaac-Pace-Anymal-D-v0` | 12 个腿关节，跟踪位置 | 使用 Isaac Lab 的 ANYmal D 资产 |
| `Isaac-Pace-Sevnce-X3mini-v0` | 12 个腿关节跟踪位置，4 个轮关节跟踪速度 | Isaac Lab 读取本地 `src/pace_sim2real/assets/data/robots/sevnce/x3mini/usd/x3mini.usd` |
| `Isaac-Pace-Sevnce-X5-v0` | 12 个腿关节跟踪位置，4 个轮关节跟踪速度 | 本地准备 X5 的 USD、MJCF 和相应网格。Isaac Lab 读取 `src/pace_sim2real/assets/data/robots/sevnce/x5/usd/x5.usd`，原生 MuJoCo 默认读取该机器人目录下的 `mjcf/x5_calibration.xml` |

## 快速跑通采集、拟合和回放

以下示例用 X5 采集 1 秒数据，在两个并行环境中拟合最多 3 代，再回放同一条轨迹。要使用纯腿的 ANYmal D，可将首行任务名改为 `Isaac-Pace-Anymal-D-v0`。

```bash
task=Isaac-Pace-Sevnce-X5-v0
uv run python scripts/pace/data_collection.py --task "$task" --visualizer none --duration 1
uv run python scripts/pace/fit.py --task "$task" --num_envs 2 env.sim2real.cmaes.max_iteration=3
uv run python scripts/pace/replay.py --task "$task" --visualizer none \
  --trajectory_file "data/$task/chirp_data.pt" --output "data/$task/replay.pt"
```

第一条命令写入 `data/$task/chirp_data.pt`，第二条默认读取该文件。第三条读取本次拟合的最佳候选，打印预测与实测之间的位置和轮速均方根误差（RMSE），并把预测轨迹另存为 `replay.pt`。

已有采集或实机记录时，可以直接从拟合开始。选择文件时注意两个入口的路径规则。

| 入口 | 如何指定参考记录 | 路径从哪里解析 |
| --- | --- | --- |
| 拟合 | `env.sim2real.data_dir=实验文件.pt` | 相对路径从 `data/<任务名>/` 解析。设置 `PACE_ROOT` 可更换数据根目录 |
| 文件回放 | `--trajectory_file data/<任务名>/实验文件.pt` | 相对路径从运行命令时的工作目录解析 |

两者都接受绝对路径。同一来源再次成功采集时会替换该来源的默认文件；需长期保存的实验可另用文件名归档。

## 使用 Isaac Lab 采集扫频数据

`data_collection.py` 使用固定基座逐步施加线性扫频指令。只给 `--task` 即使用固定参数采集。腿部 PD 反馈和保存的测量位置都使用 `物理角度 − 编码器偏置`。固定值由 `JointParameters.collection_defaults` 定义。[采集脚本](scripts/pace/data_collection.py) · [固定参数](src/pace_sim2real/utils/fit_replay.py)

| 设置位置 | 参数及默认值 | 用途 |
| --- | --- | --- |
| 命令行 | `--min_frequency 0.1`、`--max_frequency 10.0`、`--duration 20.0` | 起止频率单位为 Hz，时长单位为秒。时长须为控制步长的正整数倍，且 `0 < 起始频率 ≤ 终止频率 < 0.5 / 步长` |
| 命令行 | `--num_envs 1`、`--plot` | 保存第一个环境的响应。加 `--plot` 可在采集结束后绘制曲线 |
| 查看器与物理配置 | `--visualizer newton_gl`、`physics=newton_mjwarp` | 默认开启 Newton 查看器。无窗口采集用 `--visualizer none`。其他物理预设为 `newton_kamino`、`physx`（自动选择）、`ovphysx`、`isaacsim_physx` |
| 设备与录像 | `env.sim.device=cuda:0`、`--video`、`--video_length`、`--video_interval` | 采集设备取自任务配置。录像需要支持相机的渲染配置，可用 `--extra video` 加载录像依赖，长度和间隔按步设置 |
| 固定采集参数 | `armature=0.1`、`damping=4.5`、`friction=0.05` | PhysX 动摩擦取 `0.025`，Newton 使用单一干摩擦。腿编码器偏置为 `0.05 rad`，轮偏置为零，共享延迟为 5 步 |

扫频表达式为 `期望值 = (中心 + sin(相位)) × 幅值 × 方向`。腿部每条腿的三个中心为 `[0, 0.4, -1.4]`（无量纲），幅值为 `[0.25, 0.5, 0.99] rad`。方向同时作用于中心和振荡，右前、右后腿的第一个关节取 `-1`，其余取 `+1`。轮速中心为零，四轮幅值均为 `10 rad/s`，方向均为 `+1`。Isaac Lab 的这些值定义在[共用轨迹模块](src/pace_sim2real/utils/trajectory_simulation.py)中。

只采部分关节时，分别设置位置组和速度组。每组的 `None` 取任务全组，`[]` 跳过该组，显式列表决定输出列序。例如，只采 X3mini 左前轮可运行：

```bash
uv run python scripts/pace/data_collection.py --task Isaac-Pace-Sevnce-X3mini-v0 --visualizer none \
  'env.sim2real.reference_leg_order=[]' 'env.sim2real.reference_wheel_order=["LF_WHEEL"]'
```

该文件含 `time`、`dof_vel` 和 `des_dof_vel`。只有所选轮接收扫频，其余关节沿用部分拟合的保持目标与任务默认参数。固定的 5 步延迟作用于包含选中关节的整个执行器组。拟合及文件回放时使用同一列序声明。

## 使用原生 MuJoCo 采集 X5

原生 MuJoCo 将 X5 传感器记录写入任务目录下的 `mujoco_chirp_data.pt`。下面用这份记录在 Isaac Lab 中拟合，再按原指令回放。采集参数可在 TOML 中设置，命令行的同名参数优先。[采集入口](scripts/pace/data_collection_mujoco.py) · [默认配置](config/x5_collection.toml)

```bash
task=Isaac-Pace-Sevnce-X5-v0
uv run python scripts/pace/data_collection_mujoco.py --config config/x5_collection.toml --duration 1
uv run python scripts/pace/fit.py --task "$task" --num_envs 2 \
  env.sim2real.data_dir=mujoco_chirp_data.pt env.sim2real.cmaes.max_iteration=3
uv run python scripts/pace/replay.py --task "$task" --visualizer none \
  --trajectory_file "data/$task/mujoco_chirp_data.pt" --output "data/$task/mujoco_replay.pt"
```

| 设置位置 | 参数 | 含义与默认值 |
| --- | --- | --- |
| TOML `[run]` | `min_frequency`、`max_frequency`、`duration`、`seed` | 默认 `0.1 Hz` 至 `10 Hz`，持续 `20 s`，测量噪声种子为 `42`。前三项可用同名 `--` 选项覆盖 |
| TOML `[run]` | `visualize=false`、`plot=true` | `--visualize` / `--no-visualize` 控制仿真窗口，`--plot` 开启采集后的曲线图。全程无窗口运行时，在 TOML 中将两项都设为 `false` |
| TOML `[model]`、`[channels]` | `path`、`position_joints`、`velocity_joints` | 模型路径相对于 TOML 所在目录。关节名列表指定输出列顺序，默认按左前、右前、左后、右后排列 |
| TOML `[trajectory]` | `position_centers`、`position_amplitudes`、`position_directions` | 12 个腿关节各设一项，单位及公式与上节相同。方向只能取 `+1` 或 `-1` |
| TOML `[trajectory]` | `velocity_amplitudes`、`velocity_directions` | 4 个轮关节各设一项，幅值单位为 rad/s，方向各自独立 |
| TOML `[measurement]` | `encoder_bias` | 默认 `0.05 rad`，可用标量或按腿关节顺序给出 12 个偏置。腿测量值为传感器读数减偏置再加高斯噪声，轮速仅叠加噪声 |
| MJCF | `timestep`、`damping`、`armature`、`frictionloss`、伺服增益、限幅、`delay`、`nsample`、传感器 `noise` | 当前标定模型固定基座高 1 m，步长 `0.0025 s`，执行器延迟 `0.010 s`，历史缓冲为 4 个样本。位置和速度噪声标准差分别为 `0.01 rad`、`0.1 rad/s`，修改模型后以 XML 为准 |

## 对实测位置和轮速离线滤波

脚本在 CPU 上逐关节处理 `dof_pos` 和 `dof_vel`，支持纯位置、纯速度和混合记录。输出保留全部采样时刻、期望指令、字段、数据类型和列序。默认使用四阶 Butterworth 前后向低通，`--order` 和 `--cutoff_hz` 分别设置单程阶数和单程截止频率。采样率根据以秒为单位的均匀时间戳计算，截止频率须低于采样率的一半。

```bash
task=Isaac-Pace-Sevnce-X5-v0
record=data/$task/mujoco_0.1_10Hz_kp1500_kd30_chirp_data.pt
uv run python scripts/pace/filter_chirp_data.py "$record"
uv run python scripts/pace/filter_chirp_data.py "$record" --cutoff_hz 25 --order 4 --output "data/$task/x5_25Hz.pt"
uv run python scripts/pace/filter_chirp_data.py "$record" --analysis_band_hz 0.1 4 --plot --output "data/$task/x5_band_0.1_4.pt"
uv run python scripts/pace/fit.py --task "$task" env.sim2real.data_dir=mujoco_0.1_10Hz_kp1500_kd30_chirp_data_filtered.pt
```

默认 20 Hz 适用于本例 400 Hz 采样、最高 10 Hz 的扫频。单程截止处经过前后向处理后只保留一半稳态幅值。首尾样本使用奇对称延拓，拟合使用的首帧测量也会随滤波改变。输入和输出路径相对当前目录解析，输出须为新文件；拟合时沿用原记录的位置和速度列序配置。[滤波脚本](scripts/pace/filter_chirp_data.py)

保存后，脚本按位置组和速度组分别打印五项指标。最大峰峰值变化反映整段关节运动范围的变化；跟踪 RMSE 比例以期望指令为参考，90% 表示滤后的整组跟踪 RMSE 为滤前的 90%。有效频点上的最大幅值变化和最大时差变化用于检查受激成分；≥30 Hz 能量的最小降幅给出组内抑制最弱的关节所达到的 dB 值。

`--analysis_band_hz LOW HIGH` 默认取 0.1–10 Hz，只控制频域幅值和时差的分析范围。报告给出有效关节数，两项频域极值还列出有效的关节与频点组合数和频率范围。分母为零、缺少有效频点等情况显示 `N/A` 与原因。默认仅打印；加 `--plot` 后可按组和列号交互查看期望、滤前、滤后三条时间曲线，以及滤前测量在完整可观测频段的单边幅值谱。

## 参考数据与 CMA-ES 拟合

两种采集器写出相同格式的 PyTorch 张量字典。实机数据也按此格式整理。设 `T` 为采样点数（至少 2 个），`L`、`W` 分别为文件中实际记录的位置列数和速度列数。每一行记录施加本步指令时、推进物理仿真前的状态。

| 字段 | 形状与单位 | 内容 |
| --- | --- | --- |
| `time` | `[T]`，秒，双精度 | 两组关节共用的采样时间 |
| `dof_pos`、`des_dof_pos` | 各 `[T, L]`，rad，单精度 | 已记录位置关节的测量角度和延迟前的期望角度。仅记录速度时可省略这两个字段 |
| `dof_vel`、`des_dof_vel` | 各 `[T, W]`，rad/s，单精度 | 已记录速度关节的测量轮速和延迟前的期望轮速。仅记录位置时可省略这两个字段 |

`fit.py` 让每个并行环境评估一组候选参数。`--num_envs` 同时决定种群大小，默认及最小值均为 `2`。默认设备为 `--device cuda`，默认关闭查看器。任务配置可通过 `env.sim2real.字段=值` 覆盖。[共享配置](src/pace_sim2real/tasks/manager_based/pace/pace_sim2real_env_cfg.py) · [ANYmal D 配置](src/pace_sim2real/tasks/manager_based/pace/anymal_pace_env_cfg.py) · [X5 配置](src/pace_sim2real/tasks/manager_based/pace/sevnce_pace_env_cfg.py)

| `env.sim2real` 下的字段 | 如何设置 |
| --- | --- |
| `data_dir` | 默认 `chirp_data.pt` 读取 Isaac Lab 采集数据。X5 原生 MuJoCo 数据使用 `mujoco_chirp_data.pt`。相对路径从 `data/<任务名>/` 解析，也接受绝对路径 |
| `leg_order`、`wheel_order` | 声明机器人完整的位置与速度控制分组。纯腿任务也可沿用 `joint_order` |
| `reference_leg_order`、`reference_wheel_order` | 分别声明文件的位置列和速度列。每组的 `None` 表示按任务组序读取全部关节，`[]` 表示该组无记录，非空列表按文件实际列序写出准确名称。文件本身不保存关节名，两组合计至少一个关节 |
| `time_mode`、`legacy_sample_dt` | 默认 `strict`。采样间隔须等于 `env.sim.dt`，且 `env.decimation=1`。旧时间列需用 `legacy_index` 并显式给出真实采样间隔，该间隔仍须与仿真一致 |
| `reference_bias_model`、`reference_delay_mode` | 偏置模型为 `feedback_and_measurement`。旧版仅在测量端减偏置的 MuJoCo 数据需重新采集。延迟默认作用于指令（`command`），也可作用于力矩（`effort`），声明须与执行器配置一致 |
| `bounds_params` | 每行给出一个参数的上下界。依次放入所有关节的惯量、阻尼、摩擦，仅腿关节的偏置，以及一个共享延迟。各关节块按腿后接轮排序。当前范围依次为 `[0.00001, 1]`、`[0, 7]`、`[0, 0.5]`、`[-0.1, 0.1] rad`、`[0, 10]` 步。上下界相等可固定参数 |
| `separate_dynamic_friction`、`friction_ratio_bounds` | PhysX 可在末尾追加逐关节的动静摩擦比，默认范围 `[0, 1]`，动摩擦等于静摩擦乘该比值。ANYmal D 任务默认开启，X5 默认关闭。Newton 会告警并关闭已启用的比例辨识 |

优化器设置位于 `env.sim2real.cmaes` 下。

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `max_iteration`、`epsilon` | `200`、`0.01` | 最大代数、同代候选评分相对差距的提前停止阈值 |
| `sigma` | `0.5` | 归一化参数空间的初始搜索尺度 |
| `position_error_scale`、`velocity_error_scale` | 各 `1.0` | 可给正标量，也可给逐关节正数列表，长度分别为任务完整的位置、速度关节数，拟合按记录名称抽取并重排。可用各腿的角度范围和各轮的速度范围归一化 |
| `position_weight`、`velocity_weight` | 各 `1.0` | 两组的正权重。每组先对各关节的 `MSE / scale²` 求平均，再按参与组的权重加权平均得到总评分。日志中的 RMSE 仍以 rad、rad/s 表示 |
| `save_interval`、`save_optimization_process` | `10`、`false` | 每隔指定代数保存分布均值，设为 `0` 可关闭均值快照。开启过程保存后可离线绘制评分曲线 |

例如，对 X5 使用逐轮速度尺度并保存评分历史，运行以下命令。

```bash
uv run python scripts/pace/fit.py --task Isaac-Pace-Sevnce-X5-v0 --num_envs 2 \
  'env.sim2real.cmaes.velocity_error_scale=[10,10,10,10]' \
  env.sim2real.cmaes.save_optimization_process=true
```

### 拟合部分关节

假设已有 `data/Isaac-Pace-Sevnce-X5-v0/fl.pt`，位置列依次为左前髋、大腿、小腿，速度列为左前轮。保留任务的完整控制分组，在 Bash 中用同一组列名拟合并回放这份文件。

```bash
task=Isaac-Pace-Sevnce-X5-v0
groups=('env.sim2real.reference_leg_order=["FL_hip_joint","FL_thigh_joint","FL_calf_joint"]'
        'env.sim2real.reference_wheel_order=["FL_foot_joint"]')
uv run python scripts/pace/fit.py --task "$task" "${groups[@]}" env.sim2real.data_dir=fl.pt
uv run python scripts/pace/replay.py --task "$task" --visualizer none \
  --trajectory_file "data/$task/fl.pt" "${groups[@]}"
```

若 `wheels.pt` 只记录四个轮速，且速度列按任务的 `wheel_order` 排列，只需声明位置组为空。文件包含 `time`、`dof_vel`、`des_dof_vel`，拟合只计算速度误差。

```bash
uv run python scripts/pace/fit.py --task Isaac-Pace-Sevnce-X5-v0 \
  'env.sim2real.reference_leg_order=[]' env.sim2real.data_dir=wheels.pt
```

独立验证轨迹按自身列序声明。位置组与速度组的成员须分别与拟合结果一致，组内可以重排。

未记录关节的保持目标取自任务的 `ArticulationCfg.init_state`。位置关节保持默认物理角减默认编码器偏置，首速为零。速度关节保持默认速度，从默认角度启动。其机械参数沿用任务默认值。每个包含已记录关节的执行器组整体使用同一个候选延迟。例如将四条腿配置为四个驱动组时，单腿记录只更新对应组的延迟。改变保持工况后，回放按关节报告旧值、新值和单位，使用新目标运行。

## 用拟合结果验证其他轨迹

`replay.py` 会把最佳候选的物理参数、腿编码器偏置和共享延迟写入仿真。省略轨迹文件时，对已辨识关节生成新扫频，可观察指令跟踪效果。若关节缺少已知扫频系数，需提供 `--trajectory_file`。提供独立实测记录时，程序计算预测相对实测的误差。[回放参数校验](src/pace_sim2real/utils/fit_replay.py)

| 命令行选项 | 行为 |
| --- | --- |
| `--fit_result` 或 `--fit_result 路径` | 省略此选项或单独给标志时读取 `logs/pace-sim2real/<任务名>/` 最新时间戳运行下的 `best_result.pt`，该运行缺文件会报错。给路径时读取指定文件。结果须为含统一 `dt` 的配对结果，物理后端、求解器、延迟模式和各组关节名须匹配，组内顺序可按名称还原 |
| `--duration`、`--min_frequency`、`--max_frequency` | 用新扫频测试最佳候选，`--plot` 对比期望与预测 |
| `--trajectory_file 路径` | 使用参考文件中的期望轨迹，并根据首帧测量初始化。此选项与显式扫频参数互斥。程序打印预测相对实测的位置及轮速 RMSE，`--plot` 可同时显示期望、参考测量和预测 |
| `--output 路径` | 回放默认只计算结果。给出独立输出路径后保存响应，输入记录、拟合结果和默认采集文件受覆盖保护 |

```bash
uv run python scripts/pace/replay.py --task Isaac-Pace-Sevnce-X5-v0 \
  --duration 3 --min_frequency 0.2 --max_frequency 4 --visualizer none --plot
```

## 离线绘图与优化诊断

全量且含位置组的配对结果使用 v2，部分关节或纯速度结果使用 v3。v3 还保存任务完整关节分组、未记录关节的保持目标，以及参与延迟的驱动组。TensorBoard 和离线图按本次记录的关节展示参数、响应和分组误差。

每次拟合在 `logs/pace-sim2real/<任务名>/<时间戳>/` 写入一套结果。`best_result.pt` 保存全程实际评估过的最佳候选及其配对响应、参考轨迹和误差。`config.pt` 保存拟合配置和参考数据，`mean_*.pt` 保存指定代的分布均值，`progress.pt` 在启用过程保存时生成。

```bash
uv run python scripts/pace/plot_trajectory.py --task Isaac-Pace-Sevnce-X5-v0 --plot_trajectory
uv run python scripts/pace/plot_trajectory.py --task Isaac-Pace-Sevnce-X5-v0 --plot_score
uv run tensorboard --logdir logs/pace-sim2real
```

- `--plot_trajectory` 按关节绘制已保存的响应。`--plot_score` 读取 `progress.pt` 绘制每代最低评分。离线脚本默认选取含所需文件的最新运行，可用 `--folder_name` 指定运行目录，用 `--result_name` 指定配对结果文件。
- `--mean_name mean_010.pt` 可单独查看该代分布均值。均值只用于诊断，因此不能与 `--plot_trajectory` 或 `--result_name` 合用。
- TensorBoard 每代记录参数直方图、当代最佳候选参数、搜索分布均值、共享延迟、评分差距和分组 RMSE。拟合结束前也可打开日志查看收敛过程。

## 文献、许可与贡献

PACE 的原始工作来自苏黎世联邦理工学院机器人系统实验室。研究中使用本方法时，请引用 F. Bjelonic、F. Tischhauser 和 M. Hutter 于 2026 年发表的论文。[期刊论文](https://doi.org/10.1177/02783649261459628) · [开放获取版本](https://arxiv.org/abs/2509.06342)

项目采用 Apache 2.0 许可证。提交问题、改进建议或代码前可参阅贡献说明。[许可证](LICENSE) · [贡献指南](CONTRIBUTING.md)
