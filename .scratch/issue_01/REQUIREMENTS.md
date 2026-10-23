# Issue #1 需求规格

## 来源与范围

- Issue: `MrCCaesar/pace-sim2real#1` - "Fix compatibility issues introduced by the Isaac Lab version upgrade."
- Issue 原文要求：将 Isaac Lab 依赖升级到 3.0.0，在 Ubuntu 24.04 上使用，并保持原有功能。
- 已确认的功能范围：REQ-I03 至 REQ-I08。
- 已确认的 Isaac Lab 基线：直接使用当前系统中的 `~/IsaacLab`，不以其他发布版本替换。
- 已确认的包版本：保持 `0.2.0`。
- 已确认的平台范围：保留 `pyproject.toml` 当前声明的 Linux x86_64、Linux aarch64 和 Windows AMD64。
- 已确认的验收方式：不要求与旧版本进行数值等价比较；CMA-ES 只验证流程和产物，不要求 score 收敛到特定阈值。
- 已确认的功能验收后端：Isaac Sim + PhysX；Newton 和 OV PhysX 仍保留为可选后端，但不是本 Issue 的验收前提。
- 已确认的修改边界：允许进行 Isaac Lab 3.0 兼容性所需的机械性 API 替换和配置结构调整，不改变算法、默认参数、参数顺序、日志结构和业务行为。
- 已确认的测试方式：使用短时 smoke 参数；纯 Python/API 行为使用自动化测试；GPU 工作流使用可重复执行的 smoke 命令。
- 已确认的告警边界：deprecation warning 不构成验收失败；异常、错误退出或功能缺失才构成失败。
- 已确认的产物策略：本次 smoke 新增的 `data/`、`logs/` 和 checkpoint 在断言完成后清理，不删除运行前已存在的文件。
- 本阶段不修改业务代码。

## 验证环境说明

- 当前操作系统为 Ubuntu 24.04.5 LTS。
- 项目声明并要求 Python `>=3.12,<3.13`。
- 当前 `~/IsaacLab` checkout 的 `HEAD` 为 `f847b1cbb6e9128f4d5f65fcb83b686650072a99`，已安装包的 metadata 版本为 `isaaclab 40.0.0`。
- 用户已确认当前机器有 GPU。但当前 Codex 进程无法访问 NVIDIA 驱动：`nvidia-smi` 无法通信，`torch.cuda.is_available()` 返回 `False`。GPU 端到端验收必须在能够访问 GPU 的主机终端中执行。
- 当前仓库没有可用于系统辨识的 `data/anymal_d_sim/chirp_data.pt`，也没有可用于回放的 RSL-RL checkpoint。这些属于验收运行前需要生成的输入。

---

## REQ-I01：Isaac Lab 基线与环境平台

### Requirement ID

`REQ-I01`

### 初始条件

- 机器运行 Ubuntu 24.04。
- Python 版本满足 `>=3.12,<3.13`。
- 当前机器具备 NVIDIA GPU，且验收终端能够访问 NVIDIA 驱动。
- 当前系统存在 `~/IsaacLab` 源码 checkout。
- 项目位于 `~/IsaacLab` 之外，并通过相对路径 `../IsaacLab` 引用 Isaac Lab。

### 输入/触发条件

- 在项目根目录执行 `uv sync --locked`。
- 检查 Python、Isaac Lab 安装位置和版本。

### 可观察行为

- Uv 使用项目虚拟环境。
- Isaac Lab 包解析到当前 `~/IsaacLab` 源码 checkout，而不是下载其他版本或使用无关环境中的安装。
- 项目保留当前 `[tool.uv.sources]` 中的本地 editable source 映射。

### 验收标准

- `uv sync --locked` 退出码为 0。
- `uv pip show isaaclab` 显示 editable 安装位置为 `~/IsaacLab/source/isaaclab`。
- `import isaaclab` 可执行。
- 验证环境中的 Python 满足项目声明的版本范围。
- 验收终端中的 `torch.cuda.is_available()` 返回 `True`，且 `torch.cuda.device_count()` 大于 0。
- 不要求将当前 Isaac Lab checkout 升级或替换为其他远端 tag。
- 保留 `pyproject.toml` 中现有的 Linux x86_64、Linux aarch64 和 Windows AMD64 平台声明。

### 尚不明确的问题

- 无。

---

## REQ-I02：Uv 安装、包元数据和依赖完整性

### Requirement ID

`REQ-I02`

### 初始条件

- 项目根目录存在 `pyproject.toml` 和 `uv.lock`。
- `../IsaacLab` 路径存在。
- 项目虚拟环境可以由 Uv 在全新的 `.venv` 中创建。

### 输入/触发条件

- 在全新的项目虚拟环境中执行 `uv sync --locked`。
- 执行 `uv sync --check --locked`。
- 查询 `pace-sim2real` 的发行包元数据和导入位置。

### 可观察行为

- `pace-sim2real` 以 editable 包形式安装。
- 发行包版本为 `0.2.0`。
- 运行依赖包含 `isaaclab-dev`、`cmaes` 和 `psutil`。
- Python 模块名为 `pace_sim2real`，源码来自根目录 `src/pace_sim2real`。

### 验收标准

- `uv sync --locked` 和 `uv sync --check --locked` 均退出码为 0。
- `uv pip show pace-sim2real` 显示版本 `0.2.0`。
- `uv pip show pace-sim2real` 的 editable location 为项目根目录。
- `importlib.metadata.version("pace-sim2real")` 返回 `0.2.0`。
- `import pace_sim2real` 成功，且 `pace_sim2real.__file__` 位于项目的 `src/pace_sim2real` 下。
- `uv.lock` 与 `pyproject.toml` 一致。

### 尚不明确的问题

- 无。

---

## REQ-I03：公共 API 与 Gym 任务注册

### Requirement ID

`REQ-I03`

### 初始条件

- REQ-I01 和 REQ-I02 已满足。
- Isaac Lab Python 包可导入。
- 调用方准备一个有效的 PACE 环境配置，例如 `AnymalDPaceEnvCfg`。

### 输入/触发条件

- 导入 `pace_sim2real`。
- 导入 `pace_sim2real.utils`。
- 导入 `pace_sim2real.tasks`。
- 查询 Gymnasium registry 和 `isaaclab.tasks` entry point。
- 使用调用方提供的 `AnymalDPaceEnvCfg` 创建 `Template-Pace-Sim2real-v0` 环境，并执行 reset 和 step。

### 可观察行为

- 文档声明的公共符号可以导入。
- PACE 任务被注册到 Gymnasium。
- `Template-Pace-Sim2real-v0` 接受调用方提供的有效环境配置并运行。

### 验收标准

- 以下符号均可导入：
  - `PaceSim2realEnvCfg`
  - `PaceSim2realSceneCfg`
  - `PaceCfg`
  - `CMAESOptimizer`
  - `PaceDCMotorCfg`
  - `PaceDCMotor`
- Gymnasium registry 中存在：
  - `Isaac-Pace-Anymal-D-v0`
  - `Template-Pace-Sim2real-v0`
- 使用调用方提供的 `AnymalDPaceEnvCfg` 创建 `Template-Pace-Sim2real-v0` 后，能够执行 `reset()` 和至少一次 `step()`。
- 模板任务不新增内置默认 robot，不改变原有 `robot=MISSING` 的模板语义。
- `isaaclab.tasks` entry point `pace_sim2real` 指向 `pace_sim2real.tasks`。

### 尚不明确的问题

- 无。

---

## REQ-I04：ANYmal PACE 环境配置与仿真运行

### Requirement ID

`REQ-I04`

### 初始条件

- REQ-I01 和 REQ-I02 已满足。
- 在能够访问 GPU 的主机终端中运行。
- Isaac Sim 和 PhysX 已通过 `--extra isaacsim` 安装并可运行。

### 输入/触发条件

- 实例化 `AnymalDPaceEnvCfg`。
- 通过 Gymnasium 创建 `Isaac-Pace-Anymal-D-v0` 环境。
- 以 headless、`num_envs=1` 运行，并执行环境 reset 和 1 次 step。

### 可观察行为

- 环境配置可以通过 Isaac Lab 3.0 API 完成实例化。
- ANYmal 场景、关节、执行器和 PACE 参数配置成功创建。
- 环境可以执行 reset 和 step，不出现属性、类型或 API 不兼容错误。

### 验收标准

- `AnymalDPaceEnvCfg()` 实例化成功。
- 环境配置包含 12 个按 `joint_order` 定义的 ANYmal 关节。
- `sim.dt` 为 `0.0025`，`decimation` 为 `1`。
- `separate_dynamic_friction=True` 时，环境初始化后的优化参数数量为 61。
- Gymnasium 环境可以使用 Isaac Sim + PhysX、`num_envs=1` 创建并重置。
- 环境可以完成 1 次 step。
- reset 后的动作和观测可正常生成；执行 step 后不出现异常，观测值不包含意外 NaN 或 Inf。
- 不要求特定轨迹、奖励或动力学响应与旧 Isaac Lab 版本逐元素或数值等价。

### 尚不明确的问题

- 无。

---

## REQ-I05：PACE 执行器模型行为

### Requirement ID

`REQ-I05`

### 初始条件

- `PaceDCMotor` 和 `PaceDCMotorCfg` 可导入。
- 存在确定性的控制动作、关节位置和关节速度输入。

### 输入/触发条件

- 使用 `delay_mode="command"`、`delay_mode="effort"` 和零延迟配置分别构造执行器行为。
- 设置 encoder bias。
- 设置静态摩擦和动态/静态摩擦比例。

### 可观察行为

- `"command"` 模式延迟位置、速度和前馈力矩目标。
- `"effort"` 模式延迟计算出的关节力矩。
- Encoder bias 作用于执行器控制所使用的位置测量。
- 动态摩擦由静态摩擦乘以比例得到，并且不超过静态摩擦。

### 验收标准

- `PaceDCMotorCfg` 可以实例化并被 PACE 执行器使用。
- 两种 `delay_mode` 均能运行。
- 无效 `delay_mode` 被拒绝。
- 零延迟时，延迟缓冲行为与无延迟输入一致。
- 非零延迟时，输出按文档定义的通道延迟。
- Encoder bias 和摩擦比例行为符合上述语义。
- 可脱离仿真器的确定性行为由自动化测试覆盖。
- 为适配 Isaac Lab 3.0 可以替换机械性 API，但不改变算法、默认参数或参数顺序。
- 不要求与 Isaac Lab 2.x 输出进行数值或逐元素比较。

### 尚不明确的问题

- 无。

---

## REQ-I06：激励数据采集流程

### Requirement ID

`REQ-I06`

### 初始条件

- REQ-I04 已满足。
- 在能够访问 GPU 的主机终端中运行。
- 项目根目录可写。

### 输入/触发条件

- 执行 `scripts/pace/data_collection.py`。
- 使用 `num_envs=1`、`duration=0.1` 秒、默认频率范围 `0.1–10 Hz` 和 `cuda:0`。
- 在验收进程中设置 `MPLBACKEND=Agg`，但不修改脚本自身的绘图逻辑。

### 可观察行为

- 脚本启动 ANYmal PACE 环境。
- 脚本应用 chirp 激励、执行完整轨迹并关闭环境。
- 脚本生成 `data/anymal_d_sim/chirp_data.pt`。

### 验收标准

- 脚本退出码为 0。
- 输出文件存在且可以用 `torch.load` 加载。
- 输出文件包含 `time`、`dof_pos`、`des_dof_pos`。
- 三个序列的时间维长度一致。
- 关节维长度为 12。
- 保存的数据中没有意外 NaN 或 Inf。
- 不要求图表内容或具体轨迹与旧版本一致。
- 原有 `plt.show()` 代码保持不变；Agg 后端使其在自动化验收中不会阻塞。
- 若本次验收还执行后续 I07，则先保留该数据供 fit 使用，并在整个 smoke 流程结束后清理。

### 尚不明确的问题

- 无。

---

## REQ-I07：CMA-ES 系统辨识与结果产物

### Requirement ID

`REQ-I07`

### 初始条件

- REQ-I06 已生成符合格式要求的 `chirp_data.pt`。
- 在能够访问 GPU 的主机终端中运行。

### 输入/触发条件

- 执行 `scripts/pace/fit.py`。
- 使用 `num_envs=2`、`max_iteration=1` 和 `cuda:0`。
- 执行 `scripts/pace/plot_trajectory.py` 读取生成结果。
- 在验收进程中设置 `MPLBACKEND=Agg`。

### 可观察行为

- CMA-ES 完成参数采样、仿真 rollout、评分和迭代更新。
- 优化日志和 checkpoint 写入 `logs/pace/anymal_d_sim`。
- 绘图脚本可以读取最新一次运行的结果。

### 验收标准

- fit 流程正常退出，不出现校验失败或 API 不兼容异常。
- 运行目录中存在并可以重新加载：
  - `config.pt`
  - `best_trajectory.pt`
  - 至少一个 `mean_*.pt`
  - TensorBoard 输出
- 配置文件中的 bounds、joint order、时间序列和摩擦模式的形状与配置一致。
- 绘图脚本能找到最新参数文件，并完成轨迹和/或 score 产物的读取。
- 绘图流程正常执行并打印完成信息，但不要求生成持久化图片文件。
- 不要求最终 score 达到特定阈值。
- 不要求收敛到特定精度，也不要求满足特定运行时长。
- 整个 smoke 流程结束后清理本次新增的 `data/`、`logs/` 和相关 checkpoint。

### 尚不明确的问题

- 无。

---

## REQ-I08：RSL-RL 训练与回放流程

### Requirement ID

`REQ-I08`

### 初始条件

- REQ-I03 和 REQ-I04 已满足。
- `rsl-rl-lib` 及其 Isaac Lab 3.0 集成可导入。
- 在能够访问 GPU 的主机终端中运行。

### 输入/触发条件

- 加载 PACE 的 RSL-RL agent 配置。
- 使用 `scripts/rsl_rl/train.py`、`num_envs=1` 和 `max_iterations=1` 执行短训练。
- 使用生成的 checkpoint，以 `--video --video_length=1` 执行 `scripts/rsl_rl/play.py`。

### 可观察行为

- RSL-RL agent 配置可加载。
- 训练环境可以创建并执行至少一次学习迭代。
- 训练日志和 checkpoint 生成。
- play 脚本可以加载 checkpoint、创建推理策略并执行环境 step。

### 验收标准

- `PPORunnerCfg` 可以导入和实例化。
- train 流程正常退出并生成日志及 checkpoint。
- play 流程能够找到 checkpoint、加载模型并完成 1 步回放。
- play 流程使用 `--video --video_length=1` 执行 1 步后自动退出。
- 策略导出或推理路径不出现 API 不兼容错误。
- 不要求达到特定训练 reward、policy 性能或收敛指标。
- 训练和 play 产生的本次新增日志、checkpoint 和视频在断言完成后清理。

### 尚不明确的问题

- 无。

---

## 范围外与暂不变更项

- 不要求将 PACE 动力学输出与 Isaac Lab 2.x 做数值等价回归。
- 不要求 CMA-ES 达到文档中的历史 score 或运行时间。
- 本阶段不修改 `src/` 下的业务代码。
- 实现阶段允许进行 Isaac Lab 3.0 兼容性所需的机械性 API 和配置结构调整，但不得改变原有业务逻辑、默认语义或参数顺序。
- deprecation warning 不构成验收失败；异常、错误退出和功能缺失才构成失败。
- smoke 产物在断言完成后清理；只删除本次验收新增的文件，不删除已有数据和日志。
- 本次需求确认不包含安装文档、教程路径和截图的大范围重写；若实现需要更新命令才能完成安装验证，应作为独立变更提出。

## 当前已知实现风险

- `AnymalDPaceEnvCfg()` 当前因 Isaac Lab 3.0 `articulation_props` 结构变化失败。
- `PPORunnerCfg` 当前因 `RslRlPpoActorCriticCfg` 不再导出而无法加载。
- `Template-Pace-Sim2real-v0` 保持调用方提供配置的模板语义；验收时传入 `AnymalDPaceEnvCfg`。
- 当前 `.venv` 未安装 `isaacsim`，运行 GPU 验收前需同步 `--extra isaacsim`。
- PACE 脚本使用已在 Isaac Lab 3.0 中标记为 deprecated 的 `AppLauncher`；允许 warning，但要求原有流程仍可运行。
- 当前进程无法访问 GPU，因此 REQ-I04 至 REQ-I08 的运行时验收需要在可见 GPU 的终端中执行。
